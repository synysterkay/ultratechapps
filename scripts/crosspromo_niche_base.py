#!/usr/bin/env python3
"""Shared short niche crosspromo sequence (tip → install), Agent 2 / passedai.io."""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from gmail_sender import GmailSender, SKIP_RESULTS, has_email_credentials
from thesis_email_chrome import render as render_email
from deliverability_monitor import pick_healthy_sender
from crosspromo_pool import build_pool, source_is_android_first
import localize_phrase

_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
PREFERRED_SENDER = 'hello@passedai.io'
CROSSPROMO_FROM = os.getenv('ZEPTOMAIL_PASSED_AI_SENDER_EMAIL', 'hello@passedai.io')
REENROLL_COOLDOWN_DAYS = 90

# Short 3-email bridge (days 0 / 3 / 7)
DEFAULT_STAGES = [('e1', 0), ('e2', 3), ('e3', 7)]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def _ref(email: str) -> str:
    return hashlib.sha256(f'{_REF_SALT}:{email.lower().strip()}'.encode()).hexdigest()[:16]


def _skip_email(email: str) -> bool:
    e = email.lower()
    return (
        not e
        or 'cloudtestlabaccounts.com' in e
        or e.endswith('@example.com')
        or 'test@' in e
    )


def _load_suppressed() -> set[str]:
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


def _emails_from_export(export_file: str) -> set[str]:
    path = Path(__file__).parent.parent / 'firebase_exports' / export_file
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        users = data if isinstance(data, list) else data.get('users', [])
    except Exception:
        return set()
    out = set()
    for u in users:
        e = (u.get('email') or u.get('Email') or '').lower().strip()
        if e and '@' in e:
            out.add(e)
    return out


def _emails_touched_state(*state_paths: Path) -> set[str]:
    """Emails that already got source tip/founder (eligible for bridge)."""
    out = set()
    for path in state_paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        users = data.get('users') or {}
        out.update(e.lower() for e in users if isinstance(e, str) and '@' in e)
    return out


def run_niche_pack(
    *,
    campaign: str,
    kind_prefix: str,
    target: str,
    app_name: str,
    store_ios: str,
    store_play: str,
    en_sources: dict,
    state_file: Path,
    source_app_names: set[str],
    exclude_export_files: list[str],
    require_source_state_files: list[Path],
    daily_cap_env: str,
    footer: str,
    stages: list[tuple[str, int]] | None = None,
    dry_run: bool = False,
    limit: int = 0,
) -> None:
    stages = stages or DEFAULT_STAGES
    daily_cap = int(os.getenv(daily_cap_env, os.getenv('CROSSPROMO_DAILY_CAP', '60')))
    enroll_budget = int(os.getenv(f'{daily_cap_env.replace("DAILY", "ENROLL")}', str(daily_cap)))

    os.environ['EMAIL_PROVIDER'] = 'zeptomail'
    os.environ.setdefault('ZEPTOMAIL_PASSED_AI_SENDER_EMAIL', CROSSPROMO_FROM)

    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding='utf-8'))
        except Exception:
            state = {}
    else:
        state = {}
    state.setdefault('campaign', campaign)
    state.setdefault('enrolled', {})
    state.setdefault('sent_counts', {s: 0 for s, _ in stages})

    suppressed = _load_suppressed()
    target_emails = set()
    for ef in exclude_export_files:
        target_emails |= _emails_from_export(ef)

    prior = _emails_touched_state(*require_source_state_files)
    print(f'📬 Niche pack {campaign}: prior source touches={len(prior):,}')
    if require_source_state_files and not prior:
        print('⏭️ No source tip/founder sends yet — skip niche pack until prior state exists')
        return

    pool = build_pool(exclude_emails=suppressed | target_emails)
    # Affinity filter: must include at least one source app
    filtered = []
    for rec in pool:
        apps = set(rec.get('source_apps') or [])
        if not (apps & source_app_names):
            continue
        email = rec['email']
        if email not in prior:
            continue
        if _skip_email(email):
            continue
        filtered.append(rec)
    print(f'   Eligible after source/prior/target filters: {len(filtered):,}')

    enrolled = state['enrolled']
    newly = 0
    for rec in filtered:
        if newly >= enroll_budget:
            break
        email = rec['email']
        existing = enrolled.get(email)
        if existing and existing.get('completed_at'):
            try:
                days = (datetime.now(timezone.utc) - _parse_ts(existing['completed_at'])).days
                if days < REENROLL_COOLDOWN_DAYS:
                    continue
            except Exception:
                continue
        elif existing and not existing.get('completed_at'):
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

    def due_stage(record: dict) -> str | None:
        if record.get('completed_at'):
            return None
        stages_sent = set((record.get('stages') or {}).keys())
        try:
            days = (datetime.now(timezone.utc) - _parse_ts(record.get('enrolled_at') or _utc_now())).days
        except Exception:
            days = 0
        for key, min_day in stages:
            if key in stages_sent:
                continue
            if days >= min_day:
                return key
            break
        return None

    due_queue = []
    for email, record in enrolled.items():
        if email in suppressed or email in target_emails or _skip_email(email):
            continue
        stage = due_stage(record)
        if not stage:
            continue
        if GmailSender.already_emailed_today(email):
            continue
        due_queue.append((email, record, stage))
    due_queue.sort(key=lambda t: (t[1].get('affinity', 50), t[0]))
    if limit > 0:
        due_queue = due_queue[:limit]
    else:
        due_queue = due_queue[:daily_cap]

    print(f'💌 Due sends: {len(due_queue):,} (cap={daily_cap})')

    identity = pick_healthy_sender(prefer=PREFERRED_SENDER, require_green=True)
    if not identity:
        print('🚨 No healthy pool sender — skip niche pack')
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state['updated_at'] = _utc_now()
        state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
        return

    from_email = CROSSPROMO_FROM
    from_name = os.getenv('ZEPTOMAIL_PASSED_AI_SENDER_NAME') or 'Alex'
    print(f'📤 From {from_email} as {from_name}')

    if dry_run:
        for email, record, stage in due_queue[:25]:
            print(f'   • {email}  {stage}  apps={record.get("source_apps")}')
        print('🏁 DRY RUN')
        return

    if not has_email_credentials():
        print('❌ Email credentials missing')
        return

    sender = GmailSender(sender_email=from_email, sender_name=from_name)
    if not sender.connect():
        return

    ios = {'url': store_ios, 'variant': 'ios', 'line1': 'Download on the', 'line2': 'App Store'}
    play = {'url': store_play, 'variant': 'android', 'line1': 'GET IT ON', 'line2': 'Google Play'}

    sent_n = failed = 0
    for email, record, stage in due_queue:
        src = en_sources[stage]
        plan = {'first_name': ''}
        subject = localize_phrase.interpolate('en', src['subject'], plan)
        paragraphs = [localize_phrase.interpolate('en', p, plan) for p in src['body']]
        android_first = source_is_android_first(record.get('source_apps') or [])
        fallback = store_play if android_first else store_ios
        html = render_email(
            'en', paragraphs, src['cta'], fallback,
            sender_name='Alex', sender_org='Kaynel', app_name=app_name,
            gradient='invite', greeting_override='', footer_override=footer,
            address_override='Kaynel', compact=True,
            preview_text=src.get('preview'),
            cta_links=[play, ios] if android_first else [ios, play],
        )
        kind = f'{kind_prefix}_{stage}'
        tags = [
            {'name': 'app', 'value': 'crosspromo'},
            {'name': 'kind', 'value': kind},
            {'name': 'system', 'value': 'crosspromotion'},
            {'name': 'target', 'value': target},
            {'name': 'stage', 'value': stage},
            {'name': 'language', 'value': 'en'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html,
            from_name=from_name, tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent_n += 1
            record.setdefault('stages', {})[stage] = {'sent_at': _utc_now()}
            state['sent_counts'][stage] = state['sent_counts'].get(stage, 0) + 1
            if stage == stages[-1][0] or set(record['stages']) >= {s for s, _ in stages}:
                record['completed_at'] = _utc_now()
            print(f'   ✅ [{sent_n}] {email}  {stage}')
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} {result}')
        else:
            failed += 1
        time.sleep(float(os.getenv('CROSSPROMO_SEND_DELAY_SECONDS', '0.35')))

    sender.disconnect()
    state['updated_at'] = _utc_now()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2), encoding='utf-8')
    print(f'📊 {campaign} done — sent={sent_n}, failed={failed}')
