#!/usr/bin/env python3
"""
App Retention Email System
Main orchestrator: Loads Firebase users per app, sends 7-email retention
funnel via Gmail SMTP. Tracks progress per user to never send duplicates.

Usage:
  python scripts/app_retention_emailer.py              # Send next batch
  python scripts/app_retention_emailer.py --generate   # Pre-generate all emails
  python scripts/app_retention_emailer.py --status      # Show campaign status
  python scripts/app_retention_emailer.py --refresh     # Re-export Firebase users
"""
import os
import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from firebase_user_loader import FirebaseUserLoader, FIREBASE_APPS
from retention_email_generator import RetentionEmailGenerator, APP_CONTEXT
from gmail_sender import GmailSender


class AppRetentionEmailer:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.state_file = self.base_dir / 'cache' / 'retention_state.json'
        self.state_file.parent.mkdir(exist_ok=True)
        
        self.firebase_loader = FirebaseUserLoader()
        self.email_generator = RetentionEmailGenerator()
        
        # Load tracking state
        self.state = self._load_state()
    
    # ─── STATE MANAGEMENT ──────────────────────────────────
    
    def _load_state(self):
        """
        Load state tracking which users got which emails.
        State structure: {
            "users": {
                "user@email.com": {
                    "app": "App Name",
                    "emails_sent": 3,          # How many of the 7 they've received
                    "last_email_sent": "2026-02-19T...",
                    "first_email_at": "2026-02-15T...",
                }
            },
            "daily_stats": {
                "2026-02-19": {"sent": 45, "failed": 2}
            }
        }
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"users": {}, "daily_stats": {}}
    
    def _save_state(self):
        """Persist state to disk"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    # ─── EMAIL HTML TEMPLATE ───────────────────────────────
    
    def _build_html(self, email_data, app_info):
        """Build beautiful HTML email from generated content"""
        
        app_name = email_data.get('app_name', app_info['name'])
        cta_text = email_data.get('cta_text', f'Open {app_name}')
        
        # Build body paragraphs
        body_html = ""
        paragraphs = email_data.get('body_paragraphs', [])
        for i, p in enumerate(paragraphs):
            # Convert \n to <br> for line breaks within paragraphs
            p_html = p.replace('\n', '<br>')
            if i == 0:
                body_html += f'<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;">{p_html}</p>'
            elif 'P.S.' in p or 'P.S' in p:
                body_html += f'<div style="margin:32px 0 0;padding:16px 20px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;"><p style="margin:0;font-size:16px;color:#92400e;line-height:1.7;">{p_html}</p></div>'
            else:
                body_html += f'<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;">{p_html}</p>'
        
        # CTA button - link to app store
        app_store_url = app_info.get('app_store_url', '')
        google_play_url = app_info.get('google_play_url', '')
        is_web_app = app_store_url and not any(x in app_store_url for x in ['apps.apple.com', 'play.google.com'])
        
        cta_html = ""
        if is_web_app:
            cta_html = f'''
            <div style="text-align:center;margin:36px 0;">
                <a href="{app_store_url}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:16px 44px;text-decoration:none;border-radius:8px;font-weight:700;font-size:17px;box-shadow:0 6px 20px rgba(102,126,234,0.35);">
                    🚀 {cta_text} →
                </a>
            </div>'''
        elif app_store_url and google_play_url:
            cta_html = f'''
            <div style="text-align:center;margin:36px 0;">
                <a href="{app_store_url}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
                    📱 {cta_text} (iOS)
                </a>
                <a href="{google_play_url}" style="display:inline-block;background:linear-gradient(135deg,#34d399 0%,#10b981 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
                    🤖 {cta_text} (Android)
                </a>
            </div>'''
        elif app_store_url:
            cta_html = f'''
            <div style="text-align:center;margin:36px 0;">
                <a href="{app_store_url}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:16px 44px;text-decoration:none;border-radius:8px;font-weight:700;font-size:17px;">
                    📱 {cta_text} →
                </a>
            </div>'''
        elif google_play_url:
            cta_html = f'''
            <div style="text-align:center;margin:36px 0;">
                <a href="{google_play_url}" style="display:inline-block;background:linear-gradient(135deg,#34d399 0%,#10b981 100%);color:#fff;padding:16px 44px;text-decoration:none;border-radius:8px;font-weight:700;font-size:17px;">
                    🤖 {cta_text} →
                </a>
            </div>'''
        
        html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;">
    
    <div style="margin-bottom:28px;">
        <p style="margin:0 0 24px;font-size:18px;color:#6b7280;">Hey there,</p>
        {body_html}
    </div>
    
    {cta_html}
    
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;">
        Talk soon,<br>
        <strong style="color:#1f2937;">Ana</strong>
    </p>
    
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:#d1d5db;">San Francisco, CA 94117, United States</p>
        <p style="margin:0;font-size:12px;color:#d1d5db;">
            You're receiving this because you signed up for {app_name}.
        </p>
    </div>
    
</body>
</html>'''
        
        return html
    
    # ─── CAMPAIGN LOGIC ────────────────────────────────────
    
    def _get_eligible_users(self, users_by_app, daily_limit=None):
        """
        Find users who should receive their next email today.
        Rules:
        - New users (not in state) get email #1 immediately
        - Existing users wait the scheduled days between emails
        """
        eligible = []
        now = datetime.now()
        
        for app_name, users in users_by_app.items():
            app_info = self.firebase_loader.get_app_info(app_name)
            if not app_info:
                continue
            
            # Only process apps that have email templates defined
            if app_name not in APP_CONTEXT:
                continue
            
            for user in users:
                email = user['email']
                user_state = self.state['users'].get(email)
                
                if user_state is None:
                    # New user — send email #1
                    eligible.append({
                        'email': email,
                        'app_name': app_name,
                        'app_info': app_info,
                        'next_email': 1,
                    })
                else:
                    emails_sent = user_state.get('emails_sent', 0)
                    
                    # Already completed all 30 emails
                    if emails_sent >= 30:
                        continue
                    
                    # Check timing — import the sequence schedule
                    from retention_email_generator import EMAIL_SEQUENCE
                    next_email_num = emails_sent + 1
                    
                    if next_email_num > 30:
                        continue
                    
                    target_day = EMAIL_SEQUENCE[next_email_num - 1]['day']
                    prev_day = EMAIL_SEQUENCE[emails_sent - 1]['day'] if emails_sent > 0 else 0
                    days_to_wait = target_day - prev_day
                    
                    # Check if enough time has passed
                    last_sent_str = user_state.get('last_email_sent')
                    if last_sent_str:
                        last_sent = datetime.fromisoformat(last_sent_str)
                        hours_since_last = (now - last_sent).total_seconds() / 3600
                        hours_to_wait = max(days_to_wait * 24, 20)  # At least 20 hours
                        
                        if hours_since_last < hours_to_wait:
                            continue
                    
                    eligible.append({
                        'email': email,
                        'app_name': app_name,
                        'app_info': app_info,
                        'next_email': next_email_num,
                    })
                
                if daily_limit and len(eligible) >= daily_limit:
                    break
            
            if daily_limit and len(eligible) >= daily_limit:
                break
        
        return eligible
    
    def run_campaign(self, dry_run=False):
        """
        Main campaign runner. Loads users, finds eligible, sends emails.
        """
        print("=" * 60)
        print(f"🚀 APP RETENTION EMAIL CAMPAIGN")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        
        # 1. Load users from Firebase exports
        print("\n📱 Loading Firebase users...")
        users_by_app = self.firebase_loader.load_users_by_app()
        total_users = sum(len(u) for u in users_by_app.values())
        print(f"   Total: {total_users} users across {len(users_by_app)} apps")
        
        # 2. Find eligible users
        print("\n🎯 Finding eligible users...")
        eligible = self._get_eligible_users(users_by_app)
        
        if not eligible:
            print("   ✅ No users eligible right now. All caught up!")
            return
        
        # Group by app for summary
        by_app = {}
        for e in eligible:
            by_app.setdefault(e['app_name'], []).append(e)
        
        print(f"   📬 {len(eligible)} users ready for emails:")
        for app, users in sorted(by_app.items(), key=lambda x: -len(x[1])):
            email_nums = [u['next_email'] for u in users]
            print(f"      {app}: {len(users)} users (emails: {set(email_nums)})")
        
        if dry_run:
            print("\n🏁 DRY RUN - no emails sent")
            return
        
        # 3. Pre-generate needed emails
        print("\n📝 Preparing email content...")
        needed_emails = set()
        for e in eligible:
            needed_emails.add((e['app_name'], e['next_email']))
        
        email_content = {}
        for app_name, email_num in needed_emails:
            email_data = self.email_generator.get_email(app_name, email_num)
            if email_data:
                email_content[(app_name, email_num)] = email_data
                print(f"   ✅ {app_name} #{email_num}: {email_data['subject'][:50]}...")
            else:
                print(f"   ❌ Failed: {app_name} #{email_num}")
        
        # 4. Send emails via Brevo
        print(f"\n📧 Sending {len(eligible)} emails via Brevo...")
        gmail = GmailSender()
        
        if not gmail.connect():
            print("❌ Cannot connect to Brevo. Aborting.")
            return
        
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.state['daily_stats']:
            self.state['daily_stats'][today] = {'sent': 0, 'failed': 0}
        
        sent = 0
        failed = 0
        
        for i, entry in enumerate(eligible):
            email_addr = entry['email']
            app_name = entry['app_name']
            email_num = entry['next_email']
            app_info = entry['app_info']
            
            email_data = email_content.get((app_name, email_num))
            if not email_data:
                failed += 1
                continue
            
            # Build HTML
            html = self._build_html(email_data, app_info)
            
            # Send
            success = gmail.send_email(
                to_email=email_addr,
                subject=email_data['subject'],
                html_body=html,
                from_name=app_name
            )
            
            if success:
                sent += 1
                # Update user state
                now_str = datetime.now().isoformat()
                if email_addr not in self.state['users']:
                    self.state['users'][email_addr] = {
                        'app': app_name,
                        'emails_sent': 0,
                        'first_email_at': now_str,
                    }
                
                self.state['users'][email_addr]['emails_sent'] = email_num
                self.state['users'][email_addr]['last_email_sent'] = now_str
                self.state['daily_stats'][today]['sent'] += 1
                
                print(f"   ✅ [{sent}/{len(eligible)}] {email_addr} ← {app_name} #{email_num}")
            else:
                failed += 1
                self.state['daily_stats'][today]['failed'] += 1
                print(f"   ❌ [{i+1}/{len(eligible)}] {email_addr} FAILED")
            
            # Save state every 25 emails
            if (sent + failed) % 25 == 0:
                self._save_state()
            
            # Rate limit (1s for Brevo REST API)
            if i < len(eligible) - 1:
                time.sleep(1)
        
        gmail.disconnect()
        
        # Final state save
        self._save_state()
        
        print(f"\n{'='*60}")
        print(f"📊 CAMPAIGN RESULTS")
        print(f"   ✅ Sent: {sent}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📅 Daily total: {self.state['daily_stats'][today]}")
        print(f"{'='*60}")
    
    def show_status(self):
        """Show current campaign status"""
        print("=" * 60)
        print("📊 RETENTION CAMPAIGN STATUS")
        print("=" * 60)
        
        # Load users
        users_by_app = self.firebase_loader.load_users_by_app()
        total_users = sum(len(u) for u in users_by_app.values())
        
        # Analyze state
        tracked = len(self.state.get('users', {}))
        completed = sum(1 for u in self.state.get('users', {}).values() if u.get('emails_sent', 0) >= 30)
        
        print(f"\n📱 Total app users: {total_users}")
        print(f"📧 Users in email system: {tracked}")
        print(f"✅ Completed all 30 emails: {completed}")
        print(f"⏳ Still in sequence: {tracked - completed}")
        print(f"🆕 Not yet started: {total_users - tracked}")
        
        # Per-app breakdown
        print(f"\n{'─'*60}")
        by_app = {}
        for email, data in self.state.get('users', {}).items():
            app = data.get('app', 'Unknown')
            by_app.setdefault(app, {'total': 0, 'by_email': {}})
            by_app[app]['total'] += 1
            en = data.get('emails_sent', 0)
            by_app[app]['by_email'][en] = by_app[app]['by_email'].get(en, 0) + 1
        
        for app_name, stats in sorted(by_app.items()):
            firebase_count = len(users_by_app.get(app_name, []))
            print(f"\n📱 {app_name} ({firebase_count} total users)")
            for email_num in sorted(stats['by_email'].keys()):
                count = stats['by_email'][email_num]
                bar = "█" * min(count // 5, 30)
                print(f"   Email #{email_num}: {count} users {bar}")
        
        # Recent daily stats
        print(f"\n{'─'*60}")
        print("📅 Recent daily stats:")
        for date in sorted(self.state.get('daily_stats', {}).keys())[-7:]:
            stats = self.state['daily_stats'][date]
            print(f"   {date}: ✅ {stats['sent']} sent, ❌ {stats.get('failed', 0)} failed")


if __name__ == '__main__':
    import sys
    
    emailer = AppRetentionEmailer()
    
    if '--generate' in sys.argv:
        # Pre-generate all emails
        generator = RetentionEmailGenerator()
        generator.generate_all_emails()
    
    elif '--status' in sys.argv:
        emailer.show_status()
    
    elif '--refresh' in sys.argv:
        # Re-export Firebase users
        loader = FirebaseUserLoader()
        loader.refresh_exports()
    
    elif '--dry-run' in sys.argv:
        emailer.run_campaign(dry_run=True)
    
    else:
        emailer.run_campaign()
