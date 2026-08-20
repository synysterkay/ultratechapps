#!/usr/bin/env python3
"""Weekly recap — Sundays, active in last 14 days. Investment."""
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from ong_users_loader import (
    get_access_token, load_all_users, days_since_open,
    predictions_created, answers_count,
)
from ong_send import connect_sender, send_ong, load_state, save_state, remaining, APP_SLUG
from ong_templates import get_template, fill

KIND = f'{APP_SLUG}_weekly_recap'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'ong_weekly_recap_state.json'


def _week_key() -> str:
    n = datetime.now(timezone.utc)
    return n.strftime('%G-W%V')


def _summary(user: dict) -> str:
    preds = predictions_created(user)
    answers = answers_count(user)
    streak = int(user.get('streak') or 0)
    karma = int(user.get('karma') or 0)
    return (
        f"{preds} prediction{'s' if preds != 1 else ''} created · "
        f"{answers} answer{'s' if answers != 1 else ''} locked · "
        f"streak {streak} · karma {karma}"
    )


def main(dry_run=False):
    now = datetime.now(timezone.utc)
    if now.weekday() != 6:
        print('📅 Not Sunday UTC — weekly recap skipped')
        return

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    week = _week_key()
    state = load_state(STATE_FILE)
    state.setdefault('weeks', {})
    state['weeks'].setdefault(week, {})

    candidates = []
    for user in load_all_users(token):
        if user['uid'] in state['weeks'][week]:
            continue
        days = days_since_open(user)
        if days < 0 or days > 14:
            continue
        if predictions_created(user) < 1 and answers_count(user) < 1:
            continue
        candidates.append(user)

    print(f'📊 {len(candidates)} weekly-recap candidates ({week})')
    if dry_run:
        for u in candidates[:15]:
            print(f"   • {u['email']}  {_summary(u)}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    tpl = get_template('weekly_recap')
    sent = failed = 0
    for user in candidates:
        if remaining() <= 0:
            break
        filled = fill(
            tpl,
            first_name=user.get('first_name', 'there'),
            week_summary=_summary(user),
        )
        result = send_ong(
            sender, email=user['email'], subject=filled['subject'],
            paragraphs=filled['body'], cta=filled['cta'], kind=KIND, gradient='calm',
        )
        if result == 'sent':
            sent += 1
            state['weeks'][week][user['uid']] = True
            print(f"   ✅ [{sent}] {user['email']}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
