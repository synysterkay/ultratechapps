#!/usr/bin/env python3
"""
Deadline Countdown Sender (Thesis Generator)

Sends a single personalized email when the user's `plan.deadline` is
14 / 7 / 3 / 1 / 0 days out. Each milestone fires at most once per user.

This complements the in-app deadline notification — together they form
the highest-signal external trigger pair for Hooked-aligned retention.

All 20 app languages are supported: any not already cached gets a one-shot
DeepSeek translation per (milestone, language) pair on first send.

Usage:
    python scripts/deadline_countdown_sender.py
    python scripts/deadline_countdown_sender.py --dry-run
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS, has_email_credentials
from thesis_users_loader import get_access_token, load_all_users, is_paid
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


MILESTONES = [14, 7, 3, 1, 0]
APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'deadline_countdown_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


# English source per milestone. Each yields its own translation cache so
# DeepSeek can phrase the urgency level naturally per language (14-day
# voice is calmer than 0-day voice).
EN_SOURCES = {
    14: {
        'subject': '{{topic}} — {{days_left}}',
        'body': [
            "Two weeks out from your {{work_type}} on {{topic}}. {{pain_hook}}",
            "Two weeks is plenty if you start now — generate the next chapter today and you'll feel a different kind of week ahead.",
        ],
        'cta': 'Continue my {{work_type}}',
    },
    7: {
        'subject': 'One week to go on {{topic}}',
        'body': [
            "A week from your deadline on {{topic}}, {{first_name}}. The next chapter takes about 60 seconds to generate.",
            "Most of the people who finish on time generate something every day this week. Tap below to keep moving.",
        ],
        'cta': "Open my {{work_type}}",
    },
    3: {
        'subject': '3 days left, {{first_name}}',
        'body': [
            "Three days. You can absolutely still make this.",
            "Open the app, tap the next chapter, and the AI takes care of the rest. Repeat tomorrow.",
            "P.S. If you're stuck on the topic, edit it in the form screen before generating — even small tweaks help.",
        ],
        'cta': 'Generate my next chapter',
    },
    1: {
        'subject': 'Tomorrow is the day for {{topic}}',
        'body': [
            "One day left. If you have one chapter left to generate, do it now and export tonight.",
            "If everything's already drafted, the export flow takes 20 seconds. Tap below.",
        ],
        'cta': 'Export my {{work_type}}',
    },
    0: {
        'subject': 'Today: finish {{topic}}',
        'body': [
            "Today is the day. Whatever shape your {{work_type}} is in, export the PDF and turn it in.",
            "Done beats perfect. The version you submit today matters infinitely more than the perfect one you don't.",
        ],
        'cta': 'Export & finish',
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


def _days_until(deadline):
    if not deadline:
        return None
    try:
        now = datetime.now(timezone.utc)
        delta = deadline - now
        return delta.days
    except Exception:
        return None


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set — cannot query deadlines')
        return

    candidates = []
    for u in load_all_users(token):
        plan = u.get('plan') or {}
        deadline = plan.get('deadline')
        d = _days_until(deadline)
        if d is None or d not in MILESTONES:
            continue
        already = set(state['users'].get(u['email'], {}).get('milestones', []))
        if d in already:
            continue
        candidates.append((u, d))

    if not candidates:
        print('✅ No users at a deadline milestone right now.')
        return
    print(f'📧 {len(candidates)} candidates at a deadline milestone')

    if dry_run:
        for u, d in candidates[:25]:
            topic = (u.get('plan') or {}).get('topic', '')[:40]
            print(f"   • {u['email']}  d={d}  topic={topic}  lang={u['language']}  paid={is_paid(u)}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not has_email_credentials():
        print('❌ Email API credentials not set (ZEPTOMAIL_API_KEY / RESEND_API_KEY / …)')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for u, d in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['work_type'] = plan.get('workType') or plan.get('work_type') or 'fullThesis'
        plan['days_left'] = d

        kind = f'deadline_{d}d'
        tpl = get_localized(kind, lang, EN_SOURCES[d])
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCES[d]['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCES[d]['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCES[d]['cta']), plan)

        gradient = 'urgent' if d <= 3 else 'invite'
        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME, gradient=gradient)

        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'deadline'},
            {'name': 'milestone', 'value': str(d)},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(u) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            record = state['users'].setdefault(email, {'milestones': []})
            record['milestones'] = sorted(set(record.get('milestones', []) + [d]))
            record['last_sent_at'] = datetime.now().isoformat()
            record['language'] = lang
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  d={d}  {lang}')
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} result={result}')
        else:
            failed += 1
            print(f'   ❌ {email} result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
