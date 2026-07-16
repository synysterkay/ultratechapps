#!/usr/bin/env python3
"""
Predictify Soccer — behavioral email entry point.

Runs predictify_v2 with P0/P1 triggers only from hello@predictifyfootball.com
(ZeptoMail). The 30-email drip is disabled in app_retention_emailer.py.

Normally invoked automatically as step 0 of app_retention_emailer.run_campaign().
This script exists for manual runs / dry-run debugging.

Usage:
    python scripts/predictify_orchestrator.py
    python scripts/predictify_orchestrator.py --dry-run
    python scripts/predictify_orchestrator.py --status
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Defaults — workflows override via env.
os.environ.setdefault('PREDICTIFY_ACTIVE_TRIGGERS', 'p0p1')
os.environ.setdefault('PREDICTIFY_DISABLE_FOUNDER_FALLBACK', '1')
os.environ.setdefault('PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL', 'hello@predictifyfootball.com')
os.environ.setdefault('PREDICTIFY_ZEPTOMAIL_SENDER_NAME', 'Predictify')


def main():
    dry_run = '--dry-run' in sys.argv
    if '--status' in sys.argv:
        from predictify_v2.orchestrator import status
        status()
        return

    from predictify_v2.orchestrator import run
    sent = run(dry_run=dry_run)
    print(f'✅ Predictify v2 done — {len(sent)} sends')


if __name__ == '__main__':
    main()
