#!/usr/bin/env python3
"""
Abandoned-App Sender (PupShape)

Fires for users whose `usage.lastOpenMs` is older than 2 / 5 / 10 days
AND who don't have an active subscription (paid users are handled by
the in-app side; this sender's job is funnel rescue for free users).

Each stage fires exactly once per user; if a user re-opens the app
between stages, the in-app side resets `lastOpenMs` and the sender just
won't match them next run.

State cache: cache/abandoned_app_state.json
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
KIND = 'abandoned_app'
DEEP_LINK = 'pupshape://home'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'abandoned_app_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Stages: days since last open. Larger numbers first so we pick the
# strongest justified nudge each run.
STAGES = [10, 5, 2]


EN_SOURCES = {
    '2d': {
        'subject': "{{dog_name}}'s plan is waiting on a weigh-in",
        'body': [
            "{{first_name}}, the plan for {{dog_name}} only adapts as fast as the weigh-ins arrive. The last one is two days old.",
            "Two days isn't a problem yet — bodies don't change at that resolution. But the plan refresh that runs after each weigh-in is what catches plateaus before the slope flattens for real, and that loop hasn't run in 48 hours.",
            "Same scale, same time, before breakfast. The thirty-second version is the version that works.",
        ],
        'cta': "Log {{dog_name}}'s weigh-in",
    },
    '5d': {
        'subject': "Five days, no weigh-in — {{dog_name}}'s plan is flying blind",
        'body': [
            "{{first_name}}, the engine for {{dog_name}} hasn't had a fresh data point in five days. After five days the recommended calories drift toward defaults — which is fine, but defaults are what every generic calculator gives you.",
            "The personalised part — the bit you signed up for — only works when the weigh-in cadence keeps pace. One weigh-in resets the loop.",
            "P.S. If something specific happened (vet visit, scale broken, travel) just say — the plan can be paused properly instead of decaying.",
        ],
        'cta': "Reopen {{dog_name}}'s plan",
    },
    '10d': {
        'subject': "Ten days — should we pause {{dog_name}}'s plan?",
        'body': [
            "{{first_name}}, ten days without a weigh-in. We can either restart with a fresh number when you're ready, or we can pause {{dog_name}}'s plan properly so you don't get any more nudges.",
            "There's no judgment here. Real life crowds out apps, especially the daily ones. The plan and the data don't expire — they wait.",
            "Tap below to come back if now's the right time. If not, the silence is the answer and we'll go quiet on this thread.",
        ],
        'cta': "Restart {{dog_name}}'s plan",
    },
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
    return {'users': {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), indent=2)


def _last_open(user: dict):
    usage = user.get('usage') or {}
    raw = usage.get('lastOpenMs') or usage.get('last_open_ms') or usage.get('lastOpenAt')
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw / 1000.0, tz=timezone.utc)
        return datetime.fromisoformat(str(raw).replace('Z', '+00:00').replace(' ', 'T'))
    except Exception:
        return None


def _days_since_open(user: dict) -> int:
    last = _last_open(user)
    if last is None:
        return -1
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).days


def _pick_stage(days: int, fired: set) -> str:
    """Returns the largest unfired stage ≤ days, as a stage key ('10d',
    '5d', '2d'). Empty string if nothing to fire."""
    for s in STAGES:
        key = f'{s}d'
        if days >= s and key not in fired:
            return key
    return ''


def main(dry_run: bool = False) -> None:
    print(f"\n👋 Running {KIND}_sender (dry_run={dry_run})…")
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
        if is_paid(user):
            continue  # paid users handled in-app
        days = _days_since_open(user)
        if days < STAGES[-1]:
            continue
        fired = set((state.get('users', {}).get(uid) or {}).get('stages', []))
        stage_key = _pick_stage(days, fired)
        if not stage_key:
            continue
        dogs = user.get('dogs', [])
        lead_dog = dogs[0] if dogs else {'name': 'your pup', 'image_url': ''}
        candidates.append((user, lead_dog, stage_key, days))

    if not candidates:
        print('   ✅ No abandoned-app candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} abandoned-app emails")
        for u, d, s, dd in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  stage={s} (last open {dd}d)")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, stage_key, days in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name':  user.get('first_name', ''),
            'dog_name':    dog.get('name', 'your pup'),
            'days_since':  str(days),
        }
        en = EN_SOURCES[stage_key]
        tpl = get_localized(f"{KIND}_stage_{stage_key}", lang, en)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', en['subject']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in tpl.get('body', en['body'])]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', en['cta']), ctx)
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
            {'name': 'stage', 'value': stage_key},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(user) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            if stage_key not in rec['stages']:
                rec['stages'].append(stage_key)
            rec['last_sent_at'] = datetime.now().isoformat()
            rec['language'] = lang
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  stage={stage_key}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
