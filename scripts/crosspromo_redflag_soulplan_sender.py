#!/usr/bin/env python3
"""Crosspromo: Red Flag users → SoulPlan (niche bridge)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from crosspromo_niche_base import run_niche_pack

CACHE = Path(__file__).parent.parent / 'cache'

EN_SOURCES = {
    'e1': {
        'subject': 'You know what’s unhealthy — build something intentional',
        'preview': 'A soft tip for keeping the spark on purpose.',
        'body': [
            "If Red Flag Scanner helped you see patterns, the next skill is quieter: plan connection on purpose.",
            "[[VALUE]]SoulPlan is for couples who are tired of \"what do you want to do?\" — one intentional date at a time.",
            "[[SUB]]Free to peek.",
            "P.S. Spotting red flags and planning green nights are both relationship skills.",
        ],
        'cta': 'Try SoulPlan free',
    },
    'e2': {
        'subject': 'Tip: lock a date slot before you negotiate the vibe',
        'preview': 'Schedule first, then choose.',
        'body': [
            "Tip: lock a day/time first, then pick the activity. Plans without a slot die in the chat.",
            "SoulPlan if you want ideas ready to send. Ignore if you're not there yet.",
        ],
        'cta': 'Plan one date',
    },
    'e3': {
        'subject': 'Last tip: one small adventure this week',
        'preview': 'Closing this bridge.',
        'body': [
            "Last note: spark isn't constant fireworks — it's choosing each other once this week.",
            "SoulPlan is there if you want it. Mute anytime.",
            "P.S. You're receiving this because you use Red Flag Scanner.",
        ],
        'cta': 'Open SoulPlan',
    },
}


def run(*, dry_run: bool = False, limit: int = 0) -> None:
    run_niche_pack(
        campaign='crosspromo_redflag_soulplan_v1',
        kind_prefix='crosspromo_redflag_soulplan',
        target='soulplan',
        app_name='SoulPlan',
        store_ios='https://apps.apple.com/app/soulplan-plan-dates-together/id6702018988',
        store_play='https://play.google.com/store/apps/details?id=com.aifun.dateideas.planadate',
        en_sources=EN_SOURCES,
        state_file=CACHE / 'crosspromo_redflag_soulplan_state.json',
        source_app_names={'Red Flag Scanner AI'},
        exclude_export_files=['soulplan-dateplanner_fresh.json'],
        require_source_state_files=[
            CACHE / 'red_flag_tip_state.json',
            CACHE / 'red_flag_founder_story_state.json',
        ],
        daily_cap_env='CROSSPROMO_REDFLAG_SOULPLAN_DAILY_CAP',
        footer=(
            "You're receiving this because you use Red Flag Scanner. "
            "We're sharing SoulPlan in case intentional dates help next."
        ),
        dry_run=dry_run,
        limit=limit,
    )


def print_status() -> None:
    path = CACHE / 'crosspromo_redflag_soulplan_state.json'
    print(f'=== Red Flag → SoulPlan state: {path} exists={path.exists()} ===')


if __name__ == '__main__':
    if '--status' in sys.argv:
        print_status()
    else:
        run(dry_run='--dry-run' in sys.argv)
