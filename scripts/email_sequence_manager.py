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
        self.from_email = f'Best AI Apps <hello@{self.domain}>'
        
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
            body_html += f'<p style="margin: 0 0 20px 0; color: #333333; font-size: 16px; line-height: 1.8; font-weight: 400;">{paragraph}</p>'
        
        # Add CTA if present
        cta_html = ""
        if email_data.get('cta_text') and email_data.get('cta_url'):
            cta_html = f'''
            <tr>
                <td align="center" style="padding: 30px 40px 50px 40px;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                        <tr>
                            <td align="center" style="border-radius: 6px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                <a href="{email_data['cta_url']}" target="_blank" style="display: inline-block; padding: 16px 48px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; letter-spacing: 0.3px;">
                                    {email_data['cta_text']}
                                </a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            '''
        
        # Add key takeaways if present
        takeaways_html = ""
        if email_data.get('key_takeaways'):
            takeaways_items = "".join([f'<tr><td style="padding: 8px 0;"><table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"><tr><td width="20" valign="top" style="color: #667eea; font-size: 18px; font-weight: 700;">·</td><td style="color: #555555; font-size: 15px; line-height: 1.6;">{item}</td></tr></table></td></tr>' for item in email_data['key_takeaways']])
            takeaways_html = f'''
            <tr>
                <td style="padding: 0 40px 30px 40px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8f9fb; border-left: 4px solid #667eea; border-radius: 4px;">
                        <tr>
                            <td style="padding: 24px 28px;">
                                <h3 style="margin: 0 0 16px 0; color: #1a1a2e; font-size: 18px; font-weight: 600;">Key Takeaways</h3>
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                    {takeaways_items}
                                </table>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            '''
        
        html = f'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="IE=edge">
            <title>Best AI Apps</title>
            <!--[if mso]>
            <style type="text/css">
                body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
            </style>
            <![endif]-->
        </head>
        <body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            
            <!-- Outer Table for Email Clients -->
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 0; padding: 0; background-color: #f4f4f4;">
                <tr>
                    <td align="center" style="padding: 40px 20px;">
                        
                        <!-- Main Container -->
                        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            
                            <!-- Header -->
                            <tr>
                                <td align="center" style="padding: 50px 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                    <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700; letter-spacing: -0.5px;">Best AI Apps</h1>
                                    <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.95); font-size: 16px; font-weight: 400;">Discover AI Tools That Transform Your Life</p>
                                </td>
                            </tr>
                            
                            <!-- Content Section -->
                            <tr>
                                <td style="padding: 50px 40px;">
                                    {body_html}
                                </td>
                            </tr>
                            
                            <!-- Key Takeaways -->
                            {takeaways_html}
                            
                            <!-- CTA Section -->
                            {cta_html}
                            
                            <!-- Footer -->
                            <tr>
                                <td style="padding: 40px; background-color: #fafafa; border-top: 1px solid #e8e8e8;">
                                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                        <tr>
                                            <td align="center" style="padding-bottom: 20px;">
                                                <a href="https://bestaiapps.site" style="color: #667eea; text-decoration: none; font-size: 14px; font-weight: 500; margin: 0 12px;">Visit Blog</a>
                                                <span style="color: #ddd; margin: 0 4px;">·</span>
                                                <a href="https://bestaiapps.site/apps/" style="color: #667eea; text-decoration: none; font-size: 14px; font-weight: 500; margin: 0 12px;">All Apps</a>
                                            </td>
                                        </tr>
                                        <tr>
                                            <td align="center" style="padding-top: 10px; color: #999999; font-size: 13px; line-height: 1.6;">
                                                Best AI Apps · Curated AI Tools for Everyone<br>
                                                You're receiving this because you subscribed to Best AI Apps.
                                            </td>
                                        </tr>
                                        <tr>
                                            <td align="center" style="padding-top: 20px;">
                                                <a href="%mailing_list_unsubscribe_url%" style="color: #999999; text-decoration: underline; font-size: 12px;">Unsubscribe</a>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            
                        </table>
                        
                    </td>
                </tr>
            </table>
            
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
