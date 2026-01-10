#!/usr/bin/env python3
"""
Format Firebase Auth exports from multiple projects into single import file
"""

import json
import os
import glob

# Map export filenames to app names
FILE_TO_APP = {
    'smart_notes_users.json': 'Smart Notes',
    'ai_girlfriend_users.json': 'Ai Girlfriend',
    'red_flag_scanner_users.json': 'Red Flag Scanner',
    'fresh_start_users.json': 'Fresh Start',
    'soulplan_users.json': 'SoulPlan',
    'pupshape_users.json': 'PupShape',
    'predictify_users.json': 'Predictify'
}

def main():
    print("🔄 Formatting Firebase exports...")
    print("=" * 50)
    
    all_users = []
    exports_dir = 'firebase_exports'
    
    if not os.path.exists(exports_dir):
        print(f"❌ Directory not found: {exports_dir}")
        print("   Run: bash scripts/export_all_firebase_users.sh first")
        return
    
    # Process each export file
    for export_file in glob.glob(f'{exports_dir}/*.json'):
        filename = os.path.basename(export_file)
        app_name = FILE_TO_APP.get(filename, 'Unknown App')
        
        print(f"\n📱 Processing: {app_name}")
        
        try:
            with open(export_file, 'r') as f:
                data = json.load(f)
            
            # Firebase CLI format: {"users": [...]}
            users = data.get('users', [])
            
            count = 0
            for user in users:
                email = user.get('email')
                if email:
                    all_users.append({
                        'email': email,
                        'app': app_name
                    })
                    count += 1
            
            print(f"   ✅ Found {count} users with emails")
        
        except Exception as e:
            print(f"   ⚠️  Error: {e}")
    
    if not all_users:
        print("\n❌ No users found in exports")
        return
    
    # Remove duplicates (keep first occurrence)
    seen_emails = set()
    unique_users = []
    duplicates = 0
    
    for user in all_users:
        if user['email'] not in seen_emails:
            seen_emails.add(user['email'])
            unique_users.append(user)
        else:
            duplicates += 1
    
    # Save formatted file
    output_file = 'firebase_users_formatted.json'
    
    with open(output_file, 'w') as f:
        json.dump(unique_users, f, indent=2)
    
    print("\n" + "=" * 50)
    print(f"✅ Formatting complete!")
    print(f"\n📊 Statistics:")
    print(f"   Total users: {len(all_users)}")
    print(f"   Unique users: {len(unique_users)}")
    print(f"   Duplicates removed: {duplicates}")
    print(f"\n💾 Output file: {output_file}")
    
    # Show sample by app
    print(f"\n📋 Users by app:")
    app_counts = {}
    for user in unique_users:
        app = user['app']
        app_counts[app] = app_counts.get(app, 0) + 1
    
    for app, count in sorted(app_counts.items()):
        print(f"   {app}: {count} users")
    
    print(f"\n🚀 Next step: Import to Mailgun")
    print(f"   python3 scripts/import_firebase_users.py")
    print(f"   Choose option 2 (JSON file)")
    print(f"   Enter: {output_file}")

if __name__ == "__main__":
    main()
