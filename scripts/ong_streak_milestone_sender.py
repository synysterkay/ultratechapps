#!/usr/bin/env python3
"""Streak milestone — 3 / 7 / 14 / 30 days. Variable reward."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from ong_users_loader import get_access_token, load_all_users
from ong_send import connect_sender, send_ong, load_state, save_state, remaining, APP_SLUG
from ong_templates import get_template, fill

KIND = f'{APP_SLUG}_streak_milestone'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'ong_streak_milestone_state.json'
STAGES = [30, 14, 7, 3]


def _pick_stage(streak: int, fired: set):
    for s in STAGES:
        if streak >= s and str(s) not in fired:
            return s
    return None


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = load_state(STATE_FILE)
    candidates = []
    for user in load_all_users(token):
        streak = int(user.get('streak') or 0)
        if streak < STAGES[-1]:
            continue
        fired = set((state.get('users', {}).get(user['uid']) or {}).get('stages', []))
        stage = _pick_stage(streak, fired)
        if stage is None:
            continue
        candidates.append((user, stage, streak))

    print(f'🏅 {len(candidates)} streak-milestone candidates')
    if dry_run:
        for u, s, st in candidates[:15]:
            print(f"   • {u['email']}  stage={s}  streak={st}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, stage, streak in candidates:
        if remaining() <= 0:
            break
        tpl = fill(get_template('streak_milestone', stage), first_name=user.get('first_name', 'there'))
        result = send_ong(
            sender, email=user['email'], subject=tpl['subject'],
            paragraphs=tpl['body'], cta=tpl['cta'], kind=KIND, stage=stage, gradient='celebrate',
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            rec['stages'].append(str(stage))
            rec['last_sent_at'] = datetime.now().isoformat()
            print(f"   ✅ [{sent}] {user['email']}  {stage}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
