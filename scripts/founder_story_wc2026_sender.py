#!/usr/bin/env python3
"""Deprecated wrapper — delegates to founder_story_predictify_sender.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == '__main__':
    if '--non-subscribers-only' in sys.argv and '--v2' not in sys.argv:
        sys.argv.insert(1, '--v2')
    if '--warm' not in sys.argv and '--backfill' not in sys.argv and '--v2' not in sys.argv:
        sys.argv.insert(1, '--backfill')
    from founder_story_predictify_sender import main
    main()
