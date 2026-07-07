#!/usr/bin/env python3
"""Kinbound Email Orchestrator — batch retention senders for parents-ai-e49a8."""
import os
import sys
import time
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SENDERS = [
    ('struggle_rescue',   'kinbound_struggle_rescue_sender'),
    ('streak_milestone',  'kinbound_streak_milestone_sender'),
    ('streak_at_risk',    'kinbound_streak_at_risk_sender'),
    ('abandoned_app',     'kinbound_abandoned_app_sender'),
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


def warm_all_translations():
    from kinbound_template_translator import warm_all, SUPPORTED
    total_pairs = 0
    for name, mod_name in SENDERS:
        try:
            module = importlib.import_module(mod_name)
        except Exception as e:
            print(f'⚠️ skip {name}: {e}')
            continue
        en_source = getattr(module, 'EN_SOURCE', None)
        en_sources = getattr(module, 'EN_SOURCES', None)
        kind = getattr(module, 'KIND', name)
        if en_sources:
            for sub_key, src in en_sources.items():
                sub_kind = f'{kind}_{sub_key}'
                print(f'\n--- warming {sub_kind} ({len(SUPPORTED)-1} langs) ---')
                warm_all(sub_kind, src)
                total_pairs += len(SUPPORTED) - 1
        elif en_source:
            print(f'\n--- warming {kind} ({len(SUPPORTED)-1} langs) ---')
            warm_all(kind, en_source)
            total_pairs += len(SUPPORTED) - 1
    print(f'\n✅ Warm complete. {total_pairs} (kind, lang) pairs verified.')


def main():
    dry_run = '--dry-run' in sys.argv
    if '--warm' in sys.argv:
        warm_all_translations()
        return
    only = None
    if '--only' in sys.argv:
        idx = sys.argv.index('--only')
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1]
    print(f'🚀 Kinbound orchestrator starting (dry_run={dry_run}, only={only or "all"})')
    for name, mod_name in SENDERS:
        if only and only != name:
            continue
        run_one(name, mod_name, dry_run)
        time.sleep(0.5)
    print('\n✅ Kinbound orchestrator done')


if __name__ == '__main__':
    main()
