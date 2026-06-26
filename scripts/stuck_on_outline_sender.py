#!/usr/bin/env python3
"""
Stuck-On-Outline Sender (Thesis Generator)

Fires when a user generated their outline (thesis.status == 'draft' with
progress > 0 and at least one chapter title in `chapters[]`) but didn't
generate any chapter for 24+ hours. The hand-off between outline and
chapter 1 is the single biggest drop-off point in the app's funnel.

One nudge per (thesis, user) — never retried on the same thesis.
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS
from thesis_users_loader import (
    get_access_token, load_users_dict, load_theses_by_status, is_paid,
)
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
KIND = 'stuck_on_outline'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'stuck_on_outline_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': "Your outline's done — pick chapter 1, {{first_name}}",
    'body': [
        "You've got an outline for {{topic}}. The hardest part of academic writing is over — you know what each chapter says.",
        "Tap a chapter, hit generate, and you have a draft in 60 seconds. Most users do chapter 1 the same day they pick it.",
        "P.S. You don't have to pick chapter 1 — pick whichever feels easiest. The AI doesn't care about order.",
    ],
    'cta': 'Generate chapter 1',
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


def main(dry_run=False):
    state = _load_state()
    state.setdefault('theses', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    by_email, by_uid = load_users_dict(token)
    now = datetime.now(timezone.utc)
    candidates = []
    for t in load_theses_by_status(token, ['draft']):
        # Outline created but no chapter generated -> progress < 5%.
        progress = t.get('progress') or 0
        if progress >= 5 or progress == 0:
            # 0 means topic-only (no outline yet); skip both ends.
            continue
        last = t.get('last_modified') or t.get('created_at')
        if not last or (now - last) < timedelta(hours=24):
            continue
        if (now - last) > timedelta(days=14):
            # Beyond the freshness window — abandoned_thesis sender owns this.
            continue
        if t['thesis_id'] in state['theses']:
            continue
        user = by_uid.get(t.get('user_id'))
        if not user or not user.get('email'):
            continue
        candidates.append((user, t))

    if not candidates:
        print('✅ No stuck-on-outline candidates.')
        return
    print(f'📑 {len(candidates)} stuck-on-outline nudges queued')
    if dry_run:
        for u, t in candidates[:20]:
            print(f"   • {u['email']}  thesis={t['thesis_id']}  topic={t.get('topic','')[:40]}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent_n = failed = 0
    for u, t in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['topic'] = t.get('topic') or plan.get('topic') or ''
        plan['work_type'] = plan.get('workType') or plan.get('work_type') or 'fullThesis'

        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = tpl.get('cta', EN_SOURCE['cta'])

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME, gradient='invite')
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(u) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent_n += 1
            state['theses'][t['thesis_id']] = {
                'email': email,
                'sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent_n % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent_n}] {email}  {lang}')
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
