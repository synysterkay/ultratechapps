#!/usr/bin/env python3
"""Crosspromo: Fresh Start users → Red Flag Scanner (niche bridge)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from crosspromo_niche_base import run_niche_pack

CACHE = Path(__file__).parent.parent / 'cache'

EN_SOURCES = {
    'e1': {
        'subject': 'After healing: spot the pattern before it repeats',
        'preview': 'One tip from a sister app — name the behavior.',
        'body': [
            "You already took a hard step with Fresh Start. Tip for what comes after: before you explain away a bad feeling, name one concrete behavior.",
            "[[VALUE]]Red Flag Scanner is built for that — plain-language red and green flags so the next relationship (or the current one) is clearer.",
            "[[SUB]]Free to try. No pressure.",
            "P.S. Healing and pattern-spotting are different skills. Both help.",
        ],
        'cta': 'Try Red Flag Scanner free',
    },
    'e2': {
        'subject': 'Tip: look for the repeat, not the apology',
        'preview': 'Three times is a pattern.',
        'body': [
            "Micro-tip: forgive the story if you want — but check whether the same pattern shows up three times.",
            "[[VALUE]]Red Flag Scanner helps you map that without turning every chat into a fight.",
            "P.S. If you're not dating right now, save it for later. Mute anytime.",
        ],
        'cta': 'Run one scan',
    },
    'e3': {
        'subject': 'Last bridge tip: green flags count too',
        'preview': 'Closing this short thread.',
        'body': [
            "Last note: healthy isn't perfect. Collect green flags on purpose — consistency, repair, respect for a no.",
            "Red Flag Scanner if you want the tool. If not — all good.",
            "P.S. You're receiving this because you use Fresh Start.",
        ],
        'cta': 'Open Red Flag Scanner',
    },
}


def run(*, dry_run: bool = False, limit: int = 0) -> None:
    run_niche_pack(
        campaign='crosspromo_fs_redflag_v1',
        kind_prefix='crosspromo_fs_redflag',
        target='red_flag',
        app_name='Red Flag Scanner AI',
        store_ios='https://apps.apple.com/app/red-flag-scanner-ai/id6740946063',
        store_play='https://play.google.com/store/apps/details?id=com.redflag.scanner.ai.red_flag_scanner',
        en_sources=EN_SOURCES,
        state_file=CACHE / 'crosspromo_fs_redflag_state.json',
        source_app_names={'Fresh Start: Breakup Therapy'},
        exclude_export_files=['redflagscanner_fresh.json'],
        require_source_state_files=[
            CACHE / 'fresh_start_tip_state.json',
            CACHE / 'fresh_start_founder_story_state.json',
        ],
        daily_cap_env='CROSSPROMO_FS_REDFLAG_DAILY_CAP',
        footer=(
            "You're receiving this because you use Fresh Start. "
            "We're sharing Red Flag Scanner in case it helps next."
        ),
        dry_run=dry_run,
        limit=limit,
    )


def print_status() -> None:
    path = CACHE / 'crosspromo_fs_redflag_state.json'
    print(f'=== FS → Red Flag state: {path} exists={path.exists()} ===')


if __name__ == '__main__':
    if '--status' in sys.argv:
        print_status()
    else:
        run(dry_run='--dry-run' in sys.argv)
