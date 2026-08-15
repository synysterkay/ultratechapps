#!/usr/bin/env python3
"""
Thesis-Generator email template translator + cache.

Each sender (existing or new) declares its English source as a dict:

    EN_SOURCE = {
        'subject':  'Don\'t lose your {{streak}}, {{first_name}}',
        'body':     ["You're on a {{streak}} 🔥 — and you're one inactive day away from losing it.",
                     "Two minutes in the app keeps it alive. ..."],
        'cta':      'Keep my streak alive',
    }

To get the version for a user's language, call:

    tpl = get_localized('streak_at_risk', 'pt', EN_SOURCE)

The helper:
- Returns `EN_SOURCE` unchanged for lang == 'en'.
- Reads `cache/thesis_templates/{kind}_{lang}.json` if it exists (warm path).
- If missing, calls DeepSeek to translate, caches the result, and returns it.
- All {{placeholder}} tokens are preserved verbatim by the translation prompt.
- A precomputed bundle (run once via `python scripts/thesis_template_translator.py
  --warm <kind>` or via the batch warmer) avoids any cold API latency at send time.

Why this layer instead of inline 20-lang dicts in each sender:
- A new sender only writes English. The other 19 languages are derived.
- Centralized cache lives in git (under cache/thesis_templates/) so reviewers
  can vet the translations before they fire.
- Senders stay short and readable.
"""
import json
import os
import sys
import time
import requests
from pathlib import Path


CACHE_DIR = Path(__file__).parent.parent / 'cache' / 'thesis_templates'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


LANG_NAMES = {
    'en': 'English',     'es': 'Spanish',      'fr': 'French',
    'ar': 'Arabic',      'zh': 'Simplified Chinese', 'hi': 'Hindi',
    'de': 'German',      'pt': 'Portuguese (Brazil)', 'it': 'Italian',
    'ru': 'Russian',     'ja': 'Japanese',     'ko': 'Korean',
    'tr': 'Turkish',     'nl': 'Dutch',        'pl': 'Polish',
    'sv': 'Swedish',     'ro': 'Romanian',     'id': 'Indonesian',
    'th': 'Thai',        'vi': 'Vietnamese',
}

SUPPORTED = list(LANG_NAMES.keys())


def _cache_path(kind: str, lang: str) -> Path:
    return CACHE_DIR / f'{kind}_{lang}.json'


def _read_cache(kind: str, lang: str):
    p = _cache_path(kind, lang)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def _write_cache(kind: str, lang: str, payload: dict):
    p = _cache_path(kind, lang)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _deepseek_prompts(kind: str, lang: str, en_source: dict, mode: str = 'translate'):
    """Build system/user prompts + temperature for translate vs market-adapt."""
    target = LANG_NAMES.get(lang)
    if not target:
        raise ValueError(f'unsupported language {lang!r}')

    if mode == 'adapt':
        system = (
            "You are a senior email marketer localizing cross-promotion emails "
            "for Thesis Generator (AI thesis/essay writing app). Rewrite the "
            "English copy as NATIVE marketing for the target market — not a "
            "word-by-word translation. Keep dopamine, curiosity, and urgency "
            "intent; you may restructure sentences and subjects for local "
            "clickbait norms. Preserve every {{placeholder}} token VERBATIM "
            "(do not translate placeholder names). Keep emoji. Output STRICT "
            "JSON with the exact same keys as the input. No commentary."
        )
        user = (
            f"Adapt this email for {target}-speaking users (market rewrite). "
            f"Email kind: {kind}.\n\n"
            f"Input JSON:\n{json.dumps(en_source, ensure_ascii=False, indent=2)}\n\n"
            f"Return JSON of the same shape, rewritten for {target}. "
            f"For Arabic use natural MSA; for Portuguese use Brazilian; "
            f"for Chinese use Simplified Chinese."
        )
        temperature = 0.55
    else:
        system = (
            "You are translating marketing/retention emails for a thesis-writing "
            "iOS app called Thesis Generator. The tone is warm, second-person, "
            "and slightly informal — like a friendly mentor texting a student. "
            "Translate ACCURATELY, preserving meaning, line breaks, and every "
            "{{placeholder}} token VERBATIM (do not translate placeholder names, "
            "do not add spaces inside the {{ }}). Keep emoji as-is. Output STRICT "
            "JSON with the exact same keys as the input. Do not add commentary."
        )
        user = (
            f"Translate the following email content from English to {target}. "
            f"Email kind: {kind}.\n\n"
            f"Input JSON:\n{json.dumps(en_source, ensure_ascii=False, indent=2)}\n\n"
            f"Return JSON of the same shape, with strings translated to {target}. "
            f"For Arabic, use natural Modern Standard Arabic. For Portuguese, "
            f"use Brazilian Portuguese. For Chinese, use Simplified Chinese."
        )
        temperature = 0.2
    return system, user, temperature


def _translate_via_deepseek(kind: str, lang: str, en_source: dict, mode: str = 'translate') -> dict:
    """Single DeepSeek call that translates or adapts subject + body + cta.

    mode='translate' — accurate translation (default for lifecycle mail).
    mode='adapt' — full-content market rewrite for crosspromo localization.

    Returns a dict with the same shape as `en_source`. Raises on failure so
    callers can fall back to the English source rather than send broken text.
    """
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        raise RuntimeError('DEEPSEEK_API_KEY not set; cannot translate')

    system, user, temperature = _deepseek_prompts(kind, lang, en_source, mode=mode)

    resp = requests.post(
        'https://api.deepseek.com/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': user},
            ],
            'temperature': temperature,
            'response_format': {'type': 'json_object'},
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'DeepSeek HTTP {resp.status_code}: {resp.text[:300]}')

    content = resp.json()['choices'][0]['message']['content']
    payload = json.loads(content)

    # Sanity: every key from en_source must be present in the response,
    # and lists must remain lists of the same length.
    for k, v in en_source.items():
        if k not in payload:
            raise RuntimeError(f'translation missing key {k!r} for {lang}')
        if isinstance(v, list) and not isinstance(payload[k], list):
            raise RuntimeError(f'translation key {k!r} must remain a list for {lang}')
        if isinstance(v, list) and len(payload[k]) != len(v):
            # Pad or truncate rather than crash — better to ship slightly
            # off-shape than fall back to English.
            if len(payload[k]) < len(v):
                payload[k] = payload[k] + v[len(payload[k]):]
            else:
                payload[k] = payload[k][:len(v)]
    return payload


def get_localized(kind: str, lang: str, en_source: dict, allow_api: bool = True) -> dict:
    """Return the localized template for `lang`, generating + caching it on
    first use. Falls back to English if translation fails or `allow_api` is
    false and there's no cache entry.
    """
    if lang == 'en' or lang not in SUPPORTED:
        return en_source
    cached = _read_cache(kind, lang)
    if cached is not None:
        return cached
    if not allow_api:
        return en_source
    try:
        payload = _translate_via_deepseek(kind, lang, en_source)
        _write_cache(kind, lang, payload)
        return payload
    except Exception as e:
        print(f'   ⚠️ DeepSeek translation failed for {kind}/{lang}: {e}')
        return en_source


def warm_all(kind: str, en_source: dict, languages=None, mode: str = 'translate',
             refresh: bool = False):
    """Pre-fill the cache for every supported language. Use this once before
    rolling out a new sender so production traffic never pays for a cold
    translation. Returns dict of {lang: 'cached' | 'translated' | 'failed'}.

    mode='adapt' uses market-rewrite prompts (crosspromo full-content localization).
    refresh=True overwrites existing cache entries.
    """
    result = {}
    targets = languages or [l for l in SUPPORTED if l != 'en']
    for lang in targets:
        if not refresh and _read_cache(kind, lang) is not None:
            result[lang] = 'cached'
            continue
        try:
            payload = _translate_via_deepseek(kind, lang, en_source, mode=mode)
            _write_cache(kind, lang, payload)
            result[lang] = 'adapted' if mode == 'adapt' else 'translated'
            print(f'   ✅ {kind}/{lang}: {result[lang]}')
            # Gentle pacing — DeepSeek tolerates burst but be polite.
            time.sleep(0.4)
        except Exception as e:
            result[lang] = f'failed: {e}'
            print(f'   ❌ {kind}/{lang}: {e}')
    return result


if __name__ == '__main__':
    # CLI: python thesis_template_translator.py --warm <kind> [<lang> ...]
    # The English source is read from stdin as JSON. Useful for ad-hoc warms.
    if '--warm' in sys.argv:
        idx = sys.argv.index('--warm')
        kind = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        if not kind:
            print('usage: thesis_template_translator.py --warm <kind> [<lang>...] < source.json')
            sys.exit(1)
        langs = sys.argv[idx + 2:] or None
        src = json.loads(sys.stdin.read())
        warm_all(kind, src, languages=langs)
        sys.exit(0)
    print('Usage:')
    print('  echo \'{"subject":"...","body":["..."],"cta":"..."}\' | \\')
    print('      python thesis_template_translator.py --warm <kind>')
