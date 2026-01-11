#!/usr/bin/env python3
"""Reset all subscriber metadata to start fresh email campaign"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('MAILGUN_API_KEY')
domain = os.getenv('MAILGUN_DOMAIN', 'bestaiapps.site')
mailing_list = f'subscribers@{domain}'

print(f"🔄 Resetting subscribers for {mailing_list}...")

# Get all subscribers
response = requests.get(
    f'https://api.mailgun.net/v3/lists/{mailing_list}/members/pages',
    auth=('api', api_key),
    params={'limit': 1000}
)

if response.status_code != 200:
    print(f"Error getting subscribers: {response.text}")
    exit(1)

members = response.json().get('items', [])
print(f"Found {len(members)} subscribers")

reset_count = 0
for member in members:
    email = member['address']
    
    # Reset metadata - clear last_email_sent and emails_received
    new_vars = json.dumps({
        'emails_received': 0,
        'last_email_sent': '',
        'sequence_stage': 'welcome',
        'welcome_day': 0
    })
    
    update_response = requests.put(
        f'https://api.mailgun.net/v3/lists/{mailing_list}/members/{email}',
        auth=('api', api_key),
        data={'vars': new_vars}
    )
    
    if update_response.status_code == 200:
        reset_count += 1
    else:
        print(f"Failed to reset {email}: {update_response.text}")
    
    if reset_count % 100 == 0 and reset_count > 0:
        print(f"  Reset {reset_count} subscribers...")

print(f"✅ Reset {reset_count} subscribers to receive fresh emails")
