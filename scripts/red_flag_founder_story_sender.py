#!/usr/bin/env python3
"""Red Flag Scanner emotional founder story — free Auth users, once-ever."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_once_ever_founder

APP_NAME = 'Red Flag Scanner AI'
APP_SLUG = 'red_flag_scanner'
KIND = 'red_flag_founder_story'
STORE = 'https://apps.apple.com/app/red-flag-scanner-ai/id6740946063'
STATE = CACHE / 'red_flag_founder_story_state.json'
EXPORTS = ['redflagscanner_fresh.json', 'red_flag_scanner_fresh.json']
DAILY_CAP = int(os.getenv('RED_FLAG_FOUNDER_DAILY_CAP', '80'))

SUBJECT = "{first_name}, I kept repeating the same relationship"
BODY = [
    "Hey {first_name},",
    "Most relationships have patterns that repeat. You can talk yourself into ignoring them — especially when part of you is still protecting an old wound. It doesn't mean you're weak. It means the blind spot is familiar.",
    "I built Red Flag Scanner because I wanted a plain-language mirror: what's off, what might be healthy, and where someone may be pressing on a soft spot I didn't notice yet — without turning life into a courtroom.",
    "It also shows green flags. The point isn't paranoia. It's making a complicated feeling simpler so you can choose with clearer eyes.",
    "Your next step takes about two minutes: open the app and run one scan on a moment that still bothers you.",
    "P.S. This isn't therapy and it doesn't \"know you better than you.\" It's a pattern tool — use what helps, ignore the rest.",
]
CTA = 'Run one scan'


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
        sender_name='Selka',
        dry_run=dry_run,
    )


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
