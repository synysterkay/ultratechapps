#!/usr/bin/env python3
"""Brief-tip sender — value advice for free Onbrief users (outline / generate / revise)."""
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from onbrief_users_loader import (
    get_access_token, load_all_users, load_briefs_by_status, is_paid,
    work_label, topic_label,
)
from onbrief_send import connect_sender, send_onbrief, load_state, save_state, remaining, APP_SLUG
from onbrief_templates import get_template, fill

KIND = f'{APP_SLUG}_brief_tip'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'onbrief_brief_tip_state.json'
STAGE_PRIORITY = ('revise', 'generate', 'outline')


def _days_since(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def _pick_stage(user, briefs, already):
    now = datetime.now(timezone.utc)
    days_signup = _days_since(user.get('created_at'))
    completed = [b for b in briefs if b.get('status') == 'completed']
    drafts = [b for b in briefs if b.get('status') in ('draft', 'outline')]
    active = [b for b in briefs if b.get('status') in ('in_progress', 'generating')]

    outline_ready = any((b.get('progress') or 0) < 20 for b in drafts if (b.get('progress') or 0) > 0)
    started = bool(completed) or bool(active) or any((b.get('progress') or 0) >= 20 for b in briefs)

    quiet = None
    for b in active + [x for x in drafts if (x.get('progress') or 0) >= 20]:
        last = b.get('last_modified') or b.get('created_at')
        if last:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            quiet = max(quiet or timedelta(0), now - last)

    plan = user.get('plan') or {}
    has_topic = bool((plan.get('topic') or '').strip()) or any(
        (b.get('topic') or '').strip() for b in briefs
    )

    for stage in STAGE_PRIORITY:
        if stage in already:
            continue
        if stage == 'revise':
            if started and quiet is not None and quiet >= timedelta(days=2):
                return stage
        elif stage == 'generate':
            if outline_ready and not started:
                return stage
        elif stage == 'outline':
            if (
                days_signup is not None
                and 1 <= days_signup <= 3
                and has_topic
                and not completed
                and not started
                and not outline_ready
            ):
                return stage
    return None


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    by_uid = defaultdict(list)
    for status in ('draft', 'outline', 'in_progress', 'generating', 'completed'):
        for b in load_briefs_by_status(token, [status]) or []:
            uid = b.get('user_id')
            if uid:
                by_uid[uid].append(b)

    state = load_state(STATE_FILE)
    candidates = []
    for user in load_all_users(token):
        if is_paid(user):
            continue
        email = (user.get('email') or '').strip()
        if not email:
            continue
        briefs = by_uid.get(user['uid'], [])
        fired = set((state.get('users', {}).get(user['uid']) or {}).get('stages', []))
        stage = _pick_stage(user, briefs, fired)
        if not stage:
            continue
        candidates.append((user, stage, briefs))

    print(f'✍️ {len(candidates)} brief-tip candidates')
    if dry_run:
        for u, s, _ in candidates[:15]:
            print(f"   • {u['email']}  stage={s}  lang={u.get('language')}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, stage, briefs in candidates:
        if remaining() <= 0:
            break
        brief = briefs[0] if briefs else None
        tpl = fill(
            get_template('brief_tip', stage),
            first_name=user.get('first_name', 'there'),
            work_type=work_label(user, brief),
            topic=topic_label(user, brief),
        )
        result = send_onbrief(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, stage=stage, lang=user.get('language') or 'en',
            gradient='invite',
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
