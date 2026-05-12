#!/usr/bin/env python3
"""
Streak-at-Risk Sender (Thesis Generator)

Sends one personalized email when the user has a streak ≥ 3 days and
hasn't been active for ≥ 18 hours. Loss-aversion trigger that mirrors
the in-app streak-at-risk push notification.

Reads `users.{uid}.streak.{current, last_active_at}` written by
`streak_service.dart` (`_mirrorToFirestore`). Users without the streak
field are silently skipped — no false alarms.

Localized for all 20 app languages via DeepSeek (first send per language
triggers a one-shot translation that gets cached).
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from thesis_users_loader import get_access_token, load_all_users, is_paid
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
KIND = 'streak_at_risk'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'streak_at_risk_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': "Don't lose your {{streak}}, {{first_name}}",
    'body': [
        "You're on a {{streak}} 🔥 — and you're one inactive day away from losing it.",
        "Two minutes in the app keeps it alive. Open it now and the counter goes up tomorrow.",
    ],
    'cta': 'Keep my streak alive',
}


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'users': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _ref(email):
    return hashlib.sha256(f"{_REF_SALT}:{email.lower().strip()}".encode()).hexdigest()[:16]


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    candidates = []
    for u in load_all_users(token):
        s = u.get('streak') or {}
        current = s.get('current')
        last = s.get('last_active_at')
        if not current or current < 3 or not last:
            continue
        if (now - last) < timedelta(hours=18):
            continue
        if state['users'].get(u['email'], {}).get('last_sent_day') == today:
            continue
        candidates.append((u, current))

    if not candidates:
        print('✅ Nobody at streak-break risk.')
        return

    print(f'🔥 {len(candidates)} streaks at risk')
    if dry_run:
        for u, n in candidates[:20]:
            print(f"   • {u['email']}  streak={n}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for u, n in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['streak'] = n

        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = tpl.get('cta', EN_SOURCE['cta'])

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME, gradient='urgent')

        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'streak', 'value': str(n)},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(u) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['users'][email] = {
                'last_sent_day': today,
                'last_streak': n,
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  streak={n}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
