#!/usr/bin/env python3
"""
Import emails from Excel file to Mailgun mailing list
Safely adds new subscribers without disrupting running campaigns
"""
import openpyxl
import requests
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration - uses environment variables
API_KEY = os.getenv('MAILGUN_API_KEY')
DOMAIN = os.getenv('MAILGUN_DOMAIN', 'bestaiapps.site')
MAILING_LIST = f'subscribers@{DOMAIN}'
EXCEL_FILE = '25k Kickstarter users email list.xlsx'
MAX_WORKERS = 20  # Reduced to avoid rate limiting

def is_valid_email(email):
    """Basic email validation"""
    if not email or not isinstance(email, str):
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def get_existing_emails():
    """Get all existing subscriber emails"""
    print("📥 Fetching existing subscribers...")
    existing = set()
    page_url = f'https://api.mailgun.net/v3/lists/{MAILING_LIST}/members/pages'
    
    while page_url:
        response = requests.get(
            page_url,
            auth=('api', API_KEY),
            params={'limit': 100}
        )
        
        if response.status_code != 200:
            print(f"❌ Error fetching members: {response.text}")
            break
        
        data = response.json()
        for member in data.get('items', []):
            existing.add(member['address'].lower())
        
        # Get next page
        paging = data.get('paging', {})
        page_url = paging.get('next') if paging.get('next') != page_url else None
    
    print(f"   Found {len(existing)} existing subscribers")
    return existing

def read_excel_emails():
    """Read emails from Excel file"""
    print(f"📊 Reading emails from {EXCEL_FILE}...")
    emails = []
    
    wb = openpyxl.load_workbook(EXCEL_FILE, read_only=True)
    sheet = wb.active
    
    for row in sheet.iter_rows(min_row=2, values_only=True):  # Skip header
        if row and row[0]:
            email = str(row[0]).strip().lower()
            if is_valid_email(email):
                emails.append(email)
    
    wb.close()
    print(f"   Found {len(emails)} valid emails in Excel")
    return emails

def add_single_subscriber(email):
    """Add a single subscriber"""
    try:
        response = requests.post(
            f'https://api.mailgun.net/v3/lists/{MAILING_LIST}/members',
            auth=('api', API_KEY),
            data={
                'address': email,
                'vars': json.dumps({'emails_received': 0, 'source': 'kickstarter_import'}),
                'subscribed': 'yes',
                'upsert': 'no'
            },
            timeout=10
        )
        return response.status_code == 200, email
    except Exception as e:
        return False, email

def main():
    print("=" * 60)
    print("📧 Email Import Script (Individual Add)")
    print("=" * 60)
    
    # Get existing subscribers
    existing_emails = get_existing_emails()
    
    # Read Excel emails
    excel_emails = read_excel_emails()
    
    # Find new emails (not already subscribed)
    new_emails = [e for e in excel_emails if e not in existing_emails]
    duplicates = len(excel_emails) - len(new_emails)
    
    print(f"\n📊 Summary:")
    print(f"   Excel emails: {len(excel_emails)}")
    print(f"   Already subscribed: {duplicates}")
    print(f"   New to add: {len(new_emails)}")
    
    if not new_emails:
        print("\n✅ No new emails to add!")
        return
    
    print(f"\n🚀 Adding {len(new_emails)} subscribers with {MAX_WORKERS} parallel workers...")
    print(f"   Estimated time: ~{len(new_emails) // (MAX_WORKERS * 5)} minutes")
    
    added = 0
    failed = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(add_single_subscriber, email): email for email in new_emails}
        
        for i, future in enumerate(as_completed(futures)):
            success, email = future.result()
            if success:
                added += 1
            else:
                failed += 1
            
            # Progress update every 500
            if (i + 1) % 500 == 0 or i + 1 == len(new_emails):
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                remaining = (len(new_emails) - i - 1) / rate if rate > 0 else 0
                print(f"   Progress: {i+1}/{len(new_emails)} ({added} added, {failed} failed) - ETA: {remaining/60:.1f} min")
    
    print(f"\n" + "=" * 60)
    print(f"✅ Import Complete!")
    print(f"   Successfully added: {added}")
    print(f"   Failed/Duplicates: {failed}")
    elapsed = time.time() - start_time
    print(f"   Time taken: {elapsed/60:.1f} minutes")
    print("=" * 60)
    
    # Verify final count
    print("\n🔍 Verifying final count...")
    response = requests.get(
        f'https://api.mailgun.net/v3/lists/{MAILING_LIST}',
        auth=('api', API_KEY)
    )
    if response.status_code == 200:
        count = response.json().get('list', {}).get('members_count', 'unknown')
        print(f"   Mailgun reports: {count} total subscribers")

if __name__ == '__main__':
    main()
