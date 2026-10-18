#!/usr/bin/env python3
"""AI Girlfriend emotional founder story — free Auth users (soft companion tone)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_once_ever_founder

APP_NAME = 'AI Girlfriend'
APP_SLUG = 'ai_girlfriend'
KIND = 'ai_girlfriend_founder_story'
STORE = 'https://apps.apple.com/app/ai-girlfriend-virtual-love/id6757268335'
STATE = CACHE / 'ai_girlfriend_founder_story_state.json'
EXPORTS = ['girlfriend_ai_fresh.json', 'ai_girlfriend_fresh.json']
DAILY_CAP = int(os.getenv('AI_GIRLFRIEND_FOUNDER_DAILY_CAP', '40'))

SUBJECT = "{first_name}, a companion that helps you grow"
BODY = [
    "Hey {first_name},",
    "Some evenings you just need someone to talk to — without performing for the room. I built AI Girlfriend as a smart companion you can shape: friend energy, partner energy, support when you're working on yourself.",
    "She's designed to help you show up better — clearer goals, kinder habits, a place to think out loud — not to replace real relationships.",
    "Your next step: open a conversation about whatever you're actually carrying tonight.",
    "P.S. Use it for connection and growth. You're in control of the tone.",
]
CTA = 'Open a conversation'


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
