#!/usr/bin/env python3
"""
Shared Firestore loader for PupShape users + dogs.

Every PupShape email sender used to need the same OAuth exchange +
nested document walks. This centralizes it and exposes a single typed
view of each user (with their dogs already joined) so new senders can
be ~80 lines instead of ~250.

Returned shape per user (one entry yielded per Firestore user doc):

    {
        'uid':           '<firebase uid>',
        'email':         'sirs.human@example.com',
        'first_name':    'Anaïs',
        'language':      'es',                  # 2-letter or zh-Hans, falls back to 'en'
        'photo_url':     'https://…'|None,
        'subscription':  {...}|None,             # users.subscription map
        'usage':         {...}|None,             # users.usage map (streak/sessions/lastOpenMs)
        'streak':        {'current': 7, ...},    # alias of usage.streak for convenience
        'referrals':     {'invitedCount': 0, ...}|None,
        'dogs':          [<dog_dict>, ...],      # joined from users/{uid}/dogs subcoll
        'created_at':    datetime|None,
        'last_sign_in':  datetime|None,
    }

Each dog dict:

    {
        'dog_id':         '<doc id>',
        'name':           'Sir',
        'breed':          'Labrador Retriever',
        'weight':         15.0,
        'target_weight':  13.0,
        'age_months':     36,
        'gender':         'male',
        'image_url':      '...',
        'created_at':     datetime|None,
        'updated_at':     datetime|None,
    }

Plus a separate helper to walk a dog's milestones / weight_logs /
task_completions when a sender needs that history.
"""
from __future__ import annotations

import os
import requests
import subprocess
from datetime import datetime
from typing import Iterable


PROJECT_ID = 'petmealai'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'


_LEGACY_NAME_TO_CODE = {
    'English': 'en',     'Spanish': 'es',     'French': 'fr',
    'Portuguese': 'pt',  'German': 'de',      'Italian': 'it',
    'Dutch': 'nl',       'Japanese': 'ja',    'Korean': 'ko',
    'Chinese': 'zh-Hans',
    # Locale-tag variants that the app or older builds may have written.
    'en_US': 'en',  'en_GB': 'en',
    'es_ES': 'es',  'es_MX': 'es',
    'pt_BR': 'pt',  'pt_PT': 'pt',
    'fr_FR': 'fr',  'fr_CA': 'fr',
    'de_DE': 'de',
    'it_IT': 'it',
    'nl_NL': 'nl',
    'ja_JP': 'ja',
    'ko_KR': 'ko',
    'zh-CN': 'zh-Hans', 'zh_CN': 'zh-Hans', 'zh': 'zh-Hans',
}


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


def _f_double(fields: dict, key: str, default: float = 0.0) -> float:
    v = fields.get(key, {})
    if 'doubleValue' in v:
        try:
            return float(v['doubleValue'])
        except Exception:
            return default
    if 'integerValue' in v:
        try:
            return float(v['integerValue'])
        except Exception:
            return default
    return default


def _f_map(fields: dict, key: str):
    """Unwrap a Firestore mapValue into a plain dict (recursive)."""
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
    """Pull a Google OAuth bearer token suitable for Firestore REST.

    Prefers FIREBASE_TOKEN env var (GitHub Actions sets this).
    Falls back to `gcloud auth application-default print-access-token`
    for local dev.
    """
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
    for candidate in (display,):
        if candidate and candidate.strip():
            return candidate.strip().split()[0]
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
    # Already canonical?
    if raw in {'en', 'es', 'pt', 'fr', 'de', 'it', 'nl', 'ja', 'ko', 'zh-Hans'}:
        return raw
    # Strip region: 'fr-CA' -> 'fr', 'pt-BR' -> 'pt'.
    base = raw.split('-')[0].split('_')[0].lower()
    if base in {'en', 'es', 'pt', 'fr', 'de', 'it', 'nl', 'ja', 'ko'}:
        return base
    if base == 'zh':
        return 'zh-Hans'
    return 'en'


def load_dogs_for_user(token: str, uid: str) -> list:
    url = (
        f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)"
        f"/documents/users/{uid}/dogs"
    )
    try:
        resp = requests.get(url, headers={'Authorization': f'Bearer {token}'},
                            timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []
    dogs = []
    for doc in data.get('documents', []):
        fields = doc.get('fields', {})
        dogs.append({
            'dog_id':        doc.get('name', '').split('/')[-1],
            'name':          _f(fields, 'name', default='') or '',
            'breed':         _f(fields, 'breed', default='') or '',
            'weight':        _f_double(fields, 'weight'),
            'target_weight': _f_double(fields, 'targetWeight'),
            'age_months':    _f_int(fields, 'age'),
            'gender':        _f(fields, 'gender', default='') or '',
            'image_url':     _f(fields, 'imageUrl', default='') or '',
            'created_at':    _parse_ts(
                _f(fields, 'createdAt', kind='timestampValue')),
            'updated_at':    _parse_ts(
                _f(fields, 'updatedAt', kind='timestampValue')),
        })
    return dogs


def load_all_users(token: str, page_size: int = 300):
    """Yield one normalized user dict (with dogs joined) per Firestore
    user doc. Skips docs missing an email — those can't receive mail."""
    page_token = None
    base_url = (
        f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)/documents/users"
    )
    while True:
        params = {'pageSize': page_size}
        if page_token:
            params['pageToken'] = page_token
        try:
            resp = requests.get(base_url,
                                headers={'Authorization': f'Bearer {token}'},
                                params=params, timeout=30)
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
            raw_lang = (_f(fields, 'language', default='') or '').strip()
            lang = _normalize_language(raw_lang)
            subscription = _f_map(fields, 'subscription') or None
            usage = _f_map(fields, 'usage') or None
            streak = (usage or {}).get('streak') or {}
            referrals = _f_map(fields, 'referrals') or None

            dogs = load_dogs_for_user(token, uid)
            yield {
                'uid':           uid,
                'email':         email,
                'first_name':    _first_name(display, email),
                'display_name':  display,
                'language':      lang,
                'photo_url':     _f(fields, 'photoURL', default='') or None,
                'subscription':  subscription,
                'usage':         usage,
                'streak':        streak,
                'referrals':     referrals,
                'dogs':          dogs,
                'created_at':    _parse_ts(
                    _f(fields, 'createdAt', kind='timestampValue')),
                'last_sign_in':  _parse_ts(
                    _f(fields, 'lastSignInAt', kind='timestampValue')),
            }
        page_token = data.get('nextPageToken')
        if not page_token:
            break


def load_users_dict(token: str):
    by_email, by_uid = {}, {}
    for u in load_all_users(token):
        by_email[u['email']] = u
        by_uid[u['uid']] = u
    return by_email, by_uid


def load_dog_weight_logs(token: str, uid: str, dog_id: str) -> list:
    """Newest-first list of weight_log dicts for a specific dog."""
    url = (
        f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)"
        f"/documents/users/{uid}/dogs/{dog_id}/weight_logs"
    )
    try:
        resp = requests.get(
            url,
            headers={'Authorization': f'Bearer {token}'},
            params={'orderBy': 'date desc'},
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []
    logs = []
    for doc in data.get('documents', []):
        fields = doc.get('fields', {})
        logs.append({
            'weight': _f_double(fields, 'weight'),
            'bcs':    _f_int(fields, 'bodyConditionScore'),
            'date':   _parse_ts(_f(fields, 'date', kind='timestampValue')),
        })
    return logs


def load_dog_milestones(token: str, uid: str, dog_id: str) -> list:
    """Milestone events the Flutter app wrote when a weigh-in crossed
    25/50/75/100% toward goal."""
    url = (
        f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)"
        f"/documents/users/{uid}/dogs/{dog_id}/milestones"
    )
    try:
        resp = requests.get(url, headers={'Authorization': f'Bearer {token}'},
                            timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []
    out = []
    for doc in data.get('documents', []):
        fields = doc.get('fields', {})
        out.append({
            'key':        _f(fields, 'milestoneKey', default='') or '',
            'title':      _f(fields, 'milestoneTitle', default='') or '',
            'crossed_at': _parse_ts(
                _f(fields, 'crossedAt', kind='timestampValue')),
        })
    return out


def is_paid(user: dict) -> bool:
    sub = user.get('subscription') or {}
    return (sub.get('status') or '').lower() == 'active'
