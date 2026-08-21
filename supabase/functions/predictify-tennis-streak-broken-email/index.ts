// Supabase Edge Function: predictify-tennis-streak-broken-email
//
// Fires when a Predictify Tennis user's prediction win-streak ends. A
// re-engagement nudge at the moment a user is most likely to churn.
//
//   POST .../functions/v1/predictify-tennis-streak-broken-email
//   { uid, email, language?, first_name?, streak_length? }
//
// Dedup: (uid, 'streak_broken'). NOTE: this is intentionally once-lifetime
// to avoid nagging; a repeat-streak variant can be added later with a
// distinct kind. Fully localized (13 languages).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { handleTennisEmail, type Template } from "../_shared/tennis_email.ts";

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "{{first_name}}, your streak ended — here's the comeback",
    body: [
      "Hey {{first_name}},",
      "Your prediction streak just ended. It happens to everyone — even the model misses. What separates the sharp from the casual is showing up the next day anyway.",
      "Today's matches is live. Open the app, check the AI's picks, and start a new streak. The best run is always the one that starts right after a loss.",
      "P.S. Your all-time accuracy still counts every win — one miss barely moves it.",
    ],
    cta: "Start a new streak",
  },
  es: {
    subject: "{{first_name}}, tu racha terminó — aquí va la remontada",
    body: [
      "Hola {{first_name}},",
      "Tu racha de aciertos acaba de terminar. Le pasa a todos — hasta el modelo falla. Lo que separa al experto del casual es volver a aparecer la noche siguiente.",
      "La jornada de hoy ya está activa. Abre la app, mira las predicciones de la IA y empieza una nueva racha. La mejor racha siempre empieza justo después de una derrota.",
      "P.D. Tu precisión histórica sigue contando cada acierto — un fallo apenas la mueve.",
    ],
    cta: "Empezar nueva racha",
  },
  fr: {
    subject: "{{first_name}}, votre série s'est arrêtée — voici le retour",
    body: [
      "Bonjour {{first_name}},",
      "Votre série de bons pronostics vient de s'arrêter. Ça arrive à tout le monde — même le modèle se trompe. Ce qui distingue le fin connaisseur, c'est de revenir le lendemain malgré tout.",
      "Les matchs de ce soir sont en ligne. Ouvrez l'app, consultez les pronostics de l'IA et lancez une nouvelle série. La meilleure série commence toujours juste après une défaite.",
      "P.-S. Votre précision globale compte encore chaque réussite — un échec la bouge à peine.",
    ],
    cta: "Lancer une nouvelle série",
  },
  ar: {
    subject: "{{first_name}}، انتهت سلسلتك — وإليك طريق العودة",
    body: [
      "مرحبًا {{first_name}}،",
      "انتهت سلسلة توقعاتك الصحيحة للتو. يحدث هذا للجميع — حتى النموذج يخطئ. ما يميّز المحترف عن العابر هو العودة في الليلة التالية رغم ذلك.",
      "مباريات الليلة متاحة الآن. افتح التطبيق، راجع توقعات الذكاء الاصطناعي، وابدأ سلسلة جديدة. أفضل سلسلة تبدأ دائمًا بعد خسارة مباشرة.",
      "ملاحظة: دقتك الإجمالية ما زالت تحسب كل فوز — خسارة واحدة بالكاد تؤثر عليها.",
    ],
    cta: "ابدأ سلسلة جديدة",
  },
  pt: {
    subject: "{{first_name}}, sua sequência acabou — eis a virada",
    body: [
      "Olá {{first_name}},",
      "Sua sequência de acertos acabou. Acontece com todo mundo — até o modelo erra. O que separa o esperto do casual é aparecer na noite seguinte mesmo assim.",
      "Os jogos de hoje já estão no ar. Abra o app, veja os palpites da IA e comece uma nova sequência. A melhor sequência sempre começa logo depois de uma derrota.",
      "P.S. Sua precisão histórica ainda conta cada acerto — um erro quase não a altera.",
    ],
    cta: "Começar nova sequência",
  },
  de: {
    subject: "{{first_name}}, deine Serie ist gerissen — so kommst du zurück",
    body: [
      "Hallo {{first_name}},",
      "Deine Treffer-Serie ist gerade gerissen. Passiert jedem — sogar das Modell liegt mal daneben. Was die Profis von den Gelegenheitstippern trennt: trotzdem am nächsten Abend wieder da sein.",
      "Die heutigen Spiele sind live. Öffne die App, sieh dir die KI-Tipps an und starte eine neue Serie. Die beste Serie beginnt immer direkt nach einer Niederlage.",
      "P.S. Deine Gesamt-Trefferquote zählt weiterhin jeden Treffer — ein Fehler bewegt sie kaum.",
    ],
    cta: "Neue Serie starten",
  },
  tr: {
    subject: "{{first_name}}, serin sona erdi — işte geri dönüş",
    body: [
      "Merhaba {{first_name}},",
      "İsabet serin az önce sona erdi. Herkesin başına gelir — model bile şaşırır. Uzmanı sıradan olandan ayıran şey, ertesi gece yine de sahada olmaktır.",
      "Bu geceki maçlar yayında. Uygulamayı aç, yapay zekânın tahminlerine bak ve yeni bir seri başlat. En iyi seri her zaman bir yenilgiden hemen sonra başlar.",
      "Not: Tüm zamanlar isabet oranın her galibiyeti hâlâ sayıyor — tek bir kayıp onu zar zor etkiler.",
    ],
    cta: "Yeni seri başlat",
  },
  it: {
    subject: "{{first_name}}, la tua striscia è finita — ecco la rimonta",
    body: [
      "Ciao {{first_name}},",
      "La tua striscia di pronostici azzeccati è appena finita. Capita a tutti — sbaglia anche il modello. Ciò che distingue l'esperto dal casuale è ripresentarsi comunque la sera dopo.",
      "Le partite di stasera sono online. Apri l'app, guarda i pronostici dell'IA e inizia una nuova striscia. La striscia migliore inizia sempre subito dopo una sconfitta.",
      "P.S. La tua precisione di sempre conta ancora ogni successo — un errore la sposta a malapena.",
    ],
    cta: "Inizia una nuova striscia",
  },
  nl: {
    subject: "{{first_name}}, je reeks is voorbij — hier is de comeback",
    body: [
      "Hoi {{first_name}},",
      "Je voorspellingsreeks is net geëindigd. Overkomt iedereen — zelfs het model zit er soms naast. Wat de scherpe van de gelegenheidsspeler onderscheidt, is de volgende avond toch weer opdagen.",
      "De wedstrijden van vanavond staan live. Open de app, bekijk de AI-voorspellingen en begin een nieuwe reeks. De beste reeks begint altijd net na een verlies.",
      "P.S. Je all-time nauwkeurigheid telt nog elke winst — één misser beweegt het amper.",
    ],
    cta: "Nieuwe reeks starten",
  },
  pl: {
    subject: "{{first_name}}, Twoja seria się skończyła — oto powrót",
    body: [
      "Cześć {{first_name}},",
      "Twoja seria trafień właśnie się skończyła. Zdarza się każdemu — nawet model się myli. Eksperta od przypadkowego gracza odróżnia to, że następnego wieczoru i tak wraca.",
      "Dzisiejsze mecze są już dostępne. Otwórz aplikację, sprawdź typy AI i zacznij nową serię. Najlepsza seria zawsze zaczyna się tuż po porażce.",
      "PS Twoja ogólna skuteczność wciąż liczy każde trafienie — jedna pomyłka ledwie ją rusza.",
    ],
    cta: "Zacznij nową serię",
  },
  ja: {
    subject: "{{first_name}}さん、連続的中が途切れました — ここから巻き返しを",
    body: [
      "{{first_name}}さん、こんにちは。",
      "連続的中が途切れました。誰にでも起こること — モデルでも外します。一流と普通を分けるのは、翌晩もまた挑むかどうかです。",
      "今夜の試合が始まっています。アプリを開いてAIの予想を確認し、新たな連続記録を始めましょう。最高の連続記録は、いつも負けの直後から始まります。",
      "追伸：通算的中率は今も一勝ごとに加算されます — 一度の外れではほとんど動きません。",
    ],
    cta: "新しい連続記録を始める",
  },
  hi: {
    subject: "{{first_name}}, आपकी लय टूट गई — अब वापसी का समय",
    body: [
      "नमस्ते {{first_name}},",
      "आपकी सही भविष्यवाणियों की लय अभी टूटी। यह सबके साथ होता है — मॉडल भी चूकता है। माहिर को आम से अलग यही करता है कि वह अगली रात फिर मैदान में उतरता है।",
      "आज रात के मैच लाइव हैं। ऐप खोलें, AI के अनुमान देखें और नई लय शुरू करें। सबसे अच्छी लय हमेशा हार के तुरंत बाद शुरू होती है।",
      "पुनश्च: आपकी कुल सटीकता हर जीत को अब भी गिनती है — एक चूक से वह मुश्किल से हिलती है।",
    ],
    cta: "नई लय शुरू करें",
  },
  id: {
    subject: "{{first_name}}, rentetanmu berakhir — ini saatnya bangkit",
    body: [
      "Hai {{first_name}},",
      "Rentetan tebakan benarmu baru saja berakhir. Ini terjadi pada semua orang — model pun bisa meleset. Yang membedakan yang jeli dari yang biasa adalah tetap hadir malam berikutnya.",
      "Pertandingan malam ini sudah tayang. Buka aplikasi, lihat prediksi AI, dan mulai rentetan baru. Rentetan terbaik selalu dimulai tepat setelah kekalahan.",
      "P.S. Akurasi sepanjang masamu masih menghitung setiap kemenangan — satu kekalahan nyaris tak menggesernya.",
    ],
    cta: "Mulai rentetan baru",
  },
};

const GREETINGS: Record<string, string> = {
  en: "there", es: "amigo", fr: "champion", ar: "صديقي", pt: "amigo",
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
  en: "You're receiving this because your prediction streak on Predictify Tennis just ended.",
  es: "Recibes esto porque tu racha de predicciones en Predictify Tennis acaba de terminar.",
  fr: "Vous recevez ceci car votre série de pronostics sur Predictify Tennis vient de s'arrêter.",
  ar: "تتلقى هذا لأن سلسلة توقعاتك على Predictify Tennis انتهت للتو.",
  pt: "Você recebe isto porque sua sequência de previsões no Predictify Tennis acabou.",
  de: "Du erhältst dies, weil deine Vorhersage-Serie bei Predictify Tennis gerade gerissen ist.",
  tr: "Bunu, Predictify Tennis'deki tahmin serin az önce sona erdiği için alıyorsunuz.",
  it: "Ricevi questo perché la tua striscia di pronostici su Predictify Tennis è appena finita.",
  nl: "Je ontvangt dit omdat je voorspellingsreeks op Predictify Tennis zojuist is geëindigd.",
  pl: "Otrzymujesz to, bo Twoja seria prognoz w Predictify Tennis właśnie się skończyła.",
  ja: "Predictify Tennisでの連続的中が途切れたため、このメールをお送りしています。",
  hi: "आपको यह इसलिए मिल रहा है क्योंकि Predictify Tennis पर आपकी भविष्यवाणी लय अभी टूटी।",
  id: "Kamu menerima ini karena rentetan prediksimu di Predictify Tennis baru saja berakhir.",
};

Deno.serve((req) =>
  handleTennisEmail(req, {
    kind: "streak_broken",
    templates: TEMPLATES,
    greetings: GREETINGS,
    signoffs: SIGNOFFS,
    footers: FOOTERS,
  })
);
