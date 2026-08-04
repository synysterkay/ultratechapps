#!/usr/bin/env python3
"""
Predictify Soccer promo blast — free users only, 4 stable cohorts.

Resend uses a new CAMPAIGN_ID so every non-subscriber gets the promo again
(e.g. after a price change). Dedup is per campaign only.

Usage:
  python3 scripts/predictify_pro_promo_sender.py --dry-run --part 1 --limit 10
  python3 scripts/predictify_pro_promo_sender.py --part 1
  python3 scripts/predictify_pro_promo_sender.py --auto-part
  python3 scripts/predictify_pro_promo_sender.py --status
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import requests  # noqa: E402

from firebase_user_loader import FirebaseUserLoader  # noqa: E402
from firestore_activity_loader import FirestoreActivityLoader  # noqa: E402
from gmail_sender import GmailSender, has_email_credentials  # noqa: E402
from predictify_v2.pro_yearly_promo_html import (  # noqa: E402
    PREVIEW,
    SUBJECT,
    build_pro_yearly_promo_html,
)

STATE_PATH = ROOT / 'cache' / 'predictify_pro_promo_state.json'
CAMPAIGN_ID = 'yearly_promo_pricechange_aug2026'
KIND_PREFIX = 'pro_yearly_promo_pricechange'
NUM_PARTS = 4
CAMPAIGN_DAY_PARTS = {
    '2026-08-04': 1,
    '2026-08-05': 2,
    '2026-08-06': 3,
    '2026-08-07': 4,
}
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

UNSUB_BASE = os.environ.get(
    'PREDICTIFY_UNSUBSCRIBE_URL',
    'https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-unsubscribe',
)
UNSUB_SECRET = os.environ.get('PREDICTIFY_UNSUBSCRIBE_SECRET', '')
MARKETING_SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
MARKETING_SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _first_name(display_name: str | None, email: str) -> str:
    name = (display_name or '').strip()
    if name:
        token = name.split()[0]
        if token and '@' not in token and len(token) > 1:
            return token[:1].upper() + token[1:] if token[0].islower() else token
    local = email.split('@')[0].split('.')[0].split('_')[0]
    if local and local.isalpha() and len(local) > 1:
        return local[:1].upper() + local[1:].lower()
    return 'there'


def _unsub_url(email: str) -> str:
    payload = f'{email.lower().strip()}|predictify'.encode('utf-8')
    e = base64.urlsafe_b64encode(payload).rstrip(b'=').decode('ascii')
    if UNSUB_SECRET:
        s = hmac.new(UNSUB_SECRET.encode('utf-8'), e.encode('ascii'), hashlib.sha256).hexdigest()[:32]
        return f'{UNSUB_BASE}?e={e}&s={s}'
    return f'{UNSUB_BASE}?e={e}'


def _part_for_uid(uid: str) -> int:
    """Stable 1..4 cohort from uid."""
    h = int(hashlib.sha256(uid.encode('utf-8')).hexdigest(), 16)
    return (h % NUM_PARTS) + 1


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {
        'campaign': CAMPAIGN_ID,
        'started_at': _utc_now(),
        'parts': {str(i): {'sent_count': 0, 'completed_at': None} for i in range(1, NUM_PARTS + 1)},
        'sent': {},
        'failed': {},
    }


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state['updated_at'] = _utc_now()
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


def _is_subscriber(activity: dict | None) -> bool:
    if not activity:
        return False
    return bool(activity.get('isPremium') or activity.get('isSubscribed'))


def _load_suppressed_emails() -> set[str]:
    suppressed: set[str] = set()
    if not MARKETING_SUPABASE_URL or not MARKETING_SUPABASE_KEY:
        print('   ⚠️ Marketing Supabase creds missing — suppression list empty')
        return suppressed
    headers = {
        'apikey': MARKETING_SUPABASE_KEY,
        'Authorization': f'Bearer {MARKETING_SUPABASE_KEY}',
    }
    try:
        r = requests.get(
            f'{MARKETING_SUPABASE_URL}/rest/v1/email_events',
            params={
                'select': 'recipient',
                'event_type': 'in.(email.bounced,email.complained)',
                'recipient': 'not.is.null',
                'limit': '10000',
            },
            headers=headers,
            timeout=20,
        )
        if r.ok:
            for row in r.json():
                rec = (row.get('recipient') or '').lower()
                if rec:
                    suppressed.add(rec)
    except Exception as e:
        print(f'   ⚠️ bounce/complaint load failed: {e}')

    for scope in ('predictify', 'predictify_soccer', '*', 'global'):
        try:
            r = requests.get(
                f'{MARKETING_SUPABASE_URL}/rest/v1/email_suppressions',
                params={
                    'select': 'recipient',
                    'app': f'eq.{scope}',
                    'recipient': 'not.is.null',
                    'limit': '10000',
                },
                headers=headers,
                timeout=20,
            )
            if r.ok:
                for row in r.json():
                    rec = (row.get('recipient') or '').lower()
                    if rec:
                        suppressed.add(rec)
        except Exception as e:
            print(f'   ⚠️ suppression load failed ({scope}): {e}')
    return suppressed


def _load_recipients(refresh_activity: bool) -> tuple[list[dict], int]:
    loader = FirebaseUserLoader()
    users_by_app = loader.load_users_by_app()
    users = users_by_app.get('Predictify', [])
    if not users:
        raise SystemExit('No Predictify users loaded — refresh Firebase export first.')

    activity_loader = FirestoreActivityLoader()
    cache_file = activity_loader.cache_dir / 'predictify_activity.json'
    if refresh_activity:
        fetched = activity_loader.fetch_user_activity('Predictify')
    else:
        fetched = activity_loader._load_cache(cache_file)
    activity_count = len(fetched)

    by_email, by_uid = activity_loader.load_activity('Predictify', users=users)

    recipients = []
    skipped_sub = 0
    for u in users:
        email = (u.get('email') or '').lower().strip()
        uid = u.get('uid') or u.get('localId') or ''
        if not email or not uid or not EMAIL_RE.match(email):
            continue
        activity = by_uid.get(uid) or by_email.get(email) or {}
        if _is_subscriber(activity):
            skipped_sub += 1
            continue
        recipients.append({
            'email': email,
            'uid': uid,
            'display_name': u.get('display_name', ''),
            'first_name': _first_name(u.get('display_name'), email),
            'part': _part_for_uid(uid),
        })
    print(f'   Subscribers excluded: {skipped_sub:,}  |  Firestore activity docs: {activity_count:,}')
    return recipients, activity_count


def _auto_part(state: dict) -> int:
    today = _today()
    if today in CAMPAIGN_DAY_PARTS:
        return CAMPAIGN_DAY_PARTS[today]
    started = state.get('started_at') or _utc_now()
    try:
        start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
    except ValueError:
        start_dt = datetime.now(timezone.utc)
    days = (datetime.now(timezone.utc) - start_dt).days
    return min(NUM_PARTS, max(1, days + 1))


def _print_status(state: dict, recipients: list[dict] | None = None) -> None:
    print(f'\n=== Predictify promo campaign: {state.get("campaign", CAMPAIGN_ID)} ===')
    print(f'Started: {state.get("started_at", "?")}')
    sent = state.get('sent') or {}
    failed = state.get('failed') or {}
    print(f'Total sent: {len(sent):,}  |  Failed: {len(failed):,}')
    for p in range(1, NUM_PARTS + 1):
        ps = sum(1 for v in sent.values() if v.get('part') == p)
        pinfo = (state.get('parts') or {}).get(str(p), {})
        print(f'  Part {p}: {ps:,} sent' + (f' (completed {pinfo.get("completed_at")})' if pinfo.get('completed_at') else ''))
    if recipients is not None:
        by_part = {p: 0 for p in range(1, NUM_PARTS + 1)}
        already = set(sent.keys())
        for r in recipients:
            if r['email'] not in already:
                by_part[r['part']] += 1
        print('Remaining eligible (not yet sent):')
        for p in range(1, NUM_PARTS + 1):
            print(f'  Part {p}: {by_part[p]:,}')


def run(
    *,
    part: int,
    dry_run: bool = False,
    limit: int = 0,
    sleep: float = 0.3,
    refresh_activity: bool = True,
) -> None:
    if not dry_run and not has_email_credentials():
        raise SystemExit('Email credentials missing (EMAIL_PROVIDER + API key)')

    os.environ.setdefault('EMAIL_PROVIDER', 'zeptomail')
    os.environ.setdefault('PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL', 'hello@predictifyfootball.com')
    os.environ.setdefault('PREDICTIFY_ZEPTOMAIL_SENDER_NAME', 'Predictify')

    state = _load_state()
    if state.get('campaign') != CAMPAIGN_ID:
        state = {
            'campaign': CAMPAIGN_ID,
            'started_at': _utc_now(),
            'parts': {str(i): {'sent_count': 0, 'completed_at': None} for i in range(1, NUM_PARTS + 1)},
            'sent': {},
            'failed': {},
        }

    pinfo = (state.get('parts') or {}).get(str(part), {})
    if pinfo.get('completed_at') and not dry_run:
        print(f'Part {part} already completed at {pinfo["completed_at"]} — skipping.')
        return

    print(f'Loading Predictify free users (part {part}/{NUM_PARTS})…')
    recipients, activity_count = _load_recipients(refresh_activity=refresh_activity)
    if not dry_run and activity_count < 500:
        raise SystemExit(
            'Firestore activity too sparse — refusing live send without subscription data. '
            'Set FIREBASE_TOKEN and retry.'
        )
    suppressed = _load_suppressed_emails()
    print(f'   Free users: {len(recipients):,}  |  Suppressed: {len(suppressed):,}')

    sent_map = state.setdefault('sent', {})
    cohort = [
        r for r in recipients
        if r['part'] == part
        and r['email'] not in sent_map
        and r['email'] not in suppressed
    ]
    if limit > 0:
        cohort = cohort[:limit]

    print(f'Part {part} queue: {len(cohort):,} emails this run')
    if not cohort:
        print('Nothing to send.')
        parts = state.setdefault('parts', {})
        parts.setdefault(str(part), {})['completed_at'] = _utc_now()
        _save_state(state)
        return

    sender = None
    if not dry_run:
        sender = GmailSender(
            sender_email=os.environ['PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL'],
            sender_name=os.environ['PREDICTIFY_ZEPTOMAIL_SENDER_NAME'],
        )
        if not sender.connect():
            raise SystemExit('ZeptoMail connect failed')

    kind = f'{KIND_PREFIX}_p{part}'
    sent_n = failed_n = skipped_n = 0

    for i, r in enumerate(cohort, 1):
        email = r['email']
        html_body = build_pro_yearly_promo_html(
            first_name=r['first_name'],
            unsub_url=_unsub_url(email),
            test_banner=False,
        )
        if dry_run:
            if i <= 3:
                print(f'   [DRY] {email} ({r["first_name"]}) part={part}')
            sent_n += 1
            continue

        assert sender is not None
        result = sender.send_email(
            to_email=email,
            subject=SUBJECT,
            html_body=html_body,
            from_name='Predictify',
            tags=[
                {'name': 'app', 'value': 'predictify'},
                {'name': 'kind', 'value': kind},
                {'name': 'part', 'value': str(part)},
                {'name': 'campaign', 'value': CAMPAIGN_ID},
            ],
            ref_id=f'{CAMPAIGN_ID}:{r["uid"]}',
        )
        if result == 'sent':
            sent_n += 1
            sent_map[email] = {
                'uid': r['uid'],
                'part': part,
                'sent_at': _utc_now(),
            }
            state.setdefault('failed', {}).pop(email, None)
        elif result in ('suppressed', 'duplicate', 'throttled', 'paused'):
            skipped_n += 1
        else:
            failed_n += 1
            state.setdefault('failed', {})[email] = {
                'part': part,
                'result': result,
                'at': _utc_now(),
            }

        if i % 25 == 0:
            _save_state(state)
            print(f'   … {i}/{len(cohort)} ({sent_n} sent, {failed_n} failed, {skipped_n} skipped)')

        if sleep > 0 and not dry_run:
            time.sleep(sleep)

    parts = state.setdefault('parts', {})
    pinfo = parts.setdefault(str(part), {'sent_count': 0, 'completed_at': None})
    pinfo['sent_count'] = pinfo.get('sent_count', 0) + sent_n
    if not dry_run and len(cohort) > 0 and failed_n == 0:
        pinfo['completed_at'] = _utc_now()
    elif not dry_run and len(cohort) > 0 and sent_n > 0 and failed_n > 0:
        print(f'   ⚠️ Part {part} incomplete — {failed_n} failures (will resume on next run)')
    _save_state(state)

    print(f'\nDone part {part}: sent={sent_n}, failed={failed_n}, skipped={skipped_n}')
    print(f'Subject: {SUBJECT}')
    print(f'Preview: {PREVIEW}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Predictify Soccer promo blast (free users, 4 parts)')
    parser.add_argument('--part', type=int, choices=[1, 2, 3, 4], help='Cohort part to send (1-4)')
    parser.add_argument('--auto-part', action='store_true', help='Send part based on days since campaign start')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0, help='Max sends this run (0 = all in part)')
    parser.add_argument('--sleep', type=float, default=float(os.getenv('PROMO_SEND_DELAY', '0.3')))
    parser.add_argument('--no-refresh-activity', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument(
        '--mark-part-complete',
        type=int,
        choices=[1, 2, 3, 4],
        help='Admin: mark a cohort finished without sending (recovery)',
    )
    args = parser.parse_args()

    state = _load_state()
    if args.mark_part_complete:
        part = args.mark_part_complete
        parts = state.setdefault('parts', {})
        parts.setdefault(str(part), {'sent_count': 0, 'completed_at': None})
        parts[str(part)]['completed_at'] = _utc_now()
        parts[str(part)]['note'] = 'Marked complete manually'
        _save_state(state)
        print(f'Marked part {part} complete.')
        return

    if args.status:
        try:
            recipients, _ = _load_recipients(refresh_activity=False)
        except SystemExit:
            recipients = None
        _print_status(state, recipients)
        return

    part = args.part
    if args.auto_part:
        part = _auto_part(state)
        print(f'Auto-selected part {part} (campaign day offset)')
    if not part:
        parser.error('Specify --part N or --auto-part')

    run(
        part=part,
        dry_run=args.dry_run,
        limit=args.limit,
        sleep=args.sleep,
        refresh_activity=not args.no_refresh_activity,
    )


if __name__ == '__main__':
    main()
