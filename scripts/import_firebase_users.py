#!/usr/bin/env python3
"""
Import Firebase Auth users to Mailgun mailing list
Maps app users to niches and adds them as engaged subscribers
"""

import os
import sys
import json
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Mailgun configuration
MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
MAILING_LIST = f"subscribers@{MAILGUN_DOMAIN}"

# Map your apps to niches (update this based on your apps)
APP_TO_NICHE = {
    'Smart Notes': 'productivity',
    'Ai Girlfriend': 'relationships',
    'Red Flag Scanner': 'relationships',
    'Fresh Start': 'relationships',
    'SoulPlan': 'relationships',
    'Ai Boyfriend': 'relationships',
    'PupShape': 'wellness',
    'Reelit Downloader': 'entertainment',
    'LoveStory AI': 'entertainment',
    'Crypto AI': 'finance',
    'Volume Booster': 'lifestyle',
    'Predictify': 'sports',
    'Kinbound': 'personal_growth'
}

def get_firebase_users():
    """
    Fetch users from Firebase Auth
    This uses Firebase Admin SDK
    """
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        
        # Initialize Firebase (you'll need to provide your service account key)
        # Option 1: Use service account JSON file
        # cred = credentials.Certificate('path/to/serviceAccountKey.json')
        
        # Option 2: Use default credentials (if running on cloud with proper IAM)
        cred = credentials.ApplicationDefault()
        
        firebase_admin.initialize_app(cred)
        
        users = []
        page = auth.list_users()
        
        while page:
            for user in page.users:
                if user.email:  # Only include users with email
                    users.append({
                        'email': user.email,
                        'uid': user.uid,
                        'created_at': user.user_metadata.creation_timestamp / 1000,  # Convert to seconds
                        'display_name': user.display_name
                    })
            
            # Get next page
            page = page.get_next_page() if page.has_next_page else None
        
        return users
    
    except ImportError:
        print("❌ Firebase Admin SDK not installed.")
        print("📦 Install it: pip install firebase-admin")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error fetching Firebase users: {e}")
        sys.exit(1)

def import_from_json(json_file):
    """
    Import users from JSON file
    Expected format: [{"email": "user@example.com", "app": "Smart Notes"}, ...]
    """
    try:
        with open(json_file, 'r') as f:
            users = json.load(f)
        
        if not isinstance(users, list):
            print("❌ JSON file must contain an array of user objects")
            sys.exit(1)
        
        return users
    
    except FileNotFoundError:
        print(f"❌ File not found: {json_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        sys.exit(1)

def add_to_mailgun(email, niche, app_name=None, existing_user=True):
    """
    Add user to Mailgun mailing list
    Mark as 'engaged' since they're existing app users
    """
    url = f"https://api.mailgun.net/v3/lists/{MAILING_LIST}/members"
    
    metadata = {
        'subscribed_at': datetime.utcnow().isoformat(),
        'source': 'firebase_import',
        'status': 'active',
        'niche': niche,
        'sequence_stage': 'value' if existing_user else 'welcome',  # Skip welcome for existing users
        'welcome_day': None,
        'last_email_sent': None,
        'emails_received': 0,
        'opens': 0,
        'clicks': 0
    }
    
    if app_name:
        metadata['app_used'] = app_name
    
    data = {
        'address': email,
        'subscribed': 'yes',
        'vars': json.dumps(metadata)
    }
    
    response = requests.post(
        url,
        auth=('api', MAILGUN_API_KEY),
        data=data
    )
    
    return response

def main():
    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        print("❌ Missing environment variables:")
        print("   MAILGUN_API_KEY and MAILGUN_DOMAIN must be set")
        sys.exit(1)
    
    print("🔥 Firebase to Mailgun Importer")
    print("=" * 50)
    
    # Determine import method
    import_method = input("\nImport from:\n1. Firebase Auth (requires Firebase SDK setup)\n2. JSON file\nChoice (1/2): ").strip()
    
    users_to_import = []
    
    if import_method == '1':
        print("\n📡 Fetching users from Firebase Auth...")
        firebase_users = get_firebase_users()
        print(f"✅ Found {len(firebase_users)} users in Firebase")
        
        # Ask for app-to-user mapping
        print("\n🗺️  App Mapping:")
        print("Available apps:", ', '.join(APP_TO_NICHE.keys()))
        default_app = input("Enter default app name (or leave blank to skip users without app): ").strip()
        
        for user in firebase_users:
            users_to_import.append({
                'email': user['email'],
                'app': default_app if default_app else None
            })
    
    elif import_method == '2':
        json_file = input("\n📄 Enter JSON file path: ").strip()
        users_to_import = import_from_json(json_file)
        print(f"✅ Loaded {len(users_to_import)} users from {json_file}")
    
    else:
        print("❌ Invalid choice")
        sys.exit(1)
    
    # Confirm before importing
    print(f"\n📊 Ready to import {len(users_to_import)} users")
    print(f"📬 Mailing list: {MAILING_LIST}")
    
    # Show sample mapping
    if users_to_import:
        sample = users_to_import[0]
        sample_app = sample.get('app')
        sample_niche = APP_TO_NICHE.get(sample_app, 'general') if sample_app else 'general'
        print(f"\n📋 Sample mapping:")
        print(f"   Email: {sample['email']}")
        print(f"   App: {sample_app or 'None'}")
        print(f"   Niche: {sample_niche}")
    
    confirm = input("\nProceed with import? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Import cancelled")
        sys.exit(0)
    
    # Import users
    print("\n🚀 Importing users...")
    success_count = 0
    error_count = 0
    duplicate_count = 0
    
    for i, user in enumerate(users_to_import, 1):
        email = user.get('email')
        app_name = user.get('app')
        
        if not email:
            print(f"⚠️  Skipping user {i}: No email")
            error_count += 1
            continue
        
        # Map app to niche
        niche = 'general'
        if app_name and app_name in APP_TO_NICHE:
            niche = APP_TO_NICHE[app_name]
        
        # Add to Mailgun
        response = add_to_mailgun(email, niche, app_name)
        
        if response.status_code == 200:
            success_count += 1
            if i % 10 == 0:
                print(f"   ✓ Imported {i}/{len(users_to_import)} users...")
        elif 'already exists' in response.text.lower():
            duplicate_count += 1
        else:
            error_count += 1
            print(f"   ✗ Error for {email}: {response.text}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Import Summary:")
    print(f"   ✅ Successfully imported: {success_count}")
    print(f"   ⚠️  Already subscribed: {duplicate_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📧 Total processed: {len(users_to_import)}")
    print("\n✨ Import complete!")
    print(f"   Users will start receiving value emails (skipping welcome sequence)")
    print(f"   First emails sent by GitHub Actions at 9 AM UTC tomorrow")

if __name__ == "__main__":
    main()
