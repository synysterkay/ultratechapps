#!/usr/bin/env python3
"""
Email Sequence Manager
Orchestrates welcome sequences, value emails, and promotional campaigns
Based on subscriber journey stage and timing
"""
import os
import sys
import json
import re
import requests
import time
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
        
        # Rate limiting configuration
        self.batch_size = int(os.getenv('EMAIL_BATCH_SIZE', '50'))  # Emails per batch
        self.batch_delay = int(os.getenv('EMAIL_BATCH_DELAY', '3600'))  # Seconds between batches (default 1 hour)
        self.email_delay = int(os.getenv('EMAIL_DELAY', '2'))  # Seconds between individual emails
        
        if not self.api_key:
            raise ValueError("MAILGUN_API_KEY not found in environment")
        
        # Initialize components
        self.subscriber_manager = MailgunSubscriber()
        self.email_generator = EmailGenerator()
        
        # State file for tracking progress
        self.state_file = Path(__file__).parent.parent / "cache" / "email_campaign_state.json"
        self.state_file.parent.mkdir(exist_ok=True)
        
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
        """Generate HTML email from AI-generated content - Personal marketing style"""
        
        app_name = app_data['name']
        
        # Create landing page URL
        slug = app_name.lower().replace(':', '-').replace(' ', '-')
        slug = re.sub(r'-+', '-', slug).strip('-')  # Replace multiple dashes
        landing_page_url = f"https://bestaiapps.site/apps/{slug}/"
        
        # Build body paragraphs
        body_html = ""
        for paragraph in email_data['body_paragraphs']:
            body_html += f'<p style="margin: 0 0 20px 0; font-size: 16px; color: #2d3748; line-height: 1.7;">{paragraph}</p>'
        
        # Add key takeaways if present
        takeaways_html = ""
        if email_data.get('key_takeaways'):
            items = "".join([f'✓ {item}<br>' for item in email_data['key_takeaways']])
            takeaways_html = f'''
            <div style="margin: 35px 0 40px 0; padding-top: 25px; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0 0 15px 0; font-size: 15px; color: #4a5568; line-height: 1.7;">
                    <strong>Quick takeaways:</strong>
                </p>
                <p style="margin: 0 0 10px 0; font-size: 15px; color: #4a5568; line-height: 1.7;">
                    {items}
                </p>
            </div>
            '''
        
        # CTA button
        cta_text = email_data.get('cta_text', f'Try {app_name} Free')
        cta_url = email_data.get('cta_url', landing_page_url)
        
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
                <p style="margin: 0 0 20px 0; font-size: 16px; color: #4a5568;">Hey there,</p>
                
                <!-- AI-Generated Body Content -->
                {body_html}
                
                <!-- Social Proof Box -->
                <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-left: 4px solid #667eea; padding: 15px 20px; margin: 25px 0; border-radius: 4px;">
                    <p style="margin: 0; font-size: 15px; color: #4a5568; line-height: 1.6;">
                        ⭐⭐⭐⭐⭐ <strong>Rated 4.8</strong> by 50,000+ users<br>
                        <span style="color: #0369a1; font-size: 14px; font-weight: 600;">Free while in early access (won't last forever)</span>
                    </p>
                </div>
            </div>
            
            <!-- Single Clear CTA -->
            <div style="text-align: center; margin: 35px 0;">
                <a href="{cta_url}" style="display: inline-block; background: #667eea; color: #ffffff; padding: 16px 40px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.25);">
                    {cta_text} →
                </a>
                <p style="margin: 15px 0 0 0; font-size: 13px; color: #a0aec0;">
                    Click to see how it works · No signup required
                </p>
            </div>
            
            <!-- Key Takeaways -->
            {takeaways_html}
            
            <p style="margin: 0 0 25px 0; font-size: 15px; color: #4a5568;">
                Talk soon,<br>
                <strong style="color: #2d3748;">Kay</strong>
            </p>
            
            <!-- P.S. Line - Most Read Part -->
            <div style="margin: 30px 0; padding: 15px 20px; background: #fffbeb; border-radius: 8px; border: 1px solid #fcd34d;">
                <p style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.6;">
                    <strong>P.S.</strong> I almost forgot — they're running a promo where premium features are unlocked for free. Not sure how long that'll last, but <a href="{landing_page_url}" style="color: #b45309; font-weight: 600;">might be worth grabbing while you can</a>.
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
    
    def send_to_subscriber(self, subscriber, email_data, app_data, sequence_info):
        """Send email to individual subscriber"""
        
        email_address = subscriber['address']
        html_content = self._generate_email_html(email_data, app_data)
        
        url = f'{self.base_url}/{self.domain}/messages'
        
        # Generate unique Message-ID to prevent threading
        import uuid
        unique_id = str(uuid.uuid4())
        
        data = {
            'from': self.from_email,
            'to': email_address,
            'subject': email_data['subject'],
            'html': html_content,
            'o:tag': [f"sequence-{sequence_info['sequence']}", email_data.get('niche', 'general')],
            'o:tracking': 'yes',
            'o:tracking-clicks': 'yes',
            'o:tracking-opens': 'yes',
            'h:Message-ID': f'<{unique_id}@bestaiapps.site>'
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
    
    def _load_campaign_state(self):
        """Load campaign state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    # Check if state is from today
                    if state.get('date') == datetime.now().strftime('%Y-%m-%d'):
                        return state
            except:
                pass
        return {'date': datetime.now().strftime('%Y-%m-%d'), 'processed': [], 'sent_count': 0}
    
    def _save_campaign_state(self, state):
        """Save campaign state to file"""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def run_daily_campaign(self):
        """Main campaign runner - processes all subscribers with rate limiting"""
        
        print("🚀 Starting daily email campaign...")
        print(f"⚙️  Rate limiting: {self.batch_size} emails per batch, {self.batch_delay}s between batches")
        print()
        
        # Load campaign state
        state = self._load_campaign_state()
        already_processed = set(state.get('processed', []))
        sent_count = state.get('sent_count', 0)
        
        # Get all subscribers
        subscribers = self.subscriber_manager.get_subscribers()
        
        if not subscribers:
            print("ℹ️ No subscribers found")
            return
        
        # Filter out already processed subscribers
        pending_subscribers = [s for s in subscribers if s['address'] not in already_processed]
        
        if not pending_subscribers:
            print(f"✅ All {len(subscribers)} subscribers already processed today")
            print(f"📊 Total emails sent today: {sent_count}")
            return
        
        print(f"📋 Total subscribers: {len(subscribers)}")
        print(f"✅ Already processed: {len(already_processed)}")
        print(f"⏳ Pending: {len(pending_subscribers)}")
        print()
        
        skipped_count = 0
        batch_count = 0
        
        # Process in batches
        for i in range(0, len(pending_subscribers), self.batch_size):
            batch = pending_subscribers[i:i + self.batch_size]
            batch_count += 1
            batch_sent = 0
            
            print(f"\n{'='*60}")
            print(f"📦 Batch {batch_count}: Processing {len(batch)} subscribers")
            print(f"{'='*60}")
            
            for subscriber in batch:
                email_address = subscriber['address']
                
                # Check if should send email
                should_send, sequence_info = self._should_send_email(subscriber)
                
                if not should_send:
                    skipped_count += 1
                    already_processed.add(email_address)
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
                    already_processed.add(email_address)
                    continue
                
                print(f"   Subject: {email_data['subject']}")
                
                # Send email
                if self.send_to_subscriber(subscriber, email_data, app_data, sequence_info):
                    sent_count += 1
                    batch_sent += 1
                    print(f"   ✅ Email sent ({sent_count} total today)")
                
                # Mark as processed
                already_processed.add(email_address)
                
                # Save state after each email
                state = {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'processed': list(already_processed),
                    'sent_count': sent_count
                }
                self._save_campaign_state(state)
                
                # Delay between individual emails
                if self.email_delay > 0:
                    time.sleep(self.email_delay)
            
            print(f"\n✅ Batch {batch_count} complete: {batch_sent} emails sent")
            
            # Check if there are more batches
            remaining = len(pending_subscribers) - (i + self.batch_size)
            if remaining > 0:
                print(f"\n⏸️  Rate limit: Waiting {self.batch_delay} seconds before next batch...")
                print(f"   Remaining subscribers: {remaining}")
                print(f"   Next batch will start at: {(datetime.now() + timedelta(seconds=self.batch_delay)).strftime('%H:%M:%S UTC')}")
                
                # For GitHub Actions, we exit here and let the next run continue
                if os.getenv('GITHUB_ACTIONS'):
                    print(f"\n🔄 GitHub Actions: Exiting to resume in next scheduled run")
                    print(f"   Progress saved: {sent_count} emails sent, {len(already_processed)} processed")
                    break
                else:
                    # For local runs, actually wait
                    time.sleep(self.batch_delay)
        
        print()
        print("=" * 60)
        print(f"📊 Campaign Summary")
        print(f"   Emails sent: {sent_count}")
        print(f"   Subscribers skipped: {skipped_count}")
        print(f"   Total processed: {len(already_processed)}")
        print(f"   Total subscribers: {len(subscribers)}")
        if len(already_processed) < len(subscribers):
            print(f"   ⏳ Will resume in next run: {len(subscribers) - len(already_processed)} remaining")
        else:
            print(f"   ✅ All subscribers processed!")
        print("=" * 60)


def main():
    """Run the email sequence manager"""
    
    manager = EmailSequenceManager()
    manager.run_daily_campaign()


if __name__ == '__main__':
    main()
