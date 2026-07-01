#!/usr/bin/env python3
"""
Thesis Generator founder-story email — once-ever letter to the full user base.

Campaign kind `founder_story_thesis_v2` (Ana hybrid copy). Re-sends to users who
already received v1 (`founder_story_thesis`) because dedup is tracked separately.

Usage:
  python3 scripts/founder_story_thesis_sender.py --dry-run
  python3 scripts/founder_story_thesis_sender.py --warm
  python3 scripts/founder_story_thesis_sender.py
  python3 scripts/founder_story_thesis_sender.py --passes 3
  python3 scripts/founder_story_thesis_sender.py --daily   # orchestrator catch-up
  python3 scripts/founder_story_thesis_sender.py --rebuild-state  # restore dedup from Supabase
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender, SKIP_RESULTS
from firebase_user_loader import FirebaseUserLoader
from firestore_language_loader import FirestoreLanguageLoader
from thesis_users_loader import get_access_token, load_all_users, normalize_user_language
from thesis_template_translator import get_localized, warm_all, SUPPORTED, _read_cache
from thesis_email_chrome import render as render_email
from deliverability_monitor import DeliverabilityMonitor
import localize_phrase

APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
LEGACY_KIND = 'founder_story_thesis'
KIND = 'founder_story_thesis_v2'
TEMPLATE_KIND = 'founder_story_thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
GOOGLE_PLAY_URL = 'https://play.google.com/store/apps/details?id=com.thesis.generator.ai'
WEB_APP_URL = 'https://thesisgenerator.io'
LEGACY_STATE_FILE = Path(__file__).parent.parent / 'cache' / 'founder_story_thesis_state.json'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'founder_story_thesis_v2_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
BACKFILL_CAP = int(os.getenv('FOUNDER_STORY_THESIS_SEND_CAP', '2000'))
DAILY_CATCHUP_CAP = int(os.getenv('FOUNDER_STORY_THESIS_DAILY_CAP', '50'))

EN_SOURCE = {
    'subject': '{{first_name}}, still staring at a blank page?',
    'body': [
        'Every semester, students promise themselves: "This time I\'ll start early." Then a week becomes three days, three days become one night — and suddenly it\'s 2:14 AM with twenty tabs open and references everywhere.',
        "I built Thesis Generator because academic writing isn't laziness — it's overwhelming. Not something that thinks for you. Something that helps you think faster.",
        "One of our teammates hit that wall for real: {{work_type}} due in 48 hours, topic set, research done — then days where typing normally wasn't an option. She opened the app we'd spent a year building. Ten minutes later she had a full draft — outline, chapters, references. She edited it, submitted it, and passed 5/5.",
        "That's why Thesis Generator exists: turn {{topic}} from something you're avoiding into something you can open, edit, and submit.",
        "Your next step takes about three minutes: enter what you already know about {{topic}}, tap generate, and work from a draft instead of a blank page. Your ideas deserve more time than formatting.",
        "P.S. A rough draft today beats a perfect plan next week. Start while you still have days — not hours.",
    ],
    'cta': 'Generate my {{work_type}}',
    'cta_android': 'Get it on Android',
    'cta_web': 'Open the web app',
}


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv('SUPABASE_URL', '').rstrip('/')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
    if url and key:
        return url, key
    cfg = Path(__file__).resolve().parents[1] / 'config' / 'supabase_config.json'
    if cfg.exists():
        data = json.loads(cfg.read_text())
        return data['project']['url'].rstrip('/'), data['project']['service_role_key']
    return '', ''


def _fetch_sent_from_supabase(kind: str | None = None) -> dict[str, dict]:
    """Recipients with email.sent events for this campaign (dedup source of truth)."""
    kind = kind or KIND
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
                    'kind': f'eq.{kind}',
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


def _load_state_file(path: Path, kind: str) -> dict:
    state: dict = {'sent': {}}
    if path.exists():
        try:
            state = json.loads(path.read_text())
        except Exception:
            pass
    state.setdefault('sent', {})
    remote = _fetch_sent_from_supabase(kind)
    merged = 0
    for email, info in remote.items():
        if email not in state['sent']:
            state['sent'][email] = info
            merged += 1
    if merged:
        print(f'   📎 Merged {merged} {kind} recipients from Supabase email_events')
    return state


def _load_state() -> dict:
    return _load_state_file(STATE_FILE, KIND)


def load_combined_founder_story_state() -> dict:
    """Merge v1 + v2 founder story sends; earliest sent_at wins per email."""
    combined: dict[str, dict] = {}
    for kind, path in (
        (LEGACY_KIND, LEGACY_STATE_FILE),
        (KIND, STATE_FILE),
    ):
        state = _load_state_file(path, kind)
        for email, rec in state.get('sent', {}).items():
            email = email.lower().strip()
            if not email:
                continue
            existing = combined.get(email)
            if not existing:
                combined[email] = {**rec, 'kind': kind}
                continue
            cur = rec.get('sent_at') or ''
            prev = existing.get('sent_at') or ''
            if cur and (not prev or cur < prev):
                combined[email] = {**rec, 'kind': kind}
    return {'sent': combined}


def rebuild_state_from_supabase() -> int:
    """Rebuild cache/founder_story_thesis_v2_state.json from email_events."""
    remote = _fetch_sent_from_supabase()
    state = {'sent': remote, 'rebuilt_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    _save_state(state)
    print(f'✅ Rebuilt {STATE_FILE.name}: {len(remote)} recipients')
    return len(remote)


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


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


def _connect_senders() -> list[GmailSender]:
    senders: list[GmailSender] = []
    for info in DeliverabilityMonitor.SENDER_POOL:
        if not info.get('active', True):
            continue
        gs = GmailSender(sender_email=info['email'], sender_name=info['name'])
        if gs.connect():
            senders.append(gs)
        time.sleep(0.3)
    return senders


def _plan_for_user(user: dict) -> dict:
    plan = dict(user.get('plan') or {})
    plan['first_name'] = plan.get('first_name') or user.get('first_name') or 'there'
    plan['topic'] = plan.get('topic') or plan.get('subject') or 'your thesis'
    wt = plan.get('workType') or plan.get('work_type') or 'fullThesis'
    plan['work_type'] = wt
    return plan


def warm_templates(refresh: bool = False) -> None:
    """Pre-fill cache/thesis_templates/founder_story_thesis_{lang}.json."""
    if not os.environ.get('DEEPSEEK_API_KEY', '').strip():
        raise SystemExit('DEEPSEEK_API_KEY not set — cannot warm translations')
    if refresh:
        cache_dir = Path(__file__).resolve().parents[1] / 'cache' / 'thesis_templates'
        removed = 0
        for path in cache_dir.glob(f'{TEMPLATE_KIND}_*.json'):
            if path.name.endswith('_en.json'):
                continue
            path.unlink(missing_ok=True)
            removed += 1
        if removed:
            print(f'   🔄 Cleared {removed} cached {TEMPLATE_KIND} translations for refresh')
    _write_en_cache()
    print(f'🔥 Warming {TEMPLATE_KIND} for {len(SUPPORTED) - 1} languages…')
    result = warm_all(TEMPLATE_KIND, EN_SOURCE)
    ok = sum(1 for v in result.values() if v in ('cached', 'translated'))
    print(f'✅ Warm complete: {ok}/{len(SUPPORTED) - 1} languages ready')


def _write_en_cache() -> None:
    from thesis_template_translator import _write_cache
    _write_cache(TEMPLATE_KIND, 'en', EN_SOURCE)


def _fetch_language_map() -> dict[str, str]:
    """email → canonical lang. Live Firestore fetch with cache fallback."""
    print('   🌍 Loading Thesis Generator user languages…')
    langs = FirestoreLanguageLoader().fetch_user_languages(APP_NAME)
    out = {}
    for email, lang in langs.items():
        out[email.lower().strip()] = normalize_user_language(lang)
    print(f'   ✅ Language map: {len(out)} users')
    return out


def _load_candidates(token: str | None, lang_by_email: dict[str, str]) -> list[dict]:
    """All Thesis Generator auth users with language + Firestore plan when available."""
    auth_users = FirebaseUserLoader().load_users_by_app().get(APP_NAME, [])
    fs_by_email: dict[str, dict] = {}
    fs_by_uid: dict[str, dict] = {}
    if token:
        for u in load_all_users(token):
            fs_by_email[u['email']] = u
            if u.get('uid'):
                fs_by_uid[u['uid']] = u

    out: list[dict] = []
    for au in auth_users:
        email = au['email'].lower().strip()
        uid = au.get('uid', '')
        fs = fs_by_email.get(email) or (fs_by_uid.get(uid) if uid else None)

        lang = lang_by_email.get(email)
        if not lang and fs:
            lang = normalize_user_language(fs.get('language') or 'en')
        if not lang:
            lang = 'en'

        if fs:
            user = {**au, **fs, 'language': lang}
        else:
            local = email.split('@', 1)[0]
            user = {
                **au,
                'email': email,
                'first_name': local.split('.')[0].capitalize() if local else 'there',
                'language': lang,
                'plan': {},
            }
        out.append(user)
    return out


def _fix_mislocalized(state: dict, lang_by_email: dict[str, str]) -> int:
    """Drop state entries sent in the wrong language so we can resend correctly."""
    sent = state.get('sent', {})
    cleared = []
    for email, rec in list(sent.items()):
        correct = lang_by_email.get(email.lower().strip()) or 'en'
        correct = normalize_user_language(correct)
        sent_lang = normalize_user_language(rec.get('language') or 'en')
        if sent_lang != correct:
            cleared.append((email, sent_lang, correct))
            del sent[email]
    if cleared:
        print(f'   🔄 Cleared {len(cleared)} mislocalized sends for resend:')
        for email, was, now in cleared[:15]:
            print(f'      {email}: {was} → {now}')
        if len(cleared) > 15:
            print(f'      … and {len(cleared) - 15} more')
    return len(cleared)


def _print_lang_distribution(users: list[dict]) -> None:
    from collections import Counter
    counts = Counter(u.get('language', 'en') for u in users)
    print('   📊 Language distribution (eligible cohort):')
    for lang, n in counts.most_common(12):
        print(f'      {lang}: {n}')
    if len(counts) > 12:
        print(f'      … +{len(counts) - 12} more languages')


def run_send(*, dry_run: bool = False, send_cap: int | None = None, fix_languages: bool = False) -> list[str]:
    """Send founder story to users who haven't received it. Returns emails sent."""
    cap = send_cap if send_cap is not None else BACKFILL_CAP
    state = _load_state()
    state.setdefault('sent', {})
    already = set(state['sent'].keys())

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set — language map uses cache only')

    lang_by_email = _fetch_language_map()
    if fix_languages:
        _fix_mislocalized(state, lang_by_email)
        _save_state(state)
        already = set(state['sent'].keys())

    suppressed = _load_suppressed_emails()
    if suppressed:
        print(f'   🚫 {len(suppressed)} suppressed addresses')

    all_users = _load_candidates(token, lang_by_email)
    candidates = []
    for user in all_users:
        email = user['email']
        if _skip_email(email) or email in already or email in suppressed:
            continue
        if GmailSender._is_suppressed(email, APP_SLUG):
            continue
        candidates.append(user)

    print(f'📬 {len(candidates)} users eligible (cap={cap}, already sent={len(already)})')
    if candidates and not dry_run:
        _print_lang_distribution(candidates[:5000])
    if not candidates:
        return []

    if dry_run:
        _print_lang_distribution(candidates)
        for u in candidates[:30]:
            print(f"   • {u['email']}  lang={u.get('language', 'en')}")
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
    for i, user in enumerate(candidates):
        if len(sent_emails) >= cap:
            print(f'   🛑 Cap hit ({cap})')
            break

        email = user['email']
        lang = normalize_user_language(user.get('language') or 'en')
        plan = _plan_for_user(user)

        if lang != 'en' and _read_cache(TEMPLATE_KIND, lang) is None:
            print(f'   ⚠️ No cached template for {TEMPLATE_KIND}/{lang} — using English')
        tpl = get_localized(TEMPLATE_KIND, lang, EN_SOURCE, allow_api=False)
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
            sender_name='Ana',
            app_name=APP_NAME,
            gradient='invite',
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
            {'name': 'system', 'value': 'thesis_founder_story_v2'},
        ]
        result = sender.send_email(
            to_email=email,
            subject=subject,
            html_body=html,
            from_name=APP_NAME,
            tags=tags,
            ref_id=_ref(email),
        )
        if result == 'sent':
            sent_emails.append(email)
            state['sent'][email] = {
                'sent_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'language': lang,
                'uid': user.get('uid'),
            }
            if len(sent_emails) % 25 == 0:
                _save_state(state)
            print(f'   ✅ [{len(sent_emails)}] {email} ({lang})')
        elif result in SKIP_RESULTS:
            skipped += 1
            print(f'   ⏭️ {email} result={result}')
        else:
            failed += 1
            print(f'   ❌ {email} result={result}')
        time.sleep(0.25)

    _save_state(state)
    print(f'\n📊 Done — sent {len(sent_emails)}, skipped {skipped}, failed {failed}, total ever {len(state["sent"])}')
    return sent_emails


def main(dry_run: bool = False, warm_only: bool = False, passes: int = 1, daily: bool = False, fix_languages: bool = False, rebuild_state: bool = False, refresh_templates: bool = False) -> None:
    if rebuild_state:
        rebuild_state_from_supabase()
        return

    if warm_only:
        warm_templates(refresh=refresh_templates)
        return

    _write_en_cache()
    cap = DAILY_CATCHUP_CAP if daily else BACKFILL_CAP
    passes = int(os.environ.get('FOUNDER_STORY_THESIS_PASSES', passes))
    total = 0
    for n in range(1, passes + 1):
        if passes > 1 and not daily:
            print(f'\n=== Thesis founder story pass {n}/{passes} ===')
        batch = run_send(dry_run=dry_run, send_cap=cap, fix_languages=fix_languages and n == 1)
        total += len(batch)
        if dry_run:
            break
        if not batch:
            print('No more eligible users — stopping early')
            break
        if not daily and len(batch) < cap:
            print(f'Partial pass ({len(batch)}/{cap}) — backlog exhausted')
            break
    if passes > 1 and not dry_run and not daily:
        print(f'\n📬 Total sent across passes: {total}')


if __name__ == '__main__':
    passes = 1
    for i, arg in enumerate(sys.argv):
        if arg == '--passes' and i + 1 < len(sys.argv):
            passes = int(sys.argv[i + 1])
    main(
        dry_run='--dry-run' in sys.argv,
        warm_only='--warm' in sys.argv,
        passes=passes,
        daily='--daily' in sys.argv,
        fix_languages='--fix-languages' in sys.argv,
        rebuild_state='--rebuild-state' in sys.argv,
        refresh_templates='--refresh-templates' in sys.argv,
    )
