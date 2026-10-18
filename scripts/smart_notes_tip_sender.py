#!/usr/bin/env python3
"""Smart Notes value tips — free Auth users."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_staged_tips

APP_NAME = 'Smart Notes'
APP_SLUG = 'smart_notes'
KIND = 'smart_notes_tip'
STORE = 'https://apps.apple.com/app/smart-notes-ai-meeting-summary/id6756840480'
STATE = CACHE / 'smart_notes_tip_state.json'
EXPORTS = ['smart_notes_fresh.json', 'audio-recorder-microphone_fresh.json']
DAILY_CAP = int(os.getenv('SMART_NOTES_TIP_DAILY_CAP', '30'))

STAGES = [
    ('yap', 0, 30),
    ('organize', 31, 9999),
]
EN_SOURCES = {
    'yap': {
        'subject': 'Tip: just yap — we’ll organize it',
        'body': [
            "Gen Z tip: you don't need to write the meeting. Talk it out. Yap. Capture audio and let the structure show up after.",
            "Open Smart Notes on your next call and let it turn the mess into clean notes.",
            "P.S. Presence > frantic typing.",
        ],
        'cta': 'Try Smart Notes',
    },
    'organize': {
        'subject': 'Tip: notes in the shape you actually use',
        'body': [
            "Tip: decide the output once (actions, summary, bullets) so every meeting lands the same way.",
            "Open Smart Notes and set the format you want before the next call.",
            "P.S. Last tip for now — mute anytime.",
        ],
        'cta': 'Open Smart Notes',
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
        sender_name='Alex',
        dry_run=dry_run,
    )


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
