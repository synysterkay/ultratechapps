#!/usr/bin/env python3
"""
Email Sender — Resend (default), Mailgun, SMTP2GO, or ZeptoMail.

Set EMAIL_PROVIDER=zeptomail + ZEPTOMAIL_API_KEY.
Routes by app tag: thesis → thesisgenerator.io, predictify → predictifyfootball.com.
Set EMAIL_PROVIDER=smtp2go + SMTP2GO_API_KEY for multi-domain SMTP2GO sends.
Set EMAIL_PROVIDER=mailgun + MAILGUN_* to pin to passedai.io (legacy bridge).

Drop-in interface: connect(), send_email(), send_batch(), disconnect().
"""
import time
import os
import re
import json
import hashlib
import requests
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


_TAG_VALUE_RE = re.compile(r'[^A-Za-z0-9_-]')


def _sanitize_tag(value: str) -> str:
    """Resend tag values only allow [A-Za-z0-9_-]; replace anything else with '_'."""
    return _TAG_VALUE_RE.sub('_', value)


def _sanitize_subject(subject: str, max_len: int = 2000) -> str:
    """Resend rejects newlines and subjects over 2000 chars."""
    s = re.sub(r'[\r\n]+', ' ', subject or '').strip()
    if len(s) > max_len:
        s = s[: max_len - 1] + '…'
    return s


SKIP_RESULTS = {'duplicate', 'suppressed', 'throttled'}


def _tag_dict(tags):
    return {
        str(t.get('name')): str(t.get('value'))
        for t in (tags or [])
        if t.get('name') and t.get('value') is not None
    }


def _utc_now():
    return datetime.now(timezone.utc)


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def _is_thesis_app(app):
    return app in {'thesis', 'thesis_generator'}


def _is_predictify_app(app):
    return app in {'predictify', 'predictify_nba', 'horse_racing', 'predictify_crypto'}


def _is_breakup_app(app):
    return app in {'fresh_start', 'breakup_therapy', 'red_flag_scanner', 'redflag', 'soulplan'}


def _is_soulplan_app(app):
    return app in {'soulplan'}


def _is_selka_app(app):
    return app in {'red_flag_scanner', 'redflag'}


def _is_zeptomail_allowed_app(app):
    """Apps permitted to send when EMAIL_PROVIDER=zeptomail."""
    return _is_thesis_app(app) or _is_predictify_app(app) or _is_breakup_app(app)


def warming_app_for_sender(sender_email):
    """Map a From address to the ZeptoMail app tag for domain warmup sends."""
    addr = (sender_email or '').lower().strip()
    if addr.startswith('selka@') or '@selka.' in addr:
        return 'red_flag_scanner'
    if 'breakuprelief.com' in addr:
        return 'fresh_start'
    if 'predictifyfootball.com' in addr:
        return 'predictify'
    if 'thesisgenerator.io' in addr:
        return 'thesis_generator'
    return ''


def _zeptomail_api_key(app=None):
    if _is_breakup_app(app):
        return os.getenv('ZEPTOMAIL_BREAKUP_API_KEY') or os.getenv('ZEPTOMAIL_API_KEY', '')
    return os.getenv('ZEPTOMAIL_API_KEY', '')


def _email_provider():
    return (os.getenv('EMAIL_PROVIDER') or 'resend').lower()


def _is_mailgun():
    return _email_provider() == 'mailgun'


def _is_smtp2go():
    return _email_provider() == 'smtp2go'


def _is_zeptomail():
    return _email_provider() == 'zeptomail'


def _api_key_env_name():
    if _is_mailgun():
        return 'MAILGUN_API_KEY'
    if _is_smtp2go():
        return 'SMTP2GO_API_KEY'
    if _is_zeptomail():
        return 'ZEPTOMAIL_API_KEY'
    return 'RESEND_API_KEY'


def has_email_credentials() -> bool:
    """True if the active EMAIL_PROVIDER has the required API key set."""
    if _is_zeptomail():
        return bool(_zeptomail_api_key() or os.getenv('ZEPTOMAIL_BREAKUP_API_KEY'))
    return bool(os.getenv(_api_key_env_name()))


# Keep class name GmailSender so nothing else needs to change
class GmailSender:
    """Resend, Mailgun, SMTP2GO, or ZeptoMail email sender — same interface as previous senders."""

    RESEND_API_URL = "https://api.resend.com/emails"
    MAILGUN_API_BASE = "https://api.mailgun.net/v3"
    SMTP2GO_API_URL = "https://api.smtp2go.com/v3/email/send"
    ZEPTOMAIL_API_URL = os.getenv('ZEPTOMAIL_API_URL', 'https://api.zeptomail.eu/v1.1/email')

    # Process-wide dedup: never send the same recipient twice in one run.
    # The thesis orchestrator runs 11 senders in ONE process and each iterates
    # per-thesis, so a user with 3 thesis projects (or matching several
    # senders) was getting 2-3 emails at once — exactly the "spammy duplicate"
    # report. This class-level set is shared across every GmailSender instance
    # in the process (it survives the orchestrator's per-sender importlib
    # .reload, which only reloads the sender module, not gmail_sender), so the
    # first successful email to an address wins and the rest are suppressed.
    # v1 retention sends each user at most once per run, so it never trips this.
    _emailed_recipients: set = set()
    _suppression_cache = None
    _volume_cache = None
    _run_counts = Counter()

    @classmethod
    def reset_dedup(cls):
        """Clear the per-run dedup set (call at the start of a fresh run)."""
        cls._emailed_recipients = set()

    def __init__(self, sender_email=None, sender_name=None):
        self._use_mailgun = _is_mailgun()
        self._use_smtp2go = _is_smtp2go()
        self._use_zeptomail = _is_zeptomail()
        self.api_key = os.getenv(_api_key_env_name())
        if self._use_zeptomail and not self.api_key:
            self.api_key = os.getenv('ZEPTOMAIL_BREAKUP_API_KEY', '')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN', 'passedai.io')
        self._explicit_sender_email = sender_email is not None
        self._explicit_sender_name = sender_name is not None
        if self._use_zeptomail:
            default_sender = os.getenv(
                'PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL', 'hello@predictifyfootball.com'
            )
        else:
            default_sender = 'hello@passedai.io'
        self.sender_email = sender_email or default_sender
        self.sender_name = sender_name or 'Sam'
        if self._use_mailgun:
            delay_env = 'MAILGUN_SEND_DELAY_SECONDS'
        elif self._use_smtp2go:
            delay_env = 'SMTP2GO_SEND_DELAY_SECONDS'
        elif self._use_zeptomail:
            delay_env = 'ZEPTOMAIL_SEND_DELAY_SECONDS'
        else:
            delay_env = 'RESEND_SEND_DELAY_SECONDS'
        self.delay_between_emails = float(os.getenv(delay_env, '0.25'))
        self.connected = False

        if not self.api_key and not (self._use_zeptomail and os.getenv('ZEPTOMAIL_BREAKUP_API_KEY')):
            raise ValueError(f"{_api_key_env_name()} must be set")

    @classmethod
    def _supabase_creds(cls):
        url = os.getenv('SUPABASE_URL', '').rstrip('/')
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
        if url and key:
            return url, key

        cfg_path = Path(__file__).resolve().parent.parent / 'config' / 'supabase_config.json'
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text())
                project = cfg.get('project', {})
                url = project.get('url', '').rstrip('/')
                key = project.get('service_role_key', '')
            except Exception:
                return None, None
        return (url, key) if url and key else (None, None)

    @classmethod
    def _load_suppressions(cls):
        if cls._suppression_cache is not None:
            return cls._suppression_cache

        suppressions = defaultdict(set)
        url, key = cls._supabase_creds()
        if not url or not key:
            cls._suppression_cache = suppressions
            return suppressions

        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        page_size = 1000
        start = 0
        try:
            while True:
                end = start + page_size - 1
                resp = requests.get(
                    f"{url}/rest/v1/email_suppressions",
                    headers={**headers, "Range": f"{start}-{end}"},
                    params={"select": "recipient,app"},
                    timeout=20,
                )
                if resp.status_code >= 400:
                    print(f"   ⚠️ Suppression lookup skipped: {resp.status_code} {resp.text[:160]}")
                    break
                rows = resp.json()
                for row in rows:
                    recipient = (row.get('recipient') or '').lower().strip()
                    app = (row.get('app') or '').strip()
                    if recipient and app:
                        suppressions[recipient].add(app)
                if len(rows) < page_size:
                    break
                start += page_size
        except Exception as e:
            print(f"   ⚠️ Suppression lookup skipped: {e}")

        cls._suppression_cache = suppressions
        return suppressions

    @classmethod
    def _is_suppressed(cls, to_email, app):
        recipient = (to_email or '').lower().strip()
        if not recipient:
            return False
        apps = cls._load_suppressions().get(recipient, set())
        if {'*', 'global'} & apps:
            return True
        if app and app in apps:
            return True
        if _is_thesis_app(app) and ({'thesis', 'thesis_generator'} & apps):
            return True
        if _is_predictify_app(app) and (
            {'predictify', 'predictify_nba', 'horse_racing'} & apps
        ):
            return True
        return False

    @classmethod
    def _normalize_bounce_app(cls, app: str) -> str:
        slug = (app or '').strip().lower()
        if _is_thesis_app(slug):
            return 'thesis_generator'
        if slug in ('predictify_nba', 'horse_racing', 'predictify'):
            return slug
        if _is_predictify_app(slug):
            return slug
        return slug or 'unknown'

    @classmethod
    def _record_hard_bounce(cls, to_email, app, *, details=None):
        """Persist inline API bounces so the next send skips immediately."""
        url, key = cls._supabase_creds()
        if not url or not key:
            return

        recipient = (to_email or '').lower().strip()
        if not recipient:
            return

        app_slug = cls._normalize_bounce_app(app)
        headers = {
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal,resolution=merge-duplicates',
        }
        rows = [
            {'recipient': recipient, 'app': app_slug, 'reason': 'bounce'},
            {'recipient': recipient, 'app': '*', 'reason': 'bounce'},
        ]
        try:
            requests.post(
                f'{url}/rest/v1/email_suppressions',
                headers=headers,
                params={'on_conflict': 'recipient,app'},
                json=rows,
                timeout=15,
            )
        except Exception as e:
            print(f'   ⚠️ bounce suppression write failed: {e}')

        event_id = 'inline-' + hashlib.sha256(
            f'{recipient}:{app_slug}'.encode('utf-8')
        ).hexdigest()[:24]
        try:
            requests.post(
                f'{url}/rest/v1/email_events',
                headers=headers,
                json={
                    'svix_id': event_id,
                    'event_type': 'email.bounced',
                    'occurred_at': _utc_now().isoformat(),
                    'recipient': recipient,
                    'app': app_slug,
                    'raw': {'inline_bounce': True, 'details': details or {}},
                },
                timeout=15,
            )
        except Exception as e:
            print(f'   ⚠️ bounce event write failed: {e}')

        cls._suppression_cache = None

    @classmethod
    def _thesis_cap_disabled(cls) -> bool:
        """Daily Thesis send cap is off by default — set THESIS_DAILY_SEND_CAP_DISABLED=0 to re-enable."""
        return os.getenv('THESIS_DAILY_SEND_CAP_DISABLED', '1').lower() in ('1', 'true', 'yes')

    @classmethod
    def _fetch_thesis_volume_metrics(cls):
        now = _utc_now()
        default = {
            'cap': int(os.getenv('THESIS_DAILY_SEND_CAP_BASE', '500')),
            'sent_24h': 0,
            'sent_7d': 0,
            'delivered_7d': 0,
            'opened_7d': 0,
            'clicked_7d': 0,
            'bounced_7d': 0,
        }

        url, key = cls._supabase_creds()
        if not url or not key:
            return default

        since_7d = (now - timedelta(days=7)).isoformat()
        since_24h = now - timedelta(hours=24)
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        rows = []
        page_size = 1000
        start = 0
        try:
            while len(rows) < 50000:
                end = start + page_size - 1
                resp = requests.get(
                    f"{url}/rest/v1/email_events",
                    headers={**headers, "Range": f"{start}-{end}"},
                    params={
                        "select": "event_type,occurred_at,app",
                        "app": "in.(thesis,thesis_generator)",
                        "occurred_at": f"gte.{since_7d}",
                        "order": "occurred_at.desc",
                    },
                    timeout=25,
                )
                if resp.status_code >= 400:
                    print(f"   ⚠️ Thesis cap metrics fallback: {resp.status_code} {resp.text[:160]}")
                    return default
                page = resp.json()
                rows.extend(page)
                if len(page) < page_size:
                    break
                start += page_size
        except Exception as e:
            print(f"   ⚠️ Thesis cap metrics fallback: {e}")
            return default

        metrics = dict(default)
        for row in rows:
            event_type = row.get('event_type')
            happened_at = _parse_iso(row.get('occurred_at'))
            if event_type == 'email.sent':
                metrics['sent_7d'] += 1
                if happened_at and happened_at >= since_24h:
                    metrics['sent_24h'] += 1
            elif event_type == 'email.delivered':
                metrics['delivered_7d'] += 1
            elif event_type == 'email.opened':
                metrics['opened_7d'] += 1
            elif event_type == 'email.clicked':
                metrics['clicked_7d'] += 1
            elif event_type == 'email.bounced':
                metrics['bounced_7d'] += 1

        base = int(os.getenv('THESIS_DAILY_SEND_CAP_BASE', '500'))
        max_cap = int(os.getenv('THESIS_DAILY_SEND_CAP_MAX', '3000'))
        delivered = max(metrics['delivered_7d'], 1)
        sent = max(metrics['sent_7d'], 1)
        bounce_rate = metrics['bounced_7d'] / sent
        open_rate = metrics['opened_7d'] / delivered
        click_rate = metrics['clicked_7d'] / delivered
        daily_delivered = metrics['delivered_7d'] / 7

        cap = base
        if metrics['delivered_7d'] >= 300 and bounce_rate < 0.02:
            cap = max(cap, int(daily_delivered * 1.15))
        if metrics['delivered_7d'] >= 500 and bounce_rate < 0.015 and (open_rate >= 0.01 or click_rate >= 0.0005):
            cap = max(cap, int(daily_delivered * 1.35))
        if metrics['delivered_7d'] >= 1000 and bounce_rate < 0.01 and (open_rate >= 0.02 or click_rate >= 0.001):
            cap = max(cap, int(daily_delivered * 1.6))
        if bounce_rate >= 0.025:
            cap = min(cap, base)

        metrics['cap'] = max(base, min(max_cap, cap))
        metrics['bounce_rate'] = bounce_rate
        metrics['open_rate'] = open_rate
        metrics['click_rate'] = click_rate
        return metrics

    @classmethod
    def _thesis_volume_metrics(cls):
        if cls._thesis_cap_disabled():
            return None
        if cls._volume_cache is None:
            cls._volume_cache = cls._fetch_thesis_volume_metrics()
            m = cls._volume_cache
            print(
                "   📈 Thesis volume cap: "
                f"{m['cap']}/24h "
                f"(sent_24h={m['sent_24h']}, sent_7d={m['sent_7d']}, "
                f"bounce={m.get('bounce_rate', 0):.2%}, open={m.get('open_rate', 0):.2%}, "
                f"click={m.get('click_rate', 0):.2%})"
            )
        return cls._volume_cache

    @classmethod
    def _under_thesis_cap(cls, app):
        if not _is_thesis_app(app):
            return True
        if cls._thesis_cap_disabled():
            return True
        metrics = cls._thesis_volume_metrics()
        if not metrics:
            return True
        used = metrics.get('sent_24h', 0) + cls._run_counts['thesis']
        return used < metrics.get('cap', 0)

    def _mailgun_pinned_email(self, sender_email):
        """Pin all From addresses to passedai.io when Mailgun is active."""
        local = (sender_email or '').split('@')[0].lower()
        if local == 'selka':
            return os.getenv('MAILGUN_SELKA_SENDER_EMAIL', 'selka@passedai.io')
        return os.getenv('MAILGUN_SENDER_EMAIL', 'hello@passedai.io')

    def _zeptomail_pinned_email(self, sender_email, app=None):
        """Pin From address to the verified ZeptoMail domain for this app."""
        if _is_predictify_app(app):
            return os.getenv(
                'PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL', 'hello@predictifyfootball.com'
            )
        if _is_thesis_app(app):
            return (
                os.getenv('ZEPTOMAIL_THESIS_SENDER_EMAIL')
                or os.getenv('ZEPTOMAIL_SENDER_EMAIL', 'hello@thesisgenerator.io')
            )
        if _is_selka_app(app):
            return os.getenv('ZEPTOMAIL_SELKA_SENDER_EMAIL', 'selka@breakuprelief.com')
        if _is_soulplan_app(app):
            return (
                os.getenv('ZEPTOMAIL_SOULPLAN_SENDER_EMAIL')
                or os.getenv('ZEPTOMAIL_BREAKUP_SENDER_EMAIL', 'hello@breakuprelief.com')
            )
        if _is_breakup_app(app):
            return os.getenv('ZEPTOMAIL_BREAKUP_SENDER_EMAIL', 'hello@breakuprelief.com')
        if sender_email and '@predictifyfootball.com' in (sender_email or '').lower():
            return sender_email
        return os.getenv('ZEPTOMAIL_SENDER_EMAIL', 'hello@thesisgenerator.io')

    def _effective_sender(self, app, from_name=None):
        sender_email = self.sender_email
        sender_name = from_name or self.sender_name
        if _is_thesis_app(app) and not self._explicit_sender_email:
            sender_email = os.getenv(
                'ZEPTOMAIL_THESIS_SENDER_EMAIL'
                if self._use_zeptomail
                else 'THESIS_SENDER_EMAIL',
                'hello@thesisgenerator.io',
            )
            if not from_name and not self._explicit_sender_name:
                sender_name = os.getenv(
                    'ZEPTOMAIL_THESIS_SENDER_NAME'
                    if self._use_zeptomail
                    else 'THESIS_SENDER_NAME',
                    'Thesis Generator',
                )
        elif _is_predictify_app(app) and self._use_zeptomail:
            sender_email = self._zeptomail_pinned_email(sender_email, app)
            if not from_name and not self._explicit_sender_name:
                sender_name = os.getenv('PREDICTIFY_ZEPTOMAIL_SENDER_NAME', 'Predictify')
        if self._use_mailgun:
            sender_email = self._mailgun_pinned_email(sender_email)
        if self._use_zeptomail:
            sender_email = self._zeptomail_pinned_email(sender_email, app)
        return sender_email, sender_name

    def connect(self):
        """Verify email provider credentials."""
        if self._use_mailgun:
            return self._connect_mailgun()
        if self._use_smtp2go:
            return self._connect_smtp2go()
        if self._use_zeptomail:
            return self._connect_zeptomail()
        return self._connect_resend()

    def _connect_resend(self):
        for attempt in range(2):
            try:
                resp = requests.get(
                    "https://api.resend.com/domains",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    domains = resp.json().get('data', [])
                    domain_names = [d['name'] for d in domains] if domains else []
                    print(f"✅ Connected to Resend as {self.sender_email} (domains: {', '.join(domain_names) or 'none yet'})")
                    self.connected = True
                    return True
                elif resp.status_code == 429 and attempt == 0:
                    time.sleep(2)
                    continue
                else:
                    print(f"❌ Resend auth failed: {resp.status_code} {resp.text[:200]}")
                    return False
            except Exception as e:
                print(f"❌ Resend connection failed: {e}")
                return False
        return False

    def _connect_mailgun(self):
        try:
            resp = requests.get(
                f"{self.MAILGUN_API_BASE}/domains/{self.mailgun_domain}",
                auth=('api', self.api_key),
                timeout=10,
            )
            if resp.status_code == 200:
                state = resp.json().get('domain', {}).get('state', 'unknown')
                pinned = self._mailgun_pinned_email(self.sender_email)
                print(f"✅ Connected to Mailgun domain {self.mailgun_domain} ({state}) — sending as {pinned}")
                self.connected = True
                return True
            print(f"❌ Mailgun auth failed: {resp.status_code} {resp.text[:200]}")
            return False
        except Exception as e:
            print(f"❌ Mailgun connection failed: {e}")
            return False

    def _connect_smtp2go(self):
        try:
            resp = requests.post(
                "https://api.smtp2go.com/v3/domain/view",
                headers={
                    "X-Smtp2go-Api-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={},
                timeout=10,
            )
            if resp.status_code == 200:
                domains = resp.json().get('data', {}).get('domains', [])
                verified = []
                for entry in domains:
                    d = (entry or {}).get('domain', {})
                    name = d.get('fulldomain')
                    if not name:
                        continue
                    ok = d.get('dkim_verified') and d.get('rpath_verified')
                    verified.append(f"{name}{'✓' if ok else '…'}")
                print(f"✅ Connected to SMTP2GO as {self.sender_email} (domains: {', '.join(verified) or 'none yet'})")
                self.connected = True
                return True

            body = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
            err_code = str((body.get('data') or {}).get('error_code', ''))
            if resp.status_code == 400 and 'ENDPOINT_PERMISSION_DENIED' in err_code:
                print(f"✅ SMTP2GO API key OK — verify sender domains in the SMTP2GO dashboard")
                self.connected = True
                return True

            print(f"❌ SMTP2GO auth failed: {resp.status_code} {resp.text[:200]}")
            return False
        except Exception as e:
            print(f"❌ SMTP2GO connection failed: {e}")
            return False

    def _connect_zeptomail(self):
        thesis = self._zeptomail_pinned_email(self.sender_email, 'thesis')
        predictify = self._zeptomail_pinned_email(self.sender_email, 'predictify')
        print(
            f"✅ ZeptoMail configured — thesis: {thesis}, "
            f"predictify: {predictify} (app-tagged routing)"
        )
        self.connected = True
        return True

    def disconnect(self):
        """No-op — REST API, no persistent connection."""
        self.connected = False

    # Resend error messages that indicate a hard bounce / invalid address
    BOUNCE_INDICATORS = [
        'not found', 'does not exist', 'invalid', 'rejected',
        'bounce', 'undeliverable', 'mailbox not found', 'no such user',
        'address rejected', 'recipient rejected', 'unknown user',
        'mailbox unavailable', 'relay not permitted',
    ]

    def _is_bounce(self, status_code, response_text):
        """Detect if a send failure is a hard bounce (invalid address)."""
        text_lower = response_text.lower()
        # 4xx from Resend with bounce-like messaging
        if status_code in (400, 403, 422):
            return any(ind in text_lower for ind in self.BOUNCE_INDICATORS)
        return False

    def send_email(self, to_email, subject, html_body, from_name=None, tags=None, ref_id=None):
        """
        Send a single HTML email via Resend.
        tags: list of {"name": str, "value": str} — appears on every webhook event
              for per-app / per-email-number / per-language slicing.
        ref_id: opaque correlator (e.g. hashed user id) sent as X-Entity-Ref-ID.
                Resend echoes it on webhooks so we can join events to users without
                exposing the raw email address in tag values.
        Returns: 'sent' on success, 'bounced' if address is invalid,
        'duplicate' if this recipient was already emailed in this run,
        'suppressed' if blocked by durable suppression, 'throttled' if the
        Thesis auto-ramp daily cap has been reached, 'paused' if sending is
        globally disabled, 'failed' otherwise.
        """
        if (os.getenv('EMAIL_SENDING_PAUSED') or '').lower() in ('1', 'true', 'yes'):
            print('   ⏸️ Email sending paused (EMAIL_SENDING_PAUSED)')
            return 'paused'

        if not self.connected:
            print("   ❌ Not connected. Call connect() first.")
            return 'failed'

        tag_values = _tag_dict(tags)
        app = tag_values.get('app', '')
        is_warming = tag_values.get('kind') == 'warming'
        if is_warming and not app:
            app = warming_app_for_sender(self.sender_email)

        if self._use_zeptomail and not _is_zeptomail_allowed_app(app):
            print(f"   ⏸️ ZeptoMail — skipping unsupported app ({app or 'unknown'})")
            return 'paused'

        if self._is_suppressed(to_email, app):
            print(f"   ⏭️ Suppressed — {to_email} is on the durable suppression list")
            return 'suppressed'

        if not is_warming and not self._under_thesis_cap(app):
            metrics = self._thesis_volume_metrics() or {}
            used = metrics.get('sent_24h', 0) + GmailSender._run_counts['thesis']
            print(f"   ⏭️ Thesis volume cap reached — {used}/{metrics.get('cap', 0)} sent in 24h")
            return 'throttled'

        # One email per recipient per process run — suppress duplicates so a
        # user never receives two emails of the same app at once.
        dedup_key = (to_email or '').lower().strip()
        if dedup_key and dedup_key in GmailSender._emailed_recipients:
            print(f"   ⏭️ Duplicate suppressed — already emailed {to_email} this run")
            return 'duplicate'

        sender_email, sender_name = self._effective_sender(app, from_name)
        subject_clean = _sanitize_subject(subject)

        if self._use_mailgun:
            return self._send_mailgun(
                to_email, subject_clean, html_body, sender_email, sender_name,
                tags, ref_id, dedup_key, app,
            )
        if self._use_smtp2go:
            return self._send_smtp2go(
                to_email, subject_clean, html_body, sender_email, sender_name,
                tags, ref_id, dedup_key, app,
            )
        if self._use_zeptomail:
            return self._send_zeptomail(
                to_email, subject_clean, html_body, sender_email, sender_name,
                tags, ref_id, dedup_key, app,
            )
        return self._send_resend(
            to_email, subject_clean, html_body, sender_email, sender_name,
            tags, ref_id, dedup_key, app,
        )

    def _mark_sent(self, dedup_key, app):
        if dedup_key:
            GmailSender._emailed_recipients.add(dedup_key)
        if _is_thesis_app(app):
            GmailSender._run_counts['thesis'] += 1

    def _send_resend(self, to_email, subject, html_body, sender_email, sender_name,
                     tags, ref_id, dedup_key, app):
        sender = f"{sender_name} <{sender_email}>"
        payload = {
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
            "reply_to": sender_email,
        }
        if tags:
            payload["tags"] = [
                {"name": str(t["name"])[:256],
                 "value": _sanitize_tag(str(t["value"]))[:256]}
                for t in tags if t.get("name") and t.get("value") is not None
            ]
        if ref_id:
            payload["headers"] = {"X-Entity-Ref-ID": str(ref_id)[:256]}

        try:
            resp = requests.post(
                self.RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )

            if resp.status_code in (200, 201):
                self._mark_sent(dedup_key, app)
                return 'sent'

            if resp.status_code == 429:
                print("   ⏳ Resend rate limited — backing off...")
                time.sleep(2)
                retry = requests.post(
                    self.RESEND_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=15,
                )
                if retry.status_code in (200, 201):
                    self._mark_sent(dedup_key, app)
                    return 'sent'

            error_msg = resp.text[:200]
            if self._is_bounce(resp.status_code, resp.text):
                print(f"   🔴 BOUNCED: {to_email} — {error_msg}")
                self._record_hard_bounce(to_email, app, details=error_msg)
                return 'bounced'

            print(f"   ❌ Resend error [{resp.status_code}]: {error_msg}")
            return 'failed'
        except Exception as e:
            print(f"   ❌ Resend send error: {e}")
            return 'failed'

    def _send_mailgun(self, to_email, subject, html_body, sender_email, sender_name,
                      tags, ref_id, dedup_key, app):
        data = {
            'from': f"{sender_name} <{sender_email}>",
            'to': to_email,
            'subject': subject,
            'html': html_body,
            'h:Reply-To': sender_email,
        }
        if ref_id:
            data['v:ref_id'] = str(ref_id)[:256]
        if tags:
            data['o:tag'] = [
                f"{t['name']}:{_sanitize_tag(str(t['value']))}"
                for t in tags if t.get('name') and t.get('value') is not None
            ]

        try:
            resp = requests.post(
                f"{self.MAILGUN_API_BASE}/{self.mailgun_domain}/messages",
                auth=('api', self.api_key),
                data=data,
                timeout=15,
            )

            if resp.status_code == 200:
                self._mark_sent(dedup_key, app)
                return 'sent'

            error_msg = resp.text[:200]
            if self._is_bounce(resp.status_code, resp.text):
                print(f"   🔴 BOUNCED: {to_email} — {error_msg}")
                self._record_hard_bounce(to_email, app, details=error_msg)
                return 'bounced'

            print(f"   ❌ Mailgun error [{resp.status_code}]: {error_msg}")
            return 'failed'
        except Exception as e:
            print(f"   ❌ Mailgun send error: {e}")
            return 'failed'

    def _send_smtp2go(self, to_email, subject, html_body, sender_email, sender_name,
                      tags, ref_id, dedup_key, app):
        payload = {
            'sender': f"{sender_name} <{sender_email}>",
            'to': [to_email],
            'subject': subject,
            'html_body': html_body,
            'custom_headers': [{'header': 'Reply-To', 'value': sender_email}],
        }
        if ref_id:
            payload['custom_headers'].append({
                'header': 'X-Entity-Ref-ID',
                'value': str(ref_id)[:256],
            })
        if tags:
            for t in tags:
                if t.get('name') and t.get('value') is not None:
                    payload['custom_headers'].append({
                        'header': f"X-Tag-{str(t['name'])[:64]}",
                        'value': _sanitize_tag(str(t['value']))[:256],
                    })

        try:
            resp = requests.post(
                self.SMTP2GO_API_URL,
                headers={
                    'X-Smtp2go-Api-Key': self.api_key,
                    'Content-Type': 'application/json',
                    'accept': 'application/json',
                },
                json=payload,
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json().get('data', {})
                if data.get('error') or data.get('failed', 0) > 0:
                    error_msg = json.dumps(data)[:200]
                    print(f"   ❌ SMTP2GO error: {error_msg}")
                    return 'failed'
                self._mark_sent(dedup_key, app)
                return 'sent'

            error_msg = resp.text[:200]
            if self._is_bounce(resp.status_code, resp.text):
                print(f"   🔴 BOUNCED: {to_email} — {error_msg}")
                self._record_hard_bounce(to_email, app, details=error_msg)
                return 'bounced'

            print(f"   ❌ SMTP2GO error [{resp.status_code}]: {error_msg}")
            return 'failed'
        except Exception as e:
            print(f"   ❌ SMTP2GO send error: {e}")
            return 'failed'

    def _send_zeptomail(self, to_email, subject, html_body, sender_email, sender_name,
                        tags, ref_id, dedup_key, app):
        mime_headers = {'Reply-To': sender_email}
        if ref_id:
            mime_headers['X-Entity-Ref-ID'] = str(ref_id)[:256]
        if tags:
            for t in tags:
                if t.get('name') and t.get('value') is not None:
                    mime_headers[f"X-Tag-{str(t['name'])[:64]}"] = _sanitize_tag(str(t['value']))[:256]

        payload = {
            'from': {'address': sender_email, 'name': sender_name},
            'to': [{'email_address': {'address': to_email, 'name': to_email.split('@')[0] or 'User'}}],
            'subject': subject,
            'htmlbody': html_body,
            'track_clicks': False,
            'track_opens': False,
            'mime_headers': mime_headers,
        }
        if ref_id:
            payload['client_reference'] = str(ref_id)[:256]

        zepto_key = _zeptomail_api_key(app) or self.api_key
        try:
            resp = requests.post(
                self.ZEPTOMAIL_API_URL,
                headers={
                    'Authorization': f'Zoho-enczapikey {zepto_key}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=15,
            )

            if resp.status_code in (200, 201):
                self._mark_sent(dedup_key, app)
                return 'sent'

            error_msg = resp.text[:200]
            if self._is_bounce(resp.status_code, resp.text):
                print(f"   🔴 BOUNCED: {to_email} — {error_msg}")
                self._record_hard_bounce(to_email, app, details=error_msg)
                return 'bounced'

            print(f"   ❌ ZeptoMail error [{resp.status_code}]: {error_msg}")
            return 'failed'
        except Exception as e:
            print(f"   ❌ ZeptoMail send error: {e}")
            return 'failed'

    def send_batch(self, emails, progress_callback=None):
        """
        Send a batch of emails with rate limiting.
        emails: list of dicts with keys: to, subject, html_body
        Returns: (sent_count, failed_count)
        """
        sent = 0
        failed = 0

        for i, email in enumerate(emails):
            result = self.send_email(
                to_email=email['to'],
                subject=email['subject'],
                html_body=email['html_body'],
                from_name=email.get('from_name', self.sender_name),
                tags=email.get('tags'),
                ref_id=email.get('ref_id'),
            )

            if result == 'sent':
                sent += 1
                if progress_callback:
                    progress_callback(email['to'], i + 1, len(emails))
            elif result in SKIP_RESULTS:
                print(f"   ⏭️ Skipped {email['to']} — {result}")
            else:
                failed += 1

            # Rate limiting
            if i < len(emails) - 1:
                time.sleep(self.delay_between_emails)

        return sent, failed
