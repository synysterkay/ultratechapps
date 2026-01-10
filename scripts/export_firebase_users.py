#!/usr/bin/env python3
"""
Export Firebase Auth users to JSON format for Mailgun import
"""

import json
import sys
import os

def export_with_firebase_admin():
    """
    Export users using Firebase Admin SDK
    """
    try:
        import firebase_admin
        from firebase_admin import credentials, auth
        
        print("🔧 Firebase Admin SDK Export")
        print("=" * 50)
        
        # Ask for credentials
        cred_path = input("\n📄 Enter path to Firebase service account JSON key: ").strip()
        
        if not os.path.exists(cred_path):
            print(f"❌ File not found: {cred_path}")
            print("\n💡 To get your service account key:")
            print("   1. Go to Firebase Console → Project Settings")
            print("   2. Click 'Service Accounts' tab")
            print("   3. Click 'Generate new private key'")
            return None
        
        # Initialize Firebase
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        
        print("\n📡 Fetching users from Firebase Auth...")
        
        users_export = []
        page = auth.list_users()
        total = 0
        
        while page:
            for user in page.users:
                if user.email:  # Only include users with email
                    total += 1
                    users_export.append({
                        'email': user.email,
                        'app': None,  # You'll need to map this manually
                        'display_name': user.display_name,
                        'uid': user.uid
                    })
            
            # Get next page
            page = page.get_next_page() if page.has_next_page else None
            
            if total % 100 == 0:
                print(f"   Fetched {total} users...")
        
        print(f"✅ Fetched {total} users with emails")
        return users_export
    
    except ImportError:
        print("❌ Firebase Admin SDK not installed")
        print("📦 Install: pip install firebase-admin")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def export_with_cli():
    """
    Guide user to export with Firebase CLI
    """
    print("\n🔧 Firebase CLI Export")
    print("=" * 50)
    print("\n1. Install Firebase CLI (if not installed):")
    print("   npm install -g firebase-tools")
    print("\n2. Login to Firebase:")
    print("   firebase login")
    print("\n3. Export users:")
    print("   firebase auth:export users.json --format=JSON")
    print("\n4. The file 'users.json' will be created")
    print("\n📄 Then manually format it to:")
    print('   [{"email": "user@example.com", "app": "AppName"}, ...]')
    
    return None

def manual_format():
    """
    Help user format an existing Firebase export
    """
    print("\n📝 Format Existing Export")
    print("=" * 50)
    
    input_file = input("\nEnter Firebase export JSON file path: ").strip()
    
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return None
    
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        # Firebase CLI export format: {"users": [...]}
        if isinstance(data, dict) and 'users' in data:
            users = data['users']
        elif isinstance(data, list):
            users = data
        else:
            print("❌ Unexpected JSON format")
            return None
        
        print(f"✅ Found {len(users)} users")
        
        # Ask for default app
        print("\n🗺️  Available apps:")
        apps = ['Smart Notes', 'Ai Girlfriend', 'Red Flag Scanner', 'Fresh Start', 
                'SoulPlan', 'Ai Boyfriend', 'PupShape', 'Reelit Downloader', 
                'LoveStory AI', 'Crypto AI', 'Volume Booster', 'Predictify', 'Kinbound']
        for i, app in enumerate(apps, 1):
            print(f"   {i}. {app}")
        
        default_app = input("\nEnter default app name (or number, or leave blank): ").strip()
        
        # Map number to app name
        if default_app.isdigit() and 1 <= int(default_app) <= len(apps):
            default_app = apps[int(default_app) - 1]
        elif not default_app:
            default_app = None
        
        # Format for import
        formatted_users = []
        for user in users:
            email = user.get('email')
            if email:
                formatted_users.append({
                    'email': email,
                    'app': default_app
                })
        
        print(f"✅ Formatted {len(formatted_users)} users")
        return formatted_users
    
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None

def main():
    print("🔥 Firebase Users Export Tool")
    print("=" * 50)
    
    print("\nChoose export method:")
    print("1. Firebase Admin SDK (Python - requires service account key)")
    print("2. Firebase CLI (command line - simpler)")
    print("3. Format existing Firebase export file")
    
    choice = input("\nChoice (1/2/3): ").strip()
    
    users = None
    
    if choice == '1':
        users = export_with_firebase_admin()
    elif choice == '2':
        export_with_cli()
        print("\n✅ Follow the instructions above")
        print("   Then run this script again with option 3 to format the export")
        return
    elif choice == '3':
        users = manual_format()
    else:
        print("❌ Invalid choice")
        return
    
    if not users:
        print("\n❌ No users exported")
        return
    
    # Save to file
    output_file = 'firebase_users_export.json'
    
    with open(output_file, 'w') as f:
        json.dump(users, f, indent=2)
    
    print(f"\n✅ Exported to: {output_file}")
    print(f"   Total users: {len(users)}")
    
    # Show sample
    if users:
        print(f"\n📋 Sample (first 3 users):")
        for user in users[:3]:
            print(f"   - {user['email']} → {user.get('app', 'No app')}")
    
    print(f"\n🚀 Next steps:")
    print(f"   1. Review {output_file} and update app names if needed")
    print(f"   2. Run: python3 scripts/import_firebase_users.py")
    print(f"   3. Choose option 2 (JSON file)")
    print(f"   4. Enter: {output_file}")

if __name__ == "__main__":
    main()
