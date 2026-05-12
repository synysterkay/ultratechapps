#!/usr/bin/env python3
"""
Streak-Milestone Celebration Sender (Thesis Generator)

Externalizes the in-app milestone push notifications (3 / 7 / 14 / 30 / 100
days) to email — the in-app push fires only on devices that have
notifications enabled (~40% of iOS users opt out). Email is the redundant
channel that variable-reward research says matters.

Reads `users.{uid}.streak.current`; fires once per milestone per user.
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
from thesis_users_loader import get_access_token, load_all_users, is_paid
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'streak_milestone_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

MILESTONES = [3, 7, 14, 30, 100]


# One source per milestone — DeepSeek phrases each at its own intensity.
EN_SOURCES = {
    3: {
        'subject': "🔥 3-day streak, {{first_name}}",
        'body': [
            "You're on a {{streak}}. Three is the inflection point — past this most people don't break.",
            "Keep it warm with one minute in the app today.",
        ],
        'cta': 'Open the app',
    },
    7: {
        'subject': "Full week, {{first_name}} 🔥",
        'body': [
            "Seven days in a row of working on your {{work_type}}. That's not the kind of thing most people manage.",
            "The week-long streak crowd is also the crowd that finishes their drafts on time. Stay with it.",
        ],
        'cta': 'Generate today\'s chapter',
    },
    14: {
        'subject': "Two weeks straight 🔥🔥",
        'body': [
            "Two weeks. Whatever shape your {{work_type}} is in, you have a writing habit now — which is the rarest thing.",
            "Even five minutes today keeps the streak alive and the muscle warm.",
        ],
        'cta': 'Keep it going',
    },
    30: {
        'subject': "30-day streak — you're a writer now",
        'body': [
            "A full month. You've written on your {{work_type}} more days than not — that's how books happen.",
            "Reply with what helped you stick. I'd love to share what's working for users like you.",
        ],
        'cta': 'Open my draft',
    },
    100: {
        'subject': "100 days, {{first_name}}",
        'body': [
            "Hundred-day streak. That's the rarest tier of users we have.",
            "If you're up for it, your story would help other students just starting. Reply to this email and I'll send back a question or two.",
        ],
        'cta': 'Open the app',
    },
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


def _pick_milestone(current, already_sent):
    for m in MILESTONES:
        if m in already_sent:
            continue
        # Allow a 1-day tolerance for clock skew between device + cron.
        if m - 1 <= current <= m + 1 or current == m:
            return m
    return None


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    candidates = []
    for u in load_all_users(token):
        s = u.get('streak') or {}
        current = s.get('current')
        if not current:
            continue
        already = set(state['users'].get(u['email'], {}).get('milestones', []))
        m = _pick_milestone(current, already)
        if not m:
            continue
        candidates.append((u, m))

    if not candidates:
        print('✅ No milestone celebrations to send.')
        return
    print(f'🎉 {len(candidates)} milestone celebrations queued')
    if dry_run:
        for u, m in candidates[:20]:
            print(f"   • {u['email']}  milestone={m}  current_streak={(u.get('streak') or {}).get('current')}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent_n = failed = 0
    for u, m in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['work_type'] = plan.get('workType') or plan.get('work_type') or 'fullThesis'
        plan['streak'] = m

        kind = f'streak_milestone_{m}'
        tpl = get_localized(kind, lang, EN_SOURCES[m])
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCES[m]['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCES[m]['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCES[m]['cta']), plan)

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME,
                            gradient='celebrate', celebratory=True)
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'streak_milestone'},
            {'name': 'milestone', 'value': str(m)},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(u) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent_n += 1
            record = state['users'].setdefault(email, {'milestones': []})
            record['milestones'] = sorted(set(record.get('milestones', []) + [m]))
            record['last_sent_at'] = datetime.now().isoformat()
            record['language'] = lang
            if sent_n % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent_n}] {email}  m={m}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent_n}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
