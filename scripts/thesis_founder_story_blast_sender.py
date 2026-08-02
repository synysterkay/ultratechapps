#!/usr/bin/env python3
"""
Thesis Generator founder story blast — non-subscribers only (Superwall), 3 cohorts.

Sends founder_story_thesis_v2 copy via ZeptoMail to users where
`users.subscription.status` is NOT active/trial/past_due.

Usage:
  python3 scripts/thesis_founder_story_blast_sender.py --status
  python3 scripts/thesis_founder_story_blast_sender.py --dry-run --part 1 --limit 5
  python3 scripts/thesis_founder_story_blast_sender.py --part 1
  python3 scripts/thesis_founder_story_blast_sender.py --auto-part
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import requests  # noqa: E402

from gmail_sender import GmailSender, SKIP_RESULTS, has_email_credentials  # noqa: E402
from thesis_template_translator import get_localized, _read_cache  # noqa: E402
from thesis_email_chrome import render as render_email  # noqa: E402
from thesis_users_loader import (  # noqa: E402
    get_access_token,
    normalize_user_language,
    is_paid,
    founder_story_audience_eligible,
    load_all_users_list,
)
import localize_phrase  # noqa: E402

from founder_story_thesis_sender import (  # noqa: E402
    APP_NAME,
    APP_SLUG,
    APP_STORE_URL,
    GOOGLE_PLAY_URL,
    EN_SOURCE,
    TEMPLATE_KIND,
    _connect_senders,
    _load_suppressed_emails,
    _plan_for_user,
    _ref,
    _skip_email,
    load_combined_founder_story_state,
    _write_en_cache,
)

LANG_CACHE_PATH = ROOT / 'firebase_exports' / 'thesis_generator_languages.json'

STATE_PATH = ROOT / 'cache' / 'thesis_founder_story_blast_state.json'
CAMPAIGN_ID = 'founder_story_blast_aug2026'
KIND_PREFIX = 'founder_story_blast'
NUM_PARTS = 3
CAMPAIGN_DAY_PARTS = {
    '2026-08-02': 1,
    '2026-08-03': 2,
    '2026-08-04': 3,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _today() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _part_for_uid(uid: str) -> int:
    h = int(hashlib.sha256(uid.encode('utf-8')).hexdigest(), 16)
    return (h % NUM_PARTS) + 1


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {
        'campaign': CAMPAIGN_ID,
        'started_at': _utc_now(),
        'parts': {str(i): {'sent_count': 0, 'completed_at': None} for i in range(1, NUM_PARTS + 1)},
        'sent': {},
        'failed': {},
    }


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state['updated_at'] = _utc_now()
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


def _load_suppressed_bounces() -> set[str]:
    """Bounces/complaints from marketing Supabase."""
    url = os.getenv('SUPABASE_URL', '').rstrip('/')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
    if not url or not key:
        return set()
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    out: set[str] = set()
    try:
        r = requests.get(
            f'{url}/rest/v1/email_events',
            params={
                'select': 'recipient',
                'event_type': 'in.(email.bounced,email.complained)',
                'recipient': 'not.is.null',
                'limit': '10000',
            },
            headers=headers,
            timeout=30,
        )
        if r.ok:
            for row in r.json():
                rec = (row.get('recipient') or '').lower().strip()
                if rec:
                    out.add(rec)
    except Exception as e:
        print(f'   ⚠️ bounce load failed: {e}')
    return out


def _load_language_cache() -> dict[str, str]:
    """Offline email→lang map (firebase_exports/thesis_generator_languages.json)."""
    if not LANG_CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(LANG_CACHE_PATH.read_text(encoding='utf-8'))
        return {
            email.lower().strip(): normalize_user_language(lang)
            for email, lang in raw.items()
            if email and lang
        }
    except Exception:
        return {}


def _resolve_language(email: str, fs_user: dict | None, lang_cache: dict[str, str]) -> str:
    """Pick the best language for a user — Firestore profile first, then cache."""
    email = email.lower().strip()
    if fs_user and fs_user.get('language'):
        return normalize_user_language(fs_user['language'])
    if lang_cache.get(email):
        return normalize_user_language(lang_cache[email])
    return 'en'


def _print_lang_distribution(users: list[dict], label: str = 'cohort') -> None:
    from collections import Counter
    counts = Counter(normalize_user_language(u.get('language') or 'en') for u in users)
    print(f'   📊 Language distribution ({label}):')
    for lang, n in counts.most_common(15):
        print(f'      {lang}: {n:,}')
    if len(counts) > 15:
        print(f'      … +{len(counts) - 15} more languages')


def _preflight_templates(users: list[dict]) -> None:
    """Warn if any cohort language lacks a cached founder story template."""
    langs = {normalize_user_language(u.get('language') or 'en') for u in users}
    missing = sorted(lang for lang in langs if lang != 'en' and _read_cache(TEMPLATE_KIND, lang) is None)
    if missing:
        print(f'   ⚠️ Missing cached templates for: {", ".join(missing)} — those users get English copy')
    else:
        print(f'   ✅ Cached templates ready for all {len(langs)} languages in queue')


def _audience_stats(token: str | None) -> dict:
    """Break down eligible non-subscriber cohort before send."""
    from firebase_user_loader import FirebaseUserLoader

    auth_users = FirebaseUserLoader().load_users_by_app().get(APP_NAME, [])
    lang_cache = _load_language_cache()
    if lang_cache:
        print(f'   🌍 Language cache: {len(lang_cache):,} emails')

    fs_by_email: dict[str, dict] = {}
    fs_by_uid: dict[str, dict] = {}
    if token:
        print('   Loading Firestore users (Superwall subscription + language)…')
        time.sleep(int(os.getenv('THESIS_FIRESTORE_WARMUP_SEC', '20')))
        for u in load_all_users_list(token):
            fs_by_email[u['email']] = u
            if u.get('uid'):
                fs_by_uid[u['uid']] = u
    else:
        lang_cache = lang_cache or {}

    stats = {
        'auth_users': len(auth_users),
        'firestore_users': len(fs_by_email),
        'paid_skipped': 0,
        'no_subscription_key': 0,
        'eligible': 0,
        'by_part': {p: 0 for p in range(1, NUM_PARTS + 1)},
    }
    eligible: list[dict] = []

    for au in auth_users:
        email = au['email'].lower().strip()
        uid = au.get('uid', '')
        fs = fs_by_email.get(email) or (fs_by_uid.get(uid) if uid else None)

        if not fs:
            stats['no_subscription_key'] += 1
            continue
        if is_paid(fs):
            stats['paid_skipped'] += 1
            continue
        if not founder_story_audience_eligible(fs):
            stats['no_subscription_key'] += 1
            continue
        if not uid:
            continue

        lang = _resolve_language(email, fs, lang_cache)
        user = {**au, **fs, 'language': lang, 'email': email}
        part = _part_for_uid(uid)
        stats['by_part'][part] += 1
        stats['eligible'] += 1
        eligible.append({**user, 'part': part})

    stats['eligible_list'] = eligible
    return stats


def _already_sent_emails(state: dict) -> set[str]:
    sent = set((state.get('sent') or {}).keys())
    prior = load_combined_founder_story_state().get('sent') or {}
    sent |= {e.lower().strip() for e in prior.keys()}
    return sent


def _auto_part(state: dict) -> int:
    today = _today()
    if today in CAMPAIGN_DAY_PARTS:
        return CAMPAIGN_DAY_PARTS[today]
    started = state.get('started_at') or _utc_now()
    try:
        start_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
    except ValueError:
        start_dt = datetime.now(timezone.utc)
    days = (datetime.now(timezone.utc) - start_dt).days
    return min(NUM_PARTS, max(1, days + 1))


def _print_status(state: dict, stats: dict | None = None) -> None:
    print(f'\n=== Thesis founder story blast: {state.get("campaign", CAMPAIGN_ID)} ===')
    print(f'Started: {state.get("started_at", "?")}')
    sent = state.get('sent') or {}
    failed = state.get('failed') or {}
    print(f'Blast sent: {len(sent):,}  |  Failed: {len(failed):,}')

    prior = load_combined_founder_story_state().get('sent') or {}
    print(f'Prior founder story (v1/v2) sent: {len(prior):,}')

    for p in range(1, NUM_PARTS + 1):
        ps = sum(1 for v in sent.values() if v.get('part') == p)
        pinfo = (state.get('parts') or {}).get(str(p), {})
        line = f'  Part {p}: {ps:,} blast sent'
        if pinfo.get('completed_at'):
            line += f' (completed {pinfo["completed_at"]})'
        print(line)

    if stats:
        print(f'\nAudience (Superwall non-subscribers with Firestore subscription doc):')
        print(f'  Auth users: {stats["auth_users"]:,}')
        print(f'  Firestore loaded: {stats["firestore_users"]:,}')
        print(f'  Active subs skipped: {stats["paid_skipped"]:,}')
        print(f'  Missing subscription doc: {stats["no_subscription_key"]:,}')
        print(f'  Eligible total: {stats["eligible"]:,}')
        already = _already_sent_emails(state)
        print(f'  Already received founder story: {len(already):,}')
        print('  Remaining by part:')
        for p in range(1, NUM_PARTS + 1):
            rem = [
                u for u in stats['eligible_list']
                if u['part'] == p and u['email'] not in already
            ]
            print(f'    Part {p}: {len(rem):,}')
            if rem and p == 1:
                _print_lang_distribution(rem[:5000], f'part {p} remaining sample')


def _render_html(user: dict, lang: str) -> tuple[str, str, str]:
    plan = _plan_for_user(user)
    tpl = get_localized(TEMPLATE_KIND, lang, EN_SOURCE, allow_api=False)
    subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
    preview = localize_phrase.interpolate(
        lang, tpl.get('preview', EN_SOURCE.get('preview', '')), plan,
    )
    paragraphs = [
        localize_phrase.interpolate(lang, p, plan)
        for p in tpl.get('body', EN_SOURCE['body'])
    ]
    cta_ios = localize_phrase.interpolate(
        lang, tpl.get('cta_ios', EN_SOURCE.get('cta_ios', 'App Store')), plan,
    )
    cta_android = localize_phrase.interpolate(
        lang, tpl.get('cta_android', EN_SOURCE.get('cta_android', 'Google Play')), plan,
    )
    html = render_email(
        lang, paragraphs, cta_ios, APP_STORE_URL,
        sender_name='Ana',
        app_name=APP_NAME,
        gradient='invite',
        preview_text=preview or None,
        cta_links=[
            {'url': APP_STORE_URL, 'variant': 'ios', 'line2': cta_ios},
            {'url': GOOGLE_PLAY_URL, 'variant': 'android', 'line2': cta_android},
        ],
    )
    return subject, preview, html


def run(
    *,
    part: int,
    dry_run: bool = False,
    limit: int = 0,
    sleep: float = 0.25,
) -> None:
    if not dry_run and not has_email_credentials():
        raise SystemExit('Email credentials missing (EMAIL_PROVIDER + ZEPTOMAIL_API_KEY)')

    os.environ.setdefault('EMAIL_PROVIDER', 'zeptomail')
    os.environ.setdefault('ZEPTOMAIL_THESIS_SENDER_EMAIL', 'hello@thesisgenerator.io')
    os.environ.setdefault('ZEPTOMAIL_THESIS_SENDER_NAME', 'Thesis Generator')

    token = get_access_token()
    if not token:
        raise SystemExit('FIREBASE_TOKEN not set — cannot load Superwall subscription status')

    _write_en_cache()

    state = _load_state()
    if state.get('campaign') != CAMPAIGN_ID:
        state = {
            'campaign': CAMPAIGN_ID,
            'started_at': _utc_now(),
            'parts': {str(i): {'sent_count': 0, 'completed_at': None} for i in range(1, NUM_PARTS + 1)},
            'sent': {},
            'failed': {},
        }

    pinfo = (state.get('parts') or {}).get(str(part), {})
    if pinfo.get('completed_at') and not dry_run:
        print(f'Part {part} already completed at {pinfo["completed_at"]} — skipping.')
        return

    print(f'Loading Thesis non-subscriber cohort (part {part}/{NUM_PARTS})…')
    stats = _audience_stats(token)
    if stats['firestore_users'] < 1000:
        raise SystemExit(
            f'Firestore too sparse ({stats["firestore_users"]} users) — refusing live send.'
        )

    suppressed = _load_suppressed_emails() | _load_suppressed_bounces()
    print(f'   Eligible: {stats["eligible"]:,}  |  Suppressed: {len(suppressed):,}')

    already = _already_sent_emails(state)
    cohort = [
        u for u in stats['eligible_list']
        if u['part'] == part
        and u['email'] not in already
        and u['email'] not in suppressed
        and not _skip_email(u['email'])
        and not GmailSender._is_suppressed(u['email'], APP_SLUG)
    ]
    if limit > 0:
        cohort = cohort[:limit]

    print(f'Part {part} queue: {len(cohort):,} emails this run')
    if cohort:
        _print_lang_distribution(cohort)
        _preflight_templates(cohort)
    if not cohort:
        print('Nothing to send.')
        if not dry_run:
            parts = state.setdefault('parts', {})
            parts.setdefault(str(part), {})['completed_at'] = _utc_now()
            _save_state(state)
        return

    senders = None
    if not dry_run:
        senders = _connect_senders()
        if not senders:
            raise SystemExit('No ZeptoMail senders available')

    kind = f'{KIND_PREFIX}_p{part}'
    sent_map = state.setdefault('sent', {})
    sent_n = failed_n = skipped_n = 0

    for i, user in enumerate(cohort, 1):
        email = user['email']
        lang = normalize_user_language(user.get('language') or 'en')
        if lang != 'en' and _read_cache(TEMPLATE_KIND, lang) is None:
            print(f'   ⚠️ No template for {lang} — English fallback for {email}')

        subject, preview, html = _render_html(user, lang)

        if dry_run:
            if i <= 5:
                print(f'   [DRY] {email} lang={lang} part={part}')
                print(f'         Subject: {subject}')
            sent_n += 1
            continue

        sender = senders[i % len(senders)]
        result = sender.send_email(
            to_email=email,
            subject=subject,
            html_body=html,
            from_name=APP_NAME,
            tags=[
                {'name': 'app', 'value': APP_SLUG},
                {'name': 'kind', 'value': kind},
                {'name': 'language', 'value': lang},
                {'name': 'part', 'value': str(part)},
                {'name': 'campaign', 'value': CAMPAIGN_ID},
                {'name': 'system', 'value': 'thesis_founder_story_blast'},
            ],
            ref_id=_ref(email),
        )
        if result == 'sent':
            sent_n += 1
            sent_map[email] = {
                'uid': user.get('uid'),
                'part': part,
                'language': lang,
                'sent_at': _utc_now(),
            }
            state.setdefault('failed', {}).pop(email, None)
            if sent_n % 25 == 0:
                _save_state(state)
                print(f'   ✅ [{sent_n}] latest: {email} ({lang})')
        elif result in SKIP_RESULTS:
            skipped_n += 1
        else:
            failed_n += 1
            state.setdefault('failed', {})[email] = {
                'part': part,
                'result': result,
                'at': _utc_now(),
            }

        if sleep > 0:
            time.sleep(sleep)

    parts = state.setdefault('parts', {})
    pinfo = parts.setdefault(str(part), {'sent_count': 0, 'completed_at': None})
    pinfo['sent_count'] = pinfo.get('sent_count', 0) + sent_n

    if not dry_run:
        if sent_n > 0 and failed_n == 0:
            pinfo['completed_at'] = _utc_now()
        elif failed_n > 0:
            print(f'   ⚠️ Part {part} incomplete — {failed_n} failures (retry on next run)')
        _save_state(state)

    print(f'\nDone part {part}: sent={sent_n}, failed={failed_n}, skipped={skipped_n}')
    if cohort and not dry_run:
        sample_subj, sample_prev, _ = _render_html(cohort[0], normalize_user_language(cohort[0].get('language', 'en')))
        print(f'Subject: {sample_subj}')
        print(f'Preview: {sample_prev}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Thesis founder story blast (non-subs, 3 parts)')
    parser.add_argument('--part', type=int, choices=[1, 2, 3], help='Cohort part (1-3)')
    parser.add_argument('--auto-part', action='store_true', help='Part from campaign calendar / day index')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--sleep', type=float, default=float(os.getenv('THESIS_BLAST_SEND_DELAY', '0.25')))
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()

    token = get_access_token()
    state = _load_state()

    if args.status or (args.dry_run and not args.part and not args.auto_part):
        if not token:
            print('⚠️ FIREBASE_TOKEN not set — status uses auth export only (no Superwall filter)')
        stats = _audience_stats(token) if token else {'auth_users': 0, 'firestore_users': 0,
            'paid_skipped': 0, 'no_subscription_key': 0, 'eligible': 0,
            'by_part': {1: 0, 2: 0, 3: 0}, 'eligible_list': []}
        if token:
            _print_status(state, stats)
        else:
            from firebase_user_loader import FirebaseUserLoader
            n = len(FirebaseUserLoader().load_users_by_app().get(APP_NAME, []))
            print(f'Thesis auth users (export only): {n:,}')
            print('Set FIREBASE_TOKEN for Superwall subscription breakdown.')
        if not args.part and not args.auto_part:
            return

    part = args.part
    if args.auto_part:
        part = _auto_part(state)
        print(f'Auto-selected part {part} for {_today()}')

    if not part:
        raise SystemExit('Specify --part N, --auto-part, or --status')

    run(part=part, dry_run=args.dry_run, limit=args.limit, sleep=args.sleep)


if __name__ == '__main__':
    main()
