#!/usr/bin/env python3
"""
Localized phrase helper for retention emails.

Provides hand-curated reusable phrases ("5 days left", "your thesis is 60%
done") in every language the Thesis Generator app supports. Used by the
email renderer to interpolate user data (deadline, streak, progress) into
the language-specific template fetched from cache.

Why hand-curated vs DeepSeek-translated:
- ~20 reusable phrases × 6 languages = 120 strings. Small enough to vet.
- Inflection / plural rules differ per language (1 day vs 2 days, ar dual).
- Translations need to match the marketing voice — DeepSeek output drifts.
"""

# Supported languages.
LANGUAGES = ['en', 'es', 'fr', 'ar', 'zh', 'hi']


def _plural_en(n, one, other):
    return one if n == 1 else other


def days_left(language, n):
    """Returns a localized 'N days left' or 'today'/'tomorrow' phrase."""
    if n is None:
        return ''
    if language == 'en':
        if n < 0:
            return 'past your deadline'
        if n == 0:
            return 'due today'
        if n == 1:
            return '1 day left'
        return f'{n} days left'
    if language == 'es':
        if n < 0:
            return 'pasado tu plazo'
        if n == 0:
            return 'vence hoy'
        if n == 1:
            return 'queda 1 día'
        return f'quedan {n} días'
    if language == 'fr':
        if n < 0:
            return 'délai dépassé'
        if n == 0:
            return "à rendre aujourd'hui"
        if n == 1:
            return 'il reste 1 jour'
        return f'il reste {n} jours'
    if language == 'ar':
        if n < 0:
            return 'تجاوزت الموعد النهائي'
        if n == 0:
            return 'الموعد النهائي اليوم'
        if n == 1:
            return 'يوم واحد متبقٍّ'
        if n == 2:
            return 'يومان متبقّيان'
        if 3 <= n <= 10:
            return f'{n} أيام متبقّية'
        return f'{n} يومًا متبقّيًا'
    if language == 'zh':
        if n < 0:
            return '已超过截止日期'
        if n == 0:
            return '今天截止'
        return f'还剩 {n} 天'
    if language == 'hi':
        if n < 0:
            return 'अंतिम तिथि बीत चुकी है'
        if n == 0:
            return 'आज अंतिम दिन'
        if n == 1:
            return '1 दिन बचा है'
        return f'{n} दिन बचे हैं'
    return f'{n} days left'


def progress_percent(language, p):
    """Localizes 'N% done'."""
    if p is None:
        return ''
    p = int(p)
    if language == 'en':
        return f'{p}% done'
    if language == 'es':
        return f'{p}% completado'
    if language == 'fr':
        return f'{p}% terminé'
    if language == 'ar':
        return f'مكتمل {p}٪'
    if language == 'zh':
        return f'已完成 {p}%'
    if language == 'hi':
        return f'{p}% पूरा'
    return f'{p}% done'


def streak_phrase(language, n):
    """Localizes 'N-day streak'."""
    if n is None or n <= 0:
        return ''
    if language == 'en':
        return f'{n}-day streak'
    if language == 'es':
        return f'racha de {n} día{_plural_en(n, "", "s")}'
    if language == 'fr':
        if n == 1:
            return 'série de 1 jour'
        return f'série de {n} jours'
    if language == 'ar':
        if n == 1:
            return 'سلسلة يوم واحد'
        if n == 2:
            return 'سلسلة يومين'
        if 3 <= n <= 10:
            return f'سلسلة {n} أيام'
        return f'سلسلة {n} يومًا'
    if language == 'zh':
        return f'{n} 天连胜'
    if language == 'hi':
        return f'{n} दिन की लय'
    return f'{n}-day streak'


# Pain → empathetic hook phrase used in the opening of pain-mirror emails.
# Keep these one short sentence; the rest of the email body picks up from
# here so it should feel like a continuation, not a slogan.
PAIN_HOOK = {
    'en': {
        'deadline':      "I know the deadline feels close.",
        'confused':      "Starting from a blank page is the hardest part.",
        'noTime':        "Between everything else, finding writing time is brutal.",
        'perfectionist': "Wanting it to be excellent is its own kind of pressure.",
    },
    'es': {
        'deadline':      "Sé que el plazo se siente encima.",
        'confused':      "Empezar desde cero es lo más difícil.",
        'noTime':        "Entre todo lo demás, encontrar tiempo para escribir es brutal.",
        'perfectionist': "Querer que sea excelente trae su propia presión.",
    },
    'fr': {
        'deadline':      "Je sais que l'échéance approche vite.",
        'confused':      "Partir d'une page blanche est la partie la plus dure.",
        'noTime':        "Entre tout le reste, trouver le temps d'écrire est brutal.",
        'perfectionist': "Vouloir l'excellence apporte sa propre pression.",
    },
    'ar': {
        'deadline':      "أعلم أن الموعد النهائي يقترب.",
        'confused':      "البدء من ورقة بيضاء هو أصعب جزء.",
        'noTime':        "بين كل المهام الأخرى، إيجاد وقت للكتابة صعب جدًا.",
        'perfectionist': "الرغبة في الإتقان تحمل ضغطها الخاص.",
    },
    'zh': {
        'deadline':      "我知道截止日期已经很近了。",
        'confused':      "从空白页开始是最难的部分。",
        'noTime':        "在所有事情之间，找到写作时间真的很难。",
        'perfectionist': "想要做到完美本身就是一种压力。",
    },
    'hi': {
        'deadline':      "मुझे पता है अंतिम तिथि करीब आ रही है।",
        'confused':      "खाली पेज से शुरू करना सबसे कठिन हिस्सा है।",
        'noTime':        "बाकी सब के बीच, लिखने का समय निकालना मुश्किल है।",
        'perfectionist': "उत्कृष्ट काम चाहना अपने आप में दबाव लाता है।",
    },
}


def pain_hook(language, pain):
    """Returns the opening empathy sentence for a given pain enum value."""
    if not pain:
        return ''
    table = PAIN_HOOK.get(language) or PAIN_HOOK['en']
    return table.get(pain, '')


# Translations for the WorkType enum's display label (matches Flutter app's
# enum names exactly so we can pass them through without re-mapping).
WORK_TYPE_LABEL = {
    'en': {
        'shortEssay':    'essay',
        'researchPaper': 'research paper',
        'fullThesis':    'thesis',
        'dissertation':  'dissertation',
    },
    'es': {
        'shortEssay':    'ensayo',
        'researchPaper': 'trabajo de investigación',
        'fullThesis':    'tesis',
        'dissertation':  'tesis doctoral',
    },
    'fr': {
        'shortEssay':    'dissertation',
        'researchPaper': 'article de recherche',
        'fullThesis':    'mémoire',
        'dissertation':  'thèse',
    },
    'ar': {
        'shortEssay':    'مقال',
        'researchPaper': 'ورقة بحثية',
        'fullThesis':    'أطروحة',
        'dissertation':  'رسالة دكتوراه',
    },
    'zh': {
        'shortEssay':    '论文',
        'researchPaper': '研究论文',
        'fullThesis':    '学位论文',
        'dissertation':  '博士论文',
    },
    'hi': {
        'shortEssay':    'निबंध',
        'researchPaper': 'शोध पत्र',
        'fullThesis':    'थीसिस',
        'dissertation':  'शोध-प्रबंध',
    },
}


def work_type_label(language, work_type):
    if not work_type:
        return ''
    table = WORK_TYPE_LABEL.get(language) or WORK_TYPE_LABEL['en']
    return table.get(work_type, work_type)


def interpolate(language, text, plan):
    """Replace {{placeholder}} tokens in `text` using the user's plan.

    Supported placeholders:
        {{first_name}}     → plan.first_name (fallback "")
        {{topic}}          → plan.topic
        {{days_left}}      → localized days-left phrase
        {{streak}}         → localized streak phrase
        {{progress}}       → localized progress phrase (caller must include
                             a 'progress' key in plan)
        {{work_type}}      → localized work-type label
        {{pain_hook}}      → empathy sentence based on plan.pain

    Empty placeholders collapse cleanly: trailing/leading whitespace removed
    when a value resolves to '' so the email doesn't show "Hi , ..." for a
    user without a first name.
    """
    if not text or not plan:
        return text or ''

    repl = {
        'first_name':  plan.get('first_name', '') or '',
        'topic':       plan.get('topic', '') or '',
        'days_left':   days_left(language, plan.get('days_left')),
        'streak':      streak_phrase(language, plan.get('streak')),
        'progress':    progress_percent(language, plan.get('progress')),
        'work_type':   work_type_label(language, plan.get('work_type', '')),
        'pain_hook':   pain_hook(language, plan.get('pain', '')),
    }

    out = text
    for key, value in repl.items():
        token = '{{' + key + '}}'
        if token in out:
            if value:
                out = out.replace(token, value)
            else:
                # Empty value: try to remove a leading/trailing space too so
                # the sentence still reads naturally.
                out = out.replace(' ' + token, '')
                out = out.replace(token + ' ', '')
                out = out.replace(token, '')
    return out


if __name__ == '__main__':
    sample_plan = {
        'first_name': 'María',
        'topic': 'Impacto de la IA en la educación',
        'days_left': 5,
        'streak': 3,
        'progress': 60,
        'work_type': 'fullThesis',
        'pain': 'deadline',
    }
    for lang in LANGUAGES:
        print(f"\n--- {lang} ---")
        print(interpolate(lang, 'Hi {{first_name}}, {{pain_hook}} Your {{work_type}} on "{{topic}}" — {{days_left}}.', sample_plan))
        print(interpolate(lang, '{{streak}}, {{progress}}.', sample_plan))
