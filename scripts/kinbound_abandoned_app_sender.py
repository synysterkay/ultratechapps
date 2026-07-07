#!/usr/bin/env python3
"""Abandoned app — lastOpenMs > 2 / 5 / 10 days, free users."""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime

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
KIND = 'kinbound_abandoned_app'
DEEP_LINK = 'https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'kinbound_abandoned_app_state.json'
STAGES = [10, 5, 2]
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

EN_SOURCES = {
    '2d': {
        'subject': 'Still thinking about {{struggle}}?',
        'body': [
            "{{first_name}} — Kinbound still has the script you started with for {{struggle}}.",
            "Two days away isn't a failure. Hard weeks happen. The Help me now button is one tap — same calm coach, same words ready when the moment hits.",
            "P.S. Nothing expired. Your streak paused; your saved scripts didn't.",
        ],
        'cta': 'Open Kinbound',
    },
    '5d': {
        'subject': 'Five days — your parenting coach is still here',
        'body': [
            "{{first_name}}, five days without opening Kinbound. Life got loud — we get it.",
            "The app doesn't grade you. It waits with scripts for meltdowns, bedtime, and the moments when Google makes everything worse.",
            "P.S. If {{struggle}} is still the hard part, tap Help me now first. Fastest win in the app.",
        ],
        'cta': 'Come back',
    },
    '10d': {
        'subject': 'Should we go quiet, {{first_name}}?',
        'body': [
            "{{first_name}}, ten days away. We can either welcome you back or stop nudging — your call.",
            "Kinbound keeps everything on your phone. No data leaves unless you link an account. Come back when parenting gets loud again.",
            "P.S. If now's not the time, ignore this. We won't send another on this thread.",
        ],
        'cta': 'Reopen Kinbound',
    },
}


def _ref(email):
    return hashlib.sha256(f'{_REF_SALT}::{email.lower()}'.encode()).hexdigest()[:16]


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {'users': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _pick_stage(days: int, fired: set) -> str:
    for s in STAGES:
        key = f'{s}d'
        if days >= s and key not in fired:
            return key
    return ''


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = _load_state()
    candidates = []
    for user in load_all_users(token):
        uid = user.get('uid')
        email = user.get('email')
        if not uid or not email:
            continue
        if is_paid(user):
            continue
        days = days_since_open(user)
        if days < STAGES[-1]:
            continue
        fired = set((state.get('users', {}).get(uid) or {}).get('stages', []))
        stage_key = _pick_stage(days, fired)
        if not stage_key:
            continue
        concern = (user.get('onboarding') or {}).get('primaryConcernId') or 'tantrum'
        candidates.append((user, stage_key, days, concern))

    print(f'👋 {len(candidates)} abandoned-app candidates')
    if not candidates:
        return

    if dry_run:
        for u, s, d, _ in candidates[:15]:
            print(f"   • {u['email']}  stage={s}  ({d}d)")
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, stage_key, days, concern in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        struggle = struggle_label(concern)
        ctx = {
            'first_name': user.get('first_name', 'there'),
            'struggle': struggle,
            'days_since': str(days),
        }
        en = EN_SOURCES[stage_key]
        tpl = get_localized(f'{KIND}_stage_{stage_key}', lang, en)
        subject = localize_phrase.interpolate(lang, tpl['subject'], ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl['body']]
        cta_text = localize_phrase.interpolate(lang, tpl['cta'], ctx)
        html = render_email(lang, paragraphs, cta_text, DEEP_LINK, app_name=APP_NAME, gradient='invite')
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=[
                {'name': 'app', 'value': APP_SLUG},
                {'name': 'kind', 'value': KIND},
                {'name': 'stage', 'value': stage_key},
                {'name': 'language', 'value': lang},
            ],
            ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            if stage_key not in rec['stages']:
                rec['stages'].append(stage_key)
            rec['last_sent_at'] = datetime.now().isoformat()
            print(f'   ✅ [{sent}] {email}  {stage_key}')
        else:
            failed += 1
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
