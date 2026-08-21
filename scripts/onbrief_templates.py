#!/usr/bin/env python3
"""Onbrief email templates — English, work-desk voice. Never school/thesis."""
from __future__ import annotations

import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / 'cache' / 'onbrief_templates'

TEMPLATES: dict[str, dict] = {
    'welcome': {
        '_': {
            'subject': 'Your outline is on the desk. 30 seconds to a full brief.',
            'body': [
                "You opened Onbrief. The trap is the same for almost everyone: type a title, glance at the outline, close the app, mean to finish it after the next meeting. Three days later the desk is empty and the deadline is not.",
                "The fastest win is not writing the whole thing. Open the brief that's already sitting there, tap Generate all, and let the workspace fill. That's the whole product — a finished memo you can export, not another notes app.",
                "Don't save this for Friday. Open Onbrief now, stay on that one brief, tap Generate all. You'll have a draft before this email is closed.",
                "P.S. People who generate the first brief on day one actually export it. Waiting usually means it never leaves the outline.",
            ],
            'cta': 'Generate all',
        },
    },
    'first_complete': {
        '_': {
            'subject': '{{first_name}}, the brief is done — export the PDF',
            'body': [
                "{{first_name}} — your {{work_type}} on {{topic}} is finished. That's the hard part.",
                "Now get it off the phone. Open Onbrief, go to Export, save the PDF. A brief that only lives in the app is a draft your team never sees.",
                "P.S. Save a copy to Files while you're there. Future-you will not want to regenerate this under a deadline.",
            ],
            'cta': 'Export my PDF',
        },
    },
    'quota_hit': {
        'instant': {
            'subject': "Don't lose the draft, {{first_name}} — unlock the rest",
            'body': [
                "You just saw what Onbrief can do on {{topic}}. That's the moment people usually stop — the paywall appears and the draft sits half-written.",
                "Unlock writing now and tap Generate all on the rest of the outline. The next sections take about a minute. By the time you get back to your desk, the brief is exportable.",
                "P.S. This is the same unlock that covers PDF export. One tap, then you're done arguing with a blank page.",
            ],
            'cta': 'Unlock writing',
        },
        '24h': {
            'subject': '{{first_name}}, your brief on {{topic}} is still waiting',
            'body': [
                "Yesterday you started a {{work_type}} in Onbrief. The outline is still there. The rest of the sections are one unlock away.",
                "Open the app, unlock writing, tap Generate all. Don't start over — finish the one that's already on the desk.",
                "P.S. Most people who wait a week never come back to that outline. Twenty-four hours is still recoverable.",
            ],
            'cta': 'Finish this brief',
        },
        '72h': {
            'subject': 'Three days. The outline on {{topic}} is going cold.',
            'body': [
                "{{first_name}} — it's been three days since you hit the writing gate on {{topic}}. The research is still in the workspace. The PDF is not.",
                "Open Onbrief once. Unlock. Generate all. Export. That's the whole loop you already started.",
                "P.S. If the deadline moved, ignore this. If it didn't, this is the cheapest hour you'll spend on it.",
            ],
            'cta': 'Unlock and finish',
        },
        '7d': {
            'subject': 'Last note on {{topic}}',
            'body': [
                "It's been a week. Your {{work_type}} on {{topic}} is still an outline in Onbrief.",
                "If you still need it, open the app and finish the generation. If you don't, we'll go quiet after this.",
                "P.S. This is the last upgrade nudge on this brief.",
            ],
            'cta': 'Open Onbrief',
        },
    },
    'stuck_on_outline': {
        '_': {
            'subject': '{{first_name}}, the outline is done. Generate all is the next tap.',
            'body': [
                "You have an outline sitting in Onbrief for {{topic}}. That's the setup. The brief itself starts when you tap Generate all — not when you edit the outline again.",
                "Open the workspace. Stay on that one document. Tap Generate all and let it write. Come back to a full draft instead of another empty section.",
                "P.S. People who tap Generate all the same day they build the outline are the ones who actually export a PDF.",
            ],
            'cta': 'Generate all',
        },
    },
    'abandoned_brief': {
        '2d': {
            'subject': '{{first_name}}, your {{work_type}} on {{topic}} is still open',
            'body': [
                "It's been two days. The brief is still on the desk in Onbrief — not exported, not sent.",
                "Open the app, pick up where you left off, tap Generate all if the sections are empty. Then export the PDF before the next meeting swallows it.",
                "P.S. Unfinished briefs almost never get easier on day five. Day two is the cheap save.",
            ],
            'cta': 'Continue this brief',
        },
        '5d': {
            'subject': "Five days. {{topic}} still isn't a PDF.",
            'body': [
                "{{first_name}} — your {{work_type}} has been sitting in Onbrief for five days. The outline didn't write itself.",
                "Open it once. Generate what's missing. Export. That's it.",
                "P.S. If this one is dead, start a new brief. Don't keep a zombie outline.",
            ],
            'cta': 'Finish or start clean',
        },
        '10d': {
            'subject': 'Last ping on {{topic}}',
            'body': [
                "Ten days. We'll stop after this.",
                "If you still need the {{work_type}}, it's in Onbrief. Open, generate, export. If you don't, archive it and we'll stay out of your inbox.",
                "P.S. This is the last reminder on this document.",
            ],
            'cta': 'Open Onbrief',
        },
    },
    'deadline': {
        '7': {
            'subject': "7 days until your deadline — the brief isn't exported yet",
            'body': [
                "{{first_name}}, you set a deadline in Onbrief for {{topic}}. One week out.",
                "Open the workspace today. If sections are empty, tap Generate all. If they're written, export the PDF so you're not doing this the night before.",
                "P.S. A finished PDF on day −7 beats a scramble on day 0.",
            ],
            'cta': 'Work the brief',
        },
        '3': {
            'subject': '3 days. {{topic}} still needs a PDF.',
            'body': [
                "Three days until the deadline you set. Your {{work_type}} is still in Onbrief.",
                "Generate what's missing, skim it, export. Don't wait for tomorrow's calendar to eat this.",
                "P.S. Export now even if you'll edit later. A file in Files is a file you can send.",
            ],
            'cta': 'Export a draft today',
        },
        '1': {
            'subject': 'Tomorrow. Export {{topic}} tonight.',
            'body': [
                "{{first_name}} — the deadline is tomorrow. The brief is still on the phone.",
                "Open Onbrief, tap Generate all on anything empty, export the PDF before you sleep.",
                "P.S. This is the last useful hour. Use it.",
            ],
            'cta': 'Export tonight',
        },
        '0': {
            'subject': "It's due today. Get the PDF off the phone.",
            'body': [
                "Deadline is today. Open Onbrief, export whatever is there, send it.",
                "A shipped draft beats a perfect outline nobody sees.",
                "P.S. Export first. Edit the file after it's out of the app.",
            ],
            'cta': 'Export now',
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
