#!/usr/bin/env python3
"""Reveal is live — resolved prediction they haven't opened. Variable reward."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from ong_users_loader import get_access_token, load_all_users, unopened_reveals
from ong_send import connect_sender, send_ong, load_state, save_state, remaining, APP_SLUG
from ong_templates import get_template, fill

KIND = f'{APP_SLUG}_reveal_live'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'ong_reveal_live_state.json'


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = load_state(STATE_FILE)
    sent_uids = set((state.get('users') or {}).keys())
    candidates = []
    for user in load_all_users(token):
        if not user.get('notify_reveals', True):
            continue
        if user['uid'] in sent_uids:
            continue
        if unopened_reveals(user) < 1:
            continue
        candidates.append(user)

    print(f'🔓 {len(candidates)} reveal-live candidates')
    if dry_run:
        for u in candidates[:15]:
            print(f"   • {u['email']}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    tpl = get_template('reveal_live')
    sent = failed = 0
    for user in candidates:
        if remaining() <= 0:
            break
        filled = fill(tpl, first_name=user.get('first_name', 'there'))
        result = send_ong(
            sender, email=user['email'], subject=filled['subject'],
            paragraphs=filled['body'], cta=filled['cta'], kind=KIND, gradient='celebrate',
        )
        if result == 'sent':
            sent += 1
            state['users'][user['uid']] = {
                'sent_at': datetime.now().isoformat(),
                'reveals': unopened_reveals(user),
            }
            print(f"   ✅ [{sent}] {user['email']}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
