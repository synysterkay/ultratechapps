#!/usr/bin/env python3
"""Vowcraft Email Orchestrator — Hooked behavioral emails for vowcraft-e4498."""
import sys
import time
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SENDERS = [
    ('quota_hit', 'vowcraft_quota_hit_sender'),
    ('speech_ready', 'vowcraft_speech_ready_sender'),
    ('abandoned_speech', 'vowcraft_abandoned_speech_sender'),
    ('rehearse', 'vowcraft_rehearse_sender'),
]


def run_one(name: str, mod_name: str, dry_run: bool):
    print(f'\n━━━ {name} ━━━')
    try:
        module = importlib.import_module(mod_name)
        module = importlib.reload(module)
        module.main(dry_run=dry_run)
    except ModuleNotFoundError:
        print(f'   ⏭  {name} not implemented yet — skipping')
    except Exception as e:
        print(f'   ⚠️ {name} crashed: {e}')


def main():
    dry_run = '--dry-run' in sys.argv
    if '--warm' in sys.argv:
        from vowcraft_templates import warm
        warm()
        return
    only = None
    if '--only' in sys.argv:
        idx = sys.argv.index('--only')
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1]
    print(f'🚀 Vowcraft orchestrator starting (dry_run={dry_run}, only={only or "all"})')
    for name, mod_name in SENDERS:
        if only and only != name:
            continue
        run_one(name, mod_name, dry_run)
        time.sleep(0.5)
    print('\n✅ Vowcraft orchestrator done')


if __name__ == '__main__':
    main()
