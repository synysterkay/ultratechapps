#!/usr/bin/env python3
"""
Email Deliverability Monitor & Sender Rotation

Monitors email health via Resend API and local tracking.
When a sender's reputation degrades below configurable thresholds,
automatically rotates to the next healthy sender identity.

Sender identities use different verified domains in Resend.
All domains share the same Resend API key.

Usage:
  python scripts/deliverability_monitor.py --check       # Check current health
  python scripts/deliverability_monitor.py --report      # Detailed report
  python scripts/deliverability_monitor.py --rotate      # Force rotation
"""
import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta


class DeliverabilityMonitor:
    """
    Monitors email deliverability via Resend API and manages sender rotation.
    
    Metrics tracked:
    - Bounce rate (above 3% = bad list hygiene, hurts reputation)
    - Spam complaint rate (above 0.1% = critical — ISPs will block you)
    - Delivery rate
    
    Decision logic:
    - GREEN: spam < 0.05%, bounce < 2%
    - YELLOW: spam 0.05-0.1%, or bounce 2-3%
    - RED: spam > 0.1%, or bounce > 3%
    - On RED → auto-rotate to next sender
    """

    # ── SENDER IDENTITIES (add new senders here) ───────────
    # Order matters: first = primary, rest = fallbacks.
    # SMTP2GO enabled: breakuprelief.com, kaynel.solutions, passedai.io.
    # predictifyfootball.com unverified; predictify.fun verified but disabled.
    SENDER_POOL = [
        {
            "email": "hello@breakuprelief.com",
            "name": "Casey",
            "domain": "breakuprelief.com",
            "active": True,
        },
        {
            "email": "hello@kaynel.solutions",
            "name": "Alex",
            "domain": "kaynel.solutions",
            "active": True,
        },
        {
            "email": "hello@passedai.io",
            "name": "Taylor",
            "domain": "passedai.io",
            "active": True,
        },
    ]

    # ── THRESHOLDS ──────────────────────────────────────────
    THRESHOLDS = {
        "open_rate_red": 5.0,        # Below 5% = likely going to spam
        "open_rate_yellow": 15.0,    # Below 15% = warning
        "bounce_rate_red": 3.0,      # Above 3% = critical
        "bounce_rate_yellow": 2.0,   # Above 2% = warning
        "spam_rate_red": 0.10,       # Above 0.1% = critical (ISPs block at this)
        "spam_rate_yellow": 0.05,    # Above 0.05% = watch closely
        "min_emails_for_eval": 50,   # Need at least 50 emails to evaluate
        "lookback_days": 7,          # Evaluate last 7 days of data
        "cooldown_days": 14,         # Wait 14 days before reusing rotated-out sender
    }

    def __init__(self):
        self.api_key = os.getenv('RESEND_API_KEY')
        self.base_dir = Path(__file__).parent.parent
        self.health_file = self.base_dir / 'cache' / 'sender_health.json'
        self.health_file.parent.mkdir(exist_ok=True)
        self.health_state = self._load_health_state()

    def _resend_get(self, endpoint):
        """Make a GET request to Resend API."""
        if not self.api_key:
            return None
        try:
            resp = requests.get(
                f"https://api.resend.com{endpoint}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    # ── STATE PERSISTENCE ───────────────────────────────────

    def _load_health_state(self):
        """
        Load sender health tracking state.
        Structure: {
            "active_sender_index": 0,
            "senders": {
                "apps@kaynel.pl": {
                    "last_check": "2026-02-20T...",
                    "status": "green",            # green/yellow/red
                    "rotated_out_at": null,        # ISO timestamp if rotated out
                    "metrics_history": [           # Last N check results
                        {
                            "date": "2026-02-20",
                            "sent": 450,
                            "delivered": 445,
                            "opened": 89,
                            "bounced": 3,
                            "spam_complaints": 0,
                            "blocked": 2,
                            "open_rate": 19.8,
                            "bounce_rate": 0.67,
                            "spam_rate": 0.0,
                        }
                    ]
                }
            },
            "rotation_log": []
        }
        """
        if self.health_file.exists():
            try:
                with open(self.health_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "active_sender_index": 0,
            "senders": {},
            "rotation_log": [],
        }

    def _save_health_state(self):
        with open(self.health_file, 'w') as f:
            json.dump(self.health_state, f, indent=2)

    # ── RESEND API QUERIES ──────────────────────────────────

    def fetch_email_events(self, days=7, sender_email=None):
        """
        Fetch sending statistics from Resend API by scanning recent emails.
        Filters by sender domain when sender_email is provided.
        Falls back to local health state history if API fails.
        """
        if not self.api_key:
            return None

        # Extract domain to filter by (if sender specified)
        filter_domain = None
        if sender_email and '@' in sender_email:
            filter_domain = sender_email.split('@')[1]

        try:
            # Try to get live stats from Resend API
            stats = {
                'sent': 0, 'delivered': 0, 'opened': 0, 'clicked': 0,
                'bounced': 0, 'hard_bounces': 0, 'soft_bounces': 0,
                'spam_complaints': 0, 'blocked': 0, 'invalid': 0,
            }
            cursor = None
            cutoff = datetime.now() - timedelta(days=days)
            pages = 0
            max_pages = 200

            while pages < max_pages:
                pages += 1
                params = {}
                if cursor:
                    params['starting_after'] = cursor

                resp = requests.get(
                    'https://api.resend.com/emails',
                    headers={'Authorization': f'Bearer {self.api_key}'},
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 429:
                    time.sleep(2)
                    resp = requests.get(
                        'https://api.resend.com/emails',
                        headers={'Authorization': f'Bearer {self.api_key}'},
                        params=params,
                        timeout=15,
                    )
                if resp.status_code != 200:
                    break

                data = resp.json()
                emails = data.get('data', [])
                if not emails:
                    break

                stop = False
                for e in emails:
                    created = e.get('created_at', '')
                    if created:
                        try:
                            email_date = datetime.fromisoformat(created.replace('+00', '+00:00').replace(' ', 'T'))
                            if email_date.replace(tzinfo=None) < cutoff:
                                stop = True
                                break
                        except (ValueError, TypeError):
                            pass

                    # Filter by sender domain if specified
                    if filter_domain:
                        from_field = e.get('from', '')
                        if filter_domain not in from_field:
                            continue

                    event = e.get('last_event', '')
                    stats['sent'] += 1
                    if event == 'delivered':
                        stats['delivered'] += 1
                    elif event == 'opened':
                        stats['delivered'] += 1
                        stats['opened'] += 1
                    elif event == 'clicked':
                        stats['delivered'] += 1
                        stats['opened'] += 1
                        stats['clicked'] += 1
                    elif event == 'bounced':
                        stats['bounced'] += 1
                        stats['hard_bounces'] += 1
                    elif event == 'complained':
                        stats['delivered'] += 1
                        stats['spam_complaints'] += 1
                    elif event == 'delivery_delayed':
                        pass  # Still in transit

                if stop:
                    break

                cursor = emails[-1]['id']
                if not data.get('has_more', False):
                    break

                time.sleep(0.3)

            if stats['sent'] > 0:
                return stats

            # Fallback to local history
            sender = sender_email or self.get_active_sender()['email']
            sender_state = self.health_state.get('senders', {}).get(sender, {})
            history = sender_state.get('metrics_history', [])
            if history:
                return history[-1]

            return stats
        except Exception as e:
            print(f"   Resend stats error: {e}")
            return None

    def fetch_event_log(self, event_type='spam', days=7, limit=50):
        """
        Fetch bounced/complained emails from Resend API.
        Paginates through recent emails and filters by last_event.
        """
        if not self.api_key:
            return []

        target_events = {
            'spam': ['complained'],
            'hardBounces': ['bounced'],
            'bounced': ['bounced'],
            'complained': ['complained'],
        }
        match_events = target_events.get(event_type, [event_type])

        results = []
        cursor = None
        pages = 0
        max_pages = 500  # Safety limit

        while pages < max_pages:
            pages += 1
            params = {}
            if cursor:
                params['starting_after'] = cursor

            try:
                resp = requests.get(
                    'https://api.resend.com/emails',
                    headers={'Authorization': f'Bearer {self.api_key}'},
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 429:
                    time.sleep(2)
                    resp = requests.get(
                        'https://api.resend.com/emails',
                        headers={'Authorization': f'Bearer {self.api_key}'},
                        params=params,
                        timeout=15,
                    )
                if resp.status_code != 200:
                    break

                data = resp.json()
                emails = data.get('data', [])
                if not emails:
                    break

                for e in emails:
                    # Stop if email is older than lookback period
                    created = e.get('created_at', '')
                    if created:
                        try:
                            email_date = datetime.fromisoformat(created.replace('+00', '+00:00').replace(' ', 'T'))
                            if email_date < datetime.now(email_date.tzinfo) - timedelta(days=days):
                                return results
                        except (ValueError, TypeError):
                            pass

                    if e.get('last_event') in match_events:
                        to_list = e.get('to', [])
                        results.append({
                            'email': to_list[0] if to_list else 'unknown',
                            'id': e.get('id'),
                            'event': e.get('last_event'),
                            'created_at': created,
                        })
                        if len(results) >= limit:
                            return results

                cursor = emails[-1]['id']
                if not data.get('has_more', False):
                    break

                time.sleep(0.3)
            except Exception as e:
                print(f"   Resend event log error: {e}")
                break

        return results

    # ── HEALTH EVALUATION ───────────────────────────────────

    def evaluate_sender_health(self, sender_email=None):
        """
        Evaluate current sender's deliverability health.
        Returns: {status: 'green'|'yellow'|'red', metrics: {...}, issues: [...]}
        """
        if not self.api_key:
            return {'status': 'unknown', 'metrics': {}, 'issues': ['No RESEND_API_KEY set']}

        metrics = self.fetch_email_events(days=self.THRESHOLDS['lookback_days'], sender_email=sender_email)
        if not metrics:
            return {'status': 'unknown', 'metrics': {}, 'issues': ['Could not fetch metrics from Resend']}

        sent = metrics['sent']
        if sent < self.THRESHOLDS['min_emails_for_eval']:
            return {
                'status': 'insufficient_data',
                'metrics': metrics,
                'issues': [f"Only {sent} emails sent (need {self.THRESHOLDS['min_emails_for_eval']}+ to evaluate)"],
            }

        # Calculate rates
        open_rate = (metrics['opened'] / sent * 100) if sent > 0 else 0
        bounce_rate = (metrics['bounced'] / sent * 100) if sent > 0 else 0
        spam_rate = (metrics['spam_complaints'] / sent * 100) if sent > 0 else 0
        delivery_rate = (metrics['delivered'] / sent * 100) if sent > 0 else 0

        metrics.update({
            'open_rate': round(open_rate, 2),
            'bounce_rate': round(bounce_rate, 2),
            'spam_rate': round(spam_rate, 3),
            'delivery_rate': round(delivery_rate, 2),
        })

        issues = []
        status = 'green'

        # ── Spam rate check (most critical) ──
        if spam_rate > self.THRESHOLDS['spam_rate_red']:
            issues.append(f"🚨 CRITICAL: Spam rate {spam_rate:.3f}% exceeds {self.THRESHOLDS['spam_rate_red']}%")
            status = 'red'
        elif spam_rate > self.THRESHOLDS['spam_rate_yellow']:
            issues.append(f"⚠️ WARNING: Spam rate {spam_rate:.3f}% approaching danger zone")
            if status != 'red':
                status = 'yellow'

        # ── Bounce rate check ──
        if bounce_rate > self.THRESHOLDS['bounce_rate_red']:
            issues.append(f"🚨 CRITICAL: Bounce rate {bounce_rate:.1f}% exceeds {self.THRESHOLDS['bounce_rate_red']}%")
            status = 'red'
        elif bounce_rate > self.THRESHOLDS['bounce_rate_yellow']:
            issues.append(f"⚠️ WARNING: Bounce rate {bounce_rate:.1f}% is elevated")
            if status != 'red':
                status = 'yellow'

        # ── Open rate check (strong indicator of spam folder) ──
        # NOTE: 0.0% open rate with high delivered count is likely a tracking issue,
        # not actual spam placement. Only flag as RED if we've seen this pattern
        # across multiple checks (not just one run).
        if open_rate == 0.0 and sent >= self.THRESHOLDS['min_emails_for_eval']:
            # Check if previous checks also showed 0% — could be Resend tracking bug
            sender = sender_email or self.get_active_sender()['email']
            prev_history = self.health_state.get('senders', {}).get(sender, {}).get('metrics_history', [])
            consecutive_zero = sum(1 for h in prev_history[-3:] if h.get('open_rate', 0) == 0.0)
            if consecutive_zero >= 2:
                issues.append(f"🚨 CRITICAL: Open rate 0.0% for {consecutive_zero + 1} consecutive checks — likely going to spam")
                status = 'red'
            else:
                issues.append(f"⚠️ WARNING: Open rate 0.0% — may be tracking issue, monitoring (check {consecutive_zero + 1}/3)")
                if status != 'red':
                    status = 'yellow'
        elif open_rate > 0 and open_rate < self.THRESHOLDS['open_rate_red']:
            issues.append(f"🚨 CRITICAL: Open rate {open_rate:.1f}% suggests emails going to spam")
            status = 'red'
        elif open_rate > 0 and open_rate < self.THRESHOLDS['open_rate_yellow']:
            issues.append(f"⚠️ WARNING: Open rate {open_rate:.1f}% is below average")
            if status != 'red':
                status = 'yellow'

        if not issues:
            issues.append(f"✅ All metrics healthy (open: {open_rate:.1f}%, bounce: {bounce_rate:.1f}%, spam: {spam_rate:.3f}%)")

        # ── Persist metrics ──
        sender = sender_email or self.get_active_sender()['email']
        if sender not in self.health_state['senders']:
            self.health_state['senders'][sender] = {
                'last_check': None,
                'status': 'unknown',
                'rotated_out_at': None,
                'metrics_history': [],
            }

        self.health_state['senders'][sender]['last_check'] = datetime.now().isoformat()
        self.health_state['senders'][sender]['status'] = status
        self.health_state['senders'][sender]['metrics_history'].append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            **metrics,
        })
        # Keep last 30 checks
        self.health_state['senders'][sender]['metrics_history'] = \
            self.health_state['senders'][sender]['metrics_history'][-30:]

        self._save_health_state()

        return {'status': status, 'metrics': metrics, 'issues': issues}

    # ── SENDER ROTATION ─────────────────────────────────────

    def get_active_sender(self):
        """Get the currently active sender identity"""
        pool = [s for s in self.SENDER_POOL if s['active']]
        if not pool:
            raise ValueError("No active senders in SENDER_POOL!")
        idx = self.health_state.get('active_sender_index', 0)
        idx = idx % len(pool)
        return pool[idx]

    def get_all_healthy_senders(self):
        """Get all senders that are not in cooldown"""
        now = datetime.now()
        healthy = []
        for sender in self.SENDER_POOL:
            if not sender['active']:
                continue
            sender_state = self.health_state.get('senders', {}).get(sender['email'], {})
            rotated_out = sender_state.get('rotated_out_at')
            if rotated_out:
                rotated_time = datetime.fromisoformat(rotated_out)
                cooldown = timedelta(days=self.THRESHOLDS['cooldown_days'])
                if now - rotated_time < cooldown:
                    continue  # Still in cooldown
            healthy.append(sender)
        return healthy

    def rotate_sender(self, reason="manual"):
        """
        Rotate to the next available sender identity.
        Marks current sender as rotated-out with cooldown.
        Returns the new active sender.
        """
        current = self.get_active_sender()
        healthy_senders = self.get_all_healthy_senders()

        # Remove current from candidates
        candidates = [s for s in healthy_senders if s['email'] != current['email']]

        if not candidates:
            print("⚠️ No backup senders available! Cannot rotate.")
            print("   Add more senders to SENDER_POOL in deliverability_monitor.py")
            print("   Then verify them in Resend dashboard: https://resend.com/domains")
            return None

        # Pick the next one
        new_sender = candidates[0]

        # Mark current as rotated out
        if current['email'] not in self.health_state['senders']:
            self.health_state['senders'][current['email']] = {
                'status': 'red', 'metrics_history': [],
            }
        self.health_state['senders'][current['email']]['rotated_out_at'] = datetime.now().isoformat()

        # Update active index
        active_pool = [s for s in self.SENDER_POOL if s['active']]
        for i, s in enumerate(active_pool):
            if s['email'] == new_sender['email']:
                self.health_state['active_sender_index'] = i
                break

        # Log rotation
        self.health_state['rotation_log'].append({
            'date': datetime.now().isoformat(),
            'from': current['email'],
            'to': new_sender['email'],
            'reason': reason,
        })

        self._save_health_state()

        print(f"🔄 SENDER ROTATED:")
        print(f"   From: {current['email']} (now in {self.THRESHOLDS['cooldown_days']}-day cooldown)")
        print(f"   To:   {new_sender['email']}")
        print(f"   Reason: {reason}")

        return new_sender

    def check_and_rotate_if_needed(self):
        """
        Main entry point: check health, auto-rotate if RED.
        Only rotates if sender has been active for at least 48 hours (to prevent
        rapid-fire rotation that burns through all senders).
        Returns the sender to use (may be same or rotated).
        """
        print("\n📊 Checking email deliverability health...")
        health = self.evaluate_sender_health()
        current = self.get_active_sender()

        for issue in health['issues']:
            print(f"   {issue}")

        if health['status'] == 'red':
            # Check minimum hold time — don't rotate if sender was activated < 48 hours ago
            last_rotation = None
            if self.health_state.get('rotation_log'):
                last_rotation = self.health_state['rotation_log'][-1].get('date')
            if last_rotation:
                last_rot_time = datetime.fromisoformat(last_rotation)
                hours_since_rotation = (datetime.now() - last_rot_time).total_seconds() / 3600
                if hours_since_rotation < 48:
                    print(f"\n🚨 Sender {current['email']} is RED but only active for {hours_since_rotation:.0f}h — holding (min 48h before rotation)")
                    return current

            print(f"\n🚨 Sender {current['email']} is in RED status — attempting rotation...")
            new_sender = self.rotate_sender(reason='; '.join(health['issues']))
            if new_sender:
                return new_sender
            else:
                print("   ⚠️ No backup senders — continuing with current (risky)")
                return current
        elif health['status'] == 'yellow':
            print(f"\n⚠️ Sender {current['email']} is in YELLOW status — watch closely")
            return current
        else:
            print(f"\n✅ Sender {current['email']} is healthy ({health['status']})")
            return current

    # ── SPAM TRAP DETECTION ─────────────────────────────────

    def _recipients_from_events(self, event_types, days):
        """Bulk-fetch recipients for the given email_events types in one
        indexed Supabase query.

        Replaces the old fetch_event_log path, which paginated the entire
        Resend /emails API (up to ~500 pages, twice per run) just to find a
        few bounces — ~24 min on the daily campaign. The resend-webhook
        already lands every bounce/complaint in email_events with an indexed
        occurred_at, so one query returns the same set in <1s.
        """
        url = os.environ.get('SUPABASE_URL', '')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
        if not url or not key:
            cfg = Path(__file__).resolve().parents[1] / 'config' / 'supabase_config.json'
            if cfg.exists():
                try:
                    data = json.load(open(cfg))
                    url = data['project']['url']
                    key = data['project']['service_role_key']
                except Exception:
                    pass
        if not url or not key:
            return set()

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
        types = ','.join(event_types)
        out = set()
        try:
            r = requests.get(
                f"{url.rstrip('/')}/rest/v1/email_events",
                params={
                    'select': 'recipient',
                    'event_type': f'in.({types})',
                    'occurred_at': f'gte.{since}',
                    'recipient': 'not.is.null',
                    'limit': '50000',
                },
                headers={'apikey': key, 'Authorization': f'Bearer {key}'},
                timeout=30,
            )
            if r.status_code == 200:
                for row in r.json():
                    rec = row.get('recipient')
                    if rec:
                        out.add(rec.lower())
        except Exception as e:
            print(f"   ⚠️ email_events query failed ({types}): {e}")
        return out

    def get_spam_reporters(self, days=7):
        """Emails that filed a spam complaint — remove from future sends.
        Sourced from email_events (one indexed query)."""
        return self._recipients_from_events(['email.complained'], days)

    def get_hard_bounces(self, days=7):
        """Hard-bounced emails (invalid addresses) — remove permanently.
        Sourced from email_events (one indexed query)."""
        return self._recipients_from_events(['email.bounced'], days)

    def clean_bad_recipients(self, state):
        """
        Remove spam reporters and hard bounces from the campaign state.
        Returns count of users suppressed.
        """
        spam_reporters = self.get_spam_reporters(days=30)
        hard_bounces = self.get_hard_bounces(days=30)
        bad_emails = spam_reporters | hard_bounces

        suppressed = 0
        for email in bad_emails:
            if email in state.get('users', {}):
                state['users'][email]['suppressed'] = True
                state['users'][email]['suppressed_reason'] = \
                    'spam_complaint' if email in spam_reporters else 'hard_bounce'
                suppressed += 1

        if suppressed:
            print(f"   🛡️ Suppressed {suppressed} bad recipients ({len(spam_reporters)} spam, {len(hard_bounces)} bounces)")

        return suppressed

    # ── REPORTING ───────────────────────────────────────────

    def print_health_report(self):
        """Print a detailed deliverability report"""
        print("=" * 60)
        print("📊 EMAIL DELIVERABILITY REPORT")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

        # Current sender
        current = self.get_active_sender()
        print(f"\n📧 Active sender: {current['email']} ({current['domain']})")

        # Health check
        health = self.evaluate_sender_health()
        status_emoji = {'green': '🟢', 'yellow': '🟡', 'red': '🔴'}.get(health['status'], '⚪')
        print(f"   Status: {status_emoji} {health['status'].upper()}")

        m = health.get('metrics', {})
        if m:
            print(f"\n   📨 Sent:           {m.get('sent', 0):,}")
            print(f"   📬 Delivered:      {m.get('delivered', 0):,} ({m.get('delivery_rate', 0):.1f}%)")
            print(f"   👁️  Unique opens:   {m.get('opened', 0):,} ({m.get('open_rate', 0):.1f}%)")
            print(f"   🖱️  Unique clicks:  {m.get('clicked', 0):,}")
            print(f"   🔙 Bounced:        {m.get('bounced', 0):,} ({m.get('bounce_rate', 0):.1f}%)")
            print(f"      Hard bounces:   {m.get('hard_bounces', 0)}")
            print(f"      Soft bounces:   {m.get('soft_bounces', 0)}")
            print(f"   🚫 Spam reports:   {m.get('spam_complaints', 0)} ({m.get('spam_rate', 0):.3f}%)")
            print(f"   ⛔ Blocked:        {m.get('blocked', 0)}")
            print(f"   ❌ Invalid:        {m.get('invalid', 0)}")

        print(f"\n{'─'*60}")
        for issue in health['issues']:
            print(f"   {issue}")

        # Sender pool status
        print(f"\n{'─'*60}")
        print("📋 SENDER POOL:")
        for sender in self.SENDER_POOL:
            state = self.health_state.get('senders', {}).get(sender['email'], {})
            is_active = sender['email'] == current['email']
            status = state.get('status', 'unknown')
            rotated_out = state.get('rotated_out_at')

            marker = "→" if is_active else " "
            status_icon = {'green': '🟢', 'yellow': '🟡', 'red': '🔴'}.get(status, '⚪')

            cooldown_note = ""
            if rotated_out:
                rot_time = datetime.fromisoformat(rotated_out)
                cooldown_end = rot_time + timedelta(days=self.THRESHOLDS['cooldown_days'])
                if datetime.now() < cooldown_end:
                    remaining = (cooldown_end - datetime.now()).days
                    cooldown_note = f" (cooldown: {remaining}d remaining)"

            print(f"   {marker} {status_icon} {sender['email']} — {sender['domain']}{cooldown_note}")

        # Rotation history
        log = self.health_state.get('rotation_log', [])
        if log:
            print(f"\n{'─'*60}")
            print("🔄 ROTATION HISTORY (last 5):")
            for entry in log[-5:]:
                print(f"   {entry['date'][:16]} | {entry['from']} → {entry['to']}")
                print(f"     Reason: {entry['reason'][:80]}")

        # Spam reporters
        print(f"\n{'─'*60}")
        reporters = self.get_spam_reporters(days=30)
        if reporters:
            print(f"🚫 SPAM REPORTERS (last 30 days): {len(reporters)}")
            for r in list(reporters)[:10]:
                print(f"   - {r}")
            if len(reporters) > 10:
                print(f"   ... and {len(reporters) - 10} more")
        else:
            print("🚫 Spam reporters (last 30 days): None 🎉")

        # Hard bounces
        bounces = self.get_hard_bounces(days=30)
        if bounces:
            print(f"🔙 HARD BOUNCES (last 30 days): {len(bounces)}")
            for b in list(bounces)[:10]:
                print(f"   - {b}")
            if len(bounces) > 10:
                print(f"   ... and {len(bounces) - 10} more")

        print(f"\n{'='*60}")


if __name__ == '__main__':
    import sys
    monitor = DeliverabilityMonitor()

    if '--report' in sys.argv:
        monitor.print_health_report()
    elif '--rotate' in sys.argv:
        monitor.rotate_sender(reason="Manual rotation requested")
    elif '--check' in sys.argv:
        monitor.check_and_rotate_if_needed()
    elif '--clean' in sys.argv:
        # Load campaign state and clean bad recipients
        state_file = Path(__file__).parent.parent / 'cache' / 'retention_state.json'
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
            monitor.clean_bad_recipients(state)
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        else:
            print("No state file found")
    else:
        print("Usage: python scripts/deliverability_monitor.py [--check|--report|--rotate|--clean]")
