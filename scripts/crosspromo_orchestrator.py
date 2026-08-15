#!/usr/bin/env python3
"""
Crosspromotion orchestrator — Thesis phase 1 entrypoint.

Usage:
  python3 scripts/crosspromo_orchestrator.py
  python3 scripts/crosspromo_orchestrator.py --dry-run
  python3 scripts/crosspromo_orchestrator.py --warm
  python3 scripts/crosspromo_orchestrator.py --warm --adapt
  python3 scripts/crosspromo_orchestrator.py --status
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main() -> None:
    parser = argparse.ArgumentParser(description='Crosspromotion orchestrator')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--warm', action='store_true')
    parser.add_argument('--adapt', action='store_true')
    parser.add_argument('--refresh-templates', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--skip-warm', action='store_true',
                        help='Skip EN cache write before send')
    args = parser.parse_args()

    enabled = os.getenv('CROSSPROMO_ENABLED', '1').strip().lower()
    if enabled in ('0', 'false', 'no', 'off') and not args.status and not args.warm:
        print('⏸️ CROSSPROMO_ENABLED=0 — skipping crosspromo run')
        return

    import crosspromo_thesis_sender as sender

    if args.status:
        sender.print_status()
        return

    if args.warm:
        sender.warm_templates(adapt=args.adapt, refresh=args.refresh_templates)
        if not args.dry_run and args.limit == 0 and '--send' not in sys.argv:
            # Warm-only unless dry-run/limit/send requested
            if not any(a in sys.argv for a in ('--dry-run', '--limit')):
                return

    if not args.skip_warm and not args.warm:
        # Ensure EN templates exist before send
        from thesis_template_translator import _write_cache
        for stage, src in sender.EN_SOURCES.items():
            _write_cache(f'{sender.KIND_PREFIX}_{stage}', 'en', src)

    sender.run(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
