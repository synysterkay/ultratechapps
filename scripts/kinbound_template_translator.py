#!/usr/bin/env python3
"""Kinbound email template translator + cache (mirrors pupshape_template_translator)."""
import json
import os
import requests
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / 'cache' / 'kinbound_templates'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LANG_NAMES = {
    'en': 'English', 'es': 'Spanish', 'pt': 'Portuguese (Brazil)',
    'fr': 'French', 'de': 'German', 'it': 'Italian', 'nl': 'Dutch',
    'ja': 'Japanese', 'ko': 'Korean', 'zh-Hans': 'Simplified Chinese',
    'ar': 'Arabic', 'hi': 'Hindi', 'id': 'Indonesian', 'pl': 'Polish',
    'ru': 'Russian', 'tr': 'Turkish',
}

SUPPORTED = list(LANG_NAMES.keys())


def _cache_path(kind: str, lang: str) -> Path:
    safe = lang.replace('-', '_')
    return CACHE_DIR / f'{kind}_{safe}.json'


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


def _translate_via_deepseek(kind: str, lang: str, en_source: dict) -> dict:
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        raise RuntimeError('DEEPSEEK_API_KEY not set; cannot translate')

    target = LANG_NAMES.get(lang)
    if not target:
        raise ValueError(f'unsupported language {lang!r}')

    system = (
        "You are translating marketing/retention emails for Kinbound — an AI "
        "parenting coach app. The voice is warm, calm, non-judgmental — like "
        "a wise friend who happens to be a parenting coach texting at 9pm. "
        "Never shame the parent. Translate ACCURATELY, preserve meaning, line "
        "breaks, and every {{placeholder}} token VERBATIM. Output STRICT JSON "
        "with the exact same keys as input."
    )

    user = (
        f"Translate from English to {target}. Email kind: {kind}.\n\n"
        f"Input JSON:\n{json.dumps(en_source, ensure_ascii=False, indent=2)}\n\n"
        f"Return JSON of the same shape. Keep {{first_name}}, {{streak}}, "
        f"{{struggle}}, {{child_name}} placeholders verbatim."
    )

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
                {'role': 'user', 'content': user},
            ],
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'DeepSeek HTTP {resp.status_code}: {resp.text[:300]}')

    payload = json.loads(resp.json()['choices'][0]['message']['content'])
    for k, v in en_source.items():
        if k not in payload:
            raise RuntimeError(f'translation missing key {k!r} for {lang}')
    return payload


def get_localized(kind: str, lang: str, en_source: dict, allow_api: bool = True) -> dict:
    if lang == 'en' or lang not in LANG_NAMES:
        return en_source
    cached = _read_cache(kind, lang)
    if cached:
        return cached
    if not allow_api:
        return en_source
    try:
        out = _translate_via_deepseek(kind, lang, en_source)
        _write_cache(kind, lang, out)
        return out
    except Exception as e:
        print(f'   ⚠️ translation {kind}/{lang} failed: {e} — using English')
        return en_source


def warm_all(kind: str, en_source: dict):
    for lang in SUPPORTED:
        if lang == 'en':
            continue
        if _read_cache(kind, lang):
            print(f'   ✓ {kind}/{lang} cached')
            continue
        try:
            out = _translate_via_deepseek(kind, lang, en_source)
            _write_cache(kind, lang, out)
            print(f'   ✅ {kind}/{lang} translated + cached')
        except Exception as e:
            print(f'   ⚠️ {kind}/{lang} failed: {e}')
