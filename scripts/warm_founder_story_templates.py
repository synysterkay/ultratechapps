#!/usr/bin/env python3
"""Translate founder-story English templates to all supported languages."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from predictify_v2.localize_templates import translate_template, TARGET_LANGS

BASE = Path(__file__).parent / 'predictify_v2'


def warm_dir(templates_dir: Path, kinds: list[str], refresh: bool = False) -> int:
    written = 0
    for kind in kinds:
        en_path = templates_dir / f'{kind}_en.json'
        if not en_path.exists():
            print(f'  ⏭️  missing {en_path.name}')
            continue
        with open(en_path, encoding='utf-8') as f:
            en = json.load(f)
        print(f'\n📧 {kind} ({templates_dir.name}/)')
        for lang, name in TARGET_LANGS.items():
            out = templates_dir / f'{kind}_{lang}.json'
            if out.exists() and not refresh:
                continue
            try:
                print(f'   → {lang} ({name})…', flush=True)
                t = translate_template(en, lang, name)
                for extra in ('app_store_url', 'google_play_url', 'cta_ios_text', 'cta_android_text'):
                    if extra in en:
                        t[extra] = en[extra]
                out.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding='utf-8')
                written += 1
                time.sleep(0.35)
            except Exception as e:
                print(f'   ⚠️ {lang} failed: {e}')
    return written


def main() -> None:
    if not os.environ.get('DEEPSEEK_API_KEY', '').strip():
        raise SystemExit('DEEPSEEK_API_KEY missing')

    refresh = '--refresh' in sys.argv
    total = 0
    total += warm_dir(
        BASE / 'templates',
        ['founder_story_soccer', 'founder_story_soccer_v2', 'founder_story_horse', 'founder_story_horse_v2'],
        refresh=refresh,
    )
    total += warm_dir(
        BASE / 'templates_nba',
        ['founder_story_nba', 'founder_story_nba_v2'],
        refresh=refresh,
    )
    total += warm_dir(
        BASE / 'templates_tennis',
        ['founder_story_tennis', 'founder_story_tennis_v2'],
        refresh=refresh,
    )
    print(f'\n✅ Wrote {total} founder-story translation files.')


if __name__ == '__main__':
    main()
