#!/usr/bin/env python3
"""First-brief-complete — celebrate + export PDF. Batch backup for the instant Edge Function."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import instant_dedup
from onbrief_users_loader import get_access_token, load_users_dict, load_briefs_by_status, work_label, topic_label
from onbrief_send import connect_sender, send_onbrief, load_state, save_state, remaining, APP_SLUG
from onbrief_templates import get_template, fill

KIND = f'{APP_SLUG}_first_complete'
EVENT_KIND = 'onbrief_complete'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'onbrief_first_complete_state.json'


def main(dry_run=False):
    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    handled = instant_dedup.fetch_handled_uids(EVENT_KIND)
    if handled:
        print(f'   📌 {len(handled)} already handled by instant path — skipping')

    state = load_state(STATE_FILE)
    by_email, by_uid = load_users_dict(token)
    candidates = []
    seen = set()
    for brief in load_briefs_by_status(token, ['completed']) or []:
        uid = brief.get('user_id')
        if not uid or uid in seen or uid in handled:
            continue
        seen.add(uid)
        if uid in state.get('users', {}):
            continue
        user = by_uid.get(uid)
        if not user or not user.get('email'):
            continue
        candidates.append((user, brief))

    print(f'📄 {len(candidates)} first-complete candidates')
    if dry_run:
        for u, b in candidates[:15]:
            print(f"   • {u['email']}  {b.get('topic', '')[:40]}")
        return
    if not candidates:
        return

    sender = connect_sender()
    if not sender:
        return
    sent = failed = 0
    for user, brief in candidates:
        if remaining() <= 0:
            break
        tpl = fill(
            get_template('first_complete'),
            first_name=user.get('first_name', 'there'),
            work_type=work_label(user, brief),
            topic=topic_label(user, brief),
        )
        result = send_onbrief(
            sender, email=user['email'], subject=tpl['subject'], paragraphs=tpl['body'],
            cta=tpl['cta'], kind=KIND, gradient='celebrate',
        )
        if result == 'sent':
            sent += 1
            state['users'][user['uid']] = {
                'email': user['email'],
                'sent_at': datetime.now().isoformat(),
                'brief_id': brief.get('brief_id'),
            }
            instant_dedup.record_sent(
                EVENT_KIND, uid=user['uid'], app_id=APP_SLUG,
                recipient=user['email'], language=user.get('language', 'en'),
            )
            print(f"   ✅ [{sent}] {user['email']}")
        else:
            failed += 1
    sender.disconnect()
    save_state(STATE_FILE, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
