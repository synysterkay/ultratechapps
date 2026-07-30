#!/usr/bin/env python3
"""Send a one-off Predictify yearly Pro promo preview email via ZeptoMail."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from predictify_v2.pro_yearly_promo_html import (
    PREVIEW,
    SUBJECT,
    build_pro_yearly_promo_html,
)
from gmail_sender import GmailSender


def _unsub_url(email: str) -> str:
    base = os.getenv(
        'PREDICTIFY_UNSUBSCRIBE_URL',
        'https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-unsubscribe',
    )
    secret = os.getenv('PREDICTIFY_UNSUBSCRIBE_SECRET', '')
    payload = f'{email.lower().strip()}|predictify'.encode('utf-8')
    e = base64.urlsafe_b64encode(payload).rstrip(b'=').decode('ascii')
    if secret:
        s = hmac.new(secret.encode('utf-8'), e.encode('ascii'), hashlib.sha256).hexdigest()[:32]
        return f'{base}?e={e}&s={s}'
    return f'{base}?e={e}'


def main() -> None:
    parser = argparse.ArgumentParser(description='Send Predictify Pro promo test email')
    parser.add_argument('to', nargs='?', default=os.getenv('TEST_EMAIL', ''))
    parser.add_argument('--first-name', default='Ana')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.to:
        print('Usage: python scripts/test_predictify_pro_promo_send.py you@example.com')
        sys.exit(1)

    os.environ.setdefault('EMAIL_PROVIDER', 'zeptomail')
    os.environ.setdefault('PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL', 'hello@predictifyfootball.com')
    os.environ.setdefault('PREDICTIFY_ZEPTOMAIL_SENDER_NAME', 'Predictify')

    html_body = build_pro_yearly_promo_html(
        first_name=args.first_name,
        unsub_url=_unsub_url(args.to),
        test_banner=True,
    )

    if args.dry_run:
        out = os.path.join(ROOT, 'cache', 'predictify_pro_promo_preview.html')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html_body)
        print(f'[DRY RUN] Wrote preview to {out}')
        print(f'Subject: {SUBJECT}')
        print(f'Preview: {PREVIEW}')
        return

    sender = GmailSender(
        sender_email=os.environ['PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL'],
        sender_name=os.environ['PREDICTIFY_ZEPTOMAIL_SENDER_NAME'],
    )
    if not sender.connect():
        sys.exit(1)

    result = sender.send_email(
        to_email=args.to,
        subject=f'[TEST] {SUBJECT}',
        html_body=html_body,
        from_name='Predictify',
        tags=[
            {'name': 'app', 'value': 'predictify'},
            {'name': 'kind', 'value': 'pro_yearly_promo_test'},
            {'name': 'system', 'value': 'test'},
        ],
        ref_id='predictify-pro-promo-test',
    )
    print(f'Result: {result}')
    sys.exit(0 if result == 'sent' else 1)


if __name__ == '__main__':
    main()
