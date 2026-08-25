#!/usr/bin/env python3
"""Vowcraft email templates — wedding speech voice. Write → Rehearse → Mean it."""
from __future__ import annotations

import json
from pathlib import Path

from localize_phrase import strip_unreplaced_placeholders

CACHE_DIR = Path(__file__).parent.parent / 'cache' / 'vowcraft_templates'

TEMPLATES: dict[str, dict] = {
    'welcome': {
        '_': {
            'subject': 'Your speech draft is waiting. Rehearse it once.',
            'body': [
                "You opened Vowcraft. The trap is the same for almost everyone: generate a draft, feel relief, close the app, mean to practice later. The wedding arrives and you're reading cold.",
                "The fastest win is not rewriting everything. Open the speech that's already there, tap Rehearse, and say the first minute aloud. That's the product — a toast you can mean, not another notes app.",
                "Don't save practice for the night before. Open Vowcraft now, stay on that one speech, rehearse once. You'll sound like yourself before this email is closed.",
                "P.S. People who rehearse on day one actually deliver. Waiting usually means a phone screen on the day.",
            ],
            'cta': 'Rehearse my speech',
        },
    },
    'speech_ready': {
        '_': {
            'subject': '{{first_name}}, your speech is ready — rehearse it',
            'body': [
                "{{first_name}} — your {{role}} speech for {{couple}} is written. That's the hard part.",
                "Now make it yours. Open Vowcraft, tap Rehearse, and say it aloud once. A short pass beats a cold read at the mic.",
                "P.S. Copy it to Notes after you rehearse. Future-you will thank you.",
            ],
            'cta': 'Rehearse now',
        },
    },
    'quota_hit': {
        'instant': {
            'subject': "Don't lose the draft, {{first_name}} — unlock the rest",
            'body': [
                "You just saw what Vowcraft can do for {{couple}}. That's when people stop — the paywall appears and the toast sits unfinished.",
                "Unlock writing now, finish the speech, then rehearse. One tap, then you're ready for the room.",
                "P.S. Unlock also covers polish and full rehearsal. Finish the one you started.",
            ],
            'cta': 'Unlock writing',
        },
        '24h': {
            'subject': '{{first_name}}, your speech for {{couple}} is still waiting',
            'body': [
                "Yesterday you started a {{role}} speech in Vowcraft. The draft is still there. The rest is one unlock away.",
                "Open the app, unlock writing, finish the toast. Don't start over — finish the one that's already open.",
                "P.S. Most people who wait a week never come back. Twenty-four hours is still recoverable.",
            ],
            'cta': 'Finish this speech',
        },
        '72h': {
            'subject': 'Three days. The toast for {{couple}} is going cold.',
            'body': [
                "{{first_name}} — it's been three days since you hit the writing gate on your {{role}} speech. The draft is still in Vowcraft. The rehearsal is not.",
                "Open once. Unlock. Finish. Rehearse. That's the loop you already started.",
                "P.S. If the wedding moved, ignore this. If it didn't, this is the cheapest hour you'll spend on it.",
            ],
            'cta': 'Unlock and finish',
        },
        '7d': {
            'subject': 'Last note on your {{role}} speech',
            'body': [
                "It's been a week. Your speech for {{couple}} is still unfinished in Vowcraft.",
                "If you still need it, open the app and finish. If you don't, we'll go quiet after this.",
                "P.S. This is the last upgrade nudge on this speech.",
            ],
            'cta': 'Open Vowcraft',
        },
    },
    'abandoned_speech': {
        '2d': {
            'subject': '{{first_name}}, your {{role}} speech is still open',
            'body': [
                "It's been two days. The speech for {{couple}} is still in Vowcraft — not rehearsed, not ready.",
                "Open the app, finish any empty lines, tap Rehearse once. Then you're done arguing with a blank page.",
                "P.S. Unfinished toasts almost never get easier on day five. Day two is the cheap save.",
            ],
            'cta': 'Continue this speech',
        },
        '5d': {
            'subject': "Five days. {{couple}} still needs your toast.",
            'body': [
                "{{first_name}} — your {{role}} speech has been sitting in Vowcraft for five days. The draft didn't rehearse itself.",
                "Open it once. Finish what's missing. Rehearse. That's it.",
                "P.S. If this one is dead, start a new speech. Don't keep a zombie draft.",
            ],
            'cta': 'Finish or start clean',
        },
        '10d': {
            'subject': 'Last ping on your speech',
            'body': [
                "Ten days. We'll stop after this.",
                "If you still need the {{role}} toast, it's in Vowcraft. Open, finish, rehearse. If you don't, archive it and we'll stay out of your inbox.",
                "P.S. This is the last reminder on this speech.",
            ],
            'cta': 'Open Vowcraft',
        },
    },
    'rehearse': {
        '_': {
            'subject': '{{first_name}}, 2 minutes aloud beats a cold read',
            'body': [
                "You have a draft in Vowcraft. Writing it was step one. Meaning it is step two.",
                "Open the app, tap Rehearse, and say the first minute out loud. Fix what sounds wrong. That's how you walk in ready.",
                "P.S. People who rehearse once sound like themselves. People who don't sound like their phone.",
            ],
            'cta': 'Rehearse now',
        },
    },
}


def _stage_key(stage) -> str:
    if stage is None or stage == '':
        return '_'
    return str(stage)


def _cache_name(kind: str, stage=None) -> str:
    key = _stage_key(stage)
    if key == '_':
        return f'vowcraft_{kind}_en.json'
    return f'vowcraft_{kind}_{key}_en.json'


def _cache_path(kind: str, stage=None) -> Path:
    return CACHE_DIR / _cache_name(kind, stage)


def get_template(kind: str, stage=None) -> dict:
    cached = _cache_path(kind, stage)
    if cached.exists():
        try:
            data = json.loads(cached.read_text(encoding='utf-8'))
            if data.get('subject') and data.get('body'):
                return data
        except Exception:
            pass
    stages = TEMPLATES.get(kind) or {}
    tpl = stages.get(_stage_key(stage)) or stages.get('_')
    if not tpl:
        raise KeyError(f'unknown Vowcraft template {kind}/{stage}')
    return tpl


def fill(tpl: dict, **replacements) -> dict:
    out = {
        'subject': tpl['subject'],
        'body': list(tpl['body']),
        'cta': tpl.get('cta', 'Open Vowcraft'),
    }
    for key, value in replacements.items():
        token = '{{' + key + '}}'
        text = str(value)
        out['subject'] = out['subject'].replace(token, text)
        out['body'] = [p.replace(token, text) for p in out['body']]
        out['cta'] = out['cta'].replace(token, text)
    out['subject'] = strip_unreplaced_placeholders(out['subject'])
    out['body'] = [strip_unreplaced_placeholders(p) for p in out['body']]
    out['cta'] = strip_unreplaced_placeholders(out['cta'])
    return out


def warm():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for kind, stages in TEMPLATES.items():
        for stage, tpl in stages.items():
            path = _cache_path(kind, None if stage == '_' else stage)
            path.write_text(
                json.dumps(tpl, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            written += 1
            print(f'   ✓ {path.name}')
    print(f'✅ Warmed {written} Vowcraft templates into {CACHE_DIR}')
    return written


if __name__ == '__main__':
    warm()
