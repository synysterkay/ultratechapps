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
from predictify_v2.community_recommender import CommunityRecommender  # noqa: E402

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


def _has_received_recently(state: dict, uid: str, kind: str, days: int) -> bool:
    """Scan the state cache for a (uid, kind) send within the last `days`.

    State shape:  {"YYYY-MM-DD": {uid: {"kind": str, "lang": str}, ...}, ...}
    """
    if days <= 0:
        return False
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    for date_str, day_state in state.items():
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            continue
        if d < cutoff:
            continue
        entry = day_state.get(uid)
        if entry and entry.get('kind') == kind:
            return True
    return False


def _prune_state(state: dict, keep_days: int = 120) -> None:
    """Drop date entries older than keep_days so the cache doesn't grow
    unbounded. 120 days is comfortably past the longest cooldown (30)."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=keep_days)
    for date_str in list(state.keys()):
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            continue
        if d < cutoff:
            del state[date_str]


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

try:
    from deliverability_monitor import DeliverabilityMonitor
    _SENDER_POOL = [s for s in DeliverabilityMonitor.SENDER_POOL if s.get('active', True)]
except Exception:
    _SENDER_POOL = [{'email': 'apps@kaynel.pl', 'name': 'Ana'}]


def _pick_sender(uid: str) -> dict:
    """Sticky-by-uid sender selection: a given user keeps the same 'from'
    across sends. Keeps thread-grouping in Gmail consistent and avoids the
    'why does Predictify email me from 5 different domains?' impression."""
    if not _SENDER_POOL:
        return {'email': 'apps@kaynel.pl', 'name': 'Ana'}
    h = sum(ord(c) for c in uid) if uid else 0
    return _SENDER_POOL[h % len(_SENDER_POOL)]


def _send(to: str, uid: str, email: RenderedEmail, dry_run: bool = False) -> bool:
    if not RESEND_KEY:
        print('⚠️ RESEND_API_KEY missing')
        return False
    sender = _pick_sender(uid)
    from_header = f"{sender['name']} <{sender['email']}>"
    html = _build_html(email)
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

    state = _load_state()
    _prune_state(state)
    today = _today()
    today_state = state.setdefault(today, {})

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
        if uid in today_state:
            skipped_dup_today += 1
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
        if _has_received_recently(state, uid, kind, cooldown):
            skipped_cooldown += 1
            continue

        rendered = render_template(kind, ctx)
        if not rendered:
            skipped_no_trigger += 1
            continue

        ok = _send(email, uid, rendered, dry_run=dry_run)
        if ok:
            today_state[uid] = {'kind': kind, 'lang': lang}
            sent.append((email, kind))
            if not dry_run:
                _save_state(state)
            print(f'   ✅ {email}: {kind} ({lang})')
        # Be gentle with downstream APIs
        time.sleep(0.05)

    cap_note = ' 🛑 CAP HIT' if cap_hit else ''
    print(f'📊 Summary: sent={len(sent)}/{V2_DAILY_SEND_CAP} skipped_dup_today={skipped_dup_today} '
          f'skipped_cooldown={skipped_cooldown} skipped_no_trigger={skipped_no_trigger}{cap_note}')
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
