#!/usr/bin/env python3
"""Sync ZeptoMail hard bounces into email_events + email_suppressions.

Uses the same durable suppression table as sync_suppressions.py / Resend
webhooks. Run after enabling ZeptoMail or to backfill bounces before the
webhook is configured.

Usage:
  export ZEPTOMAIL_API_KEY=...
  python scripts/sync_zeptomail_bounces.py --days 7
  python scripts/sync_zeptomail_bounces.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sync_suppressions import insert_suppressions, supabase_creds  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Sync ZeptoMail hard bounces")
    parser.add_argument("--days", type=int, default=7, help="Lookback window")
    parser.add_argument("--limit", type=int, default=500, help="Max logs to scan")
    parser.add_argument("--app", default="thesis_generator", help="App slug for suppressions")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y, %I:%M %p")


def fetch_hard_bounce_logs(api_key: str, api_base: str, *, days: int, limit: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    params = {
        "date_from": fmt_date(since),
        "date_to": fmt_date(now),
        "limit": min(limit, 200),
        "offset": 0,
    }
    headers = {
        "Authorization": f"Zoho-enczapikey {api_key}",
        "Accept": "application/json",
    }

    logs: list[dict] = []
    while len(logs) < limit:
        resp = requests.get(
            f"{api_base.rstrip('/')}/email",
            headers=headers,
            params=params,
            timeout=30,
        )
        if resp.status_code == 401:
            raise RuntimeError(
                "ZeptoMail logs API requires OAuth (send-mail token cannot read logs). "
                "Configure the zeptomail-webhook function for automatic hard-bounce suppression, "
                "or export hard bounces from the ZeptoMail dashboard and add them manually."
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"ZeptoMail logs API failed ({resp.status_code}): {resp.text[:400]}")

        body = resp.json()
        page = (body.get("data") or {}).get("logs") or []
        for entry in page:
            delivery = entry.get("email_delivery_details") or {}
            hard = delivery.get("hardbounce") or delivery.get("hard_bounce") or []
            if not hard and delivery.get("hard_bounced"):
                hard = delivery.get("hard_bounced")
            if isinstance(hard, dict):
                hard = [hard]
            if hard:
                logs.append(entry)
                if len(logs) >= limit:
                    break

        if len(page) < params["limit"]:
            break
        params["offset"] += params["limit"]

    return logs


def extract_recipients(entry: dict) -> list[str]:
    recipients: list[str] = []
    delivery = entry.get("email_delivery_details") or {}
    hard = delivery.get("hardbounce") or delivery.get("hard_bounce") or []
    if isinstance(hard, dict):
        hard = [hard]
    for item in hard:
        if not isinstance(item, dict):
            continue
        addr = (item.get("email") or item.get("address") or item.get("recipient") or "").lower().strip()
        if addr and "@" in addr:
            recipients.append(addr)

    if recipients:
        return recipients

    info = entry.get("email_info") or {}
    for item in info.get("to") or []:
        if isinstance(item, dict):
            addr = (item.get("address") or "").lower().strip()
            if addr and "@" in addr:
                recipients.append(addr)
    return recipients


def main():
    args = parse_args()
    api_key = os.getenv("ZEPTOMAIL_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set ZEPTOMAIL_API_KEY")

    api_base = os.getenv("ZEPTOMAIL_API_URL", "https://api.zeptomail.eu/v1.1").rstrip("/email")
    if api_base.endswith("/email"):
        api_base = api_base[:-6]

    url, key = supabase_creds()
    logs = fetch_hard_bounce_logs(api_key, api_base, days=args.days, limit=args.limit)

    suppressions = []
    events = []
    seen = set()

    for entry in logs:
        info = entry.get("email_info") or {}
        request_id = entry.get("request_id") or info.get("email_reference") or ""
        occurred_at = info.get("processed_time") or datetime.now(timezone.utc).isoformat()
        sender = ((info.get("from") or {}).get("address") or "")
        sender_domain = sender.split("@")[1].lower() if "@" in sender else None
        client_ref = info.get("client_reference") or ""

        for recipient in extract_recipients(entry):
            dedupe = (recipient, args.app)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            suppressions.extend([
                {"recipient": recipient, "app": args.app, "reason": "bounce"},
                {"recipient": recipient, "app": "*", "reason": "bounce"},
            ])
            events.append({
                "svix_id": f"zm-sync-{request_id}-{recipient}",
                "message_id": request_id or None,
                "event_type": "email.bounced",
                "occurred_at": occurred_at,
                "recipient": recipient,
                "sender_domain": sender_domain,
                "app": args.app,
                "kind": "welcome",
                "email_num": "1",
                "cycle": "1",
                "ref_id": client_ref or None,
                "raw": entry,
            })

    print(f"Hard-bounce log entries scanned: {len(logs):,}")
    print(f"Unique bounced recipients: {len(seen):,}")
    for recipient in sorted(seen):
        print(f"  - {recipient[0]}")

    if args.dry_run:
        print("Dry run — no rows written.")
        return

    if suppressions:
        insert_suppressions(url, key, suppressions)

    if events:
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        }
        for start in range(0, len(events), 200):
            batch = events[start:start + 200]
            resp = requests.post(
                f"{url}/rest/v1/email_events",
                headers=headers,
                params={"on_conflict": "svix_id"},
                json=batch,
                timeout=45,
            )
            if resp.status_code not in (200, 201, 204):
                print(f"⚠️ email_events insert warning: {resp.status_code} {resp.text[:200]}")

    print(f"Upserted {len(suppressions):,} suppression rows.")


if __name__ == "__main__":
    main()
