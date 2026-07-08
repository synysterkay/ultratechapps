#!/usr/bin/env python3
"""Add Mailgun DNS records for passedai.io via Hostinger API."""
from __future__ import annotations

import json
import os
import re
import sys

import requests

DOMAIN = "passedai.io"
API_BASE = "https://developers.hostinger.com/api/dns/v1/zones"

MAILGUN_DKIM = (
    "k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCpwamABdUC6N2MTuBPyam98InNxI9aLcVbMLndJW9HCY2hLiGM+u2xMcmqhEE3F93FCeTdpBIQO0METrjImPupx1+cK8gOowzeu6hhcSOJh6NYLP+pSaB5rNARkxVVl9fAY8tgs1pIXg8P0js4RaXlAx0GphgcQezTFDXClsHYgwIDAQAB"
)
MAILGUN_DMARC = (
    "v=DMARC1; p=none; pct=100; fo=1; ri=3600; "
    "rua=mailto:f3aa1034@dmarc.mailgun.org,mailto:xtmzjr4zbv5@inbox.ondmarc.com; "
    "ruf=mailto:f3aa1034@dmarc.mailgun.org,mailto:xtmzjr4zbv5@inbox.ondmarc.com;"
)


def hostinger_tokens() -> list[str]:
    tokens = []
    for key in ("HOSTINGER_API_TOKEN", "HOSTINGER_API_TOKEN_1", "HOSTINGER_API_TOKEN_2"):
        val = os.getenv(key, "").strip()
        if val and val not in tokens:
            tokens.append(val)
    return tokens


def txt_content(value: str) -> str:
    v = value.strip().strip('"')
    return f'"{v}"'


def record_content(rec: dict) -> str:
    parts = rec.get("records") or []
    if not parts:
        return ""
    return str(parts[0].get("content", "")).strip('"')


def merge_spf(existing: str, extra_include: str) -> str:
    existing = existing.strip().strip('"')
    if extra_include in existing:
        return existing
    if existing.startswith("v=spf1"):
        body = existing[6:].strip()
        body = re.sub(r"\s*[~\-?]all\s*$", "", body).strip()
        return f"v=spf1 {body} {extra_include} ~all".replace("  ", " ")
    return f"v=spf1 {extra_include} ~all"


def upsert_txt(zone: list[dict], name: str, value: str, ttl: int = 3600) -> None:
    content = txt_content(value)
    for rec in zone:
        if rec.get("type") == "TXT" and rec.get("name") == name:
            rec["ttl"] = ttl
            rec["records"] = [{"content": content, "is_disabled": False}]
            return
    zone.append({
        "type": "TXT",
        "name": name,
        "ttl": ttl,
        "records": [{"content": content, "is_disabled": False}],
    })


def upsert_cname(zone: list[dict], name: str, target: str, ttl: int = 3600) -> None:
    target = target if target.endswith(".") else f"{target}."
    for rec in zone:
        if rec.get("type") == "CNAME" and rec.get("name") == name:
            rec["ttl"] = ttl
            rec["records"] = [{"content": target, "is_disabled": False}]
            return
    zone.append({
        "type": "CNAME",
        "name": name,
        "ttl": ttl,
        "records": [{"content": target, "is_disabled": False}],
    })


def upsert_mx(zone: list[dict], name: str, hosts: list[tuple[int, str]], ttl: int = 14400) -> None:
    records = []
    for prio, host in hosts:
        host = host if host.endswith(".") else f"{host}."
        records.append({"content": f"{prio} {host}", "is_disabled": False})
    for rec in zone:
        if rec.get("type") == "MX" and rec.get("name") == name:
            rec["ttl"] = ttl
            rec["records"] = records
            return
    zone.append({"type": "MX", "name": name, "ttl": ttl, "records": records})


def apply_mailgun(zone: list[dict]) -> None:
    spf_existing = ""
    for rec in zone:
        if rec.get("type") == "TXT" and rec.get("name") == "@" and record_content(rec).startswith("v=spf1"):
            spf_existing = record_content(rec)
            break

    upsert_txt(zone, "@", merge_spf(spf_existing, "include:mailgun.org"))
    upsert_txt(zone, "mx._domainkey", MAILGUN_DKIM, ttl=14400)
    upsert_txt(zone, "_dmarc", MAILGUN_DMARC)
    upsert_cname(zone, "email", "mailgun.org")
    upsert_mx(zone, "@", [(10, "mxa.mailgun.org"), (10, "mxb.mailgun.org")])


def find_zone_token(tokens: list[str]) -> tuple[str, list[dict]]:
    headers = {"Accept": "application/json"}
    for token in tokens:
        r = requests.get(f"{API_BASE}/{DOMAIN}", headers={**headers, "Authorization": f"Bearer {token}"}, timeout=30)
        if r.status_code == 200:
            return token, r.json()
    raise RuntimeError(f"{DOMAIN} not found on any Hostinger account")


def put_zone(token: str, zone: list[dict]) -> requests.Response:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    for payload in (zone, {"zone": zone}):
        r = requests.put(f"{API_BASE}/{DOMAIN}", headers=headers, json=payload, timeout=60)
        if r.status_code < 400:
            return r
    return r


def main() -> int:
    tokens = hostinger_tokens()
    if not tokens:
        print("Set HOSTINGER_API_TOKEN or HOSTINGER_API_TOKEN_1/_2", file=sys.stderr)
        return 1

    token, zone = find_zone_token(tokens)
    print(f"Found {DOMAIN} — {len(zone)} existing records")
    apply_mailgun(zone)

    put = put_zone(token, zone)
    print("PUT status:", put.status_code)
    if put.status_code >= 400:
        print(put.text[:2000])
        return 1

    print("✅ Mailgun DNS applied for", DOMAIN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
