#!/usr/bin/env python3
"""
Free-Quota-Hit Upgrade Sequence (Thesis Generator)

Three-email sequence for users who burned their lifetime free chapter
(`users.{uid}.usage.freeChapterUsed == true`) and have not converted
to Superwall premium. Fires at 24h / 72h / 7d after the quota hit.

The free chapter is the AHA moment — the user has experienced the AI's
output quality. This sequence reaches them when they've walked away
from the in-app paywall without buying. Highest-intent conversion email
in the entire system once subscription state is in Firestore.

Skips users whose `subscription.status` is anything but missing/free.
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS, has_email_credentials
from thesis_users_loader import get_access_token, load_all_users, is_paid
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase
import instant_dedup


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'free_quota_hit_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


# (stage_key, min_hours_since_quota_hit, max_hours)
STAGES = [
    ('h24',  24, 71),
    ('h72',  72, 167),
    ('d7',  168, 720),
]

EN_SOURCES = {
    'h24': {
        'subject': "You've already done the hard part, {{first_name}}",
        'body': [
            "You generated your first chapter yesterday — the hardest part is over.",
            "Unlock the rest of your {{work_type}} and finish it this week. The next chapter takes 60 seconds. The one after that, also 60 seconds. By the weekend you have a complete draft.",
        ],
        'cta': 'Unlock all chapters',
    },
    'h72': {
        'subject': "Most students finish in 4 days once they unlock",
        'body': [
            "Three days since you generated your first chapter on {{topic}}. {{pain_hook}}",
            "Once people upgrade, most finish in 4 days — because each chapter takes about a minute. The bottleneck isn't writing time, it's the gate between chapter 1 and chapter 2.",
            "P.S. The upgrade includes unlimited chapters, PDF export, and language picks. No usage caps after.",
        ],
        'cta': 'See the upgrade options',
    },
    'd7': {
        'subject': "Last week of full access, {{first_name}}",
        'body': [
            "A week since your free chapter. Your draft, your outline, and your topic are all still saved — nothing's gone.",
            "Upgrading today gets you back to writing in two taps. If a week from now you still haven't, this is the last email you'll get about it.",
        ],
        'cta': 'Continue my {{work_type}}',
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


def _hours_since(ts):
    if not ts:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds() / 3600


def _pick_stage(hours, already_sent):
    for key, lo, hi in STAGES:
        if key in already_sent:
            continue
        if lo <= hours <= hi:
            return key
    return None


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    # Instant Edge Function (free-quota-hit-email) may have already
    # fired for this user when they hit the paywall in-app. If so,
    # skip all 3 batch stages — the instant email is timed perfectly
    # and follow-ups would over-pitch.
    handled_by_instant = instant_dedup.fetch_handled_uids('free_quota_hit')
    if handled_by_instant:
        print(f'   📌 {len(handled_by_instant)} users already handled by instant Edge Function — skipping')

    candidates = []
    for u in load_all_users(token):
        if is_paid(u):
            continue
        uid = u.get('uid') or u.get('id') or ''
        if uid and uid in handled_by_instant:
            continue
        usage = u.get('usage') or {}
        if not usage.get('freeChapterUsed'):
            continue
        when = usage.get('freeChapterUsedAt')
        h = _hours_since(when)
        if h is None or h < 24:
            continue
        sent = set(state['users'].get(u['email'], {}).get('stages', []))
        stage = _pick_stage(h, sent)
        if not stage:
            continue
        candidates.append((u, stage))

    if not candidates:
        print('✅ No free-quota-hit upgrade nudges queued.')
        return
    print(f'💰 {len(candidates)} free-quota nudges queued')

    if dry_run:
        for u, stage in candidates[:25]:
            print(f"   • {u['email']}  stage={stage}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not has_email_credentials():
        print('❌ Email API credentials not set (ZEPTOMAIL_API_KEY / RESEND_API_KEY / …)')
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
        plan['work_type'] = plan.get('workType') or plan.get('work_type') or 'fullThesis'
        plan['topic'] = plan.get('topic') or ''

        kind = f'free_quota_hit_{stage}'
        tpl = get_localized(kind, lang, EN_SOURCES[stage])
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCES[stage]['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCES[stage]['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCES[stage]['cta']), plan)

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME, gradient='upgrade')

        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'free_quota_hit'},
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
            # Mirror to Supabase dedup so instant Edge Function returns
            # duplicate=true if it fires later. One row per user — even
            # if the batch sends multiple stages, only the first insert
            # lands due to the (uid, event_kind) unique constraint.
            instant_dedup.record_sent(
                'free_quota_hit',
                uid=u.get('uid') or u.get('id') or '',
                app_id='thesis_generator',
                recipient=email,
                language=lang,
                metadata={'stage': stage, 'source': 'batch'},
            )
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
