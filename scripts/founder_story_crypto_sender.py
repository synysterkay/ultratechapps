#!/usr/bin/env python3
"""
Predictify Crypto founder-story helpers.

Templates live in scripts/predictify_crypto/templates/.
Full lapsed orchestration should follow predictify_v2 once the crypto
Firestore activity loader exists — until then use --print-template to review copy.

Usage:
  python3 scripts/founder_story_crypto_sender.py --print-template
  python3 scripts/founder_story_crypto_sender.py --print-template --v2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / 'predictify_crypto' / 'templates'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--print-template', action='store_true')
    parser.add_argument('--v2', action='store_true')
    args = parser.parse_args()

    kind = 'founder_story_crypto_v2' if args.v2 else 'founder_story_crypto'
    path = TEMPLATES / f'{kind}_en.json'
    if not path.exists():
        raise SystemExit(f'Missing {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if args.print_template:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print(
        f'Template ready: {path.name}\n'
        'Wire Zepto send via marketing-tool orchestrator when crypto user '
        'activity snapshots are available (see PREDICTIFY_CRYPTO_EMAILS_PLAN.md).'
    )


if __name__ == '__main__':
    main()
