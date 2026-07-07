#!/usr/bin/env python3
"""Struggle rescue — primary concern set, no app open in 24h."""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from kinbound_users_loader import (
    get_access_token, load_all_users, is_paid, days_since_open, struggle_label,
)
from kinbound_template_translator import get_localized
from kinbound_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'Kinbound'
APP_SLUG = 'kinbound'
KIND = 'kinbound_struggle_rescue'
DEEP_LINK = 'https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'kinbound_struggle_rescue_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

EN_SOURCE = {
    'subject': '{{first_name}}, still thinking about {{struggle}}?',
    'body': [
        "{{first_name}} — you told Kinbound that {{struggle}} is the hard part right now. That matters.",
        "The script you got in onboarding was built for that exact moment. It's still saved on your phone — one tap opens Help me now and walks you through what to say.",
        "P.S. You don't need a perfect day to use it. Messy moments are literally what it's for.",
    ],
    'cta': 'Open Help me now',
}


def _ref(email):
    return hashlib.sha256(f'{_REF_SALT}:{email.lower().strip()}'.encode()).hexdigest()[:16]


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'users': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = _load_state()
    targets = []
    for user in load_all_users(token):
        uid = user['uid']
        if state.get('users', {}).get(uid):
            continue
        onboarding = user.get('onboarding') or {}
        concern = (onboarding.get('primaryConcernId') or '').strip()
        if not concern:
            continue
        if not onboarding.get('hasSeenOnboarding'):
            continue
        days = days_since_open(user)
        if days < 1:
            continue
        if is_paid(user):
            continue
        targets.append((user, concern))

    print(f'🫂 {len(targets)} struggle-rescue candidates')
    if not targets:
        return

    if dry_run:
        for u, c in targets[:20]:
            print(f"   • {u['email']}  {c}  lang={u['language']}")
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, concern in targets:
        email = user['email']
        lang = user.get('language') or 'en'
        struggle = struggle_label(concern)
        ctx = {
            'first_name': user.get('first_name', 'there'),
            'struggle': struggle,
        }
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl['subject'], ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl['body']]
        cta_text = localize_phrase.interpolate(lang, tpl['cta'], ctx)
        html = render_email(lang, paragraphs, cta_text, DEEP_LINK, app_name=APP_NAME, gradient='calm')
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=[
                {'name': 'app', 'value': APP_SLUG},
                {'name': 'kind', 'value': KIND},
                {'name': 'language', 'value': lang},
            ],
            ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state.setdefault('users', {})[user['uid']] = {
                'sent_at': datetime.now(timezone.utc).isoformat(),
                'concern': concern,
            }
            print(f'   ✅ [{sent}] {email}')
        else:
            failed += 1
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
