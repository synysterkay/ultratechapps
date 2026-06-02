#!/usr/bin/env python3
"""
PupShape Email Orchestrator

Single entry point that runs every PupShape-specific sender in the
right order. Designed to be invoked from `.github/workflows/retention-
emails.yml` so the workflow doesn't have to know about each individual
script.

Order matters — celebratory + emotionally-peak senders first, then
re-engagement, then monetization:

1. first_weigh_in_celebration       (variable reward — engine can adapt)
2. milestone_crossed                 (variable reward — peak emotional moment)
3. progress_card_share_nudge         (24h follow-up if milestone share skipped)
4. streak_milestone                  (variable reward — externalized celebration)
5. weekly_recap                      (investment — every Sunday)
6. streak_at_risk                    (loss aversion — internal trigger)
7. plateau_detected                  (trust — engine is doing real work)
8. body_check_reminder               (external trigger — Path BCS re-engagement)
9. abandoned_app                     (external trigger — funnel rescue)
10. at_goal_celebration              (variable reward — once per dog)
11. invite_friend_reminder           (tribe — compounds social capital)
12. winback                          (monetization — lapsed sub recovery)

A user might match multiple senders in one run; each sender's local
state-cache prevents double-sends.

Run modes:
    python scripts/pupshape_orchestrator.py            # send for real
    python scripts/pupshape_orchestrator.py --dry-run  # preview
    python scripts/pupshape_orchestrator.py --only milestone_crossed
    python scripts/pupshape_orchestrator.py --warm     # pre-fill translations
"""
import os
import sys
import time
import importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# (display_name, module_name) — modules imported lazily so a broken
# sender can't take down the rest of the orchestrator run.
SENDERS = [
    ('first_weigh_in_celebration',  'first_weigh_in_celebration_sender'),
    ('milestone_crossed',           'milestone_crossed_sender'),
    ('progress_card_share_nudge',   'progress_card_share_nudge_sender'),
    ('streak_milestone',            'pupshape_streak_milestone_sender'),
    ('weekly_recap',                'weekly_recap_sender'),
    ('streak_at_risk',              'pupshape_streak_at_risk_sender'),
    ('plateau_detected',            'plateau_detected_sender'),
    ('body_check_reminder',         'body_check_reminder_sender'),
    ('abandoned_app',               'abandoned_app_sender'),
    ('at_goal_celebration',         'at_goal_celebration_sender'),
    ('invite_friend_reminder',      'invite_friend_reminder_sender'),
    ('winback',                     'pupshape_winback_sender'),
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
    """Walk every sender, extract its EN_SOURCE(s), warm the DeepSeek
    cache for all non-English supported languages."""
    from pupshape_template_translator import warm_all, SUPPORTED

    total_pairs = 0
    for name, mod_name in SENDERS:
        try:
            module = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            print(f'⏭  skip {name} (not implemented)')
            continue
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
    print(f"🚀 PupShape orchestrator starting "
          f"(dry_run={dry_run}, only={only or 'all'})")
    for name, mod_name in SENDERS:
        if only and only != name:
            continue
        run_one(name, mod_name, dry_run)
        time.sleep(0.5)
    print('\n🏁 PupShape orchestrator done.')


if __name__ == '__main__':
    main()
