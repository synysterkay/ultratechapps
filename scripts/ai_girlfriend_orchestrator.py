#!/usr/bin/env python3
"""AI Girlfriend orchestrator — founder (kaynel.solutions)."""
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SENDERS = [
    ('founder', 'ai_girlfriend_founder_story_sender'),
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
    print(f'🚀 AI Girlfriend orchestrator (dry_run={dry_run})')
    for name, mod in SENDERS:
        run_one(name, mod, dry_run)
        time.sleep(0.3)
    print('\n✅ AI Girlfriend orchestrator done')


if __name__ == '__main__':
    main()
