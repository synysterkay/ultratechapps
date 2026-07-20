#!/usr/bin/env python3
"""
Horse Racing emails via predictify_v2 (horse Firebase profile).

Daily retention: lapsed founder story fallback (14d+) + small cap.
Backfill: --backfill flag sends v1 to entire unsent cohort.

Usage:
  python3 scripts/founder_story_horse_sender.py
  python3 scripts/founder_story_horse_sender.py --dry-run
  python3 scripts/founder_story_horse_sender.py --backfill --passes 5
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault('PREDICTIFY_APP_NAME', 'Predictify: Horse Racing AI')
os.environ.setdefault('PREDICTIFY_FIREBASE_PROJECT_ID', 'horse-racing-f67e8')
os.environ.setdefault('PREDICTIFY_DISABLE_FOUNDER_FALLBACK', '0')
os.environ.setdefault('FOUNDER_STORY_LAPSED_DAYS', '14')
os.environ.setdefault('V2_DAILY_SEND_CAP', os.environ.get('FOUNDER_STORY_HORSE_DAILY_CAP', '50'))


def main() -> None:
    dry_run = '--dry-run' in sys.argv
    if '--backfill' in sys.argv:
        from founder_story_predictify_sender import main as backfill_main
        if '--passes' not in sys.argv:
            sys.argv.extend(['--passes', os.environ.get('FOUNDER_STORY_HORSE_PASSES', '5')])
        backfill_main()
        return

    from predictify_v2.orchestrator import run
    run(dry_run=dry_run)


if __name__ == '__main__':
    main()
