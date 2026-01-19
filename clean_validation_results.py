#!/usr/bin/env python3
"""Remove undeliverable and high-risk emails from subscriber list based on validation results"""
import os
import csv
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
mailing_list = f'subscribers@{domain}'

# Find emails to remove from validation CSV
to_remove = []

with open('c2f48d88-44ce-4b8a-bf75-4013bd70b094.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        result = row.get('result', '')
        risk = row.get('risk', '')
        email = row.get('address', '')
        
        # Remove: undeliverable, do_not_send, or high risk
        if result in ['undeliverable', 'do_not_send'] or risk == 'high':
            to_remove.append(email)

print(f'📊 Emails to remove: {len(to_remove)}')
print(f'   - undeliverable + do_not_send + high risk')
print()

# Remove from mailing list
removed = 0
failed = 0

for i, email in enumerate(to_remove):
    url = f'https://api.mailgun.net/v3/lists/{mailing_list}/members/{email}'
    resp = requests.delete(url, auth=('api', api_key))
    if resp.status_code == 200:
        removed += 1
        if removed % 50 == 0:
            print(f'  Progress: {removed}/{len(to_remove)} removed...')
    else:
        failed += 1

print()
print(f'✅ Removed from list: {removed}')
print(f'⏭️  Not in list/already removed: {failed}')
