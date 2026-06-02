#!/usr/bin/env python3
"""
Milestone-Crossed Sender (PupShape)

Fires when a dog crosses 25 / 50 / 75 / 100% of the journey toward
their goal weight. The Flutter app writes the event to
`users/{uid}/dogs/{dogId}/milestones/{key}` at the moment of crossing
(see weight_logging_screen.dart) so this sender just walks that
collection.

The in-app share sheet that fires at the same moment is the FIRST
distribution attempt; this email is the SECOND, with the rendered
progress card inline so a one-tap share is still possible from inbox.

State cache: cache/milestone_crossed_state.json keyed by
(uid, dog_id, milestone_key) so each milestone fires exactly once.
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
    get_access_token, load_all_users, load_dog_milestones, is_paid,
)
from pupshape_template_translator import get_localized
from pupshape_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'milestone_crossed'
DEEP_LINK = 'pupshape://journey'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'milestone_crossed_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


# One template per milestone key. The orchestrator's `--warm` walks
# EN_SOURCES (plural) and translates each sub-template independently
# so subject lines stay milestone-specific in every language.
EN_SOURCES = {
    'm25': {
        'subject': "{{dog_name}} is 25% of the way there 🐾",
        'body': [
            "Quarter of the way, {{first_name}}. {{dog_name}} crossed the 25% mark.",
            "This is the part of every journey where nothing visible has happened yet — the ribs aren't back yet, the spring in the walk is still emerging. The plan worked anyway. The next quarter usually moves faster because the body adapts.",
            "Tap below to see the snake-board update.",
        ],
        'cta': "See {{dog_name}}'s journey",
    },
    'm50': {
        'subject': "Halfway 🎉 — {{dog_name}} is officially over the hump",
        'body': [
            "Halfway, {{first_name}}. {{dog_name}} just crossed the 50% line.",
            "This is the milestone where most owners notice it without looking. The waist tuck. The faster jump onto the couch. The vet, next visit, will say something. You did this.",
            "P.S. The progress card below is yours to share — friends will ask which app.",
        ],
        'cta': "Share the halfway win",
    },
    'm75': {
        'subject': "{{dog_name}} hit 75% — the home stretch starts now",
        'body': [
            "Three-quarters of the way, {{first_name}}. {{dog_name}} just crossed 75%.",
            "The last quarter is the trickiest — the body resists the final kilos hardest. The engine is already pre-tuning for it. Trust the rhythm; don't accelerate.",
            "Same scale, same Sunday, same routine. The finish line is closer than you think.",
        ],
        'cta': "See the home stretch",
    },
    'goal': {
        'subject': "🏆 {{dog_name}} hit goal weight",
        'body': [
            "{{first_name}}. {{dog_name}} just reached {{target_weight}} kg — the number we set 12 weeks ago.",
            "Studies say a lean dog lives up to two years longer. You bought {{dog_name}} those years. That's not a hyperbolic email line — it's the actual literature.",
            "From here the app switches to maintenance mode: a wider calorie band, lighter weigh-ins, the same Bailey when you have questions.",
            "P.S. The progress card below is ready to share. Friends who've never weighed their dog will start after they see it.",
        ],
        'cta': 'Open maintenance mode',
    },
}


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'events': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _ref(email):
    return hashlib.sha256(
        f"{_REF_SALT}:{email.lower().strip()}".encode()
    ).hexdigest()[:16]


def main(dry_run=False):
    state = _load_state()
    state.setdefault('events', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    print('🔎 Walking users + dogs + milestones...')
    targets = []  # (user, dog, milestone_dict)
    for user in load_all_users(token):
        for dog in user.get('dogs', []):
            for m in load_dog_milestones(token, user['uid'], dog['dog_id']):
                event_key = f"{user['uid']}::{dog['dog_id']}::{m['key']}"
                if event_key in state['events']:
                    continue
                if m['key'] not in EN_SOURCES:
                    continue
                targets.append((user, dog, m))

    print(f'🏅 {len(targets)} new milestone crossings')
    if not targets:
        return

    if dry_run:
        for u, d, m in targets[:25]:
            print(f"   • {u['email']}  {d['name']}  {m['key']}  lang={u['language']}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, m in targets:
        email = user['email']
        lang = user.get('language') or 'en'
        en_src = EN_SOURCES[m['key']]
        kind = f"{KIND}_{m['key']}"
        ctx = {
            'first_name':    user.get('first_name', ''),
            'dog_name':      dog.get('name', 'your pup'),
            'target_weight': f"{dog.get('target_weight', 0):.1f}",
        }
        tpl = get_localized(kind, lang, en_src)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', en_src['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', en_src['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', en_src['cta']), ctx)

        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='celebrate', celebratory=True,
            dog_image_url=dog.get('image_url') or '',
            dog_name=dog.get('name', ''),
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': kind},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['events'][f"{user['uid']}::{dog['dog_id']}::{m['key']}"] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  {m["key"]}  ({dog["name"]})')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
