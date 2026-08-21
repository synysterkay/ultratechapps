#!/usr/bin/env python3
"""Firestore loader for Onbrief (onbrief-185c5). Guests without email are skipped."""
from __future__ import annotations

import os
import requests
import subprocess
from datetime import datetime, timezone
from typing import Iterable

PROJECT_ID = os.getenv('ONBRIEF_FIREBASE_PROJECT_ID', 'onbrief-185c5')
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


def _any_value(field):
    if not field:
        return None
    for k in ('integerValue', 'doubleValue', 'stringValue', 'booleanValue', 'timestampValue'):
        if k in field:
            return field[k]
    return None


def _coerce_int(v, default=0):
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        try:
            return int(float(v))
        except (ValueError, TypeError):
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
            out[k] = _parse_ts(v['timestampValue'])
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
        refresh = token
        try:
            resp = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh,
                    'client_id': '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com',
                    'client_secret': 'j9iVZfS8kkCEFUPaAeJV0sAi',
                },
                timeout=15,
            )
            if resp.status_code == 200:
                access = resp.json().get('access_token')
                if access:
                    return access
        except Exception:
            pass
        if not token.startswith('1//') and len(token) > 80:
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
                print(f'   ❌ Firestore users {resp.status_code}: {resp.text[:200]}')
                return
            data = resp.json()
        except Exception as exc:
            print(f'   ❌ Firestore users exception: {exc}')
            return

        for doc in data.get('documents', []):
            fields = doc.get('fields', {})
            email = (_f(fields, 'email', default='') or '').lower().strip()
            if not email:
                continue
            display = _f(fields, 'displayName', default='') or ''
            usage = _f_map(fields, 'usage') or {}
            if usage.get('isGuest') is True:
                continue
            uid = doc.get('name', '').split('/')[-1]
            plan = _f_map(fields, 'plan') or {}
            subscription = _f_map(fields, 'subscription') or {}
            streak = _f_map(fields, 'streak') or {}
            language = (_f(fields, 'language', default='') or 'en').split('-')[0].lower()
            if not language:
                language = 'en'
            yield {
                'uid': uid,
                'email': email,
                'first_name': _first_name(display, email),
                'display_name': display,
                'language': language,
                'usage': usage,
                'plan': plan,
                'subscription': subscription,
                'streak': streak,
                'created_at': _parse_ts(_f(fields, 'createdAt', kind='timestampValue')),
                'last_sign_in': _parse_ts(_f(fields, 'lastSignInAt', kind='timestampValue')),
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


def load_briefs_by_status(token: str, statuses: Iterable[str]):
    statuses = list(statuses)
    url = f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)/documents:runQuery"
    where = {
        'fieldFilter': {
            'field': {'fieldPath': 'status'},
            'op': 'IN' if len(statuses) > 1 else 'EQUAL',
            'value': ({'arrayValue': {'values': [{'stringValue': s} for s in statuses]}}
                      if len(statuses) > 1
                      else {'stringValue': statuses[0]}),
        }
    }
    body = {'structuredQuery': {'from': [{'collectionId': 'theses'}], 'where': where}}
    try:
        resp = requests.post(
            url,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=body,
            timeout=60,
        )
        if resp.status_code != 200:
            print(f'   ❌ briefs runQuery {resp.status_code}: {resp.text[:200]}')
            return
        results = resp.json() if isinstance(resp.json(), list) else [resp.json()]
    except Exception as e:
        print(f'   ❌ briefs runQuery exception: {e}')
        return
    for r in results:
        doc = r.get('document')
        if not doc:
            continue
        fields = doc.get('fields', {})
        yield {
            'brief_id': doc.get('name', '').split('/')[-1],
            'user_id': _f(fields, 'userId', default=''),
            'status': _f(fields, 'status', default=''),
            'topic': _f(fields, 'topic', default='') or _f(fields, 'title', default=''),
            'title': _f(fields, 'title', default=''),
            'progress': _coerce_int(_any_value(fields.get('progressPercentage'))),
            'created_at': _parse_ts(_f(fields, 'createdAt', kind='timestampValue')),
            'last_modified': _parse_ts(_f(fields, 'lastModified', kind='timestampValue')),
            'completed_at': _parse_ts(_f(fields, 'completedAt', kind='timestampValue')),
        }


def is_paid(user: dict) -> bool:
    sub = user.get('subscription') or {}
    if sub.get('isPro') is True:
        return True
    return (sub.get('status') or '').lower() in {'active', 'trial'}


def last_open_ms(user: dict):
    usage = user.get('usage') or {}
    raw = usage.get('lastOpenMs') or usage.get('last_open_ms')
    if raw is None:
        streak = user.get('streak') or {}
        last = streak.get('last_active_at')
        if isinstance(last, datetime):
            return int(last.timestamp() * 1000)
        return None
    try:
        return int(raw)
    except Exception:
        return None


def days_since_open(user: dict) -> int:
    raw = last_open_ms(user)
    if raw is None:
        sign_in = user.get('last_sign_in')
        if isinstance(sign_in, datetime):
            return (datetime.now(timezone.utc) - sign_in).days
        return -1
    last = datetime.fromtimestamp(raw / 1000.0, tz=timezone.utc)
    return (datetime.now(timezone.utc) - last).days


def work_label(user: dict, brief: dict | None = None) -> str:
    plan = user.get('plan') or {}
    raw = (plan.get('workType') or plan.get('work_type') or '').strip().lower()
    mapping = {
        'brief': 'brief',
        'memo': 'memo',
        'report': 'report',
        'research': 'research brief',
        'fullthesis': 'brief',
        'thesis': 'brief',
        'essay': 'brief',
    }
    if raw in mapping:
        return mapping[raw]
    topic = ''
    if brief:
        topic = (brief.get('title') or brief.get('topic') or '').lower()
    if 'memo' in topic:
        return 'memo'
    if 'report' in topic:
        return 'report'
    return 'brief'


def topic_label(user: dict, brief: dict | None = None) -> str:
    if brief:
        t = (brief.get('title') or brief.get('topic') or '').strip()
        if t:
            return t
    plan = user.get('plan') or {}
    t = (plan.get('topic') or '').strip()
    return t or 'your brief'
