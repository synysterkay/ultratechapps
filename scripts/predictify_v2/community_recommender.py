"""
community_recommender.py — Picks a public community to invite a user to.

The pool of recommendable communities is small (~tens of public ones in
Predictify today), so we load the top N once per run and recommend from
the in-memory list. Per-user scoring favours matching the user's
followed leagues; we then verify the user isn't already a member of the
chosen community before returning it.

Schema (from lib/models/community.dart):
  - isPublic (bool)
  - leagues (List<int>) — API-Football league ids
  - leagueNames (List<string>)
  - ownerId, ownerName, memberCount, name

Membership: subcollection `communities/{cid}/members/{uid}` — one doc per
member, doc id is the uid. Existence-check is O(1) via a Get on the
exact doc path.
"""
from __future__ import annotations

import time
import requests

from . import user_context as _uc  # reuse _fb_token + FIRESTORE_BASE


# How many candidates we evaluate per user before giving up. Keeps the
# per-user worst-case to 5 Firestore Get calls (already-a-member checks).
MAX_CANDIDATES_PER_USER = 5

# Minimum members for a community to feel "alive" enough to invite to.
# Below this it reads like an empty room and the invite backfires.
MIN_ACTIVE_MEMBER_COUNT = 5

# Cap the candidate pool size. There aren't many public communities yet,
# so 50 is plenty; if the app grows past that we can paginate.
POOL_SIZE = 50


class CommunityRecommender:
    def __init__(self) -> None:
        self.pool: list[dict] = []
        self._token: str | None = None

    # ──────────────────────────────────────────────────────────
    # Bulk load: public communities, ordered by memberCount desc.
    # ──────────────────────────────────────────────────────────
    def load(self) -> int:
        tok = _uc._fb_token()
        if not tok:
            print('   ⚠️ CommunityRecommender: no Firebase token, skipping')
            return 0
        self._token = tok
        try:
            body = {
                'structuredQuery': {
                    'from': [{'collectionId': 'communities'}],
                    'where': {
                        'fieldFilter': {
                            'field': {'fieldPath': 'isPublic'},
                            'op': 'EQUAL',
                            'value': {'booleanValue': True},
                        }
                    },
                    'orderBy': [
                        {'field': {'fieldPath': 'memberCount'},
                         'direction': 'DESCENDING'},
                        # Tie-break by createdAt to keep the order stable.
                        {'field': {'fieldPath': '__name__'},
                         'direction': 'DESCENDING'},
                    ],
                    'limit': POOL_SIZE,
                }
            }
            r = requests.post(
                f'{_uc.FIRESTORE_BASE}:runQuery',
                headers={'Authorization': f'Bearer {tok}'},
                json=body,
                timeout=15,
            )
            if not r.ok:
                if 'index' in r.text.lower() or r.status_code in (400, 412):
                    print(
                        '   ⚠️ CommunityRecommender: Firestore index missing '
                        f'on {_uc.FIREBASE_PROJECT_ID} — skipping community invites'
                    )
                    return 0
                print(f'   ⚠️ CommunityRecommender pool query {r.status_code}: '
                      f'{r.text[:200]}')
                return 0
            pool: list[dict] = []
            for entry in r.json():
                doc = entry.get('document')
                if not doc:
                    continue
                fields = doc.get('fields', {})
                member_count = int(
                    fields.get('memberCount', {}).get('integerValue') or 0)
                if member_count < MIN_ACTIVE_MEMBER_COUNT:
                    continue
                # Leagues array — Firestore returns arrayValue.values with
                # integerValue strings; coerce to ints.
                leagues_val = fields.get('leagues', {}).get('arrayValue', {})
                leagues = []
                for v in leagues_val.get('values', []) or []:
                    iv = v.get('integerValue')
                    if iv is not None:
                        try:
                            leagues.append(int(iv))
                        except (TypeError, ValueError):
                            pass
                league_names_val = fields.get(
                    'leagueNames', {}).get('arrayValue', {})
                league_names = [
                    v.get('stringValue', '')
                    for v in (league_names_val.get('values') or [])
                    if v.get('stringValue')
                ]
                pool.append({
                    'id': doc['name'].rsplit('/', 1)[-1],
                    'name': fields.get('name', {}).get('stringValue') or '',
                    'ownerId': fields.get('ownerId', {}).get('stringValue') or '',
                    'ownerName': (fields.get('ownerName', {}).get('stringValue')
                                  or 'a Predictify owner'),
                    'memberCount': member_count,
                    'leagues': leagues,
                    'leagueNames': league_names,
                })
            self.pool = pool
            print(f'   📡 CommunityRecommender: loaded {len(pool)} candidate '
                  f'communities')
            return len(pool)
        except Exception as e:
            print(f'   ⚠️ CommunityRecommender load failed: {e}')
            return 0

    # ──────────────────────────────────────────────────────────
    # Per-user recommendation.
    # ──────────────────────────────────────────────────────────
    def recommend(
        self,
        uid: str,
        followed_league_ids: list[int],
        owned_community_id: str | None,
    ) -> dict | None:
        if not self.pool:
            return None
        followed = set(followed_league_ids or [])

        # Score each candidate. Higher = better fit.
        scored: list[tuple[int, dict]] = []
        for c in self.pool:
            if c['ownerId'] == uid:
                continue  # don't invite to your own community
            if owned_community_id and c['id'] == owned_community_id:
                continue
            league_overlap = len(followed.intersection(c['leagues']))
            # League fit is the dominant signal. Within the same fit
            # bucket we fall back to popularity (member count).
            score = league_overlap * 10_000 + c['memberCount']
            scored.append((score, c))

        scored.sort(key=lambda x: -x[0])

        # Walk top candidates, skipping ones the user is already a member of.
        for _score, c in scored[:MAX_CANDIDATES_PER_USER]:
            if self._is_member(c['id'], uid):
                continue
            return c
        return None

    # ──────────────────────────────────────────────────────────
    # Member existence check — single Get on the exact doc path.
    # Returns True on confirmed-member, False on confirmed-not-member.
    # On error we err on the side of "skip this candidate" to avoid
    # inviting an existing member, which is the worst failure mode.
    # ──────────────────────────────────────────────────────────
    def _is_member(self, community_id: str, uid: str) -> bool:
        tok = self._token or _uc._fb_token()
        if not tok:
            return True  # be safe — skip candidate
        try:
            r = requests.get(
                f'{_uc.FIRESTORE_BASE}/communities/{community_id}/members/{uid}',
                headers={'Authorization': f'Bearer {tok}'},
                timeout=8,
            )
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                return False
            return True  # treat unexpected status as "skip"
        except Exception:
            return True

    # ──────────────────────────────────────────────────────────
    # Best-effort "is the user in ANY community?" — used to populate
    # joined_community_count. Walks our (already-loaded) pool and stops
    # at the first hit. Worst case = POOL_SIZE doc-existence GETs, but
    # in practice the first 1-2 candidates resolve it for active users.
    # ──────────────────────────────────────────────────────────
    def joined_count_estimate(self, uid: str) -> int:
        """Returns 0 if no hits in pool, 1 if at least one. We don't need
        an exact count for trigger logic — the predicate only ever asks
        '== 0' vs '> 0'."""
        if not self.pool:
            return 0
        # Bound the scan so we don't pay POOL_SIZE GETs on quiet users.
        for c in self.pool[:8]:
            if self._is_member(c['id'], uid):
                return 1
            # Tiny pause keeps us under aggressive rate limits.
            time.sleep(0.02)
        return 0
