#!/usr/bin/env python3
"""Streak milestone celebration — 3 / 7 / 14 / 30 calm days."""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from kinbound_users_loader import get_access_token, load_all_users
from kinbound_template_translator import get_localized
from kinbound_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'Kinbound'
APP_SLUG = 'kinbound'
KIND = 'kinbound_streak_milestone'
DEEP_LINK = 'https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'kinbound_streak_milestone_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
STAGES = [30, 14, 7, 3]

EN_SOURCES = {
    3: {
        'subject': 'Three calm days, {{first_name}} 🌱',
        'body': [
            "{{first_name}} — three days of showing up for yourself as a parent. That's not small.",
            "Kinbound noticed. The streak on Today is the external proof of an internal shift — you're building a rhythm.",
            "P.S. Day 7 unlocks a little celebration in-app. You're already halfway there.",
        ],
        'cta': 'See my streak',
    },
    7: {
        'subject': 'A full week of calm check-ins',
        'body': [
            "{{first_name}}, seven days. A week of pausing before reacting — or at least trying to.",
            "Parents who hit seven days come back on hard nights 2× more often. The habit is sticking.",
            "P.S. Save one script from Help me now this week. Future-you at bedtime will thank present-you.",
        ],
        'cta': 'Open Today',
    },
    14: {
        'subject': 'Two weeks — {{first_name}}, you\'re building something',
        'body': [
            "Fourteen calm days isn't luck. It's fourteen times you chose to check in instead of spiral.",
            "Kinbound keeps your scripts and moments on-device — this streak is yours, not ours. We're just cheering.",
            "P.S. If you haven't linked Google or Apple yet, today's a good day. Takes 10 seconds and backs up your streak.",
        ],
        'cta': 'Keep going',
    },
    30: {
        'subject': '30 days — quiet parenting wins add up',
        'body': [
            "{{first_name}}, thirty days. A month of showing up.",
            "Most parenting apps measure opens. We measure whether you felt calmer on hard days. Thirty check-ins is real data that you're changing how you respond.",
            "P.S. You don't have to be perfect on day 31. The streak can rest; the skill stays.",
        ],
        'cta': 'Open Kinbound',
    },
}


def _ref(email):
    return hashlib.sha256(f'{_REF_SALT}:{email.lower().strip()}'.encode()).hexdigest()[:16]


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


def _next_unfired_stage(current: int, fired: set) -> int:
    for stage in STAGES:
        if current >= stage and stage not in fired:
            return stage
    return 0


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
        current = int(user.get('streak') or 0)
        if current < STAGES[-1]:
            continue
        fired = set((state.get('users', {}).get(uid) or {}).get('stages', []))
        stage = _next_unfired_stage(current, fired)
        if not stage:
            continue
        candidates.append((user, stage))

    print(f'🎉 {len(candidates)} streak milestones')
    if not candidates:
        return

    if dry_run:
        for u, s in candidates[:15]:
            print(f"   • {u['email']}  stage={s}")
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, stage in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {'first_name': user.get('first_name', 'there'), 'streak': str(stage)}
        en = EN_SOURCES[stage]
        tpl = get_localized(f'{KIND}_stage_{stage}', lang, en)
        subject = localize_phrase.interpolate(lang, tpl['subject'], ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl['body']]
        cta_text = localize_phrase.interpolate(lang, tpl['cta'], ctx)
        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            app_name=APP_NAME, gradient='celebrate', celebratory=True,
        )
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=[
                {'name': 'app', 'value': APP_SLUG},
                {'name': 'kind', 'value': KIND},
                {'name': 'stage', 'value': str(stage)},
                {'name': 'language', 'value': lang},
            ],
            ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            print(f'   ✅ [{sent}] {email}  stage={stage}')
        else:
            failed += 1
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
