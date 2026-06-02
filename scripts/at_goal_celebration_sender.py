#!/usr/bin/env python3
"""
At-Goal-Celebration Sender (PupShape)

Fires once per dog when their latest weigh-in reaches the target:
  - loss plan: dog.weight ≤ dog.target_weight + 0.1 kg
  - gain plan: dog.weight ≥ dog.target_weight - 0.1 kg
This is the peak-emotional moment for a pet parent and the right place
to transition to maintenance voice (the second life of the app).

Dedupe per (uid, dog_id) — once a dog hits goal, this fires exactly once.

State cache: cache/at_goal_celebration_state.json
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
KIND = 'at_goal_celebration'
DEEP_LINK = 'pupshape://maintenance'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'at_goal_celebration_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Tolerance band around target weight (kg)
_TOLERANCE = 0.1


EN_SOURCE = {
    'subject': "{{dog_name}} hit goal weight 🎉",
    'body': [
        "{{first_name}}, this is the email you've been working toward.",
        "{{dog_name}} just landed on target: {{current_weight}} kg. From {{start_weight}} kg to here — that's {{total_delta}} kg of patient, daily work that no one but you saw the whole of.",
        "Here's the next chapter: maintenance. The plan now switches to holding this weight, which is a different game — small caloric tweaks instead of a steady deficit. The engine handles that automatically; your only job is the weigh-in cadence (every other week is enough now).",
        "P.S. Tell your vet at the next visit. They've seen the before; the after is yours to show.",
    ],
    'cta': "Switch {{dog_name}} to maintenance",
}


def _ref(email: str) -> str:
    h = hashlib.sha256(f"{_REF_SALT}::{email.lower()}".encode()).hexdigest()
    return h[:16]


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {'dogs': {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _at_goal(current: float, start: float, target: float) -> bool:
    """Returns True if the dog has reached (or crossed) target weight on
    either a loss plan or a gain plan."""
    if start is None or target is None or current is None:
        return False
    losing = start > target
    if losing:
        return current <= target + _TOLERANCE
    gaining = start < target
    if gaining:
        return current >= target - _TOLERANCE
    return False


def main(dry_run: bool = False) -> None:
    print(f"\n🎯 Running {KIND}_sender (dry_run={dry_run})…")
    token = get_access_token()
    if not token:
        print("   ⚠️ no token — skipping")
        return

    users = list(load_all_users(token))
    state = _load_state()
    already_sent = set(state.get('dogs', {}).keys())

    candidates = []
    for user in users:
        uid = user.get('uid')
        if not uid or not user.get('email'):
            continue
        for dog in user.get('dogs', []):
            dog_id = dog.get('dog_id')
            if not dog_id:
                continue
            key = f"{uid}::{dog_id}"
            if key in already_sent:
                continue
            target = dog.get('target_weight')
            start = dog.get('start_weight') or dog.get('initial_weight')
            current = dog.get('weight')
            if current is None:
                logs = load_dog_weight_logs(token, uid, dog_id)
                if logs:
                    logs.sort(key=lambda l: l.get('logged_at') or '')
                    current = logs[-1].get('weight')
                    if start is None and logs:
                        start = logs[0].get('weight')
            try:
                if _at_goal(float(current), float(start), float(target)):
                    candidates.append((user, dog, float(current), float(start), float(target)))
            except (TypeError, ValueError):
                continue

    if not candidates:
        print('   ✅ No dogs at goal this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} at-goal emails")
        for u, d, *_ in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  {u.get('language','en')}")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, current, start, target in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name':     user.get('first_name', ''),
            'dog_name':       dog.get('name', 'your pup'),
            'current_weight': f"{current:.1f}",
            'start_weight':   f"{start:.1f}",
            'target_weight':  f"{target:.1f}",
            'total_delta':    f"{abs(start - current):.1f}",
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
            state['dogs'][f"{user['uid']}::{dog['dog_id']}"] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
                'current_weight': current,
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
