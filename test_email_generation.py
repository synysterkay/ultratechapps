#!/usr/bin/env python3
"""Test email generation with app store links"""

import json
import sys
sys.path.insert(0, 'scripts')
from email_sequence_manager import EmailSequenceManager

# Initialize manager
manager = EmailSequenceManager()

# Load apps
apps = json.load(open('apps.json'))

# Test with an app that has both stores
app_dual = apps[1]  # Smart Notes - AI Meeting Summary (has both)
print(f"Testing dual-store app: {app_dual['name']}")
print(f"  App Store: {app_dual.get('app_store_url', 'None')[:50]}...")
print(f"  Google Play: {app_dual.get('google_play_url', 'None')[:50]}...")

# Generate test email data
email_data = {
    'subject': 'Test Email - Dual Store',
    'body_paragraphs': [
        'This is the first paragraph to hook you in.',
        'Second paragraph with more details.',
        'Third paragraph with the value proposition.'
    ],
    'key_takeaways': [
        'Feature 1',
        'Feature 2',
        'Feature 3'
    ]
}

# Generate HTML
html = manager._generate_email_html(email_data, app_dual)

# Save to file
with open('test_email_dual.html', 'w') as f:
    f.write(html)

print("\n✅ Test email saved to test_email_dual.html")

# Test with app that has only Google Play
app_single = apps[0]  # Volume Booster (Google Play only)
print(f"\nTesting single-store app: {app_single['name']}")
print(f"  App Store: {app_single.get('app_store_url') or 'None'}")
print(f"  Google Play: {app_single.get('google_play_url', 'None')[:50]}...")

html2 = manager._generate_email_html(email_data, app_single)
with open('test_email_single.html', 'w') as f:
    f.write(html2)

print("✅ Test email saved to test_email_single.html")

# Test with newly added Humanize AI (App Store only)
app_humanize = [a for a in apps if 'Humanize' in a['name']][0]
print(f"\nTesting App Store only app: {app_humanize['name']}")
print(f"  App Store: {app_humanize.get('app_store_url', 'None')[:50]}...")
print(f"  Google Play: {app_humanize.get('google_play_url') or 'None'}")

html3 = manager._generate_email_html(email_data, app_humanize)
with open('test_email_appstore.html', 'w') as f:
    f.write(html3)

print("✅ Test email saved to test_email_appstore.html")
