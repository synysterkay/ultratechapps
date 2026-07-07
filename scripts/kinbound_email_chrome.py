#!/usr/bin/env python3
"""Warm bone/peach HTML chrome for Kinbound retention emails."""
from localize_phrase import (
    GREETINGS,
    SIGNOFFS,
    CELEBRATORY_GREETINGS,
    CELEBRATORY_SIGNOFFS,
    RTL_LANGUAGES,
    footer_text,
    normalize_language,
)

GRADIENTS = {
    'celebrate': ('#E29578', '#D4A24C'),   # peach → gold
    'urgent':    ('#4F5B7D', '#2A2520'),   # indigo → ink
    'invite':    ('#E29578', '#FDE7D2'),   # peach → sand
    'calm':      ('#A4B49A', '#E29578'),   # sage → peach
}


def render(language: str,
           paragraphs,
           cta_text: str,
           cta_url: str,
           sender_name: str = 'Maya',
           app_name: str = 'Kinbound',
           gradient: str = 'invite',
           celebratory: bool = False,
           greeting_override: str = None,
           signoff_override: str = None) -> str:
    lang = normalize_language(language)
    is_rtl = lang in RTL_LANGUAGES
    dir_attr = ' dir="rtl"' if is_rtl else ''
    text_align = 'right' if is_rtl else 'left'

    if greeting_override is not None:
        greeting = greeting_override
    elif celebratory:
        greeting = CELEBRATORY_GREETINGS.get(lang, CELEBRATORY_GREETINGS['en'])
    else:
        greeting = GREETINGS.get(lang, GREETINGS['en'])

    if signoff_override is not None:
        signoff = signoff_override
    elif celebratory:
        signoff = CELEBRATORY_SIGNOFFS.get(lang, CELEBRATORY_SIGNOFFS['en'])
    else:
        signoff = SIGNOFFS.get(lang, SIGNOFFS['en'])

    footer = footer_text(lang, app_name)
    c1, c2 = GRADIENTS.get(gradient, GRADIENTS['invite'])

    body_html_parts = []
    for i, p in enumerate(paragraphs):
        is_ps = any(marker in p for marker in ('P.S', 'P.D', 'P.S.', 'PS:', 'PS：'))
        if is_ps:
            body_html_parts.append(
                f'<div style="margin:24px 0 0;padding:14px 18px;background:#FAF6F0;'
                f'border-radius:10px;border:1px solid #FDE7D2;text-align:{text_align};">'
                f'<p style="margin:0;font-size:15px;color:#867E76;line-height:1.7;">{p}</p></div>'
            )
            continue
        size = '19px' if i == 0 else '17px'
        color = '#2A2520' if i == 0 else '#867E76'
        weight = 'font-weight:600;' if i == 0 else ''
        body_html_parts.append(
            f'<p style="margin:0 0 22px;font-size:{size};color:{color};line-height:1.7;'
            f'{weight}text-align:{text_align};">{p}</p>'
        )
    body_html = ''.join(body_html_parts)

    return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2A2520;max-width:600px;margin:0 auto;padding:40px 24px;background:#FAF6F0;text-align:{text_align};">
  <div style="text-align:center;margin:0 0 28px;">
    <div style="display:inline-block;width:56px;height:56px;border-radius:16px;background:linear-gradient(135deg,{c1} 0%,{c2} 100%);line-height:56px;font-size:28px;">🌱</div>
    <p style="margin:12px 0 0;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#867E76;">{app_name}</p>
  </div>
  <p style="margin:0 0 24px;font-size:17px;color:#867E76;text-align:{text_align};">{greeting}</p>
  {body_html}
  <div style="text-align:center;margin:36px 0;">
    <a href="{cta_url}" style="display:inline-block;background:linear-gradient(135deg,{c1} 0%,{c2} 100%);color:#fff;padding:16px 32px;text-decoration:none;border-radius:12px;font-weight:700;font-size:16px;">{cta_text}</a>
  </div>
  <p style="margin:32px 0 0;font-size:17px;color:#867E76;text-align:{text_align};">{signoff}<br><strong style="color:#2A2520;">{sender_name}</strong></p>
  <div style="margin-top:48px;padding-top:24px;border-top:1px solid #FDE7D2;text-align:center;"><p style="margin:0;font-size:12px;color:#C4BAB0;">{footer}</p></div>
</body>
</html>'''
