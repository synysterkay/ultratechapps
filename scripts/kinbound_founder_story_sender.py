#!/usr/bin/env python3
"""KinBound emotional founder story — free Auth users, once-ever."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_once_ever_founder

APP_NAME = 'KinBound'
APP_SLUG = 'kinbound'
KIND = 'kinbound_founder_story'
STORE = 'https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071'
STATE = CACHE / 'kinbound_founder_story_state.json'
EXPORTS = ['parents_ai_e49a8_fresh.json', 'kinbound_fresh.json']
DAILY_CAP = int(os.getenv('KINBOUND_FOUNDER_DAILY_CAP', '40'))

SUBJECT = "{first_name}, I didn't want to regret what I allowed"
BODY = [
    "Hey {first_name},",
    "Parenting with social media in the room is a different game. You worry about what you allowed, what you didn't, and whether your kid will thank you — or ask why you stayed quiet.",
    "I built KinBound for the 3 AM spiral and the hard conversations: calm, evidence-based guidance when Google gives you forty conflicting answers — including how you talk with your kid so they grow into someone who can lead their own life.",
    "You're not failing. You're doing the quiet work of raising them in a loud world.",
    "Your next step takes about a minute: open KinBound and ask one real question you're carrying tonight.",
    "P.S. No perfect parents — just clearer next steps when you need them.",
]
CTA = 'Ask one parenting question'


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
