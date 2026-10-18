#!/usr/bin/env python3
"""SoulPlan value tips — free Auth users, staged, capped."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_staged_tips

APP_NAME = 'SoulPlan'
APP_SLUG = 'soulplan'
KIND = 'soulplan_tip'
STORE = 'https://apps.apple.com/app/soulplan-plan-dates-together/id6702018988'
STATE = CACHE / 'soulplan_tip_state.json'
EXPORTS = ['soulplan-dateplanner_fresh.json', 'soulplan_fresh.json']
DAILY_CAP = int(os.getenv('SOULPLAN_TIP_DAILY_CAP', '40'))

STAGES = [
    ('spark', 0, 21),
    ('plan', 22, 60),
    ('ritual', 61, 9999),
]
EN_SOURCES = {
    'spark': {
        'subject': 'Tip: replace “what do you want to do?” once this week',
        'body': [
            "Long-term love cools when every night defaults to the same couch and the same question. Tip: bring one specific idea before anyone asks.",
            "Open SoulPlan and pick one date idea you'll actually do this week — small counts.",
            "P.S. Spark is intentional, not constant fireworks.",
        ],
        'cta': 'Plan one date',
    },
    'plan': {
        'subject': 'Tip: schedule the date before you negotiate the vibe',
        'body': [
            "Tip: lock a day/time first, then choose the activity. Negotiation without a slot usually dies in the group chat.",
            "Open SoulPlan, save one plan, and send it. Make the next adventure real.",
            "P.S. You're not boring — you're busy. Planning is the fix.",
        ],
        'cta': 'Open SoulPlan',
    },
    'ritual': {
        'subject': 'Tip: one recurring “adventure hour”',
        'body': [
            "Tip: pick a recurring weekly window for something new-together (walk, new café, tiny trip). Ritual beats inspiration.",
            "Open SoulPlan and stash 3 ideas for that slot so you're never starting from zero.",
            "P.S. Last tip in this series. Mute anytime.",
        ],
        'cta': 'Save three ideas',
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
        sender_name='Casey',
        dry_run=dry_run,
    )


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
