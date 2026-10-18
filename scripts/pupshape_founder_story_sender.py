#!/usr/bin/env python3
"""PupShape emotional founder story — free Auth users, once-ever."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth_export_mail import CACHE, send_once_ever_founder

APP_NAME = 'PupShape'
APP_SLUG = 'pupshape'
KIND = 'pupshape_founder_story'
STORE = 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749'
STATE = CACHE / 'pupshape_founder_story_state.json'
EXPORTS = ['petmealai_fresh.json', 'pupshape_fresh.json']
DAILY_CAP = int(os.getenv('PUPSHAPE_FOUNDER_DAILY_CAP', '40'))

SUBJECT = "{first_name}, your dog is family — love them longer"
BODY = [
    "Hey {first_name},",
    "Everyone who loves their dog knows the look — the eyes that make you say yes to another treat. They're not \"just a pet.\" They're family. And love without a plan can quietly create health problems.",
    "I built PupShape because caring for your dog is like caring for a kid: the right food, the right portions, the long game. More healthy years together — that's the thank-you they can't say out loud.",
    "This isn't about guilt. It's about love that shows up as better choices.",
    "Your next step takes about a minute: open PupShape and start today's plan for your dog.",
    "P.S. Small consistent steps beat a perfect diet you abandon in a week.",
]
CTA = "Start today's plan"


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
