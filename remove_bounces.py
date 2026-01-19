#!/usr/bin/env python3
"""Remove all bounced emails from subscriber list"""
import os
import requests

# Load .env
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value.strip('"').strip("'")

api_key = os.environ.get('MAILGUN_API_KEY')
domain = 'bestaiapps.site'

# Get ALL bounces (paginate)
all_bounces = []
url = f'https://api.mailgun.net/v3/{domain}/bounces'
params = {'limit': 300}

while True:
    response = requests.get(url, auth=('api', api_key), params=params)
    if response.status_code != 200:
        break
    data = response.json()
    items = data.get('items', [])
    if not items:
        break
    all_bounces.extend(items)
    paging = data.get('paging', {})
    next_url = paging.get('next')
    if not next_url or len(items) < 300:
        break
    url = next_url
    params = {}

print(f'Total bounced emails: {len(all_bounces)}')

# Remove each bounced email from the mailing list
mailing_list = f'subscribers@{domain}'
removed = 0
failed = 0

for bounce in all_bounces:
    email = bounce['address']
    unsub_url = f'https://api.mailgun.net/v3/lists/{mailing_list}/members/{email}'
    resp = requests.delete(unsub_url, auth=('api', api_key))
    if resp.status_code == 200:
        removed += 1
        print(f'  Removed: {email}')
    else:
        failed += 1

print(f'\nRemoved from list: {removed}')
print(f'Not in list/failed: {failed}')
