"""
triggers.py — Decide which v2 email (if any) should fire for a given user.

Each trigger has:
  • a priority (lower = checked first; first match wins)
  • a condition (predicate over UserContext)
  • a kind (template name)

Returns the kind to send, or None if no v2 email applies and we should
fall back to the v1 daily sequence.

Why priority matters:
  A user who is mid-streak AND has an upcoming followed-league match
  should get the streak_saver (loss aversion is the strongest internal
  trigger). They also shouldn't get the welcome email twice.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from .user_context import UserContext


# A trigger is (priority, kind, predicate). Lower priority = higher precedence.
TRIGGERS: list[tuple[int, str, Callable[[UserContext], bool]]] = [
    # ── 1. Streak about to break (loss aversion = highest internal trigger) ──
    (10, 'streak_saver', lambda c: (
        c.streak_days >= 3
        and (c.hours_since_last_pick or 0) >= 18
        and (c.hours_since_last_pick or 0) <= 30
    )),

    # ── 2. Match-day in followed league within 2-12 hours ──
    (20, 'match_day', lambda c: (
        c.next_match is not None
        and c.next_match.headline_pick_label is not None
        and 2 <= _hours_until(c.next_match.kickoff_dt) <= 12
    )),

    # ── 3. New user welcome (first 24h, no picks yet) ──
    (30, 'welcome', lambda c: (
        c.total_picks_30d == 0
        and (c.last_pick_at is None)
        and c.todays_top_pick is not None
    )),

    # ── 4. Owner growth nudge (community owner with <5 members) ──
    (40, 'owner_growth', lambda c: (
        c.owned_community_id is not None
        and c.owned_community_member_count < 5
    )),

    # ── 5. Win-back for users gone 5-14 days ──
    (50, 'win_back', lambda c: (
        c.last_pick_at is not None
        and 5 * 24 <= (c.hours_since_last_pick or 0) <= 14 * 24
        and c.total_picks_30d >= 1
    )),

    # ── 6. Weekly recap for engaged users (Sunday only) ──
    (60, 'weekly_recap', lambda c: (
        c.total_picks_30d >= 3
        and datetime.now(timezone.utc).weekday() == 6  # Sunday
    )),

    # ── 7. Community invite for new users with no community ──
    (70, 'community_invite', lambda c: (
        c.joined_community_count == 0
        and c.owned_community_id is None
        and c.total_picks_30d >= 2
        and getattr(c, '_recommended_community_id', None) is not None
    )),
]


def select_trigger(ctx: UserContext) -> str | None:
    """First matching trigger wins. Returns kind or None."""
    for _prio, kind, pred in sorted(TRIGGERS):
        try:
            if pred(ctx):
                return kind
        except Exception:
            continue
    return None


def _hours_until(dt) -> int:
    if not dt:
        return 0
    return max(0, int((dt - datetime.now(timezone.utc)).total_seconds() // 3600))
