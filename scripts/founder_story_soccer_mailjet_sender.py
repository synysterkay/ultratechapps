#!/usr/bin/env python3
"""
Founder-story broadcast for Predictify Soccer via Mailjet + CSV list.

Sends personalized emails from predictify@aibettips.io using the
founder_story_soccer template. Dedup state lives in
cache/founder_story_soccer_mailjet_state.json so runs can resume safely.

Usage:
  export MAILJET_API_KEY=...
  export MAILJET_SECRET_KEY=...

  python3 scripts/founder_story_soccer_mailjet_sender.py --dry-run
  python3 scripts/founder_story_soccer_mailjet_sender.py --limit 5
  python3 scripts/founder_story_soccer_mailjet_sender.py --test-to you@example.com
  python3 scripts/founder_story_soccer_mailjet_sender.py
  python3 scripts/founder_story_soccer_mailjet_sender.py --verified-only
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print('Install requests: pip install requests')
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = (
    Path(__file__).parent / 'predictify_v2' / 'templates' / 'founder_story_soccer_en.json'
)
DEFAULT_CSV = ROOT / 'exports' / 'predictify_soccer.csv'
STATE_PATH = ROOT / 'cache' / 'founder_story_soccer_mailjet_state.json'

KIND = 'founder_story_soccer'
FROM_EMAIL = os.environ.get('MAILJET_FROM_EMAIL', 'predictify@aibettips.io')
FROM_NAME = os.environ.get('MAILJET_FROM_NAME', 'Predictify')
MAILJET_SEND_URL = 'https://api.mailjet.com/v3.1/send'
BATCH_SIZE = 50  # Mailjet max messages per Send API call
UNSUB_URL = os.environ.get(
    'PREDICTIFY_UNSUBSCRIBE_URL',
    'https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-unsubscribe',
)

APP_STORE_URL = 'https://apps.apple.com/app/predictify-football-ai/id6756571193'
GOOGLE_PLAY_URL = (
    'https://play.google.com/store/apps/details?id=com.predictify.soccer.prediction'
)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _load_template() -> dict:
    with open(TEMPLATE_PATH, encoding='utf-8') as f:
        return json.load(f)


def _first_name(display_name: str | None, email: str) -> str:
    name = (display_name or '').strip()
    if name:
        token = name.split()[0]
        # Drop obvious placeholders / emails-as-names
        if token and '@' not in token and len(token) > 1:
            return token[:1].upper() + token[1:] if token[0].islower() else token
    local = email.split('@')[0].split('.')[0].split('_')[0]
    if local and local.isalpha() and len(local) > 1:
        return local[:1].upper() + local[1:].lower()
    return 'there'


def _fill(text: str, first_name: str) -> str:
    return (text or '').replace('{first_name}', first_name)


def _build_html(tmpl: dict, first_name: str, unsub_url: str) -> str:
    subject = _fill(tmpl['subject'], first_name)
    preview = _fill(tmpl.get('preview_text', ''), first_name)
    paras = [_fill(p, first_name) for p in tmpl.get('body_paragraphs', [])]
    cta_text = _fill(tmpl.get('cta_text', 'Open Predictify'), first_name)
    ios_text = tmpl.get('cta_ios_text', 'Download on the App Store')
    android_text = tmpl.get('cta_android_text', 'Get it on Google Play')
    app_store = tmpl.get('app_store_url', APP_STORE_URL)
    play = tmpl.get('google_play_url', GOOGLE_PLAY_URL)

    body_parts = []
    for i, p in enumerate(paras):
        esc = html.escape(p).replace('\n', '<br>')
        is_ps = p.strip().startswith('P.S.')
        if is_ps:
            body_parts.append(
                '<div style="margin:24px 0 0;padding:14px 18px;background:#fffbeb;'
                'border-radius:8px;border:1px solid #fcd34d;">'
                f'<p style="margin:0;font-size:15px;color:#92400e;line-height:1.7;">{esc}</p>'
                '</div>'
            )
            continue
        size = '16px' if i == 0 else '15px'
        weight = 'font-weight:600;' if i == 0 else ''
        body_parts.append(
            f'<p style="margin:0 0 16px;color:#1f2937;font-size:{size};'
            f'line-height:1.65;{weight}">{esc}</p>'
        )

    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{html.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{html.escape(preview)}</div>
<div style="max-width:580px;margin:0 auto;background:#ffffff;padding:32px 24px">
  <div style="font-size:22px;font-weight:800;color:#0E1117;margin-bottom:6px">Predictify</div>
  <div style="font-size:13px;color:#6b7280;margin-bottom:4px">Football AI predictions</div>
  <div style="height:1px;background:#e5e7eb;margin:16px 0 24px"></div>
  {''.join(body_parts)}
  <div style="text-align:center;margin:28px 0 8px">
    <a href="{html.escape(play)}" style="display:inline-block;padding:14px 28px;background:#16a34a;color:#ffffff;text-decoration:none;border-radius:10px;font-weight:700;font-size:15px">{html.escape(cta_text)}</a>
  </div>
  <div style="text-align:center;margin:8px 0 0;font-size:13px;color:#6b7280;line-height:1.7">
    <a href="{html.escape(play)}" style="color:#16a34a;font-weight:600;text-decoration:none">{html.escape(android_text)}</a>
    &nbsp;·&nbsp;
    <a href="{html.escape(app_store)}" style="color:#2563eb;font-weight:600;text-decoration:none">{html.escape(ios_text)}</a>
  </div>
  <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af;text-align:center;line-height:1.6">
    You're receiving this because you signed up for Predictify.<br>
    <a href="{html.escape(unsub_url)}" style="color:#9ca3af">Unsubscribe</a>
  </div>
</div>
</body>
</html>'''


def _build_text(tmpl: dict, first_name: str, unsub_url: str) -> str:
    paras = [_fill(p, first_name) for p in tmpl.get('body_paragraphs', [])]
    cta = _fill(tmpl.get('cta_text', 'Open Predictify'), first_name)
    play = tmpl.get('google_play_url', GOOGLE_PLAY_URL)
    app_store = tmpl.get('app_store_url', APP_STORE_URL)
    return '\n\n'.join([
        'PREDICTIFY',
        *paras,
        f'{cta}\nAndroid: {play}\niOS: {app_store}',
        f"You're receiving this because you signed up for Predictify.\nUnsubscribe: {unsub_url}",
    ])


def _unsub_url(email: str) -> str:
    import base64
    payload = f'{email.lower().strip()}|predictify_soccer'.encode('utf-8')
    e = base64.urlsafe_b64encode(payload).rstrip(b'=').decode('ascii')
    return f'{UNSUB_URL}?e={e}'


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'kind': KIND, 'sent': {}, 'failed': {}, 'started_at': _utc_now()}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state['updated_at'] = _utc_now()
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


def _load_recipients(csv_path: Path, verified_only: bool) -> list[dict]:
    rows = []
    seen = set()
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            email = (row.get('email') or '').strip().lower()
            if not email or email in seen:
                continue
            if not EMAIL_RE.match(email):
                continue
            if verified_only and str(row.get('email_verified', '')).lower() != 'true':
                continue
            seen.add(email)
            rows.append({
                'email': email,
                'uid': (row.get('uid') or '').strip(),
                'display_name': (row.get('display_name') or '').strip(),
                'first_name': _first_name(row.get('display_name'), email),
            })
    return rows


def _auth() -> tuple[str, str]:
    key = os.environ.get('MAILJET_API_KEY', '').strip()
    secret = os.environ.get('MAILJET_SECRET_KEY', '').strip()
    if not key or not secret:
        raise SystemExit(
            'Set MAILJET_API_KEY and MAILJET_SECRET_KEY in the environment '
            '(do not hardcode secrets in files).'
        )
    return key, secret


def verify_mailjet() -> dict:
    key, secret = _auth()
    r = requests.get(
        'https://api.mailjet.com/v3/REST/sender',
        auth=(key, secret),
        params={'Limit': 50},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _message_for(tmpl: dict, recipient: dict) -> dict:
    first = recipient['first_name']
    unsub = _unsub_url(recipient['email'])
    subject = _fill(tmpl['subject'], first)
    return {
        'From': {'Email': FROM_EMAIL, 'Name': FROM_NAME},
        'To': [{'Email': recipient['email'], 'Name': first}],
        'Subject': subject,
        'TextPart': _build_text(tmpl, first, unsub),
        'HTMLPart': _build_html(tmpl, first, unsub),
        'CustomID': f'{KIND}:{recipient.get("uid") or recipient["email"]}',
        'Headers': {
            'List-Unsubscribe': f'<{unsub}>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
            'X-Campaign': KIND,
        },
    }


def send_batch(messages: list[dict]) -> dict:
    key, secret = _auth()
    r = requests.post(
        MAILJET_SEND_URL,
        auth=(key, secret),
        json={'Messages': messages},
        timeout=60,
    )
    try:
        data = r.json()
    except Exception:
        data = {'raw': r.text}
    if r.status_code >= 400:
        raise RuntimeError(f'Mailjet HTTP {r.status_code}: {data}')
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description='Predictify Soccer founder story via Mailjet')
    parser.add_argument('--csv', default=str(DEFAULT_CSV), help='Recipient CSV path')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0, help='Max new sends this run (0 = all)')
    parser.add_argument(
        '--campaign-cap',
        type=int,
        default=int(os.environ.get('FOUNDER_STORY_SOCCER_CAMPAIGN_CAP', '0') or 0),
        help='Hard max total sends across runs (0 = unlimited). Already-sent count counts toward this.',
    )
    parser.add_argument('--verified-only', action='store_true')
    parser.add_argument('--test-to', default='', help='Send one personalized sample to this address')
    parser.add_argument('--sleep', type=float, default=0.35, help='Pause between batches (seconds)')
    parser.add_argument('--reset-failed', action='store_true', help='Retry previously failed emails')
    args = parser.parse_args()

    tmpl = _load_template()
    print(f'Template: {TEMPLATE_PATH.name} ({tmpl["kind"]})')
    print(f'From: {FROM_NAME} <{FROM_EMAIL}>')
    print(f'Subject: {tmpl["subject"]}')

    if args.test_to:
        recipient = {
            'email': args.test_to.strip().lower(),
            'uid': 'test',
            'display_name': 'Friend',
            'first_name': 'Friend',
        }
        msg = _message_for(tmpl, recipient)
        if args.dry_run:
            print(f'[DRY] would send test to {recipient["email"]}: {msg["Subject"]!r}')
            print(msg['TextPart'][:400], '...')
            return
        print(f'Sending test to {recipient["email"]}…')
        data = send_batch([msg])
        print(json.dumps(data, indent=2)[:1200])
        return

    # Verify credentials / sender domain before blasting.
    if not args.dry_run:
        try:
            senders = verify_mailjet()
            emails = {
                (s.get('Email') or '').lower()
                for s in (senders.get('Data') or [])
            }
            print(f'Mailjet senders visible: {len(emails)}')
            if FROM_EMAIL.lower() not in emails:
                print(
                    f'⚠️  {FROM_EMAIL} not in Mailjet sender list yet — '
                    'send may fail until the address/domain is verified.'
                )
            else:
                print(f'✅ Sender {FROM_EMAIL} found in Mailjet')
        except Exception as e:
            raise SystemExit(f'Mailjet auth/sender check failed: {e}')

    recipients = _load_recipients(Path(args.csv), verified_only=args.verified_only)
    state = _load_state()
    sent = state.setdefault('sent', {})
    failed = state.setdefault('failed', {})

    pending = []
    for r in recipients:
        em = r['email']
        if em in sent:
            continue
        if em in failed and not args.reset_failed:
            continue
        pending.append(r)

    if args.campaign_cap and args.campaign_cap > 0:
        remaining_cap = max(0, args.campaign_cap - len(sent))
        if remaining_cap == 0:
            print(
                f'Campaign cap reached ({len(sent)}/{args.campaign_cap}). '
                'Nothing more to send until you raise --campaign-cap.'
            )
            return
        pending = pending[:remaining_cap]
        print(f'Campaign cap: {args.campaign_cap} (room left this run: {remaining_cap})')

    if args.limit and args.limit > 0:
        pending = pending[: args.limit]

    print(f'CSV recipients: {len(recipients)}')
    print(f'Already sent: {len(sent)} | previously failed skipped: {len(failed)}')
    print(f'To send this run: {len(pending)}')

    if args.dry_run:
        for r in pending[:5]:
            subj = _fill(tmpl['subject'], r['first_name'])
            print(f'  [DRY] {r["email"]} → {subj!r}')
        if len(pending) > 5:
            print(f'  … and {len(pending) - 5} more')
        return

    if not pending:
        print('Nothing to send.')
        return

    ok = 0
    err = 0
    for i in range(0, len(pending), BATCH_SIZE):
        chunk = pending[i : i + BATCH_SIZE]
        messages = [_message_for(tmpl, r) for r in chunk]
        try:
            data = send_batch(messages)
            results = data.get('Messages') or []
            for r, res in zip(chunk, results):
                status = (res.get('Status') or '').lower()
                if status == 'success':
                    sent[r['email']] = {
                        'sent_at': _utc_now(),
                        'first_name': r['first_name'],
                        'uid': r.get('uid', ''),
                    }
                    failed.pop(r['email'], None)
                    ok += 1
                else:
                    failed[r['email']] = {
                        'at': _utc_now(),
                        'error': res,
                    }
                    err += 1
            # Handle length mismatch (treat extras as failed)
            if len(results) < len(chunk):
                for r in chunk[len(results) :]:
                    failed[r['email']] = {'at': _utc_now(), 'error': 'missing_result'}
                    err += 1
        except Exception as e:
            print(f'Batch error at offset {i}: {e}')
            for r in chunk:
                failed[r['email']] = {'at': _utc_now(), 'error': str(e)}
                err += 1

        _save_state(state)
        done = min(i + BATCH_SIZE, len(pending))
        print(f'  Progress {done}/{len(pending)} — ok={ok} err={err}')
        if i + BATCH_SIZE < len(pending):
            time.sleep(max(0.0, args.sleep))

    print(f'\nDone. Sent={ok} Failed={err} State={STATE_PATH}')


if __name__ == '__main__':
    main()
