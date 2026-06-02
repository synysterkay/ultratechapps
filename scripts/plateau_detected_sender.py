#!/usr/bin/env python3
"""
Plateau-Detected Sender (PupShape)

Fires when the in-app CaloriePlan flags `plateauDetected = true` for 3
consecutive Sundays — i.e. the engine has done the work AND wants to
explain itself. The trust pillar: shows the user the plan is alive and
not just a timer. Caps at one email per (uid, dog_id) per 14 days so
even a long plateau doesn't repeat.

State cache: cache/plateau_detected_state.json
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from pupshape_users_loader import (
    get_access_token, load_all_users, is_paid,
)
from pupshape_template_translator import get_localized
from pupshape_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'plateau_detected'
DEEP_LINK = 'pupshape://plan'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'plateau_detected_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

_COOLDOWN_DAYS = 14


EN_SOURCE = {
    'subject': "We mixed up {{dog_name}}'s plan — see what changed",
    'body': [
        "{{first_name}}, the engine flagged a plateau for {{dog_name}} and made an automatic adjustment. Here's what happened, and why.",
        "A plateau in a weight-loss plan is normal — the body adapts to the new intake and the slope flattens. The lazy answer is to wait it out. The honest answer is to break the pattern: shuffle macros, change the activity prompt, recalculate the deficit on the current weight instead of the starting weight.",
        "The plan you'll see when you open the app has done all three. The deficit is now {{plateau_action}} smaller than last week, plus a fresh activity nudge timed to {{dog_name}}'s usual walking window. Same goal, different route.",
        "P.S. This is the part of an adaptive plan that most owners never see. It's working in the background even when the scale isn't.",
    ],
    'cta': "See {{dog_name}}'s adjusted plan",
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


def _within_cooldown(prev_iso: str) -> bool:
    if not prev_iso:
        return False
    try:
        prev = datetime.fromisoformat(prev_iso)
    except Exception:
        return False
    return (datetime.now() - prev).days < _COOLDOWN_DAYS


def _plateau_active(dog: dict) -> bool:
    """Reads the CaloriePlan.plateauDetected flag.

    The Flutter CalorieEngine._detectPlateau already requires multiple
    sustained weigh-ins to flag a plateau (it's not a one-snapshot
    decision), so we trust the boolean and rely on the 14-day cooldown
    (above) to keep this email from re-firing during a long plateau.
    """
    plan = dog.get('calorie_plan') or dog.get('plan') or {}
    return bool(plan.get('plateauDetected') or plan.get('plateau_detected'))


def main(dry_run: bool = False) -> None:
    print(f"\n📈 Running {KIND}_sender (dry_run={dry_run})…")
    token = get_access_token()
    if not token:
        print("   ⚠️ no token — skipping")
        return

    users = list(load_all_users(token))
    state = _load_state()

    candidates = []
    for user in users:
        uid = user.get('uid')
        email = user.get('email')
        if not uid or not email:
            continue
        for dog in user.get('dogs', []):
            dog_id = dog.get('dog_id')
            if not dog_id:
                continue
            if not _plateau_active(dog):
                continue
            key = f"{uid}::{dog_id}"
            prev = (state.get('dogs', {}).get(key) or {}).get('sent_at')
            if _within_cooldown(prev):
                continue
            candidates.append((user, dog))

    if not candidates:
        print('   ✅ No plateau-detected candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} plateau emails")
        for u, d in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  {u.get('language','en')}")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        plan = dog.get('calorie_plan') or dog.get('plan') or {}
        action_kcal = plan.get('plateauActionKcal') or plan.get('plateau_action_kcal') or 60
        ctx = {
            'first_name':     user.get('first_name', ''),
            'dog_name':       dog.get('name', 'your pup'),
            'plateau_action': f"{int(action_kcal)} kcal",
        }
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCE['cta']), ctx)
        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='calm', celebratory=False,
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
            state.setdefault('dogs', {})[f"{user['uid']}::{dog['dog_id']}"] = {
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
