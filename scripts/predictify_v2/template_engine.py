"""
template_engine.py — Load JSON templates and render them with merge fields
from a UserContext. Produces the same shape v1 produces (subject,
preview_text, body_paragraphs, cta_text) so the existing HTML wrapper +
sender pipeline can consume it unchanged.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

from .user_context import UserContext, UpcomingMatch


# Soccer uses `templates/`; the NBA app profile sets
# PREDICTIFY_TEMPLATES_DIR=templates_nba so the same engine renders NBA copy.
TEMPLATES_DIR = Path(__file__).parent / os.environ.get(
    'PREDICTIFY_TEMPLATES_DIR', 'templates')

# Languages we support. Falls back to English if a per-language file is
# missing — the existing v1 system supports all of these.
SUPPORTED_LANGS = [
    'en', 'ar', 'de', 'es', 'fr', 'hi', 'id', 'it', 'ja', 'nl', 'pl',
    'pp', 'pt', 'tr',
]


@dataclass
class RenderedEmail:
    kind: str
    language: str
    subject: str
    preview_text: str
    body_paragraphs: list[str]
    cta_text: str
    cta_deeplink: str


def render_template(kind: str, ctx: UserContext) -> RenderedEmail | None:
    """Load template by kind in user's language (fallback en) and render
    with merge fields. Returns None if the template can't be satisfied
    (e.g. a match_day template requested but the user has no upcoming match)."""
    tmpl = _load_template(kind, ctx.language)
    if not tmpl:
        return None
    fields = _build_merge_fields(kind, ctx)
    if fields is None:
        return None  # template can't be rendered for this user

    def fill(s: str) -> str:
        return _safe_format(s, fields)

    return RenderedEmail(
        kind=kind,
        language=ctx.language,
        subject=fill(tmpl['subject']),
        preview_text=fill(tmpl.get('preview_text', '')),
        body_paragraphs=[fill(p) for p in tmpl.get('body_paragraphs', [])],
        cta_text=fill(tmpl.get('cta_text', 'Open Predictify')),
        cta_deeplink=fill(tmpl.get('cta_deeplink', 'predictify://')),
    )


def _load_template(kind: str, language: str) -> dict | None:
    # Try user language first, then English fallback. Languages without their
    # own file inherit English copy until they're translated — better than
    # silently dropping the email.
    candidates = [language, 'en']
    seen = set()
    for lang in candidates:
        if lang in seen:
            continue
        seen.add(lang)
        path = TEMPLATES_DIR / f'{kind}_{lang}.json'
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                continue
    return None


# ─────────────────────────────────────────────────────────
#  Merge field builder per template kind
# ─────────────────────────────────────────────────────────

def _build_merge_fields(kind: str, ctx: UserContext) -> dict[str, str] | None:
    base = _common_fields(ctx)
    if kind == 'match_day':
        m = ctx.next_match or ctx.todays_top_pick
        if not m or not m.headline_pick_label:
            return None
        base.update(_match_fields(m))
        return base
    if kind == 'streak_saver':
        if ctx.streak_days < 2:
            return None
        m = ctx.next_match or ctx.todays_top_pick
        base['hours_to_break'] = str(_hours_until_streak_break(ctx))
        base['top_match_line'] = _format_top_match_line(m) if m else \
            'Open the app — fresh predictions waiting.'
        if m:
            base['fixture_id'] = str(m.fixture_id)
        return base
    if kind == 'win_back':
        m = ctx.todays_top_pick or ctx.next_match
        base['top_match_line'] = _format_top_match_line(m) if m else \
            'today\'s slate — open the app to see.'
        if m:
            base['fixture_id'] = str(m.fixture_id)
        # Use 30d numbers if we have them, else generic copy via 0
        if ctx.total_picks_30d > 0:
            base['recent_total'] = str(ctx.total_picks_30d)
            base['recent_correct'] = str(ctx.correct_picks_30d)
            base['recent_accuracy_pct'] = str(int(round(
                (ctx.accuracy_30d or 0) * 100)))
        else:
            return None  # no data → don't send
        return base
    if kind == 'community_invite':
        # Caller must have already populated recommended community fields
        # via context overlay; if not present we can't render.
        rc_id = getattr(ctx, '_recommended_community_id', None)
        rc_name = getattr(ctx, '_recommended_community_name', None)
        rc_owner = getattr(ctx, '_recommended_community_owner', None) or 'a Predictify owner'
        rc_count = getattr(ctx, '_recommended_community_member_count', None) or 0
        rc_league = getattr(ctx, '_recommended_community_league', None) or 'football'
        if not rc_id or not rc_name:
            return None
        base['recommended_community_name'] = rc_name
        base['community_id'] = rc_id
        base['owner_name'] = rc_owner
        base['member_count'] = str(rc_count)
        base['league_short'] = rc_league
        return base
    if kind == 'owner_growth':
        if not ctx.owned_community_id or not ctx.owned_community_name:
            return None
        base['community_name'] = ctx.owned_community_name
        base['community_id'] = ctx.owned_community_id
        base['member_count'] = str(ctx.owned_community_member_count)
        base['member_plural'] = '' if ctx.owned_community_member_count == 1 else 's'
        return base
    if kind == 'weekly_recap':
        if ctx.total_picks_30d < 3:
            return None
        m = ctx.next_match or ctx.todays_top_pick
        base['recent_correct'] = str(ctx.correct_picks_30d)
        base['recent_total'] = str(ctx.total_picks_30d)
        base['accuracy_pct'] = str(int(round((ctx.accuracy_30d or 0) * 100)))
        base['top_match_line'] = _format_top_match_line(m) if m else 'TBD'
        if m:
            base['fixture_id'] = str(m.fixture_id)
        return base
    if kind == 'welcome':
        m = ctx.todays_top_pick
        base['top_match_line'] = _format_top_match_line(m) if m else \
            'check today\'s predictions'
        if m:
            base['fixture_id'] = str(m.fixture_id)
        return base
    if kind == 'login_streak_reward':
        # Only fires for free users (gated by trigger). Reward is the
        # short Pro flag toggled by the in-app reward screen.
        return base
    if kind == 'upgrade_after_hot_week':
        if ctx.total_picks_30d < 5 or (ctx.accuracy_30d or 0) < 0.6:
            return None
        base['recent_total'] = str(ctx.total_picks_30d)
        base['accuracy_pct'] = str(int(round((ctx.accuracy_30d or 0) * 100)))
        # Pro accuracy target shown comparatively. Conservative: 72%.
        base['pro_target_pct'] = '72'
        return base
    if kind == 'pro_power_tip':
        m = ctx.todays_top_pick or ctx.next_match
        if not m:
            return None
        base['top_match_line'] = _format_top_match_line(m)
        base['fixture_id'] = str(m.fixture_id)
        return base
    if kind == 'pro_owner_pitch':
        return base
    if kind == 'owner_marketing_kit':
        if not ctx.owned_community_id or not ctx.owned_community_name:
            return None
        base['community_name'] = ctx.owned_community_name
        base['community_id'] = ctx.owned_community_id
        base['member_count'] = str(ctx.owned_community_member_count)
        base['member_plural'] = '' if ctx.owned_community_member_count == 1 else 's'
        # Pick the first followed-league name for the share-tease line.
        base['league_short'] = (ctx.followed_league_names[0]
                                if ctx.followed_league_names else 'football')
        return base
    if kind == 'winback_lapsed_pro':
        # Fires for premium-but-inactive users. The "free 30 days" is an
        # admin-applied bonusProUntil window (no Stripe roundtrip needed).
        return base
    if kind == 'referral_invite':
        if ctx.total_picks_30d < 3:
            return None
        return base
    return None


def _common_fields(ctx: UserContext) -> dict[str, str]:
    first = (ctx.display_name or 'there').split()[0]
    return {
        'first_name': first,
        'streak_days': str(ctx.streak_days),
        'language': ctx.language,
        'fixture_id': '',
    }


def _match_fields(m: UpcomingMatch) -> dict[str, str]:
    h = max(0, _hours_until(m.kickoff_dt))
    tier_label = {
        'elite': 'Elite (top accuracy band)',
        'premium': 'Premium',
        'standard': 'Standard',
    }.get(m.tier or 'standard', 'Standard')
    return {
        'fixture_id': str(m.fixture_id),
        'home_team': m.home_team,
        'away_team': m.away_team,
        'league_name': m.league_name,
        'pick_label': m.headline_pick_label or '',
        'confidence_pct': str(m.confidence_pct),
        'tier_label': tier_label,
        'hours_to_kickoff': str(h),
    }


def _format_top_match_line(m: UpcomingMatch) -> str:
    if not m or not m.headline_pick_label:
        return ''
    return (f'{m.home_team} vs {m.away_team} — {m.headline_pick_label} '
            f'at {m.confidence_pct}% confidence')


def _hours_until(dt) -> int:
    if not dt:
        return 0
    delta = dt - datetime.now(timezone.utc)
    return max(0, int(delta.total_seconds() // 3600))


def _hours_until_streak_break(ctx: UserContext) -> int:
    """Streak window resets at midnight UTC — give a friendly remaining-hours
    figure ('about 14 hours' etc)."""
    now = datetime.now(timezone.utc)
    end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return max(1, int((end_of_day - now).total_seconds() // 3600))


_FIELD_RE = re.compile(r'\{([a-z_][a-z0-9_]*)\}')


def _safe_format(s: str, fields: dict[str, str]) -> str:
    """Replace {placeholders} with field values, leaving unknown ones intact
    rather than crashing — easier to debug than KeyError when a translator
    introduces a typo."""
    return _FIELD_RE.sub(
        lambda m: str(fields.get(m.group(1), m.group(0))),
        s,
    )
