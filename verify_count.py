#!/usr/bin/env python3
"""Verify exact count of missing welcome emails for Predictify."""
import os
import requests

SUPABASE_URL = 'https://jimcdgkwbbrxgakingtg.supabase.co'
SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImppbWNkZ2t3YmJyeGdha2luZ3RnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzOTkyMCwiZXhwIjoyMDg4NDE1OTIwfQ.wD9UOqu3YufoKmnvaJghKfAcBBIokVkKXc-BCQ4tXP4'
h = {'apikey': SERVICE_KEY, 'Authorization': f'Bearer {SERVICE_KEY}'}

# Get ALL Predictify welcomed emails (paginate past 1000 limit)
welcomed = set()
offset = 0
while True:
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/welcomed_users?app_id=eq.predictify&select=email&offset={offset}&limit=1000',
        headers=h, timeout=30
    )
    data = r.json()
    for u in data:
        welcomed.add(u['email'].lower().strip())
    print(f'  Fetched page at offset {offset}: {len(data)} rows')
    if len(data) < 1000:
        break
    offset += 1000

print(f'\nTotal welcomed Predictify users: {len(welcomed)}')

# Now get Firebase user count from investigate script's approach
REFRESH_TOKEN = os.environ.get('FIREBASE_TOKEN', '')

# Get access token
token_r = requests.post('https://oauth2.googleapis.com/token', data={
    'client_id': '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com',
    'client_secret': 'j9iVZfS8kkCEFUPaAeJV0sAi',
    'refresh_token': REFRESH_TOKEN,
    'grant_type': 'refresh_token',
}, timeout=15)
access_token = token_r.json()['access_token']

# List ALL Firebase users for predictify
firebase_emails = set()
next_page = None
page_num = 0
while True:
    url = f'https://identitytoolkit.googleapis.com/v1/projects/predictify-3f30d/accounts:batchGet?maxResults=500'
    if next_page:
        url += f'&nextPageToken={next_page}'
    r = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, timeout=30)
    data = r.json()
    users = data.get('users', [])
    for u in users:
        email = (u.get('email') or '').lower().strip()
        if email and 'cloudtestlabaccounts' not in email and 'example.com' not in email:
            firebase_emails.add(email)
    page_num += 1
    print(f'  Firebase page {page_num}: {len(users)} users')
    next_page = data.get('nextPageToken')
    if not next_page:
        break

print(f'\nTotal Firebase Predictify users (valid): {len(firebase_emails)}')

missing = firebase_emails - welcomed
print(f'Total welcomed: {len(welcomed)}')
print(f'Missing (not welcomed): {len(missing)}')

# Show some recent missing users (by checking creation date)
if missing:
    # Get creation dates for missing users
    sample = list(missing)[:10]
    print(f'\nSample missing users (first 10):')
    for email in sample:
        print(f'  {email}')
