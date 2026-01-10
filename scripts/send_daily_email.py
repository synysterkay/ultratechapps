#!/usr/bin/env python3
"""
Daily Email Campaign Sender
Sends daily AI app highlights to subscribers
"""
import os
import sys
import json
import random
import requests
from datetime import datetime
from pathlib import Path

class DailyEmailCampaign:
    def __init__(self):
        self.api_key = os.getenv('MAILGUN_API_KEY')
        self.domain = os.getenv('MAILGUN_DOMAIN', 'bestaiapps.site')
        self.base_url = 'https://api.mailgun.net/v3'
        self.mailing_list = f'subscribers@{self.domain}'
        self.from_email = f'Best AI Apps <newsletter@{self.domain}>'
        
        if not self.api_key:
            raise ValueError("MAILGUN_API_KEY not found in environment")
        
        # Load apps
        self.apps = self._load_apps()
    
    def _load_apps(self):
        """Load apps from apps.json"""
        apps_file = Path(__file__).parent.parent / "apps.json"
        with open(apps_file, 'r') as f:
            return json.load(f)
    
    def _select_daily_app(self):
        """Select app of the day (rotate based on day of year)"""
        day_of_year = datetime.now().timetuple().tm_yday
        app_index = day_of_year % len(self.apps)
        return self.apps[app_index]
    
    def _generate_email_html(self, app, subscriber_email):
        """Generate HTML email content"""
        app_name = app['name']
        description = app.get('description', '')
        google_play = app.get('google_play_url', '')
        app_store = app.get('app_store_url', '')
        
        # Create download buttons HTML
        download_buttons = ""
        if google_play:
            download_buttons += f'''
            <a href="{google_play}" style="display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 15px 30px; text-decoration: none; border-radius: 50px; margin: 10px 5px; font-weight: 600;">
                📱 Download on Google Play
            </a>
            '''
        
        if app_store:
            download_buttons += f'''
            <a href="{app_store}" style="display: inline-block; background: linear-gradient(135deg, #000000, #434343); color: white !important; padding: 15px 30px; text-decoration: none; border-radius: 50px; margin: 10px 5px; font-weight: 600;">
                🍎 Download on App Store
            </a>
            '''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            
            <!-- Header -->
            <div style="text-align: center; padding: 30px 0; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 10px; margin-bottom: 30px;">
                <h1 style="color: white; margin: 0; font-size: 28px;">🚀 Best AI Apps</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Your Daily AI App Pick</p>
            </div>
            
            <!-- Featured App -->
            <div style="background: #f8f9fa; border-radius: 10px; padding: 30px; margin-bottom: 30px;">
                <h2 style="color: #1a1a2e; margin-top: 0; font-size: 24px;">{app_name}</h2>
                <p style="color: #666; font-size: 16px; line-height: 1.8;">{description}</p>
                
                <!-- Download Buttons -->
                <div style="text-align: center; margin: 30px 0;">
                    {download_buttons}
                </div>
            </div>
            
            <!-- Value Section -->
            <div style="padding: 20px 0; border-top: 2px solid #eee; margin-top: 30px;">
                <h3 style="color: #1a1a2e; font-size: 20px;">💡 Why This App Matters</h3>
                <p style="color: #666; line-height: 1.8;">
                    In 2026, AI-powered apps are transforming how we work, learn, and connect. 
                    {app_name} represents the cutting edge of mobile AI technology, designed to 
                    make your life easier and more productive.
                </p>
            </div>
            
            <!-- CTA Section -->
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 10px; padding: 25px; text-align: center; margin: 30px 0;">
                <h3 style="color: white; margin: 0 0 15px 0; font-size: 20px;">Ready to Transform Your Workflow?</h3>
                <p style="color: rgba(255,255,255,0.9); margin: 0 0 20px 0;">Join thousands of users already using {app_name}</p>
                {download_buttons}
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; padding: 30px 0; color: #999; font-size: 14px; border-top: 1px solid #eee; margin-top: 30px;">
                <p style="margin: 5px 0;">
                    <a href="https://bestaiapps.site" style="color: #667eea; text-decoration: none;">Visit Our Blog</a> · 
                    <a href="https://bestaiapps.site/apps/" style="color: #667eea; text-decoration: none;">All Apps</a>
                </p>
                <p style="margin: 15px 0 5px 0; color: #aaa; font-size: 12px;">
                    You're receiving this because you subscribed to Best AI Apps newsletter.
                </p>
                <p style="margin: 5px 0;">
                    <a href="%mailing_list_unsubscribe_url%" style="color: #999; text-decoration: none; font-size: 12px;">Unsubscribe</a>
                </p>
            </div>
            
        </body>
        </html>
        '''
        
        return html
    
    def send_daily_email(self):
        """Send daily email to all subscribers"""
        # Select app of the day
        app = self._select_daily_app()
        print(f"📱 Today's app: {app['name']}")
        
        # Get subject line
        subject = f"🚀 Daily AI Pick: {app['name']}"
        
        # Send to mailing list
        url = f'{self.base_url}/{self.domain}/messages'
        
        # Generate HTML (with placeholder for personalization)
        html_content = self._generate_email_html(app, '%recipient%')
        
        data = {
            'from': self.from_email,
            'to': self.mailing_list,
            'subject': subject,
            'html': html_content,
            'o:tag': ['daily-campaign', 'app-highlight'],
            'o:tracking': 'yes',
            'o:tracking-clicks': 'yes',
            'o:tracking-opens': 'yes'
        }
        
        try:
            response = requests.post(
                url,
                auth=('api', self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Email sent successfully!")
                print(f"📧 Message ID: {result.get('id')}")
                return {'success': True, 'message_id': result.get('id')}
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                return {'success': False, 'error': response.text}
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_test_email(self, test_email):
        """Send test email to specific address"""
        app = self._select_daily_app()
        print(f"📱 Sending test for: {app['name']}")
        
        url = f'{self.base_url}/{self.domain}/messages'
        
        html_content = self._generate_email_html(app, test_email)
        
        data = {
            'from': self.from_email,
            'to': test_email,
            'subject': f"🚀 [TEST] Daily AI Pick: {app['name']}",
            'html': html_content,
            'o:tag': ['test-email']
        }
        
        try:
            response = requests.post(
                url,
                auth=('api', self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                print(f"✅ Test email sent to {test_email}")
                return True
            else:
                print(f"❌ Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            return False

if __name__ == '__main__':
    campaign = DailyEmailCampaign()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Send test email
        test_email = sys.argv[2] if len(sys.argv) > 2 else 'test@example.com'
        campaign.send_test_email(test_email)
    else:
        # Send to all subscribers
        campaign.send_daily_email()
