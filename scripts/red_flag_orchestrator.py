#!/usr/bin/env python3
"""Red Flag Scanner orchestrator — tips + founder (breakuprelief / Agent 2)."""
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SENDERS = [
    ('tip', 'red_flag_tip_sender'),
    ('founder', 'red_flag_founder_story_sender'),
]


def run_one(name, mod_name, dry_run):
    print(f'\n━━━ {name} ━━━')
    try:
        module = importlib.import_module(mod_name)
        module = importlib.reload(module)
        module.main(dry_run=dry_run)
    except Exception as e:
        print(f'   ⚠️ {name} crashed: {e}')


def main():
    dry_run = '--dry-run' in sys.argv
    only = None
    if '--only' in sys.argv:
        idx = sys.argv.index('--only')
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1]
    print(f'🚀 Red Flag orchestrator (dry_run={dry_run})')
    for name, mod in SENDERS:
        if only and only != name:
            continue
        run_one(name, mod, dry_run)
        time.sleep(0.3)
    print('\n✅ Red Flag orchestrator done')


if __name__ == '__main__':
    main()
