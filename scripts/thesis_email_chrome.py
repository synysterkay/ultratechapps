#!/usr/bin/env python3
"""
Shared HTML chrome for every Thesis Generator retention email.

Matches the mobile app design system (lib/design/tokens.dart):
  - Navy #1E3A8A + gold #D4A04C brand
  - Warm ivory canvas #F7F5F0, white cards, Inter Tight typography
  - Table-based layout for reliable rendering in Gmail / Apple Mail

Each sender produces localized subject, body paragraphs, and CTA label;
this module wraps them into polished HTML with RTL support, branded header,
and footer with unsubscribe context.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from localize_phrase import (
    GREETINGS,
    SIGNOFFS,
    CELEBRATORY_GREETINGS,
    CELEBRATORY_SIGNOFFS,
    RTL_LANGUAGES,
    footer_text,
    normalize_language,
)

# ─── Brand tokens (AppColors light theme) ───────────────────────────────────
# Canvas matched to app-icon cream (sampled from assets/thesis/icon-email.png)
CANVAS = '#F9F1E3'
CARD = '#FFFFFF'
RECESSED = '#F0E6D6'
INK_PRIMARY = '#111827'
INK_SECONDARY = '#6B7280'
INK_MUTED = '#9CA3AF'
BRAND_NAVY = '#1E3A8A'
BRAND_NAVY_ALT = '#2847A3'
BRAND_GOLD = '#D4A04C'
BRAND_SOFT = '#E7EBF7'
GOLD_SOFT = '#FAF1E1'
DIVIDER = '#E5E7EB'

FONT_STACK = (
    "'Inter Tight',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
    "Helvetica,Arial,sans-serif"
)

_ICON_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'thesis' / 'icon-email.png'
# Gmail / Apple Mail often block data: URIs — prefer a public HTTPS mark.
_ICON_HTTPS = (
    os.getenv('THESIS_EMAIL_ICON_URL')
    or 'https://cdn.jsdelivr.net/gh/synysterkay/ultratechapps@main/assets/thesis/icon-email.png'
)
_LOGO_DATA_URI: str | None = None

# Reusable colour ramps keyed by email intent. Primary CTAs use brand navy→gold.
GRADIENTS = {
    'celebrate':   (BRAND_NAVY, BRAND_GOLD),
    'urgent':      ('#EA580C', '#F59E0B'),
    'invite':      (BRAND_NAVY, BRAND_GOLD),
    'upgrade':     (BRAND_NAVY, BRAND_GOLD),
    'winback':     (BRAND_NAVY_ALT, BRAND_GOLD),
    'progress':    ('#0369A1', '#0EA5E9'),
}


def _logo_src() -> str:
    """Brand mark URL for email clients.

    Prefer HTTPS (Gmail strips data: image URIs → empty square). Fall back to
    an inlined data URI only if the remote URL env is explicitly cleared.
    """
    https = (_ICON_HTTPS or '').strip()
    if https:
        return https
    global _LOGO_DATA_URI
    if _LOGO_DATA_URI is None:
        try:
            raw = _ICON_PATH.read_bytes()
            b64 = base64.b64encode(raw).decode('ascii')
            _LOGO_DATA_URI = f'data:image/png;base64,{b64}'
        except OSError:
            _LOGO_DATA_URI = ''
    return _LOGO_DATA_URI


def _esc(text: str) -> str:
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _cta_button(text: str, url: str, *, bg: str, outline: bool = False) -> str:
    if outline:
        return (
            f'<a href="{url}" style="display:inline-block;padding:14px 28px;'
            f'color:{BRAND_NAVY};text-decoration:none;border-radius:18px;'
            f'font-weight:600;font-size:15px;border:1.5px solid {BRAND_NAVY};'
            f'background:{CARD};">{text}</a>'
        )
    return (
        f'<a href="{url}" style="display:inline-block;background:{bg};color:#fff;'
        f'padding:16px 36px;text-decoration:none;border-radius:18px;font-weight:700;'
        f'font-size:16px;letter-spacing:0.01em;box-shadow:0 4px 14px rgba(30,58,138,0.22);">'
        f'{text} &rarr;</a>'
    )


def _ios_store_button(url: str, line1: str = 'Download on the', line2: str = 'App Store') -> str:
    # Matched pair with Android — same height, dark fill, equal weight
    return (
        f'<a href="{url}" style="display:block;text-decoration:none;background:#111827;'
        f'border-radius:12px;padding:12px 16px;color:#ffffff;min-height:52px;'
        f'border:1.5px solid #111827;box-sizing:border-box;text-align:center;">'
        f'<div style="font-size:9px;line-height:1.2;opacity:0.85;letter-spacing:0.04em;">'
        f'{_esc(line1)}</div>'
        f'<div style="font-size:15px;line-height:1.25;font-weight:700;letter-spacing:-0.01em;margin-top:2px;">'
        f'{_esc(line2)}</div>'
        f'</a>'
    )


def _android_store_button(url: str, line1: str = 'GET IT ON', line2: str = 'Google Play') -> str:
    # Same visual weight as iOS (dark fill) for equal CTAs
    return (
        f'<a href="{url}" style="display:block;text-decoration:none;background:#111827;'
        f'border-radius:12px;padding:12px 16px;color:#ffffff;min-height:52px;'
        f'border:1.5px solid #111827;box-sizing:border-box;text-align:center;">'
        f'<div style="font-size:9px;line-height:1.2;opacity:0.85;letter-spacing:0.08em;">'
        f'{_esc(line1)}</div>'
        f'<div style="font-size:15px;line-height:1.25;font-weight:700;letter-spacing:-0.01em;margin-top:2px;">'
        f'{_esc(line2)}</div>'
        f'</a>'
    )


def _store_buttons_row(links: list[dict]) -> str:
    """Store badges in the order given (Play first for Android-only lists)."""
    buttons = []
    seen = set()
    for link in links:
        variant = link.get('variant', '')
        url = link.get('url') or ''
        if not url:
            continue
        if variant in {'ios', 'app_store'} and 'ios' not in seen:
            seen.add('ios')
            buttons.append(_ios_store_button(
                url,
                link.get('line1', 'Download on the'),
                link.get('line2', link.get('text', 'App Store')),
            ))
        elif variant in {'android', 'play', 'google_play'} and 'android' not in seen:
            seen.add('android')
            buttons.append(_android_store_button(
                url,
                link.get('line1', 'GET IT ON'),
                link.get('line2', link.get('text', 'Google Play')),
            ))
    if not buttons:
        return ''
    if len(buttons) == 1:
        return f'<div style="margin:32px auto 8px auto;max-width:280px;">{buttons[0]}</div>'
    cells = ''.join(
        f'<td width="50%" style="padding:{("0 6px 0 0" if i == 0 else "0 0 0 6px")};'
        f'vertical-align:top;">{btn}</td>'
        for i, btn in enumerate(buttons[:2])
    )
    return (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        f'style="margin:32px 0 8px 0;"><tr>{cells}</tr></table>'
    )


def _cta_section(
    cta_text: str,
    cta_url: str,
    c1: str,
    c2: str,
    cta_links: list[dict] | None = None,
) -> str:
    primary_bg = f'linear-gradient(135deg,{c1} 0%,{c2} 100%)'
    if cta_links:
        variants = {link.get('variant', 'primary') for link in cta_links}
        if variants & {'ios', 'android', 'app_store', 'google_play', 'play'}:
            store_html = _store_buttons_row(cta_links)
            if store_html:
                return store_html
        buttons = []
        for link in cta_links:
            variant = link.get('variant', 'primary')
            if variant == 'primary':
                btn = _cta_button(link['text'], link['url'], bg=primary_bg)
            else:
                btn = _cta_button(link['text'], link['url'], bg='', outline=True)
            buttons.append(f'<div style="margin:0 0 12px 0;">{btn}</div>')
        return f'<div style="text-align:center;margin:32px 0 8px 0;">{"".join(buttons)}</div>'
    return (
        f'<div style="text-align:center;margin:32px 0 8px 0;">'
        f'{_cta_button(cta_text, cta_url, bg=primary_bg)}'
        f'</div>'
    )


def _header_html(app_name: str, text_align: str, logo_size: int = 52) -> str:
    logo = _logo_src()
    logo_cell = ''
    if logo:
        logo_cell = (
            f'<td style="vertical-align:middle;padding:0 14px 0 0;width:{logo_size + 8}px">'
            f'<img src="{logo}" alt="{_esc(app_name)}" width="{logo_size}" height="{logo_size}" '
            f'style="display:block;border-radius:12px;width:{logo_size}px;height:{logo_size}px;'
            f'border:1px solid rgba(17,24,39,0.06);" />'
            f'</td>'
        )
    return (
        f'<tr><td style="padding:0 0 20px 0;text-align:{text_align}">'
        f'<table role="presentation" cellspacing="0" cellpadding="0">'
        f'<tr>{logo_cell}'
        f'<td style="vertical-align:middle">'
        f'<div style="font-size:18px;font-weight:700;color:{INK_PRIMARY};'
        f'letter-spacing:-0.02em;line-height:1.2;">{_esc(app_name)}</div>'
        f'<div style="font-size:10px;font-weight:500;color:{INK_SECONDARY};'
        f'letter-spacing:0.14em;text-transform:uppercase;margin-top:5px;">'
        f'Research Operating System</div>'
        f'</td></tr></table>'
        f'</td></tr>'
    )


def _paragraph_html(p: str, index: int, text_align: str) -> str:
    """Render one body paragraph; supports [[LEAD]] / [[VALUE]] / [[SUB]] markers."""
    raw = p or ''
    is_ps = any(marker in raw for marker in (
        'P.S', 'P.D', 'ملاحظة', 'P.D.', 'P. S', 'P. D',
        '附言', 'P.S.', 'PS:', 'PS：', 'تنبيه',
    ))
    if is_ps:
        return (
            f'<div style="margin:24px 0 0;padding:14px 18px;background:{GOLD_SOFT};'
            f'border-radius:10px;border-left:3px solid {BRAND_GOLD};'
            f'text-align:{text_align};">'
            f'<p style="margin:0;font-size:15px;color:#78350F;line-height:1.6;font-style:italic;">'
            f'{_esc(raw)}</p></div>'
        )

    style = 'body'
    for marker, name in (
        ('[[LEAD]]', 'lead'),
        ('[[VALUE]]', 'value'),
        ('[[SUB]]', 'sub'),
    ):
        if raw.startswith(marker):
            style = name
            raw = raw[len(marker):].lstrip()
            break

    # Preserve intentional line breaks in multi-line paragraphs
    html_text = '<br>'.join(_esc(line) for line in raw.split('\n'))

    if style == 'lead':
        return (
            f'<p style="margin:22px 0 8px;font-size:15px;color:{INK_SECONDARY};'
            f'line-height:1.55;font-weight:500;text-align:{text_align};">{html_text}</p>'
        )
    if style == 'value':
        return (
            f'<p style="margin:0 0 10px;font-size:19px;color:{INK_PRIMARY};'
            f'line-height:1.45;font-weight:700;letter-spacing:-0.01em;'
            f'text-align:{text_align};">{html_text}</p>'
        )
    if style == 'sub':
        return (
            f'<p style="margin:0 0 8px;font-size:14px;color:{INK_SECONDARY};'
            f'line-height:1.5;text-align:{text_align};">{html_text}</p>'
        )
    if index == 0:
        return (
            f'<p style="margin:0 0 16px;font-size:18px;color:{INK_PRIMARY};'
            f'line-height:1.5;font-weight:600;text-align:{text_align};">{html_text}</p>'
        )
    return (
        f'<p style="margin:0 0 14px;font-size:16px;color:#4B5563;'
        f'line-height:1.6;text-align:{text_align};">{html_text}</p>'
    )


def render(
    language: str,
    paragraphs,
    cta_text: str,
    cta_url: str,
    sender_name: str = 'Ana',
    app_name: str = 'Thesis Generator',
    gradient: str = 'invite',
    celebratory: bool = False,
    greeting_override: str = None,
    signoff_override: str = None,
    cta_links: list[dict] | None = None,
    preview_text: str | None = None,
    footer_override: str | None = None,
    address_override: str | None = None,
    sender_org: str | None = None,
    max_width: int = 600,
    compact: bool = False,
) -> str:
    """Render the full HTML body for a retention email.

    Optional overrides (crosspromo / acquisition):
      greeting_override=''  — hide chrome greeting (avoid double Hey)
      footer_override       — honest receive reason
      address_override      — company address line
      sender_org            — e.g. Kaynel under the sign-off name
      compact=True          — tighter outer padding + 560px card
    """
    lang = normalize_language(language)
    is_rtl = lang in RTL_LANGUAGES
    dir_attr = ' dir="rtl"' if is_rtl else ''
    lang_attr = f' lang="{lang}"'
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

    footer = footer_override if footer_override is not None else footer_text(lang, app_name)
    address = address_override if address_override is not None else 'San Francisco, CA 94117, United States'
    c1, c2 = GRADIENTS.get(gradient, GRADIENTS['invite'])

    width = 560 if compact else max_width
    outer_pad = '24px 12px 36px 12px' if compact else '36px 16px 48px 16px'
    card_pad = '28px 26px' if compact else '32px 28px'
    logo_size = 52 if compact else 48

    body_html = ''.join(
        _paragraph_html(p, i, text_align) for i, p in enumerate(paragraphs)
    )
    cta_html = _cta_section(cta_text, cta_url, c1, c2, cta_links)

    greeting_html = ''
    if (greeting or '').strip():
        greeting_html = (
            f'<p style="margin:0 0 18px;font-size:15px;color:{INK_MUTED};'
            f'text-align:{text_align};">{_esc(greeting)}</p>'
        )

    org_html = ''
    if sender_org:
        org_html = (
            f'<br><span style="font-size:14px;font-weight:500;color:{INK_SECONDARY};">'
            f'{_esc(sender_org)}</span>'
        )

    preheader = ''
    if preview_text:
        preheader = (
            f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
            f'color:transparent;mso-hide:all;">{_esc(preview_text)}</div>'
        )

    return f'''<!DOCTYPE html>
<html{lang_attr}{dir_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{_esc(app_name)}</title>
<!--[if mso]><style>body,table,td{{font-family:Arial,Helvetica,sans-serif!important;}}</style><![endif]-->
</head>
<body style="margin:0;padding:0;background:{CANVAS};font-family:{FONT_STACK};color:{INK_PRIMARY};-webkit-font-smoothing:antialiased;">
{preheader}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{CANVAS};">
<tr><td align="center" style="padding:{outer_pad};">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:{width}px;">

{_header_html(app_name, text_align, logo_size=logo_size)}

<tr><td style="background:{CARD};border-radius:20px;padding:{card_pad};box-shadow:0 1px 3px rgba(17,24,39,0.06),0 8px 24px rgba(17,24,39,0.04);border:1px solid {RECESSED};">
  {greeting_html}
  {body_html}
  {cta_html}
  <p style="margin:24px 0 0;font-size:15px;color:{INK_SECONDARY};text-align:{text_align};line-height:1.55;">{_esc(signoff)}<br><strong style="color:{INK_PRIMARY};">{_esc(sender_name)}</strong>{org_html}</p>
</td></tr>

<tr><td style="padding:22px 8px 0 8px;text-align:center;">
  <p style="margin:0 0 8px;font-size:12px;color:{INK_MUTED};line-height:1.6;">{_esc(address)}</p>
  <p style="margin:0 0 8px;font-size:12px;color:{INK_MUTED};line-height:1.6;">{_esc(footer)}</p>
  <p style="margin:0;font-size:12px;color:{INK_MUTED};">
    <a href="https://thesisgenerator.io" style="color:{BRAND_NAVY};text-decoration:none;font-weight:500;">thesisgenerator.io</a>
    &nbsp;&middot;&nbsp;
    <a href="%mailing_list_unsubscribe_url%" style="color:{INK_SECONDARY};text-decoration:underline;">Unsubscribe</a>
  </p>
  <p style="margin:14px 0 0;font-size:11px;color:{INK_MUTED};letter-spacing:0.06em;">&mdash; {_esc(sender_org or app_name)}</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''
