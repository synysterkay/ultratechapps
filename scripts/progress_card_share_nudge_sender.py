#!/usr/bin/env python3
"""
Progress-Card-Share-Nudge Sender (PupShape)

Fires 24h after a milestone milestone event is recorded for which the
user did NOT tap "Share this win" in-app. Re-offers the same card with
a one-line nudge, since the inbox is a second distribution surface for
the same shareable moment.

Dedupe per (uid, dog_id, milestone_key) — one nudge per milestone.

State cache: cache/progress_card_share_nudge_state.json
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
    get_access_token, load_all_users, load_dog_milestones, is_paid,
)
from pupshape_template_translator import get_localized
from pupshape_email_chrome import render as render_email
import localize_phrase

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'progress_card_share_nudge'
DEEP_LINK = 'pupshape://share'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'progress_card_share_nudge_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

_DELAY_HOURS = 24
_MAX_AGE_HOURS = 72  # don't re-surface milestones that are too old


_MILESTONE_LABELS = {
    'm25': '25%',
    'm50': '50%',
    'm75': '75%',
    'goal': 'goal',
    'm100': 'goal',
}


EN_SOURCE = {
    'subject': "{{dog_name}}'s {{milestone_label}} card — still yours to share",
    'body': [
        "{{first_name}}, {{dog_name}}'s {{milestone_label}} card is sitting in the app, unshared.",
        "Most progress on most apps is invisible. {{dog_name}}'s isn't — there's a rendered before/after card with the exact numbers. Two taps to send it to whichever friend asks \"how's your dog doing?\" most often.",
        "No pressure. Just easier to share now while the win is fresh than dig it out of an album in three months.",
        "P.S. The same card lives under {{dog_name}}'s journey screen forever — you can grab it any time.",
    ],
    'cta': "Share {{dog_name}}'s card",
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
    return {'events': {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _ts(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00').replace(' ', 'T'))
    except Exception:
        return None


def _is_ripe(milestone: dict) -> bool:
    """A milestone is ripe when it crossed ≥ _DELAY_HOURS ago but no more
    than _MAX_AGE_HOURS ago, AND the user didn't tap 'shared' in-app."""
    if milestone.get('shared'):
        return False
    crossed = _ts(milestone.get('crossed_at') or milestone.get('createdAt'))
    if not crossed:
        return False
    age = datetime.now(timezone.utc) - (crossed if crossed.tzinfo else crossed.replace(tzinfo=timezone.utc))
    return timedelta(hours=_DELAY_HOURS) <= age <= timedelta(hours=_MAX_AGE_HOURS)


def main(dry_run: bool = False) -> None:
    print(f"\n📣 Running {KIND}_sender (dry_run={dry_run})…")
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
            milestones = load_dog_milestones(token, uid, dog_id) or []
            for m in milestones:
                key = m.get('key') or m.get('milestone_key') or ''
                event_key = f"{uid}::{dog_id}::{key}"
                if event_key in state.get('events', {}):
                    continue
                if not _is_ripe(m):
                    continue
                candidates.append((user, dog, m))

    if not candidates:
        print('   ✅ No share-nudge candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} share nudges")
        for u, d, m in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  m={m.get('key')}")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, milestone in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        key = milestone.get('key') or milestone.get('milestone_key') or 'milestone'
        ctx = {
            'first_name':       user.get('first_name', ''),
            'dog_name':         dog.get('name', 'your pup'),
            'milestone_label':  _MILESTONE_LABELS.get(key, key),
        }
        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', EN_SOURCE['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCE['cta']), ctx)
        html = render_email(
            lang, paragraphs, cta_text, DEEP_LINK,
            sender_name='Bailey', app_name=APP_NAME,
            gradient='warm', celebratory=False,
            dog_image_url=dog.get('image_url') or '',
            dog_name=dog.get('name', ''),
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'milestone', 'value': str(key)},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state.setdefault('events', {})[f"{user['uid']}::{dog['dog_id']}::{key}"] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  ({dog["name"]})  m={key}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
