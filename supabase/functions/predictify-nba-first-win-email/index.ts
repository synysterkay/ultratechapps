// Supabase Edge Function: predictify-nba-first-win-email
//
// Fires INSTANTLY when a Predictify NBA user's first prediction resolves
// correct — the emotional peak that turns a trial user into a habit user.
//
//   POST .../functions/v1/predictify-nba-first-win-email
//   { uid, email, language?, first_name?, home_team?, away_team?,
//     league_name?, fixture_id? }
//
// Dedup: lifetime (uid, 'first_correct'). Fully localized (13 languages).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { handleNbaEmail, type Template } from "../_shared/nba_email.ts";

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "🎯 You called your first one, {{first_name}} — here's how to do it again",
    body: [
      "Hey {{first_name}},",
      "{{home_team}} vs {{away_team}} — you picked it, the model picked it, and the game agreed. That's your first correct NBA prediction on the board.",
      "Most people download a prediction app, scroll twice, and bounce before they ever see a confirmed call. You made it past the line that filters out 90% of fans. Open the app tomorrow and pick again — Predictify gets sharper the more you use it.",
      "P.S. Your accuracy stats are live in the app — watch them climb.",
    ],
    cta: "See today's games",
  },
  es: {
    subject: "🎯 Acertaste tu primera, {{first_name}} — así repites el éxito",
    body: [
      "Hola {{first_name}},",
      "{{home_team}} vs {{away_team}} — tú lo predijiste, el modelo lo predijo y el partido lo confirmó. Esa es tu primera predicción NBA acertada.",
      "La mayoría descarga una app de predicciones, mira dos veces y se va antes de ver un acierto confirmado. Tú superaste la línea que filtra al 90% de los aficionados. Abre la app mañana y vuelve a predecir — Predictify mejora cuanto más la usas.",
      "P.D. Tus estadísticas de acierto están en la app — míralas subir.",
    ],
    cta: "Ver los partidos de hoy",
  },
  fr: {
    subject: "🎯 Vous avez visé juste, {{first_name}} — voici comment recommencer",
    body: [
      "Bonjour {{first_name}},",
      "{{home_team}} vs {{away_team}} — vous l'avez pronostiqué, le modèle aussi, et le match a confirmé. C'est votre premier pronostic NBA réussi.",
      "La plupart téléchargent une app de pronostics, font défiler deux fois, puis abandonnent avant de voir un succès confirmé. Vous avez franchi la ligne qui élimine 90% des fans. Rouvrez l'app demain et pronostiquez encore — Predictify s'affine à mesure que vous l'utilisez.",
      "P.-S. Vos stats de réussite sont dans l'app — regardez-les grimper.",
    ],
    cta: "Voir les matchs du jour",
  },
  ar: {
    subject: "🎯 توقعك الأول كان صحيحًا يا {{first_name}} — إليك كيف تكرره",
    body: [
      "مرحبًا {{first_name}}،",
      "{{home_team}} ضد {{away_team}} — أنت توقعته، والنموذج توقعه، والمباراة أكدت ذلك. هذا أول توقع NBA صحيح لك.",
      "معظم الناس يحمّلون تطبيق توقعات، يتصفحون مرتين، ثم يغادرون قبل رؤية أي توقع صحيح. أنت تجاوزت الخط الذي يُصفّي 90% من المشجعين. افتح التطبيق غدًا وتوقّع مجددًا — يزداد Predictify دقة كلما استخدمته.",
      "ملاحظة: إحصائيات دقتك مباشرة في التطبيق — راقبها وهي ترتفع.",
    ],
    cta: "شاهد مباريات اليوم",
  },
  pt: {
    subject: "🎯 Você acertou a primeira, {{first_name}} — veja como repetir",
    body: [
      "Olá {{first_name}},",
      "{{home_team}} vs {{away_team}} — você previu, o modelo previu, e o jogo confirmou. Essa é a sua primeira previsão certa da NBA.",
      "A maioria baixa um app de previsões, rola duas vezes e desiste antes de ver um acerto confirmado. Você passou da linha que filtra 90% dos fãs. Abra o app amanhã e preveja de novo — o Predictify fica mais afiado quanto mais você usa.",
      "P.S. Suas estatísticas de acerto estão no app — veja-as subir.",
    ],
    cta: "Ver os jogos de hoje",
  },
  de: {
    subject: "🎯 Deine erste Vorhersage saß, {{first_name}} — so gelingt sie wieder",
    body: [
      "Hallo {{first_name}},",
      "{{home_team}} vs {{away_team}} — du hast es getippt, das Modell auch, und das Spiel hat es bestätigt. Das ist deine erste richtige NBA-Vorhersage.",
      "Die meisten laden eine Vorhersage-App, scrollen zweimal und steigen aus, bevor sie je einen bestätigten Treffer sehen. Du bist über die Linie, die 90% der Fans aussortiert. Öffne die App morgen und tippe wieder — Predictify wird mit jeder Nutzung schärfer.",
      "P.S. Deine Trefferquote ist live in der App — sieh zu, wie sie steigt.",
    ],
    cta: "Heutige Spiele ansehen",
  },
  tr: {
    subject: "🎯 İlk tahminini tutturdun {{first_name}} — işte tekrarının yolu",
    body: [
      "Merhaba {{first_name}},",
      "{{home_team}} - {{away_team}} — sen tahmin ettin, model tahmin etti ve maç doğruladı. Bu senin ilk doğru NBA tahminin.",
      "Çoğu kişi bir tahmin uygulaması indirir, iki kez kaydırır ve doğrulanmış bir tahmini görmeden çıkar. Sen, taraftarların %90'ını eleyen çizgiyi geçtin. Yarın uygulamayı aç ve yine tahmin et — Predictify kullandıkça keskinleşir.",
      "Not: İsabet istatistiklerin uygulamada canlı — yükselişini izle.",
    ],
    cta: "Bugünkü maçları gör",
  },
  it: {
    subject: "🎯 Hai indovinato la prima, {{first_name}} — ecco come ripetere",
    body: [
      "Ciao {{first_name}},",
      "{{home_team}} vs {{away_team}} — l'hai pronosticato tu, l'ha fatto il modello, e la partita ha confermato. È il tuo primo pronostico NBA azzeccato.",
      "Molti scaricano un'app di pronostici, scorrono due volte e se ne vanno prima di vedere un successo confermato. Tu hai superato la linea che esclude il 90% dei tifosi. Riapri l'app domani e pronostica ancora — Predictify diventa più preciso più lo usi.",
      "P.S. Le tue statistiche di precisione sono live nell'app — guardale salire.",
    ],
    cta: "Vedi le partite di oggi",
  },
  nl: {
    subject: "🎯 Je eerste voorspelling klopte, {{first_name}} — zo doe je het opnieuw",
    body: [
      "Hoi {{first_name}},",
      "{{home_team}} vs {{away_team}} — jij koos het, het model koos het, en de wedstrijd bevestigde het. Dat is je eerste juiste NBA-voorspelling.",
      "De meesten downloaden een voorspellingsapp, scrollen twee keer en haken af voordat ze ooit een bevestigde voorspelling zien. Jij bent voorbij de lijn die 90% van de fans wegfiltert. Open de app morgen en voorspel opnieuw — Predictify wordt scherper naarmate je het gebruikt.",
      "P.S. Je trefferstatistieken staan live in de app — kijk hoe ze stijgen.",
    ],
    cta: "Bekijk de wedstrijden van vandaag",
  },
  pl: {
    subject: "🎯 Trafiłeś pierwszy typ, {{first_name}} — oto jak to powtórzyć",
    body: [
      "Cześć {{first_name}},",
      "{{home_team}} vs {{away_team}} — Ty to wytypowałeś, model też, a mecz potwierdził. To Twoja pierwsza trafiona prognoza NBA.",
      "Większość pobiera aplikację z prognozami, przewija dwa razy i znika, zanim zobaczy potwierdzony typ. Ty przekroczyłeś granicę, która odsiewa 90% kibiców. Otwórz aplikację jutro i typuj dalej — Predictify staje się dokładniejszy, im częściej go używasz.",
      "PS Twoje statystyki trafień są na żywo w aplikacji — patrz, jak rosną.",
    ],
    cta: "Zobacz dzisiejsze mecze",
  },
  ja: {
    subject: "🎯 初めての予想が的中、{{first_name}}さん — 再現する方法はこちら",
    body: [
      "{{first_name}}さん、こんにちは。",
      "{{home_team}} 対 {{away_team}} — あなたが選び、モデルも選び、試合がそれを証明しました。これがあなたの初めての的中NBA予想です。",
      "多くの人は予想アプリを入れて2回スクロールし、的中を見る前に離れていきます。あなたはファンの90%がふるい落とされる一線を越えました。明日もアプリを開いて予想を。Predictifyは使うほど精度が上がります。",
      "追伸：的中率はアプリ内でリアルタイム表示。上がっていく様子をご覧ください。",
    ],
    cta: "今日の試合を見る",
  },
  hi: {
    subject: "🎯 आपकी पहली भविष्यवाणी सही रही, {{first_name}} — इसे दोहराने का तरीका",
    body: [
      "नमस्ते {{first_name}},",
      "{{home_team}} बनाम {{away_team}} — आपने चुना, मॉडल ने चुना, और मैच ने पुष्टि की। यह आपकी पहली सही NBA भविष्यवाणी है।",
      "ज़्यादातर लोग भविष्यवाणी ऐप डाउनलोड करते हैं, दो बार स्क्रॉल करते हैं और सही भविष्यवाणी देखने से पहले ही छोड़ देते हैं। आपने वह रेखा पार कर ली जो 90% फैंस को छाँट देती है। कल फिर ऐप खोलें और भविष्यवाणी करें — Predictify जितना इस्तेमाल करेंगे उतना सटीक होता जाएगा।",
      "पुनश्च: आपके सटीकता आँकड़े ऐप में लाइव हैं — उन्हें बढ़ता देखें।",
    ],
    cta: "आज के मैच देखें",
  },
  id: {
    subject: "🎯 Tebakan pertamamu tepat, {{first_name}} — begini cara mengulanginya",
    body: [
      "Hai {{first_name}},",
      "{{home_team}} vs {{away_team}} — kamu memilihnya, model memilihnya, dan pertandingan membuktikannya. Itu prediksi NBA pertamamu yang benar.",
      "Kebanyakan orang mengunduh aplikasi prediksi, menggulir dua kali, lalu pergi sebelum melihat prediksi yang terbukti. Kamu melewati garis yang menyaring 90% penggemar. Buka aplikasi besok dan prediksi lagi — Predictify makin tajam makin sering kamu pakai.",
      "P.S. Statistik akurasimu tampil langsung di aplikasi — lihat angkanya naik.",
    ],
    cta: "Lihat pertandingan hari ini",
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
  en: "You're receiving this because your first prediction on Predictify NBA just resolved correct.",
  es: "Recibes esto porque tu primera predicción en Predictify NBA acaba de acertar.",
  fr: "Vous recevez ceci car votre premier pronostic sur Predictify NBA vient d'être validé.",
  ar: "تتلقى هذا لأن أول توقع لك على Predictify NBA كان صحيحًا للتو.",
  pt: "Você recebe isto porque sua primeira previsão no Predictify NBA acabou de acertar.",
  de: "Du erhältst dies, weil deine erste Vorhersage bei Predictify NBA gerade richtig war.",
  tr: "Bunu, Predictify NBA'deki ilk tahmininiz az önce doğru çıktığı için alıyorsunuz.",
  it: "Ricevi questo perché il tuo primo pronostico su Predictify NBA è appena risultato corretto.",
  nl: "Je ontvangt dit omdat je eerste voorspelling op Predictify NBA zojuist juist bleek.",
  pl: "Otrzymujesz to, bo Twoja pierwsza prognoza w Predictify NBA właśnie się sprawdziła.",
  ja: "Predictify NBAでの初めての予想が的中したため、このメールをお送りしています。",
  hi: "आपको यह इसलिए मिल रहा है क्योंकि Predictify NBA पर आपकी पहली भविष्यवाणी अभी सही साबित हुई।",
  id: "Kamu menerima ini karena prediksi pertamamu di Predictify NBA baru saja terbukti benar.",
};

Deno.serve((req) =>
  handleNbaEmail(req, {
    kind: "first_correct",
    templates: TEMPLATES,
    greetings: GREETINGS,
    signoffs: SIGNOFFS,
    footers: FOOTERS,
  })
);
