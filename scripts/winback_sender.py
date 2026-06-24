#!/usr/bin/env python3
"""
Winback Sender (Thesis Generator)

Fires at 7 / 30 / 60 / 90 days after a paying subscriber cancelled
(`users.{uid}.subscription.{status: 'cancelled', cancelledAt: ...}`).
One email per window per user.

Predictify has the equivalent (winback_lapsed_pro_*.json); this is the
Thesis-Generator-specific port with thesis-flavored copy.
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS
from thesis_users_loader import get_access_token, load_all_users
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'winback_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


# stage_key -> (min_days_since_cancel, max_days)
STAGES = [
    ('d7',   7,  13),
    ('d30', 30,  44),
    ('d60', 60,  74),
    ('d90', 90, 120),
]

EN_SOURCES = {
    'd7': {
        'subject': "Did Thesis Generator miss anything for you?",
        'body': [
            "Hey {{first_name}}, you cancelled last week. No pressure to come back — I'd just love to know if something didn't work.",
            "Reply to this email with one line. I read every response.",
        ],
        'cta': 'Open the app',
    },
    'd30': {
        'subject': "30 days later — your draft's still here",
        'body': [
            "It's been a month. Your drafts, outlines, and chapters are still saved exactly where you left them.",
            "If you've got a new assignment coming up, the door's open. No grudges, no re-onboarding.",
        ],
        'cta': 'Continue where I left off',
    },
    'd60': {
        'subject': "We added a few things since you left",
        'body': [
            "Two months out and the app is meaningfully better — better outline quality, faster generation, more languages supported.",
            "If you've got writing on your plate, give it 60 seconds and see.",
        ],
        'cta': 'See what changed',
    },
    'd90': {
        'subject': "Final check-in, {{first_name}}",
        'body': [
            "Three months. I'll stop after this one.",
            "If a new paper is coming up, your account is intact and ready. If not, all good — and good luck out there.",
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


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    now = datetime.now(timezone.utc)
    candidates = []
    for u in load_all_users(token):
        sub = u.get('subscription') or {}
        if (sub.get('status') or '').lower() != 'cancelled':
            continue
        cancelled_at = sub.get('cancelledAt')
        if not cancelled_at:
            continue
        days = (now - cancelled_at).days
        already = set(state['users'].get(u['email'], {}).get('stages', []))
        stage = None
        for key, lo, hi in STAGES:
            if key in already:
                continue
            if lo <= days <= hi:
                stage = key
                break
        if not stage:
            continue
        candidates.append((u, stage))

    if not candidates:
        print('✅ No winback candidates right now.')
        return
    print(f'💌 {len(candidates)} winback nudges queued')
    if dry_run:
        for u, s in candidates[:20]:
            print(f"   • {u['email']}  stage={s}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent_n = failed = 0
    for u, stage in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')

        kind = f'winback_{stage}'
        tpl = get_localized(kind, lang, EN_SOURCES[stage])
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCES[stage]['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCES[stage]['body'])]
        cta_text = tpl.get('cta', EN_SOURCES[stage]['cta'])

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME, gradient='winback')
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'winback'},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': lang},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent_n += 1
            record = state['users'].setdefault(email, {'stages': []})
            record['stages'] = sorted(set(record.get('stages', []) + [stage]))
            record['last_sent_at'] = datetime.now().isoformat()
            record['language'] = lang
            if sent_n % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent_n}] {email}  {stage}  {lang}')
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} result={result}')
        else:
            failed += 1
            print(f'   ❌ {email} result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent_n}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
