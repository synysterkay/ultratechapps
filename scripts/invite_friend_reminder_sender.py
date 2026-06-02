#!/usr/bin/env python3
"""
Invite-Friend-Reminder Sender (PupShape)

Fires once per user when their usage.streak.current ≥ 7 AND
referrals.invitedCount == 0 — i.e. they're proven engaged but haven't
tried to bring anyone in yet. The tribe pillar of the Hooked model.

Dedupe per uid — one nudge ever; if they invite or hit 30+ days without
inviting we don't pester again.

State cache: cache/invite_friend_reminder_state.json
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime

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
KIND = 'invite_friend_reminder'
DEEP_LINK = 'pupshape://invite'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'invite_friend_reminder_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

_STREAK_THRESHOLD = 7


EN_SOURCE = {
    'subject': "{{dog_name}}'s streak is showing — know any pet parents who'd want this?",
    'body': [
        "{{first_name}}, you're on a {{streak_days}}-day streak with {{dog_name}}. That puts you in the top sliver of users.",
        "Most people with an overweight dog have at least one friend with the same situation. They're probably reading the same generic vet handout you skipped — \"feed less, exercise more\" — without any of the daily structure that actually moves the number.",
        "Your code below gives them their first week of Pro free. No quota, full plan. We don't pay you for it, but they'll thank you, and {{dog_name}} gets a buddy on the same journey.",
        "P.S. The in-app share sheet does the link for you. One tap, one message.",
    ],
    'cta': "Send the invite",
}


def _ref(email: str) -> str:
    h = hashlib.sha256(f"{_REF_SALT}::{email.lower()}".encode()).hexdigest()
    return h[:16]


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {'users': {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _current_streak(user: dict) -> int:
    usage = user.get('usage') or {}
    streak = usage.get('streak') or {}
    try:
        return int(streak.get('current') or 0)
    except (TypeError, ValueError):
        return 0


def _invited_count(user: dict) -> int:
    refs = (user.get('referrals') or user.get('private', {}).get('referrals') or {})
    try:
        return int(refs.get('invitedCount') or refs.get('invited_count') or 0)
    except (TypeError, ValueError):
        return 0


def main(dry_run: bool = False) -> None:
    print(f"\n🤝 Running {KIND}_sender (dry_run={dry_run})…")
    token = get_access_token()
    if not token:
        print("   ⚠️ no token — skipping")
        return

    users = list(load_all_users(token))
    state = _load_state()
    already_sent = set(state.get('users', {}).keys())

    candidates = []
    for user in users:
        uid = user.get('uid')
        email = user.get('email')
        if not uid or not email or uid in already_sent:
            continue
        if _current_streak(user) < _STREAK_THRESHOLD:
            continue
        if _invited_count(user) != 0:
            continue
        # Pick a lead dog for personalisation
        dogs = user.get('dogs', [])
        lead_dog = dogs[0] if dogs else {'name': 'your pup', 'image_url': ''}
        candidates.append((user, lead_dog))

    if not candidates:
        print('   ✅ No invite-friend candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} invite nudges")
        for u, d in candidates[:10]:
            print(f"     - {u['email']}  streak={_current_streak(u)}  ({d.get('name','?')})")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name':  user.get('first_name', ''),
            'dog_name':    dog.get('name', 'your pup'),
            'streak_days': str(_current_streak(user)),
        }
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCE['cta']), ctx)
        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='warm', celebratory=False,
            dog_image_url=dog.get('image_url') or '',
            dog_name=dog.get('name', ''),
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['users'][user['uid']] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
                'streak': _current_streak(user),
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  streak={_current_streak(user)}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
