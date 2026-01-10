#!/usr/bin/env python3
"""
Quick test of all marketing automation systems
"""

import sys
sys.path.insert(0, 'scripts')

from dotenv import load_dotenv
load_dotenv()

print("SYSTEM TEST SUMMARY")
print("=" * 50)

# Test 1: Bluesky
try:
    from publishers.social_publisher import BlueskyPublisher
    bp = BlueskyPublisher()
    print("[OK] Bluesky: Ready (credentials loaded)")
except Exception as e:
    print(f"[FAIL] Bluesky: {e}")

# Test 2: GitHub
try:
    from publishers.github_publisher import GitHubPublisher
    gp = GitHubPublisher()
    print(f"[OK] GitHub: Ready (repo: {gp.repo.full_name})")
except Exception as e:
    print(f"[FAIL] GitHub: {e}")

# Test 3: Dev.to
try:
    from publishers.devto_publisher import DevToPublisher
    dt = DevToPublisher()
    print("[OK] Dev.to: Ready (API key set)")
except Exception as e:
    print(f"[FAIL] Dev.to: {e}")

# Test 4: Mailgun (Subscribers)
try:
    from mailgun_subscriber import MailgunSubscriber
    mg = MailgunSubscriber()
    subs = mg.get_subscribers()
    print(f"[OK] Mailgun Subscribers: {len(subs)}+ loaded")
except Exception as e:
    print(f"[FAIL] Mailgun: {e}")

# Test 5: Email Generator
try:
    from email_generator import EmailGenerator
    eg = EmailGenerator()
    print("[OK] Email Generator: Ready (DeepSeek)")
except Exception as e:
    print(f"[FAIL] Email Generator: {e}")

# Test 6: Website API
import subprocess
result = subprocess.run(['curl', '-s', '-X', 'POST', 
    'https://subscribe-api.cryptoanalyser2025.workers.dev',
    '-H', 'Content-Type: application/json',
    '-d', '{"email":"api-check@test.com","niche":"test"}'],
    capture_output=True, text=True)
if 'success' in result.stdout:
    print("[OK] Website Subscribe API: Working")
else:
    print(f"[FAIL] Website API: {result.stdout[:50]}")

print("=" * 50)
print("All core systems tested!")
