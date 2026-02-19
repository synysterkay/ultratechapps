#!/usr/bin/env python3
"""
Gmail SMTP Sender
Sends emails via Gmail SMTP with App Password authentication.
Handles rate limiting (500/day for free Gmail).
"""
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


class GmailSender:
    def __init__(self):
        self.gmail_address = os.getenv('GMAIL_ADDRESS')
        self.gmail_app_password = os.getenv('GMAIL_APP_PASSWORD')
        self.smtp_server = 'smtp.gmail.com'
        self.smtp_port = 587
        self.daily_limit = 450  # Stay under 500 to be safe
        self.delay_between_emails = 2  # seconds
        
        if not self.gmail_address or not self.gmail_app_password:
            raise ValueError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set")
        
        self._connection = None
    
    def connect(self):
        """Establish SMTP connection"""
        try:
            self._connection = smtplib.SMTP(self.smtp_server, self.smtp_port)
            self._connection.ehlo()
            self._connection.starttls()
            self._connection.ehlo()
            self._connection.login(self.gmail_address, self.gmail_app_password)
            print(f"✅ Connected to Gmail SMTP as {self.gmail_address}")
            return True
        except Exception as e:
            print(f"❌ Gmail SMTP connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close SMTP connection"""
        if self._connection:
            try:
                self._connection.quit()
            except:
                pass
            self._connection = None
    
    def send_email(self, to_email, subject, html_body, from_name="Anas from Best AI Apps"):
        """
        Send a single HTML email.
        Returns True on success, False on failure.
        """
        if not self._connection:
            if not self.connect():
                return False
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f'{from_name} <{self.gmail_address}>'
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach HTML body
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        try:
            self._connection.sendmail(self.gmail_address, to_email, msg.as_string())
            return True
        except smtplib.SMTPServerDisconnected:
            # Reconnect and retry once
            print("   ⚠️ SMTP disconnected, reconnecting...")
            if self.connect():
                try:
                    self._connection.sendmail(self.gmail_address, to_email, msg.as_string())
                    return True
                except Exception as e:
                    print(f"   ❌ Retry failed: {e}")
                    return False
            return False
        except Exception as e:
            print(f"   ❌ Send failed to {to_email}: {e}")
            return False
    
    def send_batch(self, emails, progress_callback=None):
        """
        Send a batch of emails with rate limiting.
        emails: list of dicts with keys: to, subject, html_body
        Returns: (sent_count, failed_count)
        """
        if not self.connect():
            return 0, len(emails)
        
        sent = 0
        failed = 0
        
        for i, email in enumerate(emails):
            if sent >= self.daily_limit:
                print(f"⚠️ Daily limit ({self.daily_limit}) reached. Stopping.")
                failed += len(emails) - i
                break
            
            success = self.send_email(
                to_email=email['to'],
                subject=email['subject'],
                html_body=email['html_body'],
                from_name=email.get('from_name', 'Anas from Best AI Apps')
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
            
            # Reconnect every 50 emails to prevent timeout
            if sent > 0 and sent % 50 == 0:
                print(f"   🔄 Reconnecting after {sent} emails...")
                self.disconnect()
                time.sleep(2)
                if not self.connect():
                    failed += len(emails) - i - 1
                    break
        
        self.disconnect()
        return sent, failed
