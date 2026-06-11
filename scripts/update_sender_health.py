#!/usr/bin/env python3
"""
Update cache/sender_health.json from real Resend webhook data.

Reads the Supabase view `sender_health_7d` (created by 20260426_email_events.sql)
and writes status (green/yellow/red/unknown) per sender domain into
cache/sender_health.json. The auto-scaler in app_retention_emailer.py reads
that file on every run to decide each sender's daily cap.

Thresholds match config/warming_config.json `auto_scaling`:
  green:   open_rate >= 15% AND bounce_rate < 2%   → 420/day per sender
  yellow:  open_rate 5-15%  OR bounce_rate 2-3%    → 150/day per sender
  red:     open_rate < 5%   OR bounce_rate > 3%    →  50/day per sender
  unknown: < MIN_VOLUME delivered events           → 100/day per sender (default)

Min volume guard: a sender needs at least MIN_VOLUME delivered events in the
window before we trust the rate calculation. Below that, leave as 'unknown'.

Run nightly via .github/workflows/sender-health-update.yml.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests


MIN_VOLUME = 200  # delivered events in the 7-day window before we trust the rate

THRESHOLDS = {
    'green': {'min_open_rate': 0.15, 'max_bounce_rate': 0.02},
    'yellow_max_bounce': 0.03,
    'yellow_min_open': 0.05,
}


def load_supabase_creds():
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if url and key:
        return url, key
    config_path = Path(__file__).parent.parent / 'config' / 'supabase_config.json'
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        return cfg['project']['url'], cfg['project']['service_role_key']
    raise SystemExit('SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set')


def fetch_health_rows():
    url, key = load_supabase_creds()
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

    # sender_health_7d is now a MATERIALIZED view (since 2026-06-11). The
    # CTE-based regular view used to time out PostgREST with a 500 once
    # email_events crossed ~90k rows in a 7-day window. The materialized
    # view is table-fast to query — we just need to refresh it first so
    # the data reflects the last cron run.
    refresh = requests.post(
        f'{url}/rest/v1/rpc/refresh_sender_health_7d',
        headers={**headers, 'Content-Type': 'application/json'},
        json={},
        timeout=60,
    )
    if not refresh.ok:
        print(f'   ⚠️  refresh_sender_health_7d failed ({refresh.status_code}): '
              f'{refresh.text[:200]} — querying stale data')

    resp = requests.get(
        f'{url}/rest/v1/sender_health_7d',
        params={'select': '*'},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def classify(delivered, opens, bounces, complaints):
    """Return (status, metrics_dict)."""
    metrics = {
        'delivered': delivered,
        'opens': opens,
        'bounces': bounces,
        'complaints': complaints,
        'open_rate': round(opens / delivered, 4) if delivered else 0,
        'bounce_rate': round(bounces / delivered, 4) if delivered else 0,
        'complaint_rate': round(complaints / delivered, 4) if delivered else 0,
    }

    if delivered < MIN_VOLUME:
        return 'unknown', metrics

    open_rate = metrics['open_rate']
    bounce_rate = metrics['bounce_rate']
    complaint_rate = metrics['complaint_rate']

    # Spam complaints over 0.1% = instant red regardless of opens
    if complaint_rate > 0.001:
        return 'red', metrics
    if (
        open_rate >= THRESHOLDS['green']['min_open_rate']
        and bounce_rate < THRESHOLDS['green']['max_bounce_rate']
    ):
        return 'green', metrics
    if open_rate < THRESHOLDS['yellow_min_open'] or bounce_rate > THRESHOLDS['yellow_max_bounce']:
        return 'red', metrics
    return 'yellow', metrics


def main():
    health_path = Path(__file__).parent.parent / 'cache' / 'sender_health.json'
    if not health_path.exists():
        raise SystemExit(f'Missing {health_path}')

    with open(health_path) as f:
        existing = json.load(f)

    rows = fetch_health_rows()
    by_domain = {row['sender_domain']: row for row in rows}

    senders = existing.get('senders', {})
    now = datetime.utcnow().isoformat() + 'Z'
    changes = []

    for sender_email, sender_state in senders.items():
        domain = sender_email.split('@', 1)[-1].lower()
        row = by_domain.get(domain)
        if not row:
            # No events at all in window — leave status untouched, just stamp check time
            sender_state['last_check'] = now
            continue

        status, metrics = classify(
            int(row.get('delivered', 0)),
            int(row.get('opens', 0)),
            int(row.get('bounces', 0)),
            int(row.get('complaints', 0)),
        )
        old_status = sender_state.get('status', 'unknown')
        sender_state['last_check'] = now
        sender_state['status'] = status

        history = sender_state.setdefault('metrics_history', [])
        history.append({'at': now, 'status': status, **metrics})
        if len(history) > 30:
            sender_state['metrics_history'] = history[-30:]

        if status != old_status:
            changes.append((sender_email, old_status, status, metrics))

    with open(health_path, 'w') as f:
        json.dump(existing, f, indent=2)

    print('Sender health update complete.')
    if not changes:
        print('  no status changes')
    for email, old, new, m in changes:
        print(f'  {email}: {old} → {new}  '
              f'(open_rate={m["open_rate"]:.1%} bounce_rate={m["bounce_rate"]:.1%} '
              f'delivered={m["delivered"]})')


if __name__ == '__main__':
    main()
