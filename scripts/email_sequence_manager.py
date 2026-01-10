#!/usr/bin/env python3
"""
Email Sequence Manager
Orchestrates welcome sequences, value emails, and promotional campaigns
Based on subscriber journey stage and timing
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from email_generator import EmailGenerator
from mailgun_subscriber import MailgunSubscriber

class EmailSequenceManager:
    def __init__(self):
        self.api_key = os.getenv('MAILGUN_API_KEY')
        self.domain = os.getenv('MAILGUN_DOMAIN', 'bestaiapps.site')
        self.base_url = 'https://api.mailgun.net/v3'
        self.from_email = f'Best AI Apps <newsletter@{self.domain}>'
        
        if not self.api_key:
            raise ValueError("MAILGUN_API_KEY not found in environment")
        
        # Initialize components
        self.subscriber_manager = MailgunSubscriber()
        self.email_generator = EmailGenerator()
        
        # Load apps
        apps_file = Path(__file__).parent.parent / "apps.json"
        with open(apps_file, 'r') as f:
            self.apps = json.load(f)
        
        # Load config
        config_file = Path(__file__).parent.parent / "config" / "email_config.json"
        with open(config_file, 'r') as f:
            self.config = json.load(f)
    
    def _get_subscriber_stage(self, subscriber):
        """Determine subscriber's journey stage"""
        metadata = subscriber.get('metadata', {})
        
        subscribed_at_str = metadata.get('subscribed_at')
        if not subscribed_at_str:
            return 'newcomer'
        
        try:
            subscribed_at = datetime.fromisoformat(subscribed_at_str)
            days_since_signup = (datetime.now() - subscribed_at).days
            
            if days_since_signup <= 7:
                return 'newcomer'
            elif days_since_signup <= 30:
                return 'engaged'
            else:
                return 'loyal'
        except:
            return 'newcomer'
    
    def _should_send_email(self, subscriber):
        """Check if subscriber should receive email today"""
        metadata = subscriber.get('metadata', {})
        
        last_email_sent = metadata.get('last_email_sent')
        sequence_stage = metadata.get('sequence_stage', 'welcome')
        welcome_day = metadata.get('welcome_day', 0)
        
        # New subscribers: Welcome sequence (Day 0, 3, 7)
        if sequence_stage == 'welcome':
            subscribed_at_str = metadata.get('subscribed_at')
            if not subscribed_at_str:
                return False, None
            
            try:
                subscribed_at = datetime.fromisoformat(subscribed_at_str)
                days_since_signup = (datetime.now() - subscribed_at).days
                
                # Day 0: Immediate (within first 24 hours)
                if welcome_day == 0 and days_since_signup == 0:
                    return True, {'sequence': 'welcome', 'day': 0}
                
                # Day 3: Send on day 3
                elif welcome_day <= 0 and days_since_signup == 3:
                    return True, {'sequence': 'welcome', 'day': 3}
                
                # Day 7: Send on day 7 and transition to value sequence
                elif welcome_day <= 3 and days_since_signup == 7:
                    return True, {'sequence': 'welcome', 'day': 7}
                
                # Transition to value sequence after day 7
                elif days_since_signup > 7:
                    # Update subscriber to value sequence
                    metadata['sequence_stage'] = 'value'
                    self.subscriber_manager.update_subscriber_metadata(
                        subscriber['address'],
                        metadata
                    )
                    return False, None
                
            except:
                return False, None
        
        # Value sequence: Every 2 days
        elif sequence_stage == 'value':
            if not last_email_sent:
                return True, {'sequence': 'value'}
            
            try:
                last_sent = datetime.fromisoformat(last_email_sent)
                days_since_last = (datetime.now() - last_sent).days
                
                if days_since_last >= 2:
                    return True, {'sequence': 'value'}
            except:
                return True, {'sequence': 'value'}
        
        # Promotional sequence: Once per week
        elif sequence_stage == 'promotional':
            if not last_email_sent:
                return True, {'sequence': 'promotional'}
            
            try:
                last_sent = datetime.fromisoformat(last_email_sent)
                days_since_last = (datetime.now() - last_sent).days
                
                if days_since_last >= 7:
                    return True, {'sequence': 'promotional'}
            except:
                return True, {'sequence': 'promotional'}
        
        return False, None
    
    def _select_app_for_subscriber(self, subscriber):
        """Select appropriate app based on subscriber's niche"""
        metadata = subscriber.get('metadata', {})
        niche = metadata.get('niche', 'general')
        
        # Get apps for this niche
        niche_config = self.config['niches'].get(niche)
        
        if niche_config and 'apps' in niche_config:
            matching_apps = [app for app in self.apps if app['name'] in niche_config['apps']]
            if matching_apps:
                # Rotate through niche apps
                emails_received = metadata.get('emails_received', 0)
                app_index = emails_received % len(matching_apps)
                return matching_apps[app_index], niche
        
        # Fallback: general rotation
        emails_received = metadata.get('emails_received', 0)
        app_index = emails_received % len(self.apps)
        return self.apps[app_index], 'general'
    
    def _generate_email_html(self, email_data, app_data):
        """Generate HTML email from AI-generated content"""
        
        body_html = ""
        for i, paragraph in enumerate(email_data['body_paragraphs']):
            body_html += f'<p style="color: #333; line-height: 1.8; margin: 20px 0;">{paragraph}</p>'
        
        # Add CTA if present
        cta_html = ""
        if email_data.get('cta_text') and email_data.get('cta_url'):
            cta_html = f'''
            <div style="text-align: center; margin: 40px 0;">
                <a href="{email_data['cta_url']}" style="display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2); color: white !important; padding: 15px 40px; text-decoration: none; border-radius: 50px; font-weight: 600;">
                    {email_data['cta_text']}
                </a>
            </div>
            '''
        
        # Add key takeaways if present
        takeaways_html = ""
        if email_data.get('key_takeaways'):
            takeaways_items = "".join([f"<li style='margin: 10px 0;'>{item}</li>" for item in email_data['key_takeaways']])
            takeaways_html = f'''
            <div style="background: #f8f9fa; border-left: 4px solid #667eea; padding: 20px; margin: 30px 0;">
                <h3 style="color: #1a1a2e; margin-top: 0; font-size: 18px;">📌 Key Takeaways</h3>
                <ul style="color: #666; line-height: 1.8; margin: 10px 0; padding-left: 20px;">
                    {takeaways_items}
                </ul>
            </div>
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
                <h1 style="color: white; margin: 0; font-size: 28px;">Best AI Apps</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Discover AI Tools That Matter</p>
            </div>
            
            <!-- Email Content -->
            <div style="padding: 20px 0;">
                {body_html}
            </div>
            
            <!-- Key Takeaways -->
            {takeaways_html}
            
            <!-- CTA -->
            {cta_html}
            
            <!-- Footer -->
            <div style="text-align: center; padding: 30px 0; color: #999; font-size: 14px; border-top: 1px solid #eee; margin-top: 40px;">
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
    
    def send_to_subscriber(self, subscriber, email_data, app_data, sequence_info):
        """Send email to individual subscriber"""
        
        email_address = subscriber['address']
        html_content = self._generate_email_html(email_data, app_data)
        
        url = f'{self.base_url}/{self.domain}/messages'
        
        data = {
            'from': self.from_email,
            'to': email_address,
            'subject': email_data['subject'],
            'html': html_content,
            'o:tag': [f"sequence-{sequence_info['sequence']}", email_data.get('niche', 'general')],
            'o:tracking': 'yes',
            'o:tracking-clicks': 'yes',
            'o:tracking-opens': 'yes'
        }
        
        # Add preview text if available
        if email_data.get('preview_text'):
            data['h:X-Preview-Text'] = email_data['preview_text']
        
        try:
            response = requests.post(
                url,
                auth=('api', self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                # Update subscriber metadata
                metadata = subscriber.get('metadata', {})
                metadata['last_email_sent'] = datetime.now().isoformat()
                metadata['emails_received'] = metadata.get('emails_received', 0) + 1
                
                # Update welcome day if in welcome sequence
                if sequence_info['sequence'] == 'welcome':
                    metadata['welcome_day'] = sequence_info.get('day', 0)
                
                self.subscriber_manager.update_subscriber_metadata(email_address, metadata)
                
                print(f"✅ Sent to {email_address}")
                return True
            else:
                print(f"❌ Failed to send to {email_address}: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception sending to {email_address}: {str(e)}")
            return False
    
    def run_daily_campaign(self):
        """Main campaign runner - processes all subscribers"""
        
        print("🚀 Starting daily email campaign...")
        print()
        
        # Get all subscribers
        subscribers = self.subscriber_manager.get_subscribers()
        
        if not subscribers:
            print("ℹ️ No subscribers found")
            return
        
        sent_count = 0
        skipped_count = 0
        
        for subscriber in subscribers:
            email_address = subscriber['address']
            
            # Check if should send email
            should_send, sequence_info = self._should_send_email(subscriber)
            
            if not should_send:
                skipped_count += 1
                continue
            
            print(f"\n📧 Processing: {email_address}")
            print(f"   Stage: {self._get_subscriber_stage(subscriber)}")
            print(f"   Sequence: {sequence_info['sequence']}")
            
            # Select app for subscriber
            app_data, niche = self._select_app_for_subscriber(subscriber)
            print(f"   App: {app_data['name']}")
            print(f"   Niche: {niche}")
            
            # Generate email content
            day = sequence_info.get('day') if sequence_info['sequence'] == 'welcome' else None
            email_data = self.email_generator.generate_email(
                niche=niche,
                app_data=app_data,
                sequence_type=sequence_info['sequence'],
                day=day
            )
            
            if not email_data:
                print(f"   ❌ Failed to generate email content")
                continue
            
            print(f"   Subject: {email_data['subject']}")
            
            # Send email
            if self.send_to_subscriber(subscriber, email_data, app_data, sequence_info):
                sent_count += 1
        
        print()
        print("=" * 60)
        print(f"📊 Campaign Complete")
        print(f"   Emails sent: {sent_count}")
        print(f"   Subscribers skipped: {skipped_count}")
        print(f"   Total subscribers: {len(subscribers)}")
        print("=" * 60)


def main():
    """Run the email sequence manager"""
    
    manager = EmailSequenceManager()
    manager.run_daily_campaign()


if __name__ == '__main__':
    main()
