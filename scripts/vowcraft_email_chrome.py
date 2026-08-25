#!/usr/bin/env python3
"""Vowcraft email chrome — warm canvas, rose accent."""
import os
from pathlib import Path

from localize_phrase import GREETINGS, SIGNOFFS, footer_text, normalize_language

ROSE = '#9B4D4D'
INK = '#1A1512'
MUTED = '#6B635C'
CANVAS = '#FAF7F4'
CARD = '#FFFFFF'
SOFT = '#F5E8E6'
DIVIDER = '#E8E2DB'

_ICON_HTTPS = os.getenv('VOWCRAFT_EMAIL_ICON_URL') or ''
_ICON_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'vowcraft' / 'icon-email.png'


def _logo_src() -> str:
    if _ICON_HTTPS:
        return _ICON_HTTPS
    if _ICON_PATH.exists():
        import base64
        raw = _ICON_PATH.read_bytes()
        return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')
    return ''


def render(language: str,
           paragraphs,
           cta_text: str,
           cta_url: str,
           sender_name: str = 'Vowcraft',
           app_name: str = 'Vowcraft',
           gradient: str = 'invite',
           greeting_override: str = None,
           signoff_override: str = None) -> str:
    lang = normalize_language(language)
    greeting = greeting_override if greeting_override is not None else GREETINGS.get(lang, GREETINGS['en'])
    signoff = signoff_override if signoff_override is not None else SIGNOFFS.get(lang, SIGNOFFS['en'])
    footer = footer_text(lang, app_name)
    logo = _logo_src()
    _ = gradient

    body_html_parts = []
    for i, p in enumerate(paragraphs):
        is_ps = any(marker in p for marker in ('P.S', 'P.D', 'P.S.', 'PS:'))
        if is_ps:
            body_html_parts.append(
                f'<div style="margin:24px 0 0;padding:14px 18px;background:{SOFT};'
                f'border-radius:10px;border:1px solid #E8C4C4;">'
                f'<p style="margin:0;font-size:15px;color:{ROSE};line-height:1.7;">{p}</p></div>'
            )
            continue
        size = '18px' if i == 0 else '16px'
        color = INK if i == 0 else MUTED
        weight = 'font-weight:600;' if i == 0 else ''
        body_html_parts.append(
            f'<p style="margin:0 0 20px;font-size:{size};color:{color};line-height:1.7;'
            f'{weight}">{p}</p>'
        )
    body_html = ''.join(body_html_parts)
    if logo:
        logo_html = (
            f'<img src="{logo}" alt="{app_name}" width="48" height="48" '
            f'style="display:block;margin:0 auto;width:48px;height:48px;'
            f'border-radius:12px;border:1px solid {DIVIDER};background:{CARD};" />'
        )
    else:
        logo_html = (
            f'<div style="display:inline-block;padding:8px 14px;border-radius:8px;'
            f'background:{ROSE};color:#fff;font-size:13px;font-weight:700;'
            f'letter-spacing:0.04em;">Vowcraft</div>'
        )

    return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <meta name="color-scheme" content="light">
</head>
<body style="margin:0;padding:0;background:{CANVAS};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CANVAS};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:{CARD};border-radius:12px;overflow:hidden;border:1px solid {DIVIDER};">
          <tr>
            <td style="padding:28px 32px 8px;text-align:center;">{logo_html}
              <p style="margin:12px 0 0;font-size:18px;font-weight:700;color:{INK};letter-spacing:-0.02em;">Vowcraft</p>
              <p style="margin:4px 0 0;font-size:13px;color:{MUTED};">Write the speech. Rehearse it. Mean it.</p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 32px 8px;">
              <p style="margin:0 0 20px;font-size:16px;color:{MUTED};">{greeting}</p>
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 32px;text-align:center;">
              <a href="{cta_url}" style="display:inline-block;background:{ROSE};color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:15px;">{cta_text}</a>
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 28px;">
              <p style="margin:0;font-size:15px;color:{MUTED};">{signoff}<br><strong style="color:{INK};">{sender_name}</strong></p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px;background:{CANVAS};border-top:1px solid {DIVIDER};text-align:center;">
              <p style="margin:0;font-size:12px;color:#A39A92;">{footer}</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''
