#!/usr/bin/env python3
"""ONG email chrome — NGL-style white canvas, black wordmark, red seal."""
import os
from pathlib import Path

from localize_phrase import GREETINGS, SIGNOFFS, footer_text, normalize_language

_ICON_HTTPS = (
    os.getenv('ONG_EMAIL_ICON_URL')
    or 'https://cdn.jsdelivr.net/gh/synysterkay/ultratechapps@main/assets/ong/icon-email.png'
)
_ICON_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'ong' / 'icon-email.png'


def _logo_src() -> str:
    https = (_ICON_HTTPS or '').strip()
    if https:
        return https
    if _ICON_PATH.exists():
        import base64
        raw = _ICON_PATH.read_bytes()
        return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')
    return ''


def render(language: str,
           paragraphs,
           cta_text: str,
           cta_url: str,
           sender_name: str = 'ONG',
           app_name: str = 'ONG',
           gradient: str = 'invite',
           greeting_override: str = None,
           signoff_override: str = None) -> str:
    lang = normalize_language(language)
    greeting = greeting_override if greeting_override is not None else GREETINGS.get(lang, GREETINGS['en'])
    signoff = signoff_override if signoff_override is not None else SIGNOFFS.get(lang, SIGNOFFS['en'])
    footer = footer_text(lang, app_name)
    logo = _logo_src()
    _ = gradient  # kept so callers can pass intent without breaking

    body_html_parts = []
    for i, p in enumerate(paragraphs):
        is_ps = any(marker in p for marker in ('P.S', 'P.D', 'P.S.', 'PS:'))
        if is_ps:
            body_html_parts.append(
                f'<div style="margin:24px 0 0;padding:14px 18px;background:#F4F4F4;'
                f'border-radius:10px;border:1px solid #E8E8E8;">'
                f'<p style="margin:0;font-size:15px;color:#8A8A8A;line-height:1.7;">{p}</p></div>'
            )
            continue
        size = '19px' if i == 0 else '17px'
        color = '#111111' if i == 0 else '#8A8A8A'
        weight = 'font-weight:700;' if i == 0 else ''
        body_html_parts.append(
            f'<p style="margin:0 0 22px;font-size:{size};color:{color};line-height:1.7;'
            f'{weight}">{p}</p>'
        )
    body_html = ''.join(body_html_parts)
    logo_html = ''
    if logo:
        logo_html = (
            f'<img src="{logo}" alt="{app_name}" width="56" height="56" '
            f'style="display:block;margin:0 auto;width:56px;height:56px;'
            f'border-radius:14px;border:1px solid #E8E8E8;background:#FFFFFF;" />'
        )
    else:
        logo_html = (
            '<div style="display:inline-block;width:56px;height:56px;border-radius:14px;'
            'background:#111111;line-height:56px;font-size:13px;font-weight:800;'
            'letter-spacing:0.12em;color:#fff;">ONG</div>'
        )

    return f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#111111;max-width:600px;margin:0 auto;padding:40px 24px;background:#FFFFFF;">
  <div style="text-align:center;margin:0 0 28px;">{logo_html}</div>
  <p style="margin:0 0 24px;font-size:17px;color:#8A8A8A;">{greeting}</p>
  {body_html}
  <div style="text-align:center;margin:36px 0;">
    <a href="{cta_url}" style="display:inline-block;background:#111111;color:#fff;padding:16px 32px;text-decoration:none;border-radius:28px;font-weight:700;font-size:16px;">{cta_text}</a>
  </div>
  <p style="margin:32px 0 0;font-size:17px;color:#8A8A8A;">{signoff}<br><strong style="color:#111111;">{sender_name}</strong></p>
  <div style="margin-top:48px;padding-top:24px;border-top:1px solid #E8E8E8;text-align:center;"><p style="margin:0;font-size:12px;color:#B3B3B3;">{footer}</p></div>
</body>
</html>'''
