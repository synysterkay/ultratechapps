"""
user_context.py — Build per-user context for trigger evaluation + email
personalization. One UserContext object is built per user per send pass.

Pulls from:
  • Firestore: user doc (language, streak, favoriteLeague, isPremium,
    lastPredictionAt), communities (joined + owned)
  • Supabase: user_picks (recent), user_leagues (followed), predictions
    (today's matches in user's leagues)
"""
from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from pathlib import Path

import requests


# Predictify-app Supabase (predictions, user_leagues, user_picks) is a
# SEPARATE project from the marketing-tool's Supabase. Prefer the dedicated
# env vars; fall back to generic ones for local-dev convenience.
SUPABASE_URL = (
    os.environ.get('PREDICTIFY_SUPABASE_URL')
    or os.environ.get('SUPABASE_URL', '')
).rstrip('/')
SUPABASE_KEY = (
    os.environ.get('PREDICTIFY_SUPABASE_SERVICE_ROLE_KEY')
    or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
)
FIREBASE_PROJECT_ID = 'predictify-3f30d'
FIRESTORE_BASE = (
    f'https://firestore.googleapis.com/v1/projects/'
    f'{FIREBASE_PROJECT_ID}/databases/(default)/documents'
)


def _supa_headers() -> dict:
    if not SUPABASE_KEY:
        # Try config fallback for local runs.
        cfg = Path(__file__).resolve().parents[2] / 'config' / 'supabase_config.json'
        if cfg.exists():
            with open(cfg) as f:
                data = json.load(f)
            url = data['project']['url']
            key = data['project']['service_role_key']
            return {
                'apikey': key,
                'Authorization': f'Bearer {key}',
                '_url': url,
            }
        return {}
    return {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        '_url': SUPABASE_URL,
    }


@dataclass
class UpcomingMatch:
    fixture_id: int
    league_name: str
    home_team: str
    away_team: str
    kickoff_utc: str
    headline_pick_label: str | None  # e.g. "Home or Draw (1X)"
    confidence_pct: int               # 0-100
    tier: str | None                  # 'elite' | 'premium' | 'standard'

    @property
    def kickoff_dt(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.kickoff_utc.replace('Z', '+00:00'))
        except Exception:
            return None


@dataclass
class UserContext:
    uid: str
    email: str
    display_name: str
    language: str = 'en'

    # ── activity ──
    streak_days: int = 0
    last_pick_at: datetime | None = None
    is_premium: bool = False
    accuracy_30d: float | None = None  # 0..1
    total_picks_30d: int = 0
    correct_picks_30d: int = 0

    # ── preferences ──
    followed_league_ids: list[int] = field(default_factory=list)
    followed_league_names: list[str] = field(default_factory=list)

    # ── communities ──
    owned_community_id: str | None = None
    owned_community_name: str | None = None
    owned_community_member_count: int = 0
    joined_community_count: int = 0

    # ── upcoming ──
    next_match: UpcomingMatch | None = None  # next followed-league match
    todays_top_pick: UpcomingMatch | None = None  # any league, highest tier

    # ── derived helpers ──
    @property
    def has_followed_leagues(self) -> bool:
        return bool(self.followed_league_ids)

    @property
    def hours_since_last_pick(self) -> float | None:
        if not self.last_pick_at:
            return None
        delta = datetime.now(timezone.utc) - self.last_pick_at
        return delta.total_seconds() / 3600.0


def fetch_user_context(
    uid: str,
    email: str,
    display_name: str,
    language: str = 'en',
    activity: dict | None = None,
) -> UserContext:
    """Build a fresh UserContext for one user. ``activity`` is the dict
    already loaded by FirestoreActivityLoader if available — saves an
    extra round-trip."""

    ctx = UserContext(
        uid=uid,
        email=email,
        display_name=display_name or 'there',
        language=language or 'en',
    )

    # Activity (Firestore) — already provided by caller for batch efficiency.
    if activity:
        ctx.streak_days = int(activity.get('streak') or 0)
        ctx.is_premium = bool(activity.get('isPremium') or activity.get('isSubscribed'))
        last = activity.get('lastPredictionAt')
        if isinstance(last, str):
            try:
                ctx.last_pick_at = datetime.fromisoformat(last.replace('Z', '+00:00'))
            except Exception:
                pass
        elif isinstance(last, dict) and last.get('seconds'):
            ctx.last_pick_at = datetime.fromtimestamp(int(last['seconds']), tz=timezone.utc)
        if isinstance(activity.get('favoriteLeague'), int):
            ctx.followed_league_ids.append(activity['favoriteLeague'])

    # Followed leagues + recent picks + accuracy via Supabase.
    headers = _supa_headers()
    url = headers.pop('_url', SUPABASE_URL) if headers else SUPABASE_URL
    if headers and url:
        ctx.followed_league_ids = list(set(ctx.followed_league_ids) | _fetch_followed_leagues(uid, url, headers))
        ctx.followed_league_names = _fetch_league_names(ctx.followed_league_ids, url, headers)
        acc = _fetch_accuracy(uid, url, headers)
        if acc:
            ctx.accuracy_30d = acc['rate']
            ctx.total_picks_30d = acc['total']
            ctx.correct_picks_30d = acc['correct']
        ctx.next_match = _fetch_next_followed_match(ctx.followed_league_ids, url, headers)
        ctx.todays_top_pick = _fetch_top_pick_today(url, headers)

    # Community state — Firestore (best effort, do not block on errors).
    owned, joined = _fetch_community_state(uid)
    if owned:
        ctx.owned_community_id = owned['id']
        ctx.owned_community_name = owned.get('name')
        ctx.owned_community_member_count = int(owned.get('memberCount') or 0)
    ctx.joined_community_count = joined

    return ctx


# ─────────────────────────────────────────────────────────
#  Supabase queries
# ─────────────────────────────────────────────────────────

def _fetch_followed_leagues(uid: str, url: str, headers: dict) -> set[int]:
    try:
        r = requests.get(
            f'{url}/rest/v1/user_leagues',
            params={'select': 'league_id', 'firebase_uid': f'eq.{uid}', 'is_favorite': 'eq.true'},
            headers=headers, timeout=8,
        )
        if r.status_code == 200:
            return {row['league_id'] for row in r.json() if isinstance(row.get('league_id'), int)}
    except Exception:
        pass
    return set()


def _fetch_league_names(league_ids: list[int], url: str, headers: dict) -> list[str]:
    if not league_ids:
        return []
    try:
        ids = ','.join(str(i) for i in league_ids)
        r = requests.get(
            f'{url}/rest/v1/predictions',
            params={
                'select': 'league_id,league_name',
                'league_id': f'in.({ids})',
                'limit': 50,
            },
            headers=headers, timeout=8,
        )
        if r.status_code == 200:
            seen, out = set(), []
            for row in r.json():
                lid = row.get('league_id')
                name = row.get('league_name')
                if lid and name and lid not in seen:
                    seen.add(lid)
                    out.append(name)
            return out
    except Exception:
        pass
    return []


def _fetch_accuracy(uid: str, url: str, headers: dict) -> dict | None:
    """Last 30 days from user_picks (assumes table exists with uid + correct fields).
    Falls back silently if schema differs."""
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        r = requests.get(
            f'{url}/rest/v1/user_picks',
            params={
                'select': 'is_correct',
                'user_id': f'eq.{uid}',
                'created_at': f'gte.{since}',
                'is_correct': 'not.is.null',
                'limit': 200,
            },
            headers=headers, timeout=8,
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        total = len(rows)
        correct = sum(1 for r in rows if r.get('is_correct') is True)
        if total == 0:
            return None
        return {'rate': correct / total, 'total': total, 'correct': correct}
    except Exception:
        return None


def _fetch_next_followed_match(league_ids: list[int], url: str, headers: dict) -> UpcomingMatch | None:
    if not league_ids:
        return None
    try:
        ids = ','.join(str(i) for i in league_ids)
        now = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(hours=36)).isoformat()
        r = requests.get(
            f'{url}/rest/v1/predictions',
            params={
                'select': 'fixture_id,league_name,home_team_name,away_team_name,'
                          'match_date,confidence_score,prediction_data',
                'league_id': f'in.({ids})',
                'match_date': f'gte.{now}',
                'match_date': f'lte.{end}',
                'order': 'match_date.asc',
                'limit': 1,
            },
            headers=headers, timeout=8,
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        if not rows:
            return None
        return _row_to_upcoming(rows[0])
    except Exception:
        return None


def _fetch_top_pick_today(url: str, headers: dict) -> UpcomingMatch | None:
    """The single highest-confidence prediction kicking off today."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        r = requests.get(
            f'{url}/rest/v1/predictions',
            params={
                'select': 'fixture_id,league_name,home_team_name,away_team_name,'
                          'match_date,confidence_score,prediction_data',
                'match_date': f'gte.{now}',
                'match_date': f'lte.{end}',
                'order': 'confidence_score.desc',
                'limit': 1,
            },
            headers=headers, timeout=8,
        )
        if r.status_code != 200:
            return None
        rows = r.json()
        if not rows:
            return None
        return _row_to_upcoming(rows[0])
    except Exception:
        return None


def _row_to_upcoming(row: dict) -> UpcomingMatch:
    pdata = row.get('prediction_data') or {}
    hp = pdata.get('headlinePick') if isinstance(pdata, dict) else None
    label = None
    tier = None
    if isinstance(hp, dict):
        sel = hp.get('selection')
        home = row.get('home_team_name') or 'Home'
        away = row.get('away_team_name') or 'Away'
        if sel == '1X':
            label = f'{home} or Draw'
        elif sel == 'X2':
            label = f'Draw or {away}'
        elif sel == '12':
            label = f'{home} or {away}'
        tier = hp.get('tier')
    conf = row.get('confidence_score') or 0
    try:
        conf_pct = int(round(float(conf) * 100))
    except Exception:
        conf_pct = 0
    return UpcomingMatch(
        fixture_id=int(row.get('fixture_id') or 0),
        league_name=row.get('league_name') or '',
        home_team=row.get('home_team_name') or 'Home',
        away_team=row.get('away_team_name') or 'Away',
        kickoff_utc=row.get('match_date') or '',
        headline_pick_label=label,
        confidence_pct=conf_pct,
        tier=tier,
    )


# ─────────────────────────────────────────────────────────
#  Firestore queries — community state
# ─────────────────────────────────────────────────────────

_FB_TOKEN: str | None = None
_FB_TOKEN_AT: float = 0


def _fb_token() -> str | None:
    global _FB_TOKEN, _FB_TOKEN_AT
    if _FB_TOKEN and time.time() - _FB_TOKEN_AT < 3000:  # 50min cache
        return _FB_TOKEN
    rt = os.environ.get('FIREBASE_TOKEN', '')
    if not rt:
        return None
    try:
        r = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': rt,
                'client_id': '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com',
                'client_secret': 'j9iVZfS8kkCEFUPaAeJV0sAi',
            },
            timeout=15,
        )
        if r.status_code == 200:
            _FB_TOKEN = r.json()['access_token']
            _FB_TOKEN_AT = time.time()
            return _FB_TOKEN
    except Exception:
        pass
    return None


def _fetch_community_state(uid: str) -> tuple[dict | None, int]:
    """Return (owned_community_dict_or_None, joined_count). Best-effort."""
    tok = _fb_token()
    if not tok:
        return None, 0
    headers = {'Authorization': f'Bearer {tok}'}
    owned = None
    try:
        # Owned: communities where ownerId == uid
        body = {
            'structuredQuery': {
                'from': [{'collectionId': 'communities'}],
                'where': {
                    'fieldFilter': {
                        'field': {'fieldPath': 'ownerId'},
                        'op': 'EQUAL',
                        'value': {'stringValue': uid},
                    }
                },
                'limit': 1,
            }
        }
        r = requests.post(
            f'{FIRESTORE_BASE}:runQuery',
            headers=headers, json=body, timeout=10,
        )
        if r.ok:
            for entry in r.json():
                doc = entry.get('document')
                if not doc:
                    continue
                fields = doc.get('fields', {})
                owned = {
                    'id': doc['name'].rsplit('/', 1)[-1],
                    'name': fields.get('name', {}).get('stringValue'),
                    'memberCount': int(fields.get('memberCount', {}).get('integerValue') or 0),
                }
                break
    except Exception:
        pass

    # Joined count — via members collectionGroup is expensive; skip for now.
    # Falls back to 0 if unknown. Not critical for trigger logic.
    return owned, 0
