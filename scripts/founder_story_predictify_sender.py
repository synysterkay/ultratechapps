#!/usr/bin/env python3
"""
Predictify founder-story sender — Soccer (default), NBA, Tennis, or Horse via env profile.

Replaces the World Cup 2026 one-off. Uses evergreen founder_story_{app} templates
and predictify_v2 orchestrator lapsed fallback / backfill modes.

Usage:
  python3 scripts/founder_story_predictify_sender.py --dry-run
  python3 scripts/founder_story_predictify_sender.py --backfill --passes 10
  python3 scripts/founder_story_predictify_sender.py --v2 --non-subscribers-only
  PREDICTIFY_APP_NAME='Predictify: NBA AI' python3 scripts/founder_story_predictify_sender.py --backfill
  PREDICTIFY_APP_NAME='Predictify: Tennis AI' PREDICTIFY_TEMPLATES_DIR=templates_tennis python3 scripts/founder_story_predictify_sender.py --backfill
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

TEMPLATES_DIR = Path(__file__).parent / 'predictify_v2' / 'templates'

TARGET_LANGS = {
    'ar': 'Arabic', 'de': 'German', 'es': 'Spanish', 'fr': 'French',
    'hi': 'Hindi', 'id': 'Indonesian', 'it': 'Italian', 'ja': 'Japanese',
    'nl': 'Dutch', 'pl': 'Polish', 'pp': 'Brazilian Portuguese',
    'pt': 'Portuguese', 'tr': 'Turkish',
}


def _founder_v1_kind() -> str:
    from predictify_v2.template_engine import founder_story_kinds_for_app
    return founder_story_kinds_for_app()[0]


def warm_templates(refresh: bool = False) -> None:
    from predictify_v2.localize_templates import translate_template

    kind = _founder_v1_kind()
    en_path = TEMPLATES_DIR / f'{kind}_en.json'
    if not en_path.exists():
        raise SystemExit(f'Missing {en_path}')
    if not os.environ.get('DEEPSEEK_API_KEY', '').strip():
        raise SystemExit('DEEPSEEK_API_KEY not set')

    with open(en_path, encoding='utf-8') as f:
        import json
        en = json.load(f)

    if refresh:
        removed = 0
        for path in TEMPLATES_DIR.glob(f'{kind}_*.json'):
            if path.name.endswith('_en.json'):
                continue
            path.unlink(missing_ok=True)
            removed += 1
        if removed:
            print(f'   🔄 Cleared {removed} cached {kind} translations')

    print(f'🔥 Warming {kind} templates…')
    for lang, name in TARGET_LANGS.items():
        out = TEMPLATES_DIR / f'{kind}_{lang}.json'
        if out.exists() and not refresh:
            print(f'  ↪ {out.name} exists')
            continue
        print(f'  → {lang} ({name})…', flush=True)
        try:
            t = translate_template(en, lang, name)
            out.write_text(__import__('json').dumps(t, ensure_ascii=False, indent=2), encoding='utf-8')
            __import__('time').sleep(0.4)
        except Exception as e:
            print(f'    ⚠️ failed: {e}')


def main() -> None:
    dry_run = '--dry-run' in sys.argv
    if '--warm' in sys.argv:
        warm_templates(refresh='--refresh-templates' in sys.argv)
        return

    passes = 1
    for i, arg in enumerate(sys.argv):
        if arg == '--passes' and i + 1 < len(sys.argv):
            passes = int(sys.argv[i + 1])

    if '--v2' in sys.argv or '--non-subscribers-only' in sys.argv:
        from predictify_v2.orchestrator import run_founder_story_non_subscriber_resend
        run_fn = run_founder_story_non_subscriber_resend
        label = 'founder story v2'
    else:
        from predictify_v2.orchestrator import run_founder_story_backfill
        run_fn = run_founder_story_backfill
        label = 'founder story v1 backfill'

    total = 0
    for n in range(1, passes + 1):
        if passes > 1:
            print(f'\n=== {label} pass {n}/{passes} ===')
        sent = run_fn(dry_run=dry_run)
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
    main()
