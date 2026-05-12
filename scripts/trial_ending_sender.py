#!/usr/bin/env python3
"""
Trial-Ending Sender (Thesis Generator)

Fires twice per trial: 3 days before trial_end and 24 hours before.
Reads `users.{uid}.subscription.{status: 'trial', trialEnd: ...}`.

Trial-to-paid conversion lift on iOS subscriptions is typically 10-25%
when a "trial ending" reminder is sent — Superwall doesn't email by
default, so this fills the gap.
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
from thesis_users_loader import get_access_token, load_all_users
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'trial_ending_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


# stage_key -> (min_hours_until_end, max_hours)
STAGES = {
    '3d': (48, 96),
    '1d': (12, 36),
}

EN_SOURCES = {
    '3d': {
        'subject': "3 days left on your free trial",
        'body': [
            "Quick heads-up: your trial ends in 3 days. After that, you'll keep all your existing drafts, but new chapters require the paid plan.",
            "If the trial has been useful, you don't need to do anything — it auto-renews. If you'd rather cancel, the option's in Settings → Subscription.",
        ],
        'cta': 'Manage subscription',
    },
    '1d': {
        'subject': "Trial ends tomorrow, {{first_name}}",
        'body': [
            "Tomorrow is the last day of your trial.",
            "Most people who keep it tell us the time saved on the next assignment is what made the call. If you're not sure yet, finishing one more chapter today usually answers it.",
        ],
        'cta': 'Continue writing',
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
        if (sub.get('status') or '').lower() != 'trial':
            continue
        trial_end = sub.get('trialEnd')
        if not trial_end:
            continue
        hours = (trial_end - now).total_seconds() / 3600
        if hours <= 0:
            continue
        already = set(state['users'].get(u['email'], {}).get('stages', []))
        stage = None
        for key, (lo, hi) in STAGES.items():
            if key in already:
                continue
            if lo <= hours <= hi:
                stage = key
                break
        if not stage:
            continue
        candidates.append((u, stage))

    if not candidates:
        print('✅ No trials at warn-window.')
        return
    print(f'⏰ {len(candidates)} trial-ending nudges queued')
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

        kind = f'trial_ending_{stage}'
        tpl = get_localized(kind, lang, EN_SOURCES[stage])
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCES[stage]['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCES[stage]['body'])]
        cta_text = tpl.get('cta', EN_SOURCES[stage]['cta'])

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME, gradient='upgrade')
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'trial_ending'},
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
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent_n}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
