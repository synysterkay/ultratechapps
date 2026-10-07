#!/usr/bin/env python3
"""Onbrief email templates — English, work-desk voice. Tip-first, soft CTA.

Never school/thesis language. Value / advice in the body; one continue/export CTA.
Soft unlock only on quota_hit (P.S.), never trial countdown.
"""
from __future__ import annotations

import json
from pathlib import Path

from localize_phrase import strip_unreplaced_placeholders

CACHE_DIR = Path(__file__).parent.parent / 'cache' / 'onbrief_templates'

TEMPLATES: dict[str, dict] = {
    'welcome': {
        '_': {
            'subject': 'Tip: outline first, then Generate all once',
            'body': [
                "You opened Onbrief. The usual trap: type a title, glance at the outline, close the app, mean to finish after the next meeting.",
                "Fastest win: open the brief that's already on the desk, tap Generate all once, then skim. Don't rewrite the outline ten times first.",
                "Do that now — one brief, one generate pass. You'll have a draft before this email is closed.",
                "P.S. People who generate the first brief on day one actually export it. Waiting usually means it never leaves the outline.",
            ],
            'cta': 'Generate all',
        },
    },
    'first_complete': {
        '_': {
            'subject': '{{first_name}}, brief done — one pass, then export',
            'body': [
                "{{first_name}} — your {{work_type}} on {{topic}} is finished. That's the hard part.",
                "Before you send it: skim once for claim → evidence, then export the PDF. A brief that only lives in the app is a draft your team never sees.",
                "P.S. Save a copy to Files while you're there. Future-you will not want to regenerate this under a deadline.",
            ],
            'cta': 'Export my PDF',
        },
    },
    'quota_hit': {
        'instant': {
            'subject': "You've already done the hard part on {{topic}}",
            'body': [
                "You just generated the first section of {{topic}}. Starting is the bottleneck — and you already cleared it.",
                "Practical next move: keep the same outline and finish the remaining sections while the brief is fresh. Generate all, then export.",
                "P.S. When you're ready to continue past the free chapter, unlocking removes the gate so you finish without stopping mid-outline.",
            ],
            'cta': 'Continue this brief',
        },
        '24h': {
            'subject': '{{first_name}}, your brief on {{topic}} is still waiting',
            'body': [
                "Yesterday you started a {{work_type}} in Onbrief. The outline is still there.",
                "Tip: don't start a new brief. Open the one on the desk, generate the remaining sections, export once. Continuity beats a fresh blank page.",
                "P.S. Twenty-four hours is still recoverable — finish this one before the context goes cold.",
            ],
            'cta': 'Finish this brief',
        },
        '72h': {
            'subject': 'Finish {{topic}} section by section',
            'body': [
                "{{first_name}} — three days since you started {{topic}}. The research is still in the workspace.",
                "People who finish fast don't write more hours — they remove the gap between section 1 and section 2. Open once, generate what's empty, export.",
                "P.S. If the deadline moved, ignore this. If it didn't, this is still the cheapest hour you'll spend on it.",
            ],
            'cta': 'Continue writing',
        },
        '7d': {
            'subject': 'Your draft on {{topic}} is still waiting',
            'body': [
                "A week since your free chapter. Your outline and draft on {{topic}} are still saved — nothing's gone.",
                "If you still need the {{work_type}}, open Onbrief and generate the next sections. This is the last note I'll send about that free chapter.",
                "P.S. No hard sell — just the method: outline → generate → export.",
            ],
            'cta': 'Open Onbrief',
        },
    },
    'stuck_on_outline': {
        '_': {
            'subject': 'Outline done — start with the easiest section',
            'body': [
                "You have an outline in Onbrief for {{topic}}. Knowing the sections is the hard setup — writing starts when you generate, not when you edit the outline again.",
                "Tip: if Generate all feels big, tap the section you understand best first, then fill the rest. Momentum beats perfect order.",
                "P.S. People who generate the same day they build the outline are the ones who actually export a PDF.",
            ],
            'cta': 'Generate all',
        },
    },
    'abandoned_brief': {
        '2d': {
            'subject': 'A 10-minute restart for {{topic}}',
            'body': [
                "Two days quiet on your {{work_type}}. Tip: don't reopen trying to rewrite everything.",
                "Open the brief, generate only empty sections, export a draft PDF. One pass beats a guilt spiral.",
                "P.S. Day two is the cheap save — unfinished briefs almost never get easier on day five.",
            ],
            'cta': 'Continue this brief',
        },
        '5d': {
            'subject': 'Restart rule for {{topic}}',
            'body': [
                "{{first_name}} — five days since you touched {{topic}} in Onbrief.",
                "Restart rule: skim the outline two minutes, generate what's missing, export. If this brief is dead, start clean — don't keep a zombie outline.",
                "P.S. A shipped draft beats a perfect outline nobody sees.",
            ],
            'cta': 'Finish or start clean',
        },
        '10d': {
            'subject': 'Last tip on {{topic}}',
            'body': [
                "Ten days. Last note from me on this document.",
                "If you still need the {{work_type}}, open Onbrief once: generate → export. If you don't, archive it and we'll stay out of your inbox.",
                "P.S. Momentum returns faster than motivation — one section is enough.",
            ],
            'cta': 'Open Onbrief',
        },
    },
    'deadline': {
        '7': {
            'subject': '7 days out — reverse-plan {{topic}}',
            'body': [
                "{{first_name}}, you set a deadline for {{topic}}. One week out.",
                "Reverse-plan tip: list remaining sections, assign one per day, leave a buffer to export. Generate today's section now so the plan is real.",
                "P.S. A finished PDF on day −7 beats a scramble on day 0.",
            ],
            'cta': 'Work the brief',
        },
        '3': {
            'subject': '3 days — finish unfinished sections first',
            'body': [
                "Three days until the deadline. Skip polishing for now.",
                "Generate every empty section first, skim once, export a draft even if you'll edit later. A file in Files is a file you can send.",
                "P.S. Don't wait for tomorrow's calendar to eat this.",
            ],
            'cta': 'Export a draft today',
        },
        '1': {
            'subject': 'Tomorrow — export {{topic}} tonight',
            'body': [
                "{{first_name}} — deadline tomorrow. Tip: generate anything empty now, then export before you sleep. Don't leave PDF export for the morning of.",
                "Open Onbrief once and get the file off the phone.",
                "P.S. This is the last useful hour. Use it.",
            ],
            'cta': 'Export tonight',
        },
        '0': {
            'subject': 'Today: export {{topic}} and send',
            'body': [
                "Deadline is today. Export whatever is there and send it.",
                "Done beats perfect. A shipped draft beats a perfect outline nobody sees.",
                "P.S. Export first. Edit the file after it's out of the app.",
            ],
            'cta': 'Export now',
        },
    },
    'brief_tip': {
        'outline': {
            'subject': 'Start with the decision the brief must answer',
            'body': [
                "Blank-page tip for work writing: don't open a memo and “start typing.” Write one decision question first (one sentence).",
                "That question becomes your outline filter — intro, 3–5 sections, recommendation. Onbrief turns that into a structured brief fast.",
                "Open the desk, drop the question, generate the outline before you draft a paragraph.",
            ],
            'cta': 'Start my outline',
        },
        'generate': {
            'subject': "Don't polish the outline — generate the easy section",
            'body': [
                "Your outline for {{topic}} is ready. Most people stall editing section titles instead of writing.",
                "Tip: generate the section you already understand first, then fill the rest with Generate all. Momentum beats perfect order.",
                "Ten minutes from now you can have a full draft instead of a prettier outline.",
            ],
            'cta': 'Generate a section',
        },
        'revise': {
            'subject': 'One-pass revise: claim → evidence → ask',
            'body': [
                "You already have draft text on {{topic}}. Before generating more, do one focused pass:",
                "1) Underline each claim\n2) Ask what evidence supports it\n3) Add the ask / recommendation\n4) Then export",
                "That pass turns AI draft into something a manager can act on. Open the brief and try it on two paragraphs.",
            ],
            'cta': 'Open my brief',
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
        return f'onbrief_{kind}_en.json'
    return f'onbrief_{kind}_{key}_en.json'


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
        raise KeyError(f'unknown Onbrief template {kind}/{stage}')
    return tpl


def fill(tpl: dict, **replacements) -> dict:
    out = {
        'subject': tpl['subject'],
        'body': list(tpl['body']),
        'cta': tpl.get('cta', 'Open Onbrief'),
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
            path.write_text(json.dumps(tpl, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            written += 1
            print(f'   ✓ {path.name}')
    print(f'✅ Warmed {written} Onbrief templates into {CACHE_DIR}')
    return written


if __name__ == '__main__':
    warm()
