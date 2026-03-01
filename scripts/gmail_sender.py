#!/usr/bin/env python3
"""
Amazon SES Email Sender
Sends transactional emails via AWS SES API.
Cost: $0.10 per 1,000 emails ($1/month for 10K emails).

Drop-in replacement for the old Brevo sender.
Same interface: connect(), send_email(), send_batch(), disconnect().
"""
import time
import os
import boto3
from botocore.exceptions import ClientError


# Keep class name GmailSender so nothing else needs to change
class GmailSender:
    """SES email sender — same interface as the old Brevo sender."""

    def __init__(self, sender_email=None, sender_name=None):
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_SES_REGION', 'us-east-1')
        self.sender_email = sender_email or 'apps@kaynel.pl'
        self.sender_name = sender_name or 'Ana'
        self.delay_between_emails = 0.3  # Stay under rate limit (adjusted on connect)
        self.client = None

        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set")

    def connect(self):
        """Create SES client and verify credentials work."""
        try:
            self.client = boto3.client(
                'ses',
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
            )
            # Quick check: get send quota
            quota = self.client.get_send_quota()
            max_rate = quota.get('MaxSendRate', 1)
            # Adjust delay to stay within rate limit (with 20% buffer)
            self.delay_between_emails = max(0.1, 1.0 / max_rate * 1.2)
            print(f"✅ Connected to SES as {self.sender_email} (rate: {max_rate}/sec)")
            return True
        except ClientError as e:
            print(f"❌ SES auth failed: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            print(f"❌ SES connection failed: {e}")
            return False

    def disconnect(self):
        """No-op — boto3 manages connections internally."""
        self.client = None

    def send_email(self, to_email, subject, html_body, from_name=None):
        """
        Send a single HTML email via SES.
        Returns True on success, False on failure.
        """
        if not self.client:
            print("   ❌ SES client not connected. Call connect() first.")
            return False

        sender = f"{from_name or self.sender_name} <{self.sender_email}>"

        try:
            self.client.send_email(
                Source=sender,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': {
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                    },
                },
                ReplyToAddresses=[self.sender_email],
            )
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            if error_code == 'Throttling':
                print(f"   ⏳ SES throttled — backing off...")
                time.sleep(2)
                try:
                    self.client.send_email(
                        Source=sender,
                        Destination={'ToAddresses': [to_email]},
                        Message={
                            'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                            'Body': {
                                'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                            },
                        },
                        ReplyToAddresses=[self.sender_email],
                    )
                    return True
                except Exception:
                    pass
            print(f"   ❌ SES error [{error_code}]: {error_msg[:150]}")
            return False
        except Exception as e:
            print(f"   ❌ SES send error: {e}")
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
                from_name=email.get('from_name', self.sender_name),
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
