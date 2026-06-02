#!/usr/bin/env python3
"""
Streak-At-Risk Sender (PupShape)

Fires when a user has a streak ≥ 3 days AND hasn't logged anything
today AND it's already past 18:00 in their local time. Loss aversion
peaks here — the user can still save the streak with one tap.

The Flutter app's `UsageMirrorService` writes
`users.{uid}.usage.streak.current` + `users.{uid}.usage.streak.
lastSessionDay` on every Today refresh, so we read both:
- `streak.current >= 3`
- `streak.lastSessionDay != today_local_to_user`

We don't have each user's timezone (PupShape doesn't collect it yet);
we use UTC as a stand-in, which is close enough for the 18:00 cutoff
within a few-hour window. Worth threading device tz through the
usage mirror in a follow-up.

State cache: cache/pupshape_streak_at_risk_state.json keyed by
(uid, day) so the email fires once per save-the-streak window.
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from pupshape_users_loader import (
    get_access_token, load_all_users, is_paid,
)
from pupshape_template_translator import get_localized
from pupshape_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'pupshape_streak_at_risk'
DEEP_LINK = 'pupshape://today'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'pupshape_streak_at_risk_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': "{{dog_name}}'s {{streak}}-day streak ends at midnight",
    'body': [
        "{{first_name}}. {{dog_name}}'s {{streak}}-day streak is one tap from a reset.",
        "Log one meal — that's all it takes. The streak survives, the engine keeps its rhythm, and {{dog_name}} doesn't notice (but the plan does).",
        "P.S. We never send this more than once per close call. If you let the streak go tonight, the next one starts at 1 tomorrow — nothing is lost forever.",
    ],
    'cta': 'Save the streak',
}


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'days': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _ref(email):
    return hashlib.sha256(
        f"{_REF_SALT}:{email.lower().strip()}".encode()
    ).hexdigest()[:16]


def _today_key() -> str:
    n = datetime.now(timezone.utc)
    return f'{n.year}-{n.month:02d}-{n.day:02d}'


def _is_after_18_utc() -> bool:
    return datetime.now(timezone.utc).hour >= 18


def main(dry_run=False):
    # Skip entirely if it's still morning UTC — most users aren't yet
    # in the "save the streak" window. Avoids burning Firestore reads
    # when we can't fire anything.
    if not _is_after_18_utc():
        print('🕒 Pre-18:00 UTC — streak window not open yet, skipping')
        return

    state = _load_state()
    state.setdefault('days', {})
    today = _today_key()
    if today not in state['days']:
        state['days'][today] = {}

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    print('🔎 Walking users for at-risk streaks...')
    targets = []
    for user in load_all_users(token):
        if user['uid'] in state['days'][today]:
            continue
        streak = user.get('streak') or {}
        current = int(streak.get('current') or 0)
        if current < 3:
            continue
        last_day = (streak.get('lastSessionDay') or '').strip()
        if last_day == today:
            continue  # Already logged today.
        dogs = user.get('dogs') or []
        if not dogs:
            continue
        targets.append((user, dogs[0], current))

    print(f'🔥 {len(targets)} streaks at risk tonight')
    if not targets:
        return

    if dry_run:
        for u, d, s in targets[:25]:
            print(f"   • {u['email']}  {d['name']}  streak={s}  lang={u['language']}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, streak in targets:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name': user.get('first_name', ''),
            'dog_name':   dog.get('name', 'your pup'),
            'streak':     str(streak),
        }
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCE['cta']), ctx)

        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='urgent',
            dog_image_url=dog.get('image_url') or '',
            dog_name=dog.get('name', ''),
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
            {'name': 'streak', 'value': str(streak)},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['days'][today][user['uid']] = {
                'sent_at': datetime.now().isoformat(),
                'streak': streak,
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  streak={streak}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
