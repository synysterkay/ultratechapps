#!/usr/bin/env python3
"""Streak at risk — streak ≥ 2, no check-in today, after 18:00 UTC."""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from kinbound_users_loader import get_access_token, load_all_users, is_paid
from kinbound_template_translator import get_localized
from kinbound_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'Kinbound'
APP_SLUG = 'kinbound'
KIND = 'kinbound_streak_at_risk'
DEEP_LINK = 'https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'kinbound_streak_at_risk_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

EN_SOURCE = {
    'subject': 'Your {{streak}}-day calm streak is still saveable tonight',
    'body': [
        "{{first_name}} — you've checked in {{streak}} days in a row. That counts.",
        "One 10-second check-in on Today keeps the streak alive. No lecture if you missed yesterday — we just don't want tonight to be the day it quietly resets.",
        "P.S. We only send this once per close call. If tonight isn't the night, tomorrow starts fresh at 1.",
    ],
    'cta': 'Save my streak',
}


def _ref(email):
    return hashlib.sha256(f'{_REF_SALT}:{email.lower().strip()}'.encode()).hexdigest()[:16]


def _today_key() -> str:
    n = datetime.now(timezone.utc)
    return f'{n.year}-{n.month:02d}-{n.day:02d}'


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'days': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def main(dry_run=False):
    if datetime.now(timezone.utc).hour < 18:
        print('🕒 Pre-18:00 UTC — streak window not open yet')
        return

    state = _load_state()
    state.setdefault('days', {})
    today = _today_key()
    state['days'].setdefault(today, {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    targets = []
    for user in load_all_users(token):
        if user['uid'] in state['days'][today]:
            continue
        streak = int(user.get('streak') or 0)
        if streak < 2:
            continue
        if user.get('last_check_in_day') == today:
            continue
        if is_paid(user):
            continue
        targets.append((user, streak))

    print(f'🔥 {len(targets)} streaks at risk')
    if not targets:
        return

    if dry_run:
        for u, s in targets[:20]:
            print(f"   • {u['email']}  streak={s}")
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, streak in targets:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {'first_name': user.get('first_name', 'there'), 'streak': str(streak)}
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl['subject'], ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl['body']]
        cta_text = localize_phrase.interpolate(lang, tpl['cta'], ctx)
        html = render_email(lang, paragraphs, cta_text, DEEP_LINK, app_name=APP_NAME, gradient='urgent')
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
            state['days'][today][user['uid']] = True
            print(f'   ✅ [{sent}] {email}  streak={streak}')
        else:
            failed += 1
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
