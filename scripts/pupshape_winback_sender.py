#!/usr/bin/env python3
"""
Winback Sender (PupShape)

Fires for users whose `subscription.status == 'cancelled'` at 7 / 30 /
60 / 90 days post-cancellation. Each stage gets exactly one shot per
user. After day 90 we stop nudging.

Renamed to `pupshape_winback_sender` so the import doesn't collide with
the Thesis winback_sender — both apps run in the same workflow.

State cache: cache/pupshape_winback_state.json
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
KIND = 'winback'
DEEP_LINK = 'pupshape://reactivate'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'pupshape_winback_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Days post-cancellation when each stage fires.
STAGES = [7, 30, 60, 90]


EN_SOURCES = {
    7: {
        'subject': "{{dog_name}}'s plan paused — quick question",
        'body': [
            "{{first_name}}, the plan for {{dog_name}} paused a week ago when the subscription ended. Free mode still tracks weigh-ins; what stops is the adaptive part — the daily recalc and the plateau-detection that does the actual work.",
            "If something specific broke, tell me — the engine is still being tuned and feedback at this stage actually changes the next version.",
            "If it just wasn't the right time, the door's open. The first week back is free; the plan picks up from {{dog_name}}'s last weigh-in, not from scratch.",
            "P.S. The data from your weeks of weigh-ins is still here. Switching Pro back on reactivates the recalc on the same curve.",
        ],
        'cta': "Reactivate for {{dog_name}}",
    },
    30: {
        'subject': "One month off — checking on {{dog_name}}",
        'body': [
            "{{first_name}}, it's been a month since the plan went quiet. Honest question: how is {{dog_name}} doing on the no-app version?",
            "The reason I ask: the engine's whole job is the in-between. The weigh-in is a snapshot; the plan that adapts between snapshots is what bends the curve. A month is long enough to see whether the gap matters.",
            "If it does, we'd love {{dog_name}} back. Same data, same plan, picks up from the last weigh-in.",
        ],
        'cta': "Bring {{dog_name}}'s plan back",
    },
    60: {
        'subject': "Two months — last gentle nudge for {{dog_name}}",
        'body': [
            "{{first_name}}, two months out. We won't email about this much longer — promises kept.",
            "What we're learning from users who came back: the curve almost always drifted in the wrong direction during the gap. Not anyone's fault — that's the nature of an adaptive plan with no one adapting.",
            "If you do want to restart, the path is the same as ever — just open the app and reactivate Pro. The data is intact.",
        ],
        'cta': "Restart {{dog_name}}'s plan",
    },
    90: {
        'subject': "Last note about {{dog_name}}",
        'body': [
            "{{first_name}}, this is the last winback email — promises kept.",
            "If you ever want to come back, the door is open and the data is still yours. {{dog_name}}'s history is one tap away in the app whenever you re-install.",
            "Wishing {{dog_name}} health, whichever path you take from here.",
        ],
        'cta': "Open PupShape",
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


def _ts(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00').replace(' ', 'T'))
    except Exception:
        return None


def _cancelled_at(user: dict):
    """Returns the timestamp the user effectively lapsed Pro.

    The Flutter subscription_mirror_service writes `status: 'inactive'`
    (Superwall's normalised status) — NOT `'cancelled'` — and doesn't
    persist a dedicated `cancelledAt` field, only `updatedAt`. So we
    accept both labels and use `updatedAt` as the cancel-time proxy.
    Anyone whose status is 'active' or 'unknown' is excluded.
    """
    sub = user.get('subscription') or {}
    status = str(sub.get('status', '')).lower()
    if status not in ('cancelled', 'inactive', 'lapsed', 'expired'):
        return None
    return _ts(
        sub.get('cancelledAt')
        or sub.get('cancelled_at')
        or sub.get('expiresAt')
        or sub.get('updatedAt')          # ← the Flutter mirror's stamp
        or sub.get('updated_at')
    )


def _next_unfired_stage(days_since: int, fired: set) -> int:
    eligible = [s for s in STAGES if s <= days_since and s not in fired]
    return max(eligible) if eligible else 0


def main(dry_run: bool = False) -> None:
    print(f"\n🪃 Running pupshape_{KIND}_sender (dry_run={dry_run})…")
    token = get_access_token()
    if not token:
        print("   ⚠️ no token — skipping")
        return

    users = list(load_all_users(token))
    state = _load_state()
    now = datetime.now(timezone.utc)

    candidates = []
    for user in users:
        uid = user.get('uid')
        email = user.get('email')
        if not uid or not email:
            continue
        cancelled = _cancelled_at(user)
        if not cancelled:
            continue
        if cancelled.tzinfo is None:
            cancelled = cancelled.replace(tzinfo=timezone.utc)
        days_since = (now - cancelled).days
        if days_since < STAGES[0]:
            continue
        fired = set((state.get('users', {}).get(uid) or {}).get('stages', []))
        stage = _next_unfired_stage(days_since, fired)
        if not stage:
            continue
        dogs = user.get('dogs', [])
        lead_dog = dogs[0] if dogs else {'name': 'your pup', 'image_url': ''}
        candidates.append((user, lead_dog, stage))

    if not candidates:
        print('   ✅ No winback candidates this run.'); return

    if dry_run:
        print(f"   [DRY] would send {len(candidates)} winback emails")
        for u, d, s in candidates[:10]:
            print(f"     - {u['email']}  ({d.get('name','?')})  stage={s}d")
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for user, dog, stage in candidates:
        email = user['email']
        lang = user.get('language') or 'en'
        ctx = {
            'first_name': user.get('first_name', ''),
            'dog_name':   dog.get('name', 'your pup'),
            'days_since': str(stage),
        }
        en = EN_SOURCES[stage]
        tpl = get_localized(f"{KIND}_stage_{stage}d", lang, en)
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
            {'name': 'stage', 'value': f'{stage}d'},
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
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            rec['language'] = lang
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  stage={stage}d  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
