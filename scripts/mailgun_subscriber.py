#!/usr/bin/env python3
"""
Mailgun Subscriber Management
Add subscribers to mailing list via API
"""
import os
import sys
import requests
from datetime import datetime

class MailgunSubscriber:
    def __init__(self):
        self.api_key = os.getenv('MAILGUN_API_KEY')
        self.domain = os.getenv('MAILGUN_DOMAIN', 'sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org')
        self.base_url = 'https://api.mailgun.net/v3'
        self.mailing_list = f'subscribers@{self.domain}'
        
        if not self.api_key:
            raise ValueError("MAILGUN_API_KEY not found in environment")
    
    def add_subscriber(self, email, name=None):
        """Add email to mailing list"""
        url = f'{self.base_url}/lists/{self.mailing_list}/members'
        
        data = {
            'address': email,
            'subscribed': 'yes',
            'upsert': 'yes',  # Update if exists
        }
        
        if name:
            data['name'] = name
        
        # Add metadata
        data['vars'] = {
            'subscribed_at': datetime.now().isoformat(),
            'source': 'bestaiapps.site',
            'status': 'active'
        }
        
        try:
            response = requests.post(
                url,
                auth=('api', self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                print(f"✅ Added subscriber: {email}")
                return {'success': True, 'email': email}
            else:
                print(f"❌ Error: {response.status_code} - {response.text}")
                return {'success': False, 'error': response.text}
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_subscribers(self):
        """Get all subscribers from mailing list"""
        url = f'{self.base_url}/lists/{self.mailing_list}/members/pages'
        
        try:
            response = requests.get(
                url,
                auth=('api', self.api_key),
                params={'subscribed': 'yes', 'limit': 1000}
            )
            
            if response.status_code == 200:
                data = response.json()
                subscribers = data.get('items', [])
                print(f"📊 Total subscribers: {len(subscribers)}")
                return subscribers
            else:
                print(f"❌ Error fetching subscribers: {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            return []
    
    def create_mailing_list(self):
        """Create mailing list if it doesn't exist"""
        url = f'{self.base_url}/lists'
        
        data = {
            'address': self.mailing_list,
            'name': 'Best AI Apps Newsletter',
            'description': 'Subscribers to Best AI Apps newsletter',
            'access_level': 'members'
        }
        
        try:
            response = requests.post(
                url,
                auth=('api', self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                print(f"✅ Mailing list created: {self.mailing_list}")
                return True
            elif 'already exists' in response.text.lower():
                print(f"✅ Mailing list already exists: {self.mailing_list}")
                return True
            else:
                print(f"❌ Error creating list: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            return False

if __name__ == '__main__':
    # CLI usage
    if len(sys.argv) < 2:
        print("Usage: python mailgun_subscriber.py <command> [args]")
        print("Commands:")
        print("  add <email> [name]  - Add subscriber")
        print("  list                - List all subscribers")
        print("  create              - Create mailing list")
        sys.exit(1)
    
    manager = MailgunSubscriber()
    command = sys.argv[1]
    
    if command == 'add':
        email = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else None
        result = manager.add_subscriber(email, name)
        print(result)
    
    elif command == 'list':
        subscribers = manager.get_subscribers()
        for sub in subscribers:
            print(f"  - {sub['address']} ({sub.get('name', 'No name')})")
    
    elif command == 'create':
        manager.create_mailing_list()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
