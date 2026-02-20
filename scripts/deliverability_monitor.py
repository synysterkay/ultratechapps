#!/usr/bin/env python3
"""
Email Deliverability Monitor & Sender Rotation

Monitors Brevo email health metrics (opens, bounces, spam complaints).
When a sender's reputation degrades below configurable thresholds,
automatically rotates to the next healthy sender identity.

Sender identities can be:
  - Different emails on the same domain (apps@kaynel.pl, hello@kaynel.pl)
  - Different domains entirely (apps@kaynel.pl, noreply@ultratechapps.com)

Usage:
  python scripts/deliverability_monitor.py --check       # Check current health
  python scripts/deliverability_monitor.py --report      # Detailed report
  python scripts/deliverability_monitor.py --rotate      # Force rotation
"""
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta


class DeliverabilityMonitor:
    """
    Monitors email deliverability via Brevo API and manages sender rotation.
    
    Metrics tracked:
    - Open rate (below 5% = red flag for spam folder placement)
    - Bounce rate (above 3% = bad list hygiene, hurts reputation)
    - Spam complaint rate (above 0.1% = critical — ISPs will block you)
    - Block rate (Brevo-reported hard blocks)
    
    Decision logic:
    - GREEN: open rate > 15%, spam < 0.05%, bounce < 2%
    - YELLOW: open rate 5-15%, or spam 0.05-0.1%, or bounce 2-3%
    - RED: open rate < 5%, or spam > 0.1%, or bounce > 3%
    - On RED → auto-rotate to next sender
    """

    # ── SENDER IDENTITIES (add new senders here) ───────────
    # Order matters: first = primary, rest = fallbacks.
    # Each entry needs to be verified in Brevo dashboard first!
    SENDER_POOL = [
        {
            "email": "apps@kaynel.pl",
            "name": "Ana",
            "domain": "kaynel.pl",
            "active": True,
        },
        # ── Add backup senders below ──
        # {
        #     "email": "hello@kaynel.pl",
        #     "name": "Ana",
        #     "domain": "kaynel.pl",
        #     "active": True,
        # },
        # {
        #     "email": "noreply@ultratechapps.com",
        #     "name": "Ana",
        #     "domain": "ultratechapps.com",
        #     "active": True,
        # },
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
        self.api_key = os.getenv('BREVO_API_KEY')
        self.base_dir = Path(__file__).parent.parent
        self.health_file = self.base_dir / 'cache' / 'sender_health.json'
        self.health_file.parent.mkdir(exist_ok=True)
        self.health_state = self._load_health_state()

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

    # ── BREVO API QUERIES ───────────────────────────────────

    def _brevo_get(self, endpoint, params=None):
        """Make authenticated GET request to Brevo API"""
        import requests
        url = f"https://api.brevo.com/v3{endpoint}"
        headers = {'api-key': self.api_key, 'Accept': 'application/json'}
        try:
            resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"   ⚠️ Brevo API {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"   ❌ Brevo API error: {e}")
            return None

    def fetch_email_events(self, days=7, sender_email=None):
        """
        Fetch aggregated email statistics from Brevo.
        Returns dict with counts for: sent, delivered, opened, bounced, spam, blocked
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Brevo aggregated report
        params = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
        }

        # Get aggregated stats
        data = self._brevo_get('/smtp/statistics/aggregatedReport', params)
        if not data:
            return None

        result = {
            'sent': data.get('requests', 0),
            'delivered': data.get('delivered', 0),
            'opened': data.get('uniqueOpens', 0),  # unique opens more reliable
            'clicked': data.get('uniqueClicks', 0),
            'bounced': data.get('hardBounces', 0) + data.get('softBounces', 0),
            'hard_bounces': data.get('hardBounces', 0),
            'soft_bounces': data.get('softBounces', 0),
            'spam_complaints': data.get('spamReports', 0),
            'blocked': data.get('blocked', 0),
            'invalid': data.get('invalid', 0),
        }

        return result

    def fetch_event_log(self, event_type='spam', days=7, limit=50):
        """
        Fetch specific event log entries (e.g., who marked as spam).
        Useful for identifying problematic recipients.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        params = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'event': event_type,  # spam, hardBounces, softBounces, blocked
            'limit': limit,
        }
        
        data = self._brevo_get('/smtp/statistics/events', params)
        if data and 'events' in data:
            return data['events']
        return []

    # ── HEALTH EVALUATION ───────────────────────────────────

    def evaluate_sender_health(self, sender_email=None):
        """
        Evaluate current sender's deliverability health.
        Returns: {status: 'green'|'yellow'|'red', metrics: {...}, issues: [...]}
        """
        if not self.api_key:
            return {'status': 'unknown', 'metrics': {}, 'issues': ['No BREVO_API_KEY set']}

        metrics = self.fetch_email_events(days=self.THRESHOLDS['lookback_days'])
        if not metrics:
            return {'status': 'unknown', 'metrics': {}, 'issues': ['Could not fetch metrics from Brevo']}

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
        if open_rate < self.THRESHOLDS['open_rate_red']:
            issues.append(f"🚨 CRITICAL: Open rate {open_rate:.1f}% suggests emails going to spam")
            status = 'red'
        elif open_rate < self.THRESHOLDS['open_rate_yellow']:
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
            print("   Then verify them in Brevo dashboard: https://app.brevo.com/senders")
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
        Returns the sender to use (may be same or rotated).
        """
        print("\n📊 Checking email deliverability health...")
        health = self.evaluate_sender_health()
        current = self.get_active_sender()

        for issue in health['issues']:
            print(f"   {issue}")

        if health['status'] == 'red':
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

    def get_spam_reporters(self, days=7):
        """
        Get list of users who reported emails as spam.
        These should be immediately removed from future sends.
        """
        events = self.fetch_event_log(event_type='spam', days=days)
        reporters = set()
        for event in events:
            email = event.get('email')
            if email:
                reporters.add(email)
        return reporters

    def get_hard_bounces(self, days=7):
        """
        Get list of emails that hard-bounced.
        These should be permanently removed (invalid addresses).
        """
        events = self.fetch_event_log(event_type='hardBounces', days=days)
        bounced = set()
        for event in events:
            email = event.get('email')
            if email:
                bounced.add(email)
        return bounced

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
