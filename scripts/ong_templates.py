#!/usr/bin/env python3
"""ONG email templates — English cache, same pattern as thesis/kinbound.

ONG is English-only. `warm()` writes cache/ong_templates/{kind}_en.json so
copy lives next to the other apps' cached mail. Senders read via get_template().
"""
from __future__ import annotations

import json
from pathlib import Path

from localize_phrase import strip_unreplaced_placeholders

CACHE_DIR = Path(__file__).parent.parent / 'cache' / 'ong_templates'

# kind → stage_key|None → {subject, body, cta}
TEMPLATES: dict[str, dict] = {
    'welcome': {
        '_': {
            'subject': 'Lock it in. Nobody sees yours until you do.',
            'body': [
                "You just opened ONG. The whole game is one move: send a question to 3 friends. They lock in blind. Then you crack the seal and see who called it.",
                "Don't overthink the first one. \"Will they be late?\" \"Who texts first?\" That's enough. Tap make a prediction, type it, send it from the app. Thirty seconds.",
                "They can't see each other's answers until they've submitted their own. That's the point. The reveal is the fun — real names, no money, just who was right.",
                "Open the app and send one now, while it's still in your head. P.S. People who lock in a first prediction on day one actually come back for the reveal. Waiting usually means it never happens.",
            ],
            'cta': 'Make my first prediction',
        },
    },
    'waiting_on_you': {
        '1d': {
            'subject': '{{first_name}}, someone locked a question about you',
            'body': [
                "{{first_name}} — a friend sent you a prediction on ONG. They already locked in. You haven't.",
                "Nobody sees your answer until you submit. That's the whole game. Open the app, tap the invite, lock it in.",
                "P.S. If you wait until after the reveal, you don't get a call. That's the rule.",
            ],
            'cta': 'Lock in my answer',
        },
        '3d': {
            'subject': "They still don't know what you called",
            'body': [
                "{{first_name}}, it's been three days. The question is still waiting. Blind on purpose.",
                "Open ONG, find the invite, lock it in. Then you wait for the seal to crack like everyone else.",
                "P.S. This is the last nudge on this one. After that we go quiet.",
            ],
            'cta': 'Answer before the reveal',
        },
    },
    'reveal_live': {
        '_': {
            'subject': 'The seal cracked. See who called it.',
            'body': [
                "{{first_name}} — a prediction you were in just resolved. Everyone locked in blind. Now you get to see who was right.",
                "That's the whole point of ONG. Open it while the names are still a surprise.",
                "P.S. We only ping you when there's an actual reveal waiting. Not a drip.",
            ],
            'cta': 'Open the reveal',
        },
    },
    'first_lock': {
        '_': {
            'subject': "It's live. Now send it from the app.",
            'body': [
                "{{first_name}} — your prediction is locked. Nobody can change it. That's the product.",
                "The only thing left is the invite. Open ONG and send it to three friends from the share sheet. They answer blind. Then you find out who called it.",
                "P.S. A prediction with no answers is just a note to yourself. Three people is the whole game.",
            ],
            'cta': 'Send it from the app',
        },
    },
    'streak_at_risk': {
        '_': {
            'subject': 'Your {{streak}}-day streak dies at midnight',
            'body': [
                "{{first_name}} — you're on a {{streak}}-day ONG streak. One lock-in tonight keeps it alive.",
                "Doesn't have to be a new question. Answer a friend's. That's enough.",
                "P.S. We only send this once per close call.",
            ],
            'cta': 'Keep my streak',
        },
    },
    'streak_milestone': {
        '3': {
            'subject': 'Three days of calling it',
            'body': [
                "{{first_name}} — three days in a row. That's a streak, not a mood.",
                "Keep locking in. The people who get good at this are just the ones who show up before the reveal.",
                "P.S. Day 7 is when it starts feeling like a habit.",
            ],
            'cta': 'Open ONG',
        },
        '7': {
            'subject': 'A full week of locked-in calls',
            'body': [
                "{{first_name}}, seven days. You showed up blind, every day, and found out who called it.",
                "That's the game. Send another one tonight — from the app, not this email.",
                "P.S. Streaks like this are how you climb the board — not one lucky public post.",
            ],
            'cta': 'Keep it going',
        },
        '14': {
            'subject': 'Two weeks. You actually call it.',
            'body': [
                "{{first_name}} — fourteen days. Most people drop after the first reveal. You didn't.",
                "Make one more prediction while the streak is hot.",
                "P.S. This is the part friends notice.",
            ],
            'cta': 'Make another',
        },
        '30': {
            'subject': '30 days. You called it.',
            'body': [
                "{{first_name}}, a month of locking in before you saw anyone else's answer. That's rare.",
                "Don't break it for a quiet Tuesday. One tap.",
                "P.S. Screenshot the streak. That's the brag.",
            ],
            'cta': 'See my streak',
        },
    },
    'abandoned_app': {
        '2d': {
            'subject': 'You never sent the invite',
            'body': [
                "{{first_name}} — ONG is sitting on your phone with nobody in a prediction yet.",
                "One question. Three friends. They lock in blind. That's the whole game, and it takes a minute.",
                "P.S. \"Will they be late?\" is enough. Don't wait for a better one.",
            ],
            'cta': 'Make my first prediction',
        },
        '5d': {
            'subject': 'Five days. Still no seal to crack.',
            'body': [
                "{{first_name}}, five days without opening ONG. The reveal only happens if someone locks in.",
                "Open it, send one invite from the app, and you'll have a reason to come back.",
                "P.S. Friends answer faster than you think once the link is in the chat.",
            ],
            'cta': 'Open ONG',
        },
        '10d': {
            'subject': 'Should we go quiet, {{first_name}}?',
            'body': [
                "{{first_name}}, ten days away. We can welcome you back or stop nudging.",
                "ONG is still the same: lock it in, nobody sees, then you find out who called it.",
                "P.S. If now isn't the time, ignore this. We won't send another on this thread.",
            ],
            'cta': 'Reopen ONG',
        },
    },
    'weekly_recap': {
        '_': {
            'subject': 'Your week on ONG',
            'body': [
                "{{first_name}} — quick recap, not a lecture:",
                "{{week_summary}}",
                "One more lock-in this weekend and next Sunday looks better. P.S. We only send this if you actually opened the app recently.",
            ],
            'cta': 'Open ONG',
        },
    },
    'pro_gate': {
        '_': {
            'subject': 'See who called it',
            'body': [
                "{{first_name}} — you hit the names gate. You already locked in. The fun part is seeing who said what.",
                "That's Pro. One tap in the app, then the names. Not a sales sequence — this is the one time we mention it.",
                "P.S. If you'd rather stay free, ignore this. Reveals still happen. You just don't get the roster.",
            ],
            'cta': 'See the names',
        },
    },
    'founder_story': {
        '_': {
            'subject': "{{first_name}}, I built ONG because group chats lie",
            'body': [
                "{{first_name}} — group chats are full of \"I knew it\" after the fact. Nobody writes it down before. That's why the argument never ends.",
                "I built ONG so your friends lock in blind. Same question, no peeking, then the seal cracks and you see who actually called it. No money. Real names.",
                "You haven't opened it in a couple of weeks. The product is still one move: make a prediction, send it from the share sheet, wait for the reveal.",
                "If that still sounds like your group, open the app once. If it doesn't, we'll go quiet.",
                "P.S. I'm Alex. This is the only founder note. Not a 30-day drip.",
            ],
            'cta': 'Lock in one',
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
        return f'ong_{kind}_en.json'
    return f'ong_{kind}_{key}_en.json'


def _cache_path(kind: str, stage=None) -> Path:
    return CACHE_DIR / _cache_name(kind, stage)


def get_template(kind: str, stage=None) -> dict:
    """Load cached EN template, falling back to the inline registry."""
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
        raise KeyError(f'unknown ONG template {kind}/{stage}')
    return tpl


def fill(tpl: dict, **replacements) -> dict:
    out = {
        'subject': tpl['subject'],
        'body': list(tpl['body']),
        'cta': tpl.get('cta', 'Open ONG'),
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
    """Write every EN template into cache/ong_templates/."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for kind, stages in TEMPLATES.items():
        for stage, tpl in stages.items():
            path = _cache_path(kind, None if stage == '_' else stage)
            path.write_text(json.dumps(tpl, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            written += 1
            print(f'   ✓ {path.name}')
    print(f'✅ Warmed {written} ONG templates into {CACHE_DIR}')
    return written


if __name__ == '__main__':
    warm()
