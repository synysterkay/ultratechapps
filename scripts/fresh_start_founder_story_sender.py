#!/usr/bin/env python3
"""Fresh Start emotional founder story — free Auth users, once-ever, capped."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_once_ever_founder

APP_NAME = 'Fresh Start'
APP_SLUG = 'fresh_start'
KIND = 'fresh_start_founder_story'
STORE = 'https://apps.apple.com/app/fresh-start-breakup-therapy-ai/id6749954260'
STATE = CACHE / 'fresh_start_founder_story_state.json'
EXPORTS = [
    'fresh_start_users.json',
    'breakuptherapy-e7dc0_fresh.json',
    'fresh_start_fresh.json',
    'breakup_therapy_fresh.json',
]
DAILY_CAP = int(os.getenv('FRESH_START_FOUNDER_DAILY_CAP', '80'))

SUBJECT = "{first_name}, breakup feels like dying — it isn't"
BODY = [
    "Hey {first_name},",
    "If it feels like the floor dropped out — sleeping is impossible, food tastes like nothing, and every quiet moment pulls you back to them — you're not dramatic. Breakup can feel like dying. It isn't. It just hijacks your nervous system for a while.",
    "I built Fresh Start after my own hard breakup and the long middle that followed. Friends meant well when they said \"move on.\" I needed something that didn't rush me — a pocket guide for the 2 AM spiral, a next small step when willpower was gone.",
    "Weeks later, mornings weren't a fight every single day. Not overnight magic — just enough structure to breathe again.",
    "Your next step takes about three minutes: open Fresh Start tonight and run one check-in (or Emergency Mode if you're in it). One practice. That's enough for today.",
    "P.S. Healing isn't linear. This is a tool, not a therapist replacement — and you're allowed to go at your pace.",
]
CTA = 'Open a 3-minute check-in'


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
