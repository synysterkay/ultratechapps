#!/usr/bin/env python3
"""Deadline countdown — plan.deadline hits 7 / 3 / 1 / 0 days."""
from __future__ import annotations

import sys
from datetime import datetime, timezone, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from onbrief_users_loader import get_access_token, load_all_users, work_label, topic_label
from onbrief_send import connect_sender, send_onbrief, load_state, save_state, remaining, APP_SLUG
from onbrief_templates import get_template, fill

KIND = f'{APP_SLUG}_deadline'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'onbrief_deadline_state.json'
STAGES = [7, 3, 1, 0]


def _parse_deadline(raw) -> date | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()[:10]
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except Exception:
        return None


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    state = load_state(STATE_FILE)
    today = datetime.now(timezone.utc).date()
    candidates = []
    for user in load_all_users(token):
        plan = user.get('plan') or {}
        due = _parse_deadline(plan.get('deadline') or plan.get('dueDate'))
        if not due:
            continue
        delta = (due - today).days
        if delta not in STAGES:
            continue
        stage = str(delta)
        fired = set((state.get('users', {}).get(user['uid']) or {}).get('stages', []))
        if stage in fired:
            continue
        candidates.append((user, stage, due))

    print(f'⏰ {len(candidates)} deadline candidates')
    if dry_run:
        for u, s, due in candidates[:15]:
            print(f"   • {u['email']}  {s}d  due={due}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, stage, due in candidates:
        if remaining() <= 0:
            break
        tpl = fill(
            get_template('deadline', stage),
            first_name=user.get('first_name', 'there'),
            work_type=work_label(user),
            topic=topic_label(user),
        )
        result = send_onbrief(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, stage=stage, gradient='urgent',
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(user['uid'], {'stages': []})
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            print(f"   ✅ [{sent}] {user['email']}  {stage}d")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
