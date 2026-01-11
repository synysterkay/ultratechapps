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
        self.from_email = f'Best AI Apps <hello@{self.domain}>'
        
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
        
        # Create landing page URL
        slug = app_name.lower().replace(':', '-').replace(' ', '-').replace('--', '-').strip('-')
        landing_page_url = f"https://bestaiapps.site/apps/{slug}/"
        
        # Create download button pointing to landing page
        download_button = f'''
        <a href="{landing_page_url}" style="display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 15px 30px; text-decoration: none; border-radius: 50px; margin: 10px 5px; font-weight: 600; text-align: center;">
            🚀 Learn More & Download
        </a>
        '''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2d3748; max-width: 600px; margin: 0 auto; padding: 40px 20px; background: #ffffff;">
            
            <!-- Personal Greeting -->
            <div style="margin-bottom: 30px;">
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #4a5568;">Hey there 👋</p>
                
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    Quick question: <strong>What if you could {description.lower().replace('AI-powered ', '').replace('AI ', '')}?</strong>
                </p>
                
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    I just tested <strong>{app_name}</strong> and honestly... I'm impressed.
                </p>
                
                <!-- Social Proof -->
                <div style="background: #f7fafc; border-left: 4px solid #667eea; padding: 15px 20px; margin: 25px 0; border-radius: 4px;">
                    <p style="margin: 0; font-size: 15px; color: #4a5568; line-height: 1.6;">
                        ⭐⭐⭐⭐⭐ <strong>Rated 4.7+</strong> by thousands of users<br>
                        <span style="color: #718096; font-size: 14px;">Join people already transforming their workflow with AI</span>
                    </p>
                </div>
                
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    It's free to start, takes 30 seconds to set up, and you'll see results immediately.
                </p>
                
                <p style="margin: 0 0 30px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    No credit card. No BS. Just results.
                </p>
            </div>
            
            <!-- Single Clear CTA -->
            <div style="text-align: center; margin: 35px 0;">
                <a href="{landing_page_url}" style="display: inline-block; background: #667eea; color: #ffffff; padding: 16px 40px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.25);">
                    Try {app_name} Free →
                </a>
                <p style="margin: 15px 0 0 0; font-size: 13px; color: #a0aec0;">
                    Click to see how it works · No signup required to preview
                </p>
            </div>
            
            <!-- Simple Value Reminder -->
            <div style="margin: 35px 0 40px 0; padding-top: 25px; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0 0 15px 0; font-size: 15px; color: #4a5568; line-height: 1.7;">
                    <strong>Why people love it:</strong>
                </p>
                <p style="margin: 0 0 10px 0; font-size: 15px; color: #4a5568; line-height: 1.7;">
                    ✓ Works on iOS & Android<br>
                    ✓ Free to download and try<br>
                    ✓ No learning curve - intuitive design<br>
                    ✓ AI does the heavy lifting for you
                </p>
            </div>
            
            <p style="margin: 0 0 30px 0; font-size: 15px; color: #4a5568; line-height: 1.7;">
                Give it 5 minutes. You'll see why everyone's talking about it.
            </p>
            
            <p style="margin: 0; font-size: 15px; color: #4a5568;">
                – The Best AI Apps Team
            </p>
            
            <!-- Minimal Footer -->
            <div style="margin-top: 50px; padding-top: 25px; border-top: 1px solid #e2e8f0; text-align: center;">
                <p style="margin: 0 0 10px 0; font-size: 13px; color: #a0aec0;">
                    <a href="https://bestaiapps.site" style="color: #667eea; text-decoration: none;">Blog</a> · 
                    <a href="https://bestaiapps.site/apps/" style="color: #667eea; text-decoration: none;">All Apps</a>
                </p>
                <p style="margin: 0 0 15px 0; font-size: 12px; color: #cbd5e0; line-height: 1.6;">
                    Best AI Apps · Józefa Łepkowskiego 5, Kraków, Poland<br>
                    You subscribed to discover the best AI tools.
                </p>
                <p style="margin: 0;">
                    <a href="%mailing_list_unsubscribe_url%" style="color: #cbd5e0; text-decoration: none; font-size: 11px;">Unsubscribe</a>
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
