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

# Process this single subscriber
manager._process_subscriber(subscriber)
print('---')
print('Done! Check your inbox.')
