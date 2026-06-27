#!/usr/bin/env python3
"""
Thesis Generator Email Orchestrator

Single entry point that runs every Thesis-Generator-specific sender in
the right order, with shared dedup against the global suppression list.
Designed to be invoked from `retention-emails.yml` so the workflow
doesn't have to know about each individual script.

Order matters. Highest-intent / highest-revenue Thesis senders run first.
1. Free-quota-hit upgrade 24h/72h/7d       (monetization)
2. Welcome / first-thesis-complete         (fresh activation)
3. Deadline countdown 14/7/3/1/0           (urgent external trigger)
4. Trial ending 3d/1d                      (monetization)
5. Abandoned thesis 2d / 5d / 10d          (general re-engagement)
6. Stuck-on-outline                        (funnel recovery)
7. Streak milestone (3/7/14/30/100)        (variable-reward celebration)
8. Streak at risk                          (loss aversion)
9. Winback 7/30/60/90                      (lapsed-subscriber recovery)
10. Weekly progress recap (Sundays only)   (Investment summary)
11. Cumulative stats (1st of month)        (Investment summary, monthly)
12. Founder story #1 (once-ever backfill)  (Origin story)
13. Founder story #2 (5 days after #1)   (Hooked-model activation nudge)

A user might match multiple senders in one run; each sender's local
state-cache prevents double-sends.

Run modes:
    python scripts/thesis_orchestrator.py            # send for real
    python scripts/thesis_orchestrator.py --dry-run  # preview all senders
    python scripts/thesis_orchestrator.py --only stuck_on_outline
    python scripts/thesis_orchestrator.py --warm     # pre-fill translations
"""
import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Sender modules (imported lazily so a broken sender doesn't kill the run).
SENDERS = [
    ('free_quota_hit',        'free_quota_hit_sender'),
    ('first_thesis_complete', 'first_thesis_complete_sender'),
    ('deadline_countdown',    'deadline_countdown_sender'),
    ('trial_ending',          'trial_ending_sender'),
    ('abandoned_thesis',      'abandoned_thesis_sender'),
    ('stuck_on_outline',      'stuck_on_outline_sender'),
    ('streak_milestone',      'streak_milestone_sender'),
    ('streak_at_risk',        'streak_at_risk_sender'),
    ('winback',               'winback_sender'),
    ('weekly_progress',       'weekly_progress_sender'),
    ('cumulative_stats',      'cumulative_stats_sender'),
    ('founder_story',         'founder_story_thesis_sender'),
    ('founder_story_2',       'founder_story_thesis_2_sender'),
]


def run_one(name, mod, dry_run):
    """Run a single sender's `main()` with the given dry-run flag.
    Catches exceptions so one broken sender doesn't take down the rest."""
    print(f'\n━━━ {name} ━━━')
    try:
        module = __import__(mod)
        # Reload so each invocation gets fresh module state when the
        # orchestrator is run in a long-lived process.
        import importlib
        module = importlib.reload(module)
        module.main(dry_run=dry_run)
    except Exception as e:
        print(f'   ⚠️ {name} crashed: {e}')


def warm_all_translations():
    """Walk every sender, extract its EN_SOURCE(s), and warm the DeepSeek
    cache for all 34 languages. Run once after deploying new senders so
    production sends never pay the cold translation latency.

    Each sender exposes its English source either as `EN_SOURCE` (single
    template) or `EN_SOURCES` (dict keyed by stage / milestone / day).
    """
    from thesis_template_translator import warm_all, SUPPORTED

    targets = [(name, mod) for name, mod in SENDERS]
    total_pairs = 0
    for name, mod in targets:
        try:
            module = __import__(mod)
        except Exception as e:
            print(f'⚠️ skipping {name}: {e}')
            continue
        en_sources = getattr(module, 'EN_SOURCES', None)
        en_source = getattr(module, 'EN_SOURCE', None)
        if en_sources:
            for key, src in en_sources.items():
                kind = f'{name}_{key}' if not str(key).startswith(name) else str(key)
                # Some senders prefix the stage name themselves; pick the
                # canonical kind based on what the sender writes.
                if name == 'abandoned_thesis':
                    kind = f'abandoned_thesis_{key}'
                elif name == 'free_quota_hit':
                    kind = f'free_quota_hit_{key}'
                elif name == 'trial_ending':
                    kind = f'trial_ending_{key}'
                elif name == 'winback':
                    kind = f'winback_{key}'
                elif name == 'streak_milestone':
                    kind = f'streak_milestone_{key}'
                elif name == 'deadline_countdown':
                    kind = f'deadline_{key}d'
                print(f'\n--- warming {kind} ({len(SUPPORTED)-1} langs) ---')
                warm_all(kind, src)
                total_pairs += len(SUPPORTED) - 1
        elif en_source:
            kind = name
            print(f'\n--- warming {kind} ({len(SUPPORTED)-1} langs) ---')
            warm_all(kind, en_source)
            total_pairs += len(SUPPORTED) - 1
        else:
            print(f'   ⚠️ {name} has no EN_SOURCE / EN_SOURCES — skipping')
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
    print(f"🚀 Thesis orchestrator starting "
          f"(dry_run={dry_run}, only={only or 'all'})")
    for name, mod in SENDERS:
        if only and only != name:
            continue
        if name == 'founder_story':
            import importlib
            module = importlib.import_module(mod)
            module.main(dry_run=dry_run, daily=True)
        elif name == 'founder_story_2':
            import importlib
            module = importlib.import_module(mod)
            module.main(dry_run=dry_run, daily=True)
        else:
            run_one(name, mod, dry_run)
        time.sleep(0.5)
    print('\n🏁 Thesis orchestrator done.')


if __name__ == '__main__':
    main()
