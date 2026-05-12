#!/usr/bin/env python3
"""
First-Thesis-Complete Sender (Thesis Generator)

Sends one celebratory + invitation-to-export email the first time a user
marks a thesis as `completed`. This is the strongest possible upgrade
moment in the Hooked loop — the user just received the variable reward
and is most invested. The email funnels them back to the in-app PDF
export gate (which presents the Superwall paywall).

Detection: scans Firestore `theses/*` for `status == 'completed'`, then
resolves each `userId` to the corresponding `users/{uid}.email`. The
earlier version filtered for `'complete'` (silently zero-matching) and
expected an `email` field on the thesis doc (none exist) — both fixed.

Dedupes per-user via cache/first_thesis_complete_state.json so a user
who completes thesis #2, #3, ... doesn't get the email again.

All 20 languages supported via thesis_template_translator: any language
that isn't already cached triggers a one-shot DeepSeek translation on
first send and gets vetted for free thereafter.

Usage:
    python scripts/first_thesis_complete_sender.py
    python scripts/first_thesis_complete_sender.py --dry-run
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
from thesis_users_loader import (
    get_access_token, load_users_dict, load_theses_by_status, is_paid,
)
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
KIND = 'first_thesis_complete'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'first_thesis_complete_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': '🎓 You did it, {{first_name}} — export your {{work_type}}',
    'body': [
        "{{first_name}}, your {{work_type}} on {{topic}} is complete. That's a real accomplishment.",
        "Now the part that actually counts: export it as a PDF and turn it in. Tap below to open the export screen.",
        "P.S. Save the file somewhere outside the app too — future you will thank you.",
    ],
    'cta': 'Export my PDF',
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
        print('⚠️ FIREBASE_TOKEN not set — cannot query thesis completions')
        return

    print('🔎 Fetching completed theses + users...')
    by_email, by_uid = load_users_dict(token)
    completers = []  # list of (user_record, thesis_record)
    seen_uids = set()
    for t in load_theses_by_status(token, ['completed']):
        uid = t.get('user_id')
        if not uid or uid in seen_uids:
            continue
        seen_uids.add(uid)
        user = by_uid.get(uid)
        if not user or not user.get('email'):
            continue
        if user['email'] in state['users']:
            continue
        completers.append((user, t))

    print(f'🎓 {len(completers)} new first-completers found')
    if not completers:
        return

    if dry_run:
        for user, t in completers[:25]:
            print(f"   • {user['email']}  topic={t.get('topic','')[:40]}  lang={user['language']}  paid={is_paid(user)}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, t in completers:
        email = user['email']
        lang = user.get('language') or 'en'
        plan = dict(user.get('plan') or {})
        plan.setdefault('first_name', user.get('first_name', ''))
        plan.setdefault('topic', t.get('topic', '') or plan.get('topic', ''))
        plan.setdefault('work_type', plan.get('workType', 'fullThesis'))

        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = tpl.get('cta', EN_SOURCE['cta'])

        html = render_email(
            lang, paragraphs, cta_text, APP_STORE_URL,
            sender_name='Ana', app_name=APP_NAME,
            gradient='celebrate', celebratory=True,
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['users'][email] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
                'thesis_id': t.get('thesis_id'),
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
