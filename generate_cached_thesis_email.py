#!/usr/bin/env python3
"""Generate the perfect Thesis Generator email and cache it"""
import os
import sys
import json

# Load .env manually
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value.strip('"').strip("'")

sys.path.insert(0, 'scripts')
from email_generator import EmailGenerator

# Load apps
apps = json.load(open('apps.json'))
thesis_app = next((app for app in apps if 'Thesis Generator' in app['name']), None)

if not thesis_app:
    print("❌ Thesis Generator not found!")
    sys.exit(1)

print(f"🎯 Generating perfect email for: {thesis_app['name']}")
print(f"📱 App Store: {thesis_app.get('app_store_url', 'None')[:50]}...")
print(f"🤖 Google Play: {thesis_app.get('google_play_url', 'None')[:50]}...")
print()

# Generate email
generator = EmailGenerator()
email_data = generator.generate_email(
    niche='productivity',
    app_data=thesis_app,
    sequence_type='promotional'
)

if not email_data:
    print("❌ Failed to generate email!")
    sys.exit(1)

print(f"✅ Email generated successfully!")
print(f"📧 Subject: {email_data['subject']}")
print(f"📝 Preview: {email_data.get('preview_text', 'N/A')}")
print(f"📊 Paragraphs: {len(email_data['body_paragraphs'])}")
print(f"🎯 Takeaways: {len(email_data.get('key_takeaways', []))}")
print()

# Save to cache
cache_file = 'cache/thesis_generator_email_cache.json'
os.makedirs('cache', exist_ok=True)

with open(cache_file, 'w') as f:
    json.dump(email_data, f, indent=2)

print(f"💾 Cached to: {cache_file}")
print()
print("🚀 This email will now be sent to all remaining subscribers!")
