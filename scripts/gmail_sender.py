#!/usr/bin/env python3
"""
Resend Email Sender
Sends transactional emails via Resend API.
Cost: Free tier = 3,000 emails/month, then $20/month for 50K.

Drop-in replacement — same interface: connect(), send_email(), send_batch(), disconnect().
"""
import time
import os
import requests


# Keep class name GmailSender so nothing else needs to change
class GmailSender:
    """Resend email sender — same interface as previous senders."""

    API_URL = "https://api.resend.com/emails"

    def __init__(self, sender_email=None, sender_name=None):
        self.api_key = os.getenv('RESEND_API_KEY')
        self.sender_email = sender_email or 'apps@kaynel.pl'
        self.sender_name = sender_name or 'Ana'
        self.delay_between_emails = 0.15  # Resend allows ~10/sec
        self.connected = False

        if not self.api_key:
            raise ValueError("RESEND_API_KEY must be set")

    def connect(self):
        """Verify Resend API key works."""
        try:
            # Quick check: list domains
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
            else:
                print(f"❌ Resend auth failed: {resp.status_code} {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ Resend connection failed: {e}")
            return False

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

    def send_email(self, to_email, subject, html_body, from_name=None):
        """
        Send a single HTML email via Resend.
        Returns: 'sent' on success, 'bounced' if address is invalid, 'failed' otherwise.
        """
        if not self.connected:
            print("   ❌ Not connected. Call connect() first.")
            return 'failed'

        sender = f"{from_name or self.sender_name} <{self.sender_email}>"

        try:
            resp = requests.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": sender,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                    "reply_to": self.sender_email,
                },
                timeout=15,
            )

            if resp.status_code in (200, 201):
                return 'sent'

            # Rate limited — back off and retry once
            if resp.status_code == 429:
                print(f"   ⏳ Resend rate limited — backing off...")
                time.sleep(2)
                retry = requests.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": sender,
                        "to": [to_email],
                        "subject": subject,
                        "html": html_body,
                        "reply_to": self.sender_email,
                    },
                    timeout=15,
                )
                if retry.status_code in (200, 201):
                    return 'sent'

            error_msg = resp.text[:200]

            # Detect hard bounce
            if self._is_bounce(resp.status_code, resp.text):
                print(f"   🔴 BOUNCED: {to_email} — {error_msg}")
                return 'bounced'

            print(f"   ❌ Resend error [{resp.status_code}]: {error_msg}")
            return 'failed'
        except Exception as e:
            print(f"   ❌ Resend send error: {e}")
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
            )

            if result == 'sent':
                sent += 1
                if progress_callback:
                    progress_callback(email['to'], i + 1, len(emails))
            else:
                failed += 1

            # Rate limiting
            if i < len(emails) - 1:
                time.sleep(self.delay_between_emails)

        return sent, failed
