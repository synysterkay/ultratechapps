#!/usr/bin/env python3
"""
Thesis Generator Email Orchestrator

Single entry point that runs Thesis-Generator-specific behavioral senders
in priority order. Invoked from `retention-emails.yml`.

As of 2026-07-16 (ZeptoMail / thesisgenerator.io):
- The 30-email drip for Thesis is DISABLED in app_retention_emailer.py.
- Welcome is handled by Supabase check-new-users → welcome-email.
- This orchestrator only runs high-value event triggers (P0 + P1).
- Founder-story, streaks, weekly/monthly recaps, and winback are deferred
  until deliverability on thesisgenerator.io is stable.

Order (highest intent / revenue first):
1. Free-quota-hit upgrade 24h/72h/7d       (monetization) — P0
2. First-thesis-complete                   (activation) — P0
3. Deadline countdown 14/7/3/1/0           (urgency) — P1
4. Trial ending 3d/1d                      (monetization) — P1
5. Abandoned thesis 2d / 5d                (re-engagement) — P0
6. Stuck-on-outline                        (funnel rescue) — P1

Run modes:
    python scripts/thesis_orchestrator.py            # send for real
    python scripts/thesis_orchestrator.py --dry-run  # preview all senders
    python scripts/thesis_orchestrator.py --only stuck_on_outline
    python scripts/thesis_orchestrator.py --warm     # pre-fill translations
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Active senders only (P0 + P1). Deferred: streak_*, winback, weekly_progress,
# cumulative_stats, founder_story, founder_story_2.
SENDERS = [
    ('free_quota_hit',        'free_quota_hit_sender'),
    ('first_thesis_complete', 'first_thesis_complete_sender'),
    ('deadline_countdown',    'deadline_countdown_sender'),
    ('trial_ending',          'trial_ending_sender'),
    ('abandoned_thesis',      'abandoned_thesis_sender'),
    ('stuck_on_outline',      'stuck_on_outline_sender'),
]


def run_one(name, mod, dry_run):
    """Run a single sender's `main()` with the given dry-run flag.
    Catches exceptions so one broken sender doesn't take down the rest."""
    print(f'\n━━━ {name} ━━━')
    try:
        module = __import__(mod)
        import importlib
        module = importlib.reload(module)
        module.main(dry_run=dry_run)
    except Exception as e:
        print(f'   ⚠️ {name} crashed: {e}')


def warm_all_translations():
    """Walk every sender, extract its EN_SOURCE(s), and warm the DeepSeek
    cache for all supported languages."""
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
                if name == 'abandoned_thesis':
                    kind = f'abandoned_thesis_{key}'
                elif name == 'free_quota_hit':
                    kind = f'free_quota_hit_{key}'
                elif name == 'trial_ending':
                    kind = f'trial_ending_{key}'
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
          f"(dry_run={dry_run}, only={only or 'all'}, "
          f"from=hello@thesisgenerator.io)")
    for name, mod in SENDERS:
        if only and only != name:
            continue
        run_one(name, mod, dry_run)
        time.sleep(0.5)
    print('\n🏁 Thesis orchestrator done.')


if __name__ == '__main__':
    main()
