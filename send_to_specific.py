#!/usr/bin/env python3
"""Send email to specific subscriber"""
import os
import sys

# Load .env manually
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value.strip('"').strip("'")

sys.path.insert(0, 'scripts')
from email_sequence_manager import EmailSequenceManager

# Initialize manager
manager = EmailSequenceManager()

# Find subscriber
test_email = 'anaskay.13@gmail.com'
subscribers = manager.subscriber_manager.get_subscribers()

subscriber = None
for s in subscribers:
    if s.get('address') == test_email:
        subscriber = s
        break

if not subscriber:
    print(f'❌ Subscriber {test_email} not found!')
    sys.exit(1)

print(f'✅ Found subscriber: {test_email}')
print(f'📊 Stats: {subscriber.get("vars", {})}')
print()

# Get sequence info
should_send, sequence_info = manager._should_send_email(subscriber)

if not should_send or not sequence_info:
    print(f'⚠️  Subscriber not eligible yet (needs 12h between emails)')
    print(f'Forcing send anyway for testing...')
    should_send = True
    sequence_info = {'sequence': 'promotional'}

print(f'📧 Sequence: {sequence_info["sequence"]}')

# Process this subscriber
import json
apps = json.load(open('apps.json'))

# Use manager's app selection (now locked to Thesis Generator)
emails_received = subscriber.get('vars', {}).get('emails_received', 0)
app_data = manager._get_app_for_email_number(emails_received)
niche = subscriber.get('vars', {}).get('niche', 'productivity')

print(f'🎯 App: {app_data["name"]}')
print(f'📱 App Store: {"✅" if app_data.get("app_store_url") else "❌"}')
print(f'🤖 Google Play: {"✅" if app_data.get("google_play_url") else "❌"}')
print(f'🏷️  Niche: {niche}')
print()

# Generate email content
day = sequence_info.get('day') if sequence_info['sequence'] == 'welcome' else None
email_data = manager.email_generator.generate_email(
    niche=niche,
    app_data=app_data,
    sequence_type=sequence_info['sequence'],
    day=day
)

if not email_data:
    print('❌ Failed to generate email content!')
    sys.exit(1)

print(f'✉️  Subject: {email_data["subject"]}')
print()

# Send email
success = manager.send_to_subscriber(subscriber, email_data, app_data, sequence_info)

if success:
    print('✅ Email sent successfully! Check your inbox.')
else:
    print('❌ Failed to send email')
