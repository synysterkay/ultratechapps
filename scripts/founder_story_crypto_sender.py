#!/usr/bin/env python3
"""
Predictify Crypto founder-story — lapsed catch-up via Auth export.

Bulk backfill is frozen (value-first). Daily: ≥14d signup, once-ever, small cap.

Usage:
  python3 scripts/founder_story_crypto_sender.py --dry-run
  python3 scripts/founder_story_crypto_sender.py --print-template
  python3 scripts/founder_story_crypto_sender.py --print-template --v2
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, has_email_credentials, SKIP_RESULTS
from firebase_user_loader import FirebaseUserLoader

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / 'predictify_crypto' / 'templates'
STATE_FILE = ROOT.parent / 'cache' / 'crypto_founder_story_state.json'
APP_SLUG = 'predictify_crypto'
KIND = 'founder_story_crypto'
PLAY = 'https://play.google.com/store/apps/details?id=com.crypto.trading.ai.analyzer'
LAPSED_DAYS = int(os.getenv('FOUNDER_STORY_LAPSED_DAYS', '14'))
DAILY_CAP = int(os.getenv('FOUNDER_STORY_CRYPTO_DAILY_CAP', '50'))
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


def _ref(email: str) -> str:
    return hashlib.sha256(f'{_REF_SALT}:{email.lower()}'.encode()).hexdigest()[:16]


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'users': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _users_from_export():
    loader = FirebaseUserLoader()
    for name in (
        'cryptopredictify_fresh.json',
        'cryptopredictify_users.json',
        'crypto_predictify_fresh.json',
    ):
        path = loader.exports_dir / name
        if path.exists():
            try:
                data = json.loads(path.read_text())
                users = data if isinstance(data, list) else data.get('users', [])
                if users:
                    print(f'   📦 using export {path.name} ({len(users)})')
                    return users
            except Exception:
                pass
    return []


def _email_of(u: dict) -> str:
    return (u.get('email') or u.get('Email') or '').strip().lower()


def _first_name(u: dict, email: str) -> str:
    dn = (u.get('displayName') or '').strip()
    if dn:
        return dn.split()[0]
    local = email.split('@')[0]
    return local[:1].upper() + local[1:] if local else 'there'


def _created_days(u: dict) -> int | None:
    for key in ('createdAt', 'creationTime', 'created_at'):
        raw = u.get(key)
        if raw is None or raw == '':
            continue
        try:
            if isinstance(raw, str) and raw.isdigit():
                raw = int(raw)
            if isinstance(raw, (int, float)):
                dt = datetime.fromtimestamp(
                    raw / (1000 if raw > 1e12 else 1), tz=timezone.utc,
                )
            else:
                dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
            return (datetime.now(timezone.utc) - dt).days
        except Exception:
            continue
    return None


def _fill(text: str, first_name: str) -> str:
    return text.replace('{first_name}', first_name).replace('{{first_name}}', first_name)


def _build_html(paragraphs: list[str], cta: str) -> str:
    paras = ''.join(
        f'<p style="margin:0 0 16px;color:#1f2937;font-size:15px;line-height:1.6">'
        f'{html_lib.escape(p)}</p>'
        for p in paragraphs
    )
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Predictify Crypto</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:580px;margin:0 auto;background:#fff;padding:32px 24px">
<div style="font-size:22px;font-weight:800;color:#0E1117;margin-bottom:6px">Predictify Crypto</div>
<div style="height:1px;background:#e5e7eb;margin:16px 0 24px"></div>
{paras}
<div style="text-align:center;margin:28px 0">
<a href="{PLAY}" style="display:inline-block;padding:14px 28px;background:#3B82F6;color:#fff;text-decoration:none;border-radius:10px;font-weight:700;font-size:15px">{html_lib.escape(cta)}</a>
</div>
<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af;text-align:center">
You're receiving this because you signed up for Predictify Crypto.
<br><a href="https://predictifyfootball.com/unsubscribe" style="color:#9ca3af">Unsubscribe</a>
</div>
</div></body></html>'''


def main(dry_run=False):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--print-template', action='store_true')
    parser.add_argument('--v2', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--backfill', action='store_true')
    args, _ = parser.parse_known_args()
    dry_run = dry_run or args.dry_run

    kind = 'founder_story_crypto_v2' if args.v2 else 'founder_story_crypto'
    path = TEMPLATES / f'{kind}_en.json'
    if not path.exists():
        raise SystemExit(f'Missing {path}')
    data = json.loads(path.read_text(encoding='utf-8'))

    if args.print_template:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if args.backfill:
        print('⏭️ Crypto founder-story bulk backfill frozen (value-first stack)')
        return

    state = _load_state()
    users = _users_from_export()
    if not users:
        print('⚠️ No Crypto Auth export — skip founder story')
        return

    candidates = []
    for u in users:
        email = _email_of(u)
        if not email or '@' not in email:
            continue
        if 'cloudtestlabaccounts.com' in email or 'example.com' in email:
            continue
        if (state.get('users', {}).get(email) or {}).get('founder_v1'):
            continue
        days = _created_days(u)
        if days is None or days < LAPSED_DAYS:
            continue
        candidates.append((email, days, _first_name(u, email)))

    print(f'📈 {len(candidates)} Crypto founder candidates ≥{LAPSED_DAYS}d (cap={DAILY_CAP})')
    candidates = candidates[:DAILY_CAP]
    if dry_run:
        for email, days, fn in candidates[:20]:
            print(f'   • {email}  age={days}d  name={fn}')
        print('🏁 DRY RUN')
        return
    if not candidates:
        return
    if not has_email_credentials():
        print('❌ Email credentials not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for email, days, first_name in candidates:
        subject = _fill(data['subject'], first_name)
        body = [_fill(p, first_name) for p in data.get('body_paragraphs', [])]
        cta = data.get('cta_text', 'Scan one chart')
        html = _build_html(body, cta)
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': 'en'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html,
            from_name='Predictify', tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['users'][email] = {
                'founder_v1': True,
                'last_sent_at': datetime.now().isoformat(),
            }
            print(f'   ✅ [{sent}] {email}')
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} {result}')
        else:
            failed += 1
        time.sleep(0.25)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main()
