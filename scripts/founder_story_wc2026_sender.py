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
  python3 scripts/founder_story_wc2026_sender.py --passes 8
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


def warm_templates() -> None:
    """Generate missing per-language JSON from founder_story_wc2026_en.json."""
    from predictify_v2.localize_templates import translate_template

    en_path = TEMPLATES_DIR / f'{KIND}_en.json'
    if not en_path.exists():
        raise SystemExit(f'Missing {en_path}')
    if not os.environ.get('DEEPSEEK_API_KEY', '').strip():
        raise SystemExit('DEEPSEEK_API_KEY not set')

    with open(en_path, encoding='utf-8') as f:
        en = json.load(f)

    print(f'🔥 Warming {KIND} templates…')
    for lang, name in TARGET_LANGS.items():
        out = TEMPLATES_DIR / f'{KIND}_{lang}.json'
        if out.exists():
            print(f'  ↪ {out.name} exists')
            continue
        print(f'  → {lang} ({name})…', flush=True)
        try:
            t = translate_template(en, lang, name)
            out.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding='utf-8')
            time.sleep(0.4)
        except Exception as e:
            print(f'    ⚠️ failed: {e}')


def main(dry_run: bool = False, warm_only: bool = False, passes: int = 1) -> None:
    if warm_only:
        warm_templates()
        return

    from predictify_v2.orchestrator import run_founder_story_backfill

    passes = int(os.environ.get('FOUNDER_STORY_PASSES', passes))
    total = 0
    for n in range(1, passes + 1):
        if passes > 1:
            print(f'\n=== Founder story backfill pass {n}/{passes} ===')
        sent = run_founder_story_backfill(dry_run=dry_run)
        batch = len(sent)
        total += batch
        if dry_run:
            break
        if batch == 0:
            print('No more eligible users — stopping early')
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
    )
