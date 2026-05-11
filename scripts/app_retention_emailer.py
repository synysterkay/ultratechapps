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
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from firebase_user_loader import FirebaseUserLoader, FIREBASE_APPS
from retention_email_generator import RetentionEmailGenerator, APP_CONTEXT, EMAIL_SEQUENCE
from gmail_sender import GmailSender
from firestore_language_loader import FirestoreLanguageLoader
from deliverability_monitor import DeliverabilityMonitor
from firestore_activity_loader import FirestoreActivityLoader
from firestore_plan_loader import FirestorePlanLoader
import localize_phrase


# ─── DYNAMIC DAILY SEND CAP ──────────────────────────────
# Cap auto-adjusts based on ALL senders' health status.
# During warming phase, bypasses broken Resend health check.
# Volume spread across all 7 senders via round-robin.
HEALTH_CAPS = {
    'green': 420,    # Healthy domain — target 100K/month across 8 senders
    'yellow': 150,   # Caution — moderate volume
    'red': 50,       # Damaged — minimal sends, let warming fix it
    'unknown': 313,  # Post-warming default — 8 senders × 313 = ~2500/day
}

# Absolute ceiling (Resend plan: 100K/month ≈ 3,400/day)
MAX_DAILY_LIMIT = 3400

# Warming phase start date — bypass health checks during first 4 weeks
WARMING_START_DATE = '2026-04-03'
WARMING_PHASE_WEEKS = 4


def _has_recent_metrics(sender_health, max_age_days=7):
    """True if the sender's metrics_history has at least one entry within
    max_age_days. Stale entries (e.g. legacy false-negative red markings)
    return False so the warming bypass can override them."""
    hist = sender_health.get('metrics_history') or []
    if not hist:
        return False
    last = hist[-1]
    raw = last.get('at') or last.get('date') or last.get('timestamp')
    if not raw:
        return False
    try:
        # Accept ISO 8601 with optional 'Z' or just 'YYYY-MM-DD'
        s = raw.rstrip('Z')
        last_dt = datetime.fromisoformat(s) if 'T' in s else datetime.strptime(s, '%Y-%m-%d')
    except (ValueError, TypeError):
        return False
    return (datetime.now() - last_dt).days < max_age_days


def is_warming_phase():
    """Check if we're still in the warming phase (first 4 weeks)."""
    try:
        from datetime import timedelta
        start = datetime.strptime(WARMING_START_DATE, '%Y-%m-%d')
        end = start + timedelta(weeks=WARMING_PHASE_WEEKS)
        return datetime.now() < end
    except Exception:
        return True  # Safe default: assume still warming


def get_all_sender_caps():
    """
    Get per-sender caps for ALL senders in the pool.
    During warming phase: force 'unknown' status (100/sender) to bypass broken health check.
    After warming: use actual health status per sender.
    Returns: list of (sender_dict, cap) tuples and total limit.
    """
    from deliverability_monitor import DeliverabilityMonitor
    pool = DeliverabilityMonitor.SENDER_POOL
    warming = is_warming_phase()

    health_path = Path(__file__).parent.parent / 'cache' / 'sender_health.json'
    config_path = Path(__file__).parent.parent / 'config' / 'warming_config.json'

    # Load health data
    health_data = {}
    if health_path.exists():
        try:
            with open(health_path) as f:
                health_data = json.load(f).get('senders', {})
        except Exception:
            pass

    # Load scaling config
    scaling = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                scaling = json.load(f).get('auto_scaling', {})
        except Exception:
            pass

    sender_caps = []
    total = 0
    for sender in pool:
        if not sender.get('active', True):
            continue
        sender_health = health_data.get(sender['email'], {})
        # Trust the recorded status only if we have FRESH metrics (last 7 days).
        # Stale entries — e.g. the March legacy monitor that recorded
        # opened:0 across the board because no tracking pixel existed —
        # would clamp the cap at 50/sender (red) forever. Falling back to
        # 'unknown' (250/sender) is the right call until update_sender_health.py
        # writes fresh entries from real Resend webhooks.
        if _has_recent_metrics(sender_health):
            status = sender_health.get('status', 'unknown')
        else:
            status = 'unknown'

        # Get cap from config or fallback
        tier = scaling.get(status, {})
        cap = tier.get('marketing_cap_per_domain', HEALTH_CAPS.get(status, 100))
        sender_caps.append((sender, cap))
        total += cap

    total = min(total, MAX_DAILY_LIMIT)
    return sender_caps, total


def get_dynamic_send_limit():
    """
    Calculate today's total send limit across ALL senders.
    """
    try:
        sender_caps, total = get_all_sender_caps()
        warming_label = " [WARMING PHASE — health check bypassed]" if is_warming_phase() else ""
        print(f"   📊 Dynamic cap: {total}/day across {len(sender_caps)} senders{warming_label}")
        for sender, cap in sender_caps:
            print(f"      {sender['email']}: {cap}/day")
        return total

    except Exception as e:
        print(f"   ⚠️ Error reading health config, using fallback cap: {e}")
        return 100  # Safe fallback


# ─── BEHAVIORAL BRANCHING (DISABLED) ───────────────────
# Churning acceleration removed to protect sender reputation.
# All users now follow the normal email sequence and timing.
# Re-engagement emails still exist in cache but are not force-sent.
CHURNING_REMAP = {}  # Disabled — no remapping


# ─── RESTART LOOP (POST-30 RE-ENGAGEMENT) ──────────────
# When a user finishes all 30 emails, wait RESTART_COOLDOWN_DAYS then loop
# back to email #1. Restart cycles use a stretched cadence and a localized
# subject prefix so the inbox experience differs from cycle 1.
RESTART_COOLDOWN_DAYS = 30
MAX_CYCLES = 3  # Lifetime cap — ~90 emails max before we retire the user.
RESTART_MIN_HOURS_BETWEEN = 7 * 24  # 7 days between emails on cycle 2+.
# Users frozen mid-sequence (classified churning, blocked at emails_sent >= 3)
# get a fresh restart cycle once they've been silent this long.
CHURNING_RESET_DAYS = 30

# Identity-shift emails don't fit on a restart — remap them to re-engagement
# emails that already live in the cache.
CYCLE_RESTART_REMAP = {
    13: 22,  # milestone_checkin → comeback_trigger
    21: 26,  # loyalty_farewell → referral_trigger
    30: 29,  # legacy_mission → gratitude_exclusive
}

# ─── ATTRIBUTION HELPERS ───────────────────────────────
# Salt for hashing email addresses into opaque ref_ids that ride on Resend
# webhooks (X-Entity-Ref-ID). Lets us join click/open events back to users
# without putting raw addresses in tag values.
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Slug map for app names — Resend tag values are restricted to [A-Za-z0-9_-]
# and we want short stable identifiers in analytics.
_APP_SLUGS = {
    'Predictify': 'predictify',
    'Thesis Generator': 'thesis',
    'Red Flag Scanner AI': 'redflag',
    'Volume Booster - Sound Booster': 'volume_booster',
    'Fresh Start: Breakup Therapy': 'fresh_start',
    'SoulPlan: Plan Dates Together': 'soulplan',
    'PupShape: Dog Weight Loss Plan': 'pupshape',
    'Predictify: Horse Racing AI': 'horse_racing',
    'Smart Notes - AI Meeting Summary': 'smart_notes',
}


def app_slug(app_name: str) -> str:
    if app_name in _APP_SLUGS:
        return _APP_SLUGS[app_name]
    return re.sub(r'[^a-z0-9_]', '_', app_name.lower())[:32]


def user_ref(email: str) -> str:
    """Stable opaque user identifier for webhook correlation."""
    h = hashlib.sha256(f"{_REF_SALT}:{email.lower().strip()}".encode()).hexdigest()
    return h[:16]


def with_utm(url: str, *, app: str, email_num, cycle, language: str, ref: str, kind: str = 'retention') -> str:
    """Append UTM + ref params to a CTA URL, preserving any existing query."""
    if not url:
        return url
    try:
        parts = urlparse(url)
    except ValueError:
        return url
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    existing.update({
        'utm_source': 'resend',
        'utm_medium': 'email',
        'utm_campaign': f'{kind}_e{email_num}',
        'utm_content': f'cycle{cycle}_{language}',
        'utm_term': app,
        'ref': ref,
    })
    return urlunparse(parts._replace(query=urlencode(existing)))


def build_tags(*, app: str, email_num, cycle, language: str, segment: str, kind: str = 'retention') -> list:
    """Build Resend tag list for analytics slicing on every webhook event."""
    return [
        {'name': 'app', 'value': app},
        {'name': 'kind', 'value': kind},
        {'name': 'email_num', 'value': str(email_num)},
        {'name': 'cycle', 'value': str(cycle)},
        {'name': 'language', 'value': language or 'en'},
        {'name': 'segment', 'value': segment or 'normal'},
    ]


CYCLE_SUBJECT_PREFIX = {
    'en': 'Checking back in — ',
    'es': 'Volvemos a conectar — ',
    'fr': 'On se reconnecte — ',
    'pt': 'Voltando a falar — ',
    'pp': 'Voltando a falar — ',
    'de': 'Wir melden uns zurück — ',
    'ar': 'نتواصل معك مجددًا — ',
    'tr': 'Tekrar merhaba — ',
    'it': 'Ci risentiamo — ',
    'hi': 'फिर से जुड़ते हैं — ',
    'id': 'Kami kembali — ',
    'nl': 'We zijn er weer — ',
    'pl': 'Wracamy — ',
    'ja': 'またこんにちは — ',
    'zh': '再次联系 — ',
    'ru': 'Снова на связи — ',
}


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
        self.plan_loader = FirestorePlanLoader()
        self.user_languages = {}   # email -> language code
        self.user_activity = {}    # email -> {streak, favoriteLeague, isSubscribed, ...}
        # email -> dict from FirestorePlanLoader (first_name, topic, days_left,
        # work_type, pain, ...). Populated for apps that write a `plan` map
        # to their Firestore users collection (currently Thesis Generator).
        self.user_plans = {}
        
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
            # Try env vars first (GitHub Actions), then config file fallback
            url = os.environ.get('SUPABASE_URL', '')
            key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
            
            if not url or not key:
                config_path = self.base_dir / 'config' / 'supabase_config.json'
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    url = config['project']['url']
                    key = config['project']['service_role_key']
                else:
                    print("   ⚠️ No Supabase credentials — skipping welcomed_users check")
                    return self._welcomed_emails
            
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
    
    def _build_html(self, email_data, app_info, language='en', sender_name='Ana',
                     *, email_num=1, cycle=1, ref_id='', kind='retention'):
        """Build beautiful HTML email from generated content, with language support.
        UTM-tags every CTA so clicks attribute back to (app, email_num, cycle, language)
        and to the user (via ref_id)."""

        app_name = email_data.get('app_name', app_info['name'])
        cta_text = email_data.get('cta_text', f'Open {app_name}')
        slug = app_slug(app_name)
        
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
        
        # CTA button - link to app store, UTM-tagged for click attribution
        raw_app_store = app_info.get('app_store_url', '')
        raw_google_play = app_info.get('google_play_url', '')
        app_store_url = with_utm(raw_app_store, app=slug, email_num=email_num,
                                  cycle=cycle, language=language, ref=ref_id, kind=kind) if raw_app_store else ''
        google_play_url = with_utm(raw_google_play, app=slug, email_num=email_num,
                                    cycle=cycle, language=language, ref=ref_id, kind=kind) if raw_google_play else ''
        is_web_app = raw_app_store and not any(x in raw_app_store for x in ['apps.apple.com', 'play.google.com'])
        
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
        <p style="margin:0 0 8px;font-size:12px;color:#d1d5db;">
            {footer_text}
        </p>
        <p style="margin:0;font-size:12px;color:#9ca3af;">
            <a href="%mailing_list_unsubscribe_url%" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>
        </p>
    </div>
    
</body>
</html>'''
        
        return html

    # ─── PERSONALIZATION ───────────────────────────────────

    def _personalize_email(self, email_data, user_plan, language):
        """Return a copy of email_data with {{placeholder}} tokens replaced
        using the user's plan (first name, topic, deadline, work type, pain).

        Cached templates can include any of:
            {{first_name}}  {{topic}}  {{days_left}}  {{streak}}
            {{progress}}    {{work_type}}             {{pain_hook}}

        Empty values collapse cleanly so the email never reads "Hi , ..." for
        a user without a first name.
        """
        if not email_data:
            return email_data
        if not user_plan:
            # No plan data → nothing to interpolate. Return as-is to avoid
            # the overhead of copying.
            return email_data

        result = dict(email_data)
        for key in ('subject', 'preview_text', 'cta_text'):
            if key in result and isinstance(result[key], str):
                result[key] = localize_phrase.interpolate(language, result[key], user_plan)

        paragraphs = result.get('body_paragraphs')
        if isinstance(paragraphs, list):
            result['body_paragraphs'] = [
                localize_phrase.interpolate(language, p, user_plan) if isinstance(p, str) else p
                for p in paragraphs
            ]
        return result

    def _load_cached_email(self, app_name, email_num, language, cycle):
        """Load the cached email body, preferring a fresh cycle-2 template
        for apps that have generated them. Falls back to the cycle-1 cache
        (with the existing CYCLE_RESTART_REMAP behaviour) otherwise.

        Cycle-2 cache files use the convention:
            thesis_generator_cycle2_email_{N}.json           (en)
            thesis_generator_{lang}_cycle2_email_{N}.json    (other langs)
        and exist for N in 1..5. Anything beyond that falls back to the
        remap path.
        """
        if cycle >= 2:
            slug = re.sub(r'[^a-z0-9]+', '_', app_name.lower()).strip('_')
            cache_dir = Path(__file__).parent.parent / 'cache' / 'retention_emails'
            # Map the first 5 emails of the restart cycle to cycle-2 fresh
            # templates if they exist. Higher email numbers fall back below.
            if 1 <= email_num <= 5:
                if language and language != 'en':
                    path = cache_dir / f'{slug}_{language}_cycle2_email_{email_num}.json'
                else:
                    path = cache_dir / f'{slug}_cycle2_email_{email_num}.json'
                if path.exists():
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except Exception as e:
                        print(f"   ⚠️ Cycle-2 cache read failed for {path.name}: {e}")
        # Fall back to standard generator cache (already has English fallback).
        return self.email_generator.get_email(app_name, email_num, language=language, cache_only=True)

    # Sequence positions that get the pain-mirror empathy prefix. These
    # land roughly on days 2 / 4 / 7 in the cadence — early enough to
    # establish "this app gets me" without overusing the device.
    _PAIN_MIRROR_EMAIL_NUMS = {2, 3, 4}

    def _apply_pain_mirror(self, email_data, user_plan, email_num):
        """Prepend a localized empathy sentence ({{pain_hook}}) to the first
        body paragraph when this email is one of the pain-mirror slots and
        the user has a pain set. The hook itself is resolved later in
        _personalize_email's interpolation step."""
        if email_num not in self._PAIN_MIRROR_EMAIL_NUMS:
            return email_data
        if not user_plan or not user_plan.get('pain'):
            return email_data
        paragraphs = email_data.get('body_paragraphs')
        if not isinstance(paragraphs, list) or not paragraphs:
            return email_data
        first = paragraphs[0]
        if not isinstance(first, str) or '{{pain_hook}}' in first:
            return email_data
        new_paragraphs = list(paragraphs)
        new_paragraphs[0] = '{{pain_hook}} ' + first
        result = dict(email_data)
        result['body_paragraphs'] = new_paragraphs
        return result

    # ─── ACTIVE APPS (only these receive emails) ─────────
    # Priority order: first = highest tie-breaker priority for daily cap
    # allocation WITHIN a user-priority tier. App priority does NOT trump
    # user priority — a new user of any active app still beats a cycle-2
    # user of Predictify.
    ACTIVE_APPS = [
        'Predictify',
        'Thesis Generator',
        'Predictify: Horse Racing AI',
        'Volume Booster - Sound Booster',
        'Red Flag Scanner AI',
        'Fresh Start: Breakup Therapy',
        'SoulPlan: Plan Dates Together',
        'PupShape: Dog Weight Loss Plan',
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
    
    def _get_email_for_segment(self, next_email_num, segment, is_subscribed=False, cycle=1):
        """
        Get the actual email number to send based on user segment.
        Churning users get re-engagement emails instead of deepening emails.
        Subscribed users skip heavy upsell emails.
        On restart cycles (cycle > 1), identity-shift emails are remapped to
        re-engagement emails.
        Returns: (actual_email_num, remapped: bool)
        """
        if cycle > 1 and next_email_num in CYCLE_RESTART_REMAP:
            return CYCLE_RESTART_REMAP[next_email_num], True
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
        
        # Build priority-ordered list using a 3-tier user priority, with
        # app order as the tie-breaker WITHIN a tier.
        #
        # Tier 0 — never seen before (about to get email #1)
        # Tier 1 — cycle 1 mid-sequence (active 30-email funnel)
        # Tier 2 — cycle 2+ (restart loop / churning rescue) — lowest priority
        #
        # Welcome emails for brand-new Firebase users are handled separately
        # by the Supabase pg_cron path, so tier 0 here is purely about the
        # retention funnel claiming the new user's slot for email #1.
        ordered_entries = []  # ((user_tier, app_priority), app_name, user)

        for app_name, users in users_by_app.items():
            if app_name not in self.ACTIVE_APPS:
                continue

            app_priority = self.ACTIVE_APPS.index(app_name)

            for user in users:
                email = user['email']
                user_state = self.state.get('users', {}).get(email)
                if user_state is None:
                    user_tier = 0  # not in state yet
                else:
                    cycle = user_state.get('cycle', 1)
                    emails_sent = user_state.get('emails_sent', 0)
                    if cycle >= 2 or emails_sent >= 30:
                        user_tier = 2  # restart loop / churning rescue
                    else:
                        user_tier = 1  # cycle 1 mid-sequence

                ordered_entries.append(((user_tier, app_priority), app_name, user))

        # Sort by (user_tier, app_priority) — tier dominates, app breaks ties.
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

            # Skip if v2 already sent a behavioral email today.
            if email in getattr(self, '_v2_handled_emails', set()):
                continue

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
                cycle = user_state.get('cycle', 1)

                # Finished all 30 — restart after cooldown, up to MAX_CYCLES
                if emails_sent >= 30:
                    if cycle >= MAX_CYCLES:
                        continue
                    completed_at_str = (
                        user_state.get('cycle_completed_at')
                        or user_state.get('last_email_sent')
                    )
                    if not completed_at_str:
                        # Backfill so the cooldown window starts now
                        user_state['cycle_completed_at'] = now.isoformat()
                        continue
                    try:
                        completed_at = datetime.fromisoformat(completed_at_str)
                    except ValueError:
                        continue
                    if (now - completed_at).days < RESTART_COOLDOWN_DAYS:
                        continue
                    # Kick off the next cycle — reset progression, bump counter
                    cycle += 1
                    user_state['cycle'] = cycle
                    user_state['emails_sent'] = 0
                    user_state['last_email_sent'] = None
                    user_state.pop('cycle_completed_at', None)
                    emails_sent = 0

                # Stuck mid-sequence (churning-frozen at emails_sent >= 3 and
                # silent for CHURNING_RESET_DAYS) — treat like cycle completion
                # and restart into the cycle-2+ rails (7-day cadence, prefix).
                elif emails_sent >= 3 and cycle < MAX_CYCLES:
                    last_sent_str = user_state.get('last_email_sent')
                    if last_sent_str:
                        try:
                            last_sent_dt = datetime.fromisoformat(last_sent_str)
                        except ValueError:
                            last_sent_dt = None
                        if last_sent_dt and (now - last_sent_dt).days >= CHURNING_RESET_DAYS:
                            cycle += 1
                            user_state['cycle'] = cycle
                            user_state['emails_sent'] = 0
                            user_state['last_email_sent'] = None
                            user_state.pop('cycle_completed_at', None)
                            emails_sent = 0

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
                        'cycle': cycle,
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
                    if cycle > 1:
                        hours_to_wait = max(RESTART_MIN_HOURS_BETWEEN, days_to_wait * 24)
                    else:
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

                # Get actual email to send (may be remapped for churning / restart cycle)
                actual_email, remapped = self._get_email_for_segment(
                    next_email_num, segment, is_subscribed, cycle=cycle
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
                    'cycle': cycle,
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

        # 0. v2 trigger pass first (Predictify only). Personalized,
        # behavior-driven emails fire before the static v1 sequence so
        # high-priority sends (streak savers, match-day) land at the right
        # moment. Users handled by v2 are recorded in cache/predictify_v2_state.json
        # and skipped by the v1 loop below for the rest of today.
        try:
            from predictify_v2.orchestrator import run as run_v2
            v2_sent = run_v2(dry_run=dry_run)
            self._v2_handled_emails = {e for e, _kind in v2_sent}
            print(f"   v2 handled {len(self._v2_handled_emails)} users")
        except Exception as e:
            print(f"   ⚠️ v2 pass failed (continuing with v1): {e}")
            self._v2_handled_emails = set()

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
            'Thesis Generator': 'Thesis Generator',
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

        # 1b3. Load per-user plan data for Thesis Generator personalization
        # (first name, topic, deadline, work type, pain). Drives the
        # {{placeholder}} interpolation done at send time.
        if 'Thesis Generator' in users_by_app:
            print("\n📋 Loading Thesis Generator user plans from Firestore...")
            self.user_plans.update(self.plan_loader.fetch_user_plans('Thesis Generator'))
        
        # 1c. Get all senders for multi-sender distribution
        print("\n🏥 Setting up multi-sender distribution...")
        sender_caps, total_cap = get_all_sender_caps()
        print(f"   📨 Using {len(sender_caps)} senders, total cap: {total_cap}/day")
        for s, cap in sender_caps:
            print(f"      {s['email']} ({s['name']}): {cap}/day")
        
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
        # Track (app_name, email_num, language, cycle). Cycle 2+ users may
        # be served fresh cycle-2 templates if available (Thesis Generator).
        needed_emails = set()
        for e in eligible:
            lang = e.get('language', 'en')
            actual = e.get('actual_email', e['next_email'])
            cycle = e.get('cycle', 1)
            needed_emails.add((e['app_name'], actual, lang, cycle))

        email_content = {}
        for app_name, email_num, lang, cycle in needed_emails:
            email_data = self._load_cached_email(app_name, email_num, lang, cycle)
            if email_data:
                email_content[(app_name, email_num, lang, cycle)] = email_data
                lang_label = f" ({lang})" if lang != 'en' else ''
                cycle_label = f" c{cycle}" if cycle > 1 else ''
                print(f"   ✅ {app_name} #{email_num}{lang_label}{cycle_label}: {email_data['subject'][:50]}...")
            else:
                print(f"   ❌ Not cached: {app_name} #{email_num} ({lang}) — run --generate first")
        
        # 4. Send emails via Resend — MULTI-SENDER round-robin
        print(f"\n📧 Sending {len(eligible)} emails via Resend (multi-sender)...")
        
        # Create a GmailSender instance per sender
        senders = []
        for sender_info, cap in sender_caps:
            gs = GmailSender(
                sender_email=sender_info['email'],
                sender_name=sender_info['name'],
            )
            if gs.connect():
                senders.append({'gmail': gs, 'info': sender_info, 'cap': cap, 'sent': 0})
            else:
                print(f"   ⚠️ Could not connect sender {sender_info['email']} — skipping")
            time.sleep(0.5)  # Avoid Resend rate limit on connect
        
        if not senders:
            print("❌ Cannot connect to any Resend sender. Aborting.")
            return
        
        print(f"   ✅ {len(senders)} senders ready")
        
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.state['daily_stats']:
            self.state['daily_stats'][today] = {'sent': 0, 'failed': 0}
        
        # Enforce dynamic daily send cap
        daily_limit = get_dynamic_send_limit()
        already_sent_today = self.state['daily_stats'][today].get('sent', 0)
        remaining_cap = max(0, daily_limit - already_sent_today)
        if remaining_cap == 0:
            print(f"   🛑 Daily send cap reached ({daily_limit}). Skipping this run.")
            return
        if remaining_cap < len(eligible):
            print(f"   ⚠️ Cap allows {remaining_cap} more emails today (limit: {daily_limit}, already sent: {already_sent_today})")
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
            cycle = entry.get('cycle', 1)

            email_data = email_content.get((app_name, actual_num, lang, cycle))
            if not email_data:
                failed += 1
                continue

            # Round-robin sender selection — pick sender with lowest sent count
            # that hasn't hit its per-domain cap
            available = [s for s in senders if s['sent'] < s['cap']]
            if not available:
                print(f"   🛑 All sender caps exhausted after {sent} emails")
                break
            sender_slot = min(available, key=lambda s: s['sent'])
            sender_info = sender_slot['info']

            # Per-send attribution context
            ref_id = user_ref(email_addr)
            slug = app_slug(app_name)
            tags = build_tags(app=slug, email_num=email_num, cycle=cycle,
                               language=lang, segment=segment, kind='retention')

            # Personalize at send time. Each cached email body can contain
            # tokens like {{first_name}}, {{topic}}, {{days_left}},
            # {{work_type}}, {{pain_hook}} — interpolate them now using the
            # user's plan (if available). Apps without a plan loader return
            # an empty dict and the tokens collapse cleanly.
            user_plan = self.user_plans.get(email_addr) or {}
            # Pain-mirror routing: for the early-sequence emails (#2, #3, #4)
            # the first paragraph is prefixed with an empathy sentence based
            # on the user's selected pain. Localized in localize_phrase.
            pain_email_data = self._apply_pain_mirror(email_data, user_plan, email_num)
            personalized_email_data = self._personalize_email(pain_email_data, user_plan, lang)

            # Build HTML (CTAs UTM-tagged with the same context)
            html = self._build_html(personalized_email_data, app_info, lang,
                                     sender_name=sender_info['name'],
                                     email_num=email_num, cycle=cycle,
                                     ref_id=ref_id, kind='retention')

            # On restart cycles, prefix the subject so the inbox reads differently
            subject = personalized_email_data['subject']
            if cycle > 1:
                prefix = CYCLE_SUBJECT_PREFIX.get(lang, CYCLE_SUBJECT_PREFIX['en'])
                if not subject.startswith(prefix):
                    subject = prefix + subject

            # Send via this sender's connection
            result = sender_slot['gmail'].send_email(
                to_email=email_addr,
                subject=subject,
                html_body=html,
                from_name=app_name,
                tags=tags,
                ref_id=ref_id,
            )
            
            if result == 'sent':
                sent += 1
                sender_slot['sent'] += 1
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
                self.state['users'][email_addr]['sender'] = sender_info['email']
                self.state['users'][email_addr]['cycle'] = cycle
                if email_num >= 30:
                    self.state['users'][email_addr]['cycle_completed_at'] = now_str
                self.state['daily_stats'][today]['sent'] += 1

                remap_note = f" (re-engage #{actual_num})" if entry.get('remapped') else ""
                cycle_note = f" c{cycle}" if cycle > 1 else ""
                sender_tag = sender_info['email'].split('@')[1]
                print(f"   ✅ [{sent}/{len(eligible)}] {email_addr} ← {app_name} #{email_num}{cycle_note} via {sender_tag}{remap_note} [{segment}]")
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
            
            # Rate limit
            if i < len(eligible) - 1:
                time.sleep(1)
        
        # Disconnect all senders
        for s in senders:
            s['gmail'].disconnect()
        
        # Print per-sender breakdown
        print(f"\n   📨 Per-sender breakdown:")
        for s in senders:
            print(f"      {s['info']['email']}: {s['sent']}/{s['cap']} sent")
        
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
        
        # Set up multi-sender
        sender_caps, _ = get_all_sender_caps()
        senders = []
        for sender_info, cap in sender_caps:
            gs = GmailSender(sender_email=sender_info['email'], sender_name=sender_info['name'])
            if gs.connect():
                senders.append({'gmail': gs, 'info': sender_info, 'sent': 0})
        
        if not senders:
            print("❌ Cannot connect to any Resend sender. Aborting.")
            return
        
        # Get user languages
        languages = self.language_loader.fetch_user_languages('Predictify')
        app_info = self.firebase_loader.get_app_info('Predictify')
        
        sent = 0
        for user in streak_users:
            email_addr = user['email']
            streak = user['streak']
            lang = languages.get(email_addr, 'en')
            
            # Round-robin sender
            sender_slot = min(senders, key=lambda s: s['sent'])
            sender_info = sender_slot['info']
            
            # Build streak email (UTM-tag CTAs, attribute via tags + ref)
            ref_id = user_ref(email_addr)
            tags = build_tags(app='predictify', email_num=streak, cycle=1,
                               language=lang, segment='streak', kind='streak')
            html = self._build_streak_html(streak, lang, app_info, sender_info['name'],
                                            ref_id=ref_id)
            subject = self._get_streak_subject(streak, lang)

            result = sender_slot['gmail'].send_email(
                to_email=email_addr,
                subject=subject,
                html_body=html,
                from_name='Predictify',
                tags=tags,
                ref_id=ref_id,
            )
            
            if result == 'sent':
                sent += 1
                sender_slot['sent'] += 1
                if email_addr not in self.state['users']:
                    self.state['users'][email_addr] = {'app': 'Predictify', 'emails_sent': 0}
                self.state['users'][email_addr]['last_streak_email'] = now.isoformat()
                print(f"   🔥 {email_addr} (streak: {streak}) via {sender_info['email'].split('@')[1]}")
            
            time.sleep(1)
        
        for s in senders:
            s['gmail'].disconnect()
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
    
    def _build_streak_html(self, streak, lang, app_info, sender_name, *, ref_id=''):
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
        
        # Build CTA (UTM-tagged for click attribution)
        raw_app_store = app_info.get('app_store_url', '')
        raw_google_play = app_info.get('google_play_url', '')
        app_store_url = with_utm(raw_app_store, app='predictify', email_num=streak,
                                  cycle=1, language=lang, ref=ref_id, kind='streak') if raw_app_store else ''
        google_play_url = with_utm(raw_google_play, app='predictify', email_num=streak,
                                    cycle=1, language=lang, ref=ref_id, kind='streak') if raw_google_play else ''

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
        
        # Set up multi-sender
        sender_caps, _ = get_all_sender_caps()
        senders = []
        for sender_info, cap in sender_caps:
            gs = GmailSender(sender_email=sender_info['email'], sender_name=sender_info['name'])
            if gs.connect():
                senders.append({'gmail': gs, 'info': sender_info, 'sent': 0})
        
        if not senders:
            print("❌ Cannot connect to any Resend sender. Aborting.")
            return
        
        languages = self.language_loader.fetch_user_languages('Predictify')
        app_info = self.firebase_loader.get_app_info('Predictify')
        
        sent = 0
        for league, user_emails in users_by_league.items():
            for email_addr in user_emails:
                lang = languages.get(email_addr, 'en')
                # Round-robin sender
                sender_slot = min(senders, key=lambda s: s['sent'])
                sender_info = sender_slot['info']
                
                ref_id = user_ref(email_addr)
                league_slug = re.sub(r'[^A-Za-z0-9_-]', '_', league)[:32] or 'league'
                tags = build_tags(app='predictify', email_num=league_slug, cycle=1,
                                   language=lang, segment='matchday', kind='matchday')
                html = self._build_matchday_html(league, lang, app_info, sender_info['name'],
                                                  ref_id=ref_id)
                subject = self._get_matchday_subject(league, lang)

                result = sender_slot['gmail'].send_email(
                    to_email=email_addr,
                    subject=subject,
                    html_body=html,
                    from_name='Predictify',
                    tags=tags,
                    ref_id=ref_id,
                )
                
                if result == 'sent':
                    sent += 1
                    sender_slot['sent'] += 1
                    if email_addr not in self.state['users']:
                        self.state['users'][email_addr] = {'app': 'Predictify', 'emails_sent': 0}
                    self.state['users'][email_addr]['last_matchday_email'] = now.isoformat()
                    prev_count = self.state['users'][email_addr].get('matchday_emails_this_week', 0)
                    self.state['users'][email_addr]['matchday_emails_this_week'] = prev_count + 1
                    print(f"   ⚽ {email_addr} ← {league} via {sender_info['email'].split('@')[1]}")
                
                time.sleep(1)
        
        for s in senders:
            s['gmail'].disconnect()
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
    
    def _build_matchday_html(self, league, lang, app_info, sender_name, *, ref_id=''):
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
        
        league_slug = re.sub(r'[^A-Za-z0-9_-]', '_', league)[:32] or 'league'
        raw_app_store = app_info.get('app_store_url', '')
        raw_google_play = app_info.get('google_play_url', '')
        app_store_url = with_utm(raw_app_store, app='predictify', email_num=league_slug,
                                  cycle=1, language=lang, ref=ref_id, kind='matchday') if raw_app_store else ''
        google_play_url = with_utm(raw_google_play, app='predictify', email_num=league_slug,
                                    cycle=1, language=lang, ref=ref_id, kind='matchday') if raw_google_play else ''

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
    
    # ─── UPSELL TRIGGER ────────────────────────────────────
    # Constants for paid-conversion email triggers (separate from the 30-email
    # rapport sequence). Sent on schedule when a user is past the activation
    # phase but hasn't subscribed yet.
    UPSELL_APPS = ['Predictify', 'Thesis Generator', 'Predictify: Horse Racing AI']
    MIN_RETENTION_BEFORE_UPSELL = 5    # Need rapport before pitching
    UPSELL_COOLDOWN_DAYS = 14          # Min days between upsells per user
    MAX_UPSELLS_PER_USER = 3           # Lifetime cap (we have 3 variants)

    def run_upsell_triggers(self, dry_run=False):
        """
        Send paid-conversion upsell emails to free users on revenue-eligible
        apps (Predictify, Thesis Generator, Predictify Horse Racing).

        Eligibility:
          - On an UPSELL_APP
          - Has received >= MIN_RETENTION_BEFORE_UPSELL retention emails (rapport built)
          - Not currently subscribed (isSubscribed=False from Firestore activity)
          - Not received an upsell in the last UPSELL_COOLDOWN_DAYS
          - Hasn't hit MAX_UPSELLS_PER_USER lifetime
          - Not suppressed

        Each user receives variants 1, 2, 3 in order across their lifetime.
        """
        print("=" * 60)
        print("💰 UPSELL TRIGGER EMAILS (paid-conversion)")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        # 1. Refresh Firebase exports to pick up new signups + load activity
        self.firebase_loader.refresh_exports()
        users_by_app = self.firebase_loader.load_users_by_app()
        # Track which apps have usable subscription data — without it we can't
        # filter out paid users and would pitch them by mistake. Apps with
        # empty activity get skipped entirely (safer than sending to subscribers).
        apps_with_activity = set()
        for app_name in self.UPSELL_APPS:
            if app_name in users_by_app:
                activity = self.activity_loader.fetch_user_activity(app_name)
                if activity:
                    self.user_activity.update(activity)
                    apps_with_activity.add(app_name)
                else:
                    print(f"   ⚠️ {app_name}: no activity data — skipping upsell to avoid pitching paid users")

        # Languages (so non-English users get the right cache file or English fallback)
        for app_name in self.UPSELL_APPS:
            if app_name in users_by_app:
                langs = self.language_loader.fetch_user_languages(app_name)
                self.user_languages.update(langs)
                for u in users_by_app.get(app_name, []):
                    u['language'] = self.user_languages.get(u['email'], 'en')

        # 2. Find eligible users
        now = datetime.now()
        eligible = []
        for app_name in self.UPSELL_APPS:
            if app_name not in apps_with_activity:
                continue  # Safety guard — no subscription data, don't risk it
            for user in users_by_app.get(app_name, []):
                email = user['email']
                user_state = self.state['users'].get(email)
                if not user_state or user_state.get('suppressed'):
                    continue
                if user_state.get('emails_sent', 0) < self.MIN_RETENTION_BEFORE_UPSELL:
                    continue

                upsell_count = user_state.get('upsell_count', 0)
                if upsell_count >= self.MAX_UPSELLS_PER_USER:
                    continue

                # Cooldown check
                last_upsell = user_state.get('last_upsell_email')
                if last_upsell:
                    try:
                        last_dt = datetime.fromisoformat(last_upsell)
                        if (now - last_dt).days < self.UPSELL_COOLDOWN_DAYS:
                            continue
                    except ValueError:
                        pass

                # Skip already-subscribed users — pitching them is wasted
                activity = self.user_activity.get(email, {})
                if activity.get('isSubscribed') or activity.get('isPremium'):
                    continue

                variant = upsell_count + 1  # 1, 2, or 3
                eligible.append({
                    'email': email,
                    'app_name': app_name,
                    'variant': variant,
                    'language': user.get('language', 'en'),
                })

        # 3. Group + report
        by_app = {}
        for e in eligible:
            by_app.setdefault(e['app_name'], []).append(e)
        print(f"\n💰 {len(eligible)} users eligible for upsell:")
        for app, users in sorted(by_app.items(), key=lambda x: -len(x[1])):
            variants = {}
            for u in users:
                variants[u['variant']] = variants.get(u['variant'], 0) + 1
            v_str = ', '.join(f"v{k}:{v}" for k, v in sorted(variants.items()))
            print(f"   {app}: {len(users)} ({v_str})")

        if dry_run or not eligible:
            print("\n🏁 DRY RUN — no emails sent" if dry_run else "\n✅ Nobody eligible right now.")
            return

        # 4. Set up multi-sender + load templates
        sender_caps, _ = get_all_sender_caps()
        senders = []
        for sender_info, cap in sender_caps:
            gs = GmailSender(sender_email=sender_info['email'], sender_name=sender_info['name'])
            if gs.connect():
                senders.append({'gmail': gs, 'info': sender_info, 'cap': cap, 'sent': 0})
            time.sleep(0.5)
        if not senders:
            print("❌ No senders connectable")
            return

        # Load upsell templates per (app, variant, language)
        templates = {}
        needed = set((e['app_name'], e['variant'], e.get('language', 'en')) for e in eligible)
        for app_name, variant, lang in needed:
            t = self._load_upsell_template(app_name, variant, lang)
            if t:
                templates[(app_name, variant, lang)] = t
            else:
                print(f"   ⚠️ No template for {app_name} upsell #{variant} ({lang})")

        # 5. Send + update state
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.state['daily_stats']:
            self.state['daily_stats'][today] = {'sent': 0, 'failed': 0}

        sent = 0
        failed = 0
        for entry in eligible:
            email_addr = entry['email']
            app_name = entry['app_name']
            variant = entry['variant']
            lang = entry.get('language', 'en')

            template = templates.get((app_name, variant, lang))
            if not template:
                failed += 1
                continue

            # Round-robin sender (within their daily cap)
            available = [s for s in senders if s['sent'] < s['cap']]
            if not available:
                print(f"   🛑 All sender caps exhausted after {sent} upsells")
                break
            sender_slot = min(available, key=lambda s: s['sent'])
            sender_info = sender_slot['info']

            ref_id = user_ref(email_addr)
            slug = app_slug(app_name)
            tags = build_tags(app=slug, email_num=f'upsell{variant}', cycle=1,
                               language=lang, segment='upsell', kind='upsell')
            app_info = self.firebase_loader.get_app_info(app_name)
            html = self._build_html(template, app_info, lang,
                                     sender_name=sender_info['name'],
                                     email_num=f'upsell{variant}', cycle=1,
                                     ref_id=ref_id, kind='upsell')
            result = sender_slot['gmail'].send_email(
                to_email=email_addr,
                subject=template['subject'],
                html_body=html,
                from_name=app_name,
                tags=tags,
                ref_id=ref_id,
            )

            if result == 'sent':
                sent += 1
                sender_slot['sent'] += 1
                now_str = datetime.now().isoformat()
                self.state['users'][email_addr]['upsell_count'] = variant
                self.state['users'][email_addr]['last_upsell_email'] = now_str
                self.state['daily_stats'][today]['sent'] += 1
                print(f"   💰 [{sent}/{len(eligible)}] {email_addr} ← {app_name} upsell #{variant} ({lang})")
            elif result == 'bounced':
                failed += 1
                if email_addr in self.state['users']:
                    del self.state['users'][email_addr]
                self.state['daily_stats'][today]['failed'] += 1
            else:
                failed += 1
                self.state['daily_stats'][today]['failed'] += 1

            if (sent + failed) % 25 == 0:
                self._save_state()
            time.sleep(1)

        for s in senders:
            s['gmail'].disconnect()
        self._save_state()
        print(f"\n📊 Upsells sent: {sent} | failed: {failed}")

    def _load_upsell_template(self, app_name, variant, language='en'):
        """Load upsell email template from cache. Falls back to English if
        a language-specific variant isn't cached yet."""
        slug_map = {
            'Predictify': 'predictify',
            'Thesis Generator': 'thesis_generator',
            'Predictify: Horse Racing AI': 'horse_racing',
        }
        slug = slug_map.get(app_name)
        if not slug:
            return None
        base = self.base_dir / 'cache' / 'retention_emails'
        # Try language-specific first, then English fallback
        for lang_try in ([language] if language == 'en' else [language, 'en']):
            if lang_try == 'en':
                path = base / f'{slug}_upsell_{variant}.json'
            else:
                path = base / f'{slug}_{lang_try}_upsell_{variant}.json'
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        return None

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
    
    elif '--streak' in sys.argv:
        # Streak trigger emails
        dry_run = '--dry-run' in sys.argv or '--streak-dry' in sys.argv
        emailer.run_streak_triggers(dry_run=dry_run)

    elif '--matchday' in sys.argv:
        # Match-day trigger emails
        dry_run = '--dry-run' in sys.argv or '--matchday-dry' in sys.argv
        emailer.run_matchday_triggers(dry_run=dry_run)

    elif '--upsell' in sys.argv:
        # Paid-conversion upsell emails (Predictify + Thesis + Horse Racing)
        dry_run = '--dry-run' in sys.argv or '--upsell-dry' in sys.argv
        emailer.run_upsell_triggers(dry_run=dry_run)

    elif '--dry-run' in sys.argv:
        emailer.run_campaign(dry_run=True)

    else:
        emailer.run_campaign()
