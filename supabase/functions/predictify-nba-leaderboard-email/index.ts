// Supabase Edge Function: predictify-nba-leaderboard-email
//
// Fires INSTANTLY the first time a Predictify NBA user breaks into the Top 10
// of the leaderboard — the "reward of the tribe" social peak that pulls them
// back to defend their rank (the investment that loads the next loop).
//
//   POST .../functions/v1/predictify-nba-leaderboard-email
//   { uid, email, language?, first_name?, rank? }
//
// Dedup: lifetime (uid, 'leaderboard_top10') — fires once, the first time.
// Fully localized (13 languages).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { handleNbaEmail, type Template } from "../_shared/nba_email.ts";

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "🏆 You're in the Top 10, {{first_name}} — #{{rank}} and climbing",
    body: [
      "Hey {{first_name}},",
      "It's official — you've cracked the Top 10 on the Predictify NBA leaderboard. You're sitting at #{{rank}}, ahead of thousands of fans who thought they knew the game better than you.",
      "Here's the thing about the leaderboard: it never sleeps. Tonight's games reshuffle everything, and the people right behind you are locking in their picks as you read this. Stay sharp, keep predicting, and defend your spot.",
      "P.S. Top-10 status is bragging rights in every community. Make tonight's picks before someone takes your place.",
    ],
    cta: "Defend my rank",
  },
  es: {
    subject: "🏆 Estás en el Top 10, {{first_name}} — #{{rank}} y subiendo",
    body: [
      "Hola {{first_name}},",
      "Es oficial: entraste al Top 10 de la tabla de Predictify NBA. Estás en el puesto #{{rank}}, por delante de miles de aficionados que creían conocer mejor el juego.",
      "Lo de la tabla es así: nunca descansa. Los partidos de esta noche lo reordenan todo, y los que están justo detrás de ti ya están haciendo sus predicciones. Mantente afilado, sigue prediciendo y defiende tu lugar.",
      "P.D. Estar en el Top 10 da derecho a presumir en cada comunidad. Haz tus predicciones de hoy antes de que alguien te quite el puesto.",
    ],
    cta: "Defender mi puesto",
  },
  fr: {
    subject: "🏆 Tu es dans le Top 10, {{first_name}} — #{{rank}} et ça grimpe",
    body: [
      "Bonjour {{first_name}},",
      "C'est officiel : tu es entré dans le Top 10 du classement Predictify NBA. Tu es à la place #{{rank}}, devant des milliers de fans qui pensaient mieux connaître le jeu que toi.",
      "Le classement, c'est comme ça : il ne dort jamais. Les matchs de ce soir vont tout rebattre, et ceux juste derrière toi valident déjà leurs pronostics. Reste affûté, continue de pronostiquer et défends ta place.",
      "P.-S. Le Top 10, c'est le droit de frimer dans chaque communauté. Fais tes pronostics du soir avant que quelqu'un ne prenne ta place.",
    ],
    cta: "Défendre ma place",
  },
  ar: {
    subject: "🏆 أنت في المراكز العشرة الأولى يا {{first_name}} — المركز #{{rank}}",
    body: [
      "مرحبًا {{first_name}}،",
      "الأمر رسمي — دخلت قائمة أفضل 10 في ترتيب Predictify NBA. أنت في المركز #{{rank}}، متقدمًا على آلاف المشجعين الذين ظنوا أنهم يعرفون اللعبة أفضل منك.",
      "الترتيب لا ينام أبدًا. مباريات الليلة ستعيد ترتيب كل شيء، ومن خلفك مباشرة يؤكدون توقعاتهم الآن. ابقَ متيقظًا، واصل التوقع، ودافع عن مركزك.",
      "ملاحظة: المراكز العشرة الأولى فخر في كل مجتمع. توقّع مباريات الليلة قبل أن يأخذ أحدهم مكانك.",
    ],
    cta: "دافع عن مركزي",
  },
  pt: {
    subject: "🏆 Você está no Top 10, {{first_name}} — #{{rank}} e subindo",
    body: [
      "Olá {{first_name}},",
      "É oficial — você entrou no Top 10 do ranking do Predictify NBA. Está na posição #{{rank}}, à frente de milhares de fãs que achavam que entendiam mais do jogo que você.",
      "O ranking é assim: nunca dorme. Os jogos de hoje reorganizam tudo, e quem está logo atrás de você já está confirmando os palpites. Fique afiado, continue prevendo e defenda sua posição.",
      "P.S. Estar no Top 10 dá direito a se gabar em qualquer comunidade. Faça os palpites de hoje antes que alguém tome seu lugar.",
    ],
    cta: "Defender minha posição",
  },
  de: {
    subject: "🏆 Du bist in den Top 10, {{first_name}} — Platz #{{rank}}",
    body: [
      "Hallo {{first_name}},",
      "Es ist offiziell — du hast es in die Top 10 der Predictify-NBA-Rangliste geschafft. Du stehst auf Platz #{{rank}}, vor tausenden Fans, die dachten, sie kennen das Spiel besser als du.",
      "So ist die Rangliste: Sie schläft nie. Die heutigen Spiele mischen alles neu, und die direkt hinter dir tippen gerade jetzt. Bleib scharf, tippe weiter und verteidige deinen Platz.",
      "P.S. Top 10 ist Angeber-Recht in jeder Community. Mach deine Tipps für heute Abend, bevor dir jemand den Platz wegnimmt.",
    ],
    cta: "Meinen Platz verteidigen",
  },
  tr: {
    subject: "🏆 İlk 10'dasın {{first_name}} — #{{rank}} ve yükseliyor",
    body: [
      "Merhaba {{first_name}},",
      "Resmi oldu — Predictify NBA sıralamasında ilk 10'a girdin. #{{rank}} sıradasın, oyunu senden iyi bildiğini sanan binlerce taraftarın önünde.",
      "Sıralama hiç uyumaz. Bu geceki maçlar her şeyi yeniden karıştıracak ve hemen arkandakiler sen bunu okurken tahminlerini yapıyor. Keskin kal, tahmin etmeye devam et ve yerini koru.",
      "Not: İlk 10'da olmak her toplulukta övünme hakkıdır. Biri yerini almadan bu geceki tahminlerini yap.",
    ],
    cta: "Yerimi koru",
  },
  it: {
    subject: "🏆 Sei nella Top 10, {{first_name}} — #{{rank}} e in salita",
    body: [
      "Ciao {{first_name}},",
      "È ufficiale — sei entrato nella Top 10 della classifica di Predictify NBA. Sei al #{{rank}}, davanti a migliaia di tifosi che credevano di conoscere il gioco meglio di te.",
      "La classifica è così: non dorme mai. Le partite di stasera rimescolano tutto, e chi è subito dietro di te sta confermando i pronostici proprio ora. Resta lucido, continua a pronosticare e difendi il tuo posto.",
      "P.S. La Top 10 dà diritto a vantarsi in ogni community. Fai i pronostici di stasera prima che qualcuno ti prenda il posto.",
    ],
    cta: "Difendi il mio posto",
  },
  nl: {
    subject: "🏆 Je staat in de Top 10, {{first_name}} — #{{rank}} en stijgend",
    body: [
      "Hoi {{first_name}},",
      "Het is officieel — je bent doorgedrongen tot de Top 10 van de Predictify NBA-ranglijst. Je staat op #{{rank}}, vóór duizenden fans die dachten dat ze het spel beter kenden dan jij.",
      "Zo werkt de ranglijst: hij slaapt nooit. De wedstrijden van vanavond schudden alles door elkaar, en degenen vlak achter je leggen nu hun voorspellingen vast. Blijf scherp, blijf voorspellen en verdedig je plek.",
      "P.S. Top 10 geeft opscheprecht in elke community. Doe je voorspellingen voor vanavond voordat iemand je plek inpikt.",
    ],
    cta: "Mijn plek verdedigen",
  },
  pl: {
    subject: "🏆 Jesteś w Top 10, {{first_name}} — #{{rank}} i w górę",
    body: [
      "Cześć {{first_name}},",
      "To oficjalne — wszedłeś do Top 10 rankingu Predictify NBA. Jesteś na pozycji #{{rank}}, przed tysiącami kibiców, którzy myśleli, że znają grę lepiej niż Ty.",
      "Z rankingiem jest tak: nigdy nie śpi. Dzisiejsze mecze przetasują wszystko, a ci tuż za Tobą typują właśnie teraz. Trzymaj formę, typuj dalej i broń swojego miejsca.",
      "PS Top 10 to prawo do przechwałek w każdej społeczności. Obstaw dzisiejsze mecze, zanim ktoś zajmie Twoje miejsce.",
    ],
    cta: "Broń mojego miejsca",
  },
  ja: {
    subject: "🏆 トップ10入り、{{first_name}}さん — 第{{rank}}位",
    body: [
      "{{first_name}}さん、こんにちは。",
      "正式に決定 — Predictify NBAのランキングでトップ10入りを果たしました。現在第{{rank}}位、自分の方が試合を知っていると思っていた何千ものファンの上にいます。",
      "ランキングは決して眠りません。今夜の試合ですべてが入れ替わり、すぐ後ろの人たちは今まさに予想を確定しています。鋭さを保ち、予想を続け、自分の順位を守りましょう。",
      "追伸：トップ10はどのコミュニティでも自慢の的。誰かに順位を奪われる前に、今夜の予想を。",
    ],
    cta: "順位を守る",
  },
  hi: {
    subject: "🏆 आप टॉप 10 में हैं, {{first_name}} — #{{rank}} पर",
    body: [
      "नमस्ते {{first_name}},",
      "यह आधिकारिक है — आप Predictify NBA लीडरबोर्ड के टॉप 10 में पहुँच गए। आप #{{rank}} पर हैं, उन हज़ारों फैंस से आगे जो सोचते थे कि वे खेल आपसे बेहतर जानते हैं।",
      "लीडरबोर्ड कभी नहीं सोता। आज रात के मैच सब कुछ फिर से बदल देंगे, और आपके ठीक पीछे वाले अभी अपनी भविष्यवाणियाँ कर रहे हैं। तेज़ बने रहें, भविष्यवाणी करते रहें और अपनी जगह बचाएँ।",
      "पुनश्च: टॉप 10 में होना हर समुदाय में शान की बात है। इससे पहले कि कोई आपकी जगह ले, आज रात की भविष्यवाणियाँ करें।",
    ],
    cta: "अपनी रैंक बचाएँ",
  },
  id: {
    subject: "🏆 Kamu di Top 10, {{first_name}} — #{{rank}} dan naik",
    body: [
      "Hai {{first_name}},",
      "Resmi — kamu masuk Top 10 papan peringkat Predictify NBA. Kamu di posisi #{{rank}}, di depan ribuan penggemar yang mengira lebih paham permainan daripada kamu.",
      "Papan peringkat tak pernah tidur. Pertandingan malam ini mengacak ulang segalanya, dan yang tepat di belakangmu sedang mengunci prediksi mereka saat kamu membaca ini. Tetap tajam, terus prediksi, dan pertahankan posisimu.",
      "P.S. Status Top 10 adalah kebanggaan di setiap komunitas. Buat prediksi malam ini sebelum ada yang mengambil tempatmu.",
    ],
    cta: "Pertahankan peringkatku",
  },
};

const GREETINGS: Record<string, string> = {
  en: "there", es: "crack", fr: "champion", ar: "بطل", pt: "craque",
  de: "Champion", tr: "şampiyon", it: "campione", nl: "kampioen",
  pl: "mistrzu", ja: "ファン", hi: "चैंपियन", id: "juara",
};
const SIGNOFFS: Record<string, string> = {
  en: "Talk soon,", es: "Hasta pronto,", fr: "À bientôt,", ar: "إلى اللقاء،",
  pt: "Até breve,", de: "Bis bald,", tr: "Görüşürüz,", it: "A presto,",
  nl: "Tot snel,", pl: "Do zobaczenia,", ja: "それでは、", hi: "जल्द मिलते हैं,",
  id: "Sampai jumpa,",
};
const FOOTERS: Record<string, string> = {
  en: "You're receiving this because you just broke into the Top 10 on Predictify NBA.",
  es: "Recibes esto porque acabas de entrar al Top 10 en Predictify NBA.",
  fr: "Vous recevez ceci car vous venez d'entrer dans le Top 10 sur Predictify NBA.",
  ar: "تتلقى هذا لأنك دخلت للتو قائمة أفضل 10 على Predictify NBA.",
  pt: "Você recebe isto porque acabou de entrar no Top 10 no Predictify NBA.",
  de: "Du erhältst dies, weil du gerade in die Top 10 bei Predictify NBA gekommen bist.",
  tr: "Bunu, Predictify NBA'de az önce ilk 10'a girdiğiniz için alıyorsunuz.",
  it: "Ricevi questo perché sei appena entrato nella Top 10 su Predictify NBA.",
  nl: "Je ontvangt dit omdat je net de Top 10 op Predictify NBA hebt bereikt.",
  pl: "Otrzymujesz to, bo właśnie wszedłeś do Top 10 w Predictify NBA.",
  ja: "Predictify NBAでトップ10入りしたため、このメールをお送りしています。",
  hi: "आपको यह इसलिए मिल रहा है क्योंकि आप अभी Predictify NBA पर टॉप 10 में पहुँचे।",
  id: "Kamu menerima ini karena baru saja masuk Top 10 di Predictify NBA.",
};

Deno.serve((req) =>
  handleNbaEmail(req, {
    kind: "leaderboard_top10",
    templates: TEMPLATES,
    greetings: GREETINGS,
    signoffs: SIGNOFFS,
    footers: FOOTERS,
  })
);
