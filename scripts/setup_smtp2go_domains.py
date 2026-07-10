#!/usr/bin/env python3
"""
Register sender domains in SMTP2GO and print (or apply) DNS CNAME records.

SMTP2GO requires two CNAMEs per domain:
  - DKIM:   {dkim_selector}._domainkey.{domain} → dkim.smtp2go.net
  - Return: {rpath_selector}.{domain} → return.smtp2go.net

Optional link tracking CNAME (disabled by default):
  - link.{domain} → track.smtp2go.net

Usage:
  export SMTP2GO_API_KEY=api-...
  python scripts/setup_smtp2go_domains.py
  python scripts/setup_smtp2go_domains.py --verify
  python scripts/setup_smtp2go_domains.py --cloudflare academicsatire.com

DNS providers:
  CLOUDFLARE_API_TOKEN + zone lookup for academicsatire.com
  Other domains: prints records for manual / Hostinger setup
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

API_BASE = "https://api.smtp2go.com/v3"

SENDER_DOMAINS = [
    "breakuprelief.com",
    "kaynel.solutions",
    "passedai.io",
]

PENDING_DOMAINS = [
    "predictifyfootball.com",  # unverified DNS
    "predictify.fun",  # verified — enable in SMTP2GO dashboard
]


def api_key() -> str:
    key = os.getenv("SMTP2GO_API_KEY", "").strip()
    if not key:
        print("❌ Set SMTP2GO_API_KEY", file=sys.stderr)
        sys.exit(1)
    return key


def headers() -> dict:
    return {
        "X-Smtp2go-Api-Key": api_key(),
        "Content-Type": "application/json",
        "accept": "application/json",
    }


def smtp2go_post(path: str, payload: dict | None = None) -> dict:
    resp = requests.post(
        f"{API_BASE}{path}",
        headers=headers(),
        json=payload or {},
        timeout=30,
    )
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    if resp.status_code != 200:
        err = body.get("data", body)
        raise RuntimeError(f"SMTP2GO {path} failed ({resp.status_code}): {err}")
    return body


def list_domains() -> dict[str, dict]:
    try:
        data = smtp2go_post("/domain/view").get("data", {})
    except RuntimeError as e:
        if "ENDPOINT_PERMISSION_DENIED" in str(e):
            print("⚠️  API key cannot manage domains — enable 'Sender domains' permission")
            print("   in SMTP2GO → Sending → API Keys, or add domains in the dashboard.\n")
            return {}
        raise
    out: dict[str, dict] = {}
    for entry in data.get("domains", []):
        d = (entry or {}).get("domain", {})
        name = d.get("fulldomain")
        if name:
            out[name] = entry
    return out


def add_domain(domain: str) -> dict:
    return smtp2go_post("/domain/add", {"domain": domain})


def verify_domain(domain: str) -> dict:
    return smtp2go_post("/domain/verify", {"domain": domain, "requisition_ssl": False})


def dns_records(entry: dict) -> list[dict]:
    d = entry.get("domain", {})
    domain = d.get("fulldomain")
    if not domain:
        return []

    records = []
    selector = d.get("dkim_selector")
    rpath = d.get("rpath_selector")
    if selector and d.get("dkim_value"):
        records.append({
            "type": "CNAME",
            "name": f"{selector}._domainkey",
            "host": f"{selector}._domainkey.{domain}",
            "value": d["dkim_value"],
            "purpose": "DKIM",
        })
    if rpath and d.get("rpath_value"):
        records.append({
            "type": "CNAME",
            "name": rpath,
            "host": f"{rpath}.{domain}",
            "value": d["rpath_value"],
            "purpose": "Return-Path",
        })
    return records


def cloudflare_zone_id(domain: str, token: str) -> str | None:
    resp = requests.get(
        "https://api.cloudflare.com/client/v4/zones",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params={"name": domain},
        timeout=20,
    )
    if resp.status_code != 200:
        return None
    zones = resp.json().get("result", [])
    return zones[0]["id"] if zones else None


def cloudflare_upsert_cname(zone_id: str, token: str, name: str, target: str) -> bool:
    # name is FQDN like s123._domainkey.example.com
    headers_cf = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    list_resp = requests.get(
        f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
        headers=headers_cf,
        params={"type": "CNAME", "name": name},
        timeout=20,
    )
    existing = list_resp.json().get("result", []) if list_resp.status_code == 200 else []
    payload = {"type": "CNAME", "name": name, "content": target, "ttl": 1, "proxied": False}
    if existing:
        rec_id = existing[0]["id"]
        resp = requests.put(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{rec_id}",
            headers=headers_cf,
            json=payload,
            timeout=20,
        )
    else:
        resp = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
            headers=headers_cf,
            json=payload,
            timeout=20,
        )
    ok = resp.status_code == 200 and resp.json().get("success")
    if not ok:
        print(f"   ⚠️  Cloudflare CNAME failed for {name}: {resp.text[:200]}")
    return ok


def apply_cloudflare(domain: str, records: list[dict]) -> int:
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        print(f"   ℹ️  CLOUDFLARE_API_TOKEN not set — skip auto-DNS for {domain}")
        return 0
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID", "").strip() or cloudflare_zone_id(domain, token)
    if not zone_id:
        print(f"   ⚠️  No Cloudflare zone for {domain}")
        return 0
    applied = 0
    for rec in records:
        if cloudflare_upsert_cname(zone_id, token, rec["host"], rec["value"]):
            print(f"   ✅ Cloudflare: {rec['host']} → {rec['value']}")
            applied += 1
    return applied


def main():
    parser = argparse.ArgumentParser(description="Register SMTP2GO sender domains")
    parser.add_argument("--verify", action="store_true", help="Trigger DNS verification after setup")
    parser.add_argument("--cloudflare", metavar="DOMAIN", help="Apply DNS via Cloudflare for one domain")
    parser.add_argument("domains", nargs="*", help="Domains to add (default: all 7)")
    args = parser.parse_args()

    targets = args.domains or SENDER_DOMAINS
    try:
        existing = list_domains()
    except RuntimeError:
        existing = {}

    print(f"📬 SMTP2GO domain setup ({len(targets)} domains)\n")

    if not existing:
        print("Add these sender domains in SMTP2GO → Sending → Verified Senders:")
        for d in targets:
            print(f"  • {d}")
        print("\nEach domain needs two CNAME records (DKIM + Return-Path) from the dashboard.")
        print("Re-run with domain API permission enabled for automated setup.\n")
        return

    for domain in targets:
        print(f"── {domain} ──")
        if domain in existing:
            print("   Already registered")
            entry = existing[domain]
        else:
            try:
                result = add_domain(domain)
                entry = (result.get("data", {}).get("domains") or [{}])[0]
                print("   ✅ Added to SMTP2GO")
            except RuntimeError as e:
                print(f"   ❌ {e}")
                continue

        records = dns_records(entry)
        if not records:
            # refresh view for full record set
            try:
                refreshed = smtp2go_post("/domain/view", {"domain": domain})
                domains = refreshed.get("data", {}).get("domains", [])
                if domains:
                    records = dns_records(domains[0])
            except RuntimeError:
                pass

        for rec in records:
            print(f"   DNS {rec['purpose']}: {rec['host']} CNAME {rec['value']}")

        if args.cloudflare and domain == args.cloudflare:
            apply_cloudflare(domain, records)
        elif domain == "academicsatire.com" and os.getenv("CLOUDFLARE_API_TOKEN"):
            apply_cloudflare(domain, records)

        if args.verify:
            try:
                verify_domain(domain)
                print("   🔄 Verification triggered")
            except RuntimeError as e:
                print(f"   ⚠️  Verify: {e}")
        print()

    if args.verify:
        print("Waiting 15s for DNS checks…")
        time.sleep(15)
        verified = list_domains()
        print("\n📊 Verification status:")
        for domain in targets:
            entry = verified.get(domain, {})
            d = entry.get("domain", {})
            dkim = d.get("dkim_verified")
            rpath = d.get("rpath_verified")
            mark = "✅" if dkim and rpath else "⏳"
            print(f"   {mark} {domain}: DKIM={dkim} Return-Path={rpath}")


if __name__ == "__main__":
    main()
