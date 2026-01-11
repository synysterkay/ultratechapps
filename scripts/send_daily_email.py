#!/usr/bin/env python3
"""
Daily Email Campaign Sender
Sends daily AI app highlights to subscribers
"""
import os
import sys
import json
import re
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
        # Personal sender name for higher open rates
        self.from_email = f'Kay from Best AI Apps <hello@{self.domain}>'
        
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
    
    def _get_curiosity_subject(self, app):
        """Generate curiosity-gap subject lines for higher open rates"""
        app_name = app['name']
        subjects = [
            f"This AI tool changed how I {self._get_action(app)}...",
            f"I tested {app_name} for a week. Here's what happened.",
            f"The {self._get_niche(app)} secret nobody's talking about",
            f"Why thousands are switching to this for {self._get_benefit(app)}",
            f"I wish I knew about {app_name} sooner (here's why)",
            f"Stop struggling with {self._get_pain(app)} — try this",
            f"The tool that's replacing traditional {self._get_niche(app)} methods",
            f"What {app_name} does that others can't",
        ]
        # Rotate subjects based on day
        day_of_year = datetime.now().timetuple().tm_yday
        return subjects[day_of_year % len(subjects)]
    
    def _get_action(self, app):
        """Get action verb based on app type"""
        desc = app.get('description', '').lower()
        if 'note' in desc or 'meeting' in desc: return 'take notes'
        if 'relationship' in desc or 'dating' in desc: return 'approach relationships'
        if 'weight' in desc or 'health' in desc: return 'track health'
        if 'predict' in desc or 'soccer' in desc: return 'make predictions'
        if 'write' in desc or 'essay' in desc: return 'write'
        if 'crypto' in desc or 'trading' in desc: return 'analyze markets'
        return 'work'
    
    def _get_niche(self, app):
        """Get niche based on app type"""
        desc = app.get('description', '').lower()
        if 'note' in desc or 'meeting' in desc: return 'productivity'
        if 'relationship' in desc or 'dating' in desc: return 'dating'
        if 'weight' in desc or 'dog' in desc: return 'pet care'
        if 'predict' in desc or 'soccer' in desc: return 'sports prediction'
        if 'write' in desc or 'essay' in desc: return 'writing'
        if 'crypto' in desc: return 'crypto'
        if 'volume' in desc or 'sound' in desc: return 'audio'
        return 'AI tools'
    
    def _get_benefit(self, app):
        """Get primary benefit"""
        desc = app.get('description', '').lower()
        if 'note' in desc: return 'capturing ideas'
        if 'relationship' in desc: return 'finding love'
        if 'weight' in desc: return 'pet health'
        if 'predict' in desc: return 'winning predictions'
        if 'write' in desc: return 'better writing'
        if 'crypto' in desc: return 'smart trading'
        return 'better results'
    
    def _get_pain(self, app):
        """Get pain point"""
        desc = app.get('description', '').lower()
        if 'note' in desc: return 'scattered notes'
        if 'relationship' in desc: return 'dating struggles'
        if 'weight' in desc: return 'pet weight issues'
        if 'predict' in desc: return 'wrong predictions'
        if 'write' in desc: return 'writer\'s block'
        if 'crypto' in desc: return 'bad trades'
        return 'inefficiency'
    
    def _generate_email_html(self, app, subscriber_email):
        """Generate HTML email content"""
        app_name = app['name']
        description = app.get('description', '')
        
        # Create landing page URL
        slug = app_name.lower().replace(':', '-').replace(' ', '-')
        slug = re.sub(r'-+', '-', slug).strip('-')  # Replace multiple dashes
        landing_page_url = f"https://bestaiapps.site/apps/{slug}/"
        
        # Create download button pointing to landing page
        download_button = f'''
        <a href="{landing_page_url}" style="display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 15px 30px; text-decoration: none; border-radius: 50px; margin: 10px 5px; font-weight: 600; text-align: center;">
            🚀 Learn More & Download
        </a>
        '''
        
        # Get story hook based on app type
        story_hooks = {
            'productivity': "Last week, I spent 3 hours trying to find a note I took in a meeting. Three. Hours.",
            'relationships': "My friend texted me last night: 'I think I'm dating a narcissist.' I sent her one app.",
            'wellness': "My dog's vet visit last month was a wake-up call. He needed to lose weight, fast.",
            'entertainment': "I lost a Reddit video I'd been searching for. It was deleted. Gone forever.",
            'finance': "I watched my crypto portfolio drop 40% in a day. I was making emotional decisions.",
            'lifestyle': "I couldn't hear my podcast in the car. Even at max volume. So frustrating.",
            'default': "I've tested dozens of AI apps. Most are forgettable. But this one is different."
        }
        
        # Determine category
        desc_lower = description.lower()
        if 'note' in desc_lower or 'meeting' in desc_lower:
            story = story_hooks['productivity']
        elif 'relationship' in desc_lower or 'dating' in desc_lower or 'girlfriend' in desc_lower or 'boyfriend' in desc_lower:
            story = story_hooks['relationships']
        elif 'weight' in desc_lower or 'dog' in desc_lower or 'health' in desc_lower:
            story = story_hooks['wellness']
        elif 'download' in desc_lower or 'reddit' in desc_lower or 'video' in desc_lower:
            story = story_hooks['entertainment']
        elif 'crypto' in desc_lower or 'trading' in desc_lower:
            story = story_hooks['finance']
        elif 'volume' in desc_lower or 'sound' in desc_lower or 'audio' in desc_lower:
            story = story_hooks['lifestyle']
        else:
            story = story_hooks['default']
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2d3748; max-width: 600px; margin: 0 auto; padding: 40px 20px; background: #ffffff;">
            
            <!-- Personal Greeting with Story Hook -->
            <div style="margin-bottom: 30px;">
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #4a5568;">Hey there,</p>
                
                <!-- Story Hook -->
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    {story}
                </p>
                
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    Then I found <strong>{app_name}</strong>.
                </p>
                
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    It does something simple but powerful: <strong>{description.lower().replace('AI-powered ', '').replace('AI ', '')}</strong>.
                </p>
                
                <!-- Social Proof with Urgency -->
                <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-left: 4px solid #667eea; padding: 15px 20px; margin: 25px 0; border-radius: 4px;">
                    <p style="margin: 0; font-size: 15px; color: #4a5568; line-height: 1.6;">
                        ⭐⭐⭐⭐⭐ <strong>Rated 4.8</strong> by 50,000+ users<br>
                        <span style="color: #0369a1; font-size: 14px; font-weight: 600;">Free while in early access (won't last forever)</span>
                    </p>
                </div>
                
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    The setup takes literally 30 seconds. No credit card. No account creation.
                </p>
                
                <p style="margin: 0 0 30px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">
                    Just download, open, and see the difference.
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
            
            <p style="margin: 0 0 25px 0; font-size: 15px; color: #4a5568;">
                Talk soon,<br>
                <strong style="color: #2d3748;">Kay</strong>
            </p>
            
            <!-- P.S. Line - Most Read Part! -->
            <div style="margin: 30px 0; padding: 15px 20px; background: #fffbeb; border-radius: 8px; border: 1px solid #fcd34d;">
                <p style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.6;">
                    <strong>P.S.</strong> I almost forgot — they're running a promo where the premium features are unlocked for free. Not sure how long that'll last, but <a href="{landing_page_url}" style="color: #b45309; font-weight: 600;">might be worth grabbing while you can</a>.
                </p>
            </div>
            
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
        
        # Get curiosity-gap subject line for higher open rates
        subject = self._get_curiosity_subject(app)
        
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
