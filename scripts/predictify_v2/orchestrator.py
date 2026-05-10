"""
orchestrator.py — Entry point for the v2 trigger pass.

Workflow:
  1. Load all Predictify users (Firebase) + their language + activity.
  2. For each user: build context → evaluate triggers → render template.
  3. Send via Resend.
  4. Track which user got which trigger today (so we don't re-send).
  5. Return the list of (user, kind) pairs for callers/logs.

This runs BEFORE the v1 daily sequence in the existing GitHub Action — if
v2 fired an email for a user, v1 skips them today. v1 stays as fallback so
no user is silently missed.

Usage:
  python -m predictify_v2.orchestrator                # send
  python -m predictify_v2.orchestrator --dry-run      # log only
  python -m predictify_v2.orchestrator --status       # show state cache
"""
from __future__ import annotations

import os
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Allow `python -m predictify_v2.orchestrator` from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from predictify_v2.user_context import fetch_user_context  # noqa: E402
from predictify_v2.template_engine import render_template, RenderedEmail  # noqa: E402
from predictify_v2.triggers import select_trigger  # noqa: E402

try:
    from firebase_user_loader import FirebaseUserLoader  # noqa: E402
    from firestore_language_loader import FirestoreLanguageLoader  # noqa: E402
    from firestore_activity_loader import FirestoreActivityLoader  # noqa: E402
except ImportError:
    print('⚠️ Could not import firebase loaders — run from scripts/ dir')
    raise


# ─────────────────────────────────────────────────────────
#  State cache — what we've sent today
# ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / 'cache' / 'predictify_v2_state.json'
STATE_PATH.parent.mkdir(exist_ok=True)


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


# ─────────────────────────────────────────────────────────
#  Resend sender — minimal, mirrors v1 send shape
# ─────────────────────────────────────────────────────────
RESEND_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = 'Predictify <noreply@predictifyfootball.com>'


def _send(to: str, email: RenderedEmail, dry_run: bool = False) -> bool:
    if not RESEND_KEY:
        print('⚠️ RESEND_API_KEY missing')
        return False
    html = _build_html(email)
    if dry_run:
        print(f'   [DRY] would send to {to}: {email.subject!r}')
        return True
    try:
        r = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {RESEND_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'from': FROM_EMAIL,
                'to': to,
                'subject': email.subject,
                'html': html,
                'tags': [
                    {'name': 'app', 'value': 'predictify'},
                    {'name': 'kind', 'value': email.kind},
                    {'name': 'lang', 'value': email.language},
                    {'name': 'system', 'value': 'v2'},
                ],
            },
            timeout=20,
        )
        if r.status_code in (200, 201, 202):
            return True
        print(f'   ⚠️ Resend {r.status_code}: {r.text[:200]}')
        return False
    except Exception as e:
        print(f'   ⚠️ Send failed: {e}')
        return False


def _build_html(e: RenderedEmail) -> str:
    is_rtl = e.language == 'ar'
    dir_attr = ' dir="rtl"' if is_rtl else ''
    align = 'right' if is_rtl else 'left'
    paras = ''.join(
        f'<p style="margin:0 0 16px;color:#1f2937;font-size:15px;line-height:1.6;text-align:{align}">'
        f'{p.replace(chr(10), "<br>")}</p>'
        for p in e.body_paragraphs
    )
    return f'''<!DOCTYPE html><html lang="{e.language}"{dir_attr}><head><meta charset="UTF-8">
<title>{_html_escape(e.subject)}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif">
<div style="max-width:580px;margin:0 auto;background:#fff;padding:32px 24px">
<div style="font-size:22px;font-weight:800;color:#0E1117;margin-bottom:6px">⚽ Predictify</div>
<div style="height:1px;background:#e5e7eb;margin:16px 0 24px"></div>
<div style="display:none;color:#9ca3af;font-size:0">{_html_escape(e.preview_text)}</div>
{paras}
<div style="text-align:center;margin:28px 0">
<a href="https://predictifyfootball.com/?ref=email&amp;kind={e.kind}" style="display:inline-block;padding:14px 28px;background:#3B82F6;color:#fff;text-decoration:none;border-radius:10px;font-weight:700;font-size:15px">{_html_escape(e.cta_text)}</a>
</div>
<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af;text-align:center">
You're receiving this because you signed up for Predictify.
<br><a href="https://predictifyfootball.com/unsubscribe" style="color:#9ca3af">Unsubscribe</a>
</div>
</div></body></html>'''


def _html_escape(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ─────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────
def run(dry_run: bool = False, max_users: int | None = None) -> list[tuple[str, str]]:
    print(f'🚀 Predictify v2 trigger pass (dry_run={dry_run})')

    fb = FirebaseUserLoader()
    fb.refresh_exports()
    users_by_app = fb.load_users_by_app()
    users = users_by_app.get('Predictify', [])
    print(f'   Loaded {len(users)} Predictify users')

    lang_loader = FirestoreLanguageLoader()
    activity_loader = FirestoreActivityLoader()

    # Cache language + activity in batch where possible.
    try:
        languages_by_uid = lang_loader.load_languages('Predictify')
    except Exception:
        languages_by_uid = {}
    try:
        activity_by_uid = activity_loader.load_activity('Predictify')
    except Exception:
        activity_by_uid = {}

    state = _load_state()
    today = _today()
    today_state = state.setdefault(today, {})

    sent: list[tuple[str, str]] = []
    skipped_no_trigger = 0
    skipped_dup = 0

    for i, u in enumerate(users):
        if max_users and i >= max_users:
            break
        uid = u.get('localId') or u.get('uid')
        email = u.get('email')
        if not uid or not email:
            continue
        if uid in today_state:
            skipped_dup += 1
            continue

        lang = (languages_by_uid.get(uid) or 'en').lower()
        activity = activity_by_uid.get(uid) or {}
        display_name = u.get('displayName') or activity.get('displayName') or email.split('@')[0]

        try:
            ctx = fetch_user_context(uid, email, display_name, language=lang, activity=activity)
        except Exception as e:
            print(f'   ⚠️ context build failed for {uid}: {e}')
            continue

        kind = select_trigger(ctx)
        if not kind:
            skipped_no_trigger += 1
            continue

        rendered = render_template(kind, ctx)
        if not rendered:
            skipped_no_trigger += 1
            continue

        ok = _send(email, rendered, dry_run=dry_run)
        if ok:
            today_state[uid] = {'kind': kind, 'lang': lang}
            sent.append((email, kind))
            if not dry_run:
                _save_state(state)
            print(f'   ✅ {email}: {kind} ({lang})')
        # Be gentle with downstream APIs
        time.sleep(0.05)

    print(f'📊 Summary: sent={len(sent)} skipped_dup={skipped_dup} '
          f'skipped_no_trigger={skipped_no_trigger}')
    return sent


def status():
    state = _load_state()
    today = _today()
    today_state = state.get(today, {})
    print(f'📅 {today}: {len(today_state)} users sent v2 emails')
    by_kind = {}
    for v in today_state.values():
        by_kind[v['kind']] = by_kind.get(v['kind'], 0) + 1
    for k, n in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f'   {k:<20} {n}')


if __name__ == '__main__':
    if '--status' in sys.argv:
        status()
    else:
        dry = '--dry-run' in sys.argv
        run(dry_run=dry)
