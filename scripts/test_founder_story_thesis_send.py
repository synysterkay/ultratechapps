#!/usr/bin/env python3
"""Send a one-off Thesis Generator founder story preview email via ZeptoMail."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from founder_story_thesis_sender import (
    APP_NAME,
    APP_SLUG,
    APP_STORE_URL,
    EN_SOURCE,
    GOOGLE_PLAY_URL,
    KIND,
    TEMPLATE_KIND,
)
from gmail_sender import GmailSender
from thesis_email_chrome import render as render_email
from thesis_template_translator import get_localized
import localize_phrase


def main() -> None:
    parser = argparse.ArgumentParser(description='Send Thesis founder story test email')
    parser.add_argument('to', nargs='?', default=os.getenv('TEST_EMAIL', ''))
    parser.add_argument('--first-name', default='Ana')
    parser.add_argument('--topic', default='climate change policy in urban planning')
    parser.add_argument('--work-type', default='fullThesis')
    parser.add_argument('--lang', default='en')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.to:
        print('Usage: python scripts/test_founder_story_thesis_send.py you@example.com')
        sys.exit(1)

    os.environ.setdefault('EMAIL_PROVIDER', 'zeptomail')
    os.environ.setdefault('ZEPTOMAIL_THESIS_SENDER_EMAIL', 'hello@thesisgenerator.io')
    os.environ.setdefault('ZEPTOMAIL_THESIS_SENDER_NAME', 'Thesis Generator')

    plan = {
        'first_name': args.first_name,
        'topic': args.topic,
        'work_type': args.work_type,
    }
    lang = args.lang
    tpl = get_localized(TEMPLATE_KIND, lang, EN_SOURCE, allow_api=False)
    subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
    preview = localize_phrase.interpolate(
        lang, tpl.get('preview', EN_SOURCE.get('preview', '')), plan,
    )
    paragraphs = [
        localize_phrase.interpolate(lang, p, plan)
        for p in tpl.get('body', EN_SOURCE['body'])
    ]
    cta_ios = localize_phrase.interpolate(
        lang, tpl.get('cta_ios', EN_SOURCE.get('cta_ios', 'App Store')), plan,
    )
    cta_android = localize_phrase.interpolate(
        lang, tpl.get('cta_android', EN_SOURCE.get('cta_android', 'Google Play')), plan,
    )

    html_body = render_email(
        lang,
        paragraphs,
        cta_ios,
        APP_STORE_URL,
        sender_name='Ana',
        app_name=APP_NAME,
        gradient='invite',
        preview_text=preview or None,
        cta_links=[
            {'url': APP_STORE_URL, 'variant': 'ios', 'line2': cta_ios},
            {'url': GOOGLE_PLAY_URL, 'variant': 'android', 'line2': cta_android},
        ],
    )

    if args.dry_run:
        out = os.path.join(ROOT, 'cache', 'founder_story_thesis_preview.html')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html_body)
        print(f'[DRY RUN] Wrote preview to {out}')
        print(f'Subject: {subject}')
        print(f'Preview: {preview}')
        return

    sender = GmailSender(
        sender_email=os.environ['ZEPTOMAIL_THESIS_SENDER_EMAIL'],
        sender_name=os.environ['ZEPTOMAIL_THESIS_SENDER_NAME'],
    )
    if not sender.connect():
        sys.exit(1)

    result = sender.send_email(
        to_email=args.to,
        subject=f'[TEST] {subject}',
        html_body=html_body,
        from_name=APP_NAME,
        tags=[
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': f'{KIND}_test'},
            {'name': 'language', 'value': lang},
            {'name': 'system', 'value': 'test'},
        ],
        ref_id='thesis-founder-story-test',
    )
    print(f'Result: {result}')
    sys.exit(0 if result == 'sent' else 1)


if __name__ == '__main__':
    main()
