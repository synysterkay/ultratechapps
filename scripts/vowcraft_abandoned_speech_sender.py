#!/usr/bin/env python3
"""Abandoned speech — unfinished 2d / 5d / 10d."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vowcraft_users_loader import (
    get_access_token, load_users_dict, load_speeches_by_status, role_label, couple_label,
    last_open_ms,
)
from vowcraft_send import connect_sender, send_vowcraft, load_state, save_state, remaining, APP_SLUG
from vowcraft_templates import get_template, fill

KIND = f'{APP_SLUG}_abandoned_speech'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'vowcraft_abandoned_speech_state.json'
STAGES = [10, 5, 2]
UNFINISHED = ['draft', 'outline', 'in_progress', 'generating', 'ready']


def _age_days(speech) -> int:
    modified = speech.get('last_modified') or speech.get('created_at')
    if not modified:
        return -1
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - modified).days


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
    by_email, by_uid = load_users_dict(token)
    latest = {}
    for speech in load_speeches_by_status(token, UNFINISHED) or []:
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
        days = _age_days(speech)
        if days < STAGES[-1]:
            continue
        user = by_uid.get(uid)
        if not user or not user.get('email'):
            continue
        if last_open_ms(user) is None and not user.get('last_sign_in'):
            continue
        fired = set((state.get('users', {}).get(uid) or {}).get('stages', []))
        stage = _pick_stage(days, fired)
        if not stage:
            continue
        candidates.append((user, speech, stage, days))

    print(f'👋 {len(candidates)} abandoned-speech candidates')
    if dry_run:
        for u, s, stage, d in candidates[:15]:
            print(f"   • {u['email']}  stage={stage}  ({d}d)  {couple_label(u, s)[:40]}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, speech, stage, days in candidates:
        if remaining() <= 0:
            break
        tpl = fill(
            get_template('abandoned_speech', stage),
            first_name=user.get('first_name', 'there'),
            role=role_label(user, speech),
            couple=couple_label(user, speech),
        )
        result = send_vowcraft(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, stage=stage, gradient='invite',
            lang=user.get('language') or 'en',
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
