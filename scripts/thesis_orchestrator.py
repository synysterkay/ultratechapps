#!/usr/bin/env python3
"""
Thesis Generator Email Orchestrator

Single entry point that runs Thesis-Generator-specific behavioral senders
in priority order. Invoked from `retention-emails.yml`.

As of 2026-07-20 (ZeptoMail / thesisgenerator.io):
- The 30-email drip for Thesis is DISABLED in app_retention_emailer.py.
- Welcome is handled by Supabase check-new-users → welcome-email.
- This orchestrator runs high-value event triggers (P0 + P1).
- Founder story v1/v2 runs daily as lapsed catch-up (≥14d inactive, 50/day cap).
- Founder story backfill runs daily for never-emailed users (150 v1 + 100 v2/day).

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

# Active senders (P0/P1 behavioral). Founder story runs as lapsed catch-up after.
SENDERS = [
    ('free_quota_hit',        'free_quota_hit_sender'),
    ('first_thesis_complete', 'first_thesis_complete_sender'),
    ('deadline_countdown',    'deadline_countdown_sender'),
    ('trial_ending',          'trial_ending_sender'),
    ('abandoned_thesis',      'abandoned_thesis_sender'),
    ('stuck_on_outline',      'stuck_on_outline_sender'),
]

FOUNDER_STORY_DAILY_CAP = int(os.environ.get('FOUNDER_STORY_THESIS_DAILY_CAP', '50'))
FOUNDER_STORY_THESIS_BACKFILL_DAILY_CAP = int(
    os.environ.get('FOUNDER_STORY_THESIS_BACKFILL_DAILY_CAP', '150'))
FOUNDER_STORY_THESIS_2_BACKFILL_DAILY_CAP = int(
    os.environ.get('FOUNDER_STORY_THESIS_2_BACKFILL_DAILY_CAP', '100'))


def _thesis_volume_open() -> bool:
    from gmail_sender import GmailSender
    return GmailSender._under_thesis_cap('thesis')


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


def run_founder_story_daily_backfill(dry_run: bool = False) -> None:
    """Chunked backfill for users who never received founder story (no lapsed gate)."""
    print('\n━━━ founder_story backfill (v1, all unsent) ━━━')
    try:
        from founder_story_thesis_sender import run_send as fs1
        fs1(
            dry_run=dry_run,
            send_cap=FOUNDER_STORY_THESIS_BACKFILL_DAILY_CAP,
            lapsed_only=False,
        )
    except Exception as e:
        print(f'   ⚠️ founder_story v1 backfill crashed: {e}')
    print('\n━━━ founder_story_2 backfill (FS1≥7d, unsent FS2) ━━━')
    try:
        from founder_story_thesis_2_sender import run_send as fs2
        fs2(dry_run=dry_run, send_cap=FOUNDER_STORY_THESIS_2_BACKFILL_DAILY_CAP)
    except Exception as e:
        print(f'   ⚠️ founder_story v2 backfill crashed: {e}')


def run_founder_story_catchup(dry_run: bool = False) -> None:
    """Lapsed-only founder story v1 + v2 catch-up (small daily cap)."""
    print('\n━━━ founder_story (lapsed v1) ━━━')
    try:
        from founder_story_thesis_sender import run_send as fs1
        fs1(dry_run=dry_run, send_cap=FOUNDER_STORY_DAILY_CAP, lapsed_only=True)
    except Exception as e:
        print(f'   ⚠️ founder_story v1 crashed: {e}')
    print('\n━━━ founder_story_2 (lapsed v2) ━━━')
    try:
        from founder_story_thesis_2_sender import run_send as fs2
        fs2(dry_run=dry_run, send_cap=FOUNDER_STORY_DAILY_CAP)
    except Exception as e:
        print(f'   ⚠️ founder_story v2 crashed: {e}')


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
        if not only and not _thesis_volume_open():
            print(f'⏭️ Thesis daily volume cap reached — skipping {name} and remaining senders')
            break
        run_one(name, mod, dry_run)
        time.sleep(0.5)
        try:
            from firestore_quota import is_exhausted
            from thesis_users_loader import PROJECT_ID as THESIS_FS
            if not only and is_exhausted(THESIS_FS):
                print(
                    f'⏭️ Thesis Firestore quota exhausted after {name} — '
                    'skipping remaining live senders, founder-story will use snapshot'
                )
                break
        except Exception:
            pass
    if not only:
        if _thesis_volume_open():
            run_founder_story_catchup(dry_run=dry_run)
        else:
            print('⏭️ Skipping founder-story catch-up — Thesis volume cap already hit')
        if _thesis_volume_open():
            run_founder_story_daily_backfill(dry_run=dry_run)
        else:
            print('⏭️ Skipping founder-story backfill — Thesis volume cap already hit')
    print('\n🏁 Thesis orchestrator done.')


if __name__ == '__main__':
    main()
