#!/usr/bin/env python3
"""Stuck on outline — draft with low progress, inactive ≥24h. CTA: Generate all."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from onbrief_users_loader import (
    get_access_token, load_users_dict, load_briefs_by_status, work_label, topic_label,
)
from onbrief_send import connect_sender, send_onbrief, load_state, save_state, remaining, APP_SLUG
from onbrief_templates import get_template, fill

KIND = f'{APP_SLUG}_stuck_on_outline'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'onbrief_stuck_on_outline_state.json'
MIN_AGE = timedelta(hours=24)


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = load_state(STATE_FILE)
    by_email, by_uid = load_users_dict(token)
    now = datetime.now(timezone.utc)
    candidates = []
    seen = set()
    for brief in load_briefs_by_status(token, ['draft', 'outline']) or []:
        uid = brief.get('user_id')
        if not uid or uid in seen:
            continue
        if uid in state.get('users', {}):
            continue
        progress = int(brief.get('progress') or 0)
        if progress >= 20:
            continue
        modified = brief.get('last_modified') or brief.get('created_at')
        if not modified:
            continue
        if modified.tzinfo is None:
            modified = modified.replace(tzinfo=timezone.utc)
        if now - modified < MIN_AGE:
            continue
        user = by_uid.get(uid)
        if not user or not user.get('email'):
            continue
        seen.add(uid)
        candidates.append((user, brief))

    print(f'🧭 {len(candidates)} stuck-on-outline candidates')
    if dry_run:
        for u, b in candidates[:15]:
            print(f"   • {u['email']}  progress={b.get('progress')}  {b.get('topic', '')[:40]}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, brief in candidates:
        if remaining() <= 0:
            break
        tpl = fill(
            get_template('stuck_on_outline'),
            first_name=user.get('first_name', 'there'),
            work_type=work_label(user, brief),
            topic=topic_label(user, brief),
        )
        result = send_onbrief(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, gradient='invite',
        )
        if result == 'sent':
            sent += 1
            state['users'][user['uid']] = {
                'email': user['email'],
                'sent_at': datetime.now().isoformat(),
                'brief_id': brief.get('brief_id'),
            }
            print(f"   ✅ [{sent}] {user['email']}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
