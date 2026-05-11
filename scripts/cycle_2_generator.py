#!/usr/bin/env python3
"""
Cycle 2 Content Generator (Thesis Generator)

Generates 5 fresh retention emails specifically tuned for users who have
already received the entire 30-email cycle 1. The existing system just
remaps cycle-2 emails to repurposed cycle-1 templates; this produces
genuinely new copy with a cycle-2 voice ("we've been on this journey
together — here's what's next").

Cache filename convention:
    thesis_generator_cycle2_email_{1..5}.json           (English)
    thesis_generator_{lang}_cycle2_email_{1..5}.json    (other languages)

The retention emailer can be extended to prefer these files when cycle > 1,
falling back to the old CYCLE_RESTART_REMAP behaviour.

Usage:
    DEEPSEEK_API_KEY=... python scripts/cycle_2_generator.py            # all 6 langs
    DEEPSEEK_API_KEY=... python scripts/cycle_2_generator.py --lang en  # one lang
"""
import os
import sys
import json
import re
import time
import requests
from pathlib import Path


APP_NAME = 'Thesis Generator'
SUPPORTED = ['en', 'es', 'fr', 'ar', 'zh', 'hi']

LANG_NAMES = {
    'en': 'English', 'es': 'Spanish', 'fr': 'French',
    'ar': 'Arabic', 'zh': 'Chinese', 'hi': 'Hindi',
}

# 5 fresh angles that don't overlap with the cycle 1 sequence. Each is a
# distinct emotional beat for a returning user. {{first_name}}, {{topic}},
# {{work_type}}, {{days_left}} interpolation tokens are added by the
# emailer at send time.
CYCLE_2_ANGLES = [
    {
        'index': 1,
        'type': 'cycle2_welcome_back',
        'goal': 'Acknowledge the return without restating the original pitch.',
        'angle': 'You\'ve seen what we can do. Here\'s why we\'re writing again — not to re-sell, but because you\'re still on the journey and we still care.',
        'psychology': 'Reciprocity. Treat the returning user like a known friend, not a new prospect.',
    },
    {
        'index': 2,
        'type': 'cycle2_unexpected_tip',
        'goal': 'Surprise the user with a specific advanced workflow they almost certainly don\'t know.',
        'angle': 'A non-obvious feature: how to use the "enhance" action to make AI output sound less like AI, or how to inject a specific reference style mid-generation. Concrete, actionable, in <4 sentences.',
        'psychology': 'Variable reward — the user expected another generic motivational email and got something useful instead.',
    },
    {
        'index': 3,
        'type': 'cycle2_testimonial',
        'goal': 'Show one specific user story that mirrors the recipient\'s situation (deadline / confusion / no-time / perfectionist).',
        'angle': 'Use {{pain_hook}} to mirror their pain at the top, then tell a 3-sentence story of "Maria, a master\'s student, who finished her thesis on climate policy in 9 days". Make it credible — no exaggerated numbers.',
        'psychology': 'Social proof from a near-peer, not a far-away celebrity.',
    },
    {
        'index': 4,
        'type': 'cycle2_referral',
        'goal': 'Ask the user to send one friend, in exchange for nothing tangible.',
        'angle': 'Honest ask: "If this helped you, the single best thing you can do is tell one friend who\'s also stuck on a paper." Frame the share as low-cost help to a peer, not a reward chase.',
        'psychology': 'Investment — once they share, they will defend the choice and re-engage.',
    },
    {
        'index': 5,
        'type': 'cycle2_legacy',
        'goal': 'Close the loop on the entire cycle. Reflect on the journey, invite them back when needed.',
        'angle': 'Acknowledge that they may not need the app every day — and that\'s fine. The app is here when the next paper lands. Keep this short, warm, ungated.',
        'psychology': 'Permission to leave. Counter-intuitive but increases long-term retention.',
    },
]

PROMPT_TEMPLATE = """You are the team behind {app_name}, writing a CYCLE 2 retention email — meaning the user has already received the full 30-email onboarding sequence months ago and is being re-engaged.

EMAIL #{index} OF 5 in this cycle 2 mini-series.

TYPE: {type}
GOAL: {goal}
ANGLE: {angle}
PSYCHOLOGY: {psychology}

APP: {app_name}
AUDIENCE: students writing essays, research papers, theses, or dissertations. They\'ve already used the app once or several times.

PLACEHOLDERS — Use these {{tokens}} sparingly and naturally; the emailer fills them in at send time:
  {{{{first_name}}}}   — the user\'s first name (might be empty)
  {{{{topic}}}}         — their last saved thesis topic
  {{{{work_type}}}}     — "essay", "research paper", "thesis", "dissertation"
  {{{{days_left}}}}     — phrase like "5 days left" or "due today" or empty
  {{{{pain_hook}}}}     — empathy sentence (only use in email #3)
  {{{{streak}}}}        — phrase like "7-day streak" (rarely used)

SUBJECT LINE RULES:
- 4–8 words, no emojis
- Sound like a returning friend, not a brand pushing a sale
- A subject like "It's been a while, {{{{first_name}}}}" or "About your {{{{topic}}}}…" works

EMAIL BODY RULES:
- 180–300 words. Cycle-2 emails are tighter than cycle 1.
- NO emojis in body
- NO bullet points — flowing prose
- One concrete CTA at the end
- P.S. allowed if it adds, not if it pads
- Acknowledge that this is a returning audience — never restate features they already know

LANGUAGE: Write the entire email in {language_name}. Native speaker voice, not a translation.

OUTPUT FORMAT (strict JSON, no markdown):
{{{{
  "subject": "string",
  "preview_text": "80-100 chars",
  "body_paragraphs": ["...", "...", "..."],
  "cta_text": "Button label",
  "email_number": {index},
  "send_day": null,
  "type": "{type}",
  "cycle": 2
}}}}

Generate the email now."""


def _cache_path(language, index):
    base = Path(__file__).parent.parent / 'cache' / 'retention_emails'
    if language == 'en':
        return base / f'thesis_generator_cycle2_email_{index}.json'
    return base / f'thesis_generator_{language}_cycle2_email_{index}.json'


def _call_deepseek(api_key, prompt):
    resp = requests.post(
        'https://api.deepseek.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': 'You are a world-class retention copywriter. Output ONLY valid JSON, nothing else.'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.85,
            'max_tokens': 1600,
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()['choices'][0]['message']['content']
    # Some models wrap the JSON in ```json fences — strip them.
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        raise ValueError(f'no JSON in response: {raw[:200]}')
    return json.loads(m.group(0))


def generate(languages):
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print('❌ DEEPSEEK_API_KEY not set')
        sys.exit(1)

    base = Path(__file__).parent.parent / 'cache' / 'retention_emails'
    base.mkdir(parents=True, exist_ok=True)

    for lang in languages:
        lang_name = LANG_NAMES.get(lang, 'English')
        print(f'\n🌍 {lang_name}')
        for angle in CYCLE_2_ANGLES:
            path = _cache_path(lang, angle['index'])
            if path.exists():
                print(f'   ⏭  skip (exists) {path.name}')
                continue
            prompt = PROMPT_TEMPLATE.format(
                app_name=APP_NAME,
                language_name=lang_name,
                **angle,
            )
            try:
                data = _call_deepseek(api_key, prompt)
            except Exception as e:
                print(f'   ❌ {angle["type"]}: {e}')
                continue
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f'   💾 {path.name}  ({len(json.dumps(data))} chars)')
            time.sleep(1)


if __name__ == '__main__':
    languages = SUPPORTED
    for i, arg in enumerate(sys.argv):
        if arg == '--lang' and i + 1 < len(sys.argv):
            languages = [sys.argv[i + 1]]
    generate(languages)
