#!/usr/bin/env python3
"""
First-Thesis-Complete Sender (Thesis Generator)

Sends a single celebratory + invitation-to-export email the first time a
user marks a thesis as `complete`. This is the strongest possible upgrade
moment in the Hooked loop — the user just received the variable reward
and is most invested. The email funnels them back to the in-app PDF
export gate (which presents the Superwall paywall).

Detection: scans `users/{uid}/theses/*` Firestore docs and looks for
any doc with `status == "complete"`. Each user can only fire once;
deduped via cache/first_thesis_complete_state.json.

Usage:
    python scripts/first_thesis_complete_sender.py
    python scripts/first_thesis_complete_sender.py --dry-run
"""
import os
import sys
import json
import time
import hashlib
import requests
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from firestore_plan_loader import FirestorePlanLoader
from gmail_sender import GmailSender
import localize_phrase

APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
STATE_FILE = Path(__file__).parent.parent / 'cache' / 'first_thesis_complete_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')
PROJECT_ID = 'thesis-generator-web'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'


SUBJECTS = {
    'en': '🎓 You did it, {{first_name}} — export your {{work_type}}',
    'es': '🎓 Lo lograste, {{first_name}} — exporta tu {{work_type}}',
    'fr': '🎓 Tu y es arrivé, {{first_name}} — exporte ton {{work_type}}',
    'ar': '🎓 لقد فعلتها يا {{first_name}} — صدّر {{work_type}}',
    'zh': '🎓 {{first_name}}，你做到了 —— 导出你的{{work_type}}',
    'hi': '🎓 {{first_name}}, आपने कर दिखाया — अपनी {{work_type}} एक्सपोर्ट करें',
}


BODY = {
    'en': [
        "{{first_name}}, your {{work_type}} on {{topic}} is complete. That's a real accomplishment.",
        "Now the part that actually counts: export it as a PDF and turn it in. Tap below to open the export screen.",
        "P.S. Save the file somewhere outside the app too — future you will thank you.",
    ],
    'es': [
        "{{first_name}}, tu {{work_type}} sobre {{topic}} está completa. Eso es un logro real.",
        "Ahora viene la parte que importa: expórtala como PDF y entrégala. Toca abajo para abrir la pantalla de exportación.",
        "P.D. Guarda el archivo también fuera de la app — tu yo del futuro te lo agradecerá.",
    ],
    'fr': [
        "{{first_name}}, ton {{work_type}} sur {{topic}} est terminé. C'est une vraie réussite.",
        "Maintenant, ce qui compte vraiment : exporte-le en PDF et rends-le. Appuie ci-dessous pour ouvrir l'export.",
        "P.S. Sauvegarde aussi le fichier hors de l'app — ton toi futur te remerciera.",
    ],
    'ar': [
        "{{first_name}}، {{work_type}} عن {{topic}} مكتملة. هذا إنجاز حقيقي.",
        "والآن الجزء الذي يهم فعلاً: صدّرها كملف PDF وسلّمها. اضغط أدناه لفتح شاشة التصدير.",
        "ملاحظة: احفظ الملف خارج التطبيق أيضًا — ستشكر نفسك لاحقًا.",
    ],
    'zh': [
        "{{first_name}}，你关于 {{topic}} 的{{work_type}}完成了。这是了不起的成就。",
        "现在到了真正重要的环节：导出为 PDF 并提交。点击下方打开导出界面。",
        "另外：把文件保存到应用之外的位置，未来的你会感谢现在的你。",
    ],
    'hi': [
        "{{first_name}}, {{topic}} पर आपकी {{work_type}} पूरी हो गई। यह असली उपलब्धि है।",
        "अब असली काम: PDF एक्सपोर्ट करें और जमा करें। नीचे टैप करके एक्सपोर्ट स्क्रीन खोलें।",
        "P.S. फ़ाइल को ऐप के बाहर भी सेव कर लें — आगे चलकर शुक्रिया अदा करेंगे।",
    ],
}

CTA = {
    'en': 'Export my PDF',
    'es': 'Exportar mi PDF',
    'fr': 'Exporter mon PDF',
    'ar': 'صدّر ملف PDF',
    'zh': '导出 PDF',
    'hi': 'PDF एक्सपोर्ट करें',
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


def _fetch_users_with_complete_thesis(token):
    """Returns set of emails whose users collection has at least one thesis
    document with status == 'complete'. Uses Firestore `runQuery` with a
    collection-group filter so we don't have to walk every user's subcollection.
    """
    url = f"{FIRESTORE_BASE}/projects/{PROJECT_ID}/databases/(default)/documents:runQuery"
    body = {
        'structuredQuery': {
            'from': [{'collectionId': 'theses', 'allDescendants': True}],
            'where': {
                'fieldFilter': {
                    'field': {'fieldPath': 'status'},
                    'op': 'EQUAL',
                    'value': {'stringValue': 'complete'},
                }
            },
            'select': {'fields': [{'fieldPath': 'userId'}, {'fieldPath': 'email'}]},
        }
    }
    try:
        resp = requests.post(
            url, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=body, timeout=30,
        )
        if resp.status_code != 200:
            print(f'   ❌ runQuery error {resp.status_code}: {resp.text[:200]}')
            return set()
        results = resp.json() if isinstance(resp.json(), list) else [resp.json()]
        emails = set()
        for r in results:
            doc = r.get('document')
            if not doc:
                continue
            fields = doc.get('fields', {})
            email = fields.get('email', {}).get('stringValue', '').lower().strip()
            if email:
                emails.add(email)
        return emails
    except Exception as e:
        print(f'   ❌ runQuery exception: {e}')
        return set()


def _build_html(language, paragraphs, cta_text, cta_url, sender_name='Ana'):
    is_rtl = language == 'ar'
    dir_attr = ' dir="rtl"' if is_rtl else ''
    text_align = 'right' if is_rtl else 'left'
    greetings = {'en': 'Congratulations,', 'ar': 'تهانينا،', 'es': '¡Felicidades!,', 'fr': 'Félicitations,', 'zh': '恭喜，', 'hi': 'बधाई,'}
    signoffs = {'en': 'So proud of you,', 'ar': 'فخور بك،', 'es': 'Muy orgullosa de ti,', 'fr': 'Très fière de toi,', 'zh': '为你骄傲，', 'hi': 'आप पर गर्व है,'}
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
        if 'P.S' in p or 'P.D' in p or 'ملاحظة' in p:
            body_html += f'<div style="margin:24px 0 0;padding:14px 18px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;text-align:{text_align};"><p style="margin:0;font-size:15px;color:#92400e;line-height:1.7;">{p}</p></div>'
            continue
        size = '19px' if i == 0 else '17px'
        color = '#0f172a' if i == 0 else '#374151'
        weight = 'font-weight:600;' if i == 0 else ''
        body_html += f'<p style="margin:0 0 22px;font-size:{size};color:{color};line-height:1.7;{weight}text-align:{text_align};">{p}</p>'

    return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;color:#2d3748;text-align:{text_align};">
    <p style="margin:0 0 24px;font-size:18px;color:#6b7280;">{greetings.get(language, greetings['en'])}</p>
    {body_html}
    <div style="text-align:center;margin:36px 0;">
        <a href="{cta_url}" style="display:inline-block;background:linear-gradient(135deg,#10b981 0%,#059669 100%);color:#fff;padding:16px 44px;text-decoration:none;border-radius:8px;font-weight:700;font-size:17px;">{cta_text} →</a>
    </div>
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;">{signoffs.get(language, signoffs['en'])}<br><strong>{sender_name}</strong></p>
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:#d1d5db;">San Francisco, CA 94117, United States</p>
        <p style="margin:0 0 8px;font-size:12px;color:#d1d5db;">{footer}</p>
        <p style="margin:0;font-size:12px;color:#9ca3af;"><a href="%mailing_list_unsubscribe_url%" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a></p>
    </div>
</body>
</html>'''


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    token = _get_access_token()
    if not token:
        print('⚠️ FIREBASE_TOKEN not set — cannot query thesis completions')
        return

    completers = _fetch_users_with_complete_thesis(token)
    new = [e for e in completers if e not in state['users']]
    print(f'🎓 {len(new)} new first-completers found ({len(completers)} total)')
    if not new:
        return

    plans = FirestorePlanLoader().fetch_user_plans(APP_NAME)

    if dry_run:
        for e in new[:20]:
            print(f"   • {e}  topic={plans.get(e,{}).get('topic','')[:40]}  lang={plans.get(e,{}).get('language','en')}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    sender = GmailSender()
    if not sender.connect():
        return

    sent = failed = 0
    for email in new:
        plan = plans.get(email, {})
        lang = plan.get('language', 'en')
        if lang not in {'en', 'es', 'fr', 'ar', 'zh', 'hi'}:
            lang = 'en'

        subject = localize_phrase.interpolate(lang, SUBJECTS.get(lang, SUBJECTS['en']), plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in BODY.get(lang, BODY['en'])]
        cta_text = CTA.get(lang, CTA['en'])

        html = _build_html(lang, paragraphs, cta_text, APP_STORE_URL)
        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'first_complete'},
            {'name': 'language', 'value': lang},
        ]
        result = sender.send_email(
            to_email=email, subject=subject, html_body=html, from_name=APP_NAME,
            tags=tags, ref_id=_user_ref(email),
        )
        if result == 'sent':
            sent += 1
            state['users'][email] = {
                'sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
