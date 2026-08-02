#!/usr/bin/env python3
"""
Shared Firestore loader for Thesis Generator users and theses.

Every Thesis Generator email sender used to re-implement the same OAuth
exchange + pagination loop. This module centralizes it and exposes a single
typed view of each user so new senders can be ~80 lines instead of ~250.

Returned shape per email (lowercased):

    {
        'uid':           '<firebase uid>',
        'email':         'kayla@example.com',
        'first_name':    'Kayla',           # parsed from displayName / nickname
        'language':      'es',              # 2-letter code, falls back to 'en'
        'plan':          {...},             # users.plan map (pain, deadline, ...)
        'subscription':  {...},             # users.subscription map (or None)
        'usage':         {...},             # users.usage map (or None)
        'streak':        {'current': 7, 'last_active_at': datetime|None, ...},
        'created_at':    datetime|None,
        'last_sign_in':  datetime|None,
    }

For theses:

    {
        'thesis_id':    '<doc id>',
        'user_id':      '<firebase uid>',
        'status':       'completed'|'in_progress'|'draft'|'generating'|'failed',
        'topic':        '...',
        'title':        '...',
        'language':     '...',                  # thesis output language
        'progress':     0..100,
        'word_count':   int,
        'created_at':   datetime|None,
        'last_modified':datetime|None,
        'completed_at': datetime|None,          # only for status=='completed'
    }
"""
from __future__ import annotations

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable

USERS_SNAPSHOT_CACHE = Path(__file__).resolve().parents[1] / 'cache' / 'thesis_users_snapshot.json'


PROJECT_ID = 'thesis-generator-web'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'


# Maps the human-readable language names a legacy Flutter build wrote into
# `users.{uid}.language` to the canonical 2-letter codes the email senders
# use. Without this every email goes out in English for these users.
_LEGACY_NAME_TO_CODE = {
    'English': 'en',   'Spanish': 'es',     'French': 'fr',
    'Arabic': 'ar',    'Chinese': 'zh',     'Hindi': 'hi',
    'German': 'de',    'Portuguese': 'pt',  'Italian': 'it',
    'Russian': 'ru',   'Japanese': 'ja',    'Korean': 'ko',
    'Turkish': 'tr',   'Dutch': 'nl',       'Polish': 'pl',
    'Swedish': 'sv',   'Romanian': 'ro',    'Indonesian': 'id',
    'Thai': 'th',      'Vietnamese': 'vi',
    # 14 added 2026-05 alongside the picker expansion — future-proof if a
    # legacy write path ever stores these display names.
    'Bengali': 'bn',   'Urdu': 'ur',        'Persian': 'fa',
    'Farsi': 'fa',     'Hebrew': 'he',      'Greek': 'el',
    'Czech': 'cs',     'Danish': 'da',      'Finnish': 'fi',
    'Norwegian': 'no', 'Hungarian': 'hu',   'Ukrainian': 'uk',
    'Filipino': 'tl',  'Tagalog': 'tl',     'Malay': 'ms',
    'Swahili': 'sw',
}


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def _f(fields, name, kind='stringValue', default=None):
    """Read a typed value from a Firestore REST `fields` dict."""
    v = fields.get(name, {})
    if not v:
        return default
    if kind in v:
        return v[kind]
    return default


def _f_map(fields, name):
    """Read a nested map from a Firestore `fields` dict, returning a flat
    Python dict (with the same typed coercion as `_f`)."""
    raw = fields.get(name, {}).get('mapValue', {}).get('fields', {})
    return _flatten_fields(raw)


def _flatten_fields(fields):
    """Convert a Firestore `fields` dict into a plain Python dict, handling
    all common scalar types. Nested maps are recursed; arrays become lists."""
    out = {}
    for k, v in (fields or {}).items():
        if 'stringValue' in v:
            out[k] = v['stringValue']
        elif 'integerValue' in v:
            try: out[k] = int(v['integerValue'])
            except: out[k] = v['integerValue']
        elif 'doubleValue' in v:
            try: out[k] = float(v['doubleValue'])
            except: out[k] = v['doubleValue']
        elif 'booleanValue' in v:
            out[k] = bool(v['booleanValue'])
        elif 'timestampValue' in v:
            out[k] = _parse_ts(v['timestampValue'])
        elif 'mapValue' in v:
            out[k] = _flatten_fields(v['mapValue'].get('fields', {}))
        elif 'arrayValue' in v:
            arr = v['arrayValue'].get('values', [])
            out[k] = [_flatten_fields({'_': i}).get('_') if 'mapValue' not in i else _flatten_fields(i['mapValue'].get('fields', {})) for i in arr]
        elif 'nullValue' in v:
            out[k] = None
        else:
            out[k] = None
    return out


def get_access_token():
    """Refresh-token → access-token exchange (Firebase CLI flow). Identical
    to the one used by every existing sender, centralized here."""
    refresh = os.environ.get('FIREBASE_TOKEN', '')
    if not refresh:
        return None
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
            return resp.json().get('access_token')
    except Exception:
        pass
    return None


def normalize_user_language(raw: str) -> str:
    """Map Firestore `users.language` (BCP-47, legacy display names, etc.)
    to the canonical 2-letter code used by thesis email templates."""
    if not raw:
        return 'en'
    s = str(raw).strip()
    if s in _LEGACY_NAME_TO_CODE:
        return _LEGACY_NAME_TO_CODE[s]
    from localize_phrase import normalize_language
    return normalize_language(s)


def _first_name(display_name, nickname, email):
    """Best-effort first name. The Flutter app writes `displayName` from
    Apple sign-in / Google profiles, and onboarding stores `nickname`. Fall
    back to the email local part so the {{first_name}} placeholder never
    renders empty."""
    for candidate in (display_name, nickname):
        if candidate and candidate.strip():
            return candidate.strip().split()[0]
    if email and '@' in email:
        local = email.split('@', 1)[0]
        if local:
            return local.split('.')[0].capitalize()
    return ''


def load_all_users(token: str, page_size: int = 300):
    """Yields one normalized user dict per Firestore user doc. Skips any
    doc that has no email (those can't receive emails anyway)."""
    page_token = None
    base_url = f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)/documents/users"
    while True:
        params = {'pageSize': page_size}
        if page_token:
            params['pageToken'] = page_token
        data = None
        for attempt in range(6):
            try:
                resp = requests.get(
                    base_url,
                    headers={'Authorization': f'Bearer {token}'},
                    params=params,
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    break
                if resp.status_code == 429 and attempt < 5:
                    time.sleep(min(30, 2 ** attempt * 2))
                    continue
                print(f'   ❌ Firestore users page error: {resp.status_code} {resp.text[:200]}')
                return
            except Exception as exc:
                if attempt < 5:
                    time.sleep(min(30, 2 ** attempt * 2))
                    continue
                print(f'   ❌ Firestore users page failed: {exc}')
                return
        if data is None:
            return
        for doc in data.get('documents', []):
            fields = doc.get('fields', {})
            email = _f(fields, 'email', default='') or ''
            email = email.lower().strip()
            if not email:
                continue
            uid = doc.get('name', '').split('/')[-1]
            display = _f(fields, 'displayName', default='') or ''
            nickname = _f(fields, 'nickname', default='') or ''
            # Some legacy docs store `language` as the human-readable name
            # ('English', 'Swedish'). Map those down to the canonical 2-letter
            # code via `localize_phrase.normalize_language`, which also
            # canonicalizes locale strings like 'en_US' / 'pt-BR'.
            raw_lang = (_f(fields, 'language', default='') or '').strip()
            lang = normalize_user_language(raw_lang or 'en')
            plan = _f_map(fields, 'plan')
            subscription = _f_map(fields, 'subscription') or None
            usage = _f_map(fields, 'usage') or None
            streak = _f_map(fields, 'streak') or {}
            yield {
                'uid':           uid,
                'email':         email,
                'first_name':    _first_name(display, nickname, email),
                'display_name':  display or nickname,
                'language':      lang,
                'plan':          plan or {},
                'subscription':  subscription,
                'usage':         usage,
                'streak':        streak,
                'created_at':    _parse_ts(_f(fields, 'createdAt', kind='timestampValue')),
                'last_sign_in':  _parse_ts(_f(fields, 'lastSignInAt', kind='timestampValue')),
                'last_updated':  _parse_ts(_f(fields, 'lastUpdated', kind='timestampValue')),
            }
        page_token = data.get('nextPageToken')
        if not page_token:
            break


def _save_users_snapshot(users: list[dict]) -> None:
    USERS_SNAPSHOT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'saved_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': len(users),
        'users': users,
    }
    tmp = USERS_SNAPSHOT_CACHE.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload), encoding='utf-8')
    tmp.replace(USERS_SNAPSHOT_CACHE)


def _load_users_snapshot(*, max_age_hours: int = 48) -> list[dict]:
    if not USERS_SNAPSHOT_CACHE.exists():
        return []
    try:
        payload = json.loads(USERS_SNAPSHOT_CACHE.read_text(encoding='utf-8'))
        saved_at = payload.get('saved_at') or ''
        if saved_at:
            dt = datetime.fromisoformat(saved_at.replace('Z', '+00:00'))
            age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if age_h > max_age_hours:
                return []
        users = payload.get('users') or []
        if users:
            print(f'   📦 Using cached Firestore snapshot ({len(users):,} users, saved {saved_at})')
        return users
    except Exception:
        return []


def load_all_users_list(token: str, *, use_cache_on_failure: bool = True) -> list[dict]:
    """Load all Firestore users with retry + optional snapshot fallback."""
    users = list(load_all_users(token))
    if users:
        _save_users_snapshot(users)
        return users
    if use_cache_on_failure:
        cached = _load_users_snapshot()
        if cached:
            return cached
    return []


def load_users_dict(token: str):
    """Build {email: user} and {uid: user} indexes for quick joins."""
    by_email, by_uid = {}, {}
    for u in load_all_users_list(token):
        by_email[u['email']] = u
        by_uid[u['uid']] = u
    return by_email, by_uid


def load_theses_by_status(token: str, statuses: Iterable[str], page_size: int = 300):
    """Iterate over theses with `status` in the given set.

    Uses :runQuery rather than collection scan + filter so we don't pull
    every draft when we only care about completed ones.
    """
    statuses = list(statuses)
    url = f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)/documents:runQuery"
    # Firestore REST `IN` filter requires explicit array of typed values.
    where = {
        'fieldFilter': {
            'field': {'fieldPath': 'status'},
            'op': 'IN' if len(statuses) > 1 else 'EQUAL',
            'value': ({'arrayValue': {'values': [{'stringValue': s} for s in statuses]}}
                      if len(statuses) > 1
                      else {'stringValue': statuses[0]}),
        }
    }
    body = {
        'structuredQuery': {
            'from': [{'collectionId': 'theses'}],
            'where': where,
        }
    }
    try:
        resp = requests.post(
            url, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=body, timeout=60,
        )
        if resp.status_code != 200:
            print(f'   ❌ theses runQuery {resp.status_code}: {resp.text[:200]}')
            return
        results = resp.json() if isinstance(resp.json(), list) else [resp.json()]
    except Exception as e:
        print(f'   ❌ theses runQuery exception: {e}')
        return
    for r in results:
        doc = r.get('document')
        if not doc:
            continue
        fields = doc.get('fields', {})
        yield {
            'thesis_id':     doc.get('name', '').split('/')[-1],
            'user_id':       _f(fields, 'userId', default=''),
            'status':        _f(fields, 'status', default=''),
            'topic':         _f(fields, 'topic', default=''),
            'title':         _f(fields, 'title', default=''),
            'language':      _f(fields, 'language', default=''),
            'study_level':   _f(fields, 'studyLevel', default=''),
            'progress':      _coerce_int(_any_value(fields.get('progressPercentage'))),
            'word_count':    _coerce_int(_any_value(fields.get('wordCount'))),
            'pages':         _coerce_int(_any_value(fields.get('pages'))),
            'created_at':    _parse_ts(_f(fields, 'createdAt', kind='timestampValue')),
            'last_modified': _parse_ts(_f(fields, 'lastModified', kind='timestampValue')),
            'completed_at':  _parse_ts(_f(fields, 'completedAt', kind='timestampValue')),
        }


def _any_value(field):
    """Return the value of a Firestore field regardless of which typed
    union member ('integerValue' / 'doubleValue' / 'stringValue') it
    uses. The Flutter app has at times written `progressPercentage` as
    both an int and a string, so we can't depend on one kind."""
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


def is_paid(user_record) -> bool:
    """Single source of truth for 'is this user a current paid subscriber'.

    Reads `users.subscription.status` (written by the Flutter app's Superwall
    delegate + payment-success handler). A status of 'active' or 'trial'
    counts as paid; anything else (or missing entirely) is treated as free.
    """
    sub = (user_record or {}).get('subscription') or {}
    status = (sub.get('status') or '').lower()
    return status in {'active', 'trial', 'past_due'}  # past_due still has access


def founder_story_audience_eligible(user_record) -> bool:
    """Founder story goes to free + churned users only — not active subs.

    Skips users whose Firestore doc was never loaded (no `subscription`
    key) so we don't email someone who might be paid but missing from cache.
    """
    if not user_record:
        return False
    if is_paid(user_record):
        return False
    if 'subscription' not in user_record:
        return False
    return True


def hit_free_quota(user_record) -> bool:
    """Did this free user burn their lifetime free chapter?"""
    usage = (user_record or {}).get('usage') or {}
    return bool(usage.get('freeChapterUsed'))
