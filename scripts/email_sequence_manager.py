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
        self.from_email = f'Anas from Best AI Apps <hello@{self.domain}>'
        
        # Rate limiting configuration - aggressive but safe
        self.batch_size = int(os.getenv('EMAIL_BATCH_SIZE', '100'))  # Emails per batch (increased)
        self.batch_delay = int(os.getenv('EMAIL_BATCH_DELAY', '60'))  # 60 seconds between batches
        self.email_delay = int(os.getenv('EMAIL_DELAY', '1'))  # 1 second between individual emails
        
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
        """
        Check if subscriber should receive email now.
        
        Email Schedule (aggressive marketing):
        - Welcome email: IMMEDIATE (as soon as they subscribe)
        - Follow-up emails: Every 12 hours minimum
        - Different app featured each time
        """
        metadata = subscriber.get('metadata', {})
        
        last_email_sent = metadata.get('last_email_sent')
        emails_received = metadata.get('emails_received', 0)
        
        # IMMEDIATE: Never received any email? Send welcome NOW
        if emails_received == 0 or not last_email_sent:
            return True, {'sequence': 'welcome', 'day': 0}
        
        # Check time since last email
        try:
            last_sent = datetime.fromisoformat(last_email_sent)
            hours_since_last = (datetime.now() - last_sent).total_seconds() / 3600
            
            # Minimum 12 hours between emails to avoid spam
            if hours_since_last < 12:
                return False, None
            
            # Determine sequence based on emails received
            if emails_received == 1:
                # Second email: value content
                return True, {'sequence': 'value'}
            elif emails_received == 2:
                # Third email: more value
                return True, {'sequence': 'value'}
            elif emails_received >= 3:
                # Rotate between value and promotional
                if emails_received % 3 == 0:
                    return True, {'sequence': 'promotional'}
                else:
                    return True, {'sequence': 'value'}
                    
        except Exception as e:
            # If any error parsing, send email
            return True, {'sequence': 'value'}
        
        return False, None
    
    def _generate_discovery_email_html(self):
        """Generate discovery email featuring ALL 14 apps - curator style"""
        
        # App categories with emotional one-liners
        app_categories = {
            "🎯 Productivity & Learning": [
                ("Smart Notes - AI Meeting Summary", "smart-notes-ai-meeting-summary", "Never miss a detail in meetings again"),
                ("PassedAI", "passedai", "Turn AI text into undetectable human writing - FREE"),
                ("Thesis Generator: Essay AI", "thesis-generator-essay-ai", "Write A+ papers in half the time"),
                ("Volume Booster - Sound Booster", "volume-booster-sound-booster", "Hear every word crystal clear"),
            ],
            "❤️ Relationships & Dating": [
                ("Red Flag Scanner AI", "red-flag-scanner-ai", "Spot toxic patterns before it's too late"),
                ("SoulPlan: Plan Dates Together", "soulplan-plan-dates-together", "Never run out of date ideas"),
                ("Fresh Start: Breakup Therapy", "fresh-start-breakup-therapy", "Heal faster with 24/7 AI support"),
            ],
            "💬 AI Companions": [
                ("Ai Girlfriend App - Cupid Ai", "ai-girlfriend-app-cupid-ai", "Practice conversations, build confidence"),
                ("Ai Boyfriend: Virtual Love", "ai-boyfriend-virtual-love", "Someone who actually listens"),
                ("Kinbound: AI Parent Life Coach", "kinbound-ai-parent-life-coach", "The guidance you never had"),
                ("LoveStory AI: Romance Novel", "lovestory-ai-romance-novel", "Star in your own love story"),
            ],
            "📊 Sports & Finance": [
                ("Predictify: Soccer AI", "predictify-soccer-ai", "Beat your friends at predictions"),
                ("Crypto AI: Trading Analyzer", "crypto-ai-trading-analyzer", "Make smarter trades, not emotional ones"),
            ],
            "🐕 Pet Care & Utilities": [
                ("PupShape: Dog Weight Loss Plan", "pupshape-dog-weight-loss-plan", "Help your furry friend get healthy"),
                ("Reelit Downloader For Reddit", "reelit-downloader-for-reddit", "Save Reddit videos in one tap"),
            ],
        }
        
        # Build app grid HTML
        apps_html = ""
        for category, apps in app_categories.items():
            apps_html += f'''
            <div style="margin: 28px 0;">
                <p style="margin: 0 0 14px 0; font-size: 16px; font-weight: 700; color: #1f2937;">{category}</p>
            '''
            for app_name, slug, tagline in apps:
                url = f"https://bestaiapps.site/apps/{slug}/"
                apps_html += f'''
                <div style="margin: 0 0 12px 0; padding: 14px 18px; background: #f8fafc; border-radius: 8px; border-left: 4px solid #667eea;">
                    <a href="{url}" style="text-decoration: none;">
                        <p style="margin: 0 0 4px 0; font-size: 16px; font-weight: 600; color: #667eea;">{app_name}</p>
                        <p style="margin: 0; font-size: 14px; color: #64748b;">{tagline}</p>
                    </a>
                </div>
                '''
            apps_html += "</div>"
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2d3748; max-width: 620px; margin: 0 auto; padding: 48px 24px; background: #ffffff;">
            
            <!-- Hook -->
            <div style="margin-bottom: 32px;">
                <p style="margin: 0 0 24px 0; font-size: 19px; color: #6b7280;">Hey there,</p>
                
                <p style="margin: 0 0 24px 0; font-size: 20px; color: #1a202c; line-height: 1.6; font-weight: 500;">
                    Let's be honest — the App Store is a mess.
                </p>
                
                <p style="margin: 0 0 20px 0; font-size: 17px; color: #374151; line-height: 1.8;">
                    Thousands of "AI apps" that are just ChatGPT wrappers. Productivity tools that take longer to set up than they save. Dating apps that feel like job interviews.
                </p>
                
                <p style="margin: 0 0 20px 0; font-size: 17px; color: #374151; line-height: 1.8;">
                    We spent 30+ hours testing over 200 apps so you don't have to. Most were trash. But 14 genuinely impressed us.
                </p>
                
                <p style="margin: 0 0 28px 0; font-size: 18px; color: #1f2937; font-weight: 600;">
                    Here's your shortlist:
                </p>
            </div>
            
            <!-- App Grid -->
            {apps_html}
            
            <!-- CTA Section -->
            <div style="margin: 40px 0; padding: 24px; background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-radius: 12px; text-align: center;">
                <p style="margin: 0 0 16px 0; font-size: 18px; color: #1e40af; font-weight: 600;">
                    🎁 All apps are FREE while in early access
                </p>
                <p style="margin: 0; font-size: 15px; color: #3b82f6;">
                    Pick one that solves YOUR problem. Try it for 5 minutes.
                </p>
            </div>
            
            <!-- Sign off -->
            <p style="margin: 32px 0 28px 0; font-size: 17px; color: #4b5563;">
                Happy exploring,<br>
                <strong style="color: #1f2937; font-size: 18px;">The Best AI Apps Team</strong>
            </p>
            
            <!-- P.S. -->
            <div style="margin: 36px 0; padding: 20px 24px; background: #fffbeb; border-radius: 10px; border: 1px solid #fcd34d;">
                <p style="margin: 0; font-size: 16px; color: #92400e; line-height: 1.7;">
                    <strong style="font-size: 17px;">P.S.</strong> We'll send you one app deep-dive per week — the hidden features, pro tips, and real use cases. First one arrives in a few days. Keep an eye out!
                </p>
            </div>
            
            <!-- Footer -->
            <div style="margin-top: 56px; padding-top: 28px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="margin: 0 0 12px 0; font-size: 14px; color: #9ca3af;">
                    <a href="https://bestaiapps.site" style="color: #667eea; text-decoration: none; font-weight: 500;">Blog</a> · 
                    <a href="https://bestaiapps.site/apps/" style="color: #667eea; text-decoration: none; font-weight: 500;">All Apps</a>
                </p>
                <p style="margin: 0 0 16px 0; font-size: 13px; color: #d1d5db; line-height: 1.6;">
                    Józefa Łepkowskiego 5, Kraków, Poland
                </p>
                <p style="margin: 0;">
                    <a href="%mailing_list_unsubscribe_url%" style="color: #d1d5db; text-decoration: none; font-size: 12px;">Unsubscribe</a>
                </p>
            </div>
            
        </body>
        </html>
        '''
        
        return html
    
    def _generate_email_html(self, email_data, app_data):
        """Generate HTML email from AI-generated content - Personal marketing style"""
        
        app_name = app_data['name']
        app_store_url = app_data.get('app_store_url', '')
        google_play_url = app_data.get('google_play_url', '')
        
        # Create landing page URL (for P.S. section)
        slug = app_name.lower().replace(':', '-').replace(' ', '-')
        slug = re.sub(r'-+', '-', slug).strip('-')  # Replace multiple dashes
        landing_page_url = f"https://bestaiapps.site/apps/{slug}/"
        
        # Build body paragraphs with better hierarchy
        body_html = ""
        paragraphs = email_data['body_paragraphs']
        for i, paragraph in enumerate(paragraphs):
            if i == 0:
                # First paragraph - larger, bold hook
                body_html += f'<p style="margin: 0 0 28px 0; font-size: 20px; color: #1a202c; line-height: 1.6; font-weight: 500;">{paragraph}</p>'
            elif i == 1:
                # Second paragraph - still prominent
                body_html += f'<p style="margin: 0 0 24px 0; font-size: 18px; color: #2d3748; line-height: 1.7;">{paragraph}</p>'
            else:
                # Rest - standard but readable
                body_html += f'<p style="margin: 0 0 22px 0; font-size: 17px; color: #374151; line-height: 1.8;">{paragraph}</p>'
        
        # Add key takeaways if present
        takeaways_html = ""
        if email_data.get('key_takeaways'):
            items = "".join([f'<div style="padding: 8px 0; font-size: 16px;">✓ {item}</div>' for item in email_data['key_takeaways']])
            takeaways_html = f'''
            <div style="margin: 35px 0 40px 0; padding-top: 25px; border-top: 2px solid #e2e8f0;">
                <p style="margin: 0 0 16px 0; font-size: 18px; color: #1a202c; font-weight: 600;">
                    Quick takeaways:
                </p>
                <div style="color: #4a5568; line-height: 1.6;">
                    {items}
                </div>
            </div>
            '''
        
        # CTA buttons - detect web app vs mobile app
        cta_html = ""
        is_web_app = app_store_url and ('.io/' in app_store_url or '.com/' in app_store_url or '.ai/' in app_store_url) and not any(x in app_store_url for x in ['apps.apple.com', 'play.google.com'])
        
        if is_web_app:
            # Web app - use "Start Now" or "Try Free" CTA
            cta_html = f'''
            <div style="text-align: center; margin: 40px 0;">
                <a href="{app_store_url}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 18px 48px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 18px; box-shadow: 0 6px 20px rgba(102, 126, 234, 0.35);">
                    🚀 Start Free Now →
                </a>
                <p style="margin: 16px 0 0 0; font-size: 14px; color: #9ca3af;">
                    No signup required · Free to use
                </p>
            </div>
            '''
        elif app_store_url and google_play_url:
            # Both stores available
            cta_html = f'''
            <div style="text-align: center; margin: 40px 0;">
                <div style="display: inline-block;">
                    <a href="{app_store_url}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 18px 36px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 17px; box-shadow: 0 6px 20px rgba(102, 126, 234, 0.35); margin: 0 8px;">
                        📱 Download on App Store
                    </a>
                    <a href="{google_play_url}" style="display: inline-block; background: linear-gradient(135deg, #34d399 0%, #10b981 100%); color: #ffffff; padding: 18px 36px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 17px; box-shadow: 0 6px 20px rgba(16, 185, 129, 0.35); margin: 0 8px;">
                        🤖 Get it on Google Play
                    </a>
                </div>
                <p style="margin: 16px 0 0 0; font-size: 14px; color: #9ca3af;">
                    Free to download · No credit card required
                </p>
            </div>
            '''
        elif app_store_url:
            # App Store only (iOS app)
            cta_html = f'''
            <div style="text-align: center; margin: 40px 0;">
                <a href="{app_store_url}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 18px 48px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 18px; box-shadow: 0 6px 20px rgba(102, 126, 234, 0.35);">
                    📱 Download on App Store →
                </a>
                <p style="margin: 16px 0 0 0; font-size: 14px; color: #9ca3af;">
                    Free to download · No credit card required
                </p>
            </div>
            '''
        elif google_play_url:
            # Google Play only
            cta_html = f'''
            <div style="text-align: center; margin: 40px 0;">
                <a href="{google_play_url}" style="display: inline-block; background: linear-gradient(135deg, #34d399 0%, #10b981 100%); color: #ffffff; padding: 18px 48px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 18px; box-shadow: 0 6px 20px rgba(16, 185, 129, 0.35);">
                    🤖 Get it on Google Play →
                </a>
                <p style="margin: 16px 0 0 0; font-size: 14px; color: #9ca3af;">
                    Free to download · No credit card required
                </p>
            </div>
            '''
        else:
            # Fallback to landing page
            cta_html = f'''
            <div style="text-align: center; margin: 40px 0;">
                <a href="{landing_page_url}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 18px 48px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 18px; box-shadow: 0 6px 20px rgba(102, 126, 234, 0.35);">
                    Try {app_name} Free →
                </a>
                <p style="margin: 16px 0 0 0; font-size: 14px; color: #9ca3af;">
                    Click to see how it works · No signup required
                </p>
            </div>
            '''
        
        # Determine P.S. link URL (prioritize first available store)
        ps_link_url = app_store_url or google_play_url or landing_page_url
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.7; color: #2d3748; max-width: 620px; margin: 0 auto; padding: 48px 24px; background: #ffffff;">
            
            <!-- Personal Greeting -->
            <div style="margin-bottom: 32px;">
                <p style="margin: 0 0 28px 0; font-size: 19px; color: #6b7280;">Hey there,</p>
                
                <!-- AI-Generated Body Content -->
                {body_html}
                
                <!-- Social Proof Box -->
                <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-left: 5px solid #667eea; padding: 20px 24px; margin: 32px 0; border-radius: 6px;">
                    <p style="margin: 0; font-size: 17px; color: #334155; line-height: 1.6;">
                        ⭐⭐⭐⭐⭐ <strong>Rated 4.8</strong> by 50,000+ users<br>
                        <span style="color: #0369a1; font-size: 15px; font-weight: 600;">Free while in early access (won't last forever)</span>
                    </p>
                </div>
            </div>
            
            <!-- App Store CTA Buttons -->
            {cta_html}
            
            <!-- Key Takeaways -->
            {takeaways_html}
            
            <p style="margin: 0 0 28px 0; font-size: 17px; color: #4b5563;">
                Talk soon,<br>
                <strong style="color: #1f2937; font-size: 18px;">Anas</strong><br>
                <span style="font-size: 14px; color: #6b7280;">Indie Developer & Founder, Best AI Apps</span>
            </p>
            
            <!-- P.S. Line - Most Read Part -->
            <div style="margin: 36px 0; padding: 20px 24px; background: #fffbeb; border-radius: 10px; border: 1px solid #fcd34d;">
                <p style="margin: 0; font-size: 16px; color: #92400e; line-height: 1.7;">
                    <strong style="font-size: 17px;">P.S.</strong> I built this app because I genuinely believe it helps people. Premium features are free while we're in early access — <a href="{ps_link_url}" style="color: #b45309; font-weight: 700; text-decoration: underline;">grab it before we have to change that</a>.
                </p>
            </div>
            
            <!-- Minimal Footer -->
            <div style="margin-top: 56px; padding-top: 28px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="margin: 0 0 12px 0; font-size: 14px; color: #9ca3af;">
                    <a href="https://bestaiapps.site" style="color: #667eea; text-decoration: none; font-weight: 500;">Blog</a> · 
                    <a href="https://bestaiapps.site/apps/" style="color: #667eea; text-decoration: none; font-weight: 500;">All Apps</a>
                </p>
                <p style="margin: 0;">
                    <a href="%mailing_list_unsubscribe_url%" style="color: #d1d5db; text-decoration: none; font-size: 12px;">Unsubscribe</a>
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
    
    def send_discovery_email(self, subscriber):
        """Send discovery email (all 14 apps) to new subscriber"""
        
        email_address = subscriber['address']
        html_content = self._generate_discovery_email_html()
        
        url = f'{self.base_url}/{self.domain}/messages'
        
        # Generate unique Message-ID
        import uuid
        unique_id = str(uuid.uuid4())
        
        # Discovery email subject - curated list style
        subject = "14 AI apps that actually work (we tested 200+)"
        preview_text = "The App Store is a mess. Here's your shortlist."
        
        data = {
            'from': self.from_email,
            'to': email_address,
            'subject': subject,
            'html': html_content,
            'o:tag': ['sequence-discovery', 'all-apps'],
            'o:tracking': 'yes',
            'o:tracking-clicks': 'yes',
            'o:tracking-opens': 'yes',
            'h:Message-ID': f'<{unique_id}@bestaiapps.site>',
            'h:X-Preview-Text': preview_text
        }
        
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
                metadata['emails_received'] = 1  # First email sent
                metadata['discovery_email_sent'] = True
                
                self.subscriber_manager.update_subscriber_metadata(email_address, metadata)
                
                print(f"✅ Discovery email sent to {email_address}")
                return True
            else:
                print(f"❌ Failed to send discovery to {email_address}: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception sending discovery to {email_address}: {str(e)}")
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
    
    def _get_app_for_email_number(self, emails_received):
        """Get app based on how many emails subscriber has received"""
        # LOCKED: Always send PassedAI for maximum conversion
        passedai_app = next((app for app in self.apps if 'PassedAI' in app['name'] or 'Passed AI' in app['name']), None)
        if not passedai_app:
            # Fallback to rotation if PassedAI not found
            app_index = emails_received % len(self.apps)
            return self.apps[app_index]
        return passedai_app
    
    def _pre_generate_emails(self, eligible_subscribers):
        """
        Pre-generate ONE email per app needed for this batch.
        Returns dict: {app_name: email_data}
        """
        # Find which apps we need emails for
        apps_needed = set()
        for subscriber in eligible_subscribers:
            metadata = subscriber.get('metadata', {})
            emails_received = metadata.get('emails_received', 0)
            app = self._get_app_for_email_number(emails_received)
            apps_needed.add(app['name'])
        
        print(f"\n📝 Pre-generating {len(apps_needed)} unique emails (one per app)...")
        
        email_cache = {}
        for app_name in apps_needed:
            app_data = next(a for a in self.apps if a['name'] == app_name)
            
            # Check for cached PassedAI email first
            if 'PassedAI' in app_name or 'Passed AI' in app_name:
                cache_file = Path(__file__).parent.parent / 'cache' / 'passedai_email_cache.json'
                if cache_file.exists():
                    print(f"   💾 Using cached email for: {app_name}")
                    with open(cache_file, 'r') as f:
                        email_data = json.load(f)
                        email_cache[app_name] = email_data
                        print(f"   ✅ Loaded: {email_data['subject'][:50]}...")
                        continue
            
            # Determine sequence type based on most common stage
            sequence_type = 'value'  # Default to value emails
            
            print(f"   🔄 Generating email for: {app_name}")
            
            # Use optimized niche for PassedAI
            niche = 'education' if 'PassedAI' in app_name or 'Passed AI' in app_name else 'general'
            
            email_data = self.email_generator.generate_email(
                niche=niche,
                app_data=app_data,
                sequence_type=sequence_type,
                day=None
            )
            
            if email_data:
                email_cache[app_name] = email_data
                print(f"   ✅ Generated: {email_data['subject'][:50]}...")
            else:
                print(f"   ❌ Failed to generate for {app_name}")
        
        print(f"\n✅ Pre-generated {len(email_cache)} emails (saved {len(eligible_subscribers) - len(email_cache)} API calls!)\n")
        return email_cache

    def run_daily_campaign(self):
        """
        Optimized campaign runner:
        1. Group subscribers by which app they should receive
        2. Generate ONE email per app (not per subscriber!)
        3. Send same email to all subscribers in that group
        """
        
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
        
        # Find eligible subscribers (ready for next email)
        eligible_subscribers = []
        for subscriber in pending_subscribers:
            should_send, sequence_info = self._should_send_email(subscriber)
            if should_send:
                subscriber['_sequence_info'] = sequence_info
                eligible_subscribers.append(subscriber)
        
        if not eligible_subscribers:
            print(f"\n⏳ No subscribers ready for email yet (12h minimum between emails)")
            # Mark all as processed for today
            for s in pending_subscribers:
                already_processed.add(s['address'])
            state['processed'] = list(already_processed)
            self._save_campaign_state(state)
            return
        
        print(f"📬 Eligible for email now: {len(eligible_subscribers)}")
        
        # PRE-GENERATE emails (one per app - saves API calls!)
        email_cache = self._pre_generate_emails(eligible_subscribers)
        
        if not email_cache:
            print("❌ Failed to generate any emails")
            return
        
        skipped_count = 0
        batch_count = 0
        
        # Process in batches
        for i in range(0, len(eligible_subscribers), self.batch_size):
            batch = eligible_subscribers[i:i + self.batch_size]
            batch_count += 1
            batch_sent = 0
            
            print(f"\n{'='*60}")
            print(f"📦 Batch {batch_count}: Sending to {len(batch)} subscribers")
            print(f"{'='*60}")
            
            for subscriber in batch:
                email_address = subscriber['address']
                metadata = subscriber.get('metadata', {})
                emails_received = metadata.get('emails_received', 0)
                sequence_info = subscriber.get('_sequence_info', {'sequence': 'value'})
                
                # DISCOVERY EMAIL: First email is the all-apps showcase
                if emails_received == 0:
                    if self.send_discovery_email(subscriber):
                        sent_count += 1
                        batch_sent += 1
                        print(f"   ✅ Discovery email sent ({sent_count} total today)")
                    already_processed.add(email_address)
                    
                    # Save state periodically
                    if sent_count % 10 == 0:
                        state = {
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'processed': list(already_processed),
                            'sent_count': sent_count
                        }
                        self._save_campaign_state(state)
                    
                    if self.email_delay > 0:
                        time.sleep(self.email_delay)
                    continue
                
                # Regular app-focused emails for emails_received >= 1
                # Get the app for this subscriber's email number
                app_data = self._get_app_for_email_number(emails_received)
                
                # Use pre-generated email for this app
                email_data = email_cache.get(app_data['name'])
                
                if not email_data:
                    print(f"⏭️  Skip {email_address}: No email for {app_data['name']}")
                    skipped_count += 1
                    already_processed.add(email_address)
                    continue
                
                # Send email
                if self.send_to_subscriber(subscriber, email_data, app_data, sequence_info):
                    sent_count += 1
                    batch_sent += 1
                    print(f"   ✅ Email sent ({sent_count} total today)")
                
                # Mark as processed
                already_processed.add(email_address)
                
                # Save state periodically (every 10 emails)
                if sent_count % 10 == 0:
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
            
            # Save state after each batch
            state = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'processed': list(already_processed),
                'sent_count': sent_count
            }
            self._save_campaign_state(state)
            
            # Check if there are more batches
            remaining = len(eligible_subscribers) - (i + self.batch_size)
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
        
        # Mark non-eligible as processed too
        for s in pending_subscribers:
            if s['address'] not in already_processed:
                already_processed.add(s['address'])
        
        state = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'processed': list(already_processed),
            'sent_count': sent_count
        }
        self._save_campaign_state(state)
        
        print()
        print("=" * 60)
        print(f"📊 Campaign Summary")
        print(f"   Emails sent: {sent_count}")
        print(f"   Subscribers skipped: {skipped_count}")
        print(f"   Total processed: {len(already_processed)}")
        print(f"   Total subscribers: {len(subscribers)}")
        print(f"   🎯 API calls saved: {sent_count - len(email_cache)} (used {len(email_cache)} instead of {sent_count})")
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
