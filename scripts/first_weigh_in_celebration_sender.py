#!/usr/bin/env python3
"""
First-Weigh-In Celebration Sender (PupShape)

Sends one celebratory email the first time a user logs a weight for
any of their dogs. This is the moment the adaptive CalorieEngine can
*actually* adapt — without the weigh-in there's nothing to learn from.

Detection: walks every user's dogs → checks if any dog has at least
one weight_log doc. Dedupes per (user, dog) so logging a second dog
doesn't re-fire the welcome.

State cache: cache/first_weigh_in_celebration_state.json
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
from pupshape_users_loader import (
    get_access_token, load_all_users, load_dog_weight_logs, is_paid,
)
from pupshape_template_translator import get_localized
from pupshape_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'first_weigh_in_celebration'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
DEEP_LINK = 'pupshape://weigh'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'first_weigh_in_celebration_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': '{{dog_name}} weighed in — the plan starts learning now',
    'body': [
        "{{first_name}}, {{dog_name}}'s first weigh-in just landed: {{current_weight}} kg.",
        "Here's why this number matters more than the next ten: the plan adapts from real data, not from defaults. The engine now has one anchor point. Two weigh-ins from now it has a velocity. Three from now it can spot a plateau and tweak before you'd ever notice.",
        "Same scale, same time of day, before breakfast — that's all it takes for the loop to tighten.",
        "P.S. Tap below to see {{dog_name}}'s plan with the fresh number baked in.",
    ],
    'cta': "See {{dog_name}}'s plan",
}


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'pairs': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _ref(email):
    return hashlib.sha256(
        f"{_REF_SALT}:{email.lower().strip()}".encode()
    ).hexdigest()[:16]


def main(dry_run=False):
    state = _load_state()
    state.setdefault('pairs', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN / gcloud auth not available — cannot query')
        return

    print('🔎 Walking users + dogs + weight logs...')
    targets = []  # list of (user, dog, latest_log)
    for user in load_all_users(token):
        for dog in user.get('dogs', []):
            pair_key = f"{user['uid']}::{dog['dog_id']}"
            if pair_key in state['pairs']:
                continue
            logs = load_dog_weight_logs(token, user['uid'], dog['dog_id'])
            if not logs:
                continue
            # logs are newest-first; the "first" weigh-in is the
            # oldest. But for the celebration we surface the latest
            # (which is also the only one — this is *first*).
            targets.append((user, dog, logs[-1]))

    print(f'🎉 {len(targets)} new first-weigh-ins')
    if not targets:
        return

    if dry_run:
        for u, d, log in targets[:25]:
            print(f"   • {u['email']}  {d['name']}  {log['weight']:.1f}kg  lang={u['language']}  paid={is_paid(u)}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, log in targets:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name':     user.get('first_name', ''),
            'dog_name':       dog.get('name', 'your pup'),
            'current_weight': f"{log['weight']:.1f}",
            'target_weight':  f"{dog.get('target_weight', 0):.1f}",
        }
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCE['cta']), ctx)

        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='celebrate', celebratory=True,
            dog_image_url=dog.get('image_url') or '',
            dog_name=dog.get('name', ''),
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
            state['pairs'][f"{user['uid']}::{dog['dog_id']}"] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  ({dog["name"]})  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
