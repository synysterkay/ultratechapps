#!/usr/bin/env python3
"""Speech-ready — draft finished, nudge to rehearse once."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vowcraft_users_loader import (
    get_access_token, load_users_dict, load_speeches_by_status, role_label, couple_label,
)
from vowcraft_send import connect_sender, send_vowcraft, load_state, save_state, remaining, APP_SLUG
from vowcraft_templates import get_template, fill

KIND = f'{APP_SLUG}_speech_ready'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'vowcraft_speech_ready_state.json'
READY_STATUSES = ['completed', 'ready', 'generated']
MIN_AGE = timedelta(hours=2)


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
    for speech in load_speeches_by_status(token, READY_STATUSES) or []:
        uid = speech.get('user_id')
        if not uid or uid in seen or uid in state.get('users', {}):
            continue
        modified = speech.get('last_modified') or speech.get('completed_at') or speech.get('created_at')
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
        candidates.append((user, speech))

    print(f'🎤 {len(candidates)} speech-ready candidates')
    if dry_run:
        for u, s in candidates[:15]:
            print(f"   • {u['email']}  {couple_label(u, s)[:40]}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, speech in candidates:
        if remaining() <= 0:
            break
        tpl = fill(
            get_template('speech_ready'),
            first_name=user.get('first_name', 'there'),
            role=role_label(user, speech),
            couple=couple_label(user, speech),
        )
        result = send_vowcraft(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, gradient='celebrate',
            lang=user.get('language') or 'en',
        )
        if result == 'sent':
            sent += 1
            state['users'][user['uid']] = {
                'email': user['email'],
                'sent_at': datetime.now().isoformat(),
                'speech_id': speech.get('speech_id'),
            }
            print(f"   ✅ [{sent}] {user['email']}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
