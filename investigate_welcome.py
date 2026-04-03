#!/usr/bin/env python3
"""Investigate welcome email delivery for Predictify users."""
import json
import requests

SUPABASE_URL = "https://jimcdgkwbbrxgakingtg.supabase.co"
SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImppbWNkZ2t3YmJyeGdha2luZ3RnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzOTkyMCwiZXhwIjoyMDg4NDE1OTIwfQ.wD9UOqu3YufoKmnvaJghKfAcBBIokVkKXc-BCQ4tXP4"

h = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
}

# 1. Check if kaynoureddine@gmail.com is in welcomed_users
print("=" * 60)
print("1. Check kaynoureddine@gmail.com in welcomed_users")
print("=" * 60)
r = requests.get(
    f"{SUPABASE_URL}/rest/v1/welcomed_users?email=eq.kaynoureddine@gmail.com&select=*",
    headers=h, timeout=15,
)
data = r.json()
if data:
    print(json.dumps(data, indent=2))
else:
    print("  NOT FOUND in welcomed_users!")

# 2. Check recent predictify welcomed users
print("\n" + "=" * 60)
print("2. Recent Predictify welcomed users (last 10)")
print("=" * 60)
r2 = requests.get(
    f"{SUPABASE_URL}/rest/v1/welcomed_users?app_id=eq.predictify&select=*&order=welcomed_at.desc&limit=10",
    headers=h, timeout=15,
)
for u in r2.json():
    print(f"  {u.get('email')} | lang={u.get('language')} | at={u.get('welcomed_at')} | bounced={u.get('bounced')}")

# 3. Count per app
print("\n" + "=" * 60)
print("3. Welcomed users count per app")
print("=" * 60)
r3 = requests.get(
    f"{SUPABASE_URL}/rest/v1/rpc/",
    headers=h, timeout=15,
)
# Simple approach: get all app_ids
for app_id in ["thesis_generator", "redflag_scanner", "fresh_start", "soulplan", "pupshape", "predictify", "volume_booster", "horse_racing"]:
    r3 = requests.get(
        f"{SUPABASE_URL}/rest/v1/welcomed_users?app_id=eq.{app_id}&select=email",
        headers={**h, "Prefer": "count=exact"},
        timeout=15,
    )
    count = r3.headers.get("content-range", "?")
    print(f"  {app_id}: {count}")

# 4. Check if Firebase has this user
print("\n" + "=" * 60)
print("4. Check Firebase users for predictify-3f30d")
print("=" * 60)
import os
GOOGLE_CLIENT_ID = "563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "j9iVZfS8kkCEFUPaAeJV0sAi"
FIREBASE_TOKEN = os.environ.get('FIREBASE_TOKEN', '')

# Get access token
token_resp = requests.post(
    "https://oauth2.googleapis.com/token",
    data={
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": FIREBASE_TOKEN,
        "grant_type": "refresh_token",
    },
    timeout=15,
)
if token_resp.status_code != 200:
    print(f"  Token exchange failed: {token_resp.status_code}")
else:
    access_token = token_resp.json()["access_token"]
    
    # List Firebase users for predictify-3f30d
    all_users = []
    next_page = None
    while True:
        fb_url = f"https://identitytoolkit.googleapis.com/v1/projects/predictify-3f30d/accounts:batchGet?maxResults=500"
        if next_page:
            fb_url += f"&nextPageToken={next_page}"
        fb_resp = requests.get(fb_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        if fb_resp.status_code != 200:
            print(f"  Firebase API error: {fb_resp.status_code} {fb_resp.text[:200]}")
            break
        fb_data = fb_resp.json()
        users = fb_data.get("users", [])
        all_users.extend(users)
        next_page = fb_data.get("nextPageToken")
        if not next_page:
            break
    
    print(f"  Total Firebase users in predictify-3f30d: {len(all_users)}")
    
    # Find users NOT in welcomed_users
    firebase_emails = set()
    for u in all_users:
        email = (u.get("email") or "").lower().strip()
        if email and "cloudtestlabaccounts.com" not in email and "example.com" not in email:
            firebase_emails.add(email)
    
    # Get all welcomed predictify emails
    welcomed_resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/welcomed_users?app_id=eq.predictify&select=email",
        headers=h, timeout=15,
    )
    welcomed_emails = set(u["email"] for u in welcomed_resp.json())
    
    missing = firebase_emails - welcomed_emails
    print(f"  Firebase emails (valid): {len(firebase_emails)}")
    print(f"  Welcomed emails: {len(welcomed_emails)}")
    print(f"  Missing (not welcomed): {len(missing)}")
    if missing:
        print(f"  Missing emails:")
        for e in sorted(missing):
            # Find created date
            for u in all_users:
                if (u.get("email") or "").lower().strip() == e:
                    created = u.get("createdAt", "?")
                    from datetime import datetime
                    try:
                        created_dt = datetime.fromtimestamp(int(created) / 1000)
                        created_str = created_dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        created_str = created
                    print(f"    {e} | created: {created_str}")
                    break

# 5. Check pg_cron job status
print("\n" + "=" * 60)
print("5. Check pg_cron job status")
print("=" * 60)
cron_resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/rpc/",
    headers=h, timeout=15,
)
# Try querying cron.job directly via SQL
sql_resp = requests.post(
    f"{SUPABASE_URL}/rest/v1/rpc/",
    headers={**h, "Content-Type": "application/json"},
    json={},
    timeout=15,
)
print("  (Need to check via Supabase dashboard or Edge Function logs)")

# 6. Test invoke the check-new-users function manually
print("\n" + "=" * 60)
print("6. Manually invoke check-new-users Edge Function")
print("=" * 60)
invoke_resp = requests.post(
    f"{SUPABASE_URL}/functions/v1/check-new-users",
    headers={
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    },
    json={},
    timeout=120,
)
print(f"  Status: {invoke_resp.status_code}")
print(f"  Response: {invoke_resp.text[:2000]}")
