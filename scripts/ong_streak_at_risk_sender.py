#!/usr/bin/env python3
"""Streak at risk — streak ≥ 3, no open today, after 18:00 UTC."""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from ong_users_loader import get_access_token, load_all_users, days_since_open
from ong_send import connect_sender, send_ong, load_state, save_state, remaining, APP_SLUG
from ong_templates import get_template, fill

KIND = f'{APP_SLUG}_streak_at_risk'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'ong_streak_at_risk_state.json'


def _today_key() -> str:
    n = datetime.now(timezone.utc)
    return f'{n.year}-{n.month:02d}-{n.day:02d}'


def main(dry_run=False):
    if datetime.now(timezone.utc).hour < 18:
        print('🕒 Pre-18:00 UTC — streak window not open yet')
        return

    state = load_state(STATE_FILE)
    state.setdefault('days', {})
    today = _today_key()
    state['days'].setdefault(today, {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    targets = []
    for user in load_all_users(token):
        if not user.get('notify_streaks', True):
            continue
        if user['uid'] in state['days'][today]:
            continue
        streak = int(user.get('streak') or 0)
        if streak < 3:
            continue
        if days_since_open(user) < 1:
            continue
        targets.append((user, streak))

    print(f'🔥 {len(targets)} streaks at risk')
    if dry_run:
        for u, s in targets[:20]:
            print(f"   • {u['email']}  streak={s}")
        return
    if not targets:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, streak in targets:
        if remaining() <= 0:
            break
        filled = fill(
            get_template('streak_at_risk'),
            first_name=user.get('first_name', 'there'),
            streak=streak,
        )
        result = send_ong(
            sender, email=user['email'], subject=filled['subject'],
            paragraphs=filled['body'], cta=filled['cta'], kind=KIND, gradient='urgent',
        )
        if result == 'sent':
            sent += 1
            state['days'][today][user['uid']] = True
            print(f"   ✅ [{sent}] {user['email']}  streak={streak}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
