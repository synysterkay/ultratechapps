#!/usr/bin/env python3
"""
Shared dedup helper for batch senders that have an instant counterpart.

When the Flutter app calls a Supabase Edge Function (thesis-complete-email,
free-quota-hit-email, etc.), that function inserts a row into
public.instant_emails_sent keyed by (uid, event_kind). Batch senders that
cover the same event call fetch_handled_uids() once at the start of their
run to filter out users who've already received the instant email.

This keeps deployment safe during the rollout window:
  * Old-app-version users → only the batch sender fires (as today)
  * New-app-version users → instant Edge Function fires; batch sender skips
  * Webhook retries / race conditions → unique constraint on the table
    rejects the second insert; only one email goes out
"""
import os
import json
from pathlib import Path
from typing import Set

import requests


def _supabase_creds() -> tuple[str, str]:
    """Return (url, service_role_key). Falls back to config file for
    local dev so a missing env var doesn't crash a dry-run."""
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if url and key:
        return url, key
    cfg = Path(__file__).resolve().parents[1] / 'config' / 'supabase_config.json'
    if cfg.exists():
        with open(cfg) as f:
            data = json.load(f)
        return data['project']['url'].rstrip('/'), data['project']['service_role_key']
    return '', ''


def fetch_handled_uids(event_kind: str) -> Set[str]:
    """Return the set of UIDs that have already received an instant
    email of the given event_kind. Safe to call with no Supabase creds —
    returns an empty set so the caller falls through to its existing
    state-file dedup as a backup."""
    url, key = _supabase_creds()
    if not url or not key:
        return set()
    try:
        headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
        uids: Set[str] = set()
        offset = 0
        page_size = 1000
        while True:
            resp = requests.get(
                f'{url}/rest/v1/instant_emails_sent',
                params={'select': 'uid', 'event_kind': f'eq.{event_kind}',
                        'offset': offset, 'limit': page_size},
                headers=headers, timeout=15,
            )
            if resp.status_code != 200:
                # 401/403/404 → table missing / not authorized — degrade gracefully
                return uids
            rows = resp.json()
            for r in rows:
                if r.get('uid'):
                    uids.add(r['uid'])
            if len(rows) < page_size:
                break
            offset += page_size
        return uids
    except Exception:
        # Network blip, JSON parse error, etc. — fall through to caller's
        # local state-file dedup so we never block on this query.
        return set()


def record_sent(event_kind: str, *, uid: str, app_id: str, recipient: str,
                language: str = 'en', resend_id: str | None = None,
                metadata: dict | None = None) -> bool:
    """Record a send by the BATCH path into the same dedup table the
    instant Edge Functions write to. Ensures the inverse direction also
    works: if the batch sender ships first, the instant function later
    sees the record and returns duplicate=true.

    Returns True on insert success, False on failure (network, dup,
    missing creds) — callers should never treat failure as fatal.
    """
    url, key = _supabase_creds()
    if not url or not key:
        return False
    try:
        resp = requests.post(
            f'{url}/rest/v1/instant_emails_sent',
            params={'on_conflict': 'uid,event_kind'},
            headers={
                'apikey': key,
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json',
                'Prefer': 'resolution=ignore-duplicates',
            },
            json={
                'uid': uid, 'app_id': app_id, 'event_kind': event_kind,
                'recipient': recipient.lower().strip(), 'language': language,
                'resend_id': resend_id, 'metadata': metadata or {},
            },
            timeout=10,
        )
        return resp.status_code in (200, 201, 409)
    except Exception:
        return False
