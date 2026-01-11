#!/usr/bin/env python3
"""Send test email to specific subscriber using full sequence process"""

import sys
import os
sys.path.insert(0, 'scripts')

from dotenv import load_dotenv
load_dotenv()

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
    print(f'Subscriber {test_email} not found!')
    sys.exit(1)

print(f'Found subscriber: {test_email}')
print(f'Vars: {subscriber.get("vars", {})}')
print('---')

# Get sequence info for subscriber
should_send, sequence_info = manager._should_send_email(subscriber)
print(f'Sequence: {sequence_info}')

# Select app for subscriber
app_data, niche = manager._select_app_for_subscriber(subscriber)
print(f'App: {app_data["name"]}')
print(f'Niche: {niche}')

# Generate email content
day = sequence_info.get('day') if sequence_info['sequence'] == 'welcome' else None
email_data = manager.email_generator.generate_email(
    niche=niche,
    app_data=app_data,
    sequence_type=sequence_info['sequence'],
    day=day
)

if not email_data:
    print('Failed to generate email content!')
    sys.exit(1)

print(f'Subject: {email_data["subject"]}')
print('---')

# Send email
success = manager.send_to_subscriber(subscriber, email_data, app_data, sequence_info)

if success:
    print('---')
    print('✅ Done! Check your inbox.')
else:
    print('---')
    print('❌ Failed to send email')
