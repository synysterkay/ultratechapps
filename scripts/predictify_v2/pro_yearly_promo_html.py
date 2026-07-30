"""Dark-theme HTML for Predictify Soccer yearly Pro promo blast."""
from __future__ import annotations

import html
from datetime import datetime, timezone


APP_STORE_URL = 'https://apps.apple.com/app/predictify-football-ai/id6756571193'
GOOGLE_PLAY_URL = 'https://play.google.com/store/apps/details?id=com.predictify.soccer.prediction'
UPGRADE_DEEPLINK = 'predictify://upgrade?ref=yearly_promo_test'
SITE_URL = 'https://predictifyfootball.com'

SUBJECT = 'We weren\u2019t supposed to send this'
PREVIEW = 'This month only \u2014 our plans at over 50% better value. Open before it ends.'


def _esc(s: str) -> str:
    return html.escape(s or '')


def _month_end_label() -> str:
    now = datetime.now(timezone.utc)
    import calendar
    last = calendar.monthrange(now.year, now.month)[1]
    return now.strftime('%B ') + str(last)


def build_pro_yearly_promo_html(
    first_name: str = 'there',
    unsub_url: str = f'{SITE_URL}/unsubscribe',
    *,
    test_banner: bool = False,
) -> str:
    month_end = _month_end_label()
    test_note = ''
    if test_banner:
        test_note = (
            '<div style="margin:0 0 20px;padding:10px 14px;background:#1e293b;'
            'border:1px dashed #64748b;border-radius:8px;font-size:12px;color:#94a3b8;'
            'text-align:center">TEST PREVIEW \u2014 not a live promo send</div>'
        )

    benefits = [
        'Full match desk: 1X2, goals, BTTS &amp; specialist markets',
        'Probabilities, xG &amp; score projections',
        'Evidence + confidence before kickoff',
        'Deep AI breakdowns on every match you open',
    ]
    benefit_rows = ''.join(
        f'<tr><td style="padding:0 0 14px 0;vertical-align:top;width:28px">'
        f'<span style="display:inline-block;width:22px;height:22px;border-radius:50%;'
        f'background:#3B82F6;color:#fff;font-size:13px;line-height:22px;text-align:center">'
        f'&#10003;</span></td>'
        f'<td style="padding:0 0 14px 0;color:#F4F6F8;font-size:15px;line-height:1.5">'
        f'{b}</td></tr>'
        for b in benefits
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(SUBJECT)}</title>
</head>
<body style="margin:0;padding:0;background:#06080C;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{_esc(PREVIEW)}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#06080C">
<tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px">

<tr><td style="padding:0 0 24px 0">
  <div style="font-size:11px;font-weight:700;letter-spacing:0.12em;color:#FFBF24;text-transform:uppercase;margin-bottom:12px">THIS MONTH ONLY</div>
  <div style="font-size:22px;font-weight:800;color:#F4F6F8">Predictify</div>
  <div style="font-size:11px;color:#9AA4B2;margin-top:8px;letter-spacing:0.08em">MATCH DESK READY</div>
</td></tr>

{test_note}

<tr><td style="padding:0 0 8px 0">
  <h1 style="margin:0;font-size:28px;line-height:1.25;font-weight:800;color:#F4F6F8">We weren&rsquo;t supposed to send this.</h1>
</td></tr>

<tr><td style="padding:0 0 24px 0">
  <p style="margin:0;font-size:16px;line-height:1.6;color:#9AA4B2">Hey {_esc(first_name)} &mdash; this month only, our plans are at over <strong style="color:#F4F6F8">50% better value</strong> than before. Same full match desk. Easier to unlock for a limited window.</p>
</td></tr>

<tr><td style="padding:0 0 28px 0">
  <div style="padding:16px 18px;background:#0E1218;border-radius:10px;border-left:4px solid #3B82F6">
    <p style="margin:0;font-size:14px;line-height:1.55;color:#F4F6F8"><strong>Promo closes {month_end}.</strong> Then standard pricing returns.</p>
  </div>
</td></tr>

<tr><td style="padding:0 0 8px 0">
  <div style="font-size:13px;font-weight:700;letter-spacing:0.06em;color:#9AA4B2;text-transform:uppercase;margin-bottom:16px">What you get</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{benefit_rows}</table>
</td></tr>

<tr><td style="padding:8px 0 28px 0;text-align:center">
  <p style="margin:0;font-size:15px;line-height:1.6;color:#9AA4B2;font-style:italic">Every fixture hits different. Read it before kickoff.</p>
</td></tr>

<tr><td style="padding:0 0 20px 0;text-align:center">
  <a href="{_esc(UPGRADE_DEEPLINK)}" style="display:inline-block;padding:16px 32px;background:#3B82F6;color:#ffffff;text-decoration:none;border-radius:12px;font-weight:700;font-size:16px">Open Predictify</a>
  <p style="margin:12px 0 0;font-size:13px;color:#9AA4B2">See plans in-app &mdash; cancel anytime</p>
</td></tr>

<tr><td style="padding:0 0 32px 0;text-align:center">
  <table role="presentation" cellspacing="0" cellpadding="0" align="center"><tr>
    <td style="padding:6px">
      <a href="{_esc(APP_STORE_URL)}" style="display:inline-block;padding:12px 20px;background:transparent;color:#F4F6F8;text-decoration:none;border-radius:10px;font-weight:600;font-size:14px;border:1px solid #3B82F6">Open on App Store</a>
    </td>
    <td style="padding:6px">
      <a href="{_esc(GOOGLE_PLAY_URL)}" style="display:inline-block;padding:12px 20px;background:transparent;color:#F4F6F8;text-decoration:none;border-radius:10px;font-weight:600;font-size:14px;border:1px solid #3B82F6">Open on Google Play</a>
    </td>
  </tr></table>
</td></tr>

<tr><td style="padding:24px 0 0 0;border-top:1px solid #1a2030">
  <p style="margin:0 0 8px 0;font-size:12px;line-height:1.6;color:#64748b;text-align:center">Cancel anytime. Live scores stay free &mdash; paid plans unlock the desk before kickoff.</p>
  <p style="margin:0 0 8px 0;font-size:12px;line-height:1.6;color:#64748b;text-align:center">Not a bookmaker. No guaranteed wins &mdash; transparent forecasts you can verify.</p>
  <p style="margin:0;font-size:12px;line-height:1.6;color:#64748b;text-align:center">
    <a href="{_esc(SITE_URL)}" style="color:#9AA4B2">predictifyfootball.com</a>
    &nbsp;&middot;&nbsp;
    <a href="{_esc(unsub_url)}" style="color:#9AA4B2">Unsubscribe</a>
  </p>
  <p style="margin:12px 0 0;font-size:11px;color:#475569;text-align:center">&mdash; Predictify</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''


def build_pro_yearly_promo_text(first_name: str = 'there', unsub_url: str = f'{SITE_URL}/unsubscribe') -> str:
    month_end = _month_end_label()
    return f'''PREDICTIFY — THIS MONTH ONLY

We weren't supposed to send this.

Hey {first_name} — this month only, our plans are at over 50% better value than before.

Promo closes {month_end}. Then standard pricing returns.

What you get:
• Full match desk: 1X2, goals, BTTS & specialist markets
• Probabilities, xG & score projections
• Evidence + confidence before kickoff
• Deep AI breakdowns on every match you open

Open Predictify: {UPGRADE_DEEPLINK}
App Store: {APP_STORE_URL}
Google Play: {GOOGLE_PLAY_URL}

Cancel anytime. Not a bookmaker. No guaranteed wins.
Unsubscribe: {unsub_url}
'''
