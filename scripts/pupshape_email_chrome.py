#!/usr/bin/env python3
"""
Shared HTML chrome for every PupShape retention email.

Each sender produces three plain strings:
  - localized subject
  - localized list of body paragraphs
  - localized CTA label

This module wraps those into a polished HTML email with:
  - warm pet-parent palette (cream background, orange-coral gradient CTA)
  - dog photo header (the visceral hook — every email leads with the dog)
  - the right greeting + signoff for the language
  - a footer with unsubscribe + signup context

Centralizing the chrome means a copy/styling fix in one place updates
every PupShape email at once.
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


# Warm-cream PupShape palette. All gradients land between these two
# accents so colour stays brand-consistent even when senders pick
# different emotional registers.
GRADIENTS = {
    'celebrate':   ('#FFB347', '#FF6B6B'),  # Orange→coral — milestones, weigh-in
    'urgent':      ('#FF6B6B', '#E63946'),  # Coral→red — streak risk
    'invite':      ('#FFB347', '#FF8C42'),  # Warm gold — gentle CTA
    'upgrade':     ('#7C3AED', '#5B21B6'),  # Violet — paywall / monetization
    'winback':     ('#EC4899', '#BE185D'),  # Pink — re-engagement
    'progress':    ('#0EA5E9', '#0369A1'),  # Sky — weekly recap / stats
}


# Default fallback dog illustration when the user hasn't uploaded a
# photo. Hosted publicly so email clients can embed it without auth.
# Update this URL when the assets get a CDN mirror.
DEFAULT_DOG_ART = 'https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=400&q=80'


def render(language: str,
           paragraphs,
           cta_text: str,
           cta_url: str,
           sender_name: str = 'Bailey',
           app_name: str = 'PupShape',
           gradient: str = 'invite',
           celebratory: bool = False,
           dog_image_url: str = '',
           dog_name: str = '',
           greeting_override: str = None,
           signoff_override: str = None) -> str:
    """Render the full HTML body for a PupShape retention email.

    `language` may be any code; falls back to 'en' if unsupported.
    `dog_image_url` is rendered as a circular 160px hero at the top of
    the email — pull from `users.{uid}.dogs.{dogId}.imageUrl`. Falls
    back to a generic painterly dog if empty.
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
    hero_image = dog_image_url.strip() or DEFAULT_DOG_ART

    body_html_parts = []
    for i, p in enumerate(paragraphs):
        is_ps = any(marker in p for marker in (
            'P.S', 'P.D', 'P.S.', 'PS:', 'PS：',
        ))
        if is_ps:
            body_html_parts.append(
                f'<div style="margin:24px 0 0;padding:14px 18px;background:#FFF8E7;'
                f'border-radius:10px;border:1px solid #FFE5A0;text-align:{text_align};">'
                f'<p style="margin:0;font-size:15px;color:#92400e;line-height:1.7;">{p}</p></div>'
            )
            continue
        size = '19px' if i == 0 else '17px'
        color = '#1E293B' if i == 0 else '#475569'
        weight = 'font-weight:600;' if i == 0 else ''
        body_html_parts.append(
            f'<p style="margin:0 0 22px;font-size:{size};color:{color};line-height:1.7;'
            f'{weight}text-align:{text_align};">{p}</p>'
        )
    body_html = ''.join(body_html_parts)

    hero_html = (
        f'<div style="text-align:center;margin:0 0 28px;">'
        f'<div style="display:inline-block;padding:4px;background:linear-gradient(135deg,{c1} 0%,{c2} 100%);border-radius:50%;">'
        f'<img src="{hero_image}" alt="{dog_name or "your dog"}" '
        f'width="160" height="160" '
        f'style="display:block;width:160px;height:160px;border-radius:50%;object-fit:cover;background:#fff;" />'
        f'</div></div>'
    )

    return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:40px 24px;background:#FAF8F4;color:#1E293B;text-align:{text_align};">
    {hero_html}
    <p style="margin:0 0 24px;font-size:18px;color:#64748B;">{greeting}</p>
    {body_html}
    <div style="text-align:center;margin:36px 0;">
        <a href="{cta_url}" style="display:inline-block;background:linear-gradient(135deg,{c1} 0%,{c2} 100%);color:#fff;padding:16px 44px;text-decoration:none;border-radius:12px;font-weight:700;font-size:17px;">{cta_text} →</a>
    </div>
    <p style="margin:32px 0 0;font-size:17px;color:#475569;">{signoff}<br><strong>{sender_name}</strong> · Coach at {app_name}</p>
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #E2E8F0;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:#94A3B8;">PupShape · San Francisco, CA 94117</p>
        <p style="margin:0 0 8px;font-size:12px;color:#94A3B8;">{footer}</p>
        <p style="margin:0;font-size:12px;color:#94A3B8;"><a href="%mailing_list_unsubscribe_url%" style="color:#64748B;text-decoration:underline;">Unsubscribe</a></p>
    </div>
</body>
</html>'''
