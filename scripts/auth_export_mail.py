#!/usr/bin/env python3
"""Shared helpers for Auth-export tip / founder senders (value-first, free-only)."""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from firebase_user_loader import FirebaseUserLoader, FIREBASE_APPS
from free_user_gate import filter_free_users
from gmail_sender import GmailSender, SKIP_RESULTS, has_email_credentials

_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
CACHE = Path(__file__).parent.parent / 'cache'


def ref_id(email: str) -> str:
    return hashlib.sha256(f'{_REF_SALT}:{email.lower().strip()}'.encode()).hexdigest()[:16]


def email_of(u: dict) -> str:
    return (u.get('email') or u.get('Email') or '').strip().lower()


def created_days(u: dict) -> int | None:
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


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'users': {}}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding='utf-8')


def load_users_by_export_names(names: list[str]) -> list[dict]:
    loader = FirebaseUserLoader()
    for name in names:
        path = loader.exports_dir / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            users = data if isinstance(data, list) else data.get('users', [])
            if users:
                print(f'   📦 using export {path.name} ({len(users)})')
                return users
        except Exception:
            continue
    # Fallback: match FIREBASE_APPS export_file
    by_file = {info['export_file']: info for info in FIREBASE_APPS.values()}
    for name in names:
        if name in by_file:
            path = loader.exports_dir / name
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding='utf-8'))
                    users = data if isinstance(data, list) else data.get('users', [])
                    if users:
                        return users
                except Exception:
                    pass
    return []


def load_users_for_firebase_name(app_display_name: str) -> list[dict]:
    for info in FIREBASE_APPS.values():
        if info.get('name') == app_display_name:
            return load_users_by_export_names([info['export_file']])
    return []


def send_once_ever_founder(
    *,
    app_name: str,
    app_slug: str,
    kind: str,
    state_file: Path,
    export_names: list[str],
    store_url: str,
    subject: str,
    body: list[str],
    cta: str,
    daily_cap: int,
    sender_name: str = 'Casey',
    dry_run: bool = False,
    first_name_of: Callable[[dict], str] | None = None,
) -> None:
    """Once-ever founder story to free Auth-export users (capped)."""
    state = load_state(state_file)
    users = load_users_by_export_names(export_names)
    if not users:
        print(f'⚠️ No Auth export for {app_name} — skip founder')
        return
    # Conversion: free Auth users only — skip Superwall payers via Firebase
    users = filter_free_users(
        users, app_slug, email_of, require_firebase=not dry_run,
    )
    if not users:
        print(f'⚠️ No free users for {app_name} founder — skip')
        return

    candidates = []
    for u in users:
        email = email_of(u)
        if not email or '@' not in email:
            continue
        if email in (state.get('users') or {}):
            continue
        if GmailSender.already_emailed_today(email):
            continue
        fn = ''
        if first_name_of:
            fn = first_name_of(u) or ''
        else:
            fn = (u.get('displayName') or u.get('first_name') or '').split(' ')[0]
        candidates.append((email, fn or 'there'))

    print(f'✉️  {len(candidates)} {app_name} founder candidates (free only, cap={daily_cap})')
    candidates = candidates[:daily_cap]
    if dry_run:
        for email, fn in candidates[:20]:
            print(f'   • {email}  name={fn}')
        print('🏁 DRY RUN')
        return
    if not candidates:
        return
    if not has_email_credentials():
        print('❌ Email credentials not set')
        return

    from thesis_email_chrome import render as render_email

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for email, fn in candidates:
        subj = subject.replace('{first_name}', fn).replace('{{first_name}}', fn)
        paragraphs = [
            p.replace('{first_name}', fn).replace('{{first_name}}', fn) for p in body
        ]
        html = render_email(
            'en', paragraphs, cta, store_url,
            sender_name=sender_name, app_name=app_name, gradient='invite',
        )
        tags = [
            {'name': 'app', 'value': app_slug},
            {'name': 'kind', 'value': kind},
            {'name': 'language', 'value': 'en'},
        ]
        result = sender.send_email(
            to_email=email, subject=subj, html_body=html,
            from_name=app_name, tags=tags, ref_id=ref_id(email),
        )
        if result == 'sent':
            sent += 1
            state['users'][email] = {
                'sent_at': datetime.now().isoformat(),
                'kind': kind,
            }
            print(f'   ✅ [{sent}] {email}')
            if sent % 20 == 0:
                save_state(state_file, state)
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} {result}')
        else:
            failed += 1
            print(f'   ❌ {email} {result}')
        time.sleep(0.2)

    sender.disconnect()
    save_state(state_file, state)
    print(f'📊 Done — sent {sent}, failed {failed}')


def send_staged_tips(
    *,
    app_name: str,
    app_slug: str,
    kind: str,
    state_file: Path,
    export_names: list[str],
    store_url: str,
    stages: list[tuple[str, int, int]],
    en_sources: dict,
    daily_cap: int,
    sender_name: str = 'Casey',
    dry_run: bool = False,
) -> None:
    """Age-banded once-ever tip stages (same pattern as Fresh Start tips)."""
    state = load_state(state_file)
    users = load_users_by_export_names(export_names)
    if not users:
        print(f'⚠️ No Auth export for {app_name} — skip tips')
        return
    # Conversion: free Auth users only — skip Superwall payers via Firebase
    users = filter_free_users(
        users, app_slug, email_of, require_firebase=not dry_run,
    )
    if not users:
        print(f'⚠️ No free users for {app_name} tips — skip')
        return

    candidates = []
    for u in users:
        email = email_of(u)
        if not email or '@' not in email:
            continue
        if GmailSender.already_emailed_today(email):
            continue
        days = created_days(u)
        if days is None:
            days = 30
        fired = set((state.get('users', {}).get(email) or {}).get('stages', []))
        for stage, lo, hi in stages:
            if stage in fired:
                continue
            if lo <= days <= hi:
                candidates.append((email, stage, days))
                break

    print(f'💛 {len(candidates)} {app_name} tip candidates (free only, cap={daily_cap})')
    candidates = candidates[:daily_cap]
    if dry_run:
        for email, stage, days in candidates[:20]:
            print(f'   • {email}  stage={stage}  age={days}d')
        print('🏁 DRY RUN')
        return
    if not candidates:
        return
    if not has_email_credentials():
        print('❌ Email credentials not set')
        return

    from thesis_email_chrome import render as render_email

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for email, stage, days in candidates:
        src = en_sources[stage]
        html = render_email(
            'en', src['body'], src['cta'], store_url,
            sender_name=sender_name, app_name=app_name, gradient='invite',
        )
        tags = [
            {'name': 'app', 'value': app_slug},
            {'name': 'kind', 'value': kind},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': 'en'},
        ]
        result = sender.send_email(
            to_email=email, subject=src['subject'], html_body=html,
            from_name=app_name, tags=tags, ref_id=ref_id(email),
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
        time.sleep(0.2)

    sender.disconnect()
    save_state(state_file, state)
    print(f'📊 Done — sent {sent}, failed {failed}')
