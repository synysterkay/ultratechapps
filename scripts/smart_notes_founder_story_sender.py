#!/usr/bin/env python3
"""Smart Notes emotional founder story — free Auth users."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_once_ever_founder

APP_NAME = 'Smart Notes'
APP_SLUG = 'smart_notes'
KIND = 'smart_notes_founder_story'
STORE = 'https://apps.apple.com/app/smart-notes-ai-meeting-summary/id6756840480'
STATE = CACHE / 'smart_notes_founder_story_state.json'
EXPORTS = ['smart_notes_fresh.json', 'audio-recorder-microphone_fresh.json']
DAILY_CAP = int(os.getenv('SMART_NOTES_FOUNDER_DAILY_CAP', '40'))

SUBJECT = "{first_name}, you can just yap — we’ll organize it"
BODY = [
    "Hey {first_name},",
    "Meetings used to mean choosing: be present, or write everything down and miss half the room. I got tired of that trade.",
    "I built Smart Notes so you can just yap — talk the meeting, capture the audio — and get notes organized the way you actually use them afterward.",
    "Your next step: open Smart Notes on one meeting this week and let the structure appear after you hang up.",
    "P.S. You don't need perfect notes in the moment. You need a clean record after.",
]
CTA = 'Record one meeting'


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
        sender_name='Alex',
        dry_run=dry_run,
    )


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
