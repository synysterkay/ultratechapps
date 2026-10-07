#!/usr/bin/env python3
"""Predictify Crypto value tips — Auth-export audience (Firestore activity TBD).

Stages map to tip templates. Soft CTA → scan one chart.
Tags: app=predictify_crypto, kind=crypto_tip, stage, language=en
"""
from __future__ import annotations

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

APP_NAME = 'Crypto AI: Trading Analyzer'
APP_SLUG = 'predictify_crypto'
KIND = 'crypto_tip'
PLAY = 'https://play.google.com/store/apps/details?id=com.crypto.trading.ai.analyzer'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'crypto_tip_state.json'
TEMPLATES = Path(__file__).parent / 'predictify_crypto' / 'templates'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
DAILY_CAP = int(os.getenv('CRYPTO_TIP_DAILY_CAP', '40'))

# (stage, template_kind, min_days, max_days)
STAGES = [
    ('welcome_backup', 'welcome_backup', 1, 3),
    ('analysis_tip', 'analysis_tip', 4, 21),
    ('win_back', 'win_back', 22, 9999),
]


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


def _load_tmpl(kind: str) -> dict:
    path = TEMPLATES / f'{kind}_en.json'
    return json.loads(path.read_text(encoding='utf-8'))


def _fill(text: str, first_name: str) -> str:
    return (
        text.replace('{first_name}', first_name)
        .replace('{{first_name}}', first_name)
    )


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
<p style="margin:16px 0 0;font-size:12px;color:#94a3b8;text-align:center">
<a href="{PLAY}" style="color:#64748b">Google Play</a>
</p>
<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af;text-align:center">
You're receiving this because you signed up for Predictify Crypto.
<br><a href="https://predictifyfootball.com/unsubscribe" style="color:#9ca3af">Unsubscribe</a>
</div>
</div></body></html>'''


def main(dry_run=False):
    state = _load_state()
    users = _users_from_export()
    if not users:
        print('⚠️ No Crypto Auth export found — skip tips (export cryptopredictify)')
        return

    tmpl_cache = {}
    for _, kind, _, _ in STAGES:
        tmpl_cache[kind] = _load_tmpl(kind)

    candidates = []
    for u in users:
        email = _email_of(u)
        if not email or '@' not in email:
            continue
        if 'cloudtestlabaccounts.com' in email or 'example.com' in email:
            continue
        days = _created_days(u)
        if days is None:
            days = 10
        fired = set((state.get('users', {}).get(email) or {}).get('stages', []))
        for stage, kind, lo, hi in STAGES:
            if stage in fired:
                continue
            if lo <= days <= hi:
                candidates.append(
                    (email, stage, kind, days, _first_name(u, email))
                )
                break

    print(f'📈 {len(candidates)} Crypto tip candidates (cap={DAILY_CAP})')
    candidates = candidates[:DAILY_CAP]
    if dry_run:
        for email, stage, kind, days, fn in candidates[:20]:
            print(f'   • {email}  stage={stage}  kind={kind}  age={days}d  name={fn}')
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
    for email, stage, kind, days, first_name in candidates:
        tmpl = tmpl_cache[kind]
        subject = _fill(tmpl['subject'], first_name)
        body = [_fill(p, first_name) for p in tmpl.get('body_paragraphs', [])]
        cta = tmpl.get('cta_text', 'Scan one chart')
        html = _build_html(body, cta)
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': 'en'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html,
            from_name='Predictify', tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent += 1
            rec = state['users'].setdefault(email, {'stages': []})
            if stage not in rec['stages']:
                rec['stages'].append(stage)
            rec['last_sent_at'] = datetime.now().isoformat()
            print(f'   ✅ [{sent}] {email}  {stage}')
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} {result}')
        else:
            failed += 1
        time.sleep(0.25)

    sender.disconnect()
    _save_state(state)
    print(f'📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
