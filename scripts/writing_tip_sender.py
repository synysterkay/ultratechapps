#!/usr/bin/env python3
"""
Writing-Tip Sender (Thesis Generator)

Value-first advice emails for free users — tips, not sales pitches.
Three once-ever stages (outline → chapter → revise). Soft CTA opens the app.

Tags: app=thesis, kind=writing_tip, stage=<outline|chapter|revise>, language, paid=0
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS, has_email_credentials
from thesis_users_loader import (
    get_access_token, load_all_users, load_theses_by_status, is_paid,
)
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'writing_tip_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Most-advanced tip first so one send per run picks the right stage.
STAGE_PRIORITY = ('revise', 'chapter', 'outline')

EN_SOURCES = {
    'outline': {
        'subject': "Start with the research question, {{first_name}}",
        'body': [
            "The blank page is almost never a writing problem — it's a clarity problem.",
            "Write one research question for {{topic}} (one sentence). Then turn it into a short outline: intro, 3–5 sections, conclusion. That outline is the map; drafting without it is why people stall.",
            "Open the app, drop your question, and generate the outline before you write a single paragraph.",
        ],
        'cta': 'Start my outline',
    },
    'chapter': {
        'subject': "Don't start with chapter 1 — start with the easy one",
        'body': [
            "Your outline for {{topic}} is ready. Most people freeze on chapter 1 because it feels like the “real” start.",
            "Pick the section you already understand — methods, background, a case study — and generate that first. Momentum beats order. The AI does not care which chapter you write first.",
            "Ten minutes from now you can have a full section draft instead of an empty chapter 1.",
        ],
        'cta': 'Generate a chapter',
    },
    'revise': {
        'subject': "One-pass revise: claim → evidence → cite",
        'body': [
            "You already have chapter text on {{topic}}. Before generating more, do one focused pass:",
            "1) Underline each claim\n2) Ask “what evidence supports this?”\n3) Add or fix the citation\n4) Only then move to the next chapter",
            "That pass turns AI draft into something that survives a supervisor read. Open your latest chapter and try it on two paragraphs.",
        ],
        'cta': 'Open my latest chapter',
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


def _days_since(dt):
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def _has_topic(user, theses):
    plan = user.get('plan') or {}
    if (plan.get('topic') or '').strip():
        return True
    for t in theses:
        if (t.get('topic') or '').strip():
            return True
    return False


def _pick_stage(user, theses, already_sent):
    """Return one unsent stage matching user state, or None."""
    now = datetime.now(timezone.utc)
    days_signup = _days_since(user.get('created_at'))
    completed = [t for t in theses if t.get('status') == 'completed']
    drafts = [t for t in theses if t.get('status') == 'draft']
    active = [t for t in theses if t.get('status') in ('in_progress', 'generating')]

    outline_ready = any(1 <= (t.get('progress') or 0) < 5 for t in drafts)
    chapter_started = any(
        (t.get('progress') or 0) >= 5
        for t in theses
        if t.get('status') in ('draft', 'in_progress', 'generating', 'completed')
    ) or bool(completed) or bool(active)

    quiet_work = None
    for t in active + [t for t in drafts if (t.get('progress') or 0) >= 5]:
        last = t.get('last_modified') or t.get('created_at')
        if last:
            quiet_work = max(quiet_work or timedelta(0), now - last)

    for stage in STAGE_PRIORITY:
        if stage in already_sent:
            continue
        if stage == 'revise':
            if chapter_started and quiet_work is not None and quiet_work >= timedelta(days=2):
                return stage
        elif stage == 'chapter':
            if outline_ready and not chapter_started:
                return stage
        elif stage == 'outline':
            if (
                days_signup is not None
                and 1 <= days_signup <= 3
                and _has_topic(user, theses)
                and not completed
                and not chapter_started
                and not outline_ready
            ):
                return stage
    return None


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    by_uid_theses = defaultdict(list)
    for status in ('draft', 'in_progress', 'generating', 'completed'):
        for t in load_theses_by_status(token, [status]):
            uid = t.get('user_id')
            if uid:
                by_uid_theses[uid].append(t)

    candidates = []
    for u in load_all_users(token):
        if is_paid(u):
            continue
        email = (u.get('email') or '').strip()
        if not email:
            continue
        uid = u.get('uid') or u.get('id') or ''
        theses = by_uid_theses.get(uid, [])
        sent = set(state['users'].get(email, {}).get('stages', []))
        stage = _pick_stage(u, theses, sent)
        if not stage:
            continue
        candidates.append((u, stage, theses))

    if not candidates:
        print('✅ No writing-tip emails queued.')
        return
    print(f'✍️ {len(candidates)} writing-tip emails queued')

    if dry_run:
        for u, stage, _ in candidates[:25]:
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
    for u, stage, theses in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['work_type'] = plan.get('workType') or plan.get('work_type') or 'fullThesis'
        topic = plan.get('topic') or ''
        if not topic:
            for t in theses:
                if t.get('topic'):
                    topic = t['topic']
                    break
        plan['topic'] = topic

        kind = f'writing_tip_{stage}'
        src = EN_SOURCES[stage]
        tpl = get_localized(kind, lang, src)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', src['subject']), plan)
        paragraphs = [
            localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', src['body'])
        ]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', src['cta']), plan)

        html = render_email(
            lang, paragraphs, cta_text, APP_STORE_URL,
            sender_name='Ana', app_name=APP_NAME, gradient='invite',
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'writing_tip'},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '0'},
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
