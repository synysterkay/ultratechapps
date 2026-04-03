#!/usr/bin/env python3
"""
Backfill missing welcome emails for all apps.
Calls the check-new-users function per-project to send welcome emails
to users who were missed due to the timeout bug.

Usage: python3 backfill_welcome.py [project-id]
  Without args: shows missing counts per project
  With project-id: triggers backfill for that project (60 emails per call)
"""
import os
import requests
import sys
import time

SUPABASE_URL = 'https://jimcdgkwbbrxgakingtg.supabase.co'
SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImppbWNkZ2t3YmJyeGdha2luZ3RnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjgzOTkyMCwiZXhwIjoyMDg4NDE1OTIwfQ.wD9UOqu3YufoKmnvaJghKfAcBBIokVkKXc-BCQ4tXP4'
h = {'apikey': SERVICE_KEY, 'Authorization': f'Bearer {SERVICE_KEY}'}

REFRESH_TOKEN = os.environ.get('FIREBASE_TOKEN', '')
CLIENT_ID = '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com'
CLIENT_SECRET = 'j9iVZfS8kkCEFUPaAeJV0sAi'

PROJECTS = {
    'thesis-generator-web': 'thesis_generator',
    'redflagscanner': 'redflag_scanner',
    'breakuptherapy-e7dc0': 'fresh_start',
    'soulplan-dateplanner': 'soulplan',
    'petmealai': 'pupshape',
    'predictify-3f30d': 'predictify',
    'volume-booster-2f7bf': 'volume_booster',
    'horse-racing-f67e8': 'horse_racing',
}

def get_access_token():
    r = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token',
    }, timeout=15)
    return r.json()['access_token']

def get_welcomed_count(app_id):
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/welcomed_users?app_id=eq.{app_id}&select=email',
        headers={**h, 'Prefer': 'count=exact'}, timeout=15
    )
    cr = r.headers.get('content-range', '0-0/0')
    return int(cr.split('/')[-1])

def get_firebase_count(project_id, token):
    count = 0
    next_page = None
    while True:
        url = f'https://identitytoolkit.googleapis.com/v1/projects/{project_id}/accounts:batchGet?maxResults=500'
        if next_page:
            url += f'&nextPageToken={next_page}'
        r = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=30)
        data = r.json()
        users = data.get('users', [])
        for u in users:
            email = (u.get('email') or '').lower().strip()
            if email and 'cloudtestlabaccounts' not in email and 'example.com' not in email:
                count += 1
        next_page = data.get('nextPageToken')
        if not next_page:
            break
    return count

def trigger_backfill(project_id):
    """Call check-new-users with specific project to process up to 60 emails."""
    print(f'\n  Triggering backfill for {project_id} ({PROJECTS[project_id]})...')
    try:
        r = requests.post(
            f'{SUPABASE_URL}/functions/v1/check-new-users',
            headers={**h, 'Content-Type': 'application/json'},
            json={'project': project_id},
            timeout=120
        )
        if r.status_code == 200:
            data = r.json()
            print(f'  Result: sent={data.get("welcome_emails_sent", 0)}, '
                  f'found={data.get("new_users_found", 0)}, '
                  f'cap={data.get("hit_cap", False)}, '
                  f'time={data.get("elapsed_ms", 0)}ms')
            for d in data.get('details', []):
                print(f'    {d}')
            return data
        else:
            print(f'  Error: {r.status_code} {r.text[:200]}')
            return None
    except requests.exceptions.ReadTimeout:
        print(f'  TIMEOUT after 120s')
        return None

def show_status():
    print('Getting Firebase access token...')
    token = get_access_token()
    print()
    print(f'{"Project":<25} {"App ID":<20} {"Firebase":>8} {"Welcomed":>8} {"Missing":>8}')
    print('-' * 75)
    total_missing = 0
    for pid, app_id in PROJECTS.items():
        welcomed = get_welcomed_count(app_id)
        firebase = get_firebase_count(pid, token)
        missing = max(0, firebase - welcomed)
        total_missing += missing
        flag = ' ⚠️' if missing > 0 else ' ✅'
        print(f'{pid:<25} {app_id:<20} {firebase:>8} {welcomed:>8} {missing:>8}{flag}')
    print('-' * 75)
    print(f'{"TOTAL":<45} {"":>8} {"":>8} {total_missing:>8}')
    return total_missing

def main():
    if len(sys.argv) < 2:
        total = show_status()
        if total > 0:
            print(f'\nTo backfill a specific project:')
            print(f'  python3 backfill_welcome.py <project-id>')
            print(f'  python3 backfill_welcome.py predictify-3f30d')
            print(f'\nTo backfill ALL projects (loops until done):')
            print(f'  python3 backfill_welcome.py --all')
        return

    if sys.argv[1] == '--all':
        print('Backfilling ALL projects...\n')
        iteration = 0
        while True:
            iteration += 1
            total = show_status()
            if total == 0:
                print('\n✅ All users welcomed!')
                break
            print(f'\n--- Iteration {iteration} ({total} remaining) ---')
            for pid in PROJECTS:
                welcomed = get_welcomed_count(PROJECTS[pid])
                token = get_access_token()
                firebase = get_firebase_count(pid, token)
                if firebase > welcomed:
                    result = trigger_backfill(pid)
                    if result and result.get('welcome_emails_sent', 0) > 0:
                        time.sleep(2)  # Brief pause between projects
            print('\nWaiting 10s before next iteration...')
            time.sleep(10)
    else:
        project_id = sys.argv[1]
        if project_id not in PROJECTS:
            print(f'Unknown project: {project_id}')
            print(f'Valid: {", ".join(PROJECTS.keys())}')
            return
        # Keep calling until no more new users
        while True:
            result = trigger_backfill(project_id)
            if not result:
                break
            sent = result.get('welcome_emails_sent', 0)
            remaining = result.get('remaining', 0)
            if sent == 0 and remaining == 0:
                print(f'\n✅ No more new users for {project_id}')
                break
            if result.get('hit_cap') or result.get('hit_deadline'):
                print(f'  More users remaining, continuing in 5s...')
                time.sleep(5)
            else:
                print(f'\n✅ All new users processed for {project_id}')
                break

if __name__ == '__main__':
    main()
