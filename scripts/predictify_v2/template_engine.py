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
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

from .user_context import UserContext, UpcomingMatch


# Soccer uses `templates/`; NBA/Tennis profiles set
# PREDICTIFY_TEMPLATES_DIR=templates_nba or templates_tennis.
TEMPLATES_DIR = Path(__file__).parent / os.environ.get(
    'PREDICTIFY_TEMPLATES_DIR', 'templates')

SUPPORTED_LANGS = [
    'en', 'ar', 'de', 'es', 'fr', 'hi', 'id', 'it', 'ja', 'nl', 'pl',
    'pp', 'pt', 'tr',
]

# Legacy WC2026 kinds — still honored for dedup; templates map to evergreen copy.
LEGACY_FOUNDER_V1_KINDS = frozenset({'founder_story_wc2026'})
LEGACY_FOUNDER_V2_KINDS = frozenset({'founder_story_wc2026_v2'})

FOUNDER_STORY_PREFIXES = (
    'founder_story_soccer',
    'founder_story_nba',
    'founder_story_tennis',
    'founder_story_horse',
    'founder_story_wc2026',
)


def founder_story_kinds_for_app() -> tuple[str, str]:
    """Return (v1_kind, v2_kind) for the active PREDICTIFY_APP_NAME profile."""
    app_name = os.environ.get('PREDICTIFY_APP_NAME', 'Predictify')
    if 'NBA' in app_name:
        return 'founder_story_nba', 'founder_story_nba_v2'
    if 'Tennis' in app_name:
        return 'founder_story_tennis', 'founder_story_tennis_v2'
    if 'Horse' in app_name:
        return 'founder_story_horse', 'founder_story_horse_v2'
    return 'founder_story_soccer', 'founder_story_soccer_v2'


def is_founder_story_kind(kind: str) -> bool:
    return any(kind == p or kind == f'{p}_v2' for p in FOUNDER_STORY_PREFIXES)


def _template_file_kind(kind: str) -> str:
    """Map legacy send kinds to evergreen template files."""
    if kind in LEGACY_FOUNDER_V2_KINDS:
        _, v2 = founder_story_kinds_for_app()
        return v2
    if kind in LEGACY_FOUNDER_V1_KINDS:
        v1, _ = founder_story_kinds_for_app()
        return v1
    return kind


@dataclass
class RenderedEmail:
    kind: str
    language: str
    subject: str
    preview_text: str
    body_paragraphs: list[str]
    cta_text: str
    cta_deeplink: str
    app_store_url: str = ''
    google_play_url: str = ''
    cta_ios_text: str = ''
    cta_android_text: str = ''


def render_template(kind: str, ctx: UserContext) -> RenderedEmail | None:
    tmpl = _load_template(kind, ctx.language)
    if not tmpl:
        return None
    fields = _build_merge_fields(kind, ctx)
    if fields is None:
        return None

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
        app_store_url=tmpl.get('app_store_url', ''),
        google_play_url=tmpl.get('google_play_url', ''),
        cta_ios_text=fill(tmpl.get('cta_ios_text', 'App Store')),
        cta_android_text=fill(tmpl.get('cta_android_text', 'Google Play')),
    )


def _load_template(kind: str, language: str) -> dict | None:
    file_kind = _template_file_kind(kind)
    # v2 templates have their own JSON when present (founder_story_soccer_v2_en.json)
    candidates_kinds = [kind, file_kind] if kind != file_kind else [kind]
    candidates_langs = [language, 'en']
    seen: set[tuple[str, str]] = set()
    for fk in candidates_kinds:
        for lang in candidates_langs:
            key = (fk, lang)
            if key in seen:
                continue
            seen.add(key)
            path = TEMPLATES_DIR / f'{fk}_{lang}.json'
            if path.exists():
                try:
                    with open(path) as f:
                        return json.load(f)
                except Exception:
                    continue
    return None


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
        if ctx.total_picks_30d > 0:
            base['recent_total'] = str(ctx.total_picks_30d)
            base['recent_correct'] = str(ctx.correct_picks_30d)
            base['recent_accuracy_pct'] = str(int(round(
                (ctx.accuracy_30d or 0) * 100)))
        else:
            return None
        return base
    if kind == 'community_invite':
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
        return base
    if is_founder_story_kind(kind) or kind in LEGACY_FOUNDER_V1_KINDS | LEGACY_FOUNDER_V2_KINDS:
        return base
    if kind == 'upgrade_after_hot_week':
        if ctx.total_picks_30d < 5 or (ctx.accuracy_30d or 0) < 0.6:
            return None
        base['recent_total'] = str(ctx.total_picks_30d)
        base['accuracy_pct'] = str(int(round((ctx.accuracy_30d or 0) * 100)))
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
        base['league_short'] = (ctx.followed_league_names[0]
                                if ctx.followed_league_names else 'football')
        return base
    if kind == 'winback_lapsed_pro':
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
    now = datetime.now(timezone.utc)
    end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return max(1, int((end_of_day - now).total_seconds() // 3600))


_FIELD_RE = re.compile(r'\{([a-z_][a-z0-9_]*)\}')


def _safe_format(s: str, fields: dict[str, str]) -> str:
    return _FIELD_RE.sub(
        lambda m: str(fields.get(m.group(1), m.group(0))),
        s,
    )
