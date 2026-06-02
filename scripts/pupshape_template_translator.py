#!/usr/bin/env python3
"""
PupShape email template translator + cache.

Each sender declares its English source as a dict:

    EN_SOURCE = {
        'subject':  'Sir hit halfway, {{first_name}} 🎉',
        'body':     ["Sir's halfway to {{target_weight}} kg. ..."],
        'cta':      'See the recap',
    }

To get the version for a user's language, call:

    tpl = get_localized('milestone_crossed_m50', 'pt', EN_SOURCE)

The helper:
- Returns `EN_SOURCE` unchanged for lang == 'en'.
- Reads `cache/pupshape_templates/{kind}_{lang}.json` if it exists.
- If missing, calls DeepSeek to translate, caches the result, returns
  it.
- All {{placeholder}} tokens are preserved verbatim by the prompt.
- A precomputed bundle (run once via `python scripts/pupshape_orchestrator.py
  --warm`) avoids cold API latency at send time.

Mirrors the thesis_template_translator structure exactly so the team
can copy patterns between apps. PupShape's supported language set is
narrower (10 locales) but otherwise identical.
"""
import json
import os
import requests
from pathlib import Path


CACHE_DIR = Path(__file__).parent.parent / 'cache' / 'pupshape_templates'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Mirrors lib/config/supported_locale.dart in the Flutter app.
LANG_NAMES = {
    'en':       'English',
    'es':       'Spanish',
    'pt':       'Portuguese (Brazil)',
    'fr':       'French',
    'de':       'German',
    'it':       'Italian',
    'nl':       'Dutch',
    'ja':       'Japanese',
    'ko':       'Korean',
    'zh-Hans':  'Simplified Chinese',
}

SUPPORTED = list(LANG_NAMES.keys())


def _cache_path(kind: str, lang: str) -> Path:
    # Use safe filenames — replace - in zh-Hans → _.
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
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                 encoding='utf-8')


def _translate_via_deepseek(kind: str, lang: str, en_source: dict) -> dict:
    """Single DeepSeek call translating subject + body + cta in one shot."""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        raise RuntimeError('DEEPSEEK_API_KEY not set; cannot translate')

    target = LANG_NAMES.get(lang)
    if not target:
        raise ValueError(f'unsupported language {lang!r}')

    system = (
        "You are translating marketing/retention emails for an iOS app "
        "called PupShape — a dog weight-management coach. The voice is "
        "warm, pet-parent-to-pet-parent, slightly informal — like a "
        "friend who's also a vet nurse texting them about their dog. "
        "Always address the human, talk about the dog. Never moralize a "
        "missed day. Translate ACCURATELY, preserve meaning, line breaks, "
        "and every {{placeholder}} token VERBATIM (do not translate "
        "placeholder names, do not add spaces inside {{ }}). Keep emoji "
        "as-is. Output STRICT JSON with the exact same keys as input. No "
        "commentary."
    )

    user = (
        f"Translate the following email content from English to {target}. "
        f"Email kind: {kind}.\n\n"
        f"Input JSON:\n{json.dumps(en_source, ensure_ascii=False, indent=2)}\n\n"
        f"Return JSON of the same shape, with strings translated to "
        f"{target}. For Portuguese, use Brazilian Portuguese. For "
        f"Chinese, use Simplified Chinese. For Japanese keep the "
        f"informal です/ます register, not super formal.\n"
        f"Critical: keep every {{first_name}}, {{dog_name}}, {{streak}}, "
        f"{{n}}, {{target_weight}}, {{current_weight}} placeholder verbatim."
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
                {'role': 'user',   'content': user},
            ],
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f'DeepSeek HTTP {resp.status_code}: {resp.text[:300]}'
        )

    content = resp.json()['choices'][0]['message']['content']
    payload = json.loads(content)

    # Sanity: every key from en_source must be present in the response;
    # lists must remain lists of the same length.
    for k, v in en_source.items():
        if k not in payload:
            raise RuntimeError(
                f'translation missing key {k!r} for {lang}'
            )
        if isinstance(v, list) and not isinstance(payload[k], list):
            raise RuntimeError(
                f'translation key {k!r} must remain a list for {lang}'
            )
        if isinstance(v, list) and len(payload[k]) != len(v):
            if len(payload[k]) < len(v):
                payload[k] = payload[k] + v[len(payload[k]):]
            else:
                payload[k] = payload[k][:len(v)]
    return payload


def get_localized(kind: str, lang: str, en_source: dict,
                  allow_api: bool = True) -> dict:
    """Return the localized template for `lang`. Falls back to English
    if translation fails or `allow_api` is False and there's no cache.
    """
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
    """Pre-fill the cache for every non-English supported language. Run
    once after deploying a new sender so production sends never pay the
    cold latency."""
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


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--warm':
        # Walk every PupShape sender module, pull its EN_SOURCE(s),
        # warm. Lazy import keeps this script self-contained.
        from pathlib import Path
        import importlib
        scripts_dir = Path(__file__).parent
        sys.path.insert(0, str(scripts_dir))
        for f in sorted(scripts_dir.glob('*_pupshape_sender.py')):
            mod_name = f.stem
            try:
                mod = importlib.import_module(mod_name)
            except Exception as e:
                print(f'⚠️ skip {mod_name}: {e}')
                continue
            en = getattr(mod, 'EN_SOURCE', None)
            ens = getattr(mod, 'EN_SOURCES', None)
            kind = getattr(mod, 'KIND', mod_name)
            if en:
                print(f'\n--- warming {kind} ---')
                warm_all(kind, en)
            elif ens:
                for sub_key, src in ens.items():
                    sub_kind = f'{kind}_{sub_key}'
                    print(f'\n--- warming {sub_kind} ---')
                    warm_all(sub_kind, src)
