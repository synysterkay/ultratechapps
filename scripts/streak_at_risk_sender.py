#!/usr/bin/env python3
"""
Streak-at-Risk Sender (Thesis Generator)

Sends one personalized email when:
  * the user has a streak ≥ 3 days
  * the user hasn't been active for ≥ 18 hours
  * the streak has not already been "rescued" today

Mirrors the in-app streak-at-risk push notification — together they form
the loss-aversion trigger that Hooked calls "internal trigger reinforcement".

Streak data lives in SharedPreferences on-device today. For the email
channel we read the equivalent counters from the Firestore `users/{uid}`
document where the Flutter app mirrors them (fields: `streak.current`,
`streak.last_active_at`). If those fields aren't present, the user is
skipped — no false alarms.

Usage:
    python scripts/streak_at_risk_sender.py
    python scripts/streak_at_risk_sender.py --dry-run
"""
import os
import sys
import json
import time
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from firestore_plan_loader import FirestorePlanLoader
from gmail_sender import GmailSender
import localize_phrase

APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'streak_at_risk_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')

# Firestore project (matches firestore_plan_loader's mapping).
PROJECT_ID = 'thesis-generator-web'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'


SUBJECTS = {
    'en': "Don't lose your {{streak}}, {{first_name}}",
    'es': "No pierdas tu {{streak}}, {{first_name}}",
    'fr': "Ne perds pas ta {{streak}}, {{first_name}}",
    'ar': "لا تضع {{streak}} يا {{first_name}}",
    'zh': "{{first_name}}，别让 {{streak}} 中断",
    'hi': "{{first_name}}, अपनी {{streak}} मत खोएं",
}


BODY = {
    'en': [
        "You're on a {{streak}} 🔥 — and you're one inactive day away from losing it.",
        "Two minutes in the app keeps it alive. Open it now and the counter goes up tomorrow.",
    ],
    'es': [
        "Llevas una {{streak}} 🔥 — y estás a un día inactivo de perderla.",
        "Dos minutos en la app la mantienen viva. Ábrela ahora y mañana el contador sube.",
    ],
    'fr': [
        "Tu es sur une {{streak}} 🔥 — et un jour d'inactivité suffit à la perdre.",
        "Deux minutes dans l'app suffisent. Ouvre-la maintenant et le compteur monte demain.",
    ],
    'ar': [
        "أنت في {{streak}} 🔥 — ويوم واحد من الغياب يكفي لفقدانها.",
        "دقيقتان في التطبيق تكفيان للحفاظ عليها. افتحه الآن ليرتفع العدّاد غدًا.",
    ],
    'zh': [
        "你已连续 {{streak}} 🔥 —— 再有一天不打开就会清零。",
        "在应用里花两分钟就够了，明天计数会继续上升。",
    ],
    'hi': [
        "आप {{streak}} पर हैं 🔥 — और एक खाली दिन इसे तोड़ देगा।",
        "ऐप में दो मिनट काफी हैं। अभी खोलें, कल काउंटर बढ़ेगा।",
    ],
}

CTA = {
    'en': 'Keep my streak alive',
    'es': 'Mantener mi racha',
    'fr': 'Garder ma série',
    'ar': 'حافظ على سلسلتي',
    'zh': '保持连胜',
    'hi': 'मेरी लय बनाए रखें',
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


def _user_ref(email):
    return hashlib.sha256(f"{_REF_SALT}:{email.lower().strip()}".encode()).hexdigest()[:16]


def _fetch_streaks(access_token):
    """Return {email: {streak:int, last_active: datetime}} from Firestore.
    Reads `streak.current` and `streak.last_active_at` if the app writes them.
    """
    url = f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)/documents/users"
    headers = {'Authorization': f'Bearer {access_token}'}
    out = {}
    page_token = None
    while True:
        params = {'pageSize': 300}
        if page_token:
            params['pageToken'] = page_token
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code != 200:
                break
            data = resp.json()
            for doc in data.get('documents', []):
                fields = doc.get('fields', {})
                email = fields.get('email', {}).get('stringValue', '').lower().strip()
                if not email:
                    continue
                streak_map = fields.get('streak', {}).get('mapValue', {}).get('fields', {})
                if not streak_map:
                    continue
                current = streak_map.get('current', {}).get('integerValue')
                if current is None:
                    continue
                try:
                    current = int(current)
                except Exception:
                    continue
                last_iso = streak_map.get('last_active_at', {}).get('timestampValue')
                last_active = None
                if last_iso:
                    try:
                        last_active = datetime.fromisoformat(last_iso.replace('Z', '+00:00'))
                    except Exception:
                        pass
                out[email] = {'streak': current, 'last_active': last_active}
            page_token = data.get('nextPageToken')
            if not page_token:
                break
        except Exception:
            break
    return out


def _build_html(language, paragraphs, cta_text, cta_url, sender_name='Ana'):
    is_rtl = language == 'ar'
    dir_attr = ' dir="rtl"' if is_rtl else ''
    text_align = 'right' if is_rtl else 'left'
    greetings = {'en': 'Hey,', 'ar': 'مرحبًا،', 'es': 'Hola,', 'fr': 'Salut,', 'zh': '你好，', 'hi': 'नमस्ते,'}
    signoffs = {'en': 'Talk soon,', 'ar': 'إلى اللقاء،', 'es': 'Hasta pronto,', 'fr': 'À bientôt,', 'zh': '回头聊，', 'hi': 'जल्द बात करते हैं,'}
    footer = {
        'en': f"You're receiving this because you signed up for {APP_NAME}.",
        'ar': f"تتلقى هذا البريد لأنك سجلت في {APP_NAME}.",
        'es': f"Recibes esto porque te registraste en {APP_NAME}.",
        'fr': f"Vous recevez ceci car vous vous êtes inscrit(e) à {APP_NAME}.",
        'zh': f"您收到此邮件是因为您注册了 {APP_NAME}。",
        'hi': f"आपको यह ईमेल इसलिए मिल रहा है क्योंकि आपने {APP_NAME} के लिए साइन अप किया है।",
    }.get(language, f"You're receiving this because you signed up for {APP_NAME}.")

    body_html = ''
    for i, p in enumerate(paragraphs):
        size = '18px' if i == 0 else '17px'
        color = '#1a202c' if i == 0 else '#374151'
        weight = 'font-weight:500;' if i == 0 else ''
        body_html += f'<p style="margin:0 0 22px;font-size:{size};color:{color};line-height:1.7;{weight}text-align:{text_align};">{p}</p>'

    return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:{text_align};color:#2d3748;">
    <p style="margin:0 0 24px;font-size:18px;color:#6b7280;">{greetings.get(language, greetings['en'])}</p>
    {body_html}
    <div style="text-align:center;margin:36px 0;">
        <a href="{cta_url}" style="display:inline-block;background:linear-gradient(135deg,#f97316 0%,#ea580c 100%);color:#fff;padding:16px 44px;text-decoration:none;border-radius:8px;font-weight:700;font-size:17px;">{cta_text} →</a>
    </div>
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;">{signoffs.get(language, signoffs['en'])}<br><strong>{sender_name}</strong></p>
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:#d1d5db;">San Francisco, CA 94117, United States</p>
        <p style="margin:0 0 8px;font-size:12px;color:#d1d5db;">{footer}</p>
        <p style="margin:0;font-size:12px;color:#9ca3af;"><a href="%mailing_list_unsubscribe_url%" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a></p>
    </div>
</body>
</html>'''


def _get_access_token():
    refresh = os.environ.get('FIREBASE_TOKEN', '')
    if not refresh:
        return None
    try:
        resp = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh,
                'client_id': '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com',
                'client_secret': 'j9iVZfS8kkCEFUPaAeJV0sAi',
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()['access_token']
    except Exception:
        pass
    return None


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = _get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set — cannot query streaks')
        return

    streaks = _fetch_streaks(token)
    if not streaks:
        print('   No streak data available (the Flutter app may not be writing streak.* yet).')
        return

    plans = FirestorePlanLoader().fetch_user_plans(APP_NAME)
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    candidates = []
    for email, s in streaks.items():
        streak = s.get('streak', 0)
        if streak < 3:
            continue
        last = s.get('last_active')
        if not last:
            continue
        if (now - last) < timedelta(hours=18):
            continue
        # Dedupe — once per day.
        sent_today = state['users'].get(email, {}).get('last_sent_day')
        if sent_today == today:
            continue
        candidates.append((email, streak, plans.get(email, {})))

    if not candidates:
        print('✅ Nobody at streak-break risk.')
        return

    print(f'🔥 {len(candidates)} streaks at risk')
    if dry_run:
        for email, streak, plan in candidates[:20]:
            print(f"   • {email}  streak={streak}  lang={plan.get('language','en')}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for email, streak, plan in candidates:
        lang = plan.get('language', 'en')
        if lang not in {'en', 'es', 'fr', 'ar', 'zh', 'hi'}:
            lang = 'en'
        ctx = dict(plan)
        ctx['streak'] = streak

        subject = localize_phrase.interpolate(lang, SUBJECTS.get(lang, SUBJECTS['en']), ctx)
        paragraphs = [localize_phrase.interpolate(lang, p, ctx) for p in BODY.get(lang, BODY['en'])]
        cta_text = CTA.get(lang, CTA['en'])

        html = _build_html(lang, paragraphs, cta_text, APP_STORE_URL)
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'streak_at_risk'},
            {'name': 'streak', 'value': str(streak)},
            {'name': 'language', 'value': lang},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_user_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['users'][email] = {
                'last_sent_day': today,
                'last_streak': streak,
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  streak={streak}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
