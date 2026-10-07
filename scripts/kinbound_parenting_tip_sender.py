#!/usr/bin/env python3
"""Parenting tips for free Kinbound users — value first, soft open CTA."""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, has_email_credentials
from kinbound_users_loader import get_access_token, load_all_users, is_paid, days_since_open
from kinbound_template_translator import get_localized
from kinbound_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'Kinbound'
APP_SLUG = 'kinbound'
KIND = 'kinbound_parenting_tip'
DEEP_LINK = 'https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'kinbound_parenting_tip_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Once-ever stages; pick by days since signup / open.
STAGES = [
    ('meltdown', 1, 4),
    ('bedtime', 5, 10),
    ('repair', 11, 21),
]

EN_SOURCES = {
    'meltdown': {
        'subject': 'Name the feeling before the ask, {{first_name}}',
        'body': [
            "Quick parenting tip for meltdown moments: say the feeling out loud before you ask for anything.",
            "\"You're furious the tablet ended\" lands better than \"Stop screaming.\" Kids regulate faster when the feeling is named first — then the boundary.",
            "Open Help me now when you need the next line. The tip works either way.",
        ],
        'cta': 'Open Help me now',
    },
    'bedtime': {
        'subject': 'Bedtime tip: one choice, not five',
        'body': [
            "{{first_name}} — bedtime stalls when kids get a menu. Tip: offer one choice (\"book A or book B\"), then start the routine.",
            "Fewer decisions = less negotiation. Save the calm script in Kinbound for the nights that still go sideways.",
            "P.S. Consistency beats perfect tone. Same order every night is the real win.",
        ],
        'cta': 'Open Kinbound',
    },
    'repair': {
        'subject': 'After a hard moment: repair in one sentence',
        'body': [
            "Tip after a blow-up: kids need a short repair more than a lecture. One sentence — \"I got loud; you matter; we're okay\" — then move on.",
            "That models what you want them to do next time. Help me now can draft the line if your brain is fried.",
            "P.S. Repair isn't spoiling. It's teaching the ending of the story.",
        ],
        'cta': 'Try Help me now',
    },
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
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _pick_stage(days_openish, fired):
    for key, lo, hi in STAGES:
        if key in fired:
            continue
        if lo <= days_openish <= hi:
            return key
    return None


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = _load_state()
    candidates = []
    for user in load_all_users(token):
        if is_paid(user):
            continue
        email = (user.get('email') or '').strip()
        if not email:
            continue
        days = days_since_open(user)
        if days < 0:
            created = user.get('created_at')
            if isinstance(created, datetime):
                days = (datetime.now(created.tzinfo) - created).days if created.tzinfo else 0
            else:
                days = 0
        # Prefer age-since-signup for tips: use created_at days if available
        created = user.get('created_at')
        age = days
        if isinstance(created, datetime):
            try:
                age = (datetime.now(created.tzinfo or None) - created).days
            except Exception:
                age = days
        fired = set((state.get('users', {}).get(user['uid']) or {}).get('stages', []))
        stage = _pick_stage(max(age, 1), fired)
        if not stage:
            continue
        candidates.append((user, stage))

    print(f'🌱 {len(candidates)} parenting-tip candidates')
    if dry_run:
        for u, s in candidates[:20]:
            print(f"   • {u['email']}  stage={s}  lang={u.get('language')}")
        return
    if not candidates:
        return

    if not has_email_credentials():
        print('❌ Email credentials not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, stage in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        src = EN_SOURCES[stage]
        tpl = get_localized(f'{KIND}_{stage}', lang, src)
        plan = {
            'first_name': user.get('first_name', 'there'),
        }
        subject = localize_phrase.interpolate(lang, tpl.get('subject', src['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', src['body'])]
        cta = tpl.get('cta', src['cta'])
        html = render_email(lang, paragraphs, cta, DEEP_LINK, sender_name='Kinbound', app_name=APP_NAME)
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  {stage}')
        else:
            failed += 1
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
