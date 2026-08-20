#!/usr/bin/env python3
"""ONG Email Orchestrator — Hooked behavioral senders for sealed-cce0a."""
import sys
import time
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SENDERS = [
    ('waiting_on_you',   'ong_waiting_on_you_sender'),
    ('reveal_live',      'ong_reveal_live_sender'),
    ('first_lock',       'ong_first_lock_sender'),
    ('streak_at_risk',   'ong_streak_at_risk_sender'),
    ('streak_milestone', 'ong_streak_milestone_sender'),
    ('abandoned_app',    'ong_abandoned_app_sender'),
    ('weekly_recap',     'ong_weekly_recap_sender'),
    ('pro_gate',         'ong_pro_gate_sender'),
    ('founder_story',    'ong_founder_story_sender'),
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
        from ong_templates import warm
        warm()
        return
    only = None
    if '--only' in sys.argv:
        idx = sys.argv.index('--only')
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1]
    print(f'🚀 ONG orchestrator starting (dry_run={dry_run}, only={only or "all"})')
    for name, mod_name in SENDERS:
        if only and only != name:
            continue
        run_one(name, mod_name, dry_run)
        time.sleep(0.5)
    print('\n✅ ONG orchestrator done')


if __name__ == '__main__':
    main()
