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

# Allow `python -m predictify_v2.orchestrator` from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from predictify_v2.user_context import fetch_user_context  # noqa: E402
from predictify_v2.template_engine import render_template, RenderedEmail  # noqa: E402
from predictify_v2.triggers import select_trigger  # noqa: E402
from predictify_v2.community_recommender import CommunityRecommender  # noqa: E402

try:
    from firebase_user_loader import FirebaseUserLoader  # noqa: E402
    from firestore_language_loader import FirestoreLanguageLoader  # noqa: E402
    from firestore_activity_loader import FirestoreActivityLoader  # noqa: E402
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

    # Source 1: bounces + complaints from email_events (app-scoped).
    try:
        r = requests.get(
            f'{MARKETING_SUPABASE_URL}/rest/v1/email_events',
            params={
                'select': 'recipient',
                'app': 'eq.predictify',
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

    # Source 2: explicit unsubscribes (table created by step 4). Tolerate
    # absence so this is safe to deploy before the unsubscribe handler.
    try:
        r = requests.get(
            f'{MARKETING_SUPABASE_URL}/rest/v1/email_suppressions',
            params={
                'select': 'recipient',
                'app': 'eq.predictify',
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
            # 404 = table not created yet → fine. Other codes = log.
            print(f'   ⚠️ email_suppressions read {r.status_code}: {r.text[:120]}')
    except Exception as e:
        print(f'   ⚠️ email_suppressions load failed: {e}')

    return suppressed


# ─────────────────────────────────────────────────────────
#  Per-kind cooldowns (days). Same uid+kind isn't re-sent
#  inside this window even if the trigger predicate matches
#  again. Prevents "received this email twice because my
#  streak rebuilt" / "got the welcome email a month later".
#
#  Default cooldown for any kind not listed is 14 days.
# ─────────────────────────────────────────────────────────
COOLDOWN_DAYS: dict[str, int] = {
    'welcome': 9999,                  # once ever
    'login_streak_reward': 9999,      # once ever — it's a one-shot reward
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
#  Resend sender — rotates through the v1 sender pool so v2 inherits the
#  same warmup curve + deliverability monitoring. Hashing on UID keeps each
#  user assigned to the same sender across days (lower spam-folder risk).
# ─────────────────────────────────────────────────────────
RESEND_KEY = os.environ.get('RESEND_API_KEY', '')

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
    """Per-recipient signed unsubscribe URL. Encoded as `?e=<b64>&s=<hex>`
    where:
      e = url-safe base64 of the lowercased email + '|predictify'
      s = first 32 hex chars of HMAC-SHA256(secret, e)
    Truncating to 32 chars keeps the URL short while leaving plenty of
    bits for tamper resistance (128 bits)."""
    payload = f'{email_addr.lower().strip()}|predictify'.encode('utf-8')
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
    if not RESEND_KEY:
        print('⚠️ RESEND_API_KEY missing')
        return False
    sender = _pick_sender(uid)
    from_header = f"{sender['name']} <{sender['email']}>"
    unsub_url = _build_unsub_url(to)
    html = _build_html(email, unsub_url=unsub_url)
    text = _build_text(email, unsub_url=unsub_url)
    if dry_run:
        print(f'   [DRY] would send to {to} from {sender["email"]}: {email.subject!r}')
        return True
    try:
        r = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {RESEND_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'from': from_header,
                'to': to,
                'subject': email.subject,
                'html': html,
                # Plain-text fallback drops the multipart/alternative spam
                # signal that HTML-only emails carry. Most clients render
                # the HTML; the text part exists so filters don't flag.
                'text': text,
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
    cta_url = f'https://predictifyfootball.com/?ref=email&kind={e.kind}'
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
V2_DAILY_SEND_CAP = 500


def run(dry_run: bool = False, max_users: int | None = None) -> list[tuple[str, str]]:
    print(f'🚀 Predictify v2 trigger pass (dry_run={dry_run}, cap={V2_DAILY_SEND_CAP})')
    _log_env_presence()

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

    # Bulk-load the set of uids already emailed today. One query up front
    # is cheaper than per-user round-trips, and matches the "max one v2
    # email per user per day" cap the old in-memory `today_state` enforced.
    sent_today: set[str] = _firestore_sent_today_uids()
    print(f'   📨 {len(sent_today)} uids already emailed today')

    # Suppression list (bounces, complaints, explicit unsubscribes).
    # Checked AFTER trigger selection so we still count "would-have-sent"
    # in the summary line — useful for spotting drift in the suppressed
    # population vs total addressable.
    suppressed: set[str] = _load_suppressed_emails()
    print(f'   🚫 {len(suppressed)} suppressed addresses')

    # Load community pool once. The recommender keeps an in-memory list
    # of public communities ≥ MIN_ACTIVE_MEMBER_COUNT members; per-user
    # recommendation costs at most ~5 Firestore Gets to verify the user
    # isn't already a member of the picked community.
    recommender = CommunityRecommender()
    recommender.load()

    sent: list[tuple[str, str]] = []
    skipped_no_trigger = 0
    skipped_dup_today = 0
    skipped_cooldown = 0
    skipped_suppressed = 0

    cap_hit = False
    for i, u in enumerate(users):
        if max_users and i >= max_users:
            break
        if len(sent) >= V2_DAILY_SEND_CAP:
            cap_hit = True
            break
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

        lang = (languages_by_uid.get(uid) or 'en').lower()
        activity = activity_by_uid.get(uid) or {}
        display_name = u.get('displayName') or activity.get('displayName') or email.split('@')[0]

        try:
            ctx = fetch_user_context(uid, email, display_name, language=lang, activity=activity)
        except Exception as e:
            print(f'   ⚠️ context build failed for {uid}: {e}')
            continue

        # Attach a community recommendation (best-effort). This populates
        # the _recommended_community_* fields that both the trigger and
        # the template engine read. Users who already own a community or
        # who don't match any public community in the pool just won't
        # have these fields set, and the community_invite trigger will
        # skip them gracefully.
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

        kind = select_trigger(ctx)
        if not kind:
            skipped_no_trigger += 1
            continue

        cooldown = COOLDOWN_DAYS.get(kind, DEFAULT_COOLDOWN_DAYS)
        if _firestore_has_recent(uid, kind, cooldown):
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
        # Be gentle with downstream APIs
        time.sleep(0.05)

    cap_note = ' 🛑 CAP HIT' if cap_hit else ''
    print(f'📊 Summary: sent={len(sent)}/{V2_DAILY_SEND_CAP} '
          f'skipped_dup_today={skipped_dup_today} '
          f'skipped_cooldown={skipped_cooldown} '
          f'skipped_suppressed={skipped_suppressed} '
          f'skipped_no_trigger={skipped_no_trigger}{cap_note}')
    return sent


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
    else:
        dry = '--dry-run' in sys.argv
        run(dry_run=dry)
