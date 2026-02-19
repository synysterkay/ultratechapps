#!/usr/bin/env python3
"""
Brevo (Sendinblue) Email Sender
Sends transactional emails via Brevo API.
Free tier: 300/day. Paid: scales cheaply.
Sender: hello@passedai.io
"""
import requests
import time
import os


# Keep class name GmailSender so nothing else needs to change
class GmailSender:
    def __init__(self):
        self.api_key = os.getenv('BREVO_API_KEY')
        self.sender_email = 'hello@passedai.io'
        self.sender_name = 'Anas'
        self.api_url = 'https://api.brevo.com/v3/smtp/email'
        self.delay_between_emails = 0.1  # seconds (small pause to avoid overwhelming API)
        
        if not self.api_key:
            raise ValueError("BREVO_API_KEY must be set")
    
    def connect(self):
        """Verify API key works (no persistent connection needed for REST API)"""
        try:
            resp = requests.get(
                'https://api.brevo.com/v3/account',
                headers={'api-key': self.api_key},
                timeout=10
            )
            if resp.status_code == 200:
                print(f"✅ Connected to Brevo as {self.sender_email}")
                return True
            else:
                print(f"❌ Brevo auth failed: {resp.status_code} - {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"❌ Brevo connection check failed: {e}")
            return False
    
    def disconnect(self):
        """No-op — Brevo is REST API, no persistent connection"""
        pass
    
    def send_email(self, to_email, subject, html_body, from_name=None):
        """
        Send a single HTML email via Brevo API.
        Returns True on success, False on failure.
        """
        headers = {
            'api-key': self.api_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'sender': {
                'name': from_name or self.sender_name,
                'email': self.sender_email,
            },
            'to': [{'email': to_email}],
            'subject': subject,
            'htmlContent': html_body,
        }
        try:
            resp = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                return True
            else:
                print(f"   ❌ Brevo error {resp.status_code}: {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"   ❌ Brevo send error: {e}")
            return False
    
    def send_batch(self, emails, progress_callback=None):
        """
        Send a batch of emails with rate limiting.
        emails: list of dicts with keys: to, subject, html_body
        Returns: (sent_count, failed_count)
        """
        sent = 0
        failed = 0
        
        for i, email in enumerate(emails):
            success = self.send_email(
                to_email=email['to'],
                subject=email['subject'],
                html_body=email['html_body'],
                from_name=email.get('from_name', 'Anas')
            )
            
            if success:
                sent += 1
                if progress_callback:
                    progress_callback(email['to'], i + 1, len(emails))
            else:
                failed += 1
            
            # Rate limiting
            if i < len(emails) - 1:
                time.sleep(self.delay_between_emails)
        
        return sent, failed
