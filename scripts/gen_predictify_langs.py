#!/usr/bin/env python3
"""
Generate Predictify retention-email templates for the 12 languages added to the
app (bn, el, fa, ko, ro, ru, sv, th, uk, ur, vi, zh).

Cache-gated and resumable: existing templates are skipped, so re-running only
fills gaps. Reads DEEPSEEK_API_KEY from .env (or the environment).

Usage:
  python scripts/gen_predictify_langs.py --test       # one email (bn #1)
  python scripts/gen_predictify_langs.py --lang bn     # all emails for bn
  python scripts/gen_predictify_langs.py               # all 12 langs
"""
import os
import sys
import time
from pathlib import Path

# Load DEEPSEEK_API_KEY from .env if not already in the environment.
ROOT = Path(__file__).parent.parent
env = ROOT / '.env'
if 'DEEPSEEK_API_KEY' not in os.environ and env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line.startswith('DEEPSEEK_API_KEY') and '=' in line:
            os.environ['DEEPSEEK_API_KEY'] = line.split('=', 1)[1].strip().strip('"').strip("'")
            break

sys.path.insert(0, str(ROOT / 'scripts'))
from retention_email_generator import RetentionEmailGenerator, EMAIL_SEQUENCE  # noqa

NEW_LANGS = ['bn', 'el', 'fa', 'ko', 'ro', 'ru', 'sv', 'th', 'uk', 'ur', 'vi', 'zh']
APP = 'Predictify'
N = len(EMAIL_SEQUENCE)

def run(langs):
    gen = RetentionEmailGenerator()
    made = skipped = failed = 0
    for lang in langs:
        for n in range(1, N + 1):
            path = gen._get_cache_path(APP, n, lang)
            if path.exists():
                skipped += 1
                continue
            try:
                email = gen.get_email(APP, n, language=lang)
                if email and email.get('subject'):
                    made += 1
                    print(f"  ✓ {APP} {lang} #{n}: {email['subject'][:50]}")
                else:
                    failed += 1
                    print(f"  ✗ {APP} {lang} #{n}: empty result")
            except Exception as e:
                failed += 1
                print(f"  ✗ {APP} {lang} #{n}: {e}")
            time.sleep(0.4)
    print(f"\nDone. generated={made} skipped(existing)={skipped} failed={failed}  (N={N}/lang)")

if __name__ == '__main__':
    if '--lang' in sys.argv:
        run([sys.argv[sys.argv.index('--lang') + 1]])
    else:
        run(NEW_LANGS)
