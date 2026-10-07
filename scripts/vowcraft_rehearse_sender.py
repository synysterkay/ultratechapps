#!/usr/bin/env python3
"""Rehearse tip — draft exists, quiet ≥1d, remind to say minute one aloud."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vowcraft_users_loader import (
    get_access_token, load_users_dict, load_speeches_by_status, role_label, couple_label,
)
from vowcraft_send import connect_sender, send_vowcraft, load_state, save_state, remaining, APP_SLUG
from vowcraft_templates import get_template, fill

KIND = f'{APP_SLUG}_rehearse'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'vowcraft_rehearse_state.json'
HAS_DRAFT = ['draft', 'outline', 'in_progress', 'generating', 'ready', 'completed']
MIN_QUIET = timedelta(days=1)


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = load_state(STATE_FILE)
    by_email, by_uid = load_users_dict(token)
    now = datetime.now(timezone.utc)
    latest = {}
    for speech in load_speeches_by_status(token, HAS_DRAFT) or []:
        uid = speech.get('user_id')
        if not uid:
            continue
        prev = latest.get(uid)
        if not prev or (speech.get('last_modified') or datetime.min.replace(tzinfo=timezone.utc)) >= (
            prev.get('last_modified') or datetime.min.replace(tzinfo=timezone.utc)
        ):
            latest[uid] = speech

    candidates = []
    for uid, speech in latest.items():
        if uid in state.get('users', {}):
            continue
        modified = speech.get('last_modified') or speech.get('created_at')
        if not modified:
            continue
        if modified.tzinfo is None:
            modified = modified.replace(tzinfo=timezone.utc)
        if now - modified < MIN_QUIET:
            continue
        user = by_uid.get(uid)
        if not user or not user.get('email'):
            continue
        # Tip for free users primarily; paid can still get rehearse as retention tip
        candidates.append((user, speech))

    print(f'🗣️ {len(candidates)} rehearse-tip candidates')
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
            get_template('rehearse'),
            first_name=user.get('first_name', 'there'),
            role=role_label(user, speech),
            couple=couple_label(user, speech),
        )
        result = send_vowcraft(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, gradient='invite',
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
