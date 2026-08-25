#!/usr/bin/env python3
"""Vowcraft Email Orchestrator — Hooked behavioral emails for vowcraft-e4498."""
import sys
import time
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


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
    print(f'🚀 Vowcraft orchestrator starting (dry_run={dry_run}, only={only or "templates-only"})')
    # Behavioral senders can be added later (quota_hit, abandoned_speech, rehearse).
    # Warm templates are the cache source of truth for welcome + campaigns.
    from vowcraft_templates import warm, TEMPLATES
    if dry_run:
        print(f'   kinds: {", ".join(TEMPLATES.keys())}')
        print('   (no senders wired yet — use --warm to fill cache/vowcraft_templates)')
    else:
        warm()
    print('\n✅ Vowcraft orchestrator done')


if __name__ == '__main__':
    main()
