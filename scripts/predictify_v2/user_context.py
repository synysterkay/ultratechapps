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
# Soccer is the default; the NBA profile sets PREDICTIFY_FIREBASE_PROJECT_ID=
# nba-predictify so the language/Firestore lookups hit NBA's project.
FIREBASE_PROJECT_ID = os.environ.get(
    'PREDICTIFY_FIREBASE_PROJECT_ID', 'predictify-3f30d')
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

    # ── community recommendation (populated by orchestrator when the
    #    CommunityRecommender pool is available; community_invite trigger
    #    + template both read these via _recommended_* attr names). ──
    _recommended_community_id: str | None = None
    _recommended_community_name: str | None = None
    _recommended_community_owner: str | None = None
    _recommended_community_member_count: int = 0
    _recommended_community_league: str | None = None

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


# ─────────────────────────────────────────────────────────
#  Bulk prefetch — the whole behavioral dataset in ~4 queries
# ─────────────────────────────────────────────────────────
# The per-user path below makes ~5 Supabase + 1 Firestore reads PER USER.
# Across ~17k users that was ~90k round-trips / ~2h45m, almost all of it
# wasted (only ~600 users have any behavioral row). These tables are tiny
# (user_leagues ~2k, user_picks ~200, predictions ~500, communities ~20),
# so we load them ONCE here and build every UserContext from memory with
# zero per-user network calls. Same data, same triggers — ~4000x fewer reads.
@dataclass
class BulkContext:
    fav_leagues_by_uid: dict[str, set] = field(default_factory=dict)
    accuracy_by_uid: dict[str, dict] = field(default_factory=dict)
    league_name_by_id: dict[int, str] = field(default_factory=dict)
    next_match_by_league: dict[int, UpcomingMatch] = field(default_factory=dict)
    top_pick_today: UpcomingMatch | None = None
    owned_by_uid: dict[str, dict] = field(default_factory=dict)


def _supa_page(table: str, params: dict, url: str, headers: dict, step: int = 1000) -> list:
    """Range-paginate a Supabase REST table fully."""
    out, off = [], 0
    while True:
        h = dict(headers)
        h['Range-Unit'] = 'items'
        h['Range'] = f'{off}-{off + step - 1}'
        try:
            r = requests.get(f'{url}/rest/v1/{table}', params=params, headers=h, timeout=30)
        except Exception:
            break
        if r.status_code not in (200, 206):
            break
        rows = r.json()
        out += rows
        if len(rows) < step:
            break
        off += step
    return out


def prefetch_bulk_context() -> BulkContext:
    """Load the entire Predictify behavioral dataset once. Returns an empty
    BulkContext (callers fall back to per-user fetch) if creds are missing."""
    bulk = BulkContext()
    raw = _supa_headers()
    if not raw:
        return bulk
    url = raw.pop('_url', SUPABASE_URL)
    headers = raw
    if not url:
        return bulk

    now = datetime.now(timezone.utc)

    # 1. Followed leagues → {uid: set(league_id)} (favorites only, matching
    #    the per-user query's is_favorite=true filter).
    for row in _supa_page('user_leagues', {'select': 'firebase_uid,league_id,is_favorite'}, url, headers):
        if row.get('is_favorite') and isinstance(row.get('league_id'), int):
            bulk.fav_leagues_by_uid.setdefault(row['firebase_uid'], set()).add(row['league_id'])

    # 2. Pick accuracy (last 30d, scored) → {uid: {rate,total,correct}}.
    since = (now - timedelta(days=30)).isoformat()
    acc_tmp: dict[str, list] = {}
    for row in _supa_page('user_picks',
                          {'select': 'user_id,is_correct', 'created_at': f'gte.{since}',
                           'is_correct': 'not.is.null'}, url, headers):
        uid = row.get('user_id')
        if not uid:
            continue
        a = acc_tmp.setdefault(uid, [0, 0])  # [total, correct]
        a[0] += 1
        if row.get('is_correct') is True:
            a[1] += 1
    for uid, (total, correct) in acc_tmp.items():
        if total:
            bulk.accuracy_by_uid[uid] = {'rate': correct / total, 'total': total, 'correct': correct}

    # 3. Predictions (all) → league-name map + global top pick + per-league
    #    next match. One fetch covers all three; we filter windows in memory.
    preds = _supa_page('predictions',
                       {'select': 'fixture_id,league_id,league_name,home_team_name,'
                                  'away_team_name,match_date,confidence_score,prediction_data'},
                       url, headers)
    top_pick = None
    top_conf = -1.0
    soon_24h = (now + timedelta(hours=24))
    soon_36h = (now + timedelta(hours=36))
    for row in preds:
        lid = row.get('league_id')
        if isinstance(lid, int) and row.get('league_name'):
            bulk.league_name_by_id.setdefault(lid, row['league_name'])
        md = row.get('match_date')
        try:
            kickoff = datetime.fromisoformat(md.replace('Z', '+00:00')) if md else None
        except Exception:
            kickoff = None
        if not kickoff or kickoff < now:
            continue
        # Global top pick: highest confidence kicking off within 24h.
        if kickoff <= soon_24h:
            conf = float(row.get('confidence_score') or 0)
            if conf > top_conf:
                top_conf = conf
                top_pick = _row_to_upcoming(row)
        # Per-league next match within 36h (earliest wins).
        if isinstance(lid, int) and kickoff <= soon_36h:
            existing = bulk.next_match_by_league.get(lid)
            if existing is None or (existing.kickoff_dt and kickoff < existing.kickoff_dt):
                bulk.next_match_by_league[lid] = _row_to_upcoming(row)
    bulk.top_pick_today = top_pick

    # 4. Community ownership → {ownerId: {id,name,memberCount}} (Firestore,
    #    all ~20 communities in one list call — replaces a per-user runQuery).
    tok = _fb_token()
    if tok:
        try:
            r = requests.get(
                f'{FIRESTORE_BASE}/communities',
                params=[('pageSize', 300), ('mask.fieldPaths', 'ownerId'),
                        ('mask.fieldPaths', 'name'), ('mask.fieldPaths', 'memberCount')],
                headers={'Authorization': f'Bearer {tok}'}, timeout=15,
            )
            if r.ok:
                for doc in r.json().get('documents', []):
                    fields = doc.get('fields', {})
                    owner = fields.get('ownerId', {}).get('stringValue')
                    if not owner:
                        continue
                    bulk.owned_by_uid.setdefault(owner, {
                        'id': doc['name'].rsplit('/', 1)[-1],
                        'name': fields.get('name', {}).get('stringValue'),
                        'memberCount': int(fields.get('memberCount', {}).get('integerValue') or 0),
                    })
        except Exception:
            pass

    return bulk


def fetch_user_context(
    uid: str,
    email: str,
    display_name: str,
    language: str = 'en',
    activity: dict | None = None,
    bulk: BulkContext | None = None,
) -> UserContext:
    """Build a fresh UserContext for one user. ``activity`` is the dict
    already loaded by FirestoreActivityLoader if available — saves an
    extra round-trip.

    If ``bulk`` (from prefetch_bulk_context) is supplied, ALL behavioral
    fields are read from the in-memory indexes with zero per-user network
    calls. Without it, the legacy per-user query path runs (kept for
    standalone/ad-hoc use)."""

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

    if bulk is not None:
        # ── Fast path: everything from the in-memory bulk indexes ──
        fav = bulk.fav_leagues_by_uid.get(uid) or set()
        ctx.followed_league_ids = list(set(ctx.followed_league_ids) | fav)
        ctx.followed_league_names = [
            bulk.league_name_by_id[l] for l in ctx.followed_league_ids
            if l in bulk.league_name_by_id
        ]
        acc = bulk.accuracy_by_uid.get(uid)
        if acc:
            ctx.accuracy_30d = acc['rate']
            ctx.total_picks_30d = acc['total']
            ctx.correct_picks_30d = acc['correct']
        # Next followed-league match = earliest across the user's leagues.
        nm = None
        for l in ctx.followed_league_ids:
            m = bulk.next_match_by_league.get(l)
            if m and (nm is None or (m.kickoff_dt and nm.kickoff_dt and m.kickoff_dt < nm.kickoff_dt)):
                nm = m
        ctx.next_match = nm
        ctx.todays_top_pick = bulk.top_pick_today
        owned = bulk.owned_by_uid.get(uid)
        if owned:
            ctx.owned_community_id = owned['id']
            ctx.owned_community_name = owned.get('name')
            ctx.owned_community_member_count = int(owned.get('memberCount') or 0)
        return ctx

    # ── Legacy per-user path (no bulk supplied) ──
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
