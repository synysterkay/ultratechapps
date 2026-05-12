#!/usr/bin/env python3
"""
Abandoned-Thesis Sender (Thesis Generator)

Sends a recovery email to users who started a thesis (status in
'in_progress' or 'generating'), then went silent for 48+ hours.
A second nudge fires at 5 days and a third at 10 days; after that the
user is left alone — beyond that the email pattern reads as nagging.

This is the equivalent of an abandoned-cart email for thesis writing —
the user has already invested effort and is most receptive to a gentle
"pick up where you left off" prompt.

Localized for all 20 app languages via DeepSeek.
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
from thesis_users_loader import (
    get_access_token, load_users_dict, load_theses_by_status, is_paid,
)
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'abandoned_thesis_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


# (cadence_label, min_days_inactive, max_days_inactive)
STAGES = [
    ('stage_2d',  2,  4),
    ('stage_5d',  5,  9),
    ('stage_10d', 10, 30),
]

EN_SOURCES = {
    'stage_2d': {
        'subject': "Your {{work_type}} on {{topic}} is waiting",
        'body': [
            "Quick check-in, {{first_name}} — your {{work_type}} on {{topic}} is sitting at {{progress}}.",
            "Generating the next chapter takes about 60 seconds. The first sentence is always the hardest, and you've already crossed it.",
        ],
        'cta': 'Continue my {{work_type}}',
    },
    'stage_5d': {
        'subject': "5 days quiet — still want to finish {{topic}}?",
        'body': [
            "It's been five days since you touched your {{work_type}} on {{topic}}. {{pain_hook}}",
            "If the topic still matters, the next 60 seconds in the app moves the needle. If it doesn't, no judgment — just hit unsubscribe and I'll stop checking in.",
        ],
        'cta': 'Pick up where I left off',
    },
    'stage_10d': {
        'subject': "Last nudge on {{topic}}, {{first_name}}",
        'body': [
            "Last time I'll mention this. Your {{work_type}} on {{topic}} is still in your account, exactly where you left it.",
            "If you want to come back, tap below — your progress is intact. If life moved on, that's okay too.",
            "P.S. Even one more chapter changes the difficulty curve for the rest. The hardest part is reopening the app.",
        ],
        'cta': 'Open my draft',
    },
}


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'theses': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _ref(email):
    return hashlib.sha256(f"{_REF_SALT}:{email.lower().strip()}".encode()).hexdigest()[:16]


def _hours_inactive(last):
    if not last:
        return None
    return (datetime.now(timezone.utc) - last).total_seconds() / 3600


def _pick_stage(days_inactive, already_sent):
    """Return the stage_key + min_days for the next un-sent stage, or None."""
    for key, lo, hi in STAGES:
        if key in already_sent:
            continue
        if lo <= days_inactive <= hi:
            return key
    return None


def main(dry_run=False):
    state = _load_state()
    state.setdefault('theses', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    by_email, by_uid = load_users_dict(token)
    now = datetime.now(timezone.utc)
    candidates = []  # (user, thesis, stage_key)
    # Walk in_progress + generating + draft (with progress > 0).
    for status in ('in_progress', 'generating', 'draft'):
        for t in load_theses_by_status(token, [status]):
            last = t.get('last_modified') or t.get('created_at')
            if not last:
                continue
            hours = _hours_inactive(last)
            if hours is None or hours < 48:
                continue
            days = hours / 24
            user = by_uid.get(t.get('user_id'))
            if not user or not user.get('email'):
                continue
            # Skip if thesis is barely started (no real investment yet) —
            # the welcome / first-time-user retention drip covers them.
            if (t.get('progress') or 0) < 5 and status == 'draft':
                continue
            sent = set(state['theses'].get(t['thesis_id'], {}).get('stages', []))
            stage = _pick_stage(days, sent)
            if not stage:
                continue
            candidates.append((user, t, stage))

    if not candidates:
        print('✅ No abandoned theses at a nudge window.')
        return
    print(f'📧 {len(candidates)} abandoned-thesis nudges queued')

    if dry_run:
        for u, t, stage in candidates[:25]:
            print(f"   • {u['email']}  thesis={t['thesis_id']}  stage={stage}  status={t['status']}  progress={t['progress']}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for u, t, stage in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['topic'] = t.get('topic') or plan.get('topic') or ''
        plan['work_type'] = plan.get('workType') or plan.get('work_type') or 'fullThesis'
        plan['progress'] = t.get('progress') or 0

        kind = f'abandoned_thesis_{stage}'
        tpl = get_localized(kind, lang, EN_SOURCES[stage])
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCES[stage]['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCES[stage]['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCES[stage]['cta']), plan)

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME,
                            gradient='invite' if stage == 'stage_2d' else 'urgent')

        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'abandoned_thesis'},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(u) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            record = state['theses'].setdefault(t['thesis_id'], {'stages': []})
            record['stages'] = sorted(set(record.get('stages', []) + [stage]))
            record['last_sent_at'] = datetime.now().isoformat()
            record['email'] = email
            record['language'] = lang
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  {stage}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
