#!/usr/bin/env python3
"""Enable receiving (inbound) on all Resend domains and show required MX records."""

import os
import requests

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_62t3PuEy_23Q3uAQP6SMeYPRLgGVRraAr")
BASE_URL = "https://api.resend.com"
HEADERS = {
    "Authorization": f"Bearer {RESEND_API_KEY}",
    "Content-Type": "application/json",
}

DOMAINS = [
    "kaynel.pl",
    "aibettips.io",
    "predictifyfootball.com",
    "thesisgenerator.io",
    "passedai.io",
    "academicsatire.com",
]


def list_domains():
    """Get all domains from Resend."""
    resp = requests.get(f"{BASE_URL}/domains", headers=HEADERS)
    resp.raise_for_status()
    return resp.json().get("data", [])


def enable_receiving(domain_id, domain_name):
    """Enable receiving capability on a domain."""
    resp = requests.patch(
        f"{BASE_URL}/domains/{domain_id}",
        headers=HEADERS,
        json={"capabilities": {"receiving": "enabled"}},
    )
    if resp.status_code == 200:
        print(f"  ✅ Receiving enabled for {domain_name}")
    else:
        print(f"  ❌ Failed for {domain_name}: {resp.status_code} {resp.text}")
    return resp


def get_domain_details(domain_id):
    """Get domain details including DNS records."""
    resp = requests.get(f"{BASE_URL}/domains/{domain_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def main():
    print("=" * 70)
    print("RESEND DOMAIN RECEIVING SETUP")
    print("=" * 70)

    # Step 1: List all domains
    print("\n📋 Fetching domains from Resend...")
    all_domains = list_domains()

    domain_map = {}
    for d in all_domains:
        name = d.get("name", "")
        if name in DOMAINS:
            domain_map[name] = d

    print(f"   Found {len(domain_map)}/{len(DOMAINS)} domains\n")

    # Show current status
    print("CURRENT STATUS:")
    print("-" * 70)
    for name in DOMAINS:
        if name in domain_map:
            d = domain_map[name]
            caps = d.get("capabilities", {})
            sending = caps.get("sending", "unknown")
            receiving = caps.get("receiving", "unknown")
            status = d.get("status", "unknown")
            print(f"  {name:30s} | status: {status:15s} | send: {sending:10s} | recv: {receiving}")
        else:
            print(f"  {name:30s} | NOT FOUND in Resend")

    # Step 2: Enable receiving on each domain
    print("\n" + "=" * 70)
    print("ENABLING RECEIVING...")
    print("=" * 70)

    for name in DOMAINS:
        if name not in domain_map:
            print(f"\n⚠️  {name} not found — skipping")
            continue

        d = domain_map[name]
        caps = d.get("capabilities", {})
        if caps.get("receiving") == "enabled":
            print(f"\n✅ {name} — receiving already enabled")
        else:
            print(f"\n🔄 {name} — enabling receiving...")
            enable_receiving(d["id"], name)

    # Step 3: Get MX records needed
    print("\n" + "=" * 70)
    print("MX RECORDS TO ADD AT EACH DNS PROVIDER")
    print("=" * 70)

    for name in DOMAINS:
        if name not in domain_map:
            continue

        d = domain_map[name]
        details = get_domain_details(d["id"])
        records = details.get("records", [])

        mx_records = [r for r in records if r.get("type") == "MX" and r.get("record", "").upper() != "SPF"]
        receiving_records = [r for r in records if "inbound" in r.get("value", "").lower() or "receiving" in r.get("record", "").lower()]

        # Also check for any MX record that's not the SPF bounce-back one
        all_mx = [r for r in records if r.get("type") == "MX"]

        print(f"\n{'─' * 50}")
        print(f"  📧 {name}")
        print(f"     Domain ID: {d['id']}")
        print(f"     Status: {details.get('status', 'unknown')}")
        caps = details.get("capabilities", {})
        print(f"     Sending: {caps.get('sending', 'unknown')}")
        print(f"     Receiving: {caps.get('receiving', 'unknown')}")

        if all_mx:
            print(f"\n     MX Records to add:")
            for r in all_mx:
                record_type = r.get("record", "")
                name_val = r.get("name", "")
                value = r.get("value", "")
                priority = r.get("priority", "")
                status = r.get("status", "")
                print(f"       Type: MX | Name: {name_val} | Value: {value} | Priority: {priority} | Status: {status}")
        else:
            print(f"\n     ⚠️  No MX records found — check Resend dashboard")

        # Show all records for reference
        print(f"\n     All DNS records ({len(records)} total):")
        for r in records:
            rtype = r.get("type", "")
            rname = r.get("name", "")
            rvalue = r.get("value", "")[:60]
            rstatus = r.get("status", "")
            rrecord = r.get("record", "")
            print(f"       [{rrecord:5s}] {rtype:5s} | {rname:45s} | {rstatus:10s} | {rvalue}")

    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print("""
1. For each domain above, add the MX record to your DNS provider
2. Go to https://resend.com/domains and click "I've added the record"
3. Wait for verification (usually a few minutes)

⚠️  IMPORTANT for Cloudflare domains (academicsatire.com):
   These already have Cloudflare Email Routing MX records.
   Adding Resend's MX record may conflict. You have two options:
   a) Remove Cloudflare Email Routing and use Resend inbound instead
   b) Keep Cloudflare routing and skip Resend receiving on these 2 domains
""")


if __name__ == "__main__":
    main()
