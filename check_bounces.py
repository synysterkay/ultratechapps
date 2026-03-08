#!/usr/bin/env python3
"""Check Resend for bounced/complained emails and remove them from retention state."""
import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta

API_KEY = 're_62t3PuEy_23Q3uAQP6SMeYPRLgGVRraAr'
HEADERS = {'Authorization': f'Bearer {API_KEY}'}
STATE_FILE = 'cache/retention_state.json'

def get_all_bounces(max_emails=2000):
    """Check recent Resend emails for bounced/complained status."""
    bounced = []
    complained = []
    all_events = {}
    cursor = None
    total_checked = 0
    page = 0

    while total_checked < max_emails:
        page += 1
        params = {}
        if cursor:
            params['starting_after'] = cursor

        resp = requests.get(
            'https://api.resend.com/emails',
            headers=HEADERS,
            params=params,
            timeout=15,
        )
        if resp.status_code == 429:
            print(f"  Rate limited on page {page}, waiting 2s...")
            time.sleep(2)
            resp = requests.get(
                'https://api.resend.com/emails',
                headers=HEADERS,
                params=params,
                timeout=15,
            )
        if resp.status_code != 200:
            print(f"API error on page {page}: {resp.status_code}")
            break

        data = resp.json()
        emails = data.get('data', [])
        if not emails:
            break

        for e in emails:
            total_checked += 1
            event = e.get('last_event', 'unknown')
            to_list = e.get('to', [])
            to_email = to_list[0] if to_list else 'unknown'

            all_events[event] = all_events.get(event, 0) + 1

            if event == 'bounced':
                bounced.append({
                    'email': to_email,
                    'id': e['id'],
                    'subject': e.get('subject', ''),
                    'created_at': e.get('created_at', ''),
                })
            elif event == 'complained':
                complained.append({
                    'email': to_email,
                    'id': e['id'],
                    'subject': e.get('subject', ''),
                    'created_at': e.get('created_at', ''),
                })

        cursor = emails[-1]['id']
        has_more = data.get('has_more', False)

        if page % 50 == 0:
            print(f"  Page {page}: checked {total_checked} emails so far...")

        if not has_more:
            break

        time.sleep(0.3)

    print(f"\nTotal emails checked: {total_checked}")
    print(f"\nEvent breakdown:")
    for event, count in sorted(all_events.items(), key=lambda x: -x[1]):
        print(f"  {event}: {count}")

    return bounced, complained


def remove_from_state(bounced_emails, complained_emails):
    """Remove bounced/complained emails from retention state."""
    if not os.path.exists(STATE_FILE):
        print(f"\nNo state file found at {STATE_FILE}")
        return

    with open(STATE_FILE, 'r') as f:
        state = json.load(f)

    bad_emails = set()
    for b in bounced_emails:
        bad_emails.add(b['email'])
    for c in complained_emails:
        bad_emails.add(c['email'])

    if not bad_emails:
        print("\nNo bad emails to remove.")
        return

    removed = 0
    suppressed = 0
    for email in bad_emails:
        if email in state.get('users', {}):
            # Mark as suppressed rather than deleting (preserves history)
            reason = 'hard_bounce'
            if any(c['email'] == email for c in complained_emails):
                reason = 'spam_complaint'
            state['users'][email]['suppressed'] = True
            state['users'][email]['suppressed_reason'] = reason
            suppressed += 1
            print(f"  Suppressed: {email} ({reason})")

    # Also completely remove them so they never get re-added
    for email in bad_emails:
        if email in state.get('users', {}):
            del state['users'][email]
            removed += 1

    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"\nRemoved {removed} bounced/complained emails from state.")


if __name__ == '__main__':
    print("=" * 60)
    print("RESEND BOUNCE CHECK")
    print("=" * 60)

    bounced, complained = get_all_bounces(max_emails=2000)

    print(f"\n{'=' * 60}")
    print(f"BOUNCED emails: {len(bounced)}")
    for b in bounced:
        print(f"  {b['email']} (sent: {b['created_at'][:10]})")

    print(f"\nCOMPLAINED emails: {len(complained)}")
    for c in complained:
        print(f"  {c['email']} (sent: {c['created_at'][:10]})")

    if bounced or complained:
        print(f"\n{'=' * 60}")
        print("Removing from retention state...")
        remove_from_state(bounced, complained)
    else:
        print("\nNo bounced or complained emails found!")
