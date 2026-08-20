#!/usr/bin/env python3
"""Waiting on you — tagged, unanswered, inactive 1d / 3d. External trigger."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from ong_users_loader import get_access_token, load_all_users, days_since_open, unanswered_invites
from ong_send import connect_sender, send_ong, load_state, save_state, remaining, APP_SLUG
from ong_templates import get_template, fill

KIND = f'{APP_SLUG}_waiting_on_you'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'ong_waiting_on_you_state.json'
STAGES = [3, 1]


def _pick_stage(days: int, fired: set) -> str:
    for s in STAGES:
        key = f'{s}d'
        if days >= s and key not in fired:
            return key
    return ''


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = load_state(STATE_FILE)
    candidates = []
    for user in load_all_users(token):
        if not user.get('notify_invites', True):
            continue
        if unanswered_invites(user) < 1:
            continue
        days = days_since_open(user)
        if days < 0:
            days = STAGES[-1]
        if days < STAGES[-1]:
            continue
        fired = set((state.get('users', {}).get(user['uid']) or {}).get('stages', []))
        stage = _pick_stage(days, fired)
        if not stage:
            continue
        candidates.append((user, stage, days))

    print(f'📩 {len(candidates)} waiting-on-you candidates')
    if dry_run:
        for u, s, d in candidates[:15]:
            print(f"   • {u['email']}  stage={s}  ({d}d)")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, stage, days in candidates:
        if remaining() <= 0:
            break
        tpl = fill(get_template('waiting_on_you', stage), first_name=user.get('first_name', 'there'))
        result = send_ong(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, stage=stage, gradient='urgent',
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            print(f"   ✅ [{sent}] {user['email']}  {stage}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
