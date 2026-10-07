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
            'subject': "You've already started the toast for {{couple}}",
            'body': [
                "You just saw a draft for your {{role}} speech. Starting is the hard part — and you already did that.",
                "Practical next move: finish empty lines while the story is fresh, then rehearse the first minute aloud once.",
                "P.S. When you're ready to continue past the free draft, unlocking removes the gate so you can polish and rehearse without stopping mid-toast.",
            ],
            'cta': 'Continue this speech',
        },
        '24h': {
            'subject': '{{first_name}}, your speech for {{couple}} is still waiting',
            'body': [
                "Yesterday you started a {{role}} speech in Vowcraft. The draft is still there.",
                "Tip: don't start over. Open the same toast, finish empty lines, rehearse minute one. Continuity beats a blank page.",
                "P.S. Twenty-four hours is still recoverable.",
            ],
            'cta': 'Finish this speech',
        },
        '72h': {
            'subject': 'Finish the toast for {{couple}}, then rehearse once',
            'body': [
                "{{first_name}} — three days since you started your {{role}} speech. The draft is still in Vowcraft.",
                "People who deliver well don't write more hours — they finish the draft, then say the first minute aloud. Open once. Finish. Rehearse.",
                "P.S. If the wedding moved, ignore this. If it didn't, this is still the cheapest hour you'll spend on it.",
            ],
            'cta': 'Continue writing',
        },
        '7d': {
            'subject': 'Your {{role}} speech is still waiting',
            'body': [
                "A week since your free draft. Your speech for {{couple}} is still saved — nothing's gone.",
                "If you still need it, open Vowcraft, finish empty lines, rehearse once. This is the last note I'll send about that free draft.",
                "P.S. No hard sell — just the method: finish → rehearse → mean it.",
            ],
            'cta': 'Open Vowcraft',
        },
    },
    'abandoned_speech': {
        '2d': {
            'subject': 'A 10-minute restart for your {{role}} toast',
            'body': [
                "Two days quiet on the speech for {{couple}}. Tip: don't reopen trying to rewrite everything.",
                "Open the draft, fill empty lines only, tap Rehearse once for the first minute. One pass beats a guilt spiral.",
                "P.S. Day two is the cheap save — unfinished toasts almost never get easier on day five.",
            ],
            'cta': 'Continue this speech',
        },
        '5d': {
            'subject': 'Restart rule for {{couple}}',
            'body': [
                "{{first_name}} — five days since you touched your {{role}} speech.",
                "Restart rule: skim two minutes, finish what's missing, rehearse minute one aloud. If this draft is dead, start clean — don't keep a zombie toast.",
                "P.S. A rehearsed rough draft beats a perfect unread speech.",
            ],
            'cta': 'Finish or start clean',
        },
        '10d': {
            'subject': 'Last tip on your speech',
            'body': [
                "Ten days. Last note from me on this toast.",
                "If you still need the {{role}} speech for {{couple}}, open Vowcraft once: finish → rehearse. If you don't, archive it and we'll stay out of your inbox.",
                "P.S. Momentum returns faster than motivation — one minute aloud is enough.",
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
