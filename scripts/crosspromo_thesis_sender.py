#!/usr/bin/env python3
"""
Crosspromotion — Thesis Generator conversion sequence (phase 1).

Pools Auth emails from all portfolio apps (excluding Thesis Auth users),
enrolls them in a 5-email sequence, sends via ZeptoMail from
hello@passedai.io (health-aware gate prefers that domain).

Usage:
  python3 scripts/crosspromo_thesis_sender.py --status
  python3 scripts/crosspromo_thesis_sender.py --dry-run --limit 20
  python3 scripts/crosspromo_thesis_sender.py --warm
  python3 scripts/crosspromo_thesis_sender.py --warm --adapt
  python3 scripts/crosspromo_thesis_sender.py --limit 50
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

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS, has_email_credentials
from thesis_template_translator import get_localized, warm_all, _write_cache
from thesis_email_chrome import render as render_email
from deliverability_monitor import pick_healthy_sender
from crosspromo_pool import build_pool, pool_stats
import localize_phrase

APP_NAME = 'Research Generator'
APP_SLUG = 'crosspromo'  # ZeptoMail allowlist → passedai.io pin
TARGET = 'thesis'
KIND_PREFIX = 'crosspromo_thesis'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'crosspromo_thesis_state.json'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
GOOGLE_PLAY_URL = 'https://play.google.com/store/apps/details?id=com.thesis.generator.ai'
PREFERRED_SENDER = 'hello@passedai.io'
CROSSPROMO_FROM = os.getenv('ZEPTOMAIL_PASSED_AI_SENDER_EMAIL', 'hello@passedai.io')
REENROLL_COOLDOWN_DAYS = 90
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# (stage_key, min_days_since_enroll)
STAGES = [
    ('e1', 0),
    ('e2', 2),
    ('e3', 5),
    ('e4', 10),
    ('e5', 14),
]

EN_SOURCES = {
    'e1': {
        'subject': "The 47-minute research trick nobody teaches in class",
        'preview': "Blank page → research statement + outline in under 5 minutes.",
        'body': [
            "Hey {{first_name}} — quick one.",
            "People who already use our apps keep hitting the same wall:",
            "The blank page when a research paper or essay is due.\nNot the reading.\nThe starting.",
            "[[LEAD]]Start with your research question.",
            "[[VALUE]]Research Generator turns it into a research statement + structured outline in under 5 minutes.",
            "[[SUB]]Free to try. No login maze. No credit card.",
            "P.S. Open it once. If the outline sucks, delete it. If it doesn't… you just bought yourself a weekend.",
        ],
        'cta': 'Try Research Generator free',
        'cta_ios': 'App Store',
        'cta_android': 'Google Play',
    },
    'e2': {
        'subject': "I timed it: research outline ready in 4 minutes 12 seconds",
        'preview': "The dopamine hit when the blank page disappears…",
        'body': [
            "{{first_name}}, here's the move that actually feels good:",
            "1) Drop your topic into Research Generator\n2) Get a research statement + structured outline\n3) Start writing from a plan instead of panic",
            "[[VALUE]]That first outline hitting your screen? Instant relief.",
            "[[SUB]]Free to download. No account required to peek.",
            "P.S. Pro tip: generate 2–3 research angles and pick the strongest. Takes another minute. Feels unfair in a good way.",
        ],
        'cta': 'Get my outline now',
        'cta_ios': 'App Store',
        'cta_android': 'Google Play',
    },
    'e3': {
        'subject': "12,000+ students finished a research draft this month",
        'preview': "Not genius — just a better starting point.",
        'body': [
            "You're not behind because you're lazy. Most people stall because the first sentence feels impossible.",
            "Research Generator users keep saying the same thing: once the outline exists, the rest moves.",
            "[[VALUE]]Shortest path to a real first draft.",
            "[[SUB]]Paper, proposal, or dissertation — start free.",
            "P.S. The free tier is enough to prove it. Upgrade later only if you want more chapters unlocked.",
        ],
        'cta': 'Start my free draft',
        'cta_ios': 'App Store',
        'cta_android': 'Google Play',
    },
    'e4': {
        'subject': "Still free. Still no credit card. Still works at 2am.",
        'preview': "The objections I hear — answered in 20 seconds.",
        'body': [
            "{{first_name}}, if you skipped the last emails, fair. Here's the honest pitch:",
            "• Free download — no card to try\n• Built for real research assignments\n• Outline + research statement before you spiral",
            "If writing isn't on your plate this week, ignore this. If it is — open the app before the deadline owns you.",
            "P.S. Worst case you spend 3 minutes and learn it isn't for you. Best case you sleep.",
        ],
        'cta': 'Download free',
        'cta_ios': 'App Store',
        'cta_android': 'Google Play',
    },
    'e5': {
        'subject': "Last note from me about Research Generator",
        'preview': "Closing this thread — link if you want it.",
        'body': [
            "{{first_name}}, I'll stop after this one.",
            "If a paper is coming up and you want a clean starting point, Research Generator is here: free, fast, no pressure.",
            "If not — all good. Mute or unsubscribe anytime. No hard feelings.",
            "P.S. Bookmark it for the next deadline. Future-you will thank present-you.",
        ],
        'cta': 'Open Research Generator',
        'cta_ios': 'App Store',
        'cta_android': 'Google Play',
    },
}

# Crosspromo chrome: honest footer, Kaynel identity, compact layout, no double Hey
CROSSPROMO_FOOTER = (
    "You're receiving this because you use another Kaynel app. "
    "We're sharing Research Generator in case it helps with writing."
)
CROSSPROMO_ADDRESS = 'Kaynel · Built for students & researchers'


def crosspromo_render_kwargs(preview_text: str | None = None) -> dict:
    return {
        'sender_name': 'Alex',
        'sender_org': 'Kaynel',
        'app_name': APP_NAME,
        'gradient': 'invite',
        'greeting_override': '',
        'footer_override': CROSSPROMO_FOOTER,
        'address_override': CROSSPROMO_ADDRESS,
        'compact': True,
        'preview_text': preview_text,
        'cta_links': [
            {'url': APP_STORE_URL, 'variant': 'ios', 'line1': 'Download on the', 'line2': 'App Store'},
            {'url': GOOGLE_PLAY_URL, 'variant': 'android', 'line1': 'GET IT ON', 'line2': 'Google Play'},
        ],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def _ref(email: str) -> str:
    return hashlib.sha256(f"{_REF_SALT}:{email.lower().strip()}".encode()).hexdigest()[:16]


def _skip_email(email: str) -> bool:
    e = email.lower()
    return (
        not e
        or 'cloudtestlabaccounts.com' in e
        or e.endswith('@example.com')
        or 'test@' in e
    )


def _load_suppressed_emails() -> set[str]:
    url = os.getenv('SUPABASE_URL', '').rstrip('/')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
    if not url or not key:
        return set()
    try:
        import requests
        r = requests.get(
            f'{url}/rest/v1/email_suppressions',
            headers={'apikey': key, 'Authorization': f'Bearer {key}'},
            params={'select': 'email'},
            timeout=20,
        )
        if r.status_code != 200:
            return set()
        return {row['email'].lower().strip() for row in r.json() if row.get('email')}
    except Exception:
        return set()


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {
        'campaign': 'crosspromo_thesis_v1',
        'enrolled': {},
        'sent_counts': {s: 0 for s, _ in STAGES},
        'updated_at': None,
    }


def _save_state(state: dict) -> None:
    state['updated_at'] = _utc_now()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')


def _days_since(enrolled_at: str) -> int:
    try:
        return (datetime.now(timezone.utc) - _parse_ts(enrolled_at)).days
    except Exception:
        return 0


def _due_stage(record: dict) -> str | None:
    """Next unpaid stage whose day offset has been reached."""
    stages_sent = set((record.get('stages') or {}).keys())
    if record.get('completed_at'):
        return None
    days = _days_since(record.get('enrolled_at') or _utc_now())
    for key, min_day in STAGES:
        if key in stages_sent:
            continue
        if days >= min_day:
            return key
        break  # stages are ordered; don't skip ahead
    return None


def _can_reenroll(record: dict) -> bool:
    completed = record.get('completed_at')
    if not completed:
        return False
    try:
        days = (datetime.now(timezone.utc) - _parse_ts(completed)).days
        return days >= REENROLL_COOLDOWN_DAYS
    except Exception:
        return False


def warm_templates(adapt: bool = False, refresh: bool = False) -> None:
    mode = 'adapt' if adapt else 'translate'
    print(f'🔥 Warming crosspromo Thesis templates (mode={mode})…')
    for stage, src in EN_SOURCES.items():
        kind = f'{KIND_PREFIX}_{stage}'
        _write_cache(kind, 'en', src)
        print(f'   ✅ {kind}/en cached')
        warm_all(kind, src, mode=mode, refresh=refresh)


def print_status() -> None:
    state = _load_state()
    enrolled = state.get('enrolled') or {}
    print(f'\n=== Crosspromo Thesis ({state.get("campaign")}) ===')
    print(f'Enrolled: {len(enrolled):,}')
    print(f'Sent counts: {state.get("sent_counts")}')
    completed = sum(1 for r in enrolled.values() if r.get('completed_at'))
    print(f'Completed sequences: {completed:,}')
    due = 0
    for r in enrolled.values():
        if _due_stage(r):
            due += 1
    print(f'Due this run (approx): {due:,}')
    print(f'Pool stats: {pool_stats()}')
    sender = pick_healthy_sender(prefer=PREFERRED_SENDER)
    print(f'Would send from: {sender}')


def run(*, dry_run: bool = False, limit: int = 0, enroll_cap: int | None = None) -> None:
    daily_cap = enroll_cap if enroll_cap is not None else int(
        os.getenv('CROSSPROMO_DAILY_CAP', '150')
    )
    enroll_budget = int(os.getenv('CROSSPROMO_ENROLL_CAP', str(daily_cap)))

    # Crosspromo via ZeptoMail Agent 1 — From pinned to passedai.io (not thesisgenerator.io).
    os.environ['EMAIL_PROVIDER'] = 'zeptomail'
    os.environ.setdefault('ZEPTOMAIL_PASSED_AI_SENDER_EMAIL', CROSSPROMO_FROM)
    os.environ.setdefault('ZEPTOMAIL_PASSED_AI_SENDER_NAME', 'Alex')

    state = _load_state()
    state.setdefault('enrolled', {})
    state.setdefault('sent_counts', {s: 0 for s, _ in STAGES})

    suppressed = _load_suppressed_emails()
    print(f'📬 Building crosspromo pool (suppressions={len(suppressed):,})…')
    pool = build_pool(exclude_emails=suppressed)
    print(f'   Eligible after Thesis/suppression: {len(pool):,}')

    # Drop people who later joined Thesis Auth (re-check via pool builder already
    # excludes Thesis). Also skip bad emails.
    pool = [r for r in pool if not _skip_email(r['email'])]

    # Enroll new contacts (affinity-ordered) up to enroll budget.
    enrolled = state['enrolled']
    newly = 0
    for rec in pool:
        if newly >= enroll_budget:
            break
        email = rec['email']
        existing = enrolled.get(email)
        if existing and not _can_reenroll(existing):
            # Refresh source_apps / language on existing open enrollments
            if not existing.get('completed_at'):
                existing['source_apps'] = rec.get('source_apps') or existing.get('source_apps')
                existing['language'] = rec.get('language') or existing.get('language', 'en')
                existing['affinity'] = rec.get('affinity', existing.get('affinity', 50))
            continue
        enrolled[email] = {
            'enrolled_at': _utc_now(),
            'source_apps': rec.get('source_apps') or [],
            'language': rec.get('language') or 'en',
            'affinity': rec.get('affinity', 50),
            'stages': {},
            'completed_at': None,
        }
        newly += 1
    if newly:
        print(f'   Newly enrolled: {newly:,}')
        if not dry_run:
            _save_state(state)

    # Build due queue sorted by affinity
    due_queue = []
    for email, record in enrolled.items():
        if email in suppressed or _skip_email(email):
            continue
        stage = _due_stage(record)
        if not stage:
            continue
        due_queue.append((email, record, stage))
    due_queue.sort(key=lambda t: (t[1].get('affinity', 50), t[0]))

    if limit > 0:
        due_queue = due_queue[:limit]
    else:
        due_queue = due_queue[:daily_cap]

    print(f'💌 Due sends this run: {len(due_queue):,} (cap={daily_cap})')

    # Health gate prefers passedai.io; ZeptoMail From always pins to that domain.
    identity = pick_healthy_sender(prefer=PREFERRED_SENDER, require_green=True)
    if not identity:
        print('🚨 No green/unknown pool sender available — skipping crosspromo run.')
        if not dry_run:
            _save_state(state)
        return
    from_email = CROSSPROMO_FROM
    from_name = os.getenv('ZEPTOMAIL_PASSED_AI_SENDER_NAME') or identity.get('name') or 'Alex'
    print(f'📤 Health gate: {identity["email"]} ({identity.get("health_status")})')
    print(f'   ZeptoMail From: {from_email} as {from_name}')

    if dry_run:
        for email, record, stage in due_queue[:30]:
            print(
                f"   • {email}  stage={stage}  lang={record.get('language')}  "
                f"affinity={record.get('affinity')}  apps={record.get('source_apps')}"
            )
        print('🏁 DRY RUN — no sends / no state write')
        return

    if not has_email_credentials():
        print('❌ ZEPTOMAIL_API_KEY / email credentials missing')
        return

    sender = GmailSender(sender_email=from_email, sender_name=from_name)
    if not sender.connect():
        print('❌ Failed to connect ZeptoMail sender')
        return

    sent_n = failed = skipped = 0
    for email, record, stage in due_queue:
        # Re-check health mid-run every 50 sends (volume brake — From stays passedai.io)
        if sent_n and sent_n % 50 == 0:
            again = pick_healthy_sender(prefer=PREFERRED_SENDER, require_green=True)
            if not again:
                print('🚨 Pool went unhealthy mid-run — stopping.')
                break

        lang = localize_phrase.normalize_language(record.get('language') or 'en')
        kind = f'{KIND_PREFIX}_{stage}'
        en_src = EN_SOURCES[stage]
        tpl = get_localized(kind, lang, en_src, allow_api=False)
        plan = {'first_name': record.get('first_name') or ''}
        subject = localize_phrase.interpolate(lang, tpl.get('subject', en_src['subject']), plan)
        paragraphs = [
            localize_phrase.interpolate(lang, p, plan)
            for p in tpl.get('body', en_src['body'])
        ]
        cta = tpl.get('cta', en_src['cta'])
        preview = tpl.get('preview', en_src.get('preview', ''))

        html = render_email(
            lang, paragraphs, cta, APP_STORE_URL,
            **crosspromo_render_kwargs(preview_text=preview or None),
        )
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': kind},
            {'name': 'system', 'value': 'crosspromotion'},
            {'name': 'target', 'value': TARGET},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': lang},
        ]
        result = sender.send_email(
            to_email=email,
            subject=subject,
            html_body=html,
            from_name=from_name,
            tags=tags,
            ref_id=_ref(email),
        )
        if result == 'sent':
            sent_n += 1
            record.setdefault('stages', {})[stage] = {
                'sent_at': _utc_now(),
                'language': lang,
                'from': from_email,
            }
            state['sent_counts'][stage] = state['sent_counts'].get(stage, 0) + 1
            if stage == 'e5' or set(record['stages'].keys()) >= {s for s, _ in STAGES}:
                record['completed_at'] = _utc_now()
            if sent_n % 25 == 0:
                _save_state(state)
            print(f'   ✅ [{sent_n}] {email}  {stage}  {lang}')
        elif result in SKIP_RESULTS:
            skipped += 1
            print(f'   ⏭️ {email} result={result}')
        else:
            failed += 1
            print(f'   ❌ {email} result={result}')
        time.sleep(float(os.getenv('CROSSPROMO_SEND_DELAY_SECONDS', '0.35')))

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Crosspromo Thesis done — sent={sent_n}, failed={failed}, skipped={skipped}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Crosspromo Thesis sequence')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--warm', action='store_true')
    parser.add_argument('--adapt', action='store_true',
                        help='With --warm: market-adapt (full rewrite) instead of literal translate')
    parser.add_argument('--refresh-templates', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    if args.status:
        print_status()
        return
    if args.warm:
        warm_templates(adapt=args.adapt, refresh=args.refresh_templates)
        if args.dry_run or args.limit:
            pass  # allow warm+dry-run in one invocation
        else:
            return
    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
