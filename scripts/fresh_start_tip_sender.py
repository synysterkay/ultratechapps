#!/usr/bin/env python3
"""Fresh Start value tips — Auth-export audience (behavioral Firestore TBD).

Sends once-ever tip stages to Free Start users from firebase_exports.
Tags: app=fresh_start, kind=fresh_start_tip, stage, language=en
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, has_email_credentials, SKIP_RESULTS
from firebase_user_loader import FirebaseUserLoader

APP_NAME = 'Fresh Start'
APP_SLUG = 'fresh_start'
KIND = 'fresh_start_tip'
APP_STORE = 'https://apps.apple.com/app/fresh-start-breakup-therapy-ai/id6749954260'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'fresh_start_tip_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
DAILY_CAP = int(os.getenv('FRESH_START_TIP_DAILY_CAP', '40'))

# (stage, min_days_since_signup, max_days)
STAGES = [
    ('emergency', 0, 21),
    ('morning', 22, 60),
    ('no_contact', 61, 9999),
]
EN_SOURCES = {
    'emergency': {
        'subject': 'Tip: practice Emergency Mode once while calm',
        'body': [
            "When the 3AM loop hits, willpower is already gone. Tip: run Emergency Mode once today while you're calm so the path is familiar.",
            "Open Fresh Start → Emergency Mode → play once. Thirty seconds. That's the whole practice.",
            "P.S. You're not fixing the whole breakup today — you're installing an exit for tonight.",
        ],
        'cta': 'Open Emergency Mode',
    },
    'morning': {
        'subject': 'Morning tip: one sentence before you check their profile',
        'body': [
            "Before you open their socials, write one sentence: \"Checking this will cost me X hours of calm.\" Tip: name the cost out loud — it breaks autopilot more than \"don't look.\"",
            "If the urge wins anyway, open Emergency Mode after — interrupt the spiral, don't lecture yourself.",
            "P.S. Progress is fewer checks this week, not zero forever.",
        ],
        'cta': 'Open Fresh Start',
    },
    'no_contact': {
        'subject': 'No-contact tip: replace the check with a 2-minute ritual',
        'body': [
            "When you want to check their page, swap in a fixed 2-minute ritual instead (walk to the door, cold water, Emergency Mode). Tip: the brain needs a replacement, not a void.",
            "Open the app and pick one ritual you'll use this week. Same every time = easier than debating.",
            "P.S. This is the last tip in this short series. You're allowed to go quiet.",
        ],
        'cta': 'Open Fresh Start',
    },
}


def _ref(email: str) -> str:
    return hashlib.sha256(f'{_REF_SALT}:{email.lower()}'.encode()).hexdigest()[:16]


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


def _users_from_export():
    loader = FirebaseUserLoader()
    # Prefer Fresh Start export names
    for name in (
        'fresh_start_users.json',
        'breakuptherapy-e7dc0_fresh.json',
        'fresh_start_fresh.json',
        'breakup_therapy_fresh.json',
    ):
        path = loader.exports_dir / name
        if path.exists():
            try:
                data = json.loads(path.read_text())
                users = data if isinstance(data, list) else data.get('users', [])
                if users:
                    print(f'   📦 using export {path.name} ({len(users)})')
                    return users
            except Exception:
                pass
    return []


def _email_of(u: dict) -> str:
    return (u.get('email') or u.get('Email') or '').strip().lower()


def _created_days(u: dict) -> int | None:
    for key in ('createdAt', 'creationTime', 'created_at'):
        raw = u.get(key)
        if raw is None or raw == '':
            continue
        try:
            if isinstance(raw, str) and raw.isdigit():
                raw = int(raw)
            if isinstance(raw, (int, float)):
                dt = datetime.fromtimestamp(
                    raw / (1000 if raw > 1e12 else 1), tz=timezone.utc,
                )
            else:
                dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
            return (datetime.now(timezone.utc) - dt).days
        except Exception:
            continue
    return None


def main(dry_run=False):
    state = _load_state()
    users = _users_from_export()
    if not users:
        print('⚠️ No Fresh Start Auth export found — skip tips')
        return

    candidates = []
    for u in users:
        email = _email_of(u)
        if not email or '@' not in email:
            continue
        days = _created_days(u)
        if days is None:
            days = 30  # unknown age → morning tip band
        fired = set((state.get('users', {}).get(email) or {}).get('stages', []))
        for stage, lo, hi in STAGES:
            if stage in fired:
                continue
            if lo <= days <= hi:
                candidates.append((email, stage, days))
                break

    print(f'💛 {len(candidates)} Fresh Start tip candidates (cap={DAILY_CAP})')
    candidates = candidates[:DAILY_CAP]
    if dry_run:
        for email, stage, days in candidates[:20]:
            print(f'   • {email}  stage={stage}  age={days}d')
        print('🏁 DRY RUN')
        return
    if not candidates:
        return
    if not has_email_credentials():
        print('❌ Email credentials not set')
        return

    # Lazy import chrome — reuse breakup-style if present, else thesis chrome
    try:
        from thesis_email_chrome import render as render_email
    except Exception:
        print('❌ no email chrome')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for email, stage, days in candidates:
        src = EN_SOURCES[stage]
        html = render_email(
            'en', src['body'], src['cta'], APP_STORE,
            sender_name='Casey', app_name=APP_NAME, gradient='invite',
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': 'en'},
        ]
        result = sender.send_email(
            to_email=email, subject=src['subject'], html_body=html,
            from_name=APP_NAME, tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(email, {'stages': []})
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            print(f'   ✅ [{sent}] {email}  {stage}')
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} {result}')
        else:
            failed += 1
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
