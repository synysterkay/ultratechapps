#!/usr/bin/env python3
"""
Cumulative-Stats Sender (Thesis Generator)

Monthly send: for every user with non-trivial lifetime activity, summarize
their cumulative numbers (total theses, total words, longest streak,
months active). Loss-aversion reminder of accumulated value — Hooked's
"Investment" stage externalized via email.

Fires on the 1st of each month for users active at least once in the
last 60 days. One send per (month, user).
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

from gmail_sender import GmailSender, SKIP_RESULTS
from thesis_users_loader import (
    get_access_token, load_users_dict, load_theses_by_status, is_paid,
)
from thesis_template_translator import get_localized
from thesis_email_chrome import render as render_email
import localize_phrase


APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
KIND = 'cumulative_stats'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'cumulative_stats_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


EN_SOURCE = {
    'subject': "Your Thesis Generator numbers, {{first_name}}",
    'body': [
        "Quick monthly summary of what you've built in the app:",
        "{{stats_block}}",
        "If you keep going at this pace, that next number on the right gets meaningfully bigger by next month.",
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


def _stats_block(lang, total_theses, total_words, longest_streak, months_active):
    """Compact, language-aware bullet block. Numbers stay numeric; labels
    are localized."""
    labels = {
        'en': ('theses', 'total words', 'longest streak', 'months active'),
        'es': ('tesis', 'palabras totales', 'mejor racha', 'meses activos'),
        'fr': ('mémoires', 'mots au total', 'meilleure série', 'mois actifs'),
        'ar': ('أطروحات', 'إجمالي الكلمات', 'أطول سلسلة', 'الأشهر النشطة'),
        'zh': ('篇论文', '总字数', '最长连胜', '活跃月数'),
        'hi': ('थीसिस', 'कुल शब्द', 'सबसे लंबी लय', 'सक्रिय महीने'),
        'de': ('Arbeiten', 'Wörter insgesamt', 'längste Serie', 'aktive Monate'),
        'pt': ('teses', 'palavras no total', 'maior sequência', 'meses ativos'),
        'it': ('tesi', 'parole totali', 'serie più lunga', 'mesi attivi'),
        'ru': ('работ', 'всего слов', 'самая длинная серия', 'активных месяцев'),
        'ja': ('論文', '総単語数', '最長連続', 'アクティブ月数'),
        'ko': ('논문', '총 단어 수', '최장 연속', '활동 개월'),
        'tr': ('tez', 'toplam kelime', 'en uzun seri', 'aktif ay'),
        'nl': ('scripties', 'totaal woorden', 'langste reeks', 'actieve maanden'),
        'pl': ('prac', 'słów łącznie', 'najdłuższa seria', 'aktywne miesiące'),
        'sv': ('arbeten', 'totalt ord', 'längsta svit', 'aktiva månader'),
        'ro': ('lucrări', 'cuvinte în total', 'cea mai lungă serie', 'luni active'),
        'id': ('skripsi', 'total kata', 'streak terpanjang', 'bulan aktif'),
        'th': ('ฉบับ', 'คำทั้งหมด', 'ต่อเนื่องยาวสุด', 'เดือนใช้งาน'),
        'vi': ('bài', 'tổng số từ', 'chuỗi dài nhất', 'tháng hoạt động'),
    }
    a, b, c, d = labels.get(lang, labels['en'])
    return (f"• {total_theses} {a}\n"
            f"• {total_words:,} {b}\n"
            f"• {longest_streak} {c}\n"
            f"• {months_active} {d}")


def main(dry_run=False, force=False):
    now = datetime.now(timezone.utc)
    # Run on the 1st of the month unless forced.
    if now.day != 1 and not force:
        print(f'⏭️  Not the 1st (day={now.day}) — skipping.')
        return

    state = _load_state()
    state.setdefault('users', {})

    token = get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set')
        return

    cutoff = now - timedelta(days=60)
    by_email, by_uid = load_users_dict(token)

    print('🔎 Aggregating theses per user...')
    agg = defaultdict(lambda: {'count': 0, 'words': 0, 'latest': None, 'earliest': None})
    for status in ('draft', 'in_progress', 'completed', 'generating', 'failed'):
        for t in load_theses_by_status(token, [status]):
            uid = t.get('user_id')
            if not uid:
                continue
            agg[uid]['count'] += 1
            agg[uid]['words'] += int(t.get('word_count') or 0)
            for k, ts in (('latest', t.get('last_modified') or t.get('created_at')),
                          ('earliest', t.get('created_at'))):
                if not ts:
                    continue
                cur = agg[uid][k]
                if k == 'latest' and (cur is None or ts > cur):
                    agg[uid][k] = ts
                if k == 'earliest' and (cur is None or ts < cur):
                    agg[uid][k] = ts

    month_key = now.strftime('%Y-%m')
    candidates = []
    for uid, a in agg.items():
        if not a['latest'] or a['latest'] < cutoff:
            continue
        user = by_uid.get(uid)
        if not user or not user.get('email'):
            continue
        if state['users'].get(user['email'], {}).get('last_month_sent') == month_key:
            continue
        # Skip users with effectively no investment yet.
        if a['count'] < 1 or a['words'] < 200:
            continue
        candidates.append((user, a))

    if not candidates:
        print('✅ No cumulative-stats candidates.')
        return
    print(f'📈 {len(candidates)} cumulative recaps queued')
    if dry_run:
        for u, a in candidates[:20]:
            print(f"   • {u['email']}  count={a['count']}  words={a['words']}  lang={u['language']}")
        print('🏁 DRY RUN')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent_n = failed = 0
    for u, a in candidates:
        email = u['email']
        lang = u.get('language') or 'en'
        streak = (u.get('streak') or {}).get('longest') or (u.get('streak') or {}).get('current') or 0
        months_active = 1
        if a['earliest'] and a['latest']:
            delta_days = max(1, (a['latest'] - a['earliest']).days)
            months_active = max(1, delta_days // 30)
        plan = dict(u.get('plan') or {})
        plan['first_name'] = plan.get('first_name') or u.get('first_name', '')
        plan['stats_block'] = _stats_block(lang, a['count'], a['words'], streak, months_active)

        tpl = get_localized(KIND, lang, EN_SOURCE)
        subject = localize_phrase.interpolate(lang, tpl.get('subject', EN_SOURCE['subject']), plan)
        paragraphs = []
        for p in tpl.get('body', EN_SOURCE['body']):
            p = p.replace('{{stats_block}}', plan['stats_block'].replace('\n', '<br>'))
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
                'last_month_sent': month_key,
                'last_sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent_n % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent_n}] {email}  {lang}')
        elif result in SKIP_RESULTS:
            print(f'   ⏭️ {email} result={result}')
        else:
            failed += 1
            print(f'   ❌ {email} result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent_n}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv, force='--force' in sys.argv)
