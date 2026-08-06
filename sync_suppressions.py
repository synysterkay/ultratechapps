#!/usr/bin/env python3
"""Sync provider bounce/complaint events into email_suppressions.

Reads email_events (Resend webhooks, ZeptoMail webhooks, welcome-path
bounce records) and upserts durable suppressions so every sender skips
known bad addresses before the next attempt.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


EVENT_REASON = {
    "email.bounced": "bounce",
    "email.complained": "complaint",
}


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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="How far back to scan email_events. Default: 30.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50000,
        help="Maximum event rows to fetch. Default: 50000.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing.",
    )
    return parser.parse_args()


def fetch_bad_events(url: str, key: str, *, days: int, limit: int) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows: list[dict] = []
    page_size = min(500, limit)
    max_attempts = 3

    while len(rows) < limit:
        start = len(rows)
        end = min(start + page_size - 1, limit - 1)
        page = None
        for attempt in range(max_attempts):
            resp = requests.get(
                f"{url}/rest/v1/email_events",
                headers={**headers, "Range": f"{start}-{end}"},
                params={
                    "select": "recipient,app,event_type,occurred_at",
                    "event_type": "in.(email.bounced,email.complained)",
                    "recipient": "not.is.null",
                    "app": "not.is.null",
                    "occurred_at": f"gte.{since}",
                    "order": "occurred_at.desc",
                },
                timeout=45,
            )
            if resp.status_code < 400:
                page = resp.json()
                break
            body = resp.text[:500]
            is_timeout = resp.status_code == 500 and "57014" in body
            if is_timeout and attempt < max_attempts - 1:
                wait = 2 ** attempt
                print(f"   ⏳ email_events query timeout — retry in {wait}s")
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"email_events query failed: {resp.status_code} {body}"
            )
        if page is None:
            break
        rows.extend(page)
        if len(page) < page_size:
            break

    return rows


def build_suppressions(events: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], str] = {}

    def remember(recipient: str, app: str, reason: str) -> None:
        key = (recipient, app)
        # A complaint is stronger than a bounce if both exist for the same key.
        if by_key.get(key) != "complaint":
            by_key[key] = reason

    for event in events:
        recipient = (event.get("recipient") or "").lower().strip()
        app = (event.get("app") or "").strip()
        event_type = event.get("event_type")
        if not recipient or not app or event_type not in EVENT_REASON:
            continue

        reason = EVENT_REASON[event_type]
        remember(recipient, app, reason)
        # Hard bounces and complaints are recipient-level deliverability
        # signals. Keep the app-specific row for analytics, and add a global
        # row so every campaign skips that address before hitting Resend.
        remember(recipient, "*", reason)

    return [
        {"recipient": recipient, "app": app, "reason": reason}
        for (recipient, app), reason in sorted(by_key.items())
    ]


def insert_suppressions(url: str, key: str, rows: list[dict]) -> int:
    if not rows:
        return 0

    inserted = 0
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Do not overwrite explicit unsubscribe/manual rows already present.
        "Prefer": "return=minimal,resolution=ignore-duplicates",
    }
    for start in range(0, len(rows), 1000):
        batch = rows[start : start + 1000]
        resp = requests.post(
            f"{url}/rest/v1/email_suppressions",
            headers=headers,
            params={"on_conflict": "recipient,app"},
            json=batch,
            timeout=45,
        )
        if resp.status_code not in (200, 201, 204):
            raise RuntimeError(
                f"email_suppressions insert failed: {resp.status_code} {resp.text[:500]}"
            )
        inserted += len(batch)
    return inserted


def main():
    args = parse_args()
    url, key = supabase_creds()
    events = fetch_bad_events(url, key, days=args.days, limit=args.limit)
    rows = build_suppressions(events)

    by_app = Counter(row["app"] for row in rows)
    by_reason = Counter(row["reason"] for row in rows)
    print(f"Fetched bad events: {len(events):,}")
    print(f"Unique suppressions to upsert: {len(rows):,}")
    print("By app:")
    for app, total in by_app.most_common():
        print(f"  {app}: {total:,}")
    print("By reason:")
    for reason, total in by_reason.most_common():
        print(f"  {reason}: {total:,}")

    if args.dry_run:
        print("Dry run: no rows written.")
        return

    attempted = insert_suppressions(url, key, rows)
    print(f"Upsert attempted for {attempted:,} rows.")
    print("Existing duplicates were ignored by PostgREST.")


if __name__ == "__main__":
    main()
