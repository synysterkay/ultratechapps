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
import base64
import hmac
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

# Allow `python -m predictify_v2.orchestrator` from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from predictify_v2.user_context import fetch_user_context, prefetch_bulk_context  # noqa: E402
from predictify_v2.template_engine import (  # noqa: E402
    render_template,
    RenderedEmail,
    founder_story_kinds_for_app,
    is_founder_story_kind,
    LEGACY_FOUNDER_V1_KINDS,
)
from predictify_v2.triggers import select_trigger  # noqa: E402
from predictify_v2.community_recommender import CommunityRecommender  # noqa: E402

try:
    from firebase_user_loader import FirebaseUserLoader  # noqa: E402
    from firestore_language_loader import FirestoreLanguageLoader  # noqa: E402
    from firestore_activity_loader import FirestoreActivityLoader  # noqa: E402
    from gmail_sender import GmailSender, has_email_credentials  # noqa: E402
except ImportError:
    print('⚠️ Could not import firebase loaders — run from scripts/ dir')
    raise


# ─────────────────────────────────────────────────────────
#  State — Firestore-backed.
#
#  Previously this was a JSON file committed back to the git repo at the
#  end of each CI run. If the push step failed (auth, conflict, network)
#  the next run started with an empty cache and re-fired every trigger
#  for every user. Silent re-hammer risk that ages badly.
#
#  Now: each successful send creates a doc in `predictify_v2_sends/` on
#  Predictify's Firestore. Single-field queries only (auto-indexed) so
#  no manual composite-index setup is needed.
#
#  Schema:
#    predictify_v2_sends/{uid}__{kind}__{utc_iso}
#      uid:      stringValue
#      kind:     stringValue
#      lang:     stringValue
#      sent_at:  timestampValue
# ─────────────────────────────────────────────────────────
from predictify_v2 import user_context as _uc  # noqa: E402

SENDS_COLLECTION = 'predictify_v2_sends'


def _firestore_record_send(uid: str, kind: str, lang: str) -> None:
    """Write one send doc. Deterministic id keeps a retried orchestrator
    invocation from creating duplicates."""
    tok = _uc._fb_token()
    if not tok:
        return
    now = datetime.now(timezone.utc)
    doc_id = f'{uid}__{kind}__{now.strftime("%Y%m%dT%H%M%S")}'
    try:
        requests.post(
            f'{_uc.FIRESTORE_BASE}/{SENDS_COLLECTION}?documentId={doc_id}',
            headers={'Authorization': f'Bearer {tok}'},
            json={
                'fields': {
                    'uid': {'stringValue': uid},
                    'kind': {'stringValue': kind},
                    'lang': {'stringValue': lang},
                    'sent_at': {
                        'timestampValue': now.strftime('%Y-%m-%dT%H:%M:%SZ')
                    },
                }
            },
            timeout=10,
        )
    except Exception as e:
        print(f'   ⚠️ record_send failed for {uid}/{kind}: {e}')


def _firestore_has_recent(uid: str, kind: str, days: int) -> bool:
    """Was (uid, kind) sent within the last `days` days?

    Single-field uid filter (auto-indexed) plus client-side kind +
    recency filtering. Avoids requiring a manual composite index on the
    Firestore console — at <200 sends per user lifetime, the per-call
    cost is dominated by the network round-trip, not the doc volume.
    """
    if days <= 0:
        return False
    tok = _uc._fb_token()
    if not tok:
        return False  # fail-open: better a duplicate than blocking the run
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        body = {
            'structuredQuery': {
                'from': [{'collectionId': SENDS_COLLECTION}],
                'where': {
                    'fieldFilter': {
                        'field': {'fieldPath': 'uid'},
                        'op': 'EQUAL',
                        'value': {'stringValue': uid},
                    }
                },
                'limit': 200,
            }
        }
        r = requests.post(
            f'{_uc.FIRESTORE_BASE}:runQuery',
            headers={'Authorization': f'Bearer {tok}'},
            json=body, timeout=10,
        )
        if not r.ok:
            return False
        for entry in r.json():
            doc = entry.get('document')
            if not doc:
                continue
            fields = doc.get('fields', {})
            if fields.get('kind', {}).get('stringValue') != kind:
                continue
            sent_at_str = fields.get('sent_at', {}).get('timestampValue')
            if not sent_at_str:
                continue
            try:
                sent_at = datetime.fromisoformat(
                    sent_at_str.replace('Z', '+00:00'))
                if sent_at > cutoff:
                    return True
            except Exception:
                continue
    except Exception as e:
        print(f'   ⚠️ has_recent query failed for {uid}/{kind}: {e}')
    return False


def _firestore_sent_today_uids() -> set[str]:
    """Bulk-load uids that already received ANY v2 email today. One
    query saves N per-user round-trips — same daily-cap behaviour the
    old `today_state` dict provided, just persisted across runs."""
    tok = _uc._fb_token()
    if not tok:
        return set()
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).strftime('%Y-%m-%dT%H:%M:%SZ')
    uids: set[str] = set()
    try:
        body = {
            'structuredQuery': {
                'from': [{'collectionId': SENDS_COLLECTION}],
                'where': {
                    'fieldFilter': {
                        'field': {'fieldPath': 'sent_at'},
                        'op': 'GREATER_THAN_OR_EQUAL',
                        'value': {'timestampValue': today_start},
                    }
                },
                'limit': 5000,
            }
        }
        r = requests.post(
            f'{_uc.FIRESTORE_BASE}:runQuery',
            headers={'Authorization': f'Bearer {tok}'},
            json=body, timeout=30,
        )
        if r.ok:
            for entry in r.json():
                doc = entry.get('document')
                if not doc:
                    continue
                uid = doc.get('fields', {}).get('uid', {}).get('stringValue')
                if uid:
                    uids.add(uid)
    except Exception as e:
        print(f'   ⚠️ sent_today_uids query failed: {e}')
    return uids


def _firestore_all_sends() -> dict:
    """Bulk-load the ENTIRE send history into {uid: {kind: latest_sent_at}}.

    The cooldown check used to be a per-user Firestore query — and because
    nearly every user matches the (once-ever) `welcome` trigger, that meant
    ~17k sequential round-trips per run (the bulk of the old runtime). One
    paginated scan here turns the cooldown check into an in-memory lookup.
    Doubles as the source for `sent_today` (no separate query needed).
    """
    tok = _uc._fb_token()
    if not tok:
        return {}
    base = f'{_uc.FIRESTORE_BASE}/{SENDS_COLLECTION}'
    headers = {'Authorization': f'Bearer {tok}'}
    index: dict = {}
    page_token = None
    while True:
        params = [('pageSize', 300), ('mask.fieldPaths', 'uid'),
                  ('mask.fieldPaths', 'kind'), ('mask.fieldPaths', 'sent_at')]
        if page_token:
            params.append(('pageToken', page_token))
        try:
            r = requests.get(base, params=params, headers=headers, timeout=30)
        except Exception as e:
            print(f'   ⚠️ all_sends page failed: {e}')
            break
        if r.status_code != 200:
            print(f'   ⚠️ all_sends query failed: {r.status_code}')
            break
        j = r.json()
        for doc in j.get('documents', []):
            f = doc.get('fields', {})
            uid = f.get('uid', {}).get('stringValue')
            kind = f.get('kind', {}).get('stringValue')
            sa = f.get('sent_at', {}).get('timestampValue')
            if not uid or not kind or not sa:
                continue
            try:
                dt = datetime.fromisoformat(sa.replace('Z', '+00:00'))
            except Exception:
                continue
            cur = index.setdefault(uid, {})
            if kind not in cur or dt > cur[kind]:
                cur[kind] = dt
        page_token = j.get('nextPageToken')
        if not page_token:
            break
    return index


def _has_recent_in_index(index: dict, uid: str, kind: str, days: int) -> bool:
    """In-memory equivalent of _firestore_has_recent, against the bulk index.
    days>=9999 means 'once ever' — any past send of this kind blocks."""
    if days <= 0:
        return False
    dt = index.get(uid, {}).get(kind)
    if not dt:
        return False
    if days >= 9999:
        return True
    return dt > (datetime.now(timezone.utc) - timedelta(days=days))


def _today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


# ─────────────────────────────────────────────────────────
#  Suppression list — emails we must NOT send to.
#
#  Sources (both Predictify-scoped — Thesis bounces don't suppress
#  Predictify users since each app has its own user population):
#    1. email_events rows with type in (email.bounced, email.complained)
#       AND app='predictify' — populated by the resend-webhook.
#    2. email_suppressions table (step 4) — populated by the
#       predictify-unsubscribe Edge Function when a user clicks the
#       footer link. Read-tolerant: the table may not exist yet, so a
#       404 from PostgREST is treated as "no explicit unsubscribes."
#
#  Loaded once per run into an in-memory set; check is O(1) per user.
# ─────────────────────────────────────────────────────────
MARKETING_SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
MARKETING_SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')


def _marketing_headers() -> dict:
    if not MARKETING_SUPABASE_KEY:
        return {}
    return {
        'apikey': MARKETING_SUPABASE_KEY,
        'Authorization': f'Bearer {MARKETING_SUPABASE_KEY}',
    }


def _load_suppressed_emails() -> set[str]:
    """Bulk-load the set of email addresses we must skip. Lowercased
    everywhere — Resend events store recipients as lowercase, and the
    Firebase exports we compare against will be lowercased at check time."""
    suppressed: set[str] = set()
    if not MARKETING_SUPABASE_URL or not MARKETING_SUPABASE_KEY:
        print('   ⚠️ Marketing Supabase creds missing — suppression list empty')
        return suppressed

    headers = _marketing_headers()

    # Source 1: bounces + complaints from email_events. NOT app-scoped: a
    # hard bounce means the address itself is dead (bad everywhere), and a
    # complaint means "stop emailing me". We only ever check this set against
    # Predictify users anyway, so matching by recipient across all apps is
    # both safe and more robust — it also doesn't depend on the per-event
    # `app` tag being populated (historically it wasn't).
    try:
        r = requests.get(
            f'{MARKETING_SUPABASE_URL}/rest/v1/email_events',
            params={
                'select': 'recipient',
                'event_type': 'in.(email.bounced,email.complained)',
                'recipient': 'not.is.null',
                'limit': '10000',
            },
            headers=headers, timeout=15,
        )
        if r.status_code == 200:
            for row in r.json():
                rec = row.get('recipient')
                if rec:
                    suppressed.add(rec.lower())
    except Exception as e:
        print(f'   ⚠️ bounce/complaint load failed: {e}')

    # Source 2: email_suppressions (unsubscribes, webhook bounces, inline API bounces).
    app_slug = _app_slug()
    for scope in (app_slug, 'predictify', 'predictify_nba', 'horse_racing', '*', 'global'):
        try:
            r = requests.get(
                f'{MARKETING_SUPABASE_URL}/rest/v1/email_suppressions',
                params={
                    'select': 'recipient',
                    'app': f'eq.{scope}',
                    'recipient': 'not.is.null',
                    'limit': '10000',
                },
                headers=headers, timeout=15,
            )
            if r.status_code == 200:
                for row in r.json():
                    rec = row.get('recipient')
                    if rec:
                        suppressed.add(rec.lower())
            elif r.status_code != 404:
                print(f'   ⚠️ email_suppressions read {scope} {r.status_code}: {r.text[:120]}')
        except Exception as e:
            print(f'   ⚠️ email_suppressions load failed ({scope}): {e}')

    return suppressed


# ─────────────────────────────────────────────────────────
#  Per-kind cooldowns (days). Same uid+kind isn't re-sent
#  inside this window even if the trigger predicate matches
#  again. Prevents "received this email twice because my
#  streak rebuilt" / "got the welcome email a month later".
#
#  Default cooldown for any kind not listed is 14 days.
# ─────────────────────────────────────────────────────────
FOUNDER_STORY_V2_GAP_DAYS = int(os.environ.get('FOUNDER_STORY_V2_GAP_DAYS', '7'))
FOUNDER_STORY_LAPSED_DAYS = int(os.environ.get('FOUNDER_STORY_LAPSED_DAYS', '14'))


def _founder_kinds() -> tuple[str, str]:
    return founder_story_kinds_for_app()


def _cooldown_days(kind: str) -> int:
    if is_founder_story_kind(kind) or kind in LEGACY_FOUNDER_V1_KINDS:
        return 9999
    return COOLDOWN_DAYS.get(kind, DEFAULT_COOLDOWN_DAYS)


def _founder_fallback_disabled() -> bool:
    return os.environ.get('PREDICTIFY_DISABLE_FOUNDER_FALLBACK', '0').lower() in (
        '1', 'true', 'yes',
    )


COOLDOWN_DAYS: dict[str, int] = {
    'welcome': 9999,
    'login_streak_reward': 9999,
    'streak_saver': 5,
    'match_day': 1,
    'upgrade_after_hot_week': 14,
    'owner_marketing_kit': 21,
    'owner_growth': 21,
    'pro_owner_pitch': 21,
    'pro_power_tip': 7,
    'winback_lapsed_pro': 30,
    'win_back': 21,
    'referral_invite': 21,
    'weekly_recap': 6,
}
DEFAULT_COOLDOWN_DAYS = 14


def _log_env_presence() -> None:
    """Boolean-only env audit at startup so CI logs reveal missing creds
    without ever printing values. If Supabase keys are absent the user
    context queries silently degrade and match_day under-fires — this
    log makes that visible at run start."""
    keys = [
        'RESEND_API_KEY',
        'PREDICTIFY_SUPABASE_URL',
        'PREDICTIFY_SUPABASE_SERVICE_ROLE_KEY',
        'FIREBASE_TOKEN',
        # Signs unsubscribe-link tokens. Without it, links still render
        # but won't validate when clicked (function returns "expired or
        # tampered"). Must match the same name on the predictify-
        # unsubscribe Supabase function.
        'PREDICTIFY_UNSUBSCRIBE_SECRET',
        # Required for the suppression-list bulk-load (email_events +
        # email_suppressions tables on the Email Marketing project).
        'SUPABASE_URL',
        'SUPABASE_SERVICE_ROLE_KEY',
    ]
    print('🔑 env presence:')
    for k in keys:
        present = bool(os.environ.get(k, '').strip())
        print(f'   {"✅" if present else "❌"} {k}')


# ─────────────────────────────────────────────────────────
#  Email sender — rotates through the v1 sender pool (Resend or Mailgun via
#  gmail_sender.GmailSender). Hashing on UID keeps each user on the same
#  sender across days.
# ─────────────────────────────────────────────────────────
RESEND_KEY = os.environ.get('RESEND_API_KEY', '')
_EMAIL_SENDER: GmailSender | None = None


def _email_configured() -> bool:
    return has_email_credentials()


def _app_slug() -> str:
    """Firestore / suppression app id for the active profile."""
    app_name = os.environ.get('PREDICTIFY_APP_NAME', 'Predictify')
    if 'NBA' in app_name:
        return 'predictify_nba'
    if 'Horse' in app_name:
        return 'horse_racing'
    return 'predictify'


def _get_email_sender() -> GmailSender:
    global _EMAIL_SENDER
    if _EMAIL_SENDER is None:
        _EMAIL_SENDER = GmailSender()
        if not _EMAIL_SENDER.connect():
            raise RuntimeError('email provider connection failed')
    return _EMAIL_SENDER

# Unsubscribe link signing. Same secret lives on the
# predictify-unsubscribe Edge Function which verifies the HMAC before
# inserting into email_suppressions. Without a secret the orchestrator
# still works but the link won't validate — fail-open at send time so
# we don't block emails, fail-closed at click time so spoofed links
# can't unsubscribe arbitrary addresses.
UNSUBSCRIBE_BASE_URL = os.environ.get(
    'PREDICTIFY_UNSUBSCRIBE_URL',
    'https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-unsubscribe',
)
UNSUBSCRIBE_SIGNING_SECRET = os.environ.get(
    'PREDICTIFY_UNSUBSCRIBE_SECRET', '')


def _build_unsub_url(email_addr: str) -> str:
    """Per-recipient signed unsubscribe URL. Encoded as `?e=<b64>&s=<hex>`."""
    slug = _app_slug()
    payload = f'{email_addr.lower().strip()}|{slug}'.encode('utf-8')
    e = base64.urlsafe_b64encode(payload).rstrip(b'=').decode('ascii')
    if UNSUBSCRIBE_SIGNING_SECRET:
        s = hmac.new(
            UNSUBSCRIBE_SIGNING_SECRET.encode('utf-8'),
            e.encode('ascii'),
            hashlib.sha256,
        ).hexdigest()[:32]
        return f'{UNSUBSCRIBE_BASE_URL}?e={e}&s={s}'
    # No secret configured → link still includes recipient so the
    # function can render a generic confirmation page, but the function
    # will reject the unsubscribe write (no valid signature).
    return f'{UNSUBSCRIBE_BASE_URL}?e={e}'

try:
    from deliverability_monitor import DeliverabilityMonitor
    _SENDER_POOL = [s for s in DeliverabilityMonitor.SENDER_POOL if s.get('active', True)]
except Exception:
    _SENDER_POOL = [{'email': 'tips@predictifyfootball.com', 'name': 'Sam'}]


def _pick_sender(uid: str) -> dict:
    """Sticky-by-uid sender selection: a given user keeps the same 'from'
    across sends. Keeps thread-grouping in Gmail consistent and avoids the
    'why does Predictify email me from 5 different domains?' impression."""
    if not _SENDER_POOL:
        return {'email': 'tips@predictifyfootball.com', 'name': 'Sam'}
    h = sum(ord(c) for c in uid) if uid else 0
    return _SENDER_POOL[h % len(_SENDER_POOL)]


def _send(to: str, uid: str, email: RenderedEmail, dry_run: bool = False) -> bool:
    if not _email_configured():
        print('⚠️ email credentials missing (check EMAIL_PROVIDER + API key)')
        return False
    sender = _pick_sender(uid)
    unsub_url = _build_unsub_url(to)
    html = _build_html(email, unsub_url=unsub_url)
    if dry_run:
        print(f'   [DRY] would send to {to} from {sender["email"]}: {email.subject!r}')
        return True
    try:
        mailer = _get_email_sender()
        mailer.sender_email = sender['email']
        mailer.sender_name = sender['name']
        result = mailer.send_email(
            to_email=to,
            subject=email.subject,
            html_body=html,
            from_name=sender['name'],
            tags=[
                {'name': 'app', 'value': _app_slug()},
                {'name': 'kind', 'value': email.kind},
                {'name': 'lang', 'value': email.language},
                {'name': 'system', 'value': 'v2'},
            ],
        )
        if result == 'sent':
            return True
        if result in ('duplicate', 'suppressed', 'throttled'):
            print(f'   ⏭️ Skipped {to} — {result}')
            return False
        print(f'   ⚠️ Send failed for {to}: {result}')
        return False
    except Exception as e:
        print(f'   ⚠️ Send failed: {e}')
        return False


def _cta_href(e: RenderedEmail) -> str:
    """Prefer an explicit deeplink / landing URL from the template."""
    dl = (e.cta_deeplink or '').strip()
    if dl.startswith('http://') or dl.startswith('https://'):
        return dl
    if dl.startswith('predictify://'):
        return dl
    return f'https://predictifyfootball.com/?ref=email&kind={e.kind}'


def _build_html(e: RenderedEmail, unsub_url: str | None = None) -> str:
    is_rtl = e.language == 'ar'
    dir_attr = ' dir="rtl"' if is_rtl else ''
    align = 'right' if is_rtl else 'left'
    unsub = unsub_url or 'https://predictifyfootball.com/unsubscribe'
    paras = ''.join(
        f'<p style="margin:0 0 16px;color:#1f2937;font-size:15px;line-height:1.6;text-align:{align}">'
        f'{p.replace(chr(10), "<br>")}</p>'
        for p in e.body_paragraphs
    )
    store_links = ''
    if e.app_store_url or e.google_play_url:
        parts = []
        if e.app_store_url:
            parts.append(
                f'<a href="{_html_escape(e.app_store_url)}" '
                f'style="color:#64748b;margin:0 8px">{_html_escape(e.cta_ios_text or "App Store")}</a>'
            )
        if e.google_play_url:
            parts.append(
                f'<a href="{_html_escape(e.google_play_url)}" '
                f'style="color:#64748b;margin:0 8px">{_html_escape(e.cta_android_text or "Google Play")}</a>'
            )
        store_links = (
            f'<p style="margin:16px 0 0;font-size:12px;color:#94a3b8;text-align:center">'
            f'{" · ".join(parts)}</p>'
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
<a href="{_html_escape(_cta_href(e))}" style="display:inline-block;padding:14px 28px;background:#3B82F6;color:#fff;text-decoration:none;border-radius:10px;font-weight:700;font-size:15px">{_html_escape(e.cta_text)}</a>
</div>
{store_links}
<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#9ca3af;text-align:center">
You're receiving this because you signed up for Predictify.
<br><a href="{unsub}" style="color:#9ca3af">Unsubscribe</a>
</div>
</div></body></html>'''


def _html_escape(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _build_text(e: RenderedEmail, unsub_url: str | None = None) -> str:
    """Plain-text counterpart to _build_html. Mailers without multipart
    /alternative are treated as bulk/promotional by Gmail and friends —
    keeping the text version short and useful (not just an HTML strip)
    is the cheap improvement."""
    body = '\n\n'.join(p for p in e.body_paragraphs if p)
    cta_url = _cta_href(e)
    unsub = unsub_url or 'https://predictifyfootball.com/unsubscribe'
    lines = [
        'PREDICTIFY',
        '',
        body,
        '',
        f'{e.cta_text}: {cta_url}',
        '',
        '—',
        "You're receiving this because you signed up for Predictify.",
        f'Unsubscribe: {unsub}',
    ]
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────
#  Hard upper bound per single invocation. v2 cross-day cooldown already
#  prevents repeat sends per user once state persists, but this cap is
#  the second-tier safety net: even if state.json gets corrupted/lost,
#  no more than V2_DAILY_SEND_CAP emails go out in one run. With two
#  daily crons (09:00 + 17:00 UTC) the realistic worst case is
#  2 × V2_DAILY_SEND_CAP = 1000 emails/day.
V2_DAILY_SEND_CAP = 250
# Founder-story backfill uses a higher per-pass cap so one workflow run can
# clear the backlog (~20k users) in a single job.
FOUNDER_STORY_SEND_CAP = 2000


def _send_cap(founder_story_only: bool) -> int:
    if founder_story_only:
        return int(os.environ.get('FOUNDER_STORY_SEND_CAP', FOUNDER_STORY_SEND_CAP))
    return int(os.environ.get('V2_DAILY_SEND_CAP', V2_DAILY_SEND_CAP))

# Building a user's context is ~13 sequential HTTP reads (Supabase + Firestore).
# Done serially across ~17k users that was the ~2h45m the run spent before it
# ever sent an email. The reads are pure I/O and independent per user, so we
# fan them out across a bounded thread pool. All send/dedup/cap decisions stay
# strictly sequential below — only the read-only enrichment is parallel.
V2_FETCH_WORKERS = int(os.environ.get('V2_FETCH_WORKERS', '16'))
V2_FETCH_CHUNK = 96


def _legacy_founder_story_emails() -> set[str]:
    """Emails already sent by legacy standalone founder-story scripts."""
    cache = Path(__file__).resolve().parents[2] / 'cache'
    emails: set[str] = set()
    for name in (
        'founder_story_wc2026_state.json',
        'founder_story_soccer_mailjet_state.json',
    ):
        path = cache / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
            emails.update(e.lower() for e in (data.get('sent') or {}))
        except Exception:
            pass
    return emails


def _parse_firebase_ms(raw) -> datetime | None:
    if raw in (None, ''):
        return None
    try:
        if isinstance(raw, str) and raw.isdigit():
            ms = int(raw)
        elif isinstance(raw, (int, float)):
            ms = int(raw)
        else:
            return datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        if ms > 1_000_000_000_000:
            ms //= 1000
        return datetime.fromtimestamp(ms, tz=timezone.utc)
    except Exception:
        return None


def _is_lapsed(ctx, created_at_raw=None) -> bool:
    """True when user is inactive long enough for founder-story lapsed emails."""
    lapsed_hours = FOUNDER_STORY_LAPSED_DAYS * 24
    if ctx.last_pick_at:
        return (ctx.hours_since_last_pick or 0) >= lapsed_hours
    created = _parse_firebase_ms(created_at_raw)
    if not created:
        return False
    age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    return age_hours >= lapsed_hours


def _kind_sent_at(index: dict, uid: str, kind: str) -> datetime | None:
    return index.get(uid, {}).get(kind)


def _received_founder_v1(
    index: dict,
    uid: str,
    email: str,
    legacy_founder_sent: set[str],
    v1_kind: str,
) -> bool:
    if email.lower() in legacy_founder_sent:
        return True
    for legacy in LEGACY_FOUNDER_V1_KINDS:
        if _has_recent_in_index(index, uid, legacy, 9999):
            return True
    return _has_recent_in_index(index, uid, v1_kind, 9999)


def _received_founder_v2(index: dict, uid: str, v2_kind: str) -> bool:
    return _has_recent_in_index(index, uid, v2_kind, 9999)


def _days_since_kind_sent(index: dict, uid: str, kind: str) -> float | None:
    dt = _kind_sent_at(index, uid, kind)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def _days_since_any_founder_v1(
    index: dict, uid: str, v1_kind: str,
) -> float | None:
    best: float | None = None
    for kind in (v1_kind, *LEGACY_FOUNDER_V1_KINDS):
        d = _days_since_kind_sent(index, uid, kind)
        if d is not None and (best is None or d < best):
            best = d
    return best


def _pick_kind(
    ctx,
    uid: str,
    email: str,
    sends_index: dict,
    *,
    founder_story_only: bool,
    founder_story_v2: bool,
    legacy_founder_sent: set[str],
    created_at_raw=None,
    require_lapsed: bool = True,
) -> str | None:
    """Select the v2 email kind for a user."""
    v1_kind, v2_kind = _founder_kinds()

    if founder_story_v2:
        if _received_founder_v2(sends_index, uid, v2_kind):
            return None
        if founder_story_only and not _received_founder_v1(
            sends_index, uid, email, legacy_founder_sent, v1_kind,
        ):
            return None
        if require_lapsed and not _is_lapsed(ctx, created_at_raw):
            return None
        return v2_kind

    if founder_story_only:
        if _received_founder_v1(
            sends_index, uid, email, legacy_founder_sent, v1_kind,
        ):
            return None
        if require_lapsed and not _is_lapsed(ctx, created_at_raw):
            return None
        return v1_kind

    kind = select_trigger(ctx)
    if kind:
        return kind

    if _founder_fallback_disabled():
        return None

    if not _is_lapsed(ctx, created_at_raw):
        return None

    if _received_founder_v2(sends_index, uid, v2_kind):
        return None

    if _received_founder_v1(
        sends_index, uid, email, legacy_founder_sent, v1_kind,
    ):
        days = _days_since_any_founder_v1(sends_index, uid, v1_kind)
        if days is not None and days >= FOUNDER_STORY_V2_GAP_DAYS:
            return v2_kind
        return None

    return v1_kind


def _is_active_subscriber(activity: dict | None) -> bool:
    """True when Firestore shows an active Superwall / Pro subscription."""
    if not activity:
        return False
    return bool(activity.get('isPremium') or activity.get('isSubscribed'))


def _is_subscriber(activity: dict | None) -> bool:
    """Alias kept for callers that already use this name."""
    return _is_active_subscriber(activity)


def _eligible_founder_story_predictify(
    uid: str,
    email: str,
    activity_by_uid: dict,
    activity_by_email: dict,
    activity_data_available: bool,
) -> bool:
    """Free + churned only; skip users with an explicit active subscription."""
    if not activity_data_available:
        return False
    activity = activity_by_uid.get(uid)
    if activity is None:
        activity = activity_by_email.get(email.lower())
    # No Firestore profile (or empty doc) → treat as free, same as FS2 non-sub path.
    if not activity:
        return True
    return not _is_active_subscriber(activity)


def run(
    dry_run: bool = False,
    max_users: int | None = None,
    founder_story_only: bool = False,
    founder_story_v2: bool = False,
    non_subscribers_only: bool = False,
    require_lapsed: bool | None = None,
) -> list[tuple[str, str]]:
    v1_kind, v2_kind = _founder_kinds()
    if require_lapsed is None:
        require_lapsed = not (founder_story_only or founder_story_v2)
    if founder_story_v2 and non_subscribers_only:
        mode = 'founder_story v2 non-subscriber resend'
    elif founder_story_only:
        mode = 'founder_story backfill'
    else:
        mode = 'triggers'
    send_cap = _send_cap(founder_story_only or founder_story_v2)
    print(f'🚀 Predictify v2 {mode} (dry_run={dry_run}, cap={send_cap})')
    if founder_story_only or founder_story_v2:
        print('   🎯 Founder story audience: free + churned only (active subs skipped)')
    elif non_subscribers_only:
        print('   🎯 Audience: free users only (isPremium/isSubscribed=false)')
    if founder_story_v2:
        print(f'   📨 Campaign kind: {v2_kind}')
    elif founder_story_only:
        print(f'   📨 Campaign kind: {v1_kind}')
    if not require_lapsed and (founder_story_only or founder_story_v2):
        print('   📭 Backfill mode — lapsed filter OFF')
    _log_env_presence()

    fb = FirebaseUserLoader()
    fb.refresh_exports()
    users_by_app = fb.load_users_by_app()
    # Soccer default 'Predictify'; NBA profile sets PREDICTIFY_APP_NAME=
    # 'Predictify: NBA AI' to select NBA users from the same loader.
    app_name = os.environ.get('PREDICTIFY_APP_NAME', 'Predictify')
    users = users_by_app.get(app_name, [])
    print(f'   Loaded {len(users)} {app_name} users')

    lang_loader = FirestoreLanguageLoader()
    activity_loader = FirestoreActivityLoader()

    # Cache language + activity in batch where possible. Uses the same
    # env-selected app (Soccer default, or 'Predictify: NBA AI' for the NBA
    # profile) so languages come from the right Firebase project.
    try:
        languages_by_uid = lang_loader.load_languages(app_name)
    except Exception:
        languages_by_uid = {}
    try:
        activity_by_email, activity_by_uid = activity_loader.load_activity(
            app_name, users,
        )
    except Exception:
        activity_by_email, activity_by_uid = {}, {}
    activity_data_available = bool(activity_by_email) or bool(activity_by_uid)
    if (founder_story_only or founder_story_v2) and not activity_data_available:
        print('   ⚠️ No subscription activity data — skipping founder story sends')
        return []

    # Bulk-load the ENTIRE send history once → {uid: {kind: latest_sent_at}}.
    # This powers both the per-kind cooldown check (in-memory, see the loop)
    # and the "already emailed today" dedup — replacing what used to be ~17k
    # sequential per-user Firestore cooldown queries.
    t_sends = time.time()
    sends_index: dict = _firestore_all_sends()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today: set[str] = {
        uid for uid, kinds in sends_index.items()
        if any(dt >= today_start for dt in kinds.values())
    }
    print(f'   📨 send history: {len(sends_index)} uids ({time.time()-t_sends:.1f}s), '
          f'{len(sent_today)} already emailed today')

    # Suppression list (bounces, complaints, explicit unsubscribes).
    # Checked AFTER trigger selection so we still count "would-have-sent"
    # in the summary line — useful for spotting drift in the suppressed
    # population vs total addressable.
    suppressed: set[str] = _load_suppressed_emails()
    legacy_founder_sent = _legacy_founder_story_emails()
    if legacy_founder_sent:
        print(f'   📜 {len(legacy_founder_sent)} legacy founder-story sends (skipped)')
    print(f'   🚫 {len(suppressed)} suppressed addresses')

    # Load community pool once. The recommender keeps an in-memory list
    # of public communities ≥ MIN_ACTIVE_MEMBER_COUNT members; per-user
    # recommendation costs at most ~5 Firestore Gets to verify the user
    # isn't already a member of the picked community.
    recommender = CommunityRecommender()
    recommender.load()

    # Bulk-load the ENTIRE behavioral dataset once (user_leagues, user_picks,
    # predictions, communities — ~2.9k rows in ~4 queries). Each user's
    # context is then built from memory with zero per-user Supabase/Firestore
    # reads. This is what collapses the old ~90k-query / ~2h45m pass.
    t_bulk = time.time()
    bulk = prefetch_bulk_context()
    print(f'   ⚡ Bulk context loaded in {time.time() - t_bulk:.1f}s '
          f'({len(bulk.fav_leagues_by_uid)} users w/ leagues, '
          f'{len(bulk.accuracy_by_uid)} w/ picks, '
          f'{len(bulk.owned_by_uid)} community owners, '
          f'top_pick={"yes" if bulk.top_pick_today else "no"})')

    sent: list[tuple[str, str]] = []
    skipped_no_trigger = 0
    skipped_dup_today = 0
    skipped_cooldown = 0
    skipped_suppressed = 0
    skipped_subscriber = 0
    skipped_founder_audience = 0

    def _skip_founder_story(uid: str, email: str) -> bool:
        ok = _eligible_founder_story_predictify(
            uid, email, activity_by_uid, activity_by_email, activity_data_available,
        )
        return not ok

    def _enrich(u):
        """Read-only: build a user's context and attach a community
        recommendation. Pure I/O, safe to run in a worker thread — touches no
        shared mutable state (recommender.pool / _token are read-only after
        load()). Returns (u, ctx, lang) on success, ('error', uid, exc) on a
        context-build failure, or None to skip."""
        uid = u.get('localId') or u.get('uid')
        email = u.get('email')
        lang = (languages_by_uid.get(uid) or 'en').lower()
        activity = activity_by_uid.get(uid) or {}
        display_name = u.get('displayName') or activity.get('displayName') or email.split('@')[0]

        try:
            ctx = fetch_user_context(uid, email, display_name, language=lang,
                                     activity=activity, bulk=bulk)
        except Exception as e:
            return ('error', uid, e)

        # Attach a community recommendation (best-effort). This populates
        # the _recommended_community_* fields that both the trigger and
        # the template engine read. Users who already own a community or
        # who don't match any public community in the pool just won't
        # have these fields set, and the community_invite trigger will
        # skip them gracefully.
        #
        # Gate: community_invite requires total_picks_30d >= 2 and no owned
        # community. Users who can't meet that never read these fields, so we
        # skip the recommender's per-user Firestore membership checks for them
        # — the last remaining per-user network cost in this loop.
        if ctx.total_picks_30d < 2 or ctx.owned_community_id is not None:
            return (u, ctx, lang)
        try:
            rec = recommender.recommend(
                uid=ctx.uid,
                followed_league_ids=ctx.followed_league_ids,
                owned_community_id=ctx.owned_community_id,
            )
            if rec:
                ctx._recommended_community_id = rec['id']
                ctx._recommended_community_name = rec['name']
                ctx._recommended_community_owner = rec.get('ownerName')
                ctx._recommended_community_member_count = rec.get('memberCount', 0)
                # Show the first matching league name if there's overlap,
                # otherwise the community's first league name as a generic
                # fallback ("football" when even that's missing).
                followed = set(ctx.followed_league_ids or [])
                league_label = 'football'
                for lid, lname in zip(rec.get('leagues') or [],
                                      rec.get('leagueNames') or []):
                    if lid in followed and lname:
                        league_label = lname
                        break
                else:
                    names = rec.get('leagueNames') or []
                    if names:
                        league_label = names[0]
                ctx._recommended_community_league = league_label
        except Exception as e:
            print(f'   ⚠️ community recommend failed for {uid}: {e}')

        return (u, ctx, lang)

    # Process users in chunks: enrich each chunk's contexts in parallel
    # (read-only I/O), then walk the results SEQUENTIALLY to apply trigger /
    # cooldown / send decisions. Order and the cap behave exactly as the old
    # serial loop — we just stopped paying for the reads one at a time.
    cap_hit = False
    executor = ThreadPoolExecutor(max_workers=V2_FETCH_WORKERS)
    try:
        for chunk_start in range(0, len(users), V2_FETCH_CHUNK):
            if max_users and chunk_start >= max_users:
                break
            if len(sent) >= send_cap:
                cap_hit = True
                break

            chunk = users[chunk_start:chunk_start + V2_FETCH_CHUNK]

            # Cheap, no-I/O pre-filter — done serially so the skip counters
            # stay exact and we don't waste a worker fetching context for a
            # user we'd drop anyway.
            candidates = []
            for u in chunk:
                uid = u.get('localId') or u.get('uid')
                email = u.get('email')
                if not uid or not email:
                    continue
                if uid in sent_today:
                    skipped_dup_today += 1
                    continue
                if email.lower() in suppressed:
                    skipped_suppressed += 1
                    continue
                if founder_story_only or founder_story_v2:
                    if _skip_founder_story(uid, email):
                        skipped_founder_audience += 1
                        continue
                elif non_subscribers_only and _is_subscriber(activity_by_uid.get(uid)):
                    skipped_subscriber += 1
                    continue
                if founder_story_only and not founder_story_v2 and email.lower() in legacy_founder_sent:
                    skipped_cooldown += 1
                    continue
                candidates.append(u)

            if not candidates:
                continue

            # Parallel read-only enrichment for this chunk.
            results = list(executor.map(_enrich, candidates))

            # Sequential decision + send — preserves ordering and the cap.
            for res in results:
                if res is None:
                    continue
                if res[0] == 'error':
                    print(f'   ⚠️ context build failed for {res[1]}: {res[2]}')
                    continue
                if len(sent) >= send_cap:
                    cap_hit = True
                    break

                u, ctx, lang = res
                uid = ctx.uid
                email = u.get('email')

                kind = _pick_kind(
                    ctx, uid, email, sends_index,
                    founder_story_only=founder_story_only or founder_story_v2,
                    founder_story_v2=founder_story_v2,
                    legacy_founder_sent=legacy_founder_sent,
                    created_at_raw=u.get('created_at') or u.get('createdAt'),
                    require_lapsed=require_lapsed,
                )
                if not kind:
                    skipped_no_trigger += 1
                    continue

                if is_founder_story_kind(kind) and _skip_founder_story(uid, email):
                    skipped_founder_audience += 1
                    continue

                cooldown = _cooldown_days(kind)
                if _has_recent_in_index(sends_index, uid, kind, cooldown):
                    skipped_cooldown += 1
                    continue

                rendered = render_template(kind, ctx)
                if not rendered:
                    skipped_no_trigger += 1
                    continue

                ok = _send(email, uid, rendered, dry_run=dry_run)
                if ok:
                    sent_today.add(uid)
                    sent.append((email, kind))
                    if not dry_run:
                        _firestore_record_send(uid, kind, lang)
                    print(f'   ✅ {email}: {kind} ({lang})')

            if cap_hit:
                break
    finally:
        executor.shutdown(wait=False)

    cap_note = ' 🛑 CAP HIT' if cap_hit else ''
    print(f'📊 Summary: sent={len(sent)}/{send_cap} '
          f'skipped_dup_today={skipped_dup_today} '
          f'skipped_cooldown={skipped_cooldown} '
          f'skipped_suppressed={skipped_suppressed} '
          f'skipped_subscriber={skipped_subscriber} '
          f'skipped_founder_audience={skipped_founder_audience} '
          f'skipped_no_trigger={skipped_no_trigger}{cap_note}')
    return sent


def run_founder_story_backfill(dry_run: bool = False) -> list[tuple[str, str]]:
    """Send founder story v1 to users who haven't received it (backfill — no lapsed gate)."""
    return run(dry_run=dry_run, founder_story_only=True, require_lapsed=False)


def run_founder_story_non_subscriber_resend(dry_run: bool = False) -> list[tuple[str, str]]:
    """Send founder story v2 to free users who got v1 but never subscribed."""
    return run(
        dry_run=dry_run,
        founder_story_only=True,
        founder_story_v2=True,
        non_subscribers_only=True,
        require_lapsed=False,
    )


def status():
    """Snapshot of today's v2 sends, read from Firestore."""
    tok = _uc._fb_token()
    if not tok:
        print('⚠️ No Firebase token, cannot fetch status')
        return
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        body = {
            'structuredQuery': {
                'from': [{'collectionId': SENDS_COLLECTION}],
                'where': {
                    'fieldFilter': {
                        'field': {'fieldPath': 'sent_at'},
                        'op': 'GREATER_THAN_OR_EQUAL',
                        'value': {'timestampValue': today_start},
                    }
                },
                'limit': 5000,
            }
        }
        r = requests.post(
            f'{_uc.FIRESTORE_BASE}:runQuery',
            headers={'Authorization': f'Bearer {tok}'},
            json=body, timeout=30,
        )
        rows = []
        if r.ok:
            for entry in r.json():
                doc = entry.get('document')
                if not doc:
                    continue
                kind = doc.get('fields', {}).get('kind', {}).get('stringValue')
                if kind:
                    rows.append(kind)
        print(f'📅 {_today()}: {len(rows)} v2 emails sent')
        by_kind: dict[str, int] = {}
        for k in rows:
            by_kind[k] = by_kind.get(k, 0) + 1
        for k, n in sorted(by_kind.items(), key=lambda x: -x[1]):
            print(f'   {k:<20} {n}')
    except Exception as e:
        print(f'⚠️ status query failed: {e}')


if __name__ == '__main__':
    if '--status' in sys.argv:
        status()
    elif '--founder-story-non-sub' in sys.argv:
        dry = '--dry-run' in sys.argv
        run_founder_story_non_subscriber_resend(dry_run=dry)
    elif '--founder-story' in sys.argv:
        dry = '--dry-run' in sys.argv
        run_founder_story_backfill(dry_run=dry)
    else:
        dry = '--dry-run' in sys.argv
        run(dry_run=dry)
