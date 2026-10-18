#!/usr/bin/env python3
"""
Crosspromotion orchestrator — Thesis + niche relationship bridges.

Usage:
  python3 scripts/crosspromo_orchestrator.py
  python3 scripts/crosspromo_orchestrator.py --dry-run
  python3 scripts/crosspromo_orchestrator.py --warm
  python3 scripts/crosspromo_orchestrator.py --status
  python3 scripts/crosspromo_orchestrator.py --pack thesis
  python3 scripts/crosspromo_orchestrator.py --pack fs_redflag
  python3 scripts/crosspromo_orchestrator.py --pack redflag_soulplan
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

PACKS = ('thesis', 'fs_redflag', 'redflag_soulplan')


def main() -> None:
    parser = argparse.ArgumentParser(description='Crosspromotion orchestrator')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--warm', action='store_true')
    parser.add_argument('--adapt', action='store_true')
    parser.add_argument('--refresh-templates', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--skip-warm', action='store_true')
    parser.add_argument(
        '--pack',
        choices=PACKS + ('all',),
        default='all',
        help='Which pack(s) to run (default: all)',
    )
    args = parser.parse_args()

    enabled = os.getenv('CROSSPROMO_ENABLED', '1').strip().lower()
    if enabled in ('0', 'false', 'no', 'off') and not args.status and not args.warm:
        print('⏸️ CROSSPROMO_ENABLED=0 — skipping crosspromo run')
        return

    import crosspromo_thesis_sender as thesis
    import crosspromo_fs_redflag_sender as fs_rf
    import crosspromo_redflag_soulplan_sender as rf_sp

    run_thesis = args.pack in ('all', 'thesis')
    run_fs = args.pack in ('all', 'fs_redflag')
    run_sp = args.pack in ('all', 'redflag_soulplan')

    if args.status:
        if run_thesis:
            thesis.print_status()
        if run_fs:
            fs_rf.print_status()
        if run_sp:
            rf_sp.print_status()
        return

    if args.warm and run_thesis:
        thesis.warm_templates(adapt=args.adapt, refresh=args.refresh_templates)
        if not args.dry_run and args.limit == 0 and args.pack == 'thesis':
            return

    if run_thesis and not args.skip_warm and not args.warm:
        from thesis_template_translator import _write_cache
        for stage, src in thesis.EN_SOURCES.items():
            _write_cache(f'{thesis.KIND_PREFIX}_{stage}', 'en', src)

    # Budget: when running all packs, thesis uses half of CROSSPROMO_DAILY_CAP
    # via its own env; niche packs use dedicated env caps (default 60).
    if run_thesis:
        print('\n—— Crosspromo Thesis ——')
        thesis_cap = None
        if args.pack == 'all':
            total = int(os.getenv('CROSSPROMO_DAILY_CAP', '240'))
            thesis_cap = max(40, total // 2)
        thesis.run(dry_run=args.dry_run, limit=args.limit, enroll_cap=thesis_cap)

    if run_fs:
        print('\n—— Crosspromo Fresh Start → Red Flag ——')
        fs_rf.run(dry_run=args.dry_run, limit=args.limit)

    if run_sp:
        print('\n—— Crosspromo Red Flag → SoulPlan ——')
        rf_sp.run(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
