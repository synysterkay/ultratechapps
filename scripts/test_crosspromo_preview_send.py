#!/usr/bin/env python3
"""Send one Crosspromo Thesis preview email via ZeptoMail (does not enroll/run campaign).

Usage:
  python3 scripts/test_crosspromo_preview_send.py anaskay.13@gmail.com
  python3 scripts/test_crosspromo_preview_send.py anaskay.13@gmail.com --stage e1 --first-name Ana
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from crosspromo_thesis_sender import (
    APP_STORE_URL,
    CROSSPROMO_FROM,
    EN_SOURCES,
    KIND_PREFIX,
    crosspromo_render_kwargs,
)
from gmail_sender import GmailSender
from thesis_email_chrome import render as render_email
from thesis_template_translator import get_localized, _write_cache
import localize_phrase


def main() -> None:
    parser = argparse.ArgumentParser(description='Send one crosspromo Thesis preview')
    parser.add_argument('to', nargs='?', default=os.getenv('TEST_EMAIL', ''))
    parser.add_argument('--stage', default='e1', choices=list(EN_SOURCES.keys()))
    parser.add_argument('--first-name', default='Ana')
    parser.add_argument('--lang', default='en')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.to:
        print('Usage: python scripts/test_crosspromo_preview_send.py you@example.com')
        sys.exit(1)

    os.environ['EMAIL_PROVIDER'] = 'zeptomail'
    from_email = os.getenv('ZEPTOMAIL_PASSED_AI_SENDER_EMAIL', CROSSPROMO_FROM)
    from_name = os.getenv('ZEPTOMAIL_PASSED_AI_SENDER_NAME', 'Alex')
    os.environ.setdefault('ZEPTOMAIL_PASSED_AI_SENDER_EMAIL', from_email)
    os.environ.setdefault('ZEPTOMAIL_PASSED_AI_SENDER_NAME', from_name)

    stage = args.stage
    en_src = EN_SOURCES[stage]
    kind = f'{KIND_PREFIX}_{stage}'
    _write_cache(kind, 'en', en_src)

    lang = localize_phrase.normalize_language(args.lang)
    plan = {'first_name': args.first_name}
    tpl = get_localized(kind, lang, en_src, allow_api=False)
    subject = localize_phrase.interpolate(lang, tpl.get('subject', en_src['subject']), plan)
    subject = f'[PREVIEW] {subject}'
    paragraphs = [
        localize_phrase.interpolate(lang, p, plan)
        for p in tpl.get('body', en_src['body'])
    ]
    cta = tpl.get('cta', en_src['cta'])
    preview = tpl.get('preview', en_src.get('preview', ''))

    html = render_email(
        lang, paragraphs, cta, APP_STORE_URL,
        **crosspromo_render_kwargs(preview_text=preview or None),
    )

    print(f'To: {args.to}')
    print(f'Stage: {stage}  lang={lang}')
    print(f'Subject: {subject}')
    print(f'From (ZeptoMail pin): {from_email}')

    if args.dry_run:
        print('🏁 DRY RUN — not sent')
        print(html[:800], '...')
        return

    sender = GmailSender(sender_email=from_email, sender_name=from_name)
    if not sender.connect():
        sys.exit(1)

    result = sender.send_email(
        to_email=args.to,
        subject=subject,
        html_body=html,
        from_name=from_name,
        tags=[
            {'name': 'app', 'value': 'crosspromo'},
            {'name': 'kind', 'value': f'{kind}_preview'},
            {'name': 'system', 'value': 'crosspromotion_preview'},
            {'name': 'target', 'value': 'thesis'},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': lang},
        ],
        ref_id='crosspromo-preview',
    )
    sender.disconnect()
    print(f'Result: {result}')
    sys.exit(0 if result == 'sent' else 1)


if __name__ == '__main__':
    main()
