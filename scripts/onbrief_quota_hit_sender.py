#!/usr/bin/env python3
"""Quota-hit upgrade — 24h / 72h / 7d if the instant Edge Function missed."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import instant_dedup
from onbrief_users_loader import get_access_token, load_all_users, is_paid, work_label, topic_label
from onbrief_send import connect_sender, send_onbrief, load_state, save_state, remaining, APP_SLUG
from onbrief_templates import get_template, fill

KIND = f'{APP_SLUG}_quota_hit'
EVENT_KIND = 'onbrief_quota_hit'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'onbrief_quota_hit_state.json'
STAGES = [
    ('7d', 7),
    ('72h', 3),
    ('24h', 1),
]


def _used_at(user: dict):
    usage = user.get('usage') or {}
    raw = usage.get('freeChapterUsedAt') or usage.get('free_chapter_used_at')
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except Exception:
            return None
    return None


def _pick_stage(days: int, fired: set) -> str:
    for key, threshold in STAGES:
        if days >= threshold and key not in fired:
            return key
    return ''


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    handled = instant_dedup.fetch_handled_uids(EVENT_KIND)
    state = load_state(STATE_FILE)
    now = datetime.now(timezone.utc)
    candidates = []
    for user in load_all_users(token):
        if is_paid(user):
            continue
        if user['uid'] in handled:
            continue
        usage = user.get('usage') or {}
        if usage.get('freeChapterUsed') is not True and usage.get('free_chapter_used') is not True:
            continue
        used = _used_at(user)
        if not used:
            continue
        if used.tzinfo is None:
            used = used.replace(tzinfo=timezone.utc)
        days = (now - used).days
        fired = set((state.get('users', {}).get(user['uid']) or {}).get('stages', []))
        stage = _pick_stage(days, fired)
        if not stage:
            continue
        candidates.append((user, stage, days))

    print(f'💰 {len(candidates)} quota-hit candidates')
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
        tpl = fill(
            get_template('quota_hit', stage),
            first_name=user.get('first_name', 'there'),
            work_type=work_label(user),
            topic=topic_label(user),
        )
        result = send_onbrief(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, stage=stage, gradient='upgrade',
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
