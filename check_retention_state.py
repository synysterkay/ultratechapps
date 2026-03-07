#!/usr/bin/env python3
import json

with open('cache/retention_state.json') as f:
    d = json.load(f)

users = d.get('users', {})
print(f'Tracked users: {len(users)}')

apps = {}
for email, info in users.items():
    a = info.get('app', '?')
    apps[a] = apps.get(a, 0) + 1
for a, c in sorted(apps.items(), key=lambda x: -x[1]):
    print(f'  {a}: {c} users tracked')

daily = d.get('daily_sends', {})
for date in sorted(daily.keys())[-5:]:
    info = daily[date]
    print(f'  {date}: sent={info.get("sent",0)}, failed={info.get("failed",0)}')

suppressed = d.get('suppressed_recipients', [])
print(f'Suppressed: {len(suppressed)}')

pred_users = [e for e, i in users.items() if i.get('app') == 'Predictify']
print(f'\nPredictify users in retention state: {len(pred_users)}')
for u in pred_users[:5]:
    info = users[u]
    print(f'  {u}: {info.get("emails_sent",0)} emails, last: {info.get("last_email_sent","?")}')
if len(pred_users) > 5:
    print(f'  ... and {len(pred_users)-5} more')

thesis_users = [e for e, i in users.items() if i.get('app') == 'Thesis Generator']
print(f'\nThesis Generator users in retention state: {len(thesis_users)}')
max_emails = max((i.get('emails_sent', 0) for i in users.values()), default=0)
print(f'Max emails sent to any user: {max_emails}')
