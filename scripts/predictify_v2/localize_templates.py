"""
localize_templates.py — One-shot generator that translates each English
template to every supported language via DeepSeek. Run once when templates
change. Preserves merge-field placeholders ({first_name}, etc) verbatim.

Usage:
  DEEPSEEK_API_KEY=sk-... python scripts/predictify_v2/localize_templates.py
"""
import os
import json
import time
from pathlib import Path

import requests


# Which template folder to localize. Defaults to the soccer `templates/` dir;
# set PREDICTIFY_TEMPLATES_DIR=templates_nba to localize the NBA templates.
TEMPLATES_DIR = Path(__file__).parent / os.environ.get(
    'PREDICTIFY_TEMPLATES_DIR', 'templates')
TARGET_LANGS = {
    'ar': 'Arabic',
    'de': 'German',
    'es': 'Spanish',
    'fr': 'French',
    'hi': 'Hindi',
    'id': 'Indonesian',
    'it': 'Italian',
    'ja': 'Japanese',
    'nl': 'Dutch',
    'pl': 'Polish',
    'pp': 'Brazilian Portuguese',
    'pt': 'Portuguese',
    'tr': 'Turkish',
    'bn': 'Bengali',
    'el': 'Greek',
    'fa': 'Persian',
    'ko': 'Korean',
    'ro': 'Romanian',
    'ru': 'Russian',
    'sv': 'Swedish',
    'th': 'Thai',
    'uk': 'Ukrainian',
    'ur': 'Urdu',
    'vi': 'Vietnamese',
    'zh': 'Simplified Chinese',
}

DEEPSEEK_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
if not DEEPSEEK_KEY:
    raise SystemExit('DEEPSEEK_API_KEY missing')

API = 'https://api.deepseek.com/v1/chat/completions'
HEADERS = {
    'Authorization': f'Bearer {DEEPSEEK_KEY}',
    'Content-Type': 'application/json',
}


def translate_template(en_template: dict, target_lang: str, target_name: str) -> dict:
    prompt = f"""Translate this English email template to {target_name}.

CRITICAL RULES:
1. Preserve every {{placeholder}} EXACTLY — do not translate them.
   Examples of placeholders to keep verbatim: {{first_name}}, {{home_team}},
   {{away_team}}, {{league_name}}, {{pick_label}}, {{confidence_pct}},
   {{tier_label}}, {{hours_to_kickoff}}, {{streak_days}}, {{hours_to_break}},
   {{top_match_line}}, {{recent_correct}}, {{recent_total}}, {{recent_accuracy_pct}},
   {{accuracy_pct}}, {{community_name}}, {{community_id}}, {{member_count}},
   {{member_plural}}, {{owner_name}}, {{recommended_community_name}},
   {{league_short}}, {{fixture_id}}.
2. Match the casual, direct tone — these are retention emails, not formal letters.
3. Keep emojis if present.
4. Return ONLY a JSON object with these exact keys:
   subject, preview_text, body_paragraphs (array), cta_text, cta_deeplink

INPUT (English):
{json.dumps({k: en_template[k] for k in ('subject','preview_text','body_paragraphs','cta_text','cta_deeplink')}, ensure_ascii=False, indent=2)}

OUTPUT (raw JSON, no markdown fences):"""

    body = {
        'model': 'deepseek-chat',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
        'max_tokens': 1200,
    }
    r = requests.post(API, headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    raw = r.json()['choices'][0]['message']['content'].strip()
    if raw.startswith('```'):
        raw = raw.split('```', 2)[1]
        if raw.startswith('json'):
            raw = raw[4:]
        raw = raw.strip().rstrip('`').strip()
    parsed = json.loads(raw)
    parsed['kind'] = en_template['kind']
    parsed['language'] = target_lang
    parsed.setdefault('cta_deeplink', en_template.get('cta_deeplink', 'predictify://'))
    return parsed


def main():
    en_files = sorted(TEMPLATES_DIR.glob('*_en.json'))
    print(f'Found {len(en_files)} English templates to localize')
    total_written = 0
    for en_path in en_files:
        kind = en_path.stem.rsplit('_', 1)[0]
        with open(en_path) as f:
            en = json.load(f)
        for lang, name in TARGET_LANGS.items():
            out_path = TEMPLATES_DIR / f'{kind}_{lang}.json'
            if out_path.exists():
                print(f'  ↪ {kind}_{lang}.json exists, skipping')
                continue
            try:
                print(f'  → translating {kind} → {lang} ({name}) …', flush=True)
                t = translate_template(en, lang, name)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(t, f, ensure_ascii=False, indent=2)
                total_written += 1
                time.sleep(0.4)  # be gentle on the API
            except Exception as e:
                print(f'    ⚠️ {kind}/{lang} failed: {e}')
    print(f'Done. Wrote {total_written} files.')


if __name__ == '__main__':
    main()
