#!/usr/bin/env python3
"""
Update cache/sender_health.json from email_events (Supabase).

Reads the materialized view `sender_health_7d` and writes status
(green/yellow/red/unknown) per sender domain into cache/sender_health.json.

Thresholds match config/warming_config.json `auto_scaling`:
  green:   open_rate >= 15% AND bounce_rate < 2%
  yellow:  open_rate 5-15%  OR bounce_rate 2-3%
  red:     open_rate < 5%   OR bounce_rate > 3%  OR complaint_rate > 0.1%
  unknown: < MIN_VOLUME delivered events

Intermittent Supabase refresh/query timeouts used to fail the nightly job.
We retry with backoff and, if the view is still unreachable, exit 0 so
retention keeps using the last known health instead of red-failing CI.

Run nightly via .github/workflows/sender-health-update.yml.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests


MIN_VOLUME = 200  # delivered events in the 7-day window before we trust the rate
REFRESH_TIMEOUT = 120
QUERY_TIMEOUT = 60
MAX_ATTEMPTS = 3

THRESHOLDS = {
    'green': {'min_open_rate': 0.15, 'max_bounce_rate': 0.02},
    'yellow_max_bounce': 0.03,
    'yellow_min_open': 0.05,
}

# Ensure Zepto / active From domains are tracked even if never warmed via pool.
ENSURE_SENDERS = (
    'hello@breakuprelief.com',
    'selka@breakuprelief.com',
    'hello@passedai.io',
    'hello@kaynel.solutions',
    'hello@thesisgenerator.io',
    'tips@predictifyfootball.com',
)


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


def _request_with_retries(method: str, url: str, *, headers: dict, **kwargs):
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.request(method, url, headers=headers, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f'HTTP {resp.status_code}: {resp.text[:200]}'
                wait = 5 * attempt
                print(f'   ⚠️  {method} {url.split("/rest/")[-1]} attempt {attempt}/{MAX_ATTEMPTS} '
                      f'→ {last_err} — retry in {wait}s')
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            last_err = str(e)
            wait = 5 * attempt
            print(f'   ⚠️  {method} attempt {attempt}/{MAX_ATTEMPTS} error: {e} — retry in {wait}s')
            time.sleep(wait)
    raise RuntimeError(last_err or 'request failed')


def fetch_health_rows():
    url, key = load_supabase_creds()
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

    # Materialized view: refresh first, then query. Refresh may time out under
    # load — we still try the query (possibly stale) so the job completes.
    refresh = _request_with_retries(
        'POST',
        f'{url}/rest/v1/rpc/refresh_sender_health_7d',
        headers={**headers, 'Content-Type': 'application/json'},
        json={},
        timeout=REFRESH_TIMEOUT,
    )
    if not refresh.ok:
        print(f'   ⚠️  refresh_sender_health_7d failed ({refresh.status_code}): '
              f'{refresh.text[:200]} — querying possibly stale data')

    resp = _request_with_retries(
        'GET',
        f'{url}/rest/v1/sender_health_7d',
        headers=headers,
        params={'select': '*'},
        timeout=QUERY_TIMEOUT,
    )
    if not resp.ok:
        raise RuntimeError(
            f'sender_health_7d query failed ({resp.status_code}): {resp.text[:300]}'
        )
    rows = resp.json()
    if not isinstance(rows, list):
        raise RuntimeError(f'unexpected sender_health_7d payload: {type(rows)}')
    return rows


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


def ensure_tracked_senders(senders: dict) -> None:
    for email in ENSURE_SENDERS:
        if email not in senders:
            senders[email] = {'status': 'unknown', 'metrics_history': []}
            print(f'   ➕ tracking new sender {email}')


def main():
    health_path = Path(__file__).parent.parent / 'cache' / 'sender_health.json'
    if not health_path.exists():
        raise SystemExit(f'Missing {health_path}')

    with open(health_path) as f:
        existing = json.load(f)

    senders = existing.setdefault('senders', {})
    ensure_tracked_senders(senders)

    try:
        rows = fetch_health_rows()
    except Exception as e:
        # Soft-fail: keep last known health so retention/CI stay green.
        print(f'❌ Could not refresh sender health: {e}')
        print('   Leaving cache/sender_health.json unchanged (soft fail).')
        return 0

    by_domain = {}
    for row in rows:
        domain = (row.get('sender_domain') or '').lower().strip()
        if domain:
            by_domain[domain] = row

    now = datetime.utcnow().isoformat() + 'Z'
    changes = []

    for sender_email, sender_state in senders.items():
        if not isinstance(sender_state, dict):
            continue
        domain = sender_email.split('@', 1)[-1].lower()
        row = by_domain.get(domain)
        if not row:
            sender_state['last_check'] = now
            continue

        status, metrics = classify(
            int(row.get('delivered', 0) or 0),
            int(row.get('opens', 0) or 0),
            int(row.get('bounces', 0) or 0),
            int(row.get('complaints', 0) or 0),
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
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
