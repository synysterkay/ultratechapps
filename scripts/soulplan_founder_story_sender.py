#!/usr/bin/env python3
"""SoulPlan emotional founder story — free Auth users, once-ever."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_once_ever_founder

APP_NAME = 'SoulPlan'
APP_SLUG = 'soulplan'
KIND = 'soulplan_founder_story'
STORE = 'https://apps.apple.com/app/soulplan-plan-dates-together/id6702018988'
STATE = CACHE / 'soulplan_founder_story_state.json'
EXPORTS = ['soulplan-dateplanner_fresh.json', 'soulplan_fresh.json']
DAILY_CAP = int(os.getenv('SOULPLAN_FOUNDER_DAILY_CAP', '80'))

SUBJECT = "{first_name}, I got tired of “what do you want to do?”"
BODY = [
    "Hey {first_name},",
    "After a while in a relationship, love is still there — but the week gets automatic. Same couch. Same takeout. Same \"what do you want to do?\" that nobody answers.",
    "I built SoulPlan because I wanted everyday life to feel like a small adventure again: new places, new plans, intentional nights — not pressure to perform romance, just a way to keep the spark on purpose.",
    "The couples who use it don't wait for a perfect weekend. They pick one plan and go.",
    "Your next step takes about a minute: open SoulPlan and plan one date you'll actually keep.",
    "P.S. Spark isn't \"always new.\" It's choosing each other on purpose, one plan at a time.",
]
CTA = 'Plan one date'


def main(dry_run: bool = False) -> None:
    send_once_ever_founder(
        app_name=APP_NAME,
        app_slug=APP_SLUG,
        kind=KIND,
        state_file=STATE,
        export_names=EXPORTS,
        store_url=STORE,
        subject=SUBJECT,
        body=BODY,
        cta=CTA,
        daily_cap=DAILY_CAP,
        sender_name='Casey',
        dry_run=dry_run,
    )


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
