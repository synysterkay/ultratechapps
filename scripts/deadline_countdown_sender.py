#!/usr/bin/env python3
"""
Deadline Countdown Sender (Thesis Generator)

Sends a single personalized email when the user's `plan.deadline` is
14 / 7 / 3 / 1 / 0 days out. Each milestone fires at most once per user.

This complements the in-app deadline notification — together they form
the highest-signal external trigger pair for Hooked-aligned retention.

Usage:
    python scripts/deadline_countdown_sender.py             # send next batch
    python scripts/deadline_countdown_sender.py --dry-run   # preview only
"""
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime

# Reuse marketing-tool plumbing
sys.path.insert(0, str(Path(__file__).parent))

from firestore_plan_loader import FirestorePlanLoader
from gmail_sender import GmailSender
from deliverability_monitor import DeliverabilityMonitor
import localize_phrase

# Milestones (days before deadline) at which we fire.
MILESTONES = [14, 7, 3, 1, 0]

APP_NAME = 'Thesis Generator'
APP_SLUG = 'thesis'
APP_STORE_URL = 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844'
GOOGLE_PLAY_URL = 'https://play.google.com/store/apps/details?id=com.thesis.generator.ai'

STATE_FILE = Path(__file__).parent.parent / 'cache' / 'deadline_countdown_state.json'
_REF_SALT = os.getenv('EMAIL_REF_SALT', 'marketing-tool-v1')


# Localized subjects per milestone. Each is a template that gets
# {{first_name}} / {{topic}} / {{days_left}} filled at send time.
SUBJECTS = {
    14: {
        'en': '{{topic}} — {{days_left}}',
        'es': '{{topic}} — {{days_left}}',
        'fr': '{{topic}} — {{days_left}}',
        'ar': '{{topic}} — {{days_left}}',
        'zh': '{{topic}} — {{days_left}}',
        'hi': '{{topic}} — {{days_left}}',
    },
    7:  {
        'en': 'One week to go on {{topic}}',
        'es': 'Una semana para {{topic}}',
        'fr': "Une semaine pour {{topic}}",
        'ar': 'أسبوع متبقٍّ على {{topic}}',
        'zh': '距 {{topic}} 还有一周',
        'hi': '{{topic}} के लिए एक हफ्ता बचा है',
    },
    3:  {
        'en': '3 days left, {{first_name}}',
        'es': '{{first_name}}, quedan 3 días',
        'fr': '{{first_name}}, il reste 3 jours',
        'ar': '{{first_name}}، 3 أيام متبقّية',
        'zh': '{{first_name}}，还剩 3 天',
        'hi': '{{first_name}}, सिर्फ 3 दिन बाकी',
    },
    1:  {
        'en': 'Tomorrow is the day for {{topic}}',
        'es': 'Mañana es el día de {{topic}}',
        'fr': "C'est demain pour {{topic}}",
        'ar': 'غدًا هو موعد {{topic}}',
        'zh': '明天就是 {{topic}} 的截止日',
        'hi': 'कल है {{topic}} का दिन',
    },
    0:  {
        'en': 'Today: finish {{topic}}',
        'es': 'Hoy: termina {{topic}}',
        'fr': "Aujourd'hui : finir {{topic}}",
        'ar': 'اليوم: أنهِ {{topic}}',
        'zh': '今天：完成 {{topic}}',
        'hi': 'आज: {{topic}} पूरा करें',
    },
}


# Body per milestone. Two short paragraphs. {{pain_hook}} pulls from
# localize_phrase.PAIN_HOOK and lands in the opener.
BODIES = {
    14: {
        'en': [
            "{{pain_hook}}",
            "Your {{work_type}} on {{topic}} is due in two weeks. The work you put in now is what makes the last 48 hours feel calm instead of frantic — open the app and add 15 minutes today.",
        ],
        'es': [
            "{{pain_hook}}",
            "Tu {{work_type}} sobre {{topic}} se entrega en dos semanas. El trabajo que hagas ahora es lo que hace que las últimas 48 horas se sientan tranquilas — abre la app y dedica 15 minutos hoy.",
        ],
        'fr': [
            "{{pain_hook}}",
            "Votre {{work_type}} sur {{topic}} est à rendre dans deux semaines. Le travail fait maintenant rend les dernières 48 heures calmes au lieu de paniquées — ouvrez l'app et investissez 15 minutes aujourd'hui.",
        ],
        'ar': [
            "{{pain_hook}}",
            "{{work_type}} عن {{topic}} مستحق خلال أسبوعين. العمل الذي تقوم به الآن هو ما يجعل آخر 48 ساعة هادئة بدلاً من محمومة — افتح التطبيق وخصّص 15 دقيقة اليوم.",
        ],
        'zh': [
            "{{pain_hook}}",
            "你关于 {{topic}} 的{{work_type}}还有两周到期。现在投入的精力，会让最后 48 小时变得从容而不是慌乱——今天打开应用花 15 分钟。",
        ],
        'hi': [
            "{{pain_hook}}",
            "{{topic}} पर आपकी {{work_type}} दो हफ्ते में देय है। अभी की मेहनत अंतिम 48 घंटे को आसान बनाती है — आज ऐप खोलें और 15 मिनट लगाएं।",
        ],
    },
    7: {
        'en': [
            "One week to {{topic}}.",
            "If you generated the outline already, this is the week to fill in the chapters. Tap below and pick up where you left off.",
        ],
        'es': [
            "Una semana para {{topic}}.",
            "Si ya generaste el esquema, esta es la semana para escribir los capítulos. Toca abajo y continúa donde lo dejaste.",
        ],
        'fr': [
            "Une semaine avant {{topic}}.",
            "Si vous avez déjà généré le plan, c'est la semaine pour remplir les chapitres. Appuyez ci-dessous et reprenez où vous en étiez.",
        ],
        'ar': [
            "أسبوع واحد لـ {{topic}}.",
            "إذا أنشأت المخطط من قبل، هذا هو الأسبوع لإكمال الفصول. اضغط أدناه واستأنف من حيث توقفت.",
        ],
        'zh': [
            "距 {{topic}} 还有一周。",
            "如果你已经生成了大纲，这一周就该补充章节内容了。点击下方继续。",
        ],
        'hi': [
            "{{topic}} के लिए एक हफ्ता।",
            "अगर आपने पहले से ही रूपरेखा बना ली है, तो यह हफ्ता अध्याय भरने का है। नीचे टैप करें और जहां रुके थे, वहीं से शुरू करें।",
        ],
    },
    3: {
        'en': [
            "Three days, {{first_name}}.",
            "Open the app, pick up where you left off, and end the week with a finished {{work_type}}. You're closer than it feels.",
        ],
        'es': [
            "Tres días, {{first_name}}.",
            "Abre la app, continúa donde lo dejaste y termina la semana con tu {{work_type}} hecha. Estás más cerca de lo que parece.",
        ],
        'fr': [
            "Trois jours, {{first_name}}.",
            "Ouvrez l'app, reprenez où vous en étiez, et terminez la semaine avec votre {{work_type}} prête. Vous êtes plus proche que vous ne le pensez.",
        ],
        'ar': [
            "ثلاثة أيام يا {{first_name}}.",
            "افتح التطبيق، استأنف من حيث توقفت، وأنهِ الأسبوع بـ {{work_type}} مكتملة. أنت أقرب مما تشعر.",
        ],
        'zh': [
            "三天，{{first_name}}。",
            "打开应用，继续未完成的部分，本周末交出完成的{{work_type}}。你比想象中更近了。",
        ],
        'hi': [
            "तीन दिन, {{first_name}}।",
            "ऐप खोलें, जहां रुके थे वहीं से शुरू करें, और इस हफ्ते को पूरी {{work_type}} के साथ खत्म करें। आप उतने पीछे नहीं हैं जितना लगता है।",
        ],
    },
    1: {
        'en': [
            "Tomorrow.",
            "{{topic}} is due tomorrow. Tap below and finish the last chapter today — sleep well tonight knowing it's done.",
        ],
        'es': [
            "Mañana.",
            "{{topic}} se entrega mañana. Toca abajo y termina el último capítulo hoy — duerme tranquilo sabiendo que está hecho.",
        ],
        'fr': [
            "Demain.",
            "{{topic}} est à rendre demain. Appuyez ci-dessous et finissez le dernier chapitre aujourd'hui — vous dormirez tranquille.",
        ],
        'ar': [
            "غدًا.",
            "{{topic}} يستحق غدًا. اضغط أدناه وأنهِ الفصل الأخير اليوم — نَم مرتاحًا وأنت تعلم أنه أُنجز.",
        ],
        'zh': [
            "就是明天。",
            "{{topic}} 明天截止。点击下方，今天完成最后一章——安心入睡。",
        ],
        'hi': [
            "कल।",
            "{{topic}} कल देय है। नीचे टैप करें और आज ही आखिरी अध्याय पूरा करें — चैन से सोएं।",
        ],
    },
    0: {
        'en': [
            "Today, {{first_name}}.",
            "Open the app, finish the final pieces, and export the PDF. You've got this.",
        ],
        'es': [
            "Hoy, {{first_name}}.",
            "Abre la app, termina las últimas piezas y exporta el PDF. Tú puedes.",
        ],
        'fr': [
            "Aujourd'hui, {{first_name}}.",
            "Ouvrez l'app, finissez les derniers morceaux et exportez le PDF. Vous y êtes.",
        ],
        'ar': [
            "اليوم يا {{first_name}}.",
            "افتح التطبيق، أنهِ الأجزاء الأخيرة، وصدّر ملف PDF. أنت قادر.",
        ],
        'zh': [
            "今天，{{first_name}}。",
            "打开应用，完成最后的部分，导出 PDF。你可以的。",
        ],
        'hi': [
            "आज, {{first_name}}।",
            "ऐप खोलें, बाकी काम पूरा करें और PDF एक्सपोर्ट करें। आप कर सकते हैं।",
        ],
    },
}


CTA = {
    'en': 'Continue your work',
    'es': 'Continuar tu trabajo',
    'fr': 'Continuer votre travail',
    'ar': 'تابع عملك',
    'zh': '继续你的工作',
    'hi': 'अपना काम जारी रखें',
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


def _build_html(language, paragraphs, cta_text, cta_url, sender_name='Ana'):
    is_rtl = language == 'ar'
    dir_attr = ' dir="rtl"' if is_rtl else ''
    text_align = 'right' if is_rtl else 'left'

    greetings = {'en': 'Hey there,', 'ar': 'مرحبًا،', 'es': 'Hola,', 'fr': 'Salut,', 'zh': '你好，', 'hi': 'नमस्ते,'}
    signoffs = {'en': 'Talk soon,', 'ar': 'إلى اللقاء،', 'es': 'Hasta pronto,', 'fr': 'À bientôt,', 'zh': '回头聊，', 'hi': 'जल्द बात करते हैं,'}
    footer_text = {
        'en': f"You're receiving this because you signed up for {APP_NAME}.",
        'ar': f"تتلقى هذا البريد لأنك سجلت في {APP_NAME}.",
        'es': f"Recibes esto porque te registraste en {APP_NAME}.",
        'fr': f"Vous recevez ceci car vous vous êtes inscrit(e) à {APP_NAME}.",
        'zh': f"您收到此邮件是因为您注册了 {APP_NAME}。",
        'hi': f"आपको यह ईमेल इसलिए मिल रहा है क्योंकि आपने {APP_NAME} के लिए साइन अप किया है।",
    }[language if language in {'en','ar','es','fr','zh','hi'} else 'en']

    greeting = greetings.get(language, greetings['en'])
    signoff = signoffs.get(language, signoffs['en'])

    body_html = ""
    for i, p in enumerate(paragraphs):
        if not p:
            continue
        weight = 'font-weight:500;' if i == 0 else ''
        size = '18px' if i == 0 else '17px'
        color = '#1a202c' if i == 0 else '#374151'
        body_html += f'<p style="margin:0 0 22px;font-size:{size};color:{color};line-height:1.7;{weight}text-align:{text_align};">{p}</p>'

    return f'''<!DOCTYPE html>
<html{dir_attr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:{text_align};">
    <p style="margin:0 0 24px;font-size:18px;color:#6b7280;text-align:{text_align};">{greeting}</p>
    {body_html}
    <div style="text-align:center;margin:36px 0;">
        <a href="{cta_url}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:16px 44px;text-decoration:none;border-radius:8px;font-weight:700;font-size:17px;box-shadow:0 6px 20px rgba(102,126,234,0.35);">
            {cta_text} →
        </a>
    </div>
    <p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:{text_align};">
        {signoff}<br><strong style="color:#1f2937;">{sender_name}</strong>
    </p>
    <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
        <p style="margin:0 0 8px;font-size:13px;color:#d1d5db;">San Francisco, CA 94117, United States</p>
        <p style="margin:0 0 8px;font-size:12px;color:#d1d5db;">{footer_text}</p>
        <p style="margin:0;font-size:12px;color:#9ca3af;"><a href="%mailing_list_unsubscribe_url%" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a></p>
    </div>
</body>
</html>'''


def main(dry_run=False):
    state = _load_state()
    state.setdefault('users', {})

    loader = FirestorePlanLoader()
    plans = loader.fetch_user_plans(APP_NAME)
    if not plans:
        print('⚠️ No Thesis Generator plans available — has the app shipped UserPlan sync yet?')
        return

    # Filter to users at a deadline milestone.
    candidates = []
    for email, plan in plans.items():
        d = plan.get('days_left')
        if d is None:
            continue
        if d not in MILESTONES:
            continue
        # Dedupe — never re-send the same milestone to the same user.
        sent_milestones = set(state['users'].get(email, {}).get('milestones', []))
        if d in sent_milestones:
            continue
        candidates.append((email, plan, d))

    if not candidates:
        print('✅ No users at a deadline milestone right now.')
        return

    print(f'📧 {len(candidates)} candidates at a deadline milestone')
    if dry_run:
        for email, plan, d in candidates[:20]:
            print(f"   • {email}  d={d}  topic={plan.get('topic','')[:40]}  lang={plan.get('language','en')}")
        print('🏁 DRY RUN — no emails sent')
        return

    if not os.getenv('RESEND_API_KEY'):
        print('❌ RESEND_API_KEY not set')
        return

    # Skip users on the suppression list maintained by the main emailer.
    suppressed = set()
    dm = DeliverabilityMonitor()
    try:
        recipients_state = json.loads((Path(__file__).parent.parent / 'cache' / 'retention_state.json').read_text())
        for em, info in recipients_state.get('users', {}).items():
            if info.get('suppressed'):
                suppressed.add(em.lower())
    except Exception:
        pass

    sender = GmailSender()
    if not sender.connect():
        print('❌ Could not connect to Resend')
        return

    sent = 0
    failed = 0
    for email, plan, d in candidates:
        if email.lower() in suppressed:
            continue
        lang = plan.get('language', 'en')
        if lang not in {'en', 'es', 'fr', 'ar', 'zh', 'hi'}:
            lang = 'en'

        subject_tpl = SUBJECTS[d].get(lang) or SUBJECTS[d]['en']
        paragraphs_tpl = BODIES[d].get(lang) or BODIES[d]['en']
        cta_text = CTA.get(lang, CTA['en'])

        subject = localize_phrase.interpolate(lang, subject_tpl, plan)
        paragraphs = [localize_phrase.interpolate(lang, p, plan) for p in paragraphs_tpl]

        # Pick the platform URL — assume iOS by default; could be split by
        # device platform in a future pass.
        cta_url = APP_STORE_URL

        html = _build_html(lang, paragraphs, cta_text, cta_url)

        tags = [
            {'name': 'app', 'value': APP_SLUG},
            {'name': 'kind', 'value': 'deadline'},
            {'name': 'milestone', 'value': str(d)},
            {'name': 'language', 'value': lang},
        ]

        result = sender.send_email(
            to_email=email,
            subject=subject,
            html_body=html,
            from_name=APP_NAME,
            tags=tags,
            ref_id=_user_ref(email),
        )
        if result == 'sent':
            sent += 1
            milestones = set(state['users'].get(email, {}).get('milestones', []))
            milestones.add(d)
            state['users'][email] = {
                'milestones': sorted(milestones, reverse=True),
                'last_sent_at': datetime.now().isoformat(),
                'language': lang,
            }
            if sent % 10 == 0:
                _save_state(state)
            print(f'   ✅ [{sent}] {email}  d={d}  {lang}')
        else:
            failed += 1
            print(f'   ❌ {email}  d={d}  result={result}')
        time.sleep(0.2)

    sender.disconnect()
    _save_state(state)
    print(f'\n📊 Done — sent {sent}, failed {failed}')


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    main(dry_run=dry)
