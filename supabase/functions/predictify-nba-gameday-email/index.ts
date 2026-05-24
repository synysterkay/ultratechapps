// Supabase Edge Function: predictify-nba-gameday-email
//
// The game-day sender. Fired per-user by the `predictify-nba-gameday` cron on
// nights with NBA games, for users who've drifted a few days — the recurring
// external trigger at the heart of the Hooked loop ("tonight's slate is live,
// make your pick").
//
//   POST .../functions/v1/predictify-nba-gameday-email
//   { uid, email, language?, first_name?, dedup_date }
//
// Dedup: per-day via dedup_date (kind = gameday_YYYY-MM-DD) — at most one
// game-day email per user per day. Localized (13 languages).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { handleNbaEmail, type Template } from "../_shared/nba_email.ts";

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "🏀 Tonight's NBA slate is live, {{first_name}} — your picks are waiting",
    body: [
      "Hey {{first_name}},",
      "The lights are on and tonight's games are about to tip off. Predictify already ran the numbers on every matchup — pace, ratings, injuries, rest — and the confidence scores are in the app, ready before the first jump ball.",
      "Two minutes is all it takes: open the app, scan tonight's picks, and lock in the ones you believe. Every pick keeps your streak alive and your spot on the leaderboard. Skip the night and the edge goes to waste.",
      "P.S. The sharpest fans pick before tip-off, not after. Beat the buzzer.",
    ],
    cta: "Make tonight's picks",
  },
  es: {
    subject: "🏀 La cartelera NBA de hoy ya está, {{first_name}} — tus predicciones esperan",
    body: [
      "Hola {{first_name}},",
      "Las luces están encendidas y los partidos de hoy están por empezar. Predictify ya analizó cada enfrentamiento — ritmo, ratings, lesiones, descanso — y los scores de confianza están en la app, listos antes del primer salto.",
      "Solo te toma dos minutos: abre la app, revisa las predicciones de hoy y confirma las que creas. Cada predicción mantiene viva tu racha y tu lugar en la tabla. Si te saltas la noche, desperdicias la ventaja.",
      "P.D. Los más astutos predicen antes del salto inicial, no después. Gánale a la bocina.",
    ],
    cta: "Hacer las predicciones de hoy",
  },
  fr: {
    subject: "🏀 L'affiche NBA de ce soir est là, {{first_name}} — tes pronostics t'attendent",
    body: [
      "Bonjour {{first_name}},",
      "Les projecteurs sont allumés et les matchs de ce soir vont commencer. Predictify a déjà analysé chaque affiche — rythme, ratings, blessures, repos — et les scores de confiance sont dans l'appli, prêts avant l'entre-deux.",
      "Deux minutes suffisent : ouvre l'appli, parcours les pronostics du soir et valide ceux auxquels tu crois. Chaque pronostic garde ta série en vie et ta place au classement. Si tu rates la soirée, l'avantage est perdu.",
      "P.-S. Les plus malins pronostiquent avant l'entre-deux, pas après. Bats le buzzer.",
    ],
    cta: "Faire mes pronostics du soir",
  },
  ar: {
    subject: "🏀 مباريات الليلة جاهزة يا {{first_name}} — توقعاتك بانتظارك",
    body: [
      "مرحبًا {{first_name}}،",
      "الأضواء مضاءة ومباريات الليلة على وشك الانطلاق. حلّل Predictify كل مواجهة — الإيقاع، التقييمات، الإصابات، الراحة — ودرجات الثقة موجودة في التطبيق، جاهزة قبل أول قفزة.",
      "دقيقتان تكفيان: افتح التطبيق، تصفح توقعات الليلة، وأكّد ما تؤمن به. كل توقع يُبقي سلسلتك حية ومكانك في الترتيب. إن فوّت الليلة، ضاعت الأفضلية.",
      "ملاحظة: الأذكى يتوقعون قبل بداية المباراة، لا بعدها. اسبق صافرة النهاية.",
    ],
    cta: "توقّع مباريات الليلة",
  },
  pt: {
    subject: "🏀 A rodada NBA de hoje já está no ar, {{first_name}} — seus palpites esperam",
    body: [
      "Olá {{first_name}},",
      "As luzes estão acesas e os jogos de hoje estão prestes a começar. O Predictify já analisou cada confronto — ritmo, ratings, lesões, descanso — e os scores de confiança estão no app, prontos antes da primeira bola ao alto.",
      "Leva só dois minutos: abra o app, veja os palpites de hoje e confirme os que você acredita. Cada palpite mantém sua sequência viva e seu lugar no ranking. Pular a noite é desperdiçar a vantagem.",
      "P.S. Os mais espertos palpitam antes da bola subir, não depois. Vença o cronômetro.",
    ],
    cta: "Fazer os palpites de hoje",
  },
  de: {
    subject: "🏀 Das heutige NBA-Programm läuft, {{first_name}} — deine Tipps warten",
    body: [
      "Hallo {{first_name}},",
      "Das Flutlicht ist an und die heutigen Spiele stehen kurz vorm Tip-off. Predictify hat schon jede Partie durchgerechnet — Tempo, Ratings, Verletzungen, Pausen — und die Confidence Scores sind in der App, bereit vor dem ersten Sprungball.",
      "Zwei Minuten genügen: öffne die App, sieh dir die heutigen Tipps an und bestätige die, an die du glaubst. Jeder Tipp hält deine Serie am Leben und deinen Platz in der Rangliste. Verpasst du den Abend, ist der Vorteil dahin.",
      "P.S. Die Cleversten tippen vor dem Tip-off, nicht danach. Sei vor dem Buzzer dran.",
    ],
    cta: "Heutige Tipps abgeben",
  },
  tr: {
    subject: "🏀 Bu geceki NBA programı başlıyor {{first_name}} — tahminlerin seni bekliyor",
    body: [
      "Merhaba {{first_name}},",
      "Işıklar yandı ve bu geceki maçlar başlamak üzere. Predictify her eşleşmeyi çoktan analiz etti — tempo, reytingler, sakatlıklar, dinlenme — ve güven skorları uygulamada, ilk hava atışından önce hazır.",
      "Sadece iki dakika: uygulamayı aç, bu geceki tahminlere göz at ve inandıklarını onayla. Her tahmin serini ve sıralamadaki yerini canlı tutar. Geceyi kaçırırsan avantaj boşa gider.",
      "Not: En akıllılar maç başlamadan tahmin eder, sonra değil. Sona kalan dona kalır.",
    ],
    cta: "Bu geceki tahminleri yap",
  },
  it: {
    subject: "🏀 Il programma NBA di stasera è live, {{first_name}} — i tuoi pronostici aspettano",
    body: [
      "Ciao {{first_name}},",
      "Le luci sono accese e le partite di stasera stanno per iniziare. Predictify ha già elaborato ogni sfida — ritmo, rating, infortuni, riposo — e i confidence score sono nell'app, pronti prima della prima palla a due.",
      "Bastano due minuti: apri l'app, scorri i pronostici di stasera e conferma quelli in cui credi. Ogni pronostico tiene viva la tua striscia e il tuo posto in classifica. Salti la serata e il vantaggio è sprecato.",
      "P.S. I più furbi pronosticano prima della palla a due, non dopo. Batti la sirena.",
    ],
    cta: "Fai i pronostici di stasera",
  },
  nl: {
    subject: "🏀 Het NBA-programma van vanavond is live, {{first_name}} — je voorspellingen wachten",
    body: [
      "Hoi {{first_name}},",
      "De lichten zijn aan en de wedstrijden van vanavond gaan zo beginnen. Predictify heeft elke wedstrijd al doorgerekend — tempo, ratings, blessures, rust — en de confidence scores staan in de app, klaar vóór de eerste sprongbal.",
      "Twee minuten is genoeg: open de app, bekijk de voorspellingen van vanavond en bevestig die waarin je gelooft. Elke voorspelling houdt je reeks en je plek op de ranglijst in leven. Sla je de avond over, dan is het voordeel verspild.",
      "P.S. De slimsten voorspellen vóór de tip-off, niet erna. Wees op tijd voor de buzzer.",
    ],
    cta: "Voorspellingen van vanavond doen",
  },
  pl: {
    subject: "🏀 Dzisiejszy program NBA ruszył, {{first_name}} — Twoje typy czekają",
    body: [
      "Cześć {{first_name}},",
      "Światła zapalone, a dzisiejsze mecze zaraz się zaczną. Predictify już przeliczył każde starcie — tempo, oceny, kontuzje, odpoczynek — a confidence score'y są w aplikacji, gotowe przed pierwszym podrzutem.",
      "Wystarczą dwie minuty: otwórz aplikację, przejrzyj dzisiejsze typy i zatwierdź te, w które wierzysz. Każdy typ utrzymuje Twoją serię i miejsce w rankingu. Pominiesz wieczór — przewaga się marnuje.",
      "PS Najsprytniejsi typują przed podrzutem, nie po. Zdąż przed syreną.",
    ],
    cta: "Postaw dzisiejsze typy",
  },
  ja: {
    subject: "🏀 今夜のNBAが始まります、{{first_name}}さん — 予想が待っています",
    body: [
      "{{first_name}}さん、こんにちは。",
      "照明がつき、今夜の試合がまもなくティップオフ。Predictifyはすでに全カードを分析済み — ペース、レーティング、怪我、休養 — confidence scoreはアプリ内に、最初のジャンプボール前から準備できています。",
      "たった2分：アプリを開いて今夜の予想を確認し、信じるものを確定するだけ。一つひとつの予想が連勝とランキングの順位を守ります。今夜を逃せば、そのエッジは無駄になります。",
      "追伸：賢いファンはティップオフの後ではなく前に予想します。ブザーに先んじて。",
    ],
    cta: "今夜の予想をする",
  },
  hi: {
    subject: "🏀 आज रात के NBA मैच शुरू, {{first_name}} — आपकी भविष्यवाणियाँ इंतज़ार में",
    body: [
      "नमस्ते {{first_name}},",
      "लाइटें जल चुकी हैं और आज रात के मैच बस शुरू होने वाले हैं। Predictify ने हर मुकाबले का विश्लेषण कर लिया है — पेस, रेटिंग, चोटें, आराम — और confidence scores ऐप में मौजूद हैं, पहली जंप बॉल से पहले ही तैयार।",
      "बस दो मिनट: ऐप खोलें, आज की भविष्यवाणियाँ देखें और जिन पर भरोसा हो उन्हें कन्फ़र्म करें। हर भविष्यवाणी आपकी स्ट्रीक और लीडरबोर्ड पर आपकी जगह को ज़िंदा रखती है। रात चूकी तो एज बेकार गया।",
      "पुनश्च: समझदार फैंस मैच शुरू होने से पहले भविष्यवाणी करते हैं, बाद में नहीं। बज़र से पहले कर लें।",
    ],
    cta: "आज रात की भविष्यवाणियाँ करें",
  },
  id: {
    subject: "🏀 Jadwal NBA malam ini sudah mulai, {{first_name}} — prediksimu menunggu",
    body: [
      "Hai {{first_name}},",
      "Lampu sudah menyala dan pertandingan malam ini segera tip-off. Predictify sudah menghitung setiap laga — tempo, rating, cedera, istirahat — dan confidence score ada di aplikasi, siap sebelum lemparan pertama.",
      "Cukup dua menit: buka aplikasi, lihat prediksi malam ini, dan kunci yang kamu yakini. Setiap prediksi menjaga streak dan posisimu di papan peringkat tetap hidup. Lewatkan malam ini, keunggulannya terbuang.",
      "P.S. Penggemar paling jeli memprediksi sebelum tip-off, bukan sesudah. Dahului bunyi buzzer.",
    ],
    cta: "Buat prediksi malam ini",
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
  en: "You're receiving this because there are NBA games tonight and you follow them on Predictify NBA.",
  es: "Recibes esto porque hay partidos NBA esta noche y los sigues en Predictify NBA.",
  fr: "Vous recevez ceci car il y a des matchs NBA ce soir et vous les suivez sur Predictify NBA.",
  ar: "تتلقى هذا لأن هناك مباريات NBA الليلة وتتابعها على Predictify NBA.",
  pt: "Você recebe isto porque há jogos da NBA hoje e você os acompanha no Predictify NBA.",
  de: "Du erhältst dies, weil heute Abend NBA-Spiele stattfinden und du sie auf Predictify NBA verfolgst.",
  tr: "Bunu, bu gece NBA maçları olduğu ve bunları Predictify NBA'de takip ettiğiniz için alıyorsunuz.",
  it: "Ricevi questo perché stasera ci sono partite NBA e le segui su Predictify NBA.",
  nl: "Je ontvangt dit omdat er vanavond NBA-wedstrijden zijn en je ze volgt op Predictify NBA.",
  pl: "Otrzymujesz to, bo dziś są mecze NBA, które śledzisz w Predictify NBA.",
  ja: "今夜NBAの試合があり、Predictify NBAでフォローしているため、このメールをお送りしています。",
  hi: "आपको यह इसलिए मिल रहा है क्योंकि आज रात NBA मैच हैं और आप उन्हें Predictify NBA पर फॉलो करते हैं।",
  id: "Kamu menerima ini karena ada pertandingan NBA malam ini dan kamu mengikutinya di Predictify NBA.",
};

Deno.serve((req) =>
  handleNbaEmail(req, {
    kind: "gameday",
    templates: TEMPLATES,
    greetings: GREETINGS,
    signoffs: SIGNOFFS,
    footers: FOOTERS,
  })
);
