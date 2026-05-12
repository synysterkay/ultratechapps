#!/usr/bin/env python3
"""
Weekly Progress Recap Sender (Thesis Generator)

Sunday cron: for every user active in the last 14 days, summarize what
they did this week (theses worked on, total words generated, streak,
ranking quartile) and send a recap. Social-comparison variable reward
+ investment summary.

Designed to be run from `retention-emails.yml` on Sundays only (the
guard inside main() short-circuits other days).
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from gmail_sender import GmailSender
from thesis_users_loader import (
    get_access_token, load_users_dict, load_theses_by_status, is_paid,
)
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
KIND = 'weekly_progress'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'weekly_progress_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': "Your week, {{first_name}}",
    'body': [
        "Quick recap of this week:",
        "{{week_summary}}",
        "If you can squeeze in one chapter this weekend, next Sunday's recap is going to look even better.",
    ],
    'cta': 'Open the app',
}


def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {'users': {}}


def _save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _ref(email):
    return hashlib.sha256(f"{_REF_SALT}:{email.lower().strip()}".encode()).hexdigest()[:16]


def _week_summary(lang, theses_this_week, words_this_week, streak):
    """Build a short bullet-style summary string. Hand-localized for
    the 6 manually-curated languages and falls back to English for the
    rest (the surrounding paragraphs are DeepSeek-translated)."""
    table = {
        'en': f"{theses_this_week} thesis touched · {words_this_week:,} new words · streak {streak}",
        'es': f"{theses_this_week} tesis · {words_this_week:,} palabras nuevas · racha {streak}",
        'fr': f"{theses_this_week} mémoires · {words_this_week:,} nouveaux mots · série {streak}",
        'ar': f"{theses_this_week} أطروحات · {words_this_week:,} كلمات جديدة · سلسلة {streak}",
        'zh': f"{theses_this_week} 篇论文 · 新写 {words_this_week:,} 字 · 连胜 {streak} 天",
        'hi': f"{theses_this_week} थीसिस · {words_this_week:,} नए शब्द · लय {streak}",
        'de': f"{theses_this_week} Arbeiten · {words_this_week:,} neue Wörter · Serie {streak}",
        'pt': f"{theses_this_week} teses · {words_this_week:,} palavras novas · sequência {streak}",
        'it': f"{theses_this_week} tesi · {words_this_week:,} nuove parole · serie {streak}",
        'ru': f"{theses_this_week} работ · {words_this_week:,} новых слов · серия {streak}",
        'ja': f"{theses_this_week} 件 · 新規 {words_this_week:,} 語 · 連続 {streak} 日",
        'ko': f"{theses_this_week}편 · 새로 {words_this_week:,}자 · 연속 {streak}일",
        'tr': f"{theses_this_week} tez · {words_this_week:,} yeni kelime · {streak} günlük seri",
        'nl': f"{theses_this_week} stuks · {words_this_week:,} nieuwe woorden · reeks {streak}",
        'pl': f"{theses_this_week} prac · {words_this_week:,} nowych słów · seria {streak}",
        'sv': f"{theses_this_week} arbeten · {words_this_week:,} nya ord · svit {streak}",
        'ro': f"{theses_this_week} lucrări · {words_this_week:,} cuvinte noi · serie {streak}",
        'id': f"{theses_this_week} skripsi · {words_this_week:,} kata baru · streak {streak}",
        'th': f"{theses_this_week} ฉบับ · {words_this_week:,} คำใหม่ · ต่อเนื่อง {streak} วัน",
        'vi': f"{theses_this_week} bài · {words_this_week:,} từ mới · chuỗi {streak} ngày",
    }
    return table.get(lang, table['en'])


def main(dry_run=False, force=False):
    # Guard: only Sundays unless forced. The workflow can fire any day but
    # we only want this to actually do work on Sundays.
    now = datetime.now(timezone.utc)
    if now.weekday() != 6 and not force:
        print(f'⏭️  Not Sunday (weekday={now.weekday()}) — skipping.')
        return

    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    week_start = (now - timedelta(days=7))
    today = now.date().isoformat()

    # Aggregate by user: count thesis docs touched in last 7d + word totals.
    print('🔎 Fetching theses + users...')
    by_email, by_uid = load_users_dict(token)
    activity = defaultdict(lambda: {'count': 0, 'words': 0})
    for status in ('draft', 'in_progress', 'completed', 'generating'):
        for t in load_theses_by_status(token, [status]):
            last = t.get('last_modified') or t.get('created_at')
            if not last or last < week_start:
                continue
            uid = t.get('user_id')
            if not uid:
                continue
            activity[uid]['count'] += 1
            activity[uid]['words'] += int(t.get('word_count') or 0)

    candidates = []
    for uid, agg in activity.items():
        user = by_uid.get(uid)
        if not user or not user.get('email'):
            continue
        # Dedupe: one weekly email per (week_iso, user).
        wk = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
        if state['users'].get(user['email'], {}).get('last_week_sent') == wk:
            continue
        candidates.append((user, agg, wk))

    if not candidates:
        print('✅ No active users this week.')
        return
    print(f'📬 {len(candidates)} weekly recaps to send')
    if dry_run:
        for u, agg, wk in candidates[:20]:
            print(f"   • {u['email']}  count={agg['count']}  words={agg['words']}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent_n = failed = 0
    for u, agg, wk in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        streak = (u.get('streak') or {}).get('current') or 0
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['week_summary'] = _week_summary(lang, agg['count'], agg['words'], streak)
        plan['streak'] = streak

        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
        paragraphs_tpl = tpl.get('body', EN_SOURCE['body'])
        # The {{week_summary}} placeholder isn't part of localize_phrase's
        # built-in repl set — substitute it manually before interpolate.
        paragraphs = []
        for p in paragraphs_tpl:
            p = p.replace('{{week_summary}}', plan['week_summary'])
            paragraphs.append(localize_phrase.interpolate(lang, p, plan))
        cta_text = tpl.get('cta', EN_SOURCE['cta'])

        html = render_email(lang, paragraphs, cta_text, APP_STORE_URL,
                            sender_name='Ana', app_name=APP_NAME, gradient='progress')
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': KIND},
            {'name': 'language', 'value': lang},
            {'name': 'paid', 'value': '1' if is_paid(u) else '0'},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_ref(email),
        )
        if result == 'sent':
            sent_n += 1
            state['users'][email] = {
                'last_week_sent': wk,
                'last_sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent_n % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent_n}] {email}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent_n}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv, force='--force' in sys.argv)
