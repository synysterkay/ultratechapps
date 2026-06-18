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

Founder story (World Cup 2026) is NOT listed here — it fires as a
once-ever fallback in orchestrator._pick_kind() when no behavioral
trigger matches and the user hasn't received it yet.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from .user_context import UserContext


# A trigger is (priority, kind, predicate). Lower priority = higher precedence.
# Branched by Pro vs free where the message changes per segment.
TRIGGERS: list[tuple[int, str, Callable[[UserContext], bool]]] = [
    # ── 1. 3-day login streak reward (highest because it's a promise we
    #      already made — never miss it). Fires once when streak first hits 3.
    (5, 'login_streak_reward', lambda c: (
        c.streak_days == 3
        and not c.is_premium  # don't offer Pro to people who already have it
    )),

    # ── 2. Streak about to break ──
    (10, 'streak_saver', lambda c: (
        c.streak_days >= 3
        and (c.hours_since_last_pick or 0) >= 18
        and (c.hours_since_last_pick or 0) <= 30
    )),

    # ── 3. Match-day in followed league within 2-12 hours ──
    (20, 'match_day', lambda c: (
        c.next_match is not None
        and c.next_match.headline_pick_label is not None
        and 2 <= _hours_until(c.next_match.kickoff_dt) <= 12
    )),

    # ── 4. New user welcome ──
    (30, 'welcome', lambda c: (
        c.total_picks_30d == 0
        and (c.last_pick_at is None)
        and c.todays_top_pick is not None
    )),

    # ── 5. Free user with a hot accuracy week — upgrade pitch ──
    (35, 'upgrade_after_hot_week', lambda c: (
        not c.is_premium
        and c.total_picks_30d >= 5
        and (c.accuracy_30d or 0) >= 0.6
        and datetime.now(timezone.utc).weekday() in (0, 1)  # Mon/Tue
    )),

    # ── 6. Owner: marketing toolkit (7+ days post-create, <5 members) ──
    (38, 'owner_marketing_kit', lambda c: (
        c.owned_community_id is not None
        and c.owned_community_member_count < 5
    )),

    # ── 7. Pro user pitched to start own community (30+ days Pro) ──
    (40, 'pro_owner_pitch', lambda c: (
        c.is_premium
        and c.owned_community_id is None
        and c.total_picks_30d >= 5
        and datetime.now(timezone.utc).weekday() == 3  # Thursday
    )),

    # ── 8. Pro power-user education (Pro, engaged, weekly) ──
    (45, 'pro_power_tip', lambda c: (
        c.is_premium
        and c.total_picks_30d >= 3
        and datetime.now(timezone.utc).weekday() == 1  # Tuesday
    )),

    # ── 9. Win-back for users gone 5-14 days ──
    (50, 'winback_lapsed_pro', lambda c: (
        # Was Pro at some point AND has been quiet. We use the in-memory
        # is_premium signal here; full historical-Pro tracking would need a
        # Stripe-side check. For now: fires for currently-Pro users who've
        # gone quiet (i.e., paying but disengaged — risk of churn).
        c.is_premium
        and (c.hours_since_last_pick or 0) >= 7 * 24
    )),

    (55, 'win_back', lambda c: (
        not c.is_premium
        and c.last_pick_at is not None
        and 5 * 24 <= (c.hours_since_last_pick or 0) <= 14 * 24
        and c.total_picks_30d >= 1
    )),

    # ── 10. Referral invite for free users who've been engaged ──
    (58, 'referral_invite', lambda c: (
        not c.is_premium
        and c.total_picks_30d >= 3
        and datetime.now(timezone.utc).weekday() == 5  # Saturday
    )),

    # ── 11. Weekly recap (Sunday) ──
    (60, 'weekly_recap', lambda c: (
        c.total_picks_30d >= 3
        and datetime.now(timezone.utc).weekday() == 6
    )),

    # ── 12. Community invite. The orchestrator attaches a recommended
    #     community via CommunityRecommender before this predicate runs,
    #     and the recommender already filters out communities the user
    #     owns or is a member of — so the predicate doesn't need its own
    #     join-count check.
    (70, 'community_invite', lambda c: (
        c.owned_community_id is None
        and c.total_picks_30d >= 2
        and getattr(c, '_recommended_community_id', None) is not None
    )),

    # ── 13. Owner growth (legacy, lowest priority; covered by kit above) ──
    (80, 'owner_growth', lambda c: (
        c.owned_community_id is not None
        and c.owned_community_member_count < 5
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
