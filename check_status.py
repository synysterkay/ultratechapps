#!/usr/bin/env python3
import requests
import json

SUPABASE_URL = 'https://jimcdgkwbbrxgakingtg.supabase.co'
SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImppbWNkZ2t3YmJyeGdha2luZ3RnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzOTkyMCwiZXhwIjoyMDg4NDE1OTIwfQ.wD9UOqu3YufoKmnvaJghKfAcBBIokVkKXc-BCQ4tXP4'
h = {'apikey': SERVICE_KEY, 'Authorization': f'Bearer {SERVICE_KEY}'}

# 1. Count total welcomed per app and last welcomed date
print('=== WELCOMED STATS (last entry per app) ===')
apps = ['predictify', 'thesis_generator', 'redflag_scanner', 'fresh_start', 'soulplan', 'pupshape', 'volume_booster', 'horse_racing']
for app in apps:
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/welcomed_users?app_id=eq.{app}&select=email,welcomed_at&order=welcomed_at.desc&limit=1',
        headers=h, timeout=15
    )
    data = r.json()
    count_r = requests.get(
        f'{SUPABASE_URL}/rest/v1/welcomed_users?app_id=eq.{app}&select=email',
        headers={**h, 'Prefer': 'count=exact'}, timeout=15
    )
    count = count_r.headers.get('content-range', '?')
    last = data[0]['welcomed_at'] if data else 'N/A'
    print(f'  {app}: count={count}, last_welcomed={last}')

# 2. Check the most recent welcomed user across ALL apps
print()
print('=== MOST RECENT WELCOMED (any app) ===')
r = requests.get(
    f'{SUPABASE_URL}/rest/v1/welcomed_users?select=email,app_id,welcomed_at,language&order=welcomed_at.desc&limit=5',
    headers=h, timeout=15
)
for u in r.json():
    print(f'  {u["email"]} | app={u["app_id"]} | at={u["welcomed_at"]} | lang={u["language"]}')

# 3. Count bounces
print()
print('=== BOUNCED EMAILS ===')
r = requests.get(
    f'{SUPABASE_URL}/rest/v1/welcomed_users?bounced=eq.true&select=email,app_id',
    headers={**h, 'Prefer': 'count=exact'}, timeout=15
)
print(f'  Total bounced: {r.headers.get("content-range", "?")}')

# 4. Check edge function logs
print()
print('=== TRYING FUNCTION INVOCATION (with small batch) ===')
try:
    r = requests.post(
        f'{SUPABASE_URL}/functions/v1/check-new-users',
        headers={**h, 'Content-Type': 'application/json'},
        json={'maxPerProject': 5},
        timeout=30
    )
    print(f'  Status: {r.status_code}')
    print(f'  Response: {r.text[:500]}')
except Exception as e:
    print(f'  Error: {e}')
