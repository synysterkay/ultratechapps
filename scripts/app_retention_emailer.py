#!/usr/bin/env python3
"""
App Retention Email System
Main orchestrator: Loads Firebase users per app, sends 30-email retention
funnel via Resend. Tracks progress per user to never send duplicates.
Includes behavioral branching, streak triggers, and match-day triggers.

Usage:
  python scripts/app_retention_emailer.py              # Send next batch
  python scripts/app_retention_emailer.py --generate   # Pre-generate all emails
  python scripts/app_retention_emailer.py --status      # Show campaign status
  python scripts/app_retention_emailer.py --refresh     # Re-export Firebase users
  python scripts/app_retention_emailer.py --dry-run     # Simulate campaign (no send)
  python scripts/app_retention_emailer.py --streak      # Send streak reminder emails
  python scripts/app_retention_emailer.py --matchday    # Send match-day trigger emails
"""
import os
import sys
import json
import re
import time
import requests
from pathlib import Path
from datetime import datetime

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from firebase_user_loader import FirebaseUserLoader, FIREBASE_APPS
from retention_email_generator import RetentionEmailGenerator, APP_CONTEXT, EMAIL_SEQUENCE
from gmail_sender import GmailSender
from firestore_language_loader import FirestoreLanguageLoader
from deliverability_monitor import DeliverabilityMonitor
from firestore_activity_loader import FirestoreActivityLoader


# ─── DAILY SEND CAP ─────────────────────────────────────
# Limit total emails per day to protect domain reputation.
# This cap is shared across all apps per run.
DAILY_SEND_LIMIT = 1000

# ─── BEHAVIORAL BRANCHING (DISABLED) ───────────────────
# Churning acceleration removed to protect sender reputation.
# All users now follow the normal email sequence and timing.
# Re-engagement emails still exist in cache but are not force-sent.
CHURNING_REMAP = {}  # Disabled — no remapping


class AppRetentionEmailer:
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.state_file = self.base_dir / 'cache' / 'retention_state.json'
        self.state_file.parent.mkdir(exist_ok=True)
        
        self.firebase_loader = FirebaseUserLoader()
        self.email_generator = RetentionEmailGenerator()
        self.language_loader = FirestoreLanguageLoader()
        self.deliverability = DeliverabilityMonitor()
        self.activity_loader = FirestoreActivityLoader()
        self.user_languages = {}   # email -> language code
        self.user_activity = {}    # email -> {streak, favoriteLeague, isSubscribed, ...}
        
        # Load tracking state
        self.state = self._load_state()
        
        # Cache of emails already welcomed by Supabase (loaded lazily)
        self._welcomed_emails = None
    
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
    
    def _get_welcomed_emails(self):
        """
        Fetch emails already welcomed by the Supabase check-new-users cron.
        Returns a set of email addresses. Cached after first call.
        """
        if self._welcomed_emails is not None:
            return self._welcomed_emails
        
        self._welcomed_emails = set()
        try:
            config_path = self.base_dir / 'config' / 'supabase_config.json'
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            url = config['project']['url']
            key = config['project']['service_role_key']
            headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
            
            # Paginate through all welcomed users (1000 per page)
            offset = 0
            page_size = 1000
            while True:
                resp = requests.get(
                    f"{url}/rest/v1/welcomed_users",
                    params={'select': 'email', 'offset': offset, 'limit': page_size},
                    headers=headers,
                    timeout=30,
                )
                resp.raise_for_status()
                rows = resp.json()
                
                for row in rows:
                    self._welcomed_emails.add(row['email'])
                
                if len(rows) < page_size:
                    break
                offset += page_size
            
            print(f"   📋 {len(self._welcomed_emails)} users already welcomed by Supabase")
        except Exception as e:
            print(f"   ⚠️ Could not fetch Supabase welcomed_users: {e}")
        
        return self._welcomed_emails
    
    # ─── EMAIL HTML TEMPLATE ───────────────────────────────
    
    def _build_html(self, email_data, app_info, language='en', sender_name='Ana'):
        """Build beautiful HTML email from generated content, with language support"""
        
        app_name = email_data.get('app_name', app_info['name'])
        cta_text = email_data.get('cta_text', f'Open {app_name}')
        
        # Language-specific settings
        is_rtl = language == 'ar'
        dir_attr = ' dir="rtl"' if is_rtl else ''
        text_align = 'right' if is_rtl else 'left'
        
        # Localized greeting and sign-off
        greetings = {'en': 'Hey there,', 'ar': 'مرحبًا،', 'es': 'Hola,', 'fr': 'Salut,', 'zh': '你好，', 'hi': 'नमस्ते,', 'pt': 'Olá,', 'ru': 'Привет,', 'de': 'Hallo,', 'tr': 'Merhaba,', 'it': 'Ciao,', 'pp': 'Olá,', 'id': 'Halo,', 'nl': 'Hallo,', 'pl': 'Cześć,', 'ja': 'こんにちは、'}
        signoffs = {'en': 'Talk soon,', 'ar': 'إلى اللقاء،', 'es': 'Hasta pronto,', 'fr': 'À bientôt,', 'zh': '回头聊，', 'hi': 'जल्द बात करते हैं,', 'pt': 'Até logo,', 'ru': 'До скорого,', 'de': 'Bis bald,', 'tr': 'Görüşürz,', 'it': 'A presto,', 'pp': 'Até breve,', 'id': 'Sampai jumpa,', 'nl': 'Tot snel,', 'pl': 'Do zobaczenia,', 'ja': 'またね、'}
        footers = {
            'en': f"You're receiving this because you signed up for {app_name}.",
            'ar': f"تتلقى هذا البريد لأنك سجلت في {app_name}.",
            'es': f"Recibes esto porque te registraste en {app_name}.",
            'fr': f"Vous recevez ceci car vous vous êtes inscrit(e) à {app_name}.",
            'zh': f"您收到此邮件是因为您注册了 {app_name}。",
            'hi': f"आपको यह ईमेल इसलिए मिल रहा है क्योंकि आपने {app_name} के लिए साइन अप किया है।",
            'pt': f"Você está recebendo isso porque se registrou no {app_name}.",
            'ru': f"Вы получили это письмо, потому что зарегистрировались в {app_name}.",            'de': f"Du erhältst diese E-Mail, weil du dich bei {app_name} angemeldet hast.",
            'tr': f"Bu e-postayı {app_name} uygulamasına kayıt olduğunuz için alıyorsunuz.",
            'it': f"Ricevi questa email perché ti sei registrato su {app_name}.",
            'pp': f"Recebe este email porque se registou no {app_name}.",
            'id': f"Anda menerima email ini karena mendaftar di {app_name}.",
            'nl': f"Je ontvangt dit bericht omdat je je hebt aangemeld voor {app_name}.",
            'pl': f"Otrzymujesz tę wiadomość, ponieważ zarejestrowaałeś się w {app_name}.",
            'ja': f"{app_name}にご登録いただいたため、このメールをお送りしています。",        }
        
        greeting = greetings.get(language, greetings['en'])
        signoff = signoffs.get(language, signoffs['en'])
        footer_text = footers.get(language, footers['en'])
        
        # Build body paragraphs
        body_html = ""
        paragraphs = email_data.get('body_paragraphs', [])
        for i, p in enumerate(paragraphs):
            # Convert \n to <br> for line breaks within paragraphs
            p_html = p.replace('\n', '<br>')
            if i == 0:
                body_html += f'<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;text-align:{text_align};">{p_html}</p>'
            elif 'P.S.' in p or 'P.S' in p or 'ملاحظة' in p or 'P.D.' in p:
                body_html += f'<div style="margin:32px 0 0;padding:16px 20px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;"><p style="margin:0;font-size:16px;color:#92400e;line-height:1.7;text-align:{text_align};">{p_html}</p></div>'
            else:
                body_html += f'<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:{text_align};">{p_html}</p>'
        
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
<html{dir_attr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:{text_align};">
    
    <div style="margin-bottom:28px;">
        <p style="margin:0 0 24px;font-size:18px;color:#6b7280;text-align:{text_align};">{greeting}</p>
        {body_html}
    </div>
    
    {cta_html}
    
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:{text_align};">
        {signoff}<br>
        <strong style="color:#1f2937;">{sender_name}</strong>
    </p>
    
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:#d1d5db;">San Francisco, CA 94117, United States</p>
        <p style="margin:0;font-size:12px;color:#d1d5db;">
            {footer_text}
        </p>
    </div>
    
</body>
</html>'''
        
        return html
    
    # ─── ACTIVE APPS (only these receive emails) ─────────
    # Priority order: first = highest priority for daily cap allocation.
    ACTIVE_APPS = [
        'Predictify',
        'Volume Booster - Sound Booster',
        'Thesis Generator',
        'Red Flag Scanner AI',
        'Fresh Start: Breakup Therapy',
        'SoulPlan: Plan Dates Together',
        'PupShape: Dog Weight Loss Plan',
        'Predictify: Horse Racing AI',
    ]

    # ─── CAMPAIGN LOGIC ────────────────────────────────────
    
    def _classify_user(self, user, emails_sent):
        """
        Classify user into behavioral segment based on last app login.
        Returns: 'active', 'churning', or 'normal'.
        Used for emails #4+ to branch the sequence.
        """
        # Only branch after the activation phase (emails 1-3)
        if emails_sent < 3:
            return 'normal'
        
        last_login = user.get('last_login', '')
        if not last_login:
            return 'normal'
        
        try:
            # Firebase timestamp is milliseconds since epoch
            ts = int(last_login)
            if ts > 1e12:  # milliseconds
                ts = ts / 1000
            last_login_dt = datetime.fromtimestamp(ts)
            days_since = (datetime.now() - last_login_dt).days
        except (ValueError, TypeError, OSError):
            return 'normal'
        
        if days_since <= 3:
            return 'active'
        elif days_since >= 7:
            return 'churning'
        return 'normal'
    
    def _get_email_for_segment(self, next_email_num, segment, is_subscribed=False):
        """
        Get the actual email number to send based on user segment.
        Churning users get re-engagement emails instead of deepening emails.
        Subscribed users skip heavy upsell emails.
        Returns: (actual_email_num, remapped: bool)
        """
        if segment == 'churning' and next_email_num in CHURNING_REMAP:
            return CHURNING_REMAP[next_email_num], True
        return next_email_num, False
    
    def _get_eligible_users(self, users_by_app):
        """
        Find users who should receive their next email today.
        Priority order (by ACTIVE_APPS index):
          - New users of each app first, then existing users
          - Predictify gets top priority
        """
        eligible = []
        now = datetime.now()
        
        # Build priority-ordered list: new users first, then existing, per app
        ordered_entries = []  # (priority, app_name, user)
        
        for app_name, users in users_by_app.items():
            # Only process active apps
            if app_name not in self.ACTIVE_APPS:
                continue
            
            # App priority: Predictify=0, Thesis Generator=1
            app_priority = self.ACTIVE_APPS.index(app_name) if app_name in self.ACTIVE_APPS else 99
            
            for user in users:
                email = user['email']
                is_new = email not in self.state.get('users', {})
                # New users get priority 0 (first), existing get 1 (second)
                user_priority = 0 if is_new else 1
                # Combined: (app_priority * 10 + user_priority) → Predictify new=0, Predictify old=1, Thesis new=10, Thesis old=11
                combined = app_priority * 10 + user_priority
                ordered_entries.append((combined, app_name, user))
        
        # Sort by priority
        ordered_entries.sort(key=lambda x: x[0])
        
        for _, app_name, user in ordered_entries:
            app_info = self.firebase_loader.get_app_info(app_name)
            if not app_info:
                continue
            
            # Only process apps that have email templates defined
            if app_name not in APP_CONTEXT:
                continue
            
            email = user['email']
            user_state = self.state['users'].get(email)
            
            # Skip suppressed users (spam reporters / hard bounces)
            if user_state and user_state.get('suppressed'):
                continue
            
            if user_state is None:
                # New user from Firebase — check if Supabase already sent welcome email
                welcomed = self._get_welcomed_emails()
                already_welcomed = email in welcomed
                
                self.state['users'][email] = {
                    'app': app_name,
                    'emails_sent': 1 if already_welcomed else 0,
                    'first_email_at': now.isoformat(),
                    'last_email_sent': now.isoformat() if already_welcomed else None,
                }
                user_state = self.state['users'][email]
            
            if user_state:
                emails_sent = user_state.get('emails_sent', 0)
                
                # Already completed all 30 emails
                if emails_sent >= 30:
                    continue
                
                # Check timing
                from retention_email_generator import EMAIL_SEQUENCE
                next_email_num = emails_sent + 1
                
                if next_email_num > 30:
                    continue
                
                # Email #1 (welcome): send immediately, no waiting
                if emails_sent == 0:
                    eligible.append({
                        'email': email,
                        'app_name': app_name,
                        'app_info': app_info,
                        'next_email': 1,
                        'actual_email': 1,
                        'language': user.get('language', 'en'),
                        'segment': 'new',
                    })
                    continue
                
                target_day = EMAIL_SEQUENCE[next_email_num - 1]['day']
                prev_day = EMAIL_SEQUENCE[emails_sent - 1]['day'] if emails_sent > 0 else 0
                days_to_wait = target_day - prev_day
                
                # Check if enough time has passed
                last_sent_str = user_state.get('last_email_sent')
                if last_sent_str:
                    last_sent = datetime.fromisoformat(last_sent_str)
                    hours_since_last = (now - last_sent).total_seconds() / 3600
                    
                    # All users follow normal timing (no churning acceleration)
                    segment = self._classify_user(user, emails_sent)
                    hours_to_wait = max(days_to_wait * 24, 20)
                    
                    # Skip churning users who've received 3+ emails
                    # They're not engaging — sending more hurts reputation
                    if segment == 'churning' and emails_sent >= 3:
                        continue
                    
                    if hours_since_last < hours_to_wait:
                        continue
                else:
                    segment = self._classify_user(user, emails_sent)
                    if segment == 'churning' and emails_sent >= 3:
                        continue
                
                # Check activity data for subscription status
                activity = self.user_activity.get(email, {})
                is_subscribed = activity.get('isSubscribed') or activity.get('isPremium', False)
                
                # Get actual email to send (may be remapped for churning)
                actual_email, remapped = self._get_email_for_segment(
                    next_email_num, segment, is_subscribed
                )
                
                eligible.append({
                    'email': email,
                    'app_name': app_name,
                    'app_info': app_info,
                    'next_email': next_email_num,
                    'actual_email': actual_email,
                    'language': user.get('language', 'en'),
                    'segment': segment,
                    'remapped': remapped,
                })
            
        return eligible
    
    def run_campaign(self, dry_run=False):
        """
        Main campaign runner. Loads users, finds eligible, sends emails.
        """
        print("=" * 60)
        print(f"🚀 APP RETENTION EMAIL CAMPAIGN")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        
        # 1. Auto-refresh Firebase exports to pick up new signups
        print("\n🔄 Refreshing Firebase user exports...")
        self.firebase_loader.refresh_exports()
        
        print("\n📱 Loading Firebase users...")
        users_by_app = self.firebase_loader.load_users_by_app()
        total_users = sum(len(u) for u in users_by_app.values())
        print(f"   Total: {total_users} users across {len(users_by_app)} apps")
        
        # 1b. Load language preferences for multilingual apps from Firestore
        multilingual_apps = {
            'Predictify': 'Predictify',
            'Volume Booster - Sound Booster': 'Volume Booster - Sound Booster',
            'Predictify: Horse Racing AI': 'Predictify: Horse Racing AI',
        }
        for app_name, loader_key in multilingual_apps.items():
            if app_name in users_by_app:
                print(f"\n🌍 Loading {app_name} user languages from Firestore...")
                app_languages = self.language_loader.fetch_user_languages(loader_key)
                self.user_languages.update(app_languages)
                # Enrich users with language
                for user in users_by_app.get(app_name, []):
                    user['language'] = self.user_languages.get(user['email'], 'en')
        
        # 1b2. Load activity data for behavioral branching (Predictify)
        print("\n📊 Loading user activity data for behavioral branching...")
        for app_name in ['Predictify']:
            if app_name in users_by_app:
                activity = self.activity_loader.fetch_user_activity(app_name)
                self.user_activity.update(activity)
        
        # 1c. Check sender health & auto-rotate if needed
        print("\n🏥 Checking sender health...")
        active_sender = self.deliverability.check_and_rotate_if_needed()
        
        # 1d. Clean bad recipients (spam reporters + hard bounces)
        self.deliverability.clean_bad_recipients(self.state)
        self._save_state()
        
        # 2. Find eligible users (also registers new users into state)
        print("\n🎯 Finding eligible users...")
        eligible = self._get_eligible_users(users_by_app)
        self._save_state()  # Persist newly registered users
        
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
            segments = {}
            for u in users:
                seg = u.get('segment', 'normal')
                segments[seg] = segments.get(seg, 0) + 1
            seg_str = ', '.join(f"{k}:{v}" for k, v in sorted(segments.items()))
            print(f"      {app}: {len(users)} users (emails: {set(email_nums)}) [{seg_str}]")
        
        if dry_run:
            print("\n🏁 DRY RUN - no emails sent")
            return
        
        # 3. Load pre-generated emails from cache (never call DeepSeek API during campaigns)
        print("\n📝 Loading email content from cache...")
        needed_emails = set()
        for e in eligible:
            lang = e.get('language', 'en')
            actual = e.get('actual_email', e['next_email'])
            needed_emails.add((e['app_name'], actual, lang))
        
        email_content = {}
        for app_name, email_num, lang in needed_emails:
            email_data = self.email_generator.get_email(app_name, email_num, language=lang, cache_only=True)
            if email_data:
                email_content[(app_name, email_num, lang)] = email_data
                lang_label = f" ({lang})" if lang != 'en' else ''
                print(f"   ✅ {app_name} #{email_num}{lang_label}: {email_data['subject'][:50]}...")
            else:
                print(f"   ❌ Not cached: {app_name} #{email_num} ({lang}) — run --generate first")
        
        # 4. Send emails via Resend (using active sender from health check)
        print(f"\n📧 Sending {len(eligible)} emails via Resend...")
        gmail = GmailSender(
            sender_email=active_sender['email'],
            sender_name=active_sender['name'],
        )
        
        if not gmail.connect():
            print("❌ Cannot connect to Resend. Aborting.")
            return
        
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.state['daily_stats']:
            self.state['daily_stats'][today] = {'sent': 0, 'failed': 0}
        
        # Enforce daily send cap across all runs today
        already_sent_today = self.state['daily_stats'][today].get('sent', 0)
        remaining_cap = max(0, DAILY_SEND_LIMIT - already_sent_today)
        if remaining_cap == 0:
            print(f"   🛑 Daily send cap reached ({DAILY_SEND_LIMIT}). Skipping this run.")
            return
        if remaining_cap < len(eligible):
            print(f"   ⚠️ Cap allows {remaining_cap} more emails today (limit: {DAILY_SEND_LIMIT}, already sent: {already_sent_today})")
            eligible = eligible[:remaining_cap]
        
        sent = 0
        failed = 0
        
        for i, entry in enumerate(eligible):
            email_addr = entry['email']
            app_name = entry['app_name']
            email_num = entry['next_email']
            actual_num = entry.get('actual_email', email_num)
            app_info = entry['app_info']
            lang = entry.get('language', 'en')
            segment = entry.get('segment', 'normal')
            
            email_data = email_content.get((app_name, actual_num, lang))
            if not email_data:
                failed += 1
                continue
            
            # Build HTML
            html = self._build_html(email_data, app_info, lang, sender_name=active_sender['name'])
            
            # Send
            result = gmail.send_email(
                to_email=email_addr,
                subject=email_data['subject'],
                html_body=html,
                from_name=app_name
            )
            
            if result == 'sent':
                sent += 1
                # Update user state
                now_str = datetime.now().isoformat()
                if email_addr not in self.state['users']:
                    self.state['users'][email_addr] = {
                        'app': app_name,
                        'emails_sent': 0,
                        'first_email_at': now_str,
                    }
                
                # Skip suppressed users (spam reporters / hard bounces)
                if self.state['users'].get(email_addr, {}).get('suppressed'):
                    continue
                
                self.state['users'][email_addr]['emails_sent'] = email_num
                self.state['users'][email_addr]['last_email_sent'] = now_str
                self.state['users'][email_addr]['segment'] = segment
                self.state['daily_stats'][today]['sent'] += 1
                
                remap_note = f" (re-engage #{actual_num})" if entry.get('remapped') else ""
                print(f"   ✅ [{sent}/{len(eligible)}] {email_addr} ← {app_name} #{email_num}{remap_note} [{segment}]")
            elif result == 'bounced':
                # Auto-remove bounced email from the system
                failed += 1
                if email_addr in self.state['users']:
                    del self.state['users'][email_addr]
                self.state['daily_stats'][today]['failed'] += 1
                bounced_count = self.state.get('total_bounced', 0) + 1
                self.state['total_bounced'] = bounced_count
                print(f"   🔴 [{i+1}/{len(eligible)}] {email_addr} BOUNCED — removed from system")
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
    
    def run_streak_triggers(self, dry_run=False):
        """
        Send streak reminder emails to users with active streaks >= 3.
        Max 1 streak email per user per week.
        Hooked model: Internal trigger reinforcement — streak anxiety drives re-engagement.
        """
        print("=" * 60)
        print("🔥 STREAK TRIGGER EMAILS")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        
        # Load activity data
        print("\n📊 Loading user activity data...")
        activity = self.activity_loader.fetch_user_activity('Predictify')
        if not activity:
            print("   ⚠️ No activity data available (FIREBASE_TOKEN not set?)")
            return
        
        # Find users with streak >= 3
        streak_users = []
        now = datetime.now()
        for email, data in activity.items():
            streak = data.get('streak', 0)
            if streak < 3:
                continue
            
            # Check we haven't sent a streak email in the last 7 days
            user_state = self.state['users'].get(email, {})
            last_streak = user_state.get('last_streak_email')
            if last_streak:
                last_dt = datetime.fromisoformat(last_streak)
                if (now - last_dt).days < 7:
                    continue
            
            streak_users.append({'email': email, 'streak': streak})
        
        print(f"\n🔥 {len(streak_users)} users eligible for streak reminders")
        
        if not streak_users or dry_run:
            if dry_run:
                print("\n🏁 DRY RUN — no emails sent")
                for u in streak_users[:10]:
                    print(f"   Would send: {u['email']} (streak: {u['streak']})")
            return
        
        # Get sender
        active_sender = self.deliverability.check_and_rotate_if_needed()
        gmail = GmailSender(
            sender_email=active_sender['email'],
            sender_name=active_sender['name'],
        )
        if not gmail.connect():
            print("❌ Cannot connect to Resend. Aborting.")
            return
        
        # Get user languages
        languages = self.language_loader.fetch_user_languages('Predictify')
        app_info = self.firebase_loader.get_app_info('Predictify')
        
        sent = 0
        for user in streak_users:
            email_addr = user['email']
            streak = user['streak']
            lang = languages.get(email_addr, 'en')
            
            # Build streak email
            html = self._build_streak_html(streak, lang, app_info, active_sender['name'])
            subject = self._get_streak_subject(streak, lang)
            
            result = gmail.send_email(
                to_email=email_addr,
                subject=subject,
                html_body=html,
                from_name='Predictify'
            )
            
            if result == 'sent':
                sent += 1
                if email_addr not in self.state['users']:
                    self.state['users'][email_addr] = {'app': 'Predictify', 'emails_sent': 0}
                self.state['users'][email_addr]['last_streak_email'] = now.isoformat()
                print(f"   🔥 {email_addr} (streak: {streak})")
            
            time.sleep(1)
        
        gmail.disconnect()
        self._save_state()
        print(f"\n📊 Streak emails sent: {sent}/{len(streak_users)}")
    
    def _get_streak_subject(self, streak, lang):
        """Get localized streak email subject line."""
        subjects = {
            'en': f"Your {streak}-day streak is alive — don't let it die",
            'ar': f"سلسلتك من {streak} أيام لا تزال قائمة — لا تدعها تنتهي",
            'es': f"Tu racha de {streak} días sigue viva — no la pierdas",
            'fr': f"Votre série de {streak} jours est en vie — ne la perdez pas",
            'pt': f"Sua sequência de {streak} dias continua — não deixe morrer",
            'de': f"Deine {streak}-Tage-Serie lebt noch — lass sie nicht sterben",
            'tr': f"{streak} günlük seriniz devam ediyor — kaybetmeyin",
            'it': f"La tua serie di {streak} giorni è ancora viva — non lasciarla morire",
            'pp': f"A sua série de {streak} dias continua — não a deixe acabar",
            'hi': f"आपकी {streak} दिन की स्ट्रीक जारी है — इसे खत्म मत होने दीजिए",
            'id': f"Streak {streak} hari Anda masih aktif — jangan biarkan berakhir",
            'nl': f"Je {streak}-daagse reeks is nog actief — laat het niet stoppen",
            'pl': f"Twoja {streak}-dniowa seria jest aktywna — nie pozwól jej się skończyć",
            'ja': f"あなたの{streak}日連続記録はまだ続いています — 途切れさせないで",
        }
        return subjects.get(lang, subjects['en'])
    
    def _build_streak_html(self, streak, lang, app_info, sender_name):
        """Build streak reminder email HTML."""
        is_rtl = lang == 'ar'
        dir_attr = ' dir="rtl"' if is_rtl else ''
        text_align = 'right' if is_rtl else 'left'
        
        greetings = {'en': 'Hey there,', 'ar': 'مرحبًا،', 'es': 'Hola,', 'fr': 'Salut,', 'pt': 'Olá,', 'de': 'Hallo,', 'tr': 'Merhaba,', 'it': 'Ciao,', 'pp': 'Olá,', 'hi': 'नमस्ते,', 'id': 'Halo,', 'nl': 'Hallo,', 'pl': 'Cześć,', 'ja': 'こんにちは、'}
        
        bodies = {
            'en': f"You're on a {streak}-day prediction streak. That puts you ahead of most Predictify users.\n\nToday's matches are already analyzed — the AI has confidence scores ready. One quick prediction keeps your streak alive and climbing.\n\nThe users who build long streaks unlock special badges and climb the leaderboard. Your {streak}-day streak is worth protecting.\n\nP.S. Open the app now — it takes 30 seconds to make a prediction and keep your streak going.",
            'ar': f"أنت في سلسلة توقعات من {streak} أيام. هذا يضعك متقدمًا على معظم مستخدمي Predictify.\n\nمباريات اليوم تم تحليلها — الذكاء الاصطناعي لديه درجات الثقة جاهزة. توقع واحد سريع يبقي سلسلتك.\n\nالمستخدمون الذين يبنون سلاسل طويلة يفتحون شارات خاصة. سلسلتك من {streak} أيام تستحق الحماية.\n\nملاحظة: افتح التطبيق الآن — يستغرق 30 ثانية فقط.",
            'es': f"Llevas una racha de {streak} días de predicciones. Eso te pone por delante de la mayoría.\n\nLos partidos de hoy ya están analizados — la IA tiene puntuaciones de confianza listas. Una predicción rápida mantiene tu racha.\n\nLos usuarios con rachas largas desbloquean insignias y suben en el ranking. Tu racha de {streak} días vale la pena protegerla.\n\nP.D. Abre la app ahora — toma 30 segundos.",
            'fr': f"Vous êtes sur une série de {streak} jours de prédictions. Ça vous place devant la plupart des utilisateurs.\n\nLes matchs d'aujourd'hui sont déjà analysés — l'IA a les scores de confiance prêts. Une prédiction rapide maintient votre série.\n\nLes utilisateurs avec de longues séries débloquent des badges spéciaux. Votre série de {streak} jours mérite d'être protégée.\n\nP.S. Ouvrez l'app maintenant — ça prend 30 secondes.",
        }
        
        greeting = greetings.get(lang, greetings['en'])
        body = bodies.get(lang, bodies['en'])
        
        # Build CTA
        app_store_url = app_info.get('app_store_url', '')
        google_play_url = app_info.get('google_play_url', '')
        
        cta_html = ""
        if app_store_url and google_play_url:
            cta_html = f'''
            <div style="text-align:center;margin:36px 0;">
                <a href="{app_store_url}" style="display:inline-block;background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
                    🔥 Keep Streak Alive (iOS)
                </a>
                <a href="{google_play_url}" style="display:inline-block;background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
                    🔥 Keep Streak Alive (Android)
                </a>
            </div>'''
        
        paragraphs_html = ""
        for p in body.split("\n\n"):
            p_html = p.replace('\n', '<br>')
            if 'P.S.' in p or 'P.D.' in p or 'ملاحظة' in p:
                paragraphs_html += f'<div style="margin:32px 0 0;padding:16px 20px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;"><p style="margin:0;font-size:16px;color:#92400e;line-height:1.7;text-align:{text_align};">{p_html}</p></div>'
            else:
                paragraphs_html += f'<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:{text_align};">{p_html}</p>'
        
        signoffs = {'en': 'Talk soon,', 'ar': 'إلى اللقاء،', 'es': 'Hasta pronto,', 'fr': 'À bientôt,', 'pt': 'Até logo,', 'de': 'Bis bald,', 'tr': 'Görüşürüz,', 'it': 'A presto,', 'pp': 'Até breve,', 'hi': 'जल्द बात करते हैं,', 'id': 'Sampai jumpa,', 'nl': 'Tot snel,', 'pl': 'Do zobaczenia,', 'ja': 'またね、'}
        signoff = signoffs.get(lang, signoffs['en'])
        
        return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:{text_align};">
    <div style="margin-bottom:28px;">
        <p style="margin:0 0 24px;font-size:18px;color:#6b7280;text-align:{text_align};">{greeting}</p>
        {paragraphs_html}
    </div>
    {cta_html}
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:{text_align};">
        {signoff}<br>
        <strong style="color:#1f2937;">{sender_name}</strong>
    </p>
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0;font-size:12px;color:#d1d5db;">You're receiving this because you have a Predictify account.</p>
    </div>
</body>
</html>'''
    
    def run_matchday_triggers(self, dry_run=False):
        """
        Send match-day triggered emails to users whose favorite leagues have matches today.
        Max 2 match-day emails per user per week.
        Hooked model: Perfect external trigger — timed to when user thinks about football.
        """
        print("=" * 60)
        print("⚽ MATCH-DAY TRIGGER EMAILS")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        
        # Load activity data to get favorite leagues
        print("\n📊 Loading user favorite leagues...")
        activity = self.activity_loader.fetch_user_activity('Predictify')
        if not activity:
            print("   ⚠️ No activity data available")
            return
        
        # Group users by favorite league
        users_by_league = {}
        now = datetime.now()
        for email, data in activity.items():
            league = data.get('favoriteLeague')
            if not league:
                continue
            
            # Check max 2 match-day emails per week
            user_state = self.state['users'].get(email, {})
            last_matchday = user_state.get('last_matchday_email')
            matchday_count = user_state.get('matchday_emails_this_week', 0)
            
            if last_matchday:
                last_dt = datetime.fromisoformat(last_matchday)
                days_since = (now - last_dt).days
                if days_since < 1:
                    continue
                if days_since >= 7:
                    matchday_count = 0  # Reset weekly counter
            
            if matchday_count >= 2:
                continue
            
            users_by_league.setdefault(league, []).append(email)
        
        if not users_by_league:
            print("   ✅ No users with favorite leagues set")
            return
        
        print(f"   Leagues with users: {list(users_by_league.keys())}")
        total_eligible = sum(len(v) for v in users_by_league.values())
        print(f"   Total eligible: {total_eligible} users across {len(users_by_league)} leagues")
        
        if dry_run:
            print("\n🏁 DRY RUN — no emails sent")
            for league, emails in sorted(users_by_league.items(), key=lambda x: -len(x[1])):
                print(f"   {league}: {len(emails)} users")
            return
        
        # Get sender and languages
        active_sender = self.deliverability.check_and_rotate_if_needed()
        gmail = GmailSender(
            sender_email=active_sender['email'],
            sender_name=active_sender['name'],
        )
        if not gmail.connect():
            print("❌ Cannot connect to Resend. Aborting.")
            return
        
        languages = self.language_loader.fetch_user_languages('Predictify')
        app_info = self.firebase_loader.get_app_info('Predictify')
        
        sent = 0
        for league, user_emails in users_by_league.items():
            for email_addr in user_emails:
                lang = languages.get(email_addr, 'en')
                html = self._build_matchday_html(league, lang, app_info, active_sender['name'])
                subject = self._get_matchday_subject(league, lang)
                
                result = gmail.send_email(
                    to_email=email_addr,
                    subject=subject,
                    html_body=html,
                    from_name='Predictify'
                )
                
                if result == 'sent':
                    sent += 1
                    if email_addr not in self.state['users']:
                        self.state['users'][email_addr] = {'app': 'Predictify', 'emails_sent': 0}
                    self.state['users'][email_addr]['last_matchday_email'] = now.isoformat()
                    prev_count = self.state['users'][email_addr].get('matchday_emails_this_week', 0)
                    self.state['users'][email_addr]['matchday_emails_this_week'] = prev_count + 1
                    print(f"   ⚽ {email_addr} ← {league}")
                
                time.sleep(1)
        
        gmail.disconnect()
        self._save_state()
        print(f"\n📊 Match-day emails sent: {sent}/{total_eligible}")
    
    def _get_matchday_subject(self, league, lang):
        """Get localized match-day email subject."""
        subjects = {
            'en': f"{league} kicks off today — the AI's top predictions are ready",
            'ar': f"مباريات {league} اليوم — توقعات الذكاء الاصطناعي جاهزة",
            'es': f"{league} empieza hoy — las predicciones de la IA están listas",
            'fr': f"{league} commence aujourd'hui — les prédictions sont prêtes",
            'pt': f"{league} começa hoje — as previsões da IA estão prontas",
            'de': f"{league} startet heute — die KI-Vorhersagen sind bereit",
            'tr': f"{league} bugün başlıyor — yapay zekanın tahminleri hazır",
            'it': f"{league} inizia oggi — le previsioni dell'IA sono pronte",
            'pp': f"{league} começa hoje — as previsões da IA estão prontas",
            'hi': f"{league} आज शुरू होता है — AI की भविष्यवाणियां तैयार हैं",
            'id': f"{league} dimulai hari ini — prediksi AI sudah siap",
            'nl': f"{league} begint vandaag — de AI-voorspellingen staan klaar",
            'pl': f"{league} zaczyna się dzisiaj — prognozy AI są gotowe",
            'ja': f"{league}が今日開幕 — AIの予測が準備完了",
        }
        return subjects.get(lang, subjects['en'])
    
    def _build_matchday_html(self, league, lang, app_info, sender_name):
        """Build match-day trigger email HTML."""
        is_rtl = lang == 'ar'
        dir_attr = ' dir="rtl"' if is_rtl else ''
        text_align = 'right' if is_rtl else 'left'
        
        greetings = {'en': 'Hey there,', 'ar': 'مرحبًا،', 'es': 'Hola,', 'fr': 'Salut,', 'pt': 'Olá,', 'de': 'Hallo,', 'tr': 'Merhaba,', 'it': 'Ciao,', 'pp': 'Olá,', 'hi': 'नमस्ते,', 'id': 'Halo,', 'nl': 'Hallo,', 'pl': 'Cześć,', 'ja': 'こんにちは、'}
        
        bodies = {
            'en': f"It's matchday for {league}. The AI has already analyzed today's fixtures — confidence scores, head-to-head stats, and tactical breakdowns are all ready.\n\nOpen Predictify and check the AI's most confident predictions before kickoff. The predictions with the highest confidence scores have been the most accurate this season.\n\nMake your predictions before the matches start and keep your streak going. The best predictions come from checking the AI analysis early.\n\nP.S. Tap on any match to see the full breakdown — xG, defensive strength, recent form. It's all there.",
            'ar': f"اليوم يوم مباريات {league}. الذكاء الاصطناعي حلل مباريات اليوم — درجات الثقة والإحصائيات جاهزة.\n\nافتح Predictify وتحقق من أكثر التوقعات ثقة قبل صافرة البداية.\n\nقم بتوقعاتك قبل بداية المباريات وحافظ على سلسلتك.\n\nملاحظة: اضغط على أي مباراة لرؤية التحليل الكامل.",
            'es': f"Hoy es día de partido en {league}. La IA ya analizó los partidos de hoy — predicciones y estadísticas están listas.\n\nAbre Predictify y revisa las predicciones más confiables antes del inicio. Las predicciones con mayor confianza han sido las más precisas esta temporada.\n\nHaz tus predicciones antes de que empiecen los partidos.\n\nP.D. Toca cualquier partido para ver el análisis completo — xG, fortaleza defensiva, forma reciente.",
            'fr': f"C'est jour de match en {league}. L'IA a déjà analysé les rencontres d'aujourd'hui — scores de confiance et statistiques sont prêts.\n\nOuvrez Predictify et vérifiez les prédictions les plus fiables avant le coup d'envoi.\n\nFaites vos prédictions avant le début des matchs et maintenez votre série.\n\nP.S. Appuyez sur n'importe quel match pour voir l'analyse complète.",
        }
        
        greeting = greetings.get(lang, greetings['en'])
        body = bodies.get(lang, bodies['en'])
        
        app_store_url = app_info.get('app_store_url', '')
        google_play_url = app_info.get('google_play_url', '')
        
        cta_html = ""
        if app_store_url and google_play_url:
            cta_html = f'''
            <div style="text-align:center;margin:36px 0;">
                <a href="{app_store_url}" style="display:inline-block;background:linear-gradient(135deg,#10b981 0%,#059669 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
                    ⚽ See Predictions (iOS)
                </a>
                <a href="{google_play_url}" style="display:inline-block;background:linear-gradient(135deg,#10b981 0%,#059669 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
                    ⚽ See Predictions (Android)
                </a>
            </div>'''
        
        paragraphs_html = ""
        for p in body.split("\n\n"):
            p_html = p.replace('\n', '<br>')
            if 'P.S.' in p or 'P.D.' in p or 'ملاحظة' in p:
                paragraphs_html += f'<div style="margin:32px 0 0;padding:16px 20px;background:#ecfdf5;border-radius:8px;border:1px solid #6ee7b7;"><p style="margin:0;font-size:16px;color:#065f46;line-height:1.7;text-align:{text_align};">{p_html}</p></div>'
            else:
                paragraphs_html += f'<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:{text_align};">{p_html}</p>'
        
        signoffs = {'en': 'Talk soon,', 'ar': 'إلى اللقاء،', 'es': 'Hasta pronto,', 'fr': 'À bientôt,', 'pt': 'Até logo,', 'de': 'Bis bald,', 'tr': 'Görüşürüz,', 'it': 'A presto,', 'pp': 'Até breve,', 'hi': 'जल्द बात करते हैं,', 'id': 'Sampai jumpa,', 'nl': 'Tot snel,', 'pl': 'Do zobaczenia,', 'ja': 'またね、'}
        signoff = signoffs.get(lang, signoffs['en'])
        
        return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:{text_align};">
    <div style="margin-bottom:28px;">
        <p style="margin:0 0 24px;font-size:18px;color:#6b7280;text-align:{text_align};">{greeting}</p>
        {paragraphs_html}
    </div>
    {cta_html}
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:{text_align};">
        {signoff}<br>
        <strong style="color:#1f2937;">{sender_name}</strong>
    </p>
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0;font-size:12px;color:#d1d5db;">You're receiving this because you have a Predictify account.</p>
    </div>
</body>
</html>'''
    
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
    
    elif '--streak' in sys.argv:
        # Streak trigger emails
        dry_run = '--dry-run' in sys.argv or '--streak-dry' in sys.argv
        emailer.run_streak_triggers(dry_run=dry_run)
    
    elif '--matchday' in sys.argv:
        # Match-day trigger emails
        dry_run = '--dry-run' in sys.argv or '--matchday-dry' in sys.argv
        emailer.run_matchday_triggers(dry_run=dry_run)
    
    else:
        emailer.run_campaign()
