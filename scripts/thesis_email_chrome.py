#!/usr/bin/env python3
"""
Shared HTML chrome for every Thesis Generator retention email.

Each sender produces three plain strings:
  - localized subject
  - localized list of body paragraphs
  - localized CTA label

This module wraps those into a polished HTML email with:
  - the right text direction (RTL for Arabic)
  - the right greeting + signoff for the language
  - a footer with unsubscribe + signup context
  - a CTA button with the email's chosen accent gradient

Centralizing the chrome means a copy / styling fix in one place updates
every Thesis Generator email at once — no more 8 senders with slightly
different `<body style=…>` strings to keep in sync.
"""
from localize_phrase import (
    GREETINGS,
    SIGNOFFS,
    CELEBRATORY_GREETINGS,
    CELEBRATORY_SIGNOFFS,
    RTL_LANGUAGES,
    footer_text,
    normalize_language,
)


# Reusable colour ramps, keyed by intent. Senders pick the one that matches
# the email's emotional register.
GRADIENTS = {
    'celebrate':   ('#10b981', '#059669'),  # Green — completions, milestones
    'urgent':      ('#f97316', '#ea580c'),  # Orange — deadlines, streak risk
    'invite':      ('#2563eb', '#1d4ed8'),  # Blue — gentle CTA / open the app
    'upgrade':     ('#7c3aed', '#5b21b6'),  # Violet — paywall / monetization
    'winback':     ('#ec4899', '#be185d'),  # Pink — re-engagement
    'progress':    ('#0ea5e9', '#0369a1'),  # Sky — weekly recap / stats
}


def _cta_button(text: str, url: str, bg: str) -> str:
    return (
        f'<a href="{url}" style="display:inline-block;background:{bg};color:#fff;'
        f'padding:16px 44px;text-decoration:none;border-radius:8px;font-weight:700;'
        f'font-size:17px;">{text} →</a>'
    )


def _cta_section(
    cta_text: str,
    cta_url: str,
    c1: str,
    c2: str,
    cta_links: list[dict] | None = None,
) -> str:
    if not cta_links:
        bg = f'linear-gradient(135deg,{c1} 0%,{c2} 100%)'
        return (
            f'<div style="text-align:center;margin:36px 0;">'
            f'{_cta_button(cta_text, cta_url, bg)}'
            f'</div>'
        )
    play_c1, play_c2 = GRADIENTS['celebrate']
    web_c1, web_c2 = GRADIENTS['invite']
    variants = {
        'primary': f'linear-gradient(135deg,{c1} 0%,{c2} 100%)',
        'play': f'linear-gradient(135deg,{play_c1} 0%,{play_c2} 100%)',
        'web': f'linear-gradient(135deg,{web_c1} 0%,{web_c2} 100%)',
    }
    buttons = '\n'.join(
        f'<div style="margin:0 0 12px 0;">'
        f'{_cta_button(link["text"], link["url"], variants.get(link.get("variant", "primary"), variants["primary"]))}'
        f'</div>'
        for link in cta_links
    )
    return f'<div style="text-align:center;margin:36px 0;">{buttons}</div>'


def render(language: str,
           paragraphs,
           cta_text: str,
           cta_url: str,
           sender_name: str = 'Ana',
           app_name: str = 'Thesis Generator',
           gradient: str = 'invite',
           celebratory: bool = False,
           greeting_override: str = None,
           signoff_override: str = None,
           cta_links: list[dict] | None = None) -> str:
    """Render the full HTML body for a retention email.

    `language` may be any code; falls back to 'en' if unsupported.
    `paragraphs` is the localized list of body paragraphs (already interpolated).
    """
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
        # Highlight P.S. / postscript style asides as a soft yellow callout
        # — the same treatment the existing first-thesis-complete sender uses.
        is_ps = any(marker in p for marker in (
            'P.S', 'P.D', 'ملاحظة', 'P.D.', 'P. S', 'P. D',
            '附言', 'P.S.', 'PS:', 'PS：', 'تنبيه',
        ))
        if is_ps:
            body_html_parts.append(
                f'<div style="margin:24px 0 0;padding:14px 18px;background:#fffbeb;'
                f'border-radius:8px;border:1px solid #fcd34d;text-align:{text_align};">'
                f'<p style="margin:0;font-size:15px;color:#92400e;line-height:1.7;">{p}</p></div>'
            )
            continue
        size = '19px' if i == 0 else '17px'
        color = '#0f172a' if i == 0 else '#374151'
        weight = 'font-weight:600;' if i == 0 else ''
        body_html_parts.append(
            f'<p style="margin:0 0 22px;font-size:{size};color:{color};line-height:1.7;'
            f'{weight}text-align:{text_align};">{p}</p>'
        )
    body_html = ''.join(body_html_parts)
    cta_html = _cta_section(cta_text, cta_url, c1, c2, cta_links)

    return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;color:#2d3748;text-align:{text_align};">
    <p style="margin:0 0 24px;font-size:18px;color:#6b7280;">{greeting}</p>
    {body_html}
    {cta_html}
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;">{signoff}<br><strong>{sender_name}</strong></p>
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:#d1d5db;">San Francisco, CA 94117, United States</p>
        <p style="margin:0 0 8px;font-size:12px;color:#d1d5db;">{footer}</p>
        <p style="margin:0;font-size:12px;color:#9ca3af;"><a href="%mailing_list_unsubscribe_url%" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a></p>
    </div>
</body>
</html>'''
