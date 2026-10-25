#!/usr/bin/env python3
"""Red Flag Scanner value tips — free Auth users, staged, capped."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_staged_tips

APP_NAME = 'Red Flag Scanner AI'
APP_SLUG = 'red_flag_scanner'
KIND = 'red_flag_tip'
STORE = 'https://apps.apple.com/app/red-flag-scanner-ai/id6740946063'
STATE = CACHE / 'red_flag_tip_state.json'
EXPORTS = ['redflagscanner_fresh.json', 'red_flag_scanner_fresh.json']
DAILY_CAP = int(os.getenv('RED_FLAG_TIP_DAILY_CAP', '80'))

STAGES = [
    ('notice', 0, 21),
    ('pattern', 22, 60),
    ('green', 61, 9999),
]
EN_SOURCES = {
    'notice': {
        'subject': 'Tip: name one behavior before you defend it',
        'body': [
            "When something feels \"off,\" tip: write one concrete behavior (what they did, not who they are) before you explain it away.",
            "Open Red Flag Scanner and run a quick scan on that moment. Naming it breaks autopilot.",
            "P.S. Clarity first. Decisions later.",
        ],
        'cta': 'Run one scan',
    },
    'pattern': {
        'subject': 'Tip: look for the repeat, not the apology',
        'body': [
            "Most people forgive the story. Tip: check whether the same pattern shows up three times — that's the signal.",
            "Open the app and compare this week to last. Patterns are quieter than drama, and more honest.",
            "P.S. You're not \"too sensitive\" for wanting a pattern map.",
        ],
        'cta': 'Check the pattern',
    },
    'green': {
        'subject': 'Tip: collect green flags on purpose',
        'body': [
            "Healthy doesn't mean perfect. Tip: note two green flags this week (consistency, repair, respect for a no).",
            "Open Red Flag Scanner and log what felt safe — not just what felt wrong.",
            "P.S. Last tip in this short series. You're allowed to go quiet.",
        ],
        'cta': 'Open Red Flag Scanner',
    },
}


def main(dry_run: bool = False) -> None:
    send_staged_tips(
        app_name=APP_NAME,
        app_slug=APP_SLUG,
        kind=KIND,
        state_file=STATE,
        export_names=EXPORTS,
        store_url=STORE,
        stages=STAGES,
        en_sources=EN_SOURCES,
        daily_cap=DAILY_CAP,
        sender_name='Selka',
        dry_run=dry_run,
    )


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
