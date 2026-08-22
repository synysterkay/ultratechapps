#!/usr/bin/env python3
"""
Localized phrase helper for retention emails.

Provides hand-curated reusable phrases ("5 days left", "your thesis is 60%
done") in every language the Thesis Generator app supports. Used by the
email renderer to interpolate user data (deadline, streak, progress) into
the language-specific template fetched from cache.

Why hand-curated vs DeepSeek-translated:
- ~20 reusable phrases × 20 languages = 400 strings. Still small enough to vet.
- Inflection / plural rules differ per language (1 day vs 2 days, ar dual,
  ru 1 / 2–4 / 5+, etc.). LLM translation routinely gets these wrong.
- Translations need to match the marketing voice — DeepSeek output drifts.

LANGUAGES is the canonical list of locales the Flutter app exposes in
`language_selection_screen.dart`. Keep these in sync.
"""
import re

# Canonical 20-language list. Order matches the language picker in the app.
LANGUAGES = [
    'en', 'es', 'fr', 'ar', 'zh', 'hi',
    'de', 'pt', 'it', 'ru', 'ja', 'ko',
    'tr', 'nl', 'pl', 'sv', 'ro', 'id', 'th', 'vi',
]

# RTL locales — the renderer flips text-align + dir attribute for these.
RTL_LANGUAGES = {'ar'}


def _ru_plural(n):
    """Russian plural form: 0 = many, 1 = one, 2-4 = few, 5+ = many.
    Special-case the teens (11-14 are all 'many')."""
    n = abs(n)
    if 11 <= n % 100 <= 14:
        return 'many'
    last = n % 10
    if last == 1:
        return 'one'
    if 2 <= last <= 4:
        return 'few'
    return 'many'


def _pl_plural(n):
    """Polish plural form: 1 = one, 2-4 (not 12-14) = few, otherwise many."""
    n = abs(n)
    if n == 1:
        return 'one'
    if 12 <= n % 100 <= 14:
        return 'many'
    last = n % 10
    if 2 <= last <= 4:
        return 'few'
    return 'many'


def days_left(language, n):
    """Returns a localized 'N days left' or 'today'/'tomorrow' phrase."""
    if n is None:
        return ''
    if language == 'en':
        if n < 0: return 'past your deadline'
        if n == 0: return 'due today'
        if n == 1: return '1 day left'
        return f'{n} days left'
    if language == 'es':
        if n < 0: return 'pasado tu plazo'
        if n == 0: return 'vence hoy'
        if n == 1: return 'queda 1 día'
        return f'quedan {n} días'
    if language == 'fr':
        if n < 0: return 'délai dépassé'
        if n == 0: return "à rendre aujourd'hui"
        if n == 1: return 'il reste 1 jour'
        return f'il reste {n} jours'
    if language == 'ar':
        if n < 0: return 'تجاوزت الموعد النهائي'
        if n == 0: return 'الموعد النهائي اليوم'
        if n == 1: return 'يوم واحد متبقٍّ'
        if n == 2: return 'يومان متبقّيان'
        if 3 <= n <= 10: return f'{n} أيام متبقّية'
        return f'{n} يومًا متبقّيًا'
    if language == 'zh':
        if n < 0: return '已超过截止日期'
        if n == 0: return '今天截止'
        return f'还剩 {n} 天'
    if language == 'hi':
        if n < 0: return 'अंतिम तिथि बीत चुकी है'
        if n == 0: return 'आज अंतिम दिन'
        if n == 1: return '1 दिन बचा है'
        return f'{n} दिन बचे हैं'
    if language == 'de':
        if n < 0: return 'Deadline überschritten'
        if n == 0: return 'heute fällig'
        if n == 1: return 'noch 1 Tag'
        return f'noch {n} Tage'
    if language == 'pt':
        if n < 0: return 'prazo expirado'
        if n == 0: return 'vence hoje'
        if n == 1: return 'falta 1 dia'
        return f'faltam {n} dias'
    if language == 'it':
        if n < 0: return 'scadenza superata'
        if n == 0: return 'scade oggi'
        if n == 1: return 'manca 1 giorno'
        return f'mancano {n} giorni'
    if language == 'ru':
        if n < 0: return 'срок истёк'
        if n == 0: return 'дедлайн сегодня'
        form = _ru_plural(n)
        if form == 'one': return f'остался {n} день'
        if form == 'few': return f'осталось {n} дня'
        return f'осталось {n} дней'
    if language == 'ja':
        if n < 0: return '締切を過ぎています'
        if n == 0: return '本日締切'
        return f'残り {n} 日'
    if language == 'ko':
        if n < 0: return '마감일이 지났습니다'
        if n == 0: return '오늘 마감'
        return f'{n}일 남았어요'
    if language == 'tr':
        if n < 0: return 'son tarih geçti'
        if n == 0: return 'bugün teslim'
        if n == 1: return '1 gün kaldı'
        return f'{n} gün kaldı'
    if language == 'nl':
        if n < 0: return 'deadline verstreken'
        if n == 0: return 'vandaag inleveren'
        if n == 1: return 'nog 1 dag'
        return f'nog {n} dagen'
    if language == 'pl':
        if n < 0: return 'termin minął'
        if n == 0: return 'termin dzisiaj'
        form = _pl_plural(n)
        if form == 'one': return 'został 1 dzień'
        if form == 'few': return f'zostały {n} dni'
        return f'zostało {n} dni'
    if language == 'sv':
        if n < 0: return 'deadline har passerat'
        if n == 0: return 'lämnas in idag'
        if n == 1: return '1 dag kvar'
        return f'{n} dagar kvar'
    if language == 'ro':
        if n < 0: return 'termen depășit'
        if n == 0: return 'termen astăzi'
        if n == 1: return 'a mai rămas 1 zi'
        return f'au mai rămas {n} zile'
    if language == 'id':
        if n < 0: return 'tenggat sudah lewat'
        if n == 0: return 'jatuh tempo hari ini'
        return f'{n} hari lagi'
    if language == 'th':
        if n < 0: return 'เลยกำหนดส่งแล้ว'
        if n == 0: return 'กำหนดส่งวันนี้'
        return f'เหลืออีก {n} วัน'
    if language == 'vi':
        if n < 0: return 'đã quá hạn'
        if n == 0: return 'hạn nộp hôm nay'
        return f'còn {n} ngày'
    return f'{n} days left'


def progress_percent(language, p):
    """Localizes 'N% done'."""
    if p is None:
        return ''
    p = int(p)
    table = {
        'en': f'{p}% done',
        'es': f'{p}% completado',
        'fr': f'{p}% terminé',
        'ar': f'مكتمل {p}٪',
        'zh': f'已完成 {p}%',
        'hi': f'{p}% पूरा',
        'de': f'{p}% fertig',
        'pt': f'{p}% concluído',
        'it': f'{p}% completato',
        'ru': f'{p}% готово',
        'ja': f'{p}% 完了',
        'ko': f'{p}% 완료',
        'tr': f'%{p} tamamlandı',
        'nl': f'{p}% klaar',
        'pl': f'{p}% gotowe',
        'sv': f'{p}% klart',
        'ro': f'{p}% gata',
        'id': f'{p}% selesai',
        'th': f'เสร็จไป {p}%',
        'vi': f'hoàn thành {p}%',
    }
    return table.get(language, f'{p}% done')


def streak_phrase(language, n):
    """Localizes 'N-day streak'."""
    if n is None or n <= 0:
        return ''
    if language == 'en':
        return f'{n}-day streak'
    if language == 'es':
        return f'racha de {n} día' + ('' if n == 1 else 's')
    if language == 'fr':
        if n == 1: return 'série de 1 jour'
        return f'série de {n} jours'
    if language == 'ar':
        if n == 1: return 'سلسلة يوم واحد'
        if n == 2: return 'سلسلة يومين'
        if 3 <= n <= 10: return f'سلسلة {n} أيام'
        return f'سلسلة {n} يومًا'
    if language == 'zh':
        return f'{n} 天连胜'
    if language == 'hi':
        return f'{n} दिन की लय'
    if language == 'de':
        if n == 1: return '1-Tage-Serie'
        return f'{n}-Tage-Serie'
    if language == 'pt':
        return f'sequência de {n} dia' + ('' if n == 1 else 's')
    if language == 'it':
        return f'serie di {n} giorn' + ('o' if n == 1 else 'i')
    if language == 'ru':
        form = _ru_plural(n)
        if form == 'one': return f'серия {n} день'
        if form == 'few': return f'серия {n} дня'
        return f'серия {n} дней'
    if language == 'ja':
        return f'{n} 日連続'
    if language == 'ko':
        return f'{n}일 연속'
    if language == 'tr':
        return f'{n} günlük seri'
    if language == 'nl':
        if n == 1: return '1-daagse reeks'
        return f'{n}-daagse reeks'
    if language == 'pl':
        form = _pl_plural(n)
        if form == 'one': return 'seria 1 dnia'
        if form == 'few': return f'seria {n} dni'
        return f'seria {n} dni'
    if language == 'sv':
        return f'{n}-dagars svit'
    if language == 'ro':
        if n == 1: return 'serie de 1 zi'
        return f'serie de {n} zile'
    if language == 'id':
        return f'streak {n} hari'
    if language == 'th':
        return f'ต่อเนื่อง {n} วัน'
    if language == 'vi':
        return f'chuỗi {n} ngày'
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
    'de': {
        'deadline':      "Ich weiß, die Deadline rückt näher.",
        'confused':      "Vor einer leeren Seite zu sitzen ist das Schlimmste.",
        'noTime':        "Zwischen allem anderen Zeit zum Schreiben zu finden ist hart.",
        'perfectionist': "Es perfekt machen zu wollen bringt seinen eigenen Druck.",
    },
    'pt': {
        'deadline':      "Eu sei que o prazo está apertado.",
        'confused':      "Começar de uma página em branco é a parte mais difícil.",
        'noTime':        "Entre tudo o mais, achar tempo para escrever é cruel.",
        'perfectionist': "Querer que fique excelente traz sua própria pressão.",
    },
    'it': {
        'deadline':      "So che la scadenza è vicina.",
        'confused':      "Partire da una pagina bianca è la parte più dura.",
        'noTime':        "Tra tutto il resto, trovare tempo per scrivere è brutale.",
        'perfectionist': "Volere che sia eccellente porta la sua pressione.",
    },
    'ru': {
        'deadline':      "Я знаю, что дедлайн уже близко.",
        'confused':      "Начать с чистого листа — самое сложное.",
        'noTime':        "Между всем остальным найти время на письмо — это испытание.",
        'perfectionist': "Желание сделать идеально само по себе давит.",
    },
    'ja': {
        'deadline':      "締切が近づいているのは分かっています。",
        'confused':      "白紙から始めるのが一番難しい部分です。",
        'noTime':        "他のすべての中で書く時間を見つけるのは本当に大変です。",
        'perfectionist': "完璧にしたいという気持ち自体がプレッシャーですよね。",
    },
    'ko': {
        'deadline':      "마감일이 다가오고 있다는 거 알아요.",
        'confused':      "백지에서 시작하는 게 가장 어렵죠.",
        'noTime':        "다른 일들 사이에서 글 쓸 시간을 내는 건 정말 힘듭니다.",
        'perfectionist': "완벽하게 하고 싶은 마음 자체가 큰 압박이죠.",
    },
    'tr': {
        'deadline':      "Teslim tarihinin yakın olduğunu biliyorum.",
        'confused':      "Boş bir sayfayla başlamak en zor kısım.",
        'noTime':        "Diğer her şeyin arasında yazmaya zaman bulmak çok zor.",
        'perfectionist': "Mükemmel olmasını istemek kendi başına bir baskı.",
    },
    'nl': {
        'deadline':      "Ik weet dat de deadline dichtbij voelt.",
        'confused':      "Beginnen vanaf een leeg blad is het moeilijkste.",
        'noTime':        "Tussen alles door tijd vinden om te schrijven is loodzwaar.",
        'perfectionist': "Willen dat het uitstekend wordt is een druk op zich.",
    },
    'pl': {
        'deadline':      "Wiem, że termin jest blisko.",
        'confused':      "Zaczynanie od pustej strony to najtrudniejsza część.",
        'noTime':        "Między wszystkim innym znaleźć czas na pisanie jest brutalnie trudno.",
        'perfectionist': "Chęć zrobienia tego perfekcyjnie sama w sobie jest presją.",
    },
    'sv': {
        'deadline':      "Jag vet att deadline känns nära.",
        'confused':      "Att börja från ett tomt blad är det svåraste.",
        'noTime':        "Mellan allt annat är det brutalt att hitta skrivtid.",
        'perfectionist': "Att vilja att det ska bli utmärkt är sin egen sorts press.",
    },
    'ro': {
        'deadline':      "Știu că termenul se apropie.",
        'confused':      "Să începi de la o pagină goală este partea cea mai grea.",
        'noTime':        "Între toate celelalte, să găsești timp să scrii e brutal.",
        'perfectionist': "Să vrei să iasă excelent este o presiune în sine.",
    },
    'id': {
        'deadline':      "Aku tahu deadlinenya sudah dekat.",
        'confused':      "Memulai dari halaman kosong adalah bagian tersulit.",
        'noTime':        "Di tengah semua hal lain, mencari waktu menulis itu berat sekali.",
        'perfectionist': "Ingin membuatnya sempurna itu sendiri sudah jadi tekanan.",
    },
    'th': {
        'deadline':      "ฉันรู้ว่ากำหนดส่งใกล้เข้ามาแล้ว",
        'confused':      "การเริ่มต้นจากหน้ากระดาษเปล่าคือส่วนที่ยากที่สุด",
        'noTime':        "ท่ามกลางทุกอย่าง การหาเวลามาเขียนนั้นโหดมาก",
        'perfectionist': "การอยากให้มันออกมาดีเยี่ยมก็เป็นแรงกดดันในตัวมันเอง",
    },
    'vi': {
        'deadline':      "Mình biết hạn nộp đang đến gần.",
        'confused':      "Bắt đầu từ một trang trắng là phần khó nhất.",
        'noTime':        "Giữa mọi thứ khác, tìm được thời gian để viết là cực kỳ khó.",
        'perfectionist': "Muốn nó thật xuất sắc tự nó đã là một áp lực.",
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
    'en': {'shortEssay': 'essay',     'researchPaper': 'research paper',         'fullThesis': 'thesis',         'dissertation': 'dissertation'},
    'es': {'shortEssay': 'ensayo',    'researchPaper': 'trabajo de investigación','fullThesis': 'tesis',         'dissertation': 'tesis doctoral'},
    'fr': {'shortEssay': 'dissertation','researchPaper': 'article de recherche', 'fullThesis': 'mémoire',        'dissertation': 'thèse'},
    'ar': {'shortEssay': 'مقال',       'researchPaper': 'ورقة بحثية',            'fullThesis': 'أطروحة',         'dissertation': 'رسالة دكتوراه'},
    'zh': {'shortEssay': '论文',        'researchPaper': '研究论文',               'fullThesis': '学位论文',        'dissertation': '博士论文'},
    'hi': {'shortEssay': 'निबंध',       'researchPaper': 'शोध पत्र',                'fullThesis': 'थीसिस',          'dissertation': 'शोध-प्रबंध'},
    'de': {'shortEssay': 'Aufsatz',    'researchPaper': 'Forschungsarbeit',      'fullThesis': 'Abschlussarbeit','dissertation': 'Dissertation'},
    'pt': {'shortEssay': 'ensaio',    'researchPaper': 'artigo de pesquisa',    'fullThesis': 'tese',           'dissertation': 'dissertação'},
    'it': {'shortEssay': 'saggio',    'researchPaper': 'articolo di ricerca',   'fullThesis': 'tesi',           'dissertation': 'tesi di dottorato'},
    'ru': {'shortEssay': 'эссе',       'researchPaper': 'научная статья',         'fullThesis': 'дипломная работа','dissertation': 'диссертация'},
    'ja': {'shortEssay': 'エッセイ',     'researchPaper': '研究論文',                'fullThesis': '卒業論文',         'dissertation': '博士論文'},
    'ko': {'shortEssay': '에세이',      'researchPaper': '연구 논문',               'fullThesis': '졸업 논문',         'dissertation': '박사 학위 논문'},
    'tr': {'shortEssay': 'deneme',    'researchPaper': 'araştırma makalesi',    'fullThesis': 'tez',            'dissertation': 'doktora tezi'},
    'nl': {'shortEssay': 'essay',     'researchPaper': 'onderzoekspaper',       'fullThesis': 'scriptie',       'dissertation': 'proefschrift'},
    'pl': {'shortEssay': 'esej',      'researchPaper': 'praca badawcza',        'fullThesis': 'praca dyplomowa','dissertation': 'rozprawa doktorska'},
    'sv': {'shortEssay': 'essä',      'researchPaper': 'forskningsuppsats',     'fullThesis': 'examensarbete',  'dissertation': 'avhandling'},
    'ro': {'shortEssay': 'eseu',      'researchPaper': 'lucrare de cercetare',  'fullThesis': 'teză',           'dissertation': 'teză de doctorat'},
    'id': {'shortEssay': 'esai',      'researchPaper': 'makalah penelitian',    'fullThesis': 'skripsi',        'dissertation': 'disertasi'},
    'th': {'shortEssay': 'เรียงความ',  'researchPaper': 'งานวิจัย',                'fullThesis': 'วิทยานิพนธ์',     'dissertation': 'ดุษฎีนิพนธ์'},
    'vi': {'shortEssay': 'bài luận',  'researchPaper': 'bài nghiên cứu',        'fullThesis': 'luận văn',       'dissertation': 'luận án'},
}


def work_type_label(language, work_type):
    if not work_type:
        return ''
    table = WORK_TYPE_LABEL.get(language) or WORK_TYPE_LABEL['en']
    return table.get(work_type, work_type)


# Generic greeting / sign-off / footer phrases used by every email's
# HTML chrome. Senders import this dict directly instead of redefining
# the same 20 lines each time.
GREETINGS = {
    'en': 'Hey,',           'es': 'Hola,',          'fr': 'Salut,',
    'ar': 'مرحبًا،',         'zh': '你好，',          'hi': 'नमस्ते,',
    'de': 'Hallo,',         'pt': 'Olá,',           'it': 'Ciao,',
    'ru': 'Привет,',         'ja': 'こんにちは、',     'ko': '안녕하세요,',
    'tr': 'Selam,',          'nl': 'Hoi,',           'pl': 'Cześć,',
    'sv': 'Hej,',           'ro': 'Salut,',         'id': 'Hai,',
    'th': 'สวัสดี',           'vi': 'Chào bạn,',
}

SIGNOFFS = {
    'en': 'Talk soon,',     'es': 'Hasta pronto,',  'fr': 'À bientôt,',
    'ar': 'إلى اللقاء،',     'zh': '回头聊，',         'hi': 'जल्द बात करते हैं,',
    'de': 'Bis bald,',      'pt': 'Até breve,',     'it': 'A presto,',
    'ru': 'До связи,',      'ja': 'またね、',         'ko': '곧 또 봬요,',
    'tr': 'Görüşmek üzere,', 'nl': 'Tot snel,',     'pl': 'Do usłyszenia,',
    'sv': 'Vi hörs,',       'ro': 'Pe curând,',     'id': 'Sampai jumpa,',
    'th': 'แล้วคุยกันใหม่,',   'vi': 'Sớm gặp lại,',
}

CELEBRATORY_GREETINGS = {
    'en': 'Congratulations,', 'es': '¡Felicidades!,', 'fr': 'Félicitations,',
    'ar': 'تهانينا،',          'zh': '恭喜，',           'hi': 'बधाई,',
    'de': 'Glückwunsch,',     'pt': 'Parabéns,',      'it': 'Complimenti,',
    'ru': 'Поздравляю,',       'ja': 'おめでとう、',      'ko': '축하해요,',
    'tr': 'Tebrikler,',       'nl': 'Gefeliciteerd,', 'pl': 'Gratulacje,',
    'sv': 'Grattis,',         'ro': 'Felicitări,',    'id': 'Selamat,',
    'th': 'ยินดีด้วย',          'vi': 'Chúc mừng,',
}

CELEBRATORY_SIGNOFFS = {
    'en': 'So proud of you,', 'es': 'Muy orgullosa de ti,', 'fr': 'Très fière de toi,',
    'ar': 'فخور بك،',         'zh': '为你骄傲，',             'hi': 'आप पर गर्व है,',
    'de': 'Ich bin stolz auf dich,', 'pt': 'Muito orgulhosa de você,', 'it': 'Sono orgogliosa di te,',
    'ru': 'Горжусь тобой,',    'ja': '誇りに思います、',        'ko': '정말 자랑스러워요,',
    'tr': 'Seninle gurur duyuyorum,', 'nl': 'Trots op je,',  'pl': 'Jestem z ciebie dumna,',
    'sv': 'Stolt över dig,',  'ro': 'Sunt mândră de tine,', 'id': 'Bangga sama kamu,',
    'th': 'ภูมิใจในตัวคุณนะ',    'vi': 'Rất tự hào về bạn,',
}


def footer_text(language, app_name):
    """Returns the localized 'You're receiving this because…' line."""
    table = {
        'en': f"You're receiving this because you signed up for {app_name}.",
        'es': f"Recibes esto porque te registraste en {app_name}.",
        'fr': f"Vous recevez ceci car vous vous êtes inscrit(e) à {app_name}.",
        'ar': f"تتلقى هذا البريد لأنك سجلت في {app_name}.",
        'zh': f"您收到此邮件是因为您注册了 {app_name}。",
        'hi': f"आपको यह ईमेल इसलिए मिल रहा है क्योंकि आपने {app_name} के लिए साइन अप किया है।",
        'de': f"Du erhältst diese E-Mail, weil du dich bei {app_name} angemeldet hast.",
        'pt': f"Você está recebendo isso porque se cadastrou no {app_name}.",
        'it': f"Ricevi questa email perché ti sei iscritto a {app_name}.",
        'ru': f"Вы получили это письмо, потому что зарегистрировались в {app_name}.",
        'ja': f"あなたが {app_name} に登録したため、このメールをお送りしています。",
        'ko': f"{app_name}에 가입하셨기 때문에 이 이메일을 받으셨습니다.",
        'tr': f"Bu e-postayı {app_name}'a kaydolduğunuz için alıyorsunuz.",
        'nl': f"Je ontvangt dit omdat je je hebt aangemeld voor {app_name}.",
        'pl': f"Otrzymujesz tę wiadomość, ponieważ zarejestrowałeś się w {app_name}.",
        'sv': f"Du får detta mejl eftersom du registrerade dig på {app_name}.",
        'ro': f"Primești acest mesaj pentru că te-ai înscris la {app_name}.",
        'id': f"Kamu menerima ini karena mendaftar di {app_name}.",
        'th': f"คุณได้รับอีเมลนี้เพราะคุณสมัครใช้ {app_name}",
        'vi': f"Bạn nhận được email này vì đã đăng ký {app_name}.",
    }
    return table.get(language, table['en'])


def normalize_language(lang):
    """Normalize raw locale strings ('en_US', 'pt-BR', etc.) into the
    canonical 2-letter code expected by every other function here.
    Falls back to 'en' for unsupported codes."""
    if not lang:
        return 'en'
    code = str(lang).strip().lower().split('_')[0].split('-')[0]
    return code if code in LANGUAGES else 'en'


_PLACEHOLDER_RE = re.compile(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}')

# Phrase helpers — always run through the localized formatters first.
_FORMATTED_KEYS = (
    'first_name', 'topic', 'days_left', 'streak', 'progress',
    'work_type', 'pain_hook', 'app_name',
)

# Never copy these into mail even if a template accidentally uses them.
_SKIP_EXTRA_KEYS = {
    'email', 'uid', 'user_id', 'userid', 'id', 'password',
    'token', 'id_token', 'refresh_token', 'access_token',
    'api_key', 'apikey', 'fcm_token', 'push_token',
}


def _looks_secret(key):
    k = (key or '').lower()
    if k in _SKIP_EXTRA_KEYS:
        return True
    return any(part in k for part in (
        'token', 'secret', 'password', 'api_key', 'apikey', 'service_role',
    ))


def _scalar_text(value):
    """Stringify a plan value for mail, or None to skip (leftover strip)."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value == int(value) else str(value)
    if isinstance(value, str):
        return value.replace('\n', '<br>') if '\n' in value else value
    return None


def _apply_token(text, key, value):
    token = '{{' + key + '}}'
    if token not in text:
        return text
    if value:
        return text.replace(token, str(value))
    # Empty: drop a neighboring space so "Hi {{first_name}}," → "Hi,".
    text = text.replace(' ' + token, '')
    text = text.replace(token + ' ', '')
    return text.replace(token, '')


def strip_unreplaced_placeholders(text):
    """Remove leftover {{tokens}} so a missing field never ships."""
    if not text or '{{' not in text:
        return text or ''
    out = text
    for key in _PLACEHOLDER_RE.findall(out):
        out = _apply_token(out, key, '')
    return out


def interpolate(language, text, plan):
    """Replace {{placeholder}} tokens in `text` using the user's plan.

    Formatted placeholders (localized phrases):
        {{first_name}}     → plan.first_name (fallback "")
        {{topic}}          → plan.topic
        {{days_left}}      → localized days-left phrase
        {{streak}}         → localized streak phrase
        {{progress}}       → localized progress phrase (caller must include
                             a 'progress' key in plan)
        {{work_type}}      → localized work-type label
        {{pain_hook}}      → empathy sentence based on plan.pain
        {{app_name}}       → plan.app_name (fallback "Thesis Generator")

    Any other {{key}} whose value is a string/number on `plan` is filled
    as-is ({{days_since_story}}, {{dog_name}}, {{struggle}}, …). Leftover
    tokens after that are stripped so a typo never reaches the inbox.

    Empty placeholders collapse cleanly: trailing/leading whitespace removed
    when a value resolves to '' so the email doesn't show "Hi , ..." for a
    user without a first name.
    """
    if not text:
        return ''
    if not plan:
        return strip_unreplaced_placeholders(text)

    repl = {
        'first_name':  plan.get('first_name', '') or '',
        'topic':       plan.get('topic', '') or '',
        'days_left':   days_left(language, plan.get('days_left')),
        'streak':      streak_phrase(language, plan.get('streak')),
        'progress':    progress_percent(language, plan.get('progress')),
        'work_type':   work_type_label(language, plan.get('work_type', '')),
        'pain_hook':   pain_hook(language, plan.get('pain', '')),
        'app_name':    plan.get('app_name', '') or 'Thesis Generator',
    }

    out = text
    for key, value in repl.items():
        out = _apply_token(out, key, value)

    for key in _PLACEHOLDER_RE.findall(out):
        if key in _FORMATTED_KEYS or _looks_secret(key) or key not in plan:
            continue
        rendered = _scalar_text(plan.get(key))
        if rendered is None:
            continue
        out = _apply_token(out, key, rendered)

    return strip_unreplaced_placeholders(out)


if __name__ == '__main__':
    sample_plan = {
        'first_name': 'María',
        'topic': 'Impacto de la IA en la educación',
        'days_left': 5,
        'streak': 3,
        'progress': 60,
        'work_type': 'fullThesis',
        'pain': 'deadline',
        'days_since_story': '3',
        'dog_name': 'Mochi',
        'email': 'secret@example.com',
    }
    checks = [
        (
            interpolate('en', "Day {{days_since_story}} since our first note.", sample_plan),
            'Day 3 since our first note.',
        ),
        (
            interpolate('en', "Hi {{first_name}} — {{dog_name}} is waiting.", sample_plan),
            'Hi María — Mochi is waiting.',
        ),
        (
            interpolate('en', 'Leak {{email}} and {{missing_field}} here.', sample_plan),
            'Leak and here.',
        ),
        (
            interpolate('en', 'Hi {{first_name}},', {'first_name': ''}),
            'Hi,',
        ),
    ]
    failed = 0
    for got, want in checks:
        if got != want:
            failed += 1
            print(f'FAIL\n  got:  {got!r}\n  want: {want!r}')
    if failed:
        raise SystemExit(f'{failed} interpolate check(s) failed')
    print('interpolate checks passed')
    for lang in LANGUAGES:
        print(f"\n--- {lang} ---")
        print(interpolate(lang, 'Hi {{first_name}}, {{pain_hook}} Your {{work_type}} on "{{topic}}" — {{days_left}}.', sample_plan))
        print(interpolate(lang, '{{streak}}, {{progress}}.', sample_plan))
