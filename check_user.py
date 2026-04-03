#!/usr/bin/env python3
"""Check if specific user was welcomed + investigate Firestore language issue"""
import os
import requests

SUPABASE_URL = 'https://jimcdgkwbbrxgakingtg.supabase.co'
SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImppbWNkZ2t3YmJyeGdha2luZ3RnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzOTkyMCwiZXhwIjoyMDg4NDE1OTIwfQ.wD9UOqu3YufoKmnvaJghKfAcBBIokVkKXc-BCQ4tXP4'
h = {'apikey': SERVICE_KEY, 'Authorization': f'Bearer {SERVICE_KEY}'}

REFRESH_TOKEN = os.environ.get('FIREBASE_TOKEN', '')
CLIENT_ID = '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com'
CLIENT_SECRET = 'j9iVZfS8kkCEFUPaAeJV0sAi'

# Get access token
token_r = requests.post('https://oauth2.googleapis.com/token', data={
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'refresh_token': REFRESH_TOKEN,
    'grant_type': 'refresh_token',
}, timeout=15)
access_token = token_r.json()['access_token']

# 1. Check if kaynoureddine@gmail.com is in welcomed_users
print('=== CHECK kaynoureddine@gmail.com ===')
r = requests.get(
    f'{SUPABASE_URL}/rest/v1/welcomed_users?email=eq.kaynoureddine@gmail.com&select=*',
    headers=h, timeout=15
)
data = r.json()
if data:
    for u in data:
        print(f'  Found: app={u["app_id"]}, lang={u["language"]}, at={u["welcomed_at"]}, bounced={u.get("bounced")}')
else:
    print('  NOT FOUND in welcomed_users')

# 2. Check Firestore users collection structure for predictify
print('\n=== FIRESTORE USERS STRUCTURE (predictify-3f30d) ===')
url = 'https://firestore.googleapis.com/v1/projects/predictify-3f30d/databases/(default)/documents/users?pageSize=5'
r = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, timeout=15)
data = r.json()
docs = data.get('documents', [])
print(f'  Total docs in first page: {len(docs)}')
for doc in docs[:3]:
    doc_name = doc.get('name', '').split('/')[-1]
    fields = doc.get('fields', {})
    field_names = list(fields.keys())
    print(f'\n  Doc ID: {doc_name}')
    print(f'  Fields: {field_names}')
    for k, v in fields.items():
        val_type = list(v.keys())[0]
        val = v[val_type]
        if isinstance(val, str) and len(val) > 100:
            val = val[:100] + '...'
        print(f'    {k}: ({val_type}) = {val}')

# 3. Try looking up kaynoureddine@gmail.com in Firestore
print('\n=== FIRESTORE LOOKUP: kaynoureddine@gmail.com ===')
query_url = f'https://firestore.googleapis.com/v1/projects/predictify-3f30d/databases/(default)/documents:runQuery'
r = requests.post(query_url, headers={
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json',
}, json={
    'structuredQuery': {
        'from': [{'collectionId': 'users'}],
        'where': {
            'fieldFilter': {
                'field': {'fieldPath': 'email'},
                'op': 'EQUAL',
                'value': {'stringValue': 'kaynoureddine@gmail.com'},
            },
        },
        'limit': 1,
    },
}, timeout=15)
results = r.json()
if results and results[0].get('document'):
    doc = results[0]['document']
    fields = doc.get('fields', {})
    print(f'  Found! Language: {fields.get("language", {}).get("stringValue", "N/A")}')
    for k, v in fields.items():
        val_type = list(v.keys())[0]
        print(f'    {k}: {v[val_type]}')
else:
    print(f'  Not found in Firestore users collection')
    print(f'  Response: {str(results)[:300]}')
