#!/usr/bin/env python3
"""
World Cup 2026 founder-story email for Predictify Soccer.

Integrated into predictify_v2.orchestrator — fires automatically as a
once-ever fallback when no behavioral trigger matches (daily retention
runs). Use this script for manual backfill / dry-run / template warming.

Usage:
  python3 scripts/founder_story_wc2026_sender.py --dry-run
  python3 scripts/founder_story_wc2026_sender.py --warm
  python3 scripts/founder_story_wc2026_sender.py
  python3 scripts/founder_story_wc2026_sender.py --passes 10
  python3 scripts/founder_story_wc2026_sender.py --non-subscribers-only --passes 10
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

KIND = 'founder_story_wc2026'
TEMPLATES_DIR = Path(__file__).parent / 'predictify_v2' / 'templates'

TARGET_LANGS = {
    'ar': 'Arabic', 'de': 'German', 'es': 'Spanish', 'fr': 'French',
    'hi': 'Hindi', 'id': 'Indonesian', 'it': 'Italian', 'ja': 'Japanese',
    'nl': 'Dutch', 'pl': 'Polish', 'pp': 'Brazilian Portuguese',
    'pt': 'Portuguese', 'tr': 'Turkish',
    'bn': 'Bengali', 'el': 'Greek', 'fa': 'Persian', 'ko': 'Korean',
    'ro': 'Romanian', 'ru': 'Russian', 'sv': 'Swedish', 'th': 'Thai',
    'uk': 'Ukrainian', 'ur': 'Urdu', 'vi': 'Vietnamese', 'zh': 'Simplified Chinese',
}


def warm_templates(refresh: bool = False) -> None:
    """Generate per-language JSON from founder_story_wc2026_en.json."""
    from predictify_v2.localize_templates import translate_template

    en_path = TEMPLATES_DIR / f'{KIND}_en.json'
    if not en_path.exists():
        raise SystemExit(f'Missing {en_path}')
    if not os.environ.get('DEEPSEEK_API_KEY', '').strip():
        raise SystemExit('DEEPSEEK_API_KEY not set')

    with open(en_path, encoding='utf-8') as f:
        en = json.load(f)

    if refresh:
        removed = 0
        for path in TEMPLATES_DIR.glob(f'{KIND}_*.json'):
            if path.name.endswith('_en.json'):
                continue
            path.unlink(missing_ok=True)
            removed += 1
        if removed:
            print(f'   🔄 Cleared {removed} cached {KIND} translations for refresh')

    print(f'🔥 Warming {KIND} templates…')
    for lang, name in TARGET_LANGS.items():
        out = TEMPLATES_DIR / f'{KIND}_{lang}.json'
        if out.exists() and not refresh:
            print(f'  ↪ {out.name} exists')
            continue
        print(f'  → {lang} ({name})…', flush=True)
        try:
            t = translate_template(en, lang, name)
            out.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding='utf-8')
            time.sleep(0.4)
        except Exception as e:
            print(f'    ⚠️ failed: {e}')


def main(
    dry_run: bool = False,
    warm_only: bool = False,
    passes: int = 1,
    refresh_templates: bool = False,
    non_subscribers_only: bool = False,
) -> None:
    if warm_only:
        warm_templates(refresh=refresh_templates)
        return

    if non_subscribers_only:
        from predictify_v2.orchestrator import run_founder_story_non_subscriber_resend
        run_fn = run_founder_story_non_subscriber_resend
    else:
        from predictify_v2.orchestrator import run_founder_story_backfill
        run_fn = run_founder_story_backfill

    passes = int(os.environ.get('FOUNDER_STORY_PASSES', passes))
    total = 0
    for n in range(1, passes + 1):
        if passes > 1:
            label = 'non-subscriber resend' if non_subscribers_only else 'backfill'
            print(f'\n=== Founder story {label} pass {n}/{passes} ===')
        sent = run_fn(dry_run=dry_run)
        batch = len(sent)
        total += batch
        if dry_run:
            break
        if batch == 0:
            print('No more eligible users — stopping early')
            break
        per_pass_cap = int(os.environ.get('FOUNDER_STORY_SEND_CAP', '2000'))
        if not dry_run and batch < per_pass_cap:
            print(f'Partial pass ({batch}/{per_pass_cap}) — backlog exhausted')
            break
    if passes > 1 and not dry_run:
        print(f'\n📬 Total sent across passes: {total}')


if __name__ == '__main__':
    passes = 1
    for i, arg in enumerate(sys.argv):
        if arg == '--passes' and i + 1 < len(sys.argv):
            passes = int(sys.argv[i + 1])
    main(
        dry_run='--dry-run' in sys.argv,
        warm_only='--warm' in sys.argv,
        passes=passes,
        refresh_templates='--refresh-templates' in sys.argv,
        non_subscribers_only='--non-subscribers-only' in sys.argv,
    )
