// Supabase Edge Function: predictify-nba-winback-email
//
// The win-back sender. Fired per-user by the `predictify-nba-winback` cron
// for Predictify NBA users who've gone quiet for ~7 days — the external
// trigger that re-enters the Hooked loop for a lapsing user.
//
//   POST .../functions/v1/predictify-nba-winback-email
//   { uid, email, language?, first_name? }
//
// Dedup: lifetime (uid, 'winback') — one win-back per user. Localized (13 langs).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { handleNbaEmail, type Template } from "../_shared/nba_email.ts";

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "🏀 {{first_name}}, the league moved on without you",
    body: [
      "Hey {{first_name}},",
      "You've been gone about a week — and the NBA didn't wait. Upsets, buzzer-beaters, a leaderboard that reshuffled, and your prediction streak sitting at zero. The model kept calling games all week. You just weren't there to cash in.",
      "Good news: tonight's slate is stacked and your edge is one tap away. Predictify already crunched every game — the confidence scores are ready. Open the app, make one pick, and you're back in it.",
      "P.S. The fans who passed you on the leaderboard are hoping you stay away. Prove them wrong tonight.",
    ],
    cta: "See tonight's games",
  },
  es: {
    subject: "🏀 {{first_name}}, la liga siguió sin ti",
    body: [
      "Hola {{first_name}},",
      "Llevas casi una semana fuera — y la NBA no esperó. Sorpresas, canastas sobre la bocina, una tabla que se reordenó y tu racha de predicciones en cero. El modelo siguió analizando partidos toda la semana. Tú no estuviste para aprovecharlo.",
      "La buena noticia: la cartelera de esta noche está cargada y tu ventaja está a un toque. Predictify ya analizó cada partido — los scores de confianza están listos. Abre la app, haz una predicción y vuelves a estar dentro.",
      "P.D. Los que te pasaron en la tabla esperan que sigas ausente. Demuéstrales lo contrario esta noche.",
    ],
    cta: "Ver los partidos de hoy",
  },
  fr: {
    subject: "🏀 {{first_name}}, la ligue a continué sans toi",
    body: [
      "Bonjour {{first_name}},",
      "Tu es absent depuis presque une semaine — et la NBA n'a pas attendu. Surprises, paniers au buzzer, un classement rebattu, et ta série de pronostics à zéro. Le modèle a analysé les matchs toute la semaine. Tu n'étais juste pas là pour en profiter.",
      "Bonne nouvelle : l'affiche de ce soir est chargée et ton avantage est à un geste. Predictify a déjà tout analysé — les scores de confiance sont prêts. Ouvre l'appli, fais un pronostic, et te revoilà dans la course.",
      "P.-S. Ceux qui t'ont doublé au classement espèrent que tu restes au loin. Prouve-leur le contraire ce soir.",
    ],
    cta: "Voir les matchs du soir",
  },
  ar: {
    subject: "🏀 {{first_name}}، الدوري استمر بدونك",
    body: [
      "مرحبًا {{first_name}}،",
      "غبت نحو أسبوع — والدوري لم ينتظر. مفاجآت، تسديدات في الثواني الأخيرة، ترتيب أُعيد خلطه، وسلسلة توقعاتك عند الصفر. النموذج ظل يحلل المباريات طوال الأسبوع. أنت فقط لم تكن موجودًا لتستفيد.",
      "الخبر الجيد: مباريات الليلة قوية وأفضليتك على بُعد نقرة واحدة. حلّل Predictify كل مباراة — درجات الثقة جاهزة. افتح التطبيق، توقّع مباراة واحدة، وستعود إلى اللعب.",
      "ملاحظة: من تجاوزوك في الترتيب يأملون أن تبقى بعيدًا. أثبت عكس ذلك الليلة.",
    ],
    cta: "شاهد مباريات الليلة",
  },
  pt: {
    subject: "🏀 {{first_name}}, a liga seguiu sem você",
    body: [
      "Olá {{first_name}},",
      "Você sumiu por quase uma semana — e a NBA não esperou. Zebras, cestas no estouro do cronômetro, um ranking que mudou tudo, e sua sequência de palpites zerada. O modelo continuou analisando jogos a semana toda. Você só não estava lá para aproveitar.",
      "Boa notícia: a rodada de hoje está recheada e sua vantagem está a um toque. O Predictify já analisou cada jogo — os scores de confiança estão prontos. Abra o app, faça um palpite e você volta pro jogo.",
      "P.S. Quem te ultrapassou no ranking torce para você continuar fora. Prove o contrário hoje à noite.",
    ],
    cta: "Ver os jogos de hoje",
  },
  de: {
    subject: "🏀 {{first_name}}, die Liga ist ohne dich weitergezogen",
    body: [
      "Hallo {{first_name}},",
      "Du warst etwa eine Woche weg — und die NBA hat nicht gewartet. Überraschungen, Buzzer-Beater, eine neu gemischte Rangliste, und deine Vorhersage-Serie steht bei null. Das Modell hat die ganze Woche Spiele getippt. Du warst nur nicht da, um zu profitieren.",
      "Gute Nachricht: das heutige Programm ist prall gefüllt und dein Vorteil ist einen Tipp entfernt. Predictify hat schon jedes Spiel ausgewertet — die Confidence Scores sind bereit. Öffne die App, mach einen Tipp, und du bist wieder dabei.",
      "P.S. Die, die dich in der Rangliste überholt haben, hoffen, dass du wegbleibst. Beweis ihnen heute Abend das Gegenteil.",
    ],
    cta: "Heutige Spiele ansehen",
  },
  tr: {
    subject: "🏀 {{first_name}}, lig sensiz devam etti",
    body: [
      "Merhaba {{first_name}},",
      "Yaklaşık bir haftadır yoktun — ve NBA beklemedi. Sürprizler, son saniye basketleri, yeniden karışan bir sıralama ve sıfırda duran tahmin serin. Model tüm hafta maçları analiz etti. Sen sadece kazanmak için orada değildin.",
      "İyi haber: bu geceki program dolu ve avantajın bir dokunuş uzakta. Predictify her maçı çoktan analiz etti — güven skorları hazır. Uygulamayı aç, bir tahmin yap ve yeniden oyundasın.",
      "Not: Sıralamada seni geçenler uzak kalmanı umuyor. Bu gece onlara yanıldıklarını göster.",
    ],
    cta: "Bu geceki maçları gör",
  },
  it: {
    subject: "🏀 {{first_name}}, la lega è andata avanti senza di te",
    body: [
      "Ciao {{first_name}},",
      "Sei sparito per quasi una settimana — e l'NBA non ha aspettato. Sorprese, canestri sulla sirena, una classifica rimescolata e la tua striscia di pronostici a zero. Il modello ha analizzato partite tutta la settimana. Solo che tu non c'eri per approfittarne.",
      "Buona notizia: il programma di stasera è ricco e il tuo vantaggio è a un tocco. Predictify ha già elaborato ogni partita — i confidence score sono pronti. Apri l'app, fai un pronostico e sei di nuovo in gioco.",
      "P.S. Chi ti ha superato in classifica spera che tu resti lontano. Dimostragli il contrario stasera.",
    ],
    cta: "Vedi le partite di stasera",
  },
  nl: {
    subject: "🏀 {{first_name}}, de competitie ging zonder jou verder",
    body: [
      "Hoi {{first_name}},",
      "Je bent ongeveer een week weg geweest — en de NBA wachtte niet. Verrassingen, buzzer-beaters, een herschudde ranglijst, en je voorspellingsreeks staat op nul. Het model bleef de hele week wedstrijden tippen. Jij was er alleen niet bij om te profiteren.",
      "Goed nieuws: het programma van vanavond zit vol en je voordeel is één tik weg. Predictify heeft elke wedstrijd al doorgerekend — de confidence scores staan klaar. Open de app, doe één voorspelling, en je doet weer mee.",
      "P.S. Degenen die je voorbijgingen op de ranglijst hopen dat je wegblijft. Bewijs vanavond het tegendeel.",
    ],
    cta: "Bekijk de wedstrijden van vanavond",
  },
  pl: {
    subject: "🏀 {{first_name}}, liga poszła dalej bez Ciebie",
    body: [
      "Cześć {{first_name}},",
      "Nie było Cię około tygodnia — a NBA nie czekała. Niespodzianki, rzuty na ostatnią sekundę, przetasowany ranking i Twoja seria typów na zerze. Model typował mecze przez cały tydzień. Tylko Ciebie nie było, żeby to wykorzystać.",
      "Dobra wiadomość: dzisiejszy program jest nabity, a Twoja przewaga jest o jedno dotknięcie. Predictify już przeanalizował każdy mecz — confidence score'y są gotowe. Otwórz aplikację, postaw jeden typ i znów jesteś w grze.",
      "PS Ci, którzy Cię wyprzedzili w rankingu, liczą, że zostaniesz z boku. Udowodnij im dziś wieczorem, że się mylą.",
    ],
    cta: "Zobacz dzisiejsze mecze",
  },
  ja: {
    subject: "🏀 {{first_name}}さん、リーグはあなたを置いて進みました",
    body: [
      "{{first_name}}さん、こんにちは。",
      "約1週間ご無沙汰でしたね — その間もNBAは待ってくれません。番狂わせ、ブザービーター、入れ替わったランキング、そしてあなたの連勝記録はゼロのまま。モデルは一週間ずっと試合を予想していました。あなたが受け取りに来なかっただけです。",
      "朗報です：今夜の試合は見ごたえ十分、あなたのエッジはワンタップ先に。Predictifyは全試合をすでに分析済み — confidence scoreは準備できています。アプリを開いて1つ予想すれば、もう復帰です。",
      "追伸：ランキングであなたを抜いた人たちは、あなたが戻らないことを願っています。今夜それを覆しましょう。",
    ],
    cta: "今夜の試合を見る",
  },
  hi: {
    subject: "🏀 {{first_name}}, लीग आपके बिना आगे बढ़ गई",
    body: [
      "नमस्ते {{first_name}},",
      "आप करीब एक हफ्ते से गायब रहे — और NBA ने इंतज़ार नहीं किया। उलटफेर, बज़र-बीटर, फिर से बदला हुआ लीडरबोर्ड, और आपकी भविष्यवाणी स्ट्रीक शून्य पर। मॉडल पूरे हफ्ते गेम्स कॉल करता रहा। बस आप फायदा उठाने के लिए मौजूद नहीं थे।",
      "अच्छी खबर: आज रात के मैच दमदार हैं और आपका एज एक टैप दूर है। Predictify ने हर गेम का विश्लेषण कर लिया है — confidence scores तैयार हैं। ऐप खोलें, एक भविष्यवाणी करें, और आप फिर से खेल में हैं।",
      "पुनश्च: लीडरबोर्ड पर आपसे आगे निकले लोग चाहते हैं कि आप दूर रहें। आज रात उन्हें गलत साबित करें।",
    ],
    cta: "आज रात के मैच देखें",
  },
  id: {
    subject: "🏀 {{first_name}}, liga melaju tanpamu",
    body: [
      "Hai {{first_name}},",
      "Kamu menghilang sekitar seminggu — dan NBA tidak menunggu. Kejutan, tembakan buzzer-beater, papan peringkat yang teracak ulang, dan streak prediksimu di angka nol. Model terus menganalisis pertandingan sepanjang minggu. Kamu saja yang tidak ada untuk menuainya.",
      "Kabar baik: jadwal malam ini padat dan keunggulanmu cuma satu ketukan. Predictify sudah mengolah setiap pertandingan — confidence score siap. Buka aplikasi, buat satu prediksi, dan kamu kembali bermain.",
      "P.S. Mereka yang menyalipmu di papan peringkat berharap kamu tetap menjauh. Buktikan mereka salah malam ini.",
    ],
    cta: "Lihat pertandingan malam ini",
  },
};

const GREETINGS: Record<string, string> = {
  en: "there", es: "crack", fr: "champion", ar: "صديقي", pt: "craque",
  de: "Champion", tr: "şampiyon", it: "campione", nl: "kampioen",
  pl: "mistrzu", ja: "ファン", hi: "दोस्त", id: "sobat",
};
const SIGNOFFS: Record<string, string> = {
  en: "Talk soon,", es: "Hasta pronto,", fr: "À bientôt,", ar: "إلى اللقاء،",
  pt: "Até breve,", de: "Bis bald,", tr: "Görüşürüz,", it: "A presto,",
  nl: "Tot snel,", pl: "Do zobaczenia,", ja: "それでは、", hi: "जल्द मिलते हैं,",
  id: "Sampai jumpa,",
};
const FOOTERS: Record<string, string> = {
  en: "You're receiving this because it's been a while since your last Predictify NBA prediction.",
  es: "Recibes esto porque ha pasado un tiempo desde tu última predicción en Predictify NBA.",
  fr: "Vous recevez ceci car votre dernier pronostic sur Predictify NBA remonte à un moment.",
  ar: "تتلقى هذا لأنه مضى وقت منذ آخر توقع لك على Predictify NBA.",
  pt: "Você recebe isto porque já faz um tempo desde sua última previsão no Predictify NBA.",
  de: "Du erhältst dies, weil deine letzte Vorhersage bei Predictify NBA eine Weile her ist.",
  tr: "Bunu, Predictify NBA'deki son tahmininizin üzerinden bir süre geçtiği için alıyorsunuz.",
  it: "Ricevi questo perché è passato un po' dal tuo ultimo pronostico su Predictify NBA.",
  nl: "Je ontvangt dit omdat je laatste voorspelling op Predictify NBA alweer even geleden is.",
  pl: "Otrzymujesz to, bo minęło trochę czasu od Twojej ostatniej prognozy w Predictify NBA.",
  ja: "Predictify NBAでの前回の予想からしばらく経ったため、このメールをお送りしています。",
  hi: "आपको यह इसलिए मिल रहा है क्योंकि Predictify NBA पर आपकी पिछली भविष्यवाणी को कुछ समय हो गया है।",
  id: "Kamu menerima ini karena sudah cukup lama sejak prediksi terakhirmu di Predictify NBA.",
};

Deno.serve((req) =>
  handleNbaEmail(req, {
    kind: "winback",
    templates: TEMPLATES,
    greetings: GREETINGS,
    signoffs: SIGNOFFS,
    footers: FOOTERS,
  })
);
