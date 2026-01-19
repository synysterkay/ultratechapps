#!/usr/bin/env python3
"""Send discovery email test"""
import os
import sys
import requests
import uuid

# Load .env manually
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value.strip('"').strip("'")

api_key = os.environ.get('MAILGUN_API_KEY')
domain = os.environ.get('MAILGUN_DOMAIN', 'bestaiapps.site')

# Import after env is set
sys.path.insert(0, 'scripts')
from email_sequence_manager import EmailSequenceManager

manager = EmailSequenceManager()

# Generate the HTML
html_content = manager._generate_discovery_email_html()

# Send directly via Mailgun
url = f'https://api.mailgun.net/v3/{domain}/messages'

data = {
    'from': f'Anas from Best AI Apps <hello@{domain}>',
    'to': 'testkaynel@gmail.com',
    'subject': '14 AI apps that actually work (we tested 200+)',
    'html': html_content,
    'o:tag': ['test', 'discovery'],
    'o:tracking': 'yes',
    'h:Message-ID': f'<{uuid.uuid4()}@bestaiapps.site>',
    'h:X-Preview-Text': 'The App Store is a mess. Here is your shortlist.'
}

response = requests.post(url, auth=('api', api_key), data=data)

if response.status_code == 200:
    print('✅ Discovery email sent to anaskay.13@gmail.com!')
else:
    print(f'❌ Failed: {response.status_code} - {response.text}')
