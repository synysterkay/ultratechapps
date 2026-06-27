#!/usr/bin/env python3
"""
Thesis Generator founder story #2 — Hooked-model follow-up sent 5 days after
founder story #1.

Eligible: received founder_story_thesis at least DELAY_DAYS ago, not yet sent
founder_story_thesis_2. Runs daily via thesis_orchestrator with a catch-up cap.

Usage:
  python3 scripts/founder_story_thesis_2_sender.py --dry-run
  python3 scripts/founder_story_thesis_2_sender.py --warm
  python3 scripts/founder_story_thesis_2_sender.py
  python3 scripts/founder_story_thesis_2_sender.py --daily
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS
from thesis_users_loader import get_access_token, normalize_user_language
from thesis_template_translator import get_localized, warm_all
from thesis_email_chrome import render as render_email
from deliverability_monitor import DeliverabilityMonitor
import localize_phrase

from founder_story_thesis_sender import (
    APP_NAME,
    APP_SLUG,
    APP_STORE_URL,
    GOOGLE_PLAY_URL,
    WEB_APP_URL,
    _connect_senders,
    _fetch_language_map,
    _load_candidates,
    _load_state as _load_fs1_state,
    _load_suppressed_emails,
    _plan_for_user,
    _ref,
    _skip_email,
    _supabase_creds,
)

KIND = 'founder_story_thesis_2'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'founder_story_thesis_2_state.json'
DELAY_DAYS = int(os.getenv('FOUNDER_STORY_THESIS_2_DELAY_DAYS', '5'))
BACKFILL_CAP = int(os.getenv('FOUNDER_STORY_THESIS_2_SEND_CAP', '2000'))
DAILY_CATCHUP_CAP = int(os.getenv('FOUNDER_STORY_THESIS_2_DAILY_CAP', '200'))

EN_SOURCE = {
    'subject': '{{first_name}}, {{topic}} — 3 minutes to a draft you can edit',
    'body': [
        "{{first_name}}, you signed up for a reason — and {{topic}} is still waiting.",
        "Students who opened Thesis Generator this week didn't find more time. They stopped negotiating with a blank page and generated a rough {{work_type}} in under three minutes. Editing a draft feels manageable. Dreading one for another week doesn't.",
        "The loop that works: feel the deadline closing → open the app → enter {{topic}} and what you've already researched → tap generate → spend twenty minutes editing instead of twenty days stuck.",
        "Day {{days_since_story}} since our first note. Your submission date didn't move backward.",
        "P.S. If {{topic}} is already in the app, open it and finish one section today. One section is enough to restart momentum.",
    ],
    'cta': 'Draft my {{work_type}} in 3 minutes',
    'cta_android': 'Open on Android',
    'cta_web': 'Continue on web',
}


def _parse_sent_at(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None


def _fetch_fs2_sent_from_supabase() -> dict[str, dict]:
    url, key = _supabase_creds()
    if not url or not key:
        return {}
    try:
        import requests
        headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
        sent: dict[str, dict] = {}
        offset = 0
        page_size = 1000
        while True:
            r = requests.get(
                f'{url}/rest/v1/email_events',
                headers=headers,
                params={
                    'select': 'recipient,language,occurred_at',
                    'app': f'eq.{APP_SLUG}',
                    'kind': f'eq.{KIND}',
                    'event_type': 'eq.email.sent',
                    'order': 'occurred_at.asc',
                    'offset': offset,
                    'limit': page_size,
                },
                timeout=60,
            )
            if r.status_code != 200:
                return sent
            rows = r.json()
            for row in rows:
                email = (row.get('recipient') or '').lower().strip()
                if not email or email in sent:
                    continue
                occurred = row.get('occurred_at') or ''
                sent[email] = {
                    'sent_at': occurred.replace('+00:00', 'Z') if occurred else '',
                    'language': row.get('language') or 'en',
                    'source': 'supabase',
                }
            if len(rows) < page_size:
                break
            offset += page_size
        return sent
    except Exception:
        return {}


def _load_state() -> dict:
    state: dict = {'sent': {}}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    state.setdefault('sent', {})
    remote = _fetch_fs2_sent_from_supabase()
    merged = 0
    for email, info in remote.items():
        if email not in state['sent']:
            state['sent'][email] = info
            merged += 1
    if merged:
        print(f'   📎 Merged {merged} FS2 recipients from Supabase email_events')
    return state


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _write_en_cache() -> None:
    from thesis_template_translator import _write_cache
    _write_cache(KIND, 'en', EN_SOURCE)


def warm_templates(refresh: bool = False) -> None:
    if refresh:
        cache_dir = Path(__file__).resolve().parents[1] / 'cache' / 'thesis_templates'
        removed = 0
        for path in cache_dir.glob(f'{KIND}_*.json'):
            if path.name.endswith('_en.json'):
                continue
            path.unlink(missing_ok=True)
            removed += 1
        if removed:
            print(f'   🔄 Cleared {removed} cached {KIND} translations for refresh')
    _write_en_cache()
    from thesis_template_translator import SUPPORTED
    print(f'🔥 Warming {KIND} for {len(SUPPORTED) - 1} languages…')
    result = warm_all(KIND, EN_SOURCE)
    ok = sum(1 for v in result.values() if v in ('cached', 'translated'))
    print(f'✅ Warm complete: {ok}/{len(SUPPORTED) - 1} languages ready')


def _eligible_fs1_recipients(fs1_state: dict, now: datetime) -> dict[str, dict]:
    """email → {sent_at, language, days_since} for FS1 sends at least DELAY_DAYS old."""
    cutoff = now - timedelta(days=DELAY_DAYS)
    eligible: dict[str, dict] = {}
    for email, rec in fs1_state.get('sent', {}).items():
        email = email.lower().strip()
        if _skip_email(email):
            continue
        sent_at = _parse_sent_at(rec.get('sent_at', ''))
        if not sent_at or sent_at > cutoff:
            continue
        days_since = max(DELAY_DAYS, (now - sent_at).days)
        eligible[email] = {
            **rec,
            'days_since': days_since,
        }
    return eligible


def run_send(*, dry_run: bool = False, send_cap: int | None = None) -> list[str]:
    cap = send_cap if send_cap is not None else BACKFILL_CAP
    now = datetime.now(timezone.utc)
    fs1_state = _load_fs1_state()
    state = _load_state()
    state.setdefault('sent', {})
    already_fs2 = set(state['sent'].keys())

    fs1_eligible = _eligible_fs1_recipients(fs1_state, now)
    print(f'   📅 FS1 sent ≥{DELAY_DAYS}d ago: {len(fs1_eligible)} recipients')

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set — user metadata may be incomplete')

    lang_by_email = _fetch_language_map()
    suppressed = _load_suppressed_emails()
    if suppressed:
        print(f'   🚫 {len(suppressed)} suppressed addresses')

    users_by_email = {u['email']: u for u in _load_candidates(token, lang_by_email)}

    candidates: list[tuple[dict, dict]] = []
    for email, fs1_rec in fs1_eligible.items():
        if email in already_fs2 or email in suppressed:
            continue
        if GmailSender._is_suppressed(email, APP_SLUG):
            continue
        user = users_by_email.get(email)
        if not user:
            user = {
                'email': email,
                'first_name': email.split('@', 1)[0].split('.')[0].capitalize() or 'there',
                'language': fs1_rec.get('language') or lang_by_email.get(email) or 'en',
                'plan': {},
            }
        candidates.append((user, fs1_rec))

    candidates.sort(key=lambda pair: pair[1].get('sent_at', ''))

    print(f'📬 {len(candidates)} FS2 eligible (cap={cap}, already sent FS2={len(already_fs2)})')
    if not candidates:
        return []

    if dry_run:
        for user, fs1_rec in candidates[:30]:
            print(
                f"   • {user['email']}  lang={user.get('language', 'en')}  "
                f"FS1={fs1_rec.get('sent_at', '')[:10]}  days={fs1_rec.get('days_since')}"
            )
        if len(candidates) > 30:
            print(f'   … and {len(candidates) - 30} more')
        print('🏁 DRY RUN')
        return []

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return []

    senders = _connect_senders()
    if not senders:
        print('❌ No Resend senders available')
        return []

    sent_emails: list[str] = []
    failed = 0
    skipped = 0
    for i, (user, fs1_rec) in enumerate(candidates):
        if len(sent_emails) >= cap:
            print(f'   🛑 Cap hit ({cap})')
            break

        email = user['email']
        lang = normalize_user_language(user.get('language') or 'en')
        plan = _plan_for_user(user)
        plan['days_since_story'] = str(fs1_rec.get('days_since', DELAY_DAYS))

        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
        paragraphs = [
            localize_phrase.interpolate(lang, p, plan)
            for p in tpl.get('body', EN_SOURCE['body'])
        ]
        cta_text = localize_phrase.interpolate(lang, tpl.get('cta', EN_SOURCE['cta']), plan)
        cta_android = localize_phrase.interpolate(
            lang, tpl.get('cta_android', EN_SOURCE['cta_android']), plan,
        )
        cta_web = localize_phrase.interpolate(
            lang, tpl.get('cta_web', EN_SOURCE['cta_web']), plan,
        )

        html = render_email(
            lang, paragraphs, cta_text, APP_STORE_URL,
            sender_name='The Thesis Generator team',
            app_name=APP_NAME,
            gradient='urgent',
            signoff_override='',
            cta_links=[
                {'text': cta_text, 'url': APP_STORE_URL, 'variant': 'primary'},
                {'text': cta_android, 'url': GOOGLE_PLAY_URL, 'variant': 'play'},
                {'text': cta_web, 'url': WEB_APP_URL, 'variant': 'web'},
            ],
        )

        sender = senders[i % len(senders)]
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'system', 'value': 'thesis_founder_story_2'},
        ]
        result = sender.send_email(
            to_email=email,
            subject=subject,
            html_body=html,
            from_name=APP_NAME,
            tags=tags,
            ref_id=_ref(f'{email}:fs2'),
        )
        if result == 'sent':
            sent_emails.append(email)
            state['sent'][email] = {
                'sent_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'language': lang,
                'uid': user.get('uid'),
                'fs1_sent_at': fs1_rec.get('sent_at'),
                'days_after_fs1': fs1_rec.get('days_since'),
            }
            if len(sent_emails) % 25 == 0:
                _save_state(state)
            print(f'   ✅ [{len(sent_emails)}] {email} ({lang}) +{fs1_rec.get("days_since")}d')
        elif result in SKIP_RESULTS:
            skipped += 1
            print(f'   ⏭️ {email} result={result}')
        else:
            failed += 1
            print(f'   ❌ {email} result={result}')
        time.sleep(0.25)

    _save_state(state)
    print(f'\n📊 Done — sent {len(sent_emails)}, skipped {skipped}, failed {failed}, total FS2 ever {len(state["sent"])}')
    return sent_emails


def main(dry_run: bool = False, warm_only: bool = False, daily: bool = False, refresh_templates: bool = False) -> None:
    if warm_only:
        warm_templates(refresh=refresh_templates)
        return

    _write_en_cache()
    cap = DAILY_CATCHUP_CAP if daily else BACKFILL_CAP
    run_send(dry_run=dry_run, send_cap=cap)


if __name__ == '__main__':
    main(
        dry_run='--dry-run' in sys.argv,
        warm_only='--warm' in sys.argv,
        daily='--daily' in sys.argv,
        refresh_templates='--refresh-templates' in sys.argv,
    )
