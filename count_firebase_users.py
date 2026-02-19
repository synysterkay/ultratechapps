#!/usr/bin/env python3
import json

projects = {
    'Thesis Generator': 'firebase_exports/thesis_web_users.json',
    'Fresh Start: Breakup Therapy': 'firebase_exports/breakuptherapy-e7dc0_fresh.json',
    'Red Flag Scanner AI': 'firebase_exports/redflagscanner_fresh.json',
    'SoulPlan: Plan Dates Together': 'firebase_exports/soulplan-dateplanner_fresh.json',
    'PupShape: Dog Weight Loss Plan': 'firebase_exports/petmealai_fresh.json',
    'Smart Notes - AI Meeting Summary': 'firebase_exports/audio-recorder-microphone_fresh.json',
}

total = 0
total_emails = 0
print('FULL FIREBASE USER REPORT (FRESH EXPORT)')
print('=' * 60)
for name, path in projects.items():
    with open(path) as f:
        data = json.load(f)
    users = data.get('users', data) if isinstance(data, dict) else data
    emails = [u for u in users if u.get('email')]
    total += len(users)
    total_emails += len(emails)
    print(f'  {name}:')
    print(f'    Total accounts: {len(users)} | With email: {len(emails)}')
print()
print(f'TOTAL: {total} accounts | {total_emails} with email')
