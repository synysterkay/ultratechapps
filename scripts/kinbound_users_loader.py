#!/usr/bin/env python3
"""
Firestore loader for Kinbound (parents-ai-e49a8).

Yields one normalized user dict per Firestore user doc with an email.
Child names and chat never appear here — only counts, struggle ids,
and streak/usage metadata synced by the Flutter app.
"""
from __future__ import annotations

import os
import requests
import subprocess
from datetime import datetime, timezone
from typing import Iterable

PROJECT_ID = 'parents-ai-e49a8'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'

_LEGACY_NAME_TO_CODE = {
    'English': 'en', 'Spanish': 'es', 'French': 'fr',
    'Portuguese': 'pt', 'German': 'de', 'Italian': 'it',
    'Dutch': 'nl', 'Japanese': 'ja', 'Korean': 'ko',
    'Chinese': 'zh-Hans',
    'en_US': 'en', 'en_GB': 'en',
    'es_ES': 'es', 'es_MX': 'es',
    'pt_BR': 'pt', 'pt_PT': 'pt',
    'fr_FR': 'fr', 'fr_CA': 'fr',
    'de_DE': 'de', 'it_IT': 'it',
    'nl_NL': 'nl', 'ja_JP': 'ja', 'ko_KR': 'ko',
    'zh-CN': 'zh-Hans', 'zh_CN': 'zh-Hans', 'zh': 'zh-Hans',
}

STRUGGLE_LABELS = {
    'tantrum': 'a meltdown',
    'bedtime': 'bedtime',
    'siblings': 'a sibling fight',
    'defiance': 'not listening',
    'anxious': 'anxiety',
    'screen': 'screen time',
    'mealtime': 'mealtime',
    'morning': 'morning chaos',
    'teen': 'a shut-down teen',
    'myself': 'feeling overwhelmed',
}


def struggle_label(situation_id: str) -> str:
    return STRUGGLE_LABELS.get(situation_id or '', 'a hard moment')


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


def _f_map(fields: dict, key: str):
    v = fields.get(key, {})
    if 'mapValue' not in v:
        return {}
    return _unwrap_map(v['mapValue'].get('fields') or {})


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
        elif 'arrayValue' in v:
            out[k] = [
                _unwrap_value(x) for x in (v['arrayValue'].get('values') or [])
            ]
    return out


def _unwrap_value(v: dict):
    for kind in (
        'stringValue', 'integerValue', 'doubleValue',
        'booleanValue', 'timestampValue',
    ):
        if kind in v:
            return v[kind]
    if 'mapValue' in v:
        return _unwrap_map(v['mapValue'].get('fields') or {})
    return None


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
    if display and display.strip():
        return display.strip().split()[0]
    if email and '@' in email:
        local = email.split('@', 1)[0]
        if local:
            return local.split('.')[0].capitalize()
    return ''


def _normalize_language(raw: str) -> str:
    if not raw:
        return 'en'
    if raw in _LEGACY_NAME_TO_CODE:
        return _LEGACY_NAME_TO_CODE[raw]
    if raw in {'en', 'es', 'pt', 'fr', 'de', 'it', 'nl', 'ja', 'ko', 'zh-Hans',
               'ar', 'hi', 'id', 'pl', 'ru', 'tr', 'ro', 'sv', 'vi', 'th'}:
        return raw
    base = raw.split('-')[0].split('_')[0].lower()
    if base in {'en', 'es', 'pt', 'fr', 'de', 'it', 'nl', 'ja', 'ko',
                'ar', 'hi', 'id', 'pl', 'ru', 'tr', 'ro', 'sv', 'vi', 'th'}:
        return base
    if base == 'zh':
        return 'zh-Hans'
    return 'en'


def _streak_current(user: dict) -> int:
    usage = user.get('usage') or {}
    streak = usage.get('streak')
    if isinstance(streak, dict):
        return int(streak.get('current') or 0)
    if isinstance(streak, (int, float)):
        return int(streak)
    return int(user.get('streak') or 0)


def _last_check_in_day(user: dict) -> str:
    usage = user.get('usage') or {}
    raw = usage.get('lastCheckInMs') or usage.get('last_check_in_ms')
    if raw is None:
        return ''
    try:
        ms = int(raw)
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        return f'{dt.year}-{dt.month:02d}-{dt.day:02d}'
    except Exception:
        return ''


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
            if not email:
                continue
            uid = doc.get('name', '').split('/')[-1]
            display = _f(fields, 'displayName', default='') or ''
            raw_lang = (
                _f(fields, 'language', default='')
                or _f(fields, 'locale', default='')
                or ''
            ).strip()
            lang = _normalize_language(raw_lang)
            subscription = _f_map(fields, 'subscription') or None
            usage = _f_map(fields, 'usage') or None
            onboarding = _f_map(fields, 'onboarding') or None

            user = {
                'uid': uid,
                'email': email,
                'first_name': _first_name(display, email),
                'display_name': display,
                'language': lang,
                'subscription': subscription,
                'usage': usage,
                'onboarding': onboarding,
                'streak': _streak_current({'usage': usage, 'streak': _f_int(fields, 'streak')}),
                'created_at': _parse_ts(
                    _f(fields, 'createdAt', kind='timestampValue')),
                'last_sign_in': _parse_ts(
                    _f(fields, 'lastSignInAt', kind='timestampValue')),
            }
            user['last_check_in_day'] = _last_check_in_day(user)
            yield user

        page_token = data.get('nextPageToken')
        if not page_token:
            break


def is_paid(user: dict) -> bool:
    sub = user.get('subscription') or {}
    if sub.get('isPremium') is True:
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
