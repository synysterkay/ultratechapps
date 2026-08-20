#!/usr/bin/env python3
"""Firestore loader for ONG (sealed-cce0a). Guests without email are skipped."""
from __future__ import annotations

import os
import requests
import subprocess
from datetime import datetime, timezone
from typing import Iterable

PROJECT_ID = 'sealed-cce0a'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def _f(fields: dict, key: str, default=None, kind: str = 'stringValue'):
    field = fields.get(key)
    if not field:
        return default
    return field.get(kind, default)


def _f_int(fields: dict, key: str, default: int = 0) -> int:
    v = fields.get(key, {})
    if 'integerValue' in v:
        try:
            return int(v['integerValue'])
        except Exception:
            return default
    if 'doubleValue' in v:
        try:
            return int(v['doubleValue'])
        except Exception:
            return default
    return default


def _f_bool(fields: dict, key: str, default: bool = False) -> bool:
    v = fields.get(key, {})
    if 'booleanValue' in v:
        return bool(v['booleanValue'])
    return default


def _unwrap_map(fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if 'stringValue' in v:
            out[k] = v['stringValue']
        elif 'integerValue' in v:
            try:
                out[k] = int(v['integerValue'])
            except Exception:
                out[k] = v['integerValue']
        elif 'doubleValue' in v:
            out[k] = float(v['doubleValue'])
        elif 'booleanValue' in v:
            out[k] = bool(v['booleanValue'])
        elif 'timestampValue' in v:
            out[k] = v['timestampValue']
        elif 'mapValue' in v:
            out[k] = _unwrap_map(v['mapValue'].get('fields') or {})
    return out


def _f_map(fields: dict, key: str) -> dict:
    v = fields.get(key, {})
    if 'mapValue' not in v:
        return {}
    return _unwrap_map(v['mapValue'].get('fields') or {})


def get_access_token() -> str:
    token = os.getenv('FIREBASE_TOKEN') or os.getenv('GCLOUD_ACCESS_TOKEN')
    if token:
        return token
    try:
        out = subprocess.run(
            ['gcloud', 'auth', 'application-default', 'print-access-token'],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ''


def _first_name(display: str, email: str) -> str:
    if display and display.strip() and display.strip().lower() not in {'you', 'guest'}:
        return display.strip().split()[0]
    if email and '@' in email:
        local = email.split('@', 1)[0]
        if local:
            return local.split('.')[0].capitalize()
    return 'there'


def load_all_users(token: str, page_size: int = 300) -> Iterable[dict]:
    page_token = None
    base_url = (
        f'{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)/documents/users'
    )
    while True:
        params = {'pageSize': page_size}
        if page_token:
            params['pageToken'] = page_token
        try:
            resp = requests.get(
                base_url,
                headers={'Authorization': f'Bearer {token}'},
                params=params,
                timeout=30,
            )
            if resp.status_code != 200:
                return
            data = resp.json()
        except Exception:
            return

        for doc in data.get('documents', []):
            fields = doc.get('fields', {})
            email = (_f(fields, 'email', default='') or '').lower().strip()
            username = (_f(fields, 'username', default='') or '').strip().lower()
            if not email:
                continue
            if username.startswith('guest'):
                continue
            uid = doc.get('name', '').split('/')[-1]
            display = _f(fields, 'displayName', default='') or ''
            usage = _f_map(fields, 'usage') or {}
            subscription = _f_map(fields, 'subscription') or {}
            streak = int(usage.get('streak') or _f_int(fields, 'streak') or 0)
            language = (_f(fields, 'language', default='') or 'en').split('-')[0].lower()
            if language not in {'en'}:
                language = 'en'
            yield {
                'uid': uid,
                'email': email,
                'first_name': _first_name(display, email),
                'display_name': display,
                'username': username,
                'language': language,
                'usage': usage,
                'subscription': subscription,
                'streak': streak,
                'karma': _f_int(fields, 'karma'),
                'notify_invites': _f_bool(fields, 'notifyInvites', True),
                'notify_reveals': _f_bool(fields, 'notifyReveals', True),
                'notify_streaks': _f_bool(fields, 'notifyStreaks', True),
                'created_at': _parse_ts(_f(fields, 'createdAt', kind='timestampValue')),
            }

        page_token = data.get('nextPageToken')
        if not page_token:
            break


def is_paid(user: dict) -> bool:
    sub = user.get('subscription') or {}
    if sub.get('isPro') is True:
        return True
    return (sub.get('status') or '').lower() == 'active'


def last_open_ms(user: dict):
    usage = user.get('usage') or {}
    raw = usage.get('lastOpenMs') or usage.get('last_open_ms')
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def days_since_open(user: dict) -> int:
    raw = last_open_ms(user)
    if raw is None:
        return -1
    last = datetime.fromtimestamp(raw / 1000.0, tz=timezone.utc)
    return (datetime.now(timezone.utc) - last).days


def unanswered_invites(user: dict) -> int:
    usage = user.get('usage') or {}
    try:
        return int(usage.get('unansweredInviteCount') or 0)
    except Exception:
        return 0


def predictions_created(user: dict) -> int:
    usage = user.get('usage') or {}
    try:
        return int(usage.get('predictionsCreated') or 0)
    except Exception:
        return 0


def answers_count(user: dict) -> int:
    usage = user.get('usage') or {}
    try:
        return int(usage.get('answersCount') or usage.get('answers_count') or 0)
    except Exception:
        return 0


def unopened_reveals(user: dict) -> int:
    usage = user.get('usage') or {}
    for key in ('unopenedRevealCount', 'unopened_reveal_count', 'revealsWaiting'):
        try:
            n = int(usage.get(key) or 0)
        except Exception:
            n = 0
        if n:
            return n
    return 0


def names_gate_hit(user: dict) -> bool:
    usage = user.get('usage') or {}
    for key in ('namesGateHit', 'hitSeeWhoGate', 'hitNamesGate', 'seeWhoGateHit'):
        val = usage.get(key)
        if val is True or str(val).lower() in {'1', 'true'}:
            return True
        try:
            if int(val or 0) > 0:
                return True
        except Exception:
            pass
    return False
