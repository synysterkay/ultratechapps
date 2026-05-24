// Supabase Edge Function: predictify-nba-paywall-hit-email
//
// Fires when a Predictify NBA user hits the paywall but does NOT subscribe.
// Re-engages with the value proposition a few moments later by email.
//
//   POST .../functions/v1/predictify-nba-paywall-hit-email
//   { uid, email, language?, first_name? }
//
// Dedup: lifetime (uid, 'paywall_hit'). Fully localized (13 languages).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { handleNbaEmail, type Template } from "../_shared/nba_email.ts";

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "{{first_name}}, you're one tap from unlimited NBA predictions",
    body: [
      "Hey {{first_name}},",
      "You just hit the limit — which means you're actually using Predictify NBA to call games. Premium removes the ceiling: unlimited AI predictions for every matchup, every night, no credits required.",
      "It's $12.99/month with a 3-day free trial, cancel anytime. If the model steers you away from one bad call, it's already paid for itself.",
      "P.S. Prefer free? Keep earning credits by inviting friends — your choice.",
    ],
    cta: "Start my free trial",
  },
  es: {
    subject: "{{first_name}}, estás a un toque de predicciones NBA ilimitadas",
    body: [
      "Hola {{first_name}},",
      "Acabas de llegar al límite — eso significa que de verdad usas Predictify NBA para predecir partidos. Premium quita el techo: predicciones de IA ilimitadas para cada partido, cada noche, sin créditos.",
      "Son $12.99/mes con 3 días de prueba gratis, cancela cuando quieras. Si el modelo te salva de un solo error, ya se pagó solo.",
      "P.D. ¿Prefieres gratis? Sigue ganando créditos invitando amigos — tú decides.",
    ],
    cta: "Empezar prueba gratis",
  },
  fr: {
    subject: "{{first_name}}, à un clic des pronostics NBA illimités",
    body: [
      "Bonjour {{first_name}},",
      "Vous venez d'atteindre la limite — preuve que vous utilisez vraiment Predictify NBA. Premium supprime le plafond : pronostics IA illimités pour chaque match, chaque soir, sans crédits.",
      "C'est 12,99 $/mois avec 3 jours d'essai gratuit, annulable à tout moment. Si le modèle vous évite un seul mauvais pronostic, il est déjà rentabilisé.",
      "P.-S. Vous préférez le gratuit ? Continuez à gagner des crédits en invitant des amis — à vous de voir.",
    ],
    cta: "Démarrer l'essai gratuit",
  },
  ar: {
    subject: "{{first_name}}، أنت على بُعد نقرة من توقعات NBA غير محدودة",
    body: [
      "مرحبًا {{first_name}}،",
      "لقد وصلت للحد الأقصى للتو — هذا يعني أنك تستخدم Predictify NBA فعلًا لتوقع المباريات. النسخة المميزة تزيل السقف: توقعات ذكاء اصطناعي غير محدودة لكل مباراة، كل ليلة، دون أي رصيد.",
      "السعر 12.99$ شهريًا مع 3 أيام تجربة مجانية، وألغِ في أي وقت. لو أنقذك النموذج من توقع خاطئ واحد، فقد سدّد ثمنه بنفسه.",
      "ملاحظة: تفضّل المجاني؟ واصل كسب الرصيد بدعوة أصدقائك — القرار لك.",
    ],
    cta: "ابدأ التجربة المجانية",
  },
  pt: {
    subject: "{{first_name}}, você está a um toque de previsões NBA ilimitadas",
    body: [
      "Olá {{first_name}},",
      "Você acabou de atingir o limite — ou seja, está mesmo usando o Predictify NBA para prever jogos. O Premium tira o teto: previsões de IA ilimitadas para cada jogo, toda noite, sem créditos.",
      "São $12,99/mês com 3 dias de teste grátis, cancele quando quiser. Se o modelo te livrar de um único palpite ruim, já se pagou.",
      "P.S. Prefere de graça? Continue ganhando créditos convidando amigos — você escolhe.",
    ],
    cta: "Começar teste grátis",
  },
  de: {
    subject: "{{first_name}}, ein Tippen von unbegrenzten NBA-Vorhersagen entfernt",
    body: [
      "Hallo {{first_name}},",
      "Du hast gerade das Limit erreicht — das heißt, du nutzt Predictify NBA wirklich. Premium hebt die Grenze auf: unbegrenzte KI-Vorhersagen für jedes Spiel, jeden Abend, ohne Credits.",
      "Es kostet 12,99 $/Monat mit 3 Tagen Gratis-Testphase, jederzeit kündbar. Wenn dich das Modell vor einem einzigen Fehltipp bewahrt, hat es sich schon gelohnt.",
      "P.S. Lieber kostenlos? Verdiene weiter Credits, indem du Freunde einlädst — deine Wahl.",
    ],
    cta: "Gratis-Testphase starten",
  },
  tr: {
    subject: "{{first_name}}, sınırsız NBA tahminine bir dokunuş uzaktasın",
    body: [
      "Merhaba {{first_name}},",
      "Az önce sınıra ulaştın — yani Predictify NBA'i gerçekten maç tahmini için kullanıyorsun. Premium tavanı kaldırır: her maç için, her gece, kredi gerektirmeden sınırsız yapay zekâ tahmini.",
      "Aylık 12,99 $ ve 3 gün ücretsiz deneme, istediğin an iptal. Model seni tek bir kötü tahminden kurtarırsa, parasını çoktan çıkarmış olur.",
      "Not: Ücretsizi mi tercih edersin? Arkadaş davet ederek kredi kazanmaya devam et — karar senin.",
    ],
    cta: "Ücretsiz denemeyi başlat",
  },
  it: {
    subject: "{{first_name}}, sei a un tocco dai pronostici NBA illimitati",
    body: [
      "Ciao {{first_name}},",
      "Hai appena raggiunto il limite — significa che usi davvero Predictify NBA per pronosticare. Premium toglie il tetto: pronostici IA illimitati per ogni partita, ogni sera, senza crediti.",
      "Costa 12,99 $/mese con 3 giorni di prova gratuita, disdici quando vuoi. Se il modello ti evita anche un solo pronostico sbagliato, si è già ripagato.",
      "P.S. Preferisci il gratis? Continua a guadagnare crediti invitando amici — decidi tu.",
    ],
    cta: "Inizia la prova gratuita",
  },
  nl: {
    subject: "{{first_name}}, één tik verwijderd van onbeperkte NBA-voorspellingen",
    body: [
      "Hoi {{first_name}},",
      "Je hebt net de limiet bereikt — dat betekent dat je Predictify NBA echt gebruikt. Premium haalt het plafond weg: onbeperkte AI-voorspellingen voor elke wedstrijd, elke avond, zonder credits.",
      "Het is $12,99/maand met 3 dagen gratis proberen, altijd opzegbaar. Als het model je behoedt voor één verkeerde keuze, is het al terugverdiend.",
      "P.S. Liever gratis? Blijf credits verdienen door vrienden uit te nodigen — jouw keuze.",
    ],
    cta: "Gratis proefperiode starten",
  },
  pl: {
    subject: "{{first_name}}, jeden dotyk od nieograniczonych prognoz NBA",
    body: [
      "Cześć {{first_name}},",
      "Właśnie osiągnąłeś limit — to znaczy, że naprawdę używasz Predictify NBA. Premium znosi sufit: nieograniczone prognozy AI dla każdego meczu, każdej nocy, bez kredytów.",
      "To 12,99 $/miesiąc z 3-dniowym darmowym okresem próbnym, anuluj kiedy chcesz. Jeśli model uchroni Cię przed jednym złym typem, już się zwrócił.",
      "PS Wolisz za darmo? Zdobywaj kredyty, zapraszając znajomych — Twój wybór.",
    ],
    cta: "Rozpocznij darmowy okres próbny",
  },
  ja: {
    subject: "{{first_name}}さん、無制限のNBA予想まであと1タップ",
    body: [
      "{{first_name}}さん、こんにちは。",
      "上限に達しました — それはあなたが本当にPredictify NBAを使って予想している証です。プレミアムなら上限なし。毎晩すべての試合のAI予想が、クレジット不要で使い放題です。",
      "月額12.99ドル、3日間の無料トライアル付き、いつでも解約可能。たった一度の悪い予想を避けられれば、もう元は取れています。",
      "追伸：無料がよいですか？友達を招待してクレジットを貯め続けられます — お好きな方を。",
    ],
    cta: "無料トライアルを始める",
  },
  hi: {
    subject: "{{first_name}}, असीमित NBA भविष्यवाणियों से बस एक टैप दूर",
    body: [
      "नमस्ते {{first_name}},",
      "आप अभी सीमा तक पहुँचे — यानी आप वाकई Predictify NBA का इस्तेमाल कर रहे हैं। प्रीमियम सीमा हटा देता है: हर मैच के लिए, हर रात, बिना क्रेडिट के असीमित AI भविष्यवाणियाँ।",
      "यह $12.99/माह है, 3 दिन का मुफ़्त ट्रायल, कभी भी रद्द करें। अगर मॉडल आपको एक भी गलत अनुमान से बचा ले, तो इसकी कीमत वसूल हो गई।",
      "पुनश्च: मुफ़्त पसंद है? दोस्तों को बुलाकर क्रेडिट कमाते रहें — आपकी मर्ज़ी।",
    ],
    cta: "मुफ़्त ट्रायल शुरू करें",
  },
  id: {
    subject: "{{first_name}}, satu ketukan lagi menuju prediksi NBA tanpa batas",
    body: [
      "Hai {{first_name}},",
      "Kamu baru saja mencapai batas — artinya kamu benar-benar memakai Predictify NBA. Premium menghapus batas: prediksi AI tanpa batas untuk setiap pertandingan, setiap malam, tanpa kredit.",
      "Hanya $12,99/bulan dengan uji coba gratis 3 hari, batalkan kapan saja. Jika model menyelamatkanmu dari satu tebakan buruk saja, ia sudah membayar dirinya sendiri.",
      "P.S. Lebih suka gratis? Terus kumpulkan kredit dengan mengundang teman — pilihanmu.",
    ],
    cta: "Mulai uji coba gratis",
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
  en: "You're receiving this because you reached your free prediction limit on Predictify NBA.",
  es: "Recibes esto porque alcanzaste tu límite de predicciones gratis en Predictify NBA.",
  fr: "Vous recevez ceci car vous avez atteint votre limite de pronostics gratuits sur Predictify NBA.",
  ar: "تتلقى هذا لأنك بلغت حدّ التوقعات المجانية على Predictify NBA.",
  pt: "Você recebe isto porque atingiu o limite de previsões grátis no Predictify NBA.",
  de: "Du erhältst dies, weil du dein Limit an kostenlosen Vorhersagen bei Predictify NBA erreicht hast.",
  tr: "Bunu, Predictify NBA'deki ücretsiz tahmin sınırınıza ulaştığınız için alıyorsunuz.",
  it: "Ricevi questo perché hai raggiunto il limite di pronostici gratuiti su Predictify NBA.",
  nl: "Je ontvangt dit omdat je je limiet aan gratis voorspellingen op Predictify NBA hebt bereikt.",
  pl: "Otrzymujesz to, bo osiągnąłeś limit darmowych prognoz w Predictify NBA.",
  ja: "Predictify NBAの無料予想の上限に達したため、このメールをお送りしています。",
  hi: "आपको यह इसलिए मिल रहा है क्योंकि आप Predictify NBA पर मुफ़्त भविष्यवाणी सीमा तक पहुँच गए।",
  id: "Kamu menerima ini karena telah mencapai batas prediksi gratis di Predictify NBA.",
};

Deno.serve((req) =>
  handleNbaEmail(req, {
    kind: "paywall_hit",
    templates: TEMPLATES,
    greetings: GREETINGS,
    signoffs: SIGNOFFS,
    footers: FOOTERS,
  })
);
