#!/usr/bin/env python3
"""Quick operational status for the Resend/Supabase email system."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


DEFAULT_APPS = [
    "predictify",
    "thesis_generator",
    "redflag_scanner",
    "fresh_start",
    "soulplan",
    "pupshape",
    "volume_booster",
    "horse_racing",
]

EVENT_TYPES = [
    "email.sent",
    "email.delivered",
    "email.opened",
    "email.clicked",
    "email.bounced",
    "email.complained",
    "email.delivery_delayed",
]


def supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if url and key:
        return url, key

    cfg_path = Path(__file__).resolve().parent / "config" / "supabase_config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        project = cfg.get("project", {})
        url = project.get("url", "").rstrip("/")
        key = project.get("service_role_key", "")
    if not url or not key:
        raise SystemExit(
            "Missing Supabase credentials. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY or config/supabase_config.json."
        )
    return url, key


SUPABASE_URL, SERVICE_KEY = supabase_creds()
HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


def get_json(path: str, params: dict | None = None, *, timeout: int = 20):
    resp = requests.get(
        f"{SUPABASE_URL}{path}",
        headers=HEADERS,
        params=params or {},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"{path} failed: {resp.status_code} {resp.text[:300]}")
    return resp.json()


def get_all_json(
    path: str,
    params: dict | None = None,
    *,
    page_size: int = 1000,
    max_rows: int = 50000,
    timeout: int = 20,
):
    rows = []
    while len(rows) < max_rows:
        start = len(rows)
        end = min(start + page_size - 1, max_rows - 1)
        resp = requests.get(
            f"{SUPABASE_URL}{path}",
            headers={**HEADERS, "Range": f"{start}-{end}"},
            params=params or {},
            timeout=timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"{path} failed: {resp.status_code} {resp.text[:300]}")
        page = resp.json()
        rows.extend(page)
        if len(page) < page_size:
            break
    return rows


def count_rows(path: str, params: dict | None = None, *, timeout: int = 20) -> int:
    headers = {**HEADERS, "Prefer": "count=exact"}
    resp = requests.get(
        f"{SUPABASE_URL}{path}",
        headers=headers,
        params={**(params or {}), "select": "id", "limit": "1"},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"{path} count failed: {resp.status_code} {resp.text[:300]}")
    content_range = resp.headers.get("content-range", "")
    if "/" not in content_range:
        return 0
    total = content_range.rsplit("/", 1)[-1]
    return 0 if total == "*" else int(total)


def count_welcomed(app: str) -> int:
    headers = {**HEADERS, "Prefer": "count=exact"}
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/welcomed_users",
        headers=headers,
        params={"app_id": f"eq.{app}", "select": "email", "limit": "1"},
        timeout=20,
    )
    resp.raise_for_status()
    content_range = resp.headers.get("content-range", "")
    total = content_range.rsplit("/", 1)[-1] if "/" in content_range else "0"
    return 0 if total == "*" else int(total)


def print_welcomed_stats():
    print("=== WELCOMED STATS ===")
    for app in DEFAULT_APPS:
        rows = get_json(
            "/rest/v1/welcomed_users",
            {
                "app_id": f"eq.{app}",
                "select": "email,welcomed_at",
                "order": "welcomed_at.desc",
                "limit": "1",
            },
        )
        last = rows[0]["welcomed_at"] if rows else "N/A"
        print(f"  {app}: count={count_welcomed(app):,}, last_welcomed={last}")

    print()
    print("=== MOST RECENT WELCOMED ===")
    rows = get_json(
        "/rest/v1/welcomed_users",
        {
            "select": "email,app_id,welcomed_at,language",
            "order": "welcomed_at.desc",
            "limit": "8",
        },
    )
    for row in rows:
        print(
            f"  {row['email']} | app={row['app_id']} | "
            f"at={row['welcomed_at']} | lang={row['language']}"
        )


def print_event_counts():
    print()
    print("=== RESEND WEBHOOK EVENTS ===")
    now = datetime.now(timezone.utc)
    for label, since in [
        ("24h", now - timedelta(hours=24)),
        ("7d", now - timedelta(days=7)),
    ]:
        print(f"  {label}:")
        for event_type in EVENT_TYPES:
            total = count_rows(
                "/rest/v1/email_events",
                {
                    "occurred_at": f"gte.{since.isoformat()}",
                    "event_type": f"eq.{event_type}",
                },
            )
            print(f"    {event_type}: {total:,}")

    print()
    print("=== LATEST RESEND EVENTS ===")
    rows = get_json(
        "/rest/v1/email_events",
        {
            "select": "event_type,app,kind,sender_domain,occurred_at",
            "order": "occurred_at.desc",
            "limit": "10",
        },
    )
    for row in rows:
        print(
            f"  {row['occurred_at']} | {row['event_type']} | "
            f"app={row.get('app') or '-'} | kind={row.get('kind') or '-'} | "
            f"domain={row.get('sender_domain') or '-'}"
        )


def print_sender_health():
    print()
    print("=== SENDER HEALTH 7D ===")
    try:
        rows = get_json(
            "/rest/v1/sender_health_7d",
            {"select": "*", "order": "delivered.desc"},
        )
    except RuntimeError as exc:
        print(f"  unavailable: {exc}")
        return

    for row in rows:
        delivered = row.get("delivered") or 0
        opens = row.get("opens") or 0
        bounces = row.get("bounces") or 0
        complaints = row.get("complaints") or 0
        open_rate = (opens / delivered * 100) if delivered else 0
        bounce_rate = (bounces / delivered * 100) if delivered else 0
        complaint_rate = (complaints / delivered * 100) if delivered else 0
        print(
            f"  {row['sender_domain']}: delivered={delivered:,}, "
            f"opens={opens:,} ({open_rate:.2f}%), "
            f"bounces={bounces:,} ({bounce_rate:.2f}%), "
            f"complaints={complaints:,} ({complaint_rate:.3f}%)"
        )


def print_suppressions():
    print()
    print("=== EMAIL SUPPRESSIONS ===")
    try:
        rows = get_all_json(
            "/rest/v1/email_suppressions",
            {"select": "recipient,app,reason", "order": "created_at.desc"},
            timeout=30,
        )
    except RuntimeError as exc:
        print(f"  unavailable: {exc}")
        return

    print(f"  total rows fetched: {len(rows):,}")
    by_app = Counter(row.get("app") or "-" for row in rows)
    by_reason = Counter(row.get("reason") or "-" for row in rows)
    print("  by app:")
    for app, total in by_app.most_common():
        print(f"    {app}: {total:,}")
    print("  by reason:")
    for reason, total in by_reason.most_common():
        print(f"    {reason}: {total:,}")


def try_check_new_users():
    print()
    print("=== CHECK-NEW-USERS FUNCTION ===")
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/functions/v1/check-new-users",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"maxPerProject": 5},
            timeout=30,
        )
        print(f"  status: {resp.status_code}")
        print(f"  response: {resp.text[:700]}")
    except Exception as exc:
        print(f"  error: {exc}")


def main():
    print_welcomed_stats()
    print_event_counts()
    print_sender_health()
    print_suppressions()
    try_check_new_users()


if __name__ == "__main__":
    main()
