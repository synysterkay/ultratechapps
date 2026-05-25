// Supabase Edge Function: welcome-email
// Sends instant welcome email #1 when a new user signs up.
// Called by mobile apps via POST with { email, app_id, language? }
//
// Endpoint: POST https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/welcome-email
// Headers:  Authorization: Bearer <SUPABASE_ANON_KEY>
//           Content-Type: application/json

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

// ── ATTRIBUTION HELPERS ─────────────────────────────────────
async function userRef(email: string): Promise<string> {
  const data = new TextEncoder().encode(`${REF_SALT}:${email.toLowerCase().trim()}`);
  const buf = await crypto.subtle.digest("SHA-256", data);
  const hex = Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hex.slice(0, 16);
}

function sanitizeTagValue(v: string): string {
  return v.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 256);
}

function withUtm(
  url: string,
  ctx: { app: string; emailNum: string | number; cycle: number; language: string; ref: string; kind: string }
): string {
  if (!url) return url;
  try {
    const u = new URL(url);
    u.searchParams.set("utm_source", "resend");
    u.searchParams.set("utm_medium", "email");
    u.searchParams.set("utm_campaign", `${ctx.kind}_e${ctx.emailNum}`);
    u.searchParams.set("utm_content", `cycle${ctx.cycle}_${ctx.language}`);
    u.searchParams.set("utm_term", ctx.app);
    u.searchParams.set("ref", ctx.ref);
    return u.toString();
  } catch {
    return url;
  }
}

// ── SENDER POOL (same 7 domains as main system) ────────────
const SENDER_POOL = [
  // Verified-in-Resend senders only (kaynel.pl failed, vitazelki.pl retired — removed 2026-05-23).
  { email: "hello@bestaiapps.site", name: "Alex" },
  { email: "hello@aibettips.io", name: "Jordan" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
  { email: "hello@thesisgenerator.io", name: "Morgan" },
  { email: "hello@passedai.io", name: "Taylor" },
  { email: "hello@academicsatire.com", name: "Riley" },
  { email: "tips@predictify.fun", name: "Drew" },
];

function getRandomSender() {
  return SENDER_POOL[Math.floor(Math.random() * SENDER_POOL.length)];
}

// ── APP CONFIG (mapped by app_id passed from mobile apps) ───
interface EmailTemplate {
  subject: string;
  cta_text: string;
  body_paragraphs: string[];
}

interface AppConfig {
  name: string;
  multilingual: boolean;
  appStoreUrl: string;
  googlePlayUrl: string;
  emails: Record<string, EmailTemplate>;
}

const APP_CONFIG: Record<string, AppConfig> = {
  predictify: {
    name: "Predictify",
    multilingual: true,
    appStoreUrl: "https://apps.apple.com/app/predictify-soccer-ai/id6756571193",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.predictify.soccer.prediction",
    emails: {
      en: {
        subject: "Your first match prediction is waiting \u2014 here's what to do",
        cta_text: "Open My First Prediction",
        body_paragraphs: [
          "This weekend's biggest match is coming up. Your friends will guess. The pundits will argue. But you? You'll already know what the data says. Predictify just analyzed thousands of variables for every match on the schedule \u2014 xG, form, head-to-head, defensive shape \u2014 and your first prediction is ready.",
          "Here's what makes this different from every other prediction app: you don't just see who wins. You see HOW confident the AI is. That confidence score is the secret. It's the difference between 'Liverpool might win' and 'Liverpool wins 78% of the time under these exact conditions.' One number. Built from more data than you could process in a month. That's not a tip \u2014 it's an edge.",
          "Open the app right now. Tap any match on the home screen. Look at the prediction and the confidence score below it. Then make your first prediction to start your streak. It takes 30 seconds. When the match kicks off, you'll know something your friends don't. And that feeling? That's why people open this app every single day.",
          "Join a community of fans who discuss predictions daily and vote on the Prediction of the Day. P.S. Users who make a prediction on day one are 4x more likely to build a winning streak. Don't just watch football \u2014 know football."
        ],
      },
      ar: {
        subject: "\u0633\u0631\u0651 \u0648\u0627\u062d\u062f \u064a\u063a\u064a\u0651\u0631 \u0637\u0631\u064a\u0642\u0629 \u062a\u0648\u0642\u0639\u0643 \u0644\u0644\u0645\u0628\u0627\u0631\u064a\u0627\u062a \u062a\u0645\u0627\u0645\u0627\u064b",
        cta_text: "\u0627\u0641\u062a\u062d Predictify \u0627\u0644\u0622\u0646",
        body_paragraphs: [
          "\u062a\u062e\u064a\u0644 \u0623\u0646\u0643 \u062a\u0634\u0627\u0647\u062f \u0645\u0628\u0627\u0631\u0627\u0629 \u0645\u0627\u0646\u0634\u0633\u062a\u0631 \u064a\u0648\u0646\u0627\u064a\u062a\u062f \u0636\u062f \u0644\u064a\u0641\u0631\u0628\u0648\u0644. \u0627\u0644\u062c\u0645\u064a\u0639 \u064a\u062a\u062d\u062f\u062b \u0639\u0646 \u0627\u0644\u062d\u062f\u0633 \u0648\u0627\u0644\u062a\u0648\u0642\u0639\u0627\u062a. \u0644\u0643\u0646\u0643 \u062a\u0645\u0633\u0643 \u0628\u0647\u0627\u062a\u0641\u0643 \u0648\u062a\u0639\u0644\u0645 \u0627\u0644\u062d\u0642\u064a\u0642\u0629 \u0642\u0628\u0644 \u0627\u0644\u062c\u0645\u064a\u0639. \u0644\u064a\u0633 \u0633\u062d\u0631\u0627\u064b. \u0625\u0646\u0647\u0627 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a. \u0648\u0647\u0646\u0627\u0643 \u0634\u064a\u0621 \u0648\u0627\u062d\u062f \u0641\u0642\u0637 \u062a\u062d\u062a\u0627\u062c \u0644\u0641\u0639\u0644\u0647 \u0627\u0644\u0622\u0646.",
          "\u0627\u0644\u0645\u0634\u0643\u0644\u0629 \u0644\u064a\u0633\u062a \u0641\u064a \u0646\u0642\u0635 \u0627\u0644\u0645\u0639\u0644\u0648\u0645\u0627\u062a\u060c \u0628\u0644 \u0641\u064a \u0627\u0644\u0641\u0648\u0636\u0649. \u0622\u0644\u0627\u0641 \u0627\u0644\u0645\u062a\u063a\u064a\u0631\u0627\u062a \u0644\u0643\u0644 \u0645\u0628\u0627\u0631\u0627\u0629: \u0642\u0648\u0629 \u0627\u0644\u062f\u0641\u0627\u0639\u060c \u0646\u0633\u0628\u0629 \u0627\u0644\u062a\u0645\u0644\u0643\u060c xG \u0644\u0644\u0627\u0639\u0628\u064a\u0646\u060c \u0627\u0644\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0645\u0648\u0627\u062c\u0647\u0627\u062a. \u0639\u0642\u0644\u0643 \u0644\u0627 \u064a\u0633\u062a\u0637\u064a\u0639 \u0645\u0639\u0627\u0644\u062c\u0629 \u0643\u0644 \u0647\u0630\u0627. \u0644\u0643\u0646 \u0627\u0644\u0630\u0643\u0627\u0621 \u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a \u0627\u0644\u062e\u0627\u0635 \u0628\u0646\u0627 \u064a\u0641\u0639\u0644. \u0648\u0647\u0648 \u064a\u062e\u0628\u0631\u0643 \u0628\u0646\u062a\u064a\u062c\u0629 \u0648\u0627\u062d\u062f\u0629 \u0641\u0642\u0637\u060c \u0645\u0639 \u062f\u0631\u062c\u0629 \u062b\u0642\u0629 \u0648\u0627\u0636\u062d\u0629. \u0644\u0627 \u062a\u062e\u0645\u064a\u0646. \u0645\u0639\u0631\u0641\u0629.",
          "\u0627\u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642 \u0627\u0644\u0622\u0646. \u0641\u064a \u0627\u0644\u0635\u0641\u062d\u0629 \u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629\u060c \u0633\u062a\u062c\u062f '\u062a\u0648\u0642\u0639\u0627\u062a \u0627\u0644\u064a\u0648\u0645'. \u0627\u062e\u062a\u0631 \u0623\u064a \u0645\u0628\u0627\u0631\u0627\u0629. \u0633\u062a\u0638\u0647\u0631 \u0644\u0643 \u0627\u0644\u0646\u062a\u064a\u062c\u0629 \u0627\u0644\u0645\u062a\u0648\u0642\u0639\u0629 \u0648\u062f\u0631\u062c\u0629 \u0627\u0644\u062b\u0642\u0629 \u0641\u064a \u0623\u0642\u0644 \u0645\u0646 30 \u062b\u0627\u0646\u064a\u0629. \u0647\u0630\u0627 \u0647\u0648 \u0643\u0644 \u0645\u0627 \u062a\u062d\u062a\u0627\u062c\u0647 \u0644\u062a\u0628\u062f\u0623. \u0644\u0627 \u062a\u0635\u0641\u062d \u0645\u0639\u0642\u062f. \u0644\u0627 \u0636\u064a\u0627\u0639 \u0644\u0644\u0648\u0642\u062a. \u0625\u062c\u0627\u0628\u0629 \u0645\u0628\u0627\u0634\u0631\u0629 \u0639\u0644\u0649 \u0633\u0624\u0627\u0644\u0643: \u0645\u0646 \u0633\u064a\u0641\u0648\u0632\u061f",
          "\u0627\u0636\u063a\u0637 \u0627\u0644\u0632\u0631 \u0623\u062f\u0646\u0627\u0647 \u0648\u0627\u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642. \u0627\u062e\u062a\u0628\u0631 \u062a\u0648\u0642\u0639\u0627\u064b \u0648\u0627\u062d\u062f\u0627\u064b \u0641\u0642\u0637. \u0634\u0627\u0647\u062f \u0643\u064a\u0641 \u062a\u0634\u0639\u0631 \u0648\u0623\u0646\u062a \u062a\u0639\u0631\u0641 \u0645\u0627 \u0644\u0627 \u064a\u0639\u0631\u0641\u0647 \u0623\u0635\u062f\u0642\u0627\u0624\u0643. P.S.: \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0648\u0646 \u0627\u0644\u0630\u064a\u0646 \u064a\u062c\u0631\u0628\u0648\u0646 \u0647\u0630\u0647 \u0627\u0644\u0645\u064a\u0632\u0629 \u0641\u064a \u0623\u0648\u0644 5 \u062f\u0642\u0627\u0626\u0642 \u064a\u0628\u0642\u0648\u0646 \u0623\u0643\u062b\u0631 \u0628\u062b\u0644\u0627\u062b \u0645\u0631\u0627\u062a. \u0647\u0630\u0647 \u0644\u064a\u0633\u062a \u0635\u062f\u0641\u0629.",
        ],
      },
      es: {
        subject: "Confesi\u00f3n: comet\u00ed un error con tu primera predicci\u00f3n",
        cta_text: "Abrir An\u00e1lisis T\u00e1ctico",
        body_paragraphs: [
          "Acabo de revisar tu perfil y me di cuenta de algo. Cuando te diste de alta, el sistema te asign\u00f3 una predicci\u00f3n 'gen\u00e9rica' para el pr\u00f3ximo partido grande. Es el error que cometemos con todos los nuevos, pero contigo es distinto. Tu historial de b\u00fasquedas ya dice mucho.",
          "La mayor\u00eda de la gente se queda con esa predicci\u00f3n superficial y pierde la oportunidad. La que importa est\u00e1 un nivel m\u00e1s abajo. La que cruza los \u00faltimos 5 enfrentamientos entre esos equipos con el estado f\u00edsico REAL de sus 3 jugadores clave esta semana. Los n\u00fameros no mienten, y hay uno que est\u00e1 a punto de explotar.",
          "Abre la app. Ve a la pesta\u00f1a 'Hoy'. Ver\u00e1s el partido destacado. No te quedes con el porcentaje de confianza grande. Toca ah\u00ed. Se desplegar\u00e1 el 'An\u00e1lisis T\u00e1ctico Instant\u00e1neo'. En 30 segundos ver\u00e1s la variable secreta que est\u00e1 moviendo la aguja para ese encuentro. Es la diferencia entre adivinar y saber.",
          "\u00c1brelo ahora. El partido empieza pronto y esa ventana de informaci\u00f3n \u00f3ptima se cierra. Haz clic, mira el an\u00e1lisis y ver\u00e1s de lo que hablo. La app ya no es la misma despu\u00e9s de eso. P.D.: Los primeros 100 que activen el 'An\u00e1lisis T\u00e1ctico' hoy obtendr\u00e1n acceso prioritario a una funci\u00f3n nueva la pr\u00f3xima semana. Solo para los que act\u00faan.",
        ],
      },
      fr: {
        subject: "Le secret que 90% des fans de foot ignorent sur les matchs",
        cta_text: "Voir mon Score de Confiance",
        body_paragraphs: [
          "Tu sais ce sentiment quand tout le monde parie sur un r\u00e9sultat, mais que ton instinct te dit que \u00e7a va mal se passer ? Et que tu as raison ? C'est ce qui est arriv\u00e9 \u00e0 mon pote Sam hier. Tout le monde voyait une victoire facile pour le PSG. Lui, non. Et il avait raison.",
          "La raison ? Il ne se fiait pas \u00e0 son instinct. Il avait juste regard\u00e9 une seule chose dans Predictify : le Score de Confiance. En 30 secondes, il a vu que la pr\u00e9diction \"victoire facile\" n'avait qu'un score de 54%. Trop bas. Trop risqu\u00e9. Il a \u00e9vit\u00e9 un mauvais pari.",
          "Cette fonction, c'est ta jauge de v\u00e9rit\u00e9. Notre IA analyse des milliers de donn\u00e9es, puis te donne un pourcentage simple : \u00e0 quel point cette pr\u00e9diction est solide. C'est la premi\u00e8re chose que je regarde maintenant. \u00c7a t'\u00e9vite de suivre le troupeau b\u00eatement.",
          "Ouvre l'appli maintenant. Regarde le Score de Confiance pour le prochain match de ton \u00e9quipe. Tu verras tout de suite les pr\u00e9dictions qui valent le coup. C'est gratuit, et \u00e7a prend 30 secondes. P.S. : La version Premium d\u00e9bloque les analyses compl\u00e8tes derri\u00e8re chaque score. Mais commence par le gratuit, tu vas d\u00e9j\u00e0 avoir un s\u00e9rieux avantage.",
        ],
      },
      pt: {
        subject: "O erro que 90% dos novos usu\u00e1rios cometem imediatamente",
        cta_text: "Ver Meu Score de Confian\u00e7a",
        body_paragraphs: [
          "Voc\u00ea acabou de baixar o Predictify. E est\u00e1 prestes a cometer o mesmo erro que todo mundo comete. Vai olhar um jogo, ver a previs\u00e3o e pensar 'talvez'. Mas est\u00e1 ignorando a \u00fanica coisa que torna nossa IA mais inteligente que seu instinto.",
          "A verdade: uma previs\u00e3o sem confian\u00e7a \u00e9 s\u00f3 um palpite. E voc\u00ea j\u00e1 cansou disso. Nossa IA analisa milhares de dados \u2014 xG, posse de bola, forma defensiva, hist\u00f3rico de confrontos \u2014 mas a m\u00e1gica real \u00e9 o score de confian\u00e7a. \u00c9 a diferen\u00e7a entre 'o Liverpool pode ganhar' e 'o Liverpool vence 78% das vezes nessas condi\u00e7\u00f5es exatas'.",
          "Abra o app agora. V\u00e1 direto para qualquer jogo deste fim de semana. Olhe a previs\u00e3o. Depois olhe logo abaixo. V\u00ea aquela porcentagem? Esse \u00e9 o seu score de confian\u00e7a. Em 30 segundos, voc\u00ea para de adivinhar e come\u00e7a a saber.",
          "Toque no bot\u00e3o. Abra o Predictify e encontre o score de confian\u00e7a no pr\u00f3ximo jogo. Muda tudo. P.S. Usu\u00e1rios que conferem esse score no primeiro dia t\u00eam 3x mais chances de acertar na primeira semana.",
        ],
      },
      de: {
        subject: "Der eine Fehler, den 90% der neuen Nutzer sofort machen",
        cta_text: "Zeig mir den Confidence Score",
        body_paragraphs: [
          "Du hast gerade Predictify heruntergeladen. Und du bist dabei, denselben Fehler zu machen wie alle anderen. Du wirst dir ein Spiel ansehen, die Vorhersage sehen und denken 'ja, vielleicht'. Aber du \u00fcbersiehst das Eine, was unsere KI schlauer macht als dein Bauchgef\u00fchl.",
          "Die Wahrheit: Eine Vorhersage ohne Konfidenz ist nur ein Raten. Und davon hattest du genug. Unsere KI analysiert tausende Datenpunkte \u2014 xG, Ballbesitz, Defensivform, Head-to-Head-Historie \u2014 aber die echte Magie ist der Confidence Score. Das ist der Unterschied zwischen 'Liverpool k\u00f6nnte gewinnen' und 'Liverpool gewinnt zu 78% unter genau diesen Bedingungen'.",
          "\u00d6ffne die App. Jetzt sofort. Geh direkt zu einem Bundesliga-Spiel an diesem Wochenende. Schau dir die Vorhersage an. Dann schau direkt darunter. Siehst du die Prozentzahl? Das ist dein Confidence Score. In 30 Sekunden h\u00f6rst du auf zu raten und f\u00e4ngst an zu wissen.",
          "Dr\u00fcck den Button. \u00d6ffne Predictify und finde den Confidence Score f\u00fcr dein n\u00e4chstes Spiel. Es ver\u00e4ndert alles. P.S. Nutzer, die diesen Score am ersten Tag checken, erkennen 3x h\u00e4ufiger einen Value Bet in ihrer ersten Woche.",
        ],
      },
      tr: {
        subject: "Yeni kullan\u0131c\u0131lar\u0131n %90'\u0131n\u0131n hemen yapt\u0131\u011f\u0131 tek hata",
        cta_text: "G\u00fcven Skorumu G\u00f6ster",
        body_paragraphs: [
          "Predictify'i indirdin. Ve herkesin yapt\u0131\u011f\u0131 ayn\u0131 hatay\u0131 yapmak \u00fczeresin. Bir ma\u00e7a bakacak, tahmini g\u00f6recek ve 'belki' diyeceksin. Ama yapay zekam\u0131z\u0131 i\u00e7g\u00fcd\u00fcnden daha ak\u0131ll\u0131 yapan o tek \u015feyi ka\u00e7\u0131r\u0131yorsun.",
          "Ger\u00e7ek \u015fu: G\u00fcven olmadan tahmin sadece bir tahminden ibaret. Yapay zekam\u0131z her ma\u00e7 i\u00e7in binlerce veri noktas\u0131n\u0131 analiz eder \u2014 xG, topa sahip olma, defans formu, kar\u015f\u0131la\u015fma ge\u00e7mi\u015fi. As\u0131l sihir g\u00fcven skorunda. 'Liverpool kazanabilir' ile 'Liverpool tam bu ko\u015fullarda %78 oran\u0131nda kazan\u0131r' aras\u0131ndaki fark bu.",
          "Uygulamay\u0131 \u015fimdi a\u00e7. Do\u011frudan bu hafta sonu S\u00fcper Lig'deki herhangi bir ma\u00e7a git. Tahmine bak. Sonra hemen alt\u0131na bak. O y\u00fczdeyi g\u00f6r\u00fcyor musun? O senin g\u00fcven skorun. 30 saniyede tahmin etmeyi b\u0131rak\u0131p bilmeye ba\u015fl\u0131yorsun.",
          "Butona dokun. Predictify'i a\u00e7 ve bir sonraki ma\u00e7\u0131n g\u00fcven skorunu bul. Her \u015feyi de\u011fi\u015ftiriyor. P.S. \u0130lk g\u00fcn bu skoru kontrol eden kullan\u0131c\u0131lar\u0131n ilk haftada de\u011ferli bir bahis yakalamas\u0131 3 kat daha olas\u0131.",
        ],
      },
      it: {
        subject: "L'unico errore che il 90% dei nuovi utenti fa subito",
        cta_text: "Mostrami il Confidence Score",
        body_paragraphs: [
          "Hai appena scaricato Predictify. E stai per fare lo stesso errore di tutti gli altri. Guarderai una partita, vedrai la previsione e penserai 'forse'. Ma ti stai perdendo l'unica cosa che rende la nostra IA pi\u00f9 intelligente del tuo istinto.",
          "La verit\u00e0: una previsione senza confidenza \u00e8 solo un'ipotesi. La nostra IA analizza migliaia di dati \u2014 xG, possesso palla, forma difensiva, precedenti \u2014 ma la vera magia \u00e8 il confidence score. \u00c8 la differenza tra 'il Milan potrebbe vincere' e 'il Milan vince il 78% delle volte con queste condizioni'.",
          "Apri l'app. Adesso. Vai direttamente a qualsiasi partita di Serie A di questo weekend. Guarda la previsione. Poi guarda subito sotto. Vedi quella percentuale? Quello \u00e8 il tuo confidence score. In 30 secondi smetti di tirare a indovinare e inizi a sapere.",
          "Tocca il pulsante. Apri Predictify e trova il confidence score per la tua prossima partita. Cambia tutto. P.S. Gli utenti che controllano questo score il primo giorno hanno 3 volte pi\u00f9 probabilit\u00e0 di individuare una scommessa di valore nella prima settimana.",
        ],
      },
      pp: {
        subject: "O erro que 90% dos novos utilizadores cometem imediatamente",
        cta_text: "Ver o Meu Score de Confian\u00e7a",
        body_paragraphs: [
          "Acabaste de descarregar o Predictify. E est\u00e1s prestes a cometer o mesmo erro que toda a gente comete. Vais olhar para um jogo, ver a previs\u00e3o e pensar 'talvez'. Mas est\u00e1s a ignorar a \u00fanica coisa que torna a nossa IA mais inteligente que o teu instinto.",
          "A verdade: uma previs\u00e3o sem confian\u00e7a \u00e9 apenas um palpite. A nossa IA analisa milhares de dados \u2014 xG, posse de bola, forma defensiva, hist\u00f3rico de confrontos \u2014 mas a magia verdadeira \u00e9 o score de confian\u00e7a. \u00c9 a diferen\u00e7a entre 'o Benfica pode ganhar' e 'o Benfica ganha 78% das vezes nestas condi\u00e7\u00f5es exatas'.",
          "Abre a app agora. Vai diretamente a qualquer jogo da Liga Portugal deste fim de semana. Olha para a previs\u00e3o. Depois olha logo abaixo. V\u00eas aquela percentagem? Esse \u00e9 o teu score de confian\u00e7a. Em 30 segundos, deixas de adivinhar e come\u00e7as a saber.",
          "Carrega no bot\u00e3o. Abre o Predictify e encontra o score de confian\u00e7a no pr\u00f3ximo jogo. Muda tudo. P.S. Os utilizadores que verificam este score no primeiro dia t\u00eam 3x mais hip\u00f3teses de acertar na primeira semana.",
        ],
      },
      hi: {
        subject: "\u0935\u094b \u090f\u0915 \u0917\u0932\u0924\u0940 \u091c\u094b 90% \u0928\u090f \u092f\u0942\u091c\u0930\u094d\u0938 \u0924\u0941\u0930\u0902\u0924 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902",
        cta_text: "\u092e\u0941\u091d\u0947 Confidence Score \u0926\u093f\u0916\u093e\u0913",
        body_paragraphs: [
          "\u0906\u092a\u0928\u0947 \u0905\u092d\u0940 Predictify \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0915\u093f\u092f\u093e \u0939\u0948\u0964 \u0914\u0930 \u0906\u092a \u0935\u0939\u0940 \u0917\u0932\u0924\u0940 \u0915\u0930\u0928\u0947 \u0935\u093e\u0932\u0947 \u0939\u0948\u0902 \u091c\u094b \u0938\u092c \u0915\u0930\u0924\u0947 \u0939\u0948\u0902\u0964 \u0906\u092a \u090f\u0915 \u092e\u0948\u091a \u0926\u0947\u0916\u0947\u0902\u0917\u0947, \u092a\u094d\u0930\u0947\u0921\u093f\u0915\u094d\u0936\u0928 \u0926\u0947\u0916\u0947\u0902\u0917\u0947 \u0914\u0930 \u0938\u094b\u091a\u0947\u0902\u0917\u0947 '\u0936\u093e\u092f\u0926'\u0964 \u0932\u0947\u0915\u093f\u0928 \u0906\u092a \u0935\u094b \u090f\u0915 \u091a\u0940\u091c\u093c \u092e\u093f\u0938 \u0915\u0930 \u0930\u0939\u0947 \u0939\u0948\u0902 \u091c\u094b \u0939\u092e\u093e\u0930\u0940 AI \u0915\u094b \u0906\u092a\u0915\u0940 \u0905\u0902\u0924\u0930\u094d\u0926\u0943\u0937\u094d\u091f\u093f \u0938\u0947 \u0905\u0927\u093f\u0915 \u0938\u094d\u092e\u093e\u0930\u094d\u091f \u092c\u0928\u093e\u0924\u0940 \u0939\u0948\u0964",
          "\u0938\u091a\u094d\u091a\u093e\u0908 \u092f\u0939 \u0939\u0948: \u092c\u093f\u0928\u093e confidence \u0915\u0947 \u092a\u094d\u0930\u0947\u0921\u093f\u0915\u094d\u0936\u0928 \u092c\u0938 \u090f\u0915 \u0905\u0902\u0926\u093e\u091c\u093c\u093e \u0939\u0948\u0964 \u0939\u092e\u093e\u0930\u0940 AI \u0939\u091c\u093c\u093e\u0930\u094b\u0902 \u0921\u0947\u091f\u093e \u092a\u0949\u0907\u0902\u091f\u094d\u0938 \u0915\u093e \u0935\u093f\u0936\u094d\u0932\u0947\u0937\u0923 \u0915\u0930\u0924\u0940 \u0939\u0948 \u2014 xG, \u092a\u091c\u0947\u0936\u0928, \u0921\u093f\u092b\u0947\u0902\u0938\u093f\u0935 \u092b\u0949\u0930\u094d\u092e, \u0906\u092e\u0928\u0947-\u0938\u093e\u092e\u0928\u0947 \u0915\u093e \u0907\u0924\u093f\u0939\u093e\u0938 \u2014 \u0932\u0947\u0915\u093f\u0928 \u0905\u0938\u0932\u0940 \u091c\u093e\u0926\u0942 confidence score \u092e\u0947\u0902 \u0939\u0948\u0964",
          "\u0905\u092d\u0940 \u0905\u092a\u094d\u0932\u093f\u0915\u0947\u0936\u0928 \u0916\u094b\u0932\u0947\u0902\u0964 \u0907\u0938 \u0935\u0940\u0915\u0947\u0902\u0921 \u0915\u093f\u0938\u0940 \u092d\u0940 \u092e\u0948\u091a \u092a\u0930 \u091c\u093e\u090f\u0902\u0964 \u092a\u094d\u0930\u0947\u0921\u093f\u0915\u094d\u0936\u0928 \u0926\u0947\u0916\u0947\u0902\u0964 \u092b\u093f\u0930 \u0909\u0938\u0915\u0947 \u0928\u0940\u091a\u0947 \u0926\u0947\u0916\u0947\u0902\u0964 \u0935\u094b \u092a\u094d\u0930\u0924\u093f\u0936\u0924 \u0926\u093f\u0916 \u0930\u0939\u0940 \u0939\u0948? \u0935\u094b \u0906\u092a\u0915\u093e confidence score \u0939\u0948\u0964 30 \u0938\u0947\u0915\u0902\u0921 \u092e\u0947\u0902 \u0906\u092a \u0905\u0902\u0926\u093e\u091c\u093c\u093e \u0932\u0917\u093e\u0928\u093e \u092c\u0902\u0926 \u0915\u0930 \u0926\u0947\u0902\u0917\u0947\u0964",
          "\u092c\u091f\u0928 \u0926\u092c\u093e\u090f\u0902\u0964 Predictify \u0916\u094b\u0932\u0947\u0902 \u0914\u0930 \u0905\u092a\u0928\u0947 \u0905\u0917\u0932\u0947 \u092e\u0948\u091a \u0915\u093e confidence score \u0916\u094b\u091c\u0947\u0902\u0964 \u0938\u092c \u0915\u0941\u091b \u092c\u0926\u0932 \u091c\u093e\u0924\u093e \u0939\u0948\u0964 P.S. \u092a\u0939\u0932\u0947 \u0926\u093f\u0928 \u092f\u0939 \u0938\u094d\u0915\u094b\u0930 \u091a\u0947\u0915 \u0915\u0930\u0928\u0947 \u0935\u093e\u0932\u0947 \u092f\u0942\u091c\u0930\u094d\u0938 \u0915\u094b \u092a\u0939\u0932\u0947 \u0939\u092b\u094d\u0924\u0947 \u092e\u0947\u0902 \u0935\u0948\u0932\u094d\u092f\u0942 \u092c\u0947\u091f \u092e\u093f\u0932\u0928\u0947 \u0915\u0940 3 \u0917\u0941\u0928\u093e \u0905\u0927\u093f\u0915 \u0938\u0902\u092d\u093e\u0935\u0928\u093e \u0939\u0948\u0964",
        ],
      },
      id: {
        subject: "Kesalahan yang dilakukan 90% pengguna baru langsung",
        cta_text: "Tunjukkan Confidence Score",
        body_paragraphs: [
          "Kamu baru saja mengunduh Predictify. Dan kamu akan melakukan kesalahan yang sama seperti orang lain. Kamu akan melihat pertandingan, melihat prediksi, dan berpikir 'mungkin'. Tapi kamu melewatkan satu hal yang membuat AI kami lebih pintar dari instingmu.",
          "Kenyataannya: prediksi tanpa confidence hanyalah tebakan. AI kami menganalisis ribuan data poin \u2014 xG, penguasaan bola, form pertahanan, rekor pertemuan \u2014 tapi keajaiban sesungguhnya ada di confidence score. Ini bedanya antara 'Liverpool mungkin menang' dan 'Liverpool menang 78% dengan kondisi persis seperti ini'.",
          "Buka aplikasinya sekarang. Langsung ke pertandingan apa saja akhir pekan ini. Lihat prediksinya. Lalu lihat tepat di bawahnya. Lihat persentase itu? Itu confidence score-mu. Dalam 30 detik, kamu berhenti menebak dan mulai tahu.",
          "Ketuk tombolnya. Buka Predictify dan temukan confidence score untuk pertandingan berikutnya. Ini mengubah segalanya. P.S. Pengguna yang mengecek score ini di hari pertama punya kemungkinan 3x lebih besar menemukan peluang bagus di minggu pertama.",
        ],
      },
      nl: {
        subject: "De ene fout die 90% van nieuwe gebruikers meteen maakt",
        cta_text: "Toon Mijn Confidence Score",
        body_paragraphs: [
          "Je hebt net Predictify gedownload. En je staat op het punt dezelfde fout te maken als iedereen. Je gaat naar een wedstrijd kijken, de voorspelling zien en denken 'misschien'. Maar je mist het enige dat onze AI slimmer maakt dan je onderbuikgevoel.",
          "De waarheid: een voorspelling zonder vertrouwen is slechts een gok. Onze AI analyseert duizenden datapunten \u2014 xG, balbezit, defensieve vorm, onderlinge geschiedenis \u2014 maar de echte magie zit in de confidence score. Het verschil tussen 'Liverpool zou kunnen winnen' en 'Liverpool wint 78% van de tijd onder precies deze omstandigheden'.",
          "Open de app. Nu meteen. Ga direct naar een Eredivisie-wedstrijd dit weekend. Kijk naar de voorspelling. Kijk dan er direct onder. Zie je dat percentage? Dat is je confidence score. In 30 seconden stop je met gokken en begin je te weten.",
          "Druk op de knop. Open Predictify en vind de confidence score voor je volgende wedstrijd. Het verandert alles. P.S. Gebruikers die deze score op dag \u00e9\u00e9n checken, vinden 3x vaker een value bet in hun eerste week.",
        ],
      },
      pl: {
        subject: "Jeden b\u0142\u0105d, kt\u00f3ry 90% nowych u\u017cytkownik\u00f3w pope\u0142nia od razu",
        cta_text: "Poka\u017c Mi Confidence Score",
        body_paragraphs: [
          "W\u0142a\u015bnie pobra\u0142e\u015b Predictify. I zamierzasz pope\u0142ni\u0107 ten sam b\u0142\u0105d co wszyscy. Spojrzysz na mecz, zobaczysz prognoz\u0119 i pomy\u015blisz 'mo\u017ce'. Ale umyka ci jedna rzecz, kt\u00f3ra sprawia, \u017ce nasza AI jest m\u0105drzejsza od twojego przeczucia.",
          "Prawda jest taka: prognoza bez pewno\u015bci to tylko zgadywanie. Nasza AI analizuje tysi\u0105ce punkt\u00f3w danych \u2014 xG, posiadanie pi\u0142ki, form\u0119 defensywn\u0105, histori\u0119 bezpo\u015brednich spotka\u0144 \u2014 ale prawdziwa magia to confidence score. R\u00f3\u017cnica mi\u0119dzy 'Liverpool mo\u017ce wygra\u0107' a 'Liverpool wygrywa w 78% przypadk\u00f3w w dok\u0142adnie tych warunkach'.",
          "Otw\u00f3rz aplikacj\u0119. Teraz. Id\u017a prosto do dowolnego meczu Ekstraklasy w ten weekend. Sp\u00f3jrz na prognoz\u0119. Potem sp\u00f3jrz tu\u017c pod ni\u0105. Widzisz ten procent? To tw\u00f3j confidence score. W 30 sekund przestajesz zgadywa\u0107 i zaczynasz wiedzie\u0107.",
          "Kliknij przycisk. Otw\u00f3rz Predictify i znajd\u017a confidence score na nast\u0119pny mecz. To zmienia wszystko. P.S. U\u017cytkownicy, kt\u00f3rzy sprawdzaj\u0105 ten wynik pierwszego dnia, maj\u0105 3x wi\u0119ksze szanse na znalezienie warto\u015bciowego zak\u0142adu w pierwszym tygodniu.",
        ],
      },
      ja: {
        subject: "\u65b0\u898f\u30e6\u30fc\u30b6\u30fc\u306e90%\u304c\u3059\u3050\u306b\u72af\u3059\u305f\u3063\u305f\u4e00\u3064\u306e\u30df\u30b9",
        cta_text: "Confidence Score\u3092\u898b\u308b",
        body_paragraphs: [
          "Predictify\u3092\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u3057\u305f\u3070\u304b\u308a\u3067\u3059\u306d\u3002\u305d\u3057\u3066\u4ed6\u306e\u307f\u3093\u306a\u3068\u540c\u3058\u30df\u30b9\u3092\u3057\u3088\u3046\u3068\u3057\u3066\u3044\u307e\u3059\u3002\u8a66\u5408\u3092\u898b\u3066\u3001\u4e88\u6e2c\u3092\u898b\u3066\u3001\u300c\u305f\u3076\u3093\u300d\u3068\u601d\u3046\u3067\u3057\u3087\u3046\u3002\u3067\u3082\u3001\u79c1\u305f\u3061\u306eAI\u3092\u3042\u306a\u305f\u306e\u52d8\u3088\u308a\u8ce2\u304f\u3059\u308b\u305f\u3063\u305f\u4e00\u3064\u306e\u3053\u3068\u3092\u898b\u843d\u3068\u3057\u3066\u3044\u307e\u3059\u3002",
          "\u771f\u5b9f\uff1a\u78ba\u4fe1\u5ea6\u306e\u306a\u3044\u4e88\u6e2c\u306f\u305f\u3060\u306e\u63a8\u6e2c\u3067\u3059\u3002\u79c1\u305f\u3061\u306eAI\u306f\u6570\u5343\u306e\u30c7\u30fc\u30bf\u30dd\u30a4\u30f3\u30c8\u3092\u5206\u6790\u3057\u307e\u3059\u2014xG\u3001\u30dc\u30fc\u30eb\u4fdd\u6301\u7387\u3001\u5b88\u5099\u306e\u5f62\u3001\u76f4\u63a5\u5bfe\u6c7a\u306e\u6b74\u53f2\u2014\u3067\u3082\u672c\u5f53\u306e\u9b54\u6cd5\u306fconfidence score\u306b\u3042\u308a\u307e\u3059\u3002\u300c\u30ea\u30d0\u30d7\u30fc\u30eb\u304c\u52dd\u3064\u304b\u3082\u300d\u3068\u300c\u3053\u306e\u6761\u4ef6\u3067\u30ea\u30d0\u30d7\u30fc\u30eb\u304c78%\u306e\u78ba\u7387\u3067\u52dd\u3064\u300d\u306e\u9055\u3044\u3067\u3059\u3002",
          "\u30a2\u30d7\u30ea\u3092\u958b\u3044\u3066\u304f\u3060\u3055\u3044\u3002\u4eca\u3059\u3050\u3002\u4eca\u9031\u672b\u306e\u8a66\u5408\u306b\u76f4\u63a5\u884c\u3063\u3066\u304f\u3060\u3055\u3044\u3002\u4e88\u6e2c\u3092\u898b\u3066\u304f\u3060\u3055\u3044\u3002\u305d\u3057\u3066\u305d\u306e\u771f\u4e0b\u3092\u898b\u3066\u304f\u3060\u3055\u3044\u3002\u305d\u306e\u30d1\u30fc\u30bb\u30f3\u30c6\u30fc\u30b8\u304c\u898b\u3048\u307e\u3059\u304b\uff1f\u305d\u308c\u304c\u3042\u306a\u305f\u306econfidence score\u3067\u3059\u300230\u79d2\u3067\u3001\u63a8\u6e2c\u3092\u3084\u3081\u3066\u78ba\u4fe1\u306b\u5909\u308f\u308a\u307e\u3059\u3002",
          "\u30dc\u30bf\u30f3\u3092\u30bf\u30c3\u30d7\u3057\u3066\u304f\u3060\u3055\u3044\u3002Predictify\u3092\u958b\u3044\u3066\u6b21\u306e\u8a66\u5408\u306econfidence score\u3092\u898b\u3064\u3051\u3066\u304f\u3060\u3055\u3044\u3002\u3059\u3079\u3066\u304c\u5909\u308f\u308a\u307e\u3059\u3002P.S. \u521d\u65e5\u306b\u3053\u306e\u30b9\u30b3\u30a2\u3092\u30c1\u30a7\u30c3\u30af\u3057\u305f\u30e6\u30fc\u30b6\u30fc\u306f\u3001\u6700\u521d\u306e\u9031\u306b\u30d0\u30ea\u30e5\u30fc\u30d9\u30c3\u30c8\u3092\u898b\u3064\u3051\u308b\u53ef\u80fd\u6027\u304c3\u500d\u9ad8\u304f\u306a\u308a\u307e\u3059\u3002",
        ],
      },
    },
  },

  predictify_nba: {
    name: "Predictify NBA",
    multilingual: true,
    appStoreUrl: "",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.predictify.nba.prediction",
    emails: {
      en: {
        subject: "Your first NBA prediction is ready — here's the edge",
        cta_text: "Open My First Prediction",
        body_paragraphs: [
          "Tonight the NBA tips off and everyone's got a take. Your friends, the TV analysts, the group chat. But you? You'll already know what the data says. Predictify just crunched thousands of variables for every game on tonight's slate — pace, offensive and defensive ratings, rest days, injuries, head-to-head — and your first prediction is ready.",
          "Here's what makes this different from every other app: you don't just see who wins. You see HOW confident the AI is. That confidence score is the secret. It's the difference between 'the Celtics might cover' and 'the Celtics win 78% of the time under these exact conditions.' One number, built from more data than you could process in a whole season. That's not a hot take — it's an edge.",
          "Open the app right now. Tap any game on the home screen. Look at the prediction and the confidence score right below it. Then lock in your first pick to start your streak. It takes 30 seconds. When the ball goes up, you'll know something the rest of the group chat doesn't. That feeling is why people open this app every single night.",
          "Join communities of fans who break down picks daily and vote on the Pick of the Night. P.S. Users who make a prediction on day one are 4x more likely to build a winning streak. Don't just watch the NBA — know the NBA. 🏀",
        ],
      },
      ar: {
        subject: "أول توقع لك في الدوري الأمريكي جاهز — هذا هو الفرق",
        cta_text: "افتح أول توقع لي",
        body_paragraphs: [
          "الليلة تنطلق مباريات الدوري الأمريكي لكرة السلة، والجميع لديه رأي. أصدقاؤك، المحللون، مجموعة الدردشة. لكنك أنت؟ ستعرف ما تقوله البيانات مسبقًا. حلّل Predictify آلاف المتغيرات لكل مباراة الليلة — الإيقاع، تقييمات الهجوم والدفاع، أيام الراحة، الإصابات، المواجهات السابقة — وأول توقع لك جاهز.",
          "ما يجعل هذا مختلفًا عن أي تطبيق آخر: لا ترى فقط من سيفوز. بل ترى مدى ثقة الذكاء الاصطناعي. درجة الثقة هي السر. إنها الفرق بين 'قد يفوز السيلتكس' و'يفوز السيلتكس بنسبة 78% في هذه الظروف بالضبط'. رقم واحد، مبني على بيانات أكثر مما يمكنك معالجته في موسم كامل. هذا ليس تخمينًا — إنه أفضلية.",
          "افتح التطبيق الآن. اضغط على أي مباراة في الصفحة الرئيسية. انظر إلى التوقع ودرجة الثقة أسفله مباشرة. ثم أكّد أول توقع لك لتبدأ سلسلة انتصاراتك. يستغرق 30 ثانية. عندما تبدأ المباراة، ستعرف شيئًا لا تعرفه بقية المجموعة. هذا الشعور هو سبب فتح الناس لهذا التطبيق كل ليلة.",
          "انضم إلى مجتمعات من المعجبين الذين يحللون التوقعات يوميًا ويصوتون على توقع الليلة. ملاحظة: المستخدمون الذين يقومون بتوقع في اليوم الأول أكثر عرضة بـ 4 مرات لبناء سلسلة انتصارات. لا تكتفِ بمشاهدة الدوري — اعرفه. 🏀",
        ],
      },
      es: {
        subject: "Tu primera predicción NBA está lista — esta es tu ventaja",
        cta_text: "Abrir Mi Primera Predicción",
        body_paragraphs: [
          "Esta noche arranca la NBA y todos tienen una opinión. Tus amigos, los analistas de la tele, el grupo de chat. ¿Pero tú? Tú ya sabrás lo que dicen los datos. Predictify acaba de analizar miles de variables para cada partido de hoy — ritmo, ratings ofensivos y defensivos, días de descanso, lesiones, historial directo — y tu primera predicción está lista.",
          "Esto es lo que lo hace diferente de cualquier otra app: no solo ves quién gana. Ves CUÁN seguro está la IA. Ese score de confianza es el secreto. Es la diferencia entre 'los Celtics podrían cubrir' y 'los Celtics ganan el 78% de las veces en estas condiciones exactas'. Un número, construido con más datos de los que podrías procesar en toda una temporada. Eso no es un palpito — es una ventaja.",
          "Abre la app ahora mismo. Toca cualquier partido en la pantalla de inicio. Mira la predicción y el score de confianza justo debajo. Luego confirma tu primera predicción para iniciar tu racha. Tarda 30 segundos. Cuando salte el balón, sabrás algo que el resto del grupo no sabe. Esa sensación es por lo que la gente abre esta app cada noche.",
          "Únete a comunidades de fans que analizan predicciones a diario y votan por la Predicción de la Noche. P.D. Los usuarios que hacen una predicción el primer día tienen 4 veces más probabilidades de armar una racha ganadora. No solo veas la NBA — conoce la NBA. 🏀",
        ],
      },
      fr: {
        subject: "Ta première prédiction NBA est prête — voici ton avantage",
        cta_text: "Ouvrir Ma Première Prédiction",
        body_paragraphs: [
          "Ce soir la NBA reprend et tout le monde a son avis. Tes potes, les analystes à la télé, le groupe de discussion. Mais toi ? Tu sauras déjà ce que disent les données. Predictify vient d'analyser des milliers de variables pour chaque match de ce soir — le rythme, les ratings offensifs et défensifs, les jours de repos, les blessures, les confrontations directes — et ta première prédiction est prête.",
          "Voilà ce qui change tout par rapport aux autres apps : tu ne vois pas seulement qui gagne. Tu vois à quel point l'IA est confiante. Ce score de confiance, c'est le secret. C'est la différence entre 'les Celtics pourraient passer' et 'les Celtics gagnent 78% du temps dans ces conditions précises'. Un seul chiffre, bâti sur plus de données que tu ne pourrais en traiter en une saison entière. Ça, ce n'est pas un avis — c'est un avantage.",
          "Ouvre l'appli maintenant. Touche n'importe quel match sur l'écran d'accueil. Regarde la prédiction et le score de confiance juste en dessous. Puis valide ta première prédiction pour lancer ta série. Ça prend 30 secondes. Au coup d'envoi, tu sauras quelque chose que le reste du groupe ignore. C'est ce sentiment qui pousse les gens à ouvrir cette appli chaque soir.",
          "Rejoins des communautés de fans qui décortiquent les pronostics chaque jour et votent pour le Pronostic du Soir. P.S. Les utilisateurs qui font une prédiction dès le premier jour ont 4 fois plus de chances de bâtir une série gagnante. Ne te contente pas de regarder la NBA — comprends la NBA. 🏀",
        ],
      },
      pt: {
        subject: "Sua primeira previsão da NBA está pronta — essa é a sua vantagem",
        cta_text: "Abrir Minha Primeira Previsão",
        body_paragraphs: [
          "Hoje à noite a NBA começa e todo mundo tem uma opinião. Seus amigos, os analistas da TV, o grupo do zap. Mas você? Você já vai saber o que os dados dizem. O Predictify acabou de analisar milhares de variáveis para cada jogo de hoje — ritmo, ratings ofensivos e defensivos, dias de descanso, lesões, histórico de confrontos — e sua primeira previsão está pronta.",
          "O que torna isso diferente de qualquer outro app: você não vê só quem ganha. Você vê O QUÃO confiante a IA está. Esse score de confiança é o segredo. É a diferença entre 'os Celtics podem cobrir' e 'os Celtics vencem 78% das vezes nessas condições exatas'. Um número, construído com mais dados do que você processaria numa temporada inteira. Isso não é achismo — é uma vantagem.",
          "Abra o app agora. Toque em qualquer jogo na tela inicial. Olhe a previsão e o score de confiança logo abaixo. Depois confirme sua primeira previsão para começar sua sequência. Leva 30 segundos. Quando a bola subir, você vai saber algo que o resto do grupo não sabe. Essa sensação é o motivo de as pessoas abrirem esse app toda noite.",
          "Entre em comunidades de fãs que analisam palpites diariamente e votam no Palpite da Noite. P.D. Usuários que fazem uma previsão no primeiro dia têm 4x mais chances de construir uma sequência vencedora. Não só assista à NBA — entenda a NBA. 🏀",
        ],
      },
      de: {
        subject: "Deine erste NBA-Vorhersage ist bereit — das ist dein Vorteil",
        cta_text: "Meine erste Vorhersage öffnen",
        body_paragraphs: [
          "Heute Abend startet die NBA und jeder hat eine Meinung. Deine Freunde, die TV-Analysten, der Gruppenchat. Aber du? Du weißt schon, was die Daten sagen. Predictify hat gerade tausende Variablen für jedes Spiel heute Abend ausgewertet — Tempo, Offensiv- und Defensiv-Ratings, Ruhetage, Verletzungen, direkte Duelle — und deine erste Vorhersage ist bereit.",
          "Das macht es anders als jede andere App: Du siehst nicht nur, wer gewinnt. Du siehst, WIE sicher sich die KI ist. Dieser Confidence Score ist das Geheimnis. Es ist der Unterschied zwischen 'die Celtics könnten covern' und 'die Celtics gewinnen zu 78% unter genau diesen Bedingungen'. Eine Zahl, gebaut aus mehr Daten, als du in einer ganzen Saison verarbeiten könntest. Das ist keine Meinung — das ist ein Vorteil.",
          "Öffne die App jetzt. Tippe auf ein beliebiges Spiel auf dem Startbildschirm. Schau dir die Vorhersage und den Confidence Score direkt darunter an. Dann bestätige deine erste Vorhersage, um deine Serie zu starten. Es dauert 30 Sekunden. Beim Tip-off weißt du etwas, das der Rest des Gruppenchats nicht weiß. Dieses Gefühl ist der Grund, warum Leute diese App jeden Abend öffnen.",
          "Tritt Communities von Fans bei, die täglich Tipps analysieren und für den Tipp des Abends abstimmen. P.S. Nutzer, die am ersten Tag eine Vorhersage machen, bauen 4x häufiger eine Siegesserie auf. Schau nicht nur NBA — versteh die NBA. 🏀",
        ],
      },
      tr: {
        subject: "İlk NBA tahminin hazır — işte senin avantajın",
        cta_text: "İlk Tahminimi Aç",
        body_paragraphs: [
          "Bu gece NBA başlıyor ve herkesin bir fikri var. Arkadaşların, TV yorumcuları, grup sohbeti. Ama sen? Sen verilerin ne dediğini önceden bileceksin. Predictify, bu geceki her maç için binlerce değişkeni az önce analiz etti — tempo, hücum ve savunma reytingleri, dinlenme günleri, sakatlıklar, karşılaşma geçmişi — ve ilk tahminin hazır.",
          "Bunu diğer tüm uygulamalardan farklı kılan şey: sadece kimin kazanacağını görmezsin. Yapay zekanın NE KADAR emin olduğunu görürsün. O güven skoru sırdır. 'Celtics farklı kazanabilir' ile 'Celtics tam bu koşullarda %78 kazanır' arasındaki farktır. Tek bir sayı, bir sezon boyunca işleyemeyeceğin kadar veriden inşa edilmiş. Bu bir yorum değil — bir avantaj.",
          "Uygulamayı şimdi aç. Ana ekranda herhangi bir maça dokun. Tahmine ve hemen altındaki güven skoruna bak. Sonra serini başlatmak için ilk tahminini onayla. 30 saniye sürer. Maç başladığında grubun geri kalanının bilmediği bir şey bileceksin. İşte bu his, insanların bu uygulamayı her gece açmasının sebebi.",
          "Tahminleri her gün analiz eden ve Gecenin Tahmini'ne oy veren hayran topluluklarına katıl. P.S. İlk gün tahmin yapan kullanıcıların kazanma serisi oluşturma olasılığı 4 kat daha fazla. Sadece NBA izleme — NBA'i bil. 🏀",
        ],
      },
      it: {
        subject: "La tua prima previsione NBA è pronta — ecco il tuo vantaggio",
        cta_text: "Apri La Mia Prima Previsione",
        body_paragraphs: [
          "Stasera inizia l'NBA e tutti hanno un'opinione. I tuoi amici, gli analisti in TV, la chat di gruppo. Ma tu? Tu saprai già cosa dicono i dati. Predictify ha appena elaborato migliaia di variabili per ogni partita di stasera — ritmo, rating offensivi e difensivi, giorni di riposo, infortuni, precedenti — e la tua prima previsione è pronta.",
          "Ecco cosa lo rende diverso da ogni altra app: non vedi solo chi vince. Vedi QUANTO è sicura l'IA. Quel confidence score è il segreto. È la differenza tra 'i Celtics potrebbero coprire' e 'i Celtics vincono il 78% delle volte in queste esatte condizioni'. Un numero, costruito con più dati di quanti potresti elaborarne in un'intera stagione. Non è un'opinione — è un vantaggio.",
          "Apri l'app adesso. Tocca una qualsiasi partita nella schermata principale. Guarda la previsione e il confidence score subito sotto. Poi conferma la tua prima previsione per iniziare la tua striscia. Ci vogliono 30 secondi. Quando si alza la palla a due, saprai qualcosa che il resto della chat non sa. È questa sensazione che spinge la gente ad aprire l'app ogni sera.",
          "Unisciti a community di tifosi che analizzano i pronostici ogni giorno e votano il Pronostico della Sera. P.S. Gli utenti che fanno una previsione il primo giorno hanno 4 volte più probabilità di costruire una striscia vincente. Non limitarti a guardare l'NBA — conosci l'NBA. 🏀",
        ],
      },
      pp: {
        subject: "A tua primeira previsão da NBA está pronta — esta é a tua vantagem",
        cta_text: "Abrir A Minha Primeira Previsão",
        body_paragraphs: [
          "Hoje à noite a NBA arranca e toda a gente tem uma opinião. Os teus amigos, os analistas da TV, o grupo de conversa. Mas tu? Tu já vais saber o que dizem os dados. O Predictify acabou de analisar milhares de variáveis para cada jogo desta noite — ritmo, ratings ofensivos e defensivos, dias de descanso, lesões, histórico de confrontos — e a tua primeira previsão está pronta.",
          "O que torna isto diferente de qualquer outra app: não vês apenas quem ganha. Vês QUÃO confiante está a IA. Esse score de confiança é o segredo. É a diferença entre 'os Celtics podem cobrir' e 'os Celtics vencem 78% das vezes nestas condições exatas'. Um número, construído com mais dados do que conseguirias processar numa época inteira. Isto não é um palpite — é uma vantagem.",
          "Abre a app agora. Toca em qualquer jogo no ecrã inicial. Olha para a previsão e para o score de confiança mesmo por baixo. Depois confirma a tua primeira previsão para começar a tua série. Demora 30 segundos. Quando a bola subir, vais saber algo que o resto do grupo não sabe. É essa sensação que faz as pessoas abrirem esta app todas as noites.",
          "Junta-te a comunidades de fãs que analisam palpites diariamente e votam no Palpite da Noite. P.D. Os utilizadores que fazem uma previsão no primeiro dia têm 4x mais hipóteses de construir uma série vencedora. Não te limites a ver a NBA — conhece a NBA. 🏀",
        ],
      },
      hi: {
        subject: "आपकी पहली NBA भविष्यवाणी तैयार है — यह रहा आपका एज",
        cta_text: "मेरी पहली भविष्यवाणी खोलें",
        body_paragraphs: [
          "आज रात NBA शुरू हो रही है और हर किसी की अपनी राय है। आपके दोस्त, टीवी विश्लेषक, ग्रुप चैट। लेकिन आप? आपको पहले से पता होगा कि डेटा क्या कहता है। Predictify ने आज रात के हर गेम के लिए हजारों वेरिएबल का विश्लेषण किया — पेस, ऑफेंसिव और डिफेंसिव रेटिंग, आराम के दिन, चोटें, आमने-सामने का इतिहास — और आपकी पहली भविष्यवाणी तैयार है।",
          "यह हर दूसरे ऐप से क्यों अलग है: आप सिर्फ यह नहीं देखते कि कौन जीतेगा। आप देखते हैं कि AI कितना आश्वस्त है। वह confidence score ही राज है। यह 'सेल्टिक्स शायद जीतें' और 'इन हालात में सेल्टिक्स 78% बार जीतते हैं' के बीच का फर्क है। एक नंबर, जितना डेटा आप पूरे सीज़न में प्रोसेस नहीं कर सकते। यह अनुमान नहीं — यह एक एज है।",
          "अभी ऐप खोलें। होम स्क्रीन पर किसी भी गेम पर टैप करें। भविष्यवाणी और उसके ठीक नीचे confidence score देखें। फिर अपनी स्ट्रीक शुरू करने के लिए अपनी पहली भविष्यवाणी कन्फ़र्म करें। 30 सेकंड लगते हैं। जब गेम शुरू होगा, आपको कुछ ऐसा पता होगा जो बाकी ग्रुप को नहीं। यही एहसास लोगों को हर रात यह ऐप खोलने पर मजबूर करता है।",
          "उन प्रशंसकों के समुदायों से जुड़ें जो रोज़ पिक्स का विश्लेषण करते हैं और 'Pick of the Night' के लिए वोट करते हैं। P.S. पहले दिन भविष्यवाणी करने वाले यूजर्स की विनिंग स्ट्रीक बनाने की संभावना 4 गुना अधिक है। सिर्फ NBA देखें नहीं — NBA को जानें। 🏀",
        ],
      },
      id: {
        subject: "Prediksi NBA pertamamu sudah siap — ini keunggulanmu",
        cta_text: "Buka Prediksi Pertamaku",
        body_paragraphs: [
          "Malam ini NBA dimulai dan semua orang punya pendapat. Teman-temanmu, analis TV, grup chat. Tapi kamu? Kamu sudah tahu apa kata data. Predictify baru saja mengolah ribuan variabel untuk setiap pertandingan malam ini — tempo, rating ofensif dan defensif, hari istirahat, cedera, rekor pertemuan — dan prediksi pertamamu sudah siap.",
          "Inilah yang membuatnya beda dari aplikasi lain: kamu tidak cuma melihat siapa yang menang. Kamu melihat SEBERAPA yakin AI-nya. Confidence score itulah rahasianya. Itu bedanya antara 'Celtics mungkin menang' dan 'Celtics menang 78% dengan kondisi persis seperti ini'. Satu angka, dibangun dari lebih banyak data daripada yang bisa kamu proses dalam satu musim penuh. Itu bukan tebakan — itu keunggulan.",
          "Buka aplikasinya sekarang. Ketuk pertandingan mana saja di layar utama. Lihat prediksi dan confidence score tepat di bawahnya. Lalu kunci prediksi pertamamu untuk memulai streak-mu. Cuma butuh 30 detik. Saat bola dilempar, kamu akan tahu sesuatu yang tidak diketahui anggota grup lain. Perasaan itulah alasan orang membuka aplikasi ini setiap malam.",
          "Gabung dengan komunitas penggemar yang membahas prediksi setiap hari dan memilih Prediksi Malam Ini. P.S. Pengguna yang membuat prediksi di hari pertama 4x lebih mungkin membangun streak kemenangan. Jangan cuma nonton NBA — pahami NBA. 🏀",
        ],
      },
      nl: {
        subject: "Je eerste NBA-voorspelling staat klaar — dit is je voordeel",
        cta_text: "Mijn Eerste Voorspelling Openen",
        body_paragraphs: [
          "Vanavond begint de NBA en iedereen heeft een mening. Je vrienden, de analisten op tv, de groepsapp. Maar jij? Jij weet al wat de data zeggen. Predictify heeft net duizenden variabelen geanalyseerd voor elke wedstrijd van vanavond — tempo, aanvallende en verdedigende ratings, rustdagen, blessures, onderlinge duels — en je eerste voorspelling staat klaar.",
          "Dit is wat het anders maakt dan elke andere app: je ziet niet alleen wie wint. Je ziet HOE zeker de AI is. Die confidence score is het geheim. Het is het verschil tussen 'de Celtics dekken misschien' en 'de Celtics winnen 78% van de tijd onder precies deze omstandigheden'. Één getal, gebouwd op meer data dan je in een heel seizoen kunt verwerken. Dat is geen mening — dat is een voordeel.",
          "Open de app nu meteen. Tik op een willekeurige wedstrijd op het startscherm. Bekijk de voorspelling en de confidence score er direct onder. Bevestig dan je eerste voorspelling om je reeks te starten. Het kost 30 seconden. Bij de tip-off weet jij iets wat de rest van de groepsapp niet weet. Dat gevoel is waarom mensen deze app elke avond openen.",
          "Word lid van community's van fans die dagelijks voorspellingen bespreken en stemmen op de Voorspelling van de Avond. P.S. Gebruikers die op dag één een voorspelling doen, bouwen 4x vaker een winnende reeks op. Kijk niet alleen NBA — ken de NBA. 🏀",
        ],
      },
      pl: {
        subject: "Twoja pierwsza prognoza NBA jest gotowa — oto twoja przewaga",
        cta_text: "Otwórz Moją Pierwszą Prognozę",
        body_paragraphs: [
          "Dziś wieczorem rusza NBA i każdy ma swoje zdanie. Twoi znajomi, analitycy w telewizji, grupa na czacie. Ale ty? Ty już będziesz wiedzieć, co mówią dane. Predictify właśnie przeanalizował tysiące zmiennych dla każdego dzisiejszego meczu — tempo, oceny ofensywne i defensywne, dni odpoczynku, kontuzje, historia bezpośrednich spotkań — i twoja pierwsza prognoza jest gotowa.",
          "Oto co odróżnia to od każdej innej aplikacji: nie widzisz tylko, kto wygra. Widzisz, JAK pewna jest AI. Ten confidence score to sekret. To różnica między 'Celtics mogą pokryć' a 'Celtics wygrywają w 78% przypadków w dokładnie tych warunkach'. Jedna liczba, zbudowana z większej ilości danych, niż przetworzyłbyś przez cały sezon. To nie opinia — to przewaga.",
          "Otwórz aplikację teraz. Dotknij dowolnego meczu na ekranie głównym. Spójrz na prognozę i confidence score tuż pod nią. Potem potwierdź swoją pierwszą prognozę, by rozpocząć swoją serię. Zajmuje to 30 sekund. Gdy piłka pójdzie w górę, będziesz wiedzieć coś, czego nie wie reszta grupy. To uczucie sprawia, że ludzie otwierają tę aplikację każdego wieczoru.",
          "Dołącz do społeczności fanów, którzy codziennie analizują typy i głosują na Typ Wieczoru. P.S. Użytkownicy, którzy typują pierwszego dnia, 4x częściej budują zwycięską serię. Nie tylko oglądaj NBA — poznaj NBA. 🏀",
        ],
      },
      ja: {
        subject: "最初のNBA予測が準備できました — これがあなたのエッジです",
        cta_text: "最初の予測を開く",
        body_paragraphs: [
          "今夜NBAが始まり、みんなが意見を言います。友達、テレビのアナリスト、グループチャット。でもあなたは？すでにデータが何を語るかを知っているでしょう。Predictifyは今夜の全試合について何千もの変数を分析したばかり—ペース、オフェンスとディフェンスのレーティング、休養日、怪我、直接対決の成績—そしてあなたの最初の予測が準備できています。",
          "他のどのアプリとも違う点：ただ勝者を見るだけではありません。AIがどれほど確信しているかを見れます。そのconfidence scoreが秘密です。「セルティックスがカバーするかも」と「この条件でセルティックスが78%勝つ」の違いです。1つの数字、シーズン中かかっても処理しきれないほどのデータから作られています。これは意見ではなく—エッジです。",
          "今すぐアプリを開いてください。ホーム画面で任意の試合をタップ。予測と、そのすぐ下のconfidence scoreを見てください。そして最初の予測を確定して連勝をスタート。わずか30秒です。ティップオフの瞬間、グループの誰も知らないことをあなたは知っています。その感覚が、人々が毎晩このアプリを開く理由です。",
          "毎日予測を語り合い、「今夜の予測」に投票するファンのコミュニティに参加しましょう。P.S. 初日に予測したユーザーは、連勝を築く可能性が4倍高くなります。NBAをただ見るだけじゃなく—NBAを知ろう。🏀",
        ],
      },
    },
  },
  thesis_generator: {
    name: "Thesis Generator",
    multilingual: true,
    appStoreUrl: "https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.thesis.generator.ai",
    emails: {
      en: {
        subject: "The one mistake 90% of new users make",
        cta_text: "Generate Your First Thesis Now",
        body_paragraphs: [
          "I watched a student last week spend 8 hours staring at a blank page. Panic sweats, 3am, deadline in 6 hours. Sound familiar? I built Thesis Generator to stop that exact moment from ever happening again.",
          "The secret is to stop trying to write the whole paper first. That's the mistake. The fastest win is to get a solid, arguable thesis statement down IMMEDIATELY. It gives your entire essay a backbone in 30 seconds. Everything else\u2014the outline, the citations, the humanized text\u2014flows from that one core idea.",
          "Open the app. Right now. Don't overthink it. Tap 'Generate Thesis,' type your topic or paste your assignment prompt, and hit go. In 30 seconds, you'll have 3-5 viable thesis options. Pick one. Just like that, the blank page panic is gone. You're already ahead of 90% of your class.",
          "Your first thesis is waiting. Open Thesis Generator and generate your first statement before you even finish this email. The clock is ticking, but now you have the hack. P.S. The first one who uses the 'Humanize' feature on their generated thesis bypasses AI detection 99% of the time. It's your secret weapon.",
        ],
      },
      ar: {
        subject: "\u0627\u0644\u062e\u0637\u0623 \u0627\u0644\u0648\u0627\u062d\u062f \u0627\u0644\u0630\u064a \u064a\u0631\u062a\u0643\u0628\u0647 90% \u0645\u0646 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u064a\u0646 \u0627\u0644\u062c\u062f\u062f",
        cta_text: "\u0623\u0646\u0634\u0626 \u0623\u0637\u0631\u0648\u062d\u062a\u0643 \u0627\u0644\u0623\u0648\u0644\u0649 \u0627\u0644\u0622\u0646",
        body_paragraphs: [
          "\u0634\u0627\u0647\u062f\u062a \u0637\u0627\u0644\u0628\u064b\u0627 \u0627\u0644\u0623\u0633\u0628\u0648\u0639 \u0627\u0644\u0645\u0627\u0636\u064a \u064a\u0642\u0636\u064a 8 \u0633\u0627\u0639\u0627\u062a \u064a\u062d\u062f\u0651\u0642 \u0641\u064a \u0635\u0641\u062d\u0629 \u0641\u0627\u0631\u063a\u0629. \u062a\u0639\u0631\u0651\u0642 \u0645\u0646 \u0627\u0644\u0630\u0639\u0631\u060c \u0627\u0644\u0633\u0627\u0639\u0629 \u0627\u0644\u062b\u0627\u0644\u062b\u0629 \u0641\u062c\u0631\u064b\u0627\u060c \u0648\u0627\u0644\u0645\u0648\u0639\u062f \u0627\u0644\u0646\u0647\u0627\u0626\u064a \u0628\u0639\u062f 6 \u0633\u0627\u0639\u0627\u062a. \u0645\u0623\u0644\u0648\u0641\u061f \u0628\u0646\u064a\u062a Thesis Generator \u0644\u0625\u064a\u0642\u0627\u0641 \u062a\u0644\u0643 \u0627\u0644\u0644\u062d\u0638\u0629 \u0628\u0627\u0644\u0636\u0628\u0637 \u0645\u0646 \u0627\u0644\u062d\u062f\u0648\u062b \u0645\u062c\u062f\u062f\u064b\u0627.",
          "\u0627\u0644\u0633\u0631 \u0647\u0648 \u0627\u0644\u062a\u0648\u0642\u0641 \u0639\u0646 \u0645\u062d\u0627\u0648\u0644\u0629 \u0643\u062a\u0627\u0628\u0629 \u0627\u0644\u0648\u0631\u0642\u0629 \u0628\u0623\u0643\u0645\u0644\u0647\u0627 \u0623\u0648\u0644\u064b\u0627. \u0647\u0630\u0627 \u0647\u0648 \u0627\u0644\u062e\u0637\u0623. \u0623\u0633\u0631\u0639 \u0646\u0635\u0631 \u0647\u0648 \u0627\u0644\u062d\u0635\u0648\u0644 \u0639\u0644\u0649 \u0628\u064a\u0627\u0646 \u0623\u0637\u0631\u0648\u062d\u0629 \u0642\u0648\u064a \u0648\u0642\u0627\u0628\u0644 \u0644\u0644\u0646\u0642\u0627\u0634 \u0641\u0648\u0631\u064b\u0627. \u064a\u0645\u0646\u062d \u0645\u0642\u0627\u0644\u0643 \u0628\u0623\u0643\u0645\u0644\u0647 \u0639\u0645\u0648\u062f\u064b\u0627 \u0641\u0642\u0631\u064a\u064b\u0627 \u0641\u064a 30 \u062b\u0627\u0646\u064a\u0629. \u0643\u0644 \u0634\u064a\u0621 \u0622\u062e\u0631 \u2014 \u0627\u0644\u062e\u0637\u0629\u060c \u0627\u0644\u0627\u0642\u062a\u0628\u0627\u0633\u0627\u062a\u060c \u0627\u0644\u0646\u0635 \u0627\u0644\u0645\u064f\u0624\u0646\u0633\u0646 \u2014 \u064a\u0646\u0628\u0639 \u0645\u0646 \u062a\u0644\u0643 \u0627\u0644\u0641\u0643\u0631\u0629 \u0627\u0644\u062c\u0648\u0647\u0631\u064a\u0629 \u0627\u0644\u0648\u0627\u062d\u062f\u0629.",
          "\u0627\u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642. \u0627\u0644\u0622\u0646. \u0644\u0627 \u062a\u0641\u0643\u0631 \u0643\u062b\u064a\u0631\u064b\u0627. \u0627\u0636\u063a\u0637 \u0639\u0644\u0649 '\u062a\u0648\u0644\u064a\u062f \u0627\u0644\u0623\u0637\u0631\u0648\u062d\u0629'\u060c \u0627\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639\u0643 \u0623\u0648 \u0627\u0644\u0635\u0642 \u0646\u0635 \u0627\u0644\u0645\u0647\u0645\u0629\u060c \u0648\u0627\u0636\u063a\u0637 \u0627\u0628\u062f\u0623. \u062e\u0644\u0627\u0644 30 \u062b\u0627\u0646\u064a\u0629\u060c \u0633\u062a\u062d\u0635\u0644 \u0639\u0644\u0649 3-5 \u062e\u064a\u0627\u0631\u0627\u062a \u0623\u0637\u0631\u0648\u062d\u0629 \u0642\u0627\u0628\u0644\u0629 \u0644\u0644\u062a\u0637\u0628\u064a\u0642. \u0627\u062e\u062a\u0631 \u0648\u0627\u062d\u062f\u0629. \u0647\u0643\u0630\u0627 \u0628\u0628\u0633\u0627\u0637\u0629\u060c \u0627\u062e\u062a\u0641\u0649 \u0630\u0639\u0631 \u0627\u0644\u0635\u0641\u062d\u0629 \u0627\u0644\u0641\u0627\u0631\u063a\u0629. \u0623\u0646\u062a \u0645\u062a\u0642\u062f\u0645 \u0628\u0627\u0644\u0641\u0639\u0644 \u0639\u0644\u0649 90% \u0645\u0646 \u0632\u0645\u0644\u0627\u0626\u0643.",
          "\u0623\u0637\u0631\u0648\u062d\u062a\u0643 \u0627\u0644\u0623\u0648\u0644\u0649 \u062a\u0646\u062a\u0638\u0631\u0643. \u0627\u0641\u062a\u062d Thesis Generator \u0648\u0623\u0646\u0634\u0626 \u0628\u064a\u0627\u0646\u0643 \u0627\u0644\u0623\u0648\u0644 \u0642\u0628\u0644 \u0623\u0646 \u062a\u0646\u062a\u0647\u064a \u062d\u062a\u0649 \u0645\u0646 \u0647\u0630\u0627 \u0627\u0644\u0628\u0631\u064a\u062f. \u0627\u0644\u0648\u0642\u062a \u064a\u0645\u0631\u060c \u0644\u0643\u0646 \u0627\u0644\u0622\u0646 \u0644\u062f\u064a\u0643 \u0627\u0644\u062d\u0644. \u0645\u0644\u0627\u062d\u0638\u0629: \u0623\u0648\u0644 \u0645\u0646 \u064a\u0633\u062a\u062e\u062f\u0645 \u0645\u064a\u0632\u0629 '\u0627\u0644\u0623\u0646\u0633\u0646\u0629' \u0639\u0644\u0649 \u0623\u0637\u0631\u0648\u062d\u062a\u0647 \u0627\u0644\u0645\u0648\u0644\u0651\u062f\u0629 \u064a\u062a\u062c\u0627\u0648\u0632 \u0643\u0634\u0641 \u0627\u0644\u0630\u0643\u0627\u0621 \u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a \u0628\u0646\u0633\u0628\u0629 99%. \u0625\u0646\u0647\u0627 \u0633\u0644\u0627\u062d\u0643 \u0627\u0644\u0633\u0631\u064a.",
        ],
      },
      fr: {
        subject: "L'erreur que 90% des nouveaux utilisateurs commettent",
        cta_text: "G\u00e9n\u00e9rez votre premi\u00e8re th\u00e8se maintenant",
        body_paragraphs: [
          "J'ai vu la semaine derni\u00e8re un \u00e9tudiant passer 8 heures \u00e0 fixer une page blanche. Sueurs de panique, 3h du matin, deadline dans 6 heures. \u00c7a vous parle ? J'ai cr\u00e9\u00e9 Thesis Generator pour emp\u00eacher ce moment pr\u00e9cis de se reproduire.",
          "Le secret est d'arr\u00eater de vouloir \u00e9crire toute la dissertation d'abord. C'est \u00e7a l'erreur. La victoire la plus rapide est de poser IMM\u00c9DIATEMENT une th\u00e8se solide et argumentable. Elle donne \u00e0 toute votre dissertation une colonne vert\u00e9brale en 30 secondes. Tout le reste \u2014 le plan, les citations, le texte humanis\u00e9 \u2014 d\u00e9coule de cette id\u00e9e centrale.",
          "Ouvrez l'app. Maintenant. Ne r\u00e9fl\u00e9chissez pas trop. Tapez 'G\u00e9n\u00e9rer une th\u00e8se', entrez votre sujet ou collez l'\u00e9nonc\u00e9, et lancez. En 30 secondes, vous aurez 3 \u00e0 5 options de th\u00e8se viables. Choisissez-en une. Comme \u00e7a, la panique de la page blanche dispara\u00eet. Vous avez d\u00e9j\u00e0 une longueur d'avance sur 90% de votre classe.",
          "Votre premi\u00e8re th\u00e8se vous attend. Ouvrez Thesis Generator et g\u00e9n\u00e9rez votre premier \u00e9nonc\u00e9 avant m\u00eame de finir cet email. L'horloge tourne, mais maintenant vous avez l'astuce. P.S. Les premiers qui utilisent la fonction 'Humaniser' sur leur th\u00e8se contournent la d\u00e9tection IA \u00e0 99%. C'est votre arme secr\u00e8te.",
        ],
      },
      es: {
        subject: "El error que el 90% de los usuarios nuevos cometen",
        cta_text: "Genera tu primera tesis ahora",
        body_paragraphs: [
          "La semana pasada vi a un estudiante pasar 8 horas mirando una p\u00e1gina en blanco. Sudor de p\u00e1nico, las 3 de la madrugada, entrega en 6 horas. \u00bfTe suena? Constru\u00ed Thesis Generator para impedir que ese momento exacto vuelva a ocurrirte.",
          "El secreto es dejar de intentar escribir todo el ensayo primero. Ese es el error. La victoria m\u00e1s r\u00e1pida es plasmar INMEDIATAMENTE una tesis s\u00f3lida y argumentable. Le da a todo tu ensayo una columna vertebral en 30 segundos. Todo lo dem\u00e1s \u2014el esquema, las citas, el texto humanizado\u2014 fluye desde esa idea central.",
          "Abre la app. Ahora. No le des vueltas. Pulsa 'Generar Tesis', escribe tu tema o pega el enunciado, y dale go. En 30 segundos tendr\u00e1s 3-5 opciones viables. Elige una. As\u00ed de simple, el p\u00e1nico de la p\u00e1gina en blanco se acab\u00f3. Ya est\u00e1s por delante del 90% de tu clase.",
          "Tu primera tesis te espera. Abre Thesis Generator y genera tu primer enunciado antes incluso de terminar este email. El reloj corre, pero ahora tienes el truco. P.D. Los primeros que usan la funci\u00f3n 'Humanizar' en su tesis generada esquivan la detecci\u00f3n de IA el 99% de las veces. Es tu arma secreta.",
        ],
      },
      hi: {
        subject: "\u0935\u094b \u090f\u0915 \u0917\u0932\u0924\u0940 \u091c\u094b 90% \u0928\u090f \u0909\u092a\u092f\u094b\u0917\u0915\u0930\u094d\u0924\u093e \u0915\u0930\u0924\u0947 \u0939\u0948\u0902",
        cta_text: "\u0905\u092d\u0940 \u0905\u092a\u0928\u0940 \u092a\u0939\u0932\u0940 \u0925\u0940\u0938\u093f\u0938 \u092c\u0928\u093e\u090f\u0902",
        body_paragraphs: [
          "\u092a\u093f\u091b\u0932\u0947 \u0939\u092b\u094d\u0924\u0947 \u092e\u0948\u0902\u0928\u0947 \u090f\u0915 \u091b\u093e\u0924\u094d\u0930 \u0915\u094b 8 \u0918\u0902\u091f\u0947 \u0916\u093e\u0932\u0940 \u092a\u0928\u094d\u0928\u0947 \u0915\u094b \u0918\u0942\u0930\u0924\u0947 \u0939\u0941\u090f \u0926\u0947\u0916\u093e\u0964 \u0918\u092c\u0930\u093e\u0939\u091f \u0915\u093e \u092a\u0938\u0940\u0928\u093e, \u0938\u0941\u092c\u0939 \u0915\u0947 3 \u092c\u091c\u0947, 6 \u0918\u0902\u091f\u0947 \u092e\u0947\u0902 \u0921\u0947\u0921\u0932\u093e\u0907\u0928\u0964 \u092a\u0939\u091a\u093e\u0928\u093e? \u092e\u0948\u0902\u0928\u0947 Thesis Generator \u0907\u0938\u0932\u093f\u090f \u092c\u0928\u093e\u092f\u093e \u0924\u093e\u0915\u093f \u0935\u094b \u0920\u0940\u0915 \u0935\u094b \u092a\u0932 \u092b\u093f\u0930 \u0915\u092d\u0940 \u0928 \u0906\u090f\u0964",
          "\u0930\u093e\u091c\u093c \u092f\u0947 \u0939\u0948 \u0915\u093f \u092a\u0939\u0932\u0947 \u092a\u0942\u0930\u093e \u0928\u093f\u092c\u0902\u0927 \u0932\u093f\u0916\u0928\u0947 \u0915\u0940 \u0915\u094b\u0936\u093f\u0936 \u092c\u0902\u0926 \u0915\u0930\u094b\u0964 \u092f\u0939\u0940 \u0917\u0932\u0924\u0940 \u0939\u0948\u0964 \u0938\u092c\u0938\u0947 \u0924\u0947\u091c\u093c \u091c\u0940\u0924 \u0939\u0948 \u090f\u0915 \u092e\u091c\u093c\u092c\u0942\u0924, \u092c\u0939\u0938\u092f\u094b\u0917\u094d\u092f \u0925\u0940\u0938\u093f\u0938 \u0938\u094d\u091f\u0947\u091f\u092e\u0947\u0902\u091f \u0924\u0941\u0930\u0902\u0924 \u0932\u093f\u0916 \u0932\u0947\u0928\u093e\u0964 \u092f\u0939 \u0906\u092a\u0915\u0947 \u092a\u0942\u0930\u0947 \u0928\u093f\u092c\u0902\u0927 \u0915\u094b 30 \u0938\u0947\u0915\u0902\u0921 \u092e\u0947\u0902 \u0930\u0940\u0922\u093c \u0915\u0940 \u0939\u0921\u094d\u0921\u0940 \u0926\u0947\u0924\u093e \u0939\u0948\u0964 \u092c\u093e\u0915\u0940 \u0938\u092c \u0915\u0941\u091b \u2014 \u0906\u0909\u091f\u0932\u093e\u0907\u0928, \u0938\u093e\u0907\u091f\u0947\u0936\u0928, \u0939\u094d\u092f\u0942\u092e\u0928\u093e\u0907\u091c\u093c\u094d\u0921 \u091f\u0947\u0915\u094d\u0938\u094d\u091f \u2014 \u0907\u0938\u0940 \u090f\u0915 \u092e\u0942\u0932 \u0935\u093f\u091a\u093e\u0930 \u0938\u0947 \u092c\u0939\u0924\u093e \u0939\u0948\u0964",
          "\u0910\u092a \u0916\u094b\u0932\u094b\u0964 \u0905\u092d\u0940\u0964 \u091c\u093c\u094d\u092f\u093e\u0926\u093e \u092e\u0924 \u0938\u094b\u091a\u094b\u0964 'Generate Thesis' \u0926\u092c\u093e\u0913, \u0905\u092a\u0928\u093e \u0935\u093f\u0937\u092f \u091f\u093e\u0907\u092a \u0915\u0930\u094b \u092f\u093e \u0905\u0938\u093e\u0907\u0928\u092e\u0947\u0902\u091f \u092a\u094d\u0930\u0949\u092e\u094d\u092a\u094d\u091f \u092a\u0947\u0938\u094d\u091f \u0915\u0930\u094b, \u0914\u0930 \u0936\u0941\u0930\u0942 \u0915\u0930\u094b\u0964 30 \u0938\u0947\u0915\u0902\u0921 \u092e\u0947\u0902 3-5 \u0935\u094d\u092f\u093e\u0935\u0939\u093e\u0930\u093f\u0915 \u0925\u0940\u0938\u093f\u0938 \u0935\u093f\u0915\u0932\u094d\u092a \u092e\u093f\u0932\u0947\u0902\u0917\u0947\u0964 \u090f\u0915 \u091a\u0941\u0928\u094b\u0964 \u092c\u0938 \u0907\u0924\u0928\u093e \u0939\u0940, \u0916\u093e\u0932\u0940 \u092a\u0928\u094d\u0928\u0947 \u0915\u0940 \u0918\u092c\u0930\u093e\u0939\u091f \u0917\u093e\u092f\u092c\u0964 \u0906\u092a \u092a\u0939\u0932\u0947 \u0938\u0947 \u0939\u0940 \u0905\u092a\u0928\u0940 \u0915\u094d\u0932\u093e\u0938 \u0915\u0947 90% \u0938\u0947 \u0906\u0917\u0947 \u0939\u0948\u0902\u0964",
          "\u0906\u092a\u0915\u0940 \u092a\u0939\u0932\u0940 \u0925\u0940\u0938\u093f\u0938 \u0907\u0902\u0924\u091c\u093c\u093e\u0930 \u0915\u0930 \u0930\u0939\u0940 \u0939\u0948\u0964 \u092f\u0939 \u0908\u092e\u0947\u0932 \u0916\u0924\u094d\u092e \u0939\u094b\u0928\u0947 \u0938\u0947 \u092a\u0939\u0932\u0947 Thesis Generator \u0916\u094b\u0932\u0947\u0902 \u0914\u0930 \u0905\u092a\u0928\u093e \u092a\u0939\u0932\u093e \u0938\u094d\u091f\u0947\u091f\u092e\u0947\u0902\u091f \u092c\u0928\u093e\u090f\u0902\u0964 \u0918\u0921\u093c\u0940 \u091f\u093f\u0915 \u0930\u0939\u0940 \u0939\u0948, \u0932\u0947\u0915\u093f\u0928 \u0905\u092c \u0906\u092a\u0915\u0947 \u092a\u093e\u0938 \u0939\u0948\u0915 \u0939\u0948\u0964 P.S. \u092a\u0939\u0932\u0947 \u091c\u094b \u0932\u094b\u0917 'Humanize' \u092b\u0940\u091a\u0930 \u0905\u092a\u0928\u0940 \u0925\u0940\u0938\u093f\u0938 \u092a\u0930 \u0907\u0938\u094d\u0924\u0947\u092e\u093e\u0932 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902, \u0935\u094b AI \u0921\u093f\u091f\u0947\u0915\u094d\u0936\u0928 \u0915\u094b 99% \u092c\u093e\u0930 \u092c\u093e\u092f\u092a\u093e\u0938 \u0915\u0930 \u091c\u093e\u0924\u0947 \u0939\u0948\u0902\u0964 \u092f\u0947 \u0906\u092a\u0915\u093e \u0917\u0941\u092a\u094d\u0924 \u0939\u0925\u093f\u092f\u093e\u0930 \u0939\u0948\u0964",
        ],
      },
      zh: {
        subject: "90%\u7684\u65b0\u7528\u6237\u90fd\u72af\u7684\u90a3\u4e00\u4e2a\u9519\u8bef",
        cta_text: "\u7acb\u5373\u751f\u6210\u4f60\u7684\u7b2c\u4e00\u7bc7\u8bba\u70b9",
        body_paragraphs: [
          "\u4e0a\u5468\u6211\u770b\u5230\u4e00\u4e2a\u5b66\u751f\u82b1\u4e868\u5c0f\u65f6\u76ef\u7740\u4e00\u5f20\u767d\u7eb8\u3002\u51b7\u6c57\u3001\u51cc\u66683\u70b9\u30016\u5c0f\u65f6\u540e\u4ea4\u7a3f\u3002\u542c\u8d77\u6765\u719f\u6089\u5417\uff1f\u6211\u505aThesis Generator\u5c31\u662f\u4e3a\u4e86\u963b\u6b62\u90a3\u4e00\u523b\u518d\u53d1\u751f\u3002",
          "\u79d8\u8bc0\u662f\u522b\u60f3\u7740\u5148\u628a\u6574\u7bc7\u8bba\u6587\u5199\u5b8c\u3002\u8fd9\u5c31\u662f\u9519\u8bef\u3002\u6700\u5feb\u7684\u80dc\u5229\u662f\u7acb\u523b\u5199\u51fa\u4e00\u4e2a\u6709\u529b\u4e14\u53ef\u8fa9\u8bba\u7684\u8bba\u70b9\u58f0\u660e\u3002\u5b83\u80fd\u572830\u79d2\u5185\u4e3a\u6574\u7bc7\u6587\u7ae0\u5efa\u7acb\u9aa8\u67b6\u3002\u5176\u4f59\u4e00\u5207\u2014\u2014\u5927\u7eb2\u3001\u5f15\u7528\u3001\u4eba\u6027\u5316\u6587\u672c\u2014\u2014\u90fd\u4ece\u8fd9\u4e00\u4e2a\u6838\u5fc3\u60f3\u6cd5\u6d41\u51fa\u3002",
          "\u6253\u5f00\u5e94\u7528\u3002\u73b0\u5728\u3002\u522b\u60f3\u592a\u591a\u3002\u70b9\u51fb'\u751f\u6210\u8bba\u70b9'\uff0c\u8f93\u5165\u4f60\u7684\u4e3b\u9898\u6216\u7c98\u8d34\u4f5c\u4e1a\u8981\u6c42\uff0c\u6309\u5f00\u59cb\u300230\u79d2\u5185\u4f60\u4f1a\u5f97\u52303-5\u4e2a\u53ef\u884c\u7684\u8bba\u70b9\u9009\u9879\u3002\u9009\u4e00\u4e2a\u3002\u5c31\u8fd9\u6837\uff0c\u767d\u7eb8\u6050\u614c\u6d88\u5931\u4e86\u3002\u4f60\u5df2\u7ecf\u9886\u5148\u73ed\u91cc90%\u7684\u4eba\u4e86\u3002",
          "\u4f60\u7684\u7b2c\u4e00\u7bc7\u8bba\u70b9\u6b63\u5728\u7b49\u4f60\u3002\u5728\u4f60\u8bfb\u5b8c\u8fd9\u5c01\u90ae\u4ef6\u4e4b\u524d\u6253\u5f00Thesis Generator\u751f\u6210\u7b2c\u4e00\u53e5\u8bba\u70b9\u3002\u65f6\u949f\u5728\u8d70\uff0c\u4f46\u73b0\u5728\u4f60\u6709\u8fd9\u4e2a\u79d8\u8bc0\u4e86\u3002P.S. \u7b2c\u4e00\u6279\u4f7f\u7528'\u4eba\u6027\u5316'\u529f\u80fd\u5904\u7406\u751f\u6210\u8bba\u70b9\u7684\u7528\u6237\uff0c\u80fd99%\u7ed5\u8fc7AI\u68c0\u6d4b\u3002\u8fd9\u662f\u4f60\u7684\u79d8\u5bc6\u6b66\u5668\u3002",
        ],
      },
    },
  },

  red_flag_scanner: {
    name: "Red Flag Scanner AI",
    multilingual: false,
    appStoreUrl: "https://apps.apple.com/app/red-flag-scanner-ai/id6740946063",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.redflag.scanner.ai.red_flag_scanner",
    emails: {
      en: {
        subject: "The one mistake 90% of users make on day one",
        cta_text: "Open & Scan Your First Text",
        body_paragraphs: [
          "I need to tell you something before you even open the app. Most people download Red Flag Scanner AI, stare at the home screen, and then close it. They think they need a 'big' reason to use it. They wait until they're already crying on the bathroom floor. Don't be one of them.",
          "The magic isn't in waiting for a crisis. It's in the tiny, 30-second check. That gut feeling you had yesterday about a text that felt 'off'? That's the exact moment you should have opened the app. The value isn't in the big blow-up; it's in catching the small, quiet red flags before they become a screaming chorus.",
          "There's one button on the home screen: 'Scan a Conversation.' That's it. Don't overthink it. Don't save it for a 'real' fight. Screenshot the text that made your stomach twist. The one where the apology felt like another accusation. Let the AI look at the language for you. It takes 30 seconds. You get an instant toxicity score and a breakdown of what the words are actually doing.",
          "Open the app right now. Before you finish this email. Don't wait for 'proof.' Your gut feeling IS the proof. Hit 'Scan a Conversation' with the last text that pinged your radar. Just do it. P.S. The first scan is always the hardest. The 800+ people who avoided major heartache all started with one 30-second scan of something 'small.'",
        ],
      },
    },
  },

  breakup_therapy: {
    name: "Fresh Start: Breakup Therapy",
    multilingual: false,
    appStoreUrl: "https://apps.apple.com/app/fresh-start-breakup-therapy-ai/id6749954260",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.breakup.therapy.therapyforabreakup.therapistforbreakups",
    emails: {
      en: {
        subject: "The one mistake 90% of users make at 3AM",
        cta_text: "Try Emergency Mode Now",
        body_paragraphs: [
          "It's 3:17 AM and you're staring at the ceiling again. Your brain is replaying that last conversation on a loop. You know you shouldn't check their socials, but your thumb is already hovering. Here's the truth: that moment isn't just pain\u2014it's a critical turning point most people waste.",
          "I used to do the same thing. I'd scroll through old photos until sunrise, then feel wrecked all day. Then I discovered something: the 3AM spiral has a secret exit door. It's not about willpower\u2014it's about having the right tool in your pocket when your brain turns against you.",
          "Open the app right now and tap 'Emergency Mode' on the home screen. Don't wait until tonight. The first time is the hardest, and I want you to have it ready. It's a 30-second audio guide that literally interrupts the obsessive thought cycle\u2014600+ people use it to fall back asleep instead of falling apart.",
          "Tap the button below and try Emergency Mode once right now. Just once. So when 3AM hits tonight, you already know the escape route. P.S. The first user who tried this told me 'It felt like someone finally handed me a life raft in the middle of the ocean.' That someone is you, handing it to yourself.",
        ],
      },
    },
  },

  soulplan: {
    name: "SoulPlan: Plan Dates Together",
    multilingual: true,
    appStoreUrl: "https://apps.apple.com/app/soulplan-plan-dates-together/id6702018988",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.aifun.dateideas.planadate",
    emails: {
      en: {
        subject: "Tonight's date is already waiting for you",
        cta_text: "Open Tonight's Date",
        body_paragraphs: [
          "You just downloaded SoulPlan, and the trap is the same for almost everyone: open the app, browse a few ideas, close it, mean to come back later. Three weeks pass and the spark is still on the to-do list. The trick to avoid that is also the simplest thing in the app — and it takes 30 seconds tonight.",
          "On the home screen, there's a single card that already has tonight's date pre-picked for the two of you. No questionnaire. No scrolling. Just one tap on a mood (cozy, adventurous, playful or healing) and the AI builds a date you can actually use this evening. The whole point is to remove the planning, not add another inbox.",
          "Open the app right now. Tap the mood that fits tonight. Read the card. If it doesn't quite land, hit \"Show another\" — the AI rotates through different vibes so the second one usually does. When you find the one you love, tap \"Send to partner\" and they get a beautiful celebration screen waiting for them. That's the whole loop.",
          "Don't save this for the weekend. Tonight is the perfect first date because the bar is low and the surprise is high. Tap below, pick a mood, and watch your partner light up. P.S. The couples who use Tonight's Date in their first 24 hours plan 4x more dates over the next month than the ones who wait. Don't be the ones who wait.",
        ],
      },
      ar: {
        subject: "موعد الليلة بانتظارك بالفعل",
        cta_text: "افتح موعد الليلة",
        body_paragraphs: [
          "لقد حمّلت تطبيق SoulPlan للتو، والفخ نفسه للجميع تقريبًا: تفتح التطبيق، تتصفح بعض الأفكار، تغلقه، وتنوي العودة لاحقًا. تمر ثلاثة أسابيع ولا تزال الشرارة على قائمة المهام. الحيلة لتجنب ذلك هي أيضًا أبسط شيء في التطبيق — وتستغرق 30 ثانية الليلة.",
          "على الشاشة الرئيسية، هناك بطاقة واحدة تحتوي بالفعل على موعد الليلة المختار مسبقًا لكما. لا استبيانات. لا تمرير. مجرد نقرة واحدة على مزاج (دافئ، مغامر، مرح، أو شافي) ويبني الذكاء الاصطناعي موعدًا يمكنك استخدامه هذا المساء. الهدف الأساسي هو إزالة التخطيط، لا إضافة صندوق وارد آخر.",
          "افتح التطبيق الآن. انقر على المزاج الذي يناسب الليلة. اقرأ البطاقة. إذا لم تكن مناسبة تمامًا، اضغط \"Show another\" — يبدل الذكاء الاصطناعي بين الأجواء المختلفة، وعادةً ما تكون الثانية مناسبة. عندما تجد الموعد الذي يعجبك، انقر \"إرسال إلى الشريك\" وستظهر لهم شاشة احتفال جميلة بانتظارهم. هذه هي الدائرة كاملة.",
          "لا تؤجل هذا لعطلة نهاية الأسبوع. الليلة هي الموعد الأول المثالي لأن التوقعات منخفضة والمفاجأة عالية. انقر أدناه، اختر مزاجًا، وشاهد شريكك يضيء. ملاحظة: الأزواج الذين يستخدمون Tonight's Date في أول 24 ساعة يخططون لمواعيد أكثر بأربع مرات خلال الشهر التالي مقارنة بمن ينتظرون. لا تكن ممن ينتظرون.",
        ],
      },
      es: {
        subject: "Tu cita de esta noche ya te espera",
        cta_text: "Abrir Tonight's Date",
        body_paragraphs: [
          "Acabas de descargar SoulPlan, y la trampa es la misma para casi todos: abres la app, echas un vistazo a algunas ideas, la cierras, y piensas volver más tarde. Pasan tres semanas y la chispa sigue en la lista de pendientes. El truco para evitarlo es también lo más sencillo de la app, y te llevará solo 30 segundos esta noche.",
          "En la pantalla de inicio hay una sola tarjeta que ya tiene preparada la cita de esta noche para vosotros dos. Sin cuestionarios. Sin desplazarte. Solo un toque en un estado de ánimo (acogedor, aventurero, divertido o sanador) y la IA construye una cita que podéis disfrutar esta misma noche. La idea es eliminar la planificación, no añadir otra bandeja de entrada.",
          "Abre la app ahora mismo. Toca el estado de ánimo que encaje con esta noche. Lee la tarjeta. Si no termina de convencerte, pulsa \"Show another\" — la IA cambia de vibra para que la segunda opción suela acertar. Cuando encuentres la que te encanta, toca \"Send to partner\" y tu pareja recibirá una preciosa pantalla de celebración. Ese es todo el proceso.",
          "No lo guardes para el fin de semana. Esta noche es la cita perfecta porque las expectativas son bajas y la sorpresa, alta. Toca abajo, elige un estado de ánimo y mira cómo se ilumina tu pareja. PD: Las parejas que usan Tonight's Date en sus primeras 24 horas planean 4 veces más citas durante el próximo mes que las que esperan. No seáis los que esperan.",
        ],
      },
      fr: {
        subject: "Ce soir, votre date est déjà prête",
        cta_text: "Ouvrir Tonight's Date",
        body_paragraphs: [
          "Tu viens de télécharger SoulPlan, et le piège est le même pour presque tout le monde : ouvrir l'app, parcourir quelques idées, la fermer, se promettre de revenir plus tard. Trois semaines passent et l'étincelle est toujours sur la liste des choses à faire. L'astuce pour éviter ça est aussi la chose la plus simple dans l'app — et ça prend 30 secondes ce soir.",
          "Sur l'écran d'accueil, il y a une seule carte qui a déjà choisi votre date de ce soir pour vous deux. Pas de questionnaire. Pas de défilement. Un simple tap sur une humeur (cosy, aventureuse, joueuse ou réconfortante) et l'IA construit une date que vous pouvez vraiment vivre ce soir. Tout l'intérêt est de supprimer la planification, pas d'ajouter une autre boîte de réception.",
          "Ouvre l'app maintenant. Tape sur l'humeur qui correspond à ce soir. Lis la carte. Si elle ne te convient pas tout à fait, clique sur \"Show another\" — l'IA alterne entre différentes ambiances, donc la deuxième fonctionne généralement. Quand tu trouves celle que tu aimes, tape \"Send to partner\" et ton ou ta partenaire reçoit une magnifique écran de célébration qui les attend. C'est tout le processus.",
          "Ne garde pas ça pour le week-end. Ce soir est la date parfaite pour commencer, car la barre est basse et la surprise est grande. Tape ci-dessous, choisis une humeur, et regarde ton ou ta partenaire s'illuminer. P.S. Les couples qui utilisent Tonight's Date dans leurs premières 24 heures planifient 4 fois plus de dates le mois suivant que ceux qui attendent. Ne soyez pas ceux qui attendent.",
        ],
      },
      pt: {
        subject: "O encontro de hoje já está esperando por você",
        cta_text: "Abrir Tonight's Date",
        body_paragraphs: [
          "Você acabou de baixar o SoulPlan, e a armadilha é a mesma para quase todo mundo: abrir o app, ver algumas ideias, fechar, e prometer voltar depois. Três semanas passam e a faísca ainda está na lista de afazeres. O truque para evitar isso é também a coisa mais simples do app — e leva só 30 segundos hoje à noite.",
          "Na tela inicial, tem um único card que já traz o encontro de hoje pré-selecionado para vocês dois. Sem questionário. Sem rolagem infinita. É só um toque num mood (aconchegante, aventureiro, divertido ou curador) e a IA monta um encontro que vocês podem viver ainda esta noite. A ideia é eliminar o planejamento, não adicionar mais uma caixa de entrada.",
          "Abra o app agora. Toque no mood que combina com hoje. Leia o card. Se não for bem a cara de vocês, clique em \"Show another\" — a IA alterna entre diferentes vibes, então a segunda opção geralmente acerta. Quando encontrarem o encontro ideal, toquem em \"Send to partner\" e o parceiro ou parceira recebe uma linda tela de celebração. Esse é o ciclo completo.",
          "Não guarde isso para o fim de semana. Hoje é o primeiro encontro perfeito porque a expectativa é baixa e a surpresa é grande. Toque abaixo, escolha um mood e veja seu parceiro(a) se iluminar. P.S.: Os casais que usam o Tonight's Date nas primeiras 24 horas planejam 4x mais encontros no mês seguinte do que aqueles que esperam. Não seja um dos que esperam.",
        ],
      },
      pp: {
        subject: "O vosso date de hoje já está à vossa espera",
        cta_text: "Abrir Tonight's Date",
        body_paragraphs: [
          "Acabaste de descarregar o SoulPlan, e a armadilha é a mesma para quase toda a gente: abres a app, vês umas ideias, fechas, e dizes que voltas mais tarde. Passam três semanas e a faísca continua na lista de tarefas. O truque para evitar isso é também a coisa mais simples da app — e leva 30 segundos esta noite.",
          "No ecrã inicial, há um único cartão que já tem o date de hoje pré-selecionado para vocês os dois. Sem questionários. Sem scroll. Basta um toque num estado de espírito (acolhedor, aventureiro, divertido ou curativo) e a IA constrói um date que podem usar esta noite. O objetivo é mesmo eliminar o planeamento, não acrescentar mais uma caixa de entrada.",
          "Abre a app agora mesmo. Toca no estado de espírito que combina com esta noite. Lê o cartão. Se não for bem o que esperavas, carrega em \"Show another\" — a IA roda por diferentes vibes, por isso a segunda opção costuma acertar. Quando encontrarem o que adoram, toquem em \"Send to partner\" e o vosso parceiro recebe um ecrã de celebração lindo à vossa espera. Este é o ciclo completo.",
          "Não guardes isto para o fim de semana. Esta noite é o date perfeito para começar porque a barreira é baixa e a surpresa é grande. Toca abaixo, escolhe um estado de espírito e vê o teu parceiro iluminar-se. P.S. Os casais que usam o Tonight's Date nas primeiras 24 horas planeiam 4x mais dates no mês seguinte do que os que esperam. Não sejas dos que esperam.",
        ],
      },
      de: {
        subject: "Dein Date für heute Abend wartet schon",
        cta_text: "Heute Abend öffnen",
        body_paragraphs: [
          "Du hast SoulPlan gerade heruntergeladen – und die Falle ist für fast alle gleich: App öffnen, ein paar Ideen anschauen, wieder schließen, später zurückkommen wollen. Drei Wochen vergehen und der Funke steht immer noch auf der To-do-Liste. Der Trick, das zu vermeiden, ist gleichzeitig das Einfachste in der App – und dauert heute Abend nur 30 Sekunden.",
          "Auf dem Startbildschirm siehst du eine einzige Karte, die für euch beide schon ein Date für heute Abend bereithält. Kein Fragebogen. Kein Scrollen. Einfach auf eine Stimmung tippen (gemütlich, abenteuerlich, verspielt oder heilend) und die KI baut ein Date, das ihr heute Abend wirklich machen könnt. Der ganze Sinn ist, die Planung wegzulassen – nicht noch ein Postfach hinzuzufügen.",
          "Öffne jetzt die App. Tipp auf die Stimmung, die zu heute Abend passt. Lies die Karte. Wenn sie nicht ganz passt, tipp auf „Show another“ – die KI wechselt durch verschiedene Vibes, sodass die zweite meistens sitzt. Wenn du die gefunden hast, die ihr liebt, tipp auf „Send to partner“ und dein Partner bekommt einen wunderschönen Feierbildschirm. Das ist der ganze Kreislauf.",
          "Heb das nicht fürs Wochenende auf. Heute Abend ist das perfekte erste Date, weil die Hürde niedrig und die Überraschung groß ist. Tipp unten, wähl eine Stimmung und sieh zu, wie dein Partner aufleuchtet. P.S.: Paare, die Tonight's Date in den ersten 24 Stunden nutzen, planen im nächsten Monat 4x mehr Dates als die, die warten. Seid nicht die, die warten.",
        ],
      },
      it: {
        subject: "L'appuntamento di stasera ti aspetta già",
        cta_text: "Apri Tonight's Date",
        body_paragraphs: [
          "Hai appena scaricato SoulPlan, e la trappola è la stessa per quasi tutti: apri l'app, dai un'occhiata a qualche idea, la chiudi, pensi di tornare dopo. Passano tre settimane e la scintilla è ancora nella lista delle cose da fare. Il trucco per evitarlo è anche la cosa più semplice dell'app — e ti bastano 30 secondi stasera.",
          "Nella schermata principale c'è una singola card che ha già pronto l'appuntamento di stasera per voi due. Niente questionari. Niente scroll. Basta un tap su un mood (accogliente, avventuroso, giocoso o rigenerante) e l'AI costruisce una serata che potete vivere davvero questa sera. Il punto è eliminare la pianificazione, non aggiungere un'altra lista di cose da fare.",
          "Apri l'app adesso. Tocca il mood che fa per stasera. Leggi la card. Se non ti convince del tutto, premi \"Show another\" — l'AI cambia atmosfera, quindi di solito la seconda va bene. Quando trovi quella che ami, tocca \"Send to partner\" e loro riceveranno una bellissima schermata di festa che li aspetta. Questo è tutto il meccanismo.",
          "Non rimandare al weekend. Stasera è l'appuntamento perfetto perché l'asticella è bassa e la sorpresa è alta. Tocca qui sotto, scegli un mood e guarda il tuo partner illuminarsi. P.S. Le coppie che usano Tonight's Date nelle prime 24 ore organizzano 4 volte più appuntamenti nel mese successivo rispetto a chi aspetta. Non essere tra quelli che aspettano.",
        ],
      },
      pl: {
        subject: "Dzisiejsza randka już na Ciebie czeka",
        cta_text: "Otwórz Tonight's Date",
        body_paragraphs: [
          "Właśnie pobrałeś SoulPlan i pułapka jest dla prawie wszystkich taka sama: otwierasz aplikację, przeglądasz kilka pomysłów, zamykasz ją, myśląc, że wrócisz później. Mijają trzy tygodnie, a iskra wciąż jest na liście rzeczy do zrobienia. Sposób, by tego uniknąć, jest też najprostszą rzeczą w aplikacji — i zajmie Ci dziś wieczorem 30 sekund.",
          "Na ekranie głównym jest jedna karta, która już ma dla Was przygotowaną dzisiejszą randkę. Żadnych ankiet. Żadnego przewijania. Wystarczy jeden dotknięcie nastroju (przytulny, przygodowy, zabawny lub uzdrawiający), a AI tworzy randkę, którą możecie wykorzystać jeszcze dziś wieczorem. Cały sens polega na wyeliminowaniu planowania, a nie dodawaniu kolejnej skrzynki odbiorczej.",
          "Otwórz aplikację teraz. Dotknij nastroju, który pasuje na dziś. Przeczytaj kartę. Jeśli nie do końca trafia, kliknij „Show another” — AI zmienia klimaty, więc druga zwykle już trafia. Gdy znajdziesz tę jedyną, dotknij „Wyślij do partnera”, a on zobaczy piękny ekran powitalny. To cała pętla.",
          "Nie odkładaj tego na weekend. Dziś wieczór jest idealny na pierwszą randkę, bo poprzeczka jest nisko, a niespodzianka wysoka. Kliknij poniżej, wybierz nastrój i patrz, jak Twój partner promienieje. PS. Pary, które używają Tonight's Date w ciągu pierwszych 24 godzin, planują 4 razy więcej randek w następnym miesiącu niż te, które czekają. Nie bądźcie tymi, którzy czekają.",
        ],
      },
      tr: {
        subject: "Bu akşamın randevusu seni bekliyor",
        cta_text: "Tonight's Date'i Aç",
        body_paragraphs: [
          "SoulPlan'i yeni indirdin ve neredeyse herkesin düştüğü tuzak aynı: uygulamayı aç, birkaç fikre göz at, kapat, sonra geri dönmeyi düşün. Üç hafta geçer ve o kıvılcım hâlâ yapılacaklar listesinde. Bunu aşmanın yoluysa uygulamadaki en basit şey — ve bu akşam sadece 30 saniyenizi alır.",
          "Ana ekranda, ikiniz için önceden seçilmiş bu akşamın randevusunu içeren tek bir kart var. Anket yok. Kaydırma yok. Sadece bir ruh haline dokun (samimi, maceralı, eğlenceli veya şifalandırıcı) ve AI bu akşam kullanabileceğin bir randevu oluştursun. Tüm amaç planlamayı ortadan kaldırmak, bir gelen kutusu daha eklemek değil.",
          "Hemen uygulamayı aç. Bu akşama uyan ruh haline dokun. Kartı oku. Tam oturmazsa, \"Show another\"a bas — AI farklı havalar arasında geçiş yapar, genelde ikincisi tutar. Sevdiğin birini bulduğunda \"Send to partner\"a dokun ve partnerini bekleyen harika bir kutlama ekranı görsün. Döngü bu kadar.",
          "Bunu haftasonuna saklama. Bu akşam mükemmel bir ilk randevu çünkü beklenti düşük, sürpriz yüksek. Aşağıya dokun, bir ruh hali seç ve partnerinin yüzünün aydınlandığını izle. Not: Tonight's Date'i ilk 24 saat içinde kullanan çiftler, bekleyenlere kıyasla önümüzdeki ay 4 kat daha fazla randevu planlıyor. Bekleyenlerden olmayın.",
        ],
      },
      ru: {
        subject: "Свидание на сегодня уже ждёт тебя",
        cta_text: "Открыть Tonight's Date",
        body_paragraphs: [
          "Ты только что скачал SoulPlan, и ловушка знакома почти всем: открываешь приложение, листаешь пару идей, закрываешь, собираешься вернуться позже. Проходит три недели, а искра всё ещё висит в списке дел. Трюк, чтобы этого избежать, — самое простое в приложении, и займёт всего 30 секунд сегодня вечером.",
          "На главном экране есть одна карточка, где уже готово свидание на сегодня для вас двоих. Никаких опросников. Никакого скроллинга. Просто один тап по настроению (уютное, авантюрное, игривое или исцеляющее) — и AI собирает свидание, которое можно провести уже этим вечером. Смысл в том, чтобы убрать планирование, а не добавить ещё одну задачу.",
          "Открой приложение прямо сейчас. Выбери настроение, которое подходит вечеру. Прочитай карточку. Если не зашло — нажми «Show another»: AI переключает разные вайбы, так что второй вариант обычно попадает в точку. Когда найдёшь тот самый, нажми «Send to partner» — и партнёра встретит красивый экран с поздравлением. Вот и весь цикл.",
          "Не откладывай на выходные. Сегодняшний вечер — идеальное первое свидание, потому что планка низкая, а сюрприз — высокий. Жми ниже, выбирай настроение и смотри, как загорятся глаза твоего партнёра. P.S. Пары, которые используют Tonight's Date в первые 24 часа, планируют в 4 раза больше свиданий в ближайший месяц, чем те, кто ждёт. Не будьте теми, кто ждёт.",
        ],
      },
      hi: {
        subject: "आज रात की डेट पहले से आपका इंतज़ार कर रही है",
        cta_text: "Tonight's Date खोलें",
        body_paragraphs: [
          "आपने अभी SoulPlan डाउनलोड किया है, और लगभग सभी के साथ यही होता है: ऐप खोलें, कुछ आइडियाज़ देखें, बंद करें, और बाद में वापस आने का इरादा रखें। तीन हफ़्ते बीत जाते हैं और वह चिंगारी अभी भी आपकी टू-डू लिस्ट में होती है। इससे बचने का तरीका भी ऐप की सबसे आसान चीज़ है — और इसमें आज रात सिर्फ 30 सेकंड लगेंगे।",
          "होम स्क्रीन पर एक सिंगल कार्ड है जिसमें पहले से आप दोनों के लिए आज रात की डेट तैयार है। कोई सवाल नहीं। कोई स्क्रॉलिंग नहीं। बस एक मूड (आरामदायक, साहसिक, मज़ेदार या उपचारात्मक) पर टैप करें और AI एक ऐसी डेट बनाता है जिसे आप आज शाम वास्तव में इस्तेमाल कर सकते हैं। पूरा मकसद प्लानिंग को खत्म करना है, न कि एक और इनबॉक्स जोड़ना।",
          "अभी ऐप खोलें। आज रात के मूड पर टैप करें। कार्ड पढ़ें। अगर यह बिल्कुल फिट नहीं बैठता, तो \"Show another\" पर टैप करें — AI अलग-अलग वाइब्स घुमाता है, तो दूसरा आमतौर पर सही लगता है। जब आपको वह मिल जाए जो आपको पसंद है, तो \"Send to partner\" पर टैप करें और उनके लिए एक खूबसूरत सेलिब्रेशन स्क्रीन इंतज़ार कर रही होगी। बस इतना ही लूप है।",
          "इसे वीकेंड के लिए मत बचाकर रखें। आज रात पहली डेट के लिए परफेक्ट है क्योंकि बार कम है और सरप्राइज़ ज़्यादा है। नीचे टैप करें, एक मूड चुनें, और अपने पार्टनर को खिलखिलाते देखें। P.S. जो कपल्स अपने पहले 24 घंटों में Tonight's Date का इस्तेमाल करते हैं, वे अगले महीने में उन लोगों की तुलना में 4 गुना ज़्यादा डेट्स प्लान करते हैं जो इंतज़ार करते हैं। वो मत बनो जो इंतज़ार करते हैं।",
        ],
      },
      id: {
        subject: "Kencan malam ini sudah menunggumu",
        cta_text: "Buka Tonight's Date",
        body_paragraphs: [
          "Kamu baru saja mengunduh SoulPlan, dan jebakannya hampir sama untuk semua orang: buka aplikasi, lihat-lihat beberapa ide, tutup, berniat kembali lagi nanti. Tiga minggu berlalu dan percikan api masih ada di daftar tugas. Trik untuk menghindarinya juga hal paling sederhana di aplikasi ini — dan hanya butuh 30 detik malam ini.",
          "Di layar utama, ada satu kartu yang sudah berisi kencan malam ini yang dipilihkan untuk kalian berdua. Tidak perlu kuesioner. Tidak perlu scroll. Cukup satu ketukan pada suasana hati (nyaman, petualang, ceria, atau penyembuhan) dan AI akan membuatkan kencan yang benar-benar bisa kalian nikmati malam ini. Intinya adalah menghilangkan proses perencanaan, bukan menambah kotak masuk lain.",
          "Buka aplikasinya sekarang. Ketuk suasana hati yang cocok untuk malam ini. Baca kartunya. Jika kurang pas, tekan \"Show another\" — AI akan memutar berbagai nuansa berbeda sehingga yang kedua biasanya lebih cocok. Saat kamu menemukan yang kamu suka, ketuk \"Send to partner\" dan mereka akan mendapatkan layar perayaan indah yang menunggu. Itulah seluruh rangkaiannya.",
          "Jangan simpan ini untuk akhir pekan. Malam ini adalah kencan pertama yang sempurna karena ekspektasinya rendah dan kejutannya tinggi. Ketuk di bawah, pilih suasana hati, dan lihat pasanganmu berseri-seri. P.S. Pasangan yang menggunakan Tonight's Date dalam 24 jam pertama merencanakan 4x lebih banyak kencan di bulan berikutnya dibandingkan yang menunggu. Jangan jadi pasangan yang menunggu.",
        ],
      },
      ja: {
        subject: "今夜のデートがもう待っています",
        cta_text: "Tonight's Dateを開く",
        body_paragraphs: [
          "SoulPlanをダウンロードしたばかりの方、ほとんどのカップルが同じ罠にはまります。アプリを開いて、いくつかアイデアを眺めて、閉じて、また後で来ようと思う。3週間が過ぎても、ときめきはまだやることリストのまま。それを避けるコツは、アプリの中で一番シンプルな機能にあります。今夜、たった30秒でできることです。",
          "ホーム画面には、今夜のデートがすでに2人のために用意されたカードが1枚あります。アンケートもスクロールも不要。ムード（居心地の良い、冒険的、遊び心、癒し）を1つタップするだけで、AIが今夜すぐ使えるデートを組み立ててくれます。目的は計画をなくすことであって、受信箱を増やすことではありません。",
          "今すぐアプリを開いて、今夜に合うムードをタップし、カードを読んでみてください。もしピンとこなければ「Show another」をタップ。AIが違う雰囲気を次々と提案してくれるので、2回目でだいたいしっくりきます。気に入ったものを見つけたら「Send to partner」をタップ。するとパートナーに美しいお祝い画面が届きます。これがすべての流れです。",
          "週末まで取っておかないでください。今夜が完璧な初デートになる理由は、ハードルが低くてサプライズが大きいから。下をタップしてムードを選び、パートナーが笑顔になるのを見てください。P.S. 最初の24時間でTonight's Dateを使ったカップルは、待ったカップルより次の1ヶ月で4倍多くのデートを計画しています。待つ側にならないでくださいね。",
        ],
      },
      ko: {
        subject: "오늘 밤의 데이트가 벌써 기다리고 있어요",
        cta_text: "Tonight's Date 열기",
        body_paragraphs: [
          "방금 SoulPlan을 다운로드하셨죠. 대부분의 사람들이 똑같은 함정에 빠집니다. 앱을 열고, 아이디어 몇 개를 둘러보고, 닫고, 나중에 다시 오려고 마음먹죠. 그러다 3주가 지나도 불꽃은 여전히 할 일 목록에 남아 있어요. 이를 피하는 방법은 앱에서 가장 간단한 것인데, 오늘 밤 30초면 충분합니다.",
          "홈 화면에 보면, 이미 오늘 밤의 데이트가 준비된 하나의 카드가 있어요. 질문도 없고, 스크롤할 필요도 없습니다. 분위기(아늑한, 모험적인, 장난기 가득한, 힐링)를 한 번만 탭하면 AI가 오늘 저녁에 실제로 즐길 수 있는 데이트를 만들어 드려요. 핵심은 계획을 없애는 것이지, 또 다른 할 일을 추가하는 게 아니에요.",
          "지금 바로 앱을 열어보세요. 오늘 밤에 맞는 분위기를 탭하고, 카드를 읽어보세요. 마음에 딱 맞지 않는다면 \"Show another\"를 누르세요. AI가 다른 분위기로 바꿔주니 두 번째는 보통 잘 맞을 거예요. 마음에 드는 것을 찾으면 \"Send to partner\"를 탭하세요. 그러면 상대방에게 아름다운 축하 화면이 기다리고 있어요. 이것이 전부입니다.",
          "주말까지 아끼지 마세요. 오늘 밤이 완벽한 첫 데이트인 이유는 진입 장벽은 낮고, 놀라움은 크기 때문이에요. 아래를 탭하고, 분위기를 고르고, 파트너가 환해지는 모습을 지켜보세요. P.S. Tonight's Date를 처음 24시간 안에 사용한 커플들은 기다린 커플들보다 다음 달에 4배 더 많은 데이트를 계획합니다. 기다리는 쪽이 되지 마세요.",
        ],
      },
      zh: {
        subject: "今晚的约会已经在等你啦",
        cta_text: "打开今晚约会",
        body_paragraphs: [
          "你刚下载了SoulPlan，而大多数人都会掉进同一个陷阱：打开App，随便看看，关掉，想着“等会儿再来”。三周过去，火花还躺在待办清单里。避免这个陷阱的方法，恰恰是App里最简单的事——而且今晚只需30秒。",
          "主屏幕上有一张卡片，已经为你们俩预选好了今晚的约会。没有问卷，不用滑动。只需点一下心情（温馨、冒险、有趣或治愈），AI就会生成一个今晚就能用的约会方案。核心就是帮你省去规划，而不是增加又一个待办事项。",
          "现在就打开App，点一下符合今晚心情的选项，看看卡片内容。如果不合心意，就点“Show another”——AI会切换不同风格，通常第二次就能对上。找到喜欢的那张后，点“Send to partner”，对方就会收到一个漂亮的庆祝界面。整个过程就这么简单。",
          "别留到周末。今晚就是完美的第一次约会，因为门槛低，惊喜大。点下面，选个心情，看你的伴侣眼前一亮。P.S. 在最初24小时内使用Tonight's Date的伴侣，接下来一个月安排的约会次数是那些等待者的4倍。别做等待的那一对。",
        ],
      },
      nl: {
        subject: "Vanavond staat jullie date al klaar",
        cta_text: "Open Tonight's Date",
        body_paragraphs: [
          "Je hebt SoulPlan net gedownload, en de valkuil is voor bijna iedereen hetzelfde: open de app, blader door wat ideeën, sluit hem weer, en denkt er later wel aan terug te komen. Drie weken later staat de vonk nog steeds op het to-do-lijstje. De truc om dat te voorkomen is ook het allersimpelste in de app — en het kost je vanavond maar 30 seconden.",
          "Op het startscherm staat één enkele kaart met een date die al voor jullie is klaargezet. Geen vragenlijst. Geen scrollen. Gewoon één tik op een stemming (gezellig, avontuurlijk, speels of helend) en de AI bouwt een date die jullie vanavond echt kunnen doen. Het hele punt is om het plannen weg te nemen, niet om er een extra inbox bij te maken.",
          "Open de app nu. Tik op de stemming die bij vanavond past. Lees de kaart. Als het niet helemaal klikt, tik dan op \"Show another\" — de AI draait door verschillende sferen, dus de tweede past meestal wel. Zodra je de perfecte hebt gevonden, tik je op \"Send to partner\" en zij krijgen een prachtig feestelijk scherm te zien. Dat is de hele cyclus.",
          "Bewaar dit niet voor het weekend. Vanavond is de perfecte eerste date, omdat de drempel laag is en de verrassing groot. Tik hieronder, kies een stemming, en kijk hoe je partner oplicht. P.S. De stellen die Tonight's Date binnen de eerste 24 uur gebruiken, plannen de maand erop 4x vaker een date dan degenen die wachten. Wees niet degenen die wachten.",
        ],
      },
    },
  },

  pupshape: {
    name: "PupShape: Dog Weight Loss Plan",
    multilingual: false,
    appStoreUrl: "https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.mealplanner.foodofdogs.petmeal",
    emails: {
      en: {
        subject: "The one mistake 90% of dog owners make daily",
        cta_text: "Open Calorie Calculator Now",
        body_paragraphs: [
          "I was feeding my own dog, Max, and feeling that familiar pang of guilt. He'd look at me with those eyes, and I'd cave. An extra treat here, a bigger scoop there. I thought love meant more food. I was wrong. And it was slowly hurting him.",
          "Here's the truth nobody tells you: most overweight dogs aren't overfed on purpose. They're overfed by accident. Because pet food labels are confusing, and 'one cup' means nothing without knowing your dog's exact calorie needs. The gap between what you think you're feeding and what they actually need is where the weight piles on.",
          "Open PupShape right now. Don't even finish this email. Tap the 'Calorie Calculator' on the home screen. It's the fastest win in the app. In 30 seconds, you'll know the EXACT number of calories your dog should eat today. Not a guess. Not a label suggestion. The real number based on their breed, current weight, and goal. This one number changes everything.",
          "Tap the button below, open the Calorie Calculator, and get your dog's magic number. Do it now before the next meal. You'll feel a wave of relief knowing you're finally feeding the right amount. P.S. The biggest shock for most owners? Seeing how many 'healthy' treats actually blow the daily budget. That part stings, but fixing it adds years to their life.",
        ],
      },
    },
  },

  volume_booster: {
    name: "Volume Booster - Sound Booster",
    multilingual: true,
    appStoreUrl: "",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.volume.booster.free.pro",
    emails: {
      en: {
        subject: "The sound setting 95% of users miss completely",
        cta_text: "Boost Your Sound Now",
        body_paragraphs: [
          "You just downloaded Volume Booster. And right now, your phone is playing audio at maybe 60% of what it's actually capable of. Not because of your speakers. Because of one setting buried inside the app that most people scroll right past.",
          "Here's the thing: cranking your phone's volume slider to max does almost nothing for actual loudness. That's like turning up a broken speaker. The real trick is the Loudness Enhancer inside the app. It amplifies your audio signal BEFORE it hits the speaker, which means cleaner, louder, richer sound without distortion. Combined with the Bass Booster, your phone suddenly sounds like a completely different device.",
          "Open the app right now. You'll see the big volume knob on the main screen. But don't just spin it. Tap the equalizer icon first. Select your music genre preset - Pop, Rock, Electronic, whatever you listen to most. THEN crank the knob. The difference is night and day. You'll hear bass you didn't know your phone had.",
          "Tap the button below and try it with your favorite song. Just one song. You'll never go back to default audio again. P.S. Play something with heavy bass first. The reaction on your face will be worth it.",
        ],
      },
      es: {
        subject: "El ajuste de sonido que el 95% de usuarios ignora",
        cta_text: "Mejora Tu Sonido Ahora",
        body_paragraphs: [
          "Acabas de descargar Volume Booster. Y ahora mismo, tu tel\u00e9fono est\u00e1 reproduciendo audio a quiz\u00e1s el 60% de lo que realmente es capaz. No por los altavoces. Por un ajuste escondido dentro de la app que la mayor\u00eda pasa de largo.",
          "La verdad es que subir el volumen de tu tel\u00e9fono al m\u00e1ximo casi no hace nada por el volumen real. Es como subir un altavoz roto. El truco real es el Amplificador de Sonido dentro de la app. Amplifica la se\u00f1al de audio ANTES de que llegue al altavoz, lo que significa un sonido m\u00e1s limpio, m\u00e1s alto y m\u00e1s rico sin distorsi\u00f3n. Combinado con el Potenciador de Graves, tu tel\u00e9fono de repente suena como un dispositivo completamente nuevo.",
          "Abre la app ahora mismo. Ver\u00e1s el gran control de volumen en la pantalla principal. Pero no lo subas sin m\u00e1s. Primero toca el icono del ecualizador. Selecciona el preset de tu g\u00e9nero musical favorito - Pop, Rock, Electr\u00f3nica, lo que m\u00e1s escuches. LUEGO sube el volumen. La diferencia es abismal. Escuchar\u00e1s graves que no sab\u00edas que tu tel\u00e9fono ten\u00eda.",
          "Toca el bot\u00f3n y pru\u00e9balo con tu canci\u00f3n favorita. Solo una canci\u00f3n. Nunca volver\u00e1s al audio por defecto. P.D. Pon algo con muchos graves primero. La expresi\u00f3n de tu cara valdr\u00e1 la pena.",
        ],
      },
      fr: {
        subject: "Le r\u00e9glage audio que 95% des utilisateurs ratent",
        cta_text: "Am\u00e9liore Ton Son Maintenant",
        body_paragraphs: [
          "Tu viens de t\u00e9l\u00e9charger Volume Booster. Et l\u00e0, ton t\u00e9l\u00e9phone joue ta musique \u00e0 peut-\u00eatre 60% de ce qu'il peut vraiment faire. Pas \u00e0 cause des haut-parleurs. \u00c0 cause d'un r\u00e9glage cach\u00e9 dans l'appli que presque tout le monde ignore.",
          "Monter le volume de ton t\u00e9l\u00e9phone au max ne change presque rien au volume r\u00e9el. C'est comme monter le son d'une enceinte cass\u00e9e. Le vrai truc, c'est l'Amplificateur de Volume dans l'appli. Il amplifie le signal audio AVANT qu'il n'atteigne le haut-parleur. R\u00e9sultat : un son plus propre, plus fort et plus riche sans distorsion. Avec le Bass Booster en plus, ton t\u00e9l\u00e9phone sonne comme un appareil compl\u00e8tement diff\u00e9rent.",
          "Ouvre l'appli maintenant. Tu verras le gros bouton de volume sur l'\u00e9cran principal. Mais ne le tourne pas tout de suite. Appuie d'abord sur l'ic\u00f4ne de l'\u00e9galiseur. Choisis le preset qui correspond \u00e0 ta musique - Pop, Rock, \u00c9lectro, ce que tu \u00e9coutes le plus. PUIS monte le volume. La diff\u00e9rence est \u00e9norme. Tu entendras des basses que tu ne soup\u00e7onnais m\u00eame pas.",
          "Appuie sur le bouton et essaie avec ta chanson pr\u00e9f\u00e9r\u00e9e. Juste une chanson. Tu ne reviendras plus jamais au son par d\u00e9faut. P.S. Mets un morceau avec beaucoup de basses d'abord. Ta r\u00e9action vaudra le coup.",
        ],
      },
      zh: {
        subject: "\u4f60\u624b\u673a95%\u7684\u97f3\u8d28\u6f5c\u529b\u8fd8\u6ca1\u6709\u88ab\u89e3\u9501",
        cta_text: "\u7acb\u5373\u63d0\u5347\u97f3\u8d28",
        body_paragraphs: [
          "\u4f60\u521a\u4e0b\u8f7d\u4e86 Volume Booster\u3002\u73b0\u5728\uff0c\u4f60\u7684\u624b\u673a\u53ef\u80fd\u53ea\u53d1\u6325\u4e86\u5b9e\u9645\u97f3\u8d28\u80fd\u529b\u7684 60%\u3002\u4e0d\u662f\u56e0\u4e3a\u559c\u53ed\u4e0d\u884c\uff0c\u800c\u662f\u56e0\u4e3a\u5e94\u7528\u91cc\u6709\u4e00\u4e2a\u9690\u85cf\u8bbe\u7f6e\uff0c\u5927\u591a\u6570\u4eba\u90fd\u5fe7\u7565\u4e86\u3002",
          "\u8bf4\u5b9e\u8bdd\uff0c\u628a\u624b\u673a\u97f3\u91cf\u6ed1\u5757\u62c9\u5230\u6700\u5927\u51e0\u4e4e\u6ca1\u4ec0\u4e48\u7528\u3002\u8fd9\u5c31\u50cf\u628a\u574f\u4e86\u7684\u97f3\u7bb1\u97f3\u91cf\u8c03\u5230\u6700\u5927\u4e00\u6837\u3002\u771f\u6b63\u7684\u79d8\u8bc0\u662f\u5e94\u7528\u5185\u7684\u97f3\u91cf\u589e\u5f3a\u5668\u3002\u5b83\u5728\u97f3\u9891\u5230\u8fbe\u559c\u53ed\u4e4b\u524d\u5c31\u8fdb\u884c\u653e\u5927\uff0c\u58f0\u97f3\u66f4\u5e72\u51c0\u3001\u66f4\u54cd\u4eae\u3001\u66f4\u4e30\u5bcc\uff0c\u800c\u4e14\u6ca1\u6709\u5931\u771f\u3002\u518d\u914d\u5408\u4f4e\u97f3\u589e\u5f3a\uff0c\u4f60\u7684\u624b\u673a\u542c\u8d77\u6765\u5c31\u50cf\u6362\u4e86\u4e00\u90e8\u65b0\u8bbe\u5907\u3002",
          "\u73b0\u5728\u5c31\u6253\u5f00\u5e94\u7528\u3002\u4f60\u4f1a\u770b\u5230\u4e3b\u754c\u9762\u4e0a\u7684\u5927\u65cb\u94ae\u3002\u4f46\u522b\u6025\u7740\u8c03\u3002\u5148\u70b9\u51fb\u5747\u8861\u5668\u56fe\u6807\uff0c\u9009\u62e9\u4f60\u6700\u5e38\u542c\u7684\u97f3\u4e50\u98ce\u683c\u9884\u8bbe\u2014\u2014\u6d41\u884c\u3001\u6447\u6eda\u3001\u7535\u5b50\uff0c\u7136\u540e\u518d\u8c03\u65cb\u94ae\u3002\u5dee\u522b\u662f\u5929\u58e4\u4e4b\u522b\u3002\u4f60\u4f1a\u542c\u5230\u4ee5\u524d\u4ece\u672a\u611f\u53d7\u8fc7\u7684\u4f4e\u97f3\u3002",
          "\u70b9\u51fb\u4e0b\u65b9\u6309\u94ae\uff0c\u7528\u4f60\u6700\u559c\u6b22\u7684\u6b4c\u8bd5\u8bd5\u3002\u5c31\u4e00\u9996\u6b4c\u3002\u4f60\u518d\u4e5f\u4e0d\u4f1a\u60f3\u56de\u5230\u9ed8\u8ba4\u97f3\u8d28\u4e86\u3002P.S. \u5148\u653e\u4e00\u9996\u91cd\u4f4e\u97f3\u7684\u6b4c\u3002\u4f60\u8138\u4e0a\u7684\u8868\u60c5\u4f1a\u503c\u56de\u7968\u4ef7\u7684\u3002",
        ],
      },
      hi: {
        subject: "\u0935\u094b \u0938\u093e\u0909\u0902\u0921 \u0938\u0947\u091f\u093f\u0902\u0917 \u091c\u094b 95% \u092f\u0942\u091c\u0930\u094d\u0938 \u092e\u093f\u0938 \u0915\u0930 \u0926\u0947\u0924\u0947 \u0939\u0948\u0902",
        cta_text: "\u0905\u092d\u0940 \u0938\u093e\u0909\u0902\u0921 \u092c\u0942\u0938\u094d\u091f \u0915\u0930\u0947\u0902",
        body_paragraphs: [
          "\u0906\u092a\u0928\u0947 \u0905\u092d\u0940 Volume Booster \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0915\u093f\u092f\u093e \u0939\u0948\u0964 \u0914\u0930 \u0905\u092d\u0940 \u0906\u092a\u0915\u093e \u092b\u094b\u0928 \u0905\u092a\u0928\u0940 \u0905\u0938\u0932\u0940 \u0915\u094d\u0937\u092e\u0924\u093e \u0915\u093e \u0936\u093e\u092f\u0926 60% \u0939\u0940 \u0907\u0938\u094d\u0924\u0947\u092e\u093e\u0932 \u0915\u0930 \u0930\u0939\u093e \u0939\u0948\u0964 \u0938\u094d\u092a\u0940\u0915\u0930 \u0915\u0940 \u0935\u091c\u0939 \u0938\u0947 \u0928\u0939\u0940\u0902\u0964 \u090f\u092a \u0915\u0947 \u0905\u0902\u0926\u0930 \u090f\u0915 \u0939\u093f\u0921\u0928 \u0938\u0947\u091f\u093f\u0902\u0917 \u0939\u0948 \u091c\u094b \u091c\u094d\u092f\u093e\u0926\u093e\u0924\u0930 \u0932\u094b\u0917 \u0938\u094d\u0915\u093f\u092a \u0915\u0930 \u0926\u0947\u0924\u0947 \u0939\u0948\u0902\u0964",
          "\u0938\u091a \u092f\u0939 \u0939\u0948 \u0915\u093f \u092b\u094b\u0928 \u0915\u093e \u0935\u0949\u0932\u094d\u092f\u0942\u092e \u092e\u0948\u0915\u094d\u0938 \u0915\u0930\u0928\u0947 \u0938\u0947 \u0905\u0938\u0932\u0940 \u0932\u093e\u0909\u0921\u0928\u0947\u0938 \u092a\u0930 \u0915\u094b\u0908 \u092b\u0930\u094d\u0915 \u0928\u0939\u0940\u0902 \u092a\u0921\u093c\u0924\u093e\u0964 \u092f\u0939 \u090f\u0915 \u091f\u0942\u091f\u0947 \u0939\u0941\u090f \u0938\u094d\u092a\u0940\u0915\u0930 \u0915\u094b \u092e\u0948\u0915\u094d\u0938 \u0915\u0930\u0928\u0947 \u091c\u0948\u0938\u093e \u0939\u0948\u0964 \u0905\u0938\u0932\u0940 \u091f\u094d\u0930\u093f\u0915 \u0939\u0948 \u090f\u092a \u0915\u0947 \u0905\u0902\u0926\u0930 \u0915\u093e Loudness Enhancer\u0964 \u092f\u0939 \u0911\u0921\u093f\u092f\u094b \u0938\u093f\u0917\u094d\u0928\u0932 \u0915\u094b \u0938\u094d\u092a\u0940\u0915\u0930 \u0924\u0915 \u092a\u0939\u0941\u0902\u091a\u0928\u0947 \u0938\u0947 \u092a\u0939\u0932\u0947 \u0939\u0940 \u0905\u0902\u092a\u094d\u0932\u0940\u092b\u093e\u0908 \u0915\u0930\u0924\u093e \u0939\u0948\u0964 \u0928\u0924\u0940\u091c\u093e: \u0938\u093e\u092b, \u0924\u0947\u091c \u0914\u0930 \u092d\u0930\u092a\u0942\u0930 \u0906\u0935\u093e\u091c\u0964 Bass Booster \u0915\u0947 \u0938\u093e\u0925 \u092e\u093f\u0932\u093e\u0915\u0930 \u0924\u094b \u092b\u094b\u0928 \u0928\u092f\u093e \u0932\u0917\u0924\u093e \u0939\u0948\u0964",
          "\u0905\u092d\u0940 \u090f\u092a \u0916\u094b\u0932\u0947\u0902\u0964 \u092e\u0947\u0928 \u0938\u094d\u0915\u094d\u0930\u0940\u0928 \u092a\u0930 \u092c\u0921\u093c\u093e \u0935\u0949\u0932\u094d\u092f\u0942\u092e \u0928\u0949\u092c \u0926\u093f\u0916\u0947\u0917\u093e\u0964 \u0932\u0947\u0915\u093f\u0928 \u0938\u0940\u0927\u0947 \u0928 \u0918\u0941\u092e\u093e\u090f\u0902\u0964 \u092a\u0939\u0932\u0947 \u0907\u0915\u094d\u0935\u0932\u093e\u0907\u091c\u0930 \u0906\u0907\u0915\u0949\u0928 \u092a\u0930 \u091f\u0948\u092a \u0915\u0930\u0947\u0902\u0964 \u0905\u092a\u0928\u093e \u092b\u0947\u0935\u0930\u093f\u091f \u092e\u094d\u092f\u0942\u091c\u093f\u0915 \u091c\u0949\u0928\u0930 \u092a\u094d\u0930\u0940\u0938\u0947\u091f \u091a\u0941\u0928\u0947\u0902 - Pop, Rock, Electronic\u0964 \u092b\u093f\u0930 \u0928\u0949\u092c \u0918\u0941\u092e\u093e\u090f\u0902\u0964 \u092b\u0930\u094d\u0915 \u0930\u093e\u0924-\u0926\u093f\u0928 \u0915\u093e \u0939\u0948\u0964 \u0906\u092a\u0915\u094b \u0935\u094b \u092c\u0947\u0938 \u0938\u0941\u0928\u093e\u0908 \u0926\u0947\u0917\u093e \u091c\u094b \u092a\u0939\u0932\u0947 \u0915\u092d\u0940 \u0928\u0939\u0940\u0902 \u0938\u0941\u0928\u093e\u0964",
          "\u0928\u0940\u091a\u0947 \u092c\u091f\u0928 \u091f\u0948\u092a \u0915\u0930\u0947\u0902 \u0914\u0930 \u0905\u092a\u0928\u0947 \u092b\u0947\u0935\u0930\u093f\u091f \u0917\u093e\u0928\u0947 \u0915\u0947 \u0938\u093e\u0925 \u091f\u094d\u0930\u093e\u0908 \u0915\u0930\u0947\u0902\u0964 \u092c\u0938 \u090f\u0915 \u0917\u093e\u0928\u093e\u0964 \u0906\u092a \u0915\u092d\u0940 \u0921\u093f\u092b\u0949\u0932\u094d\u091f \u0911\u0921\u093f\u092f\u094b \u092a\u0930 \u0935\u093e\u092a\u0938 \u0928\u0939\u0940\u0902 \u091c\u093e\u0928\u093e \u091a\u093e\u0939\u0947\u0902\u0917\u0947\u0964 P.S. \u092a\u0939\u0932\u0947 \u0915\u094b\u0908 \u092d\u093e\u0930\u0940 \u092c\u0947\u0938 \u0935\u093e\u0932\u093e \u0917\u093e\u0928\u093e \u091a\u0932\u093e\u090f\u0902\u0964 \u0906\u092a\u0915\u0947 \u091a\u0947\u0939\u0930\u0947 \u0915\u093e \u090f\u0915\u094d\u0938\u092a\u094d\u0930\u0947\u0936\u0928 \u0926\u0947\u0916\u0928\u0947 \u0932\u093e\u092f\u0915 \u0939\u094b\u0917\u093e\u0964",
        ],
      },
      pt: {
        subject: "A configura\u00e7\u00e3o de som que 95% dos usu\u00e1rios perdem",
        cta_text: "Melhore Seu Som Agora",
        body_paragraphs: [
          "Voc\u00ea acabou de baixar o Volume Booster. E agora, seu celular est\u00e1 tocando \u00e1udio a talvez 60% do que realmente consegue. N\u00e3o por causa dos alto-falantes. Por causa de uma configura\u00e7\u00e3o escondida no app que a maioria ignora completamente.",
          "A verdade \u00e9 que aumentar o volume do celular no m\u00e1ximo quase n\u00e3o faz diferen\u00e7a no volume real. \u00c9 como aumentar o som de uma caixa quebrada. O truque real \u00e9 o Amplificador de Volume dentro do app. Ele amplifica o sinal de \u00e1udio ANTES de chegar ao alto-falante, resultando em som mais limpo, mais alto e mais rico sem distor\u00e7\u00e3o. E com o Bass Booster, seu celular soa como um aparelho completamente novo.",
          "Abra o app agora. Voc\u00ea vai ver o grande bot\u00e3o de volume na tela principal. Mas n\u00e3o aumente direto. Primeiro, toque no \u00edcone do equalizador. Selecione o preset do seu g\u00eanero musical favorito - Pop, Rock, Eletr\u00f4nica. DEPOIS aumente o volume. A diferen\u00e7a \u00e9 absurda. Voc\u00ea vai ouvir graves que nem sabia que seu celular tinha.",
          "Toque no bot\u00e3o abaixo e teste com sua m\u00fasica favorita. S\u00f3 uma m\u00fasica. Voc\u00ea nunca mais vai querer voltar ao \u00e1udio padr\u00e3o. P.S. Coloque algo com bastante grave primeiro. Sua rea\u00e7\u00e3o vai valer a pena.",
        ],
      },
      ar: {
        subject: "\u0633\u0631\u0651\u064a \u0627\u0644\u0635\u063a\u064a\u0631 \u0627\u0644\u0630\u064a \u064a\u062c\u0639\u0644 \u0647\u0627\u062a\u0641\u0643 \u064a\u0647\u062a\u0632 \u0645\u0646 \u0627\u0644\u0642\u0648\u0629",
        cta_text: "\u0627\u0636\u063a\u0637 \u0644\u062a\u0639\u0632\u064a\u0632 \u0627\u0644\u0635\u0648\u062a \u0627\u0644\u0622\u0646",
        body_paragraphs: [
          "\u0643\u0646\u062a \u0623\u0633\u062a\u0645\u0639 \u0644\u0623\u063a\u0646\u064a\u0629 \u0627\u0644\u0645\u0641\u0636\u0644\u0629 \u0628\u0627\u0644\u0623\u0645\u0633 \u0648\u0641\u062c\u0623\u0629... \u0634\u0639\u0631\u062a \u0623\u0646 \u0634\u064a\u0626\u0627\u064b \u0645\u0627 \u0646\u0627\u0642\u0635. \u0643\u0623\u0646 \u0627\u0644\u0645\u0648\u0633\u064a\u0642\u0649 \u062a\u0623\u062a\u064a \u0645\u0646 \u0628\u0639\u064a\u062f. \u062b\u0645 \u0641\u0639\u0644\u062a \u0634\u064a\u0626\u0627\u064b \u0628\u0633\u064a\u0637\u0627\u064b \u063a\u064a\u0651\u0631 \u0643\u0644 \u0634\u064a\u0621.",
          "\u0627\u0644\u0645\u0634\u0643\u0644\u0629 \u0644\u064a\u0633\u062a \u0641\u064a \u0633\u0645\u0627\u0639\u0627\u062a \u0647\u0627\u062a\u0641\u0643. \u0627\u0644\u0645\u0634\u0643\u0644\u0629 \u0623\u0646 \u0627\u0644\u0646\u0638\u0627\u0645 \u064a\u062d\u062f\u0651 \u0645\u0646 \u0642\u0648\u062a\u0647 \u062e\u0648\u0641\u0627\u064b \u0645\u0646 \u0627\u0644\u062a\u0644\u0641. \u0644\u0643\u0646 \u0647\u0646\u0627\u0643 \u0637\u0631\u064a\u0642\u0629 \u0622\u0645\u0646\u0629 \u0644\u062a\u062c\u0627\u0648\u0632 \u0647\u0630\u0627 \u0627\u0644\u062d\u062f. \u0641\u064a 30 \u062b\u0627\u0646\u064a\u0629 \u0641\u0642\u0637.",
          "\u0643\u0644 \u0645\u0627 \u0639\u0644\u064a\u0643 \u0647\u0648 \u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642 \u0648\u0627\u0644\u0636\u063a\u0637 \u0639\u0644\u0649 \u0632\u0631 '\u062a\u0639\u0632\u064a\u0632 \u0627\u0644\u0635\u0648\u062a' \u0627\u0644\u0631\u0626\u064a\u0633\u064a. \u0644\u0627 \u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0645\u0639\u0642\u062f\u0629. \u0645\u062c\u0631\u062f \u0636\u063a\u0637\u0629 \u0648\u0627\u062d\u062f\u0629 \u0633\u062a\u0634\u0639\u0631 \u0645\u0639\u0647\u0627 \u0648\u0643\u0623\u0646\u0643 \u0627\u0634\u062a\u0631\u064a\u062a \u0647\u0627\u062a\u0641\u0627\u064b \u062c\u062f\u064a\u062f\u0627\u064b. \u062c\u0631\u0628\u0647\u0627 \u0627\u0644\u0622\u0646 \u0645\u0639 \u0623\u064a \u0623\u063a\u0646\u064a\u0629.",
          "\u0627\u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642 \u0627\u0644\u0622\u0646 \u0648\u0627\u0636\u063a\u0637 \u0639\u0644\u0649 \u0627\u0644\u0632\u0631 \u0627\u0644\u0628\u0631\u062a\u0642\u0627\u0644\u064a \u0627\u0644\u0643\u0628\u064a\u0631. \u0633\u062a\u0641\u0647\u0645 \u0645\u0627 \u0623\u0642\u0635\u062f\u0647 \u0641\u064a \u0623\u0648\u0644 10 \u062b\u0648\u0627\u0646\u064a. P.S: \u0627\u0644\u0623\u063a\u0644\u0628\u064a\u0629 \u064a\u0628\u062d\u062b\u0648\u0646 \u0639\u0646 \u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0645\u062a\u0642\u062f\u0645\u0629 \u0648\u064a\u0636\u064a\u0639\u0648\u0646 \u0647\u0630\u0647 \u0627\u0644\u0645\u064a\u0632\u0629 \u0627\u0644\u0628\u0633\u064a\u0637\u0629 \u0627\u0644\u062a\u064a \u062a\u063a\u064a\u0631 \u0627\u0644\u062a\u062c\u0631\u0628\u0629 \u0628\u0627\u0644\u0643\u0627\u0645\u0644.",
        ],
      },
      ru: {
        subject: "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 \u0437\u0432\u0443\u043a\u0430, \u043a\u043e\u0442\u043e\u0440\u0443\u044e 95% \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439 \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430\u044e\u0442",
        cta_text: "\u0423\u043b\u0443\u0447\u0448\u0438 \u0437\u0432\u0443\u043a \u0441\u0435\u0439\u0447\u0430\u0441",
        body_paragraphs: [
          "\u0422\u044b \u0442\u043e\u043b\u044c\u043a\u043e \u0447\u0442\u043e \u0441\u043a\u0430\u0447\u0430\u043b Volume Booster. \u0418 \u043f\u0440\u044f\u043c\u043e \u0441\u0435\u0439\u0447\u0430\u0441 \u0442\u0432\u043e\u0439 \u0442\u0435\u043b\u0435\u0444\u043e\u043d \u0432\u043e\u0441\u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0438\u0442 \u0437\u0432\u0443\u043a \u043d\u0430 60% \u043e\u0442 \u0441\u0432\u043e\u0438\u0445 \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u0435\u0439. \u041d\u0435 \u0438\u0437-\u0437\u0430 \u0434\u0438\u043d\u0430\u043c\u0438\u043a\u043e\u0432. \u0418\u0437-\u0437\u0430 \u043e\u0434\u043d\u043e\u0439 \u0441\u043a\u0440\u044b\u0442\u043e\u0439 \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u0432 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0438, \u043a\u043e\u0442\u043e\u0440\u0443\u044e \u0431\u043e\u043b\u044c\u0448\u0438\u043d\u0441\u0442\u0432\u043e \u043f\u0440\u043e\u043b\u0438\u0441\u0442\u044b\u0432\u0430\u0435\u0442.",
          "\u041f\u0440\u0430\u0432\u0434\u0430 \u0432 \u0442\u043e\u043c, \u0447\u0442\u043e \u0432\u044b\u043a\u0440\u0443\u0442\u0438\u0442\u044c \u0433\u0440\u043e\u043c\u043a\u043e\u0441\u0442\u044c \u043d\u0430 \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c \u043f\u043e\u0447\u0442\u0438 \u043d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u0434\u0430\u0451\u0442. \u042d\u0442\u043e \u043a\u0430\u043a \u043a\u0440\u0443\u0442\u0438\u0442\u044c \u0441\u043b\u043e\u043c\u0430\u043d\u043d\u0443\u044e \u043a\u043e\u043b\u043e\u043d\u043a\u0443 \u0434\u043e \u0443\u043f\u043e\u0440\u0430. \u041d\u0430\u0441\u0442\u043e\u044f\u0449\u0438\u0439 \u0441\u0435\u043a\u0440\u0435\u0442 \u2014 \u044d\u0442\u043e \u0423\u0441\u0438\u043b\u0438\u0442\u0435\u043b\u044c \u0413\u0440\u043e\u043c\u043a\u043e\u0441\u0442\u0438 \u0432\u043d\u0443\u0442\u0440\u0438 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f. \u041e\u043d \u0443\u0441\u0438\u043b\u0438\u0432\u0430\u0435\u0442 \u0430\u0443\u0434\u0438\u043e\u0441\u0438\u0433\u043d\u0430\u043b \u0414\u041e \u0434\u0438\u043d\u0430\u043c\u0438\u043a\u043e\u0432. \u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442: \u0447\u0438\u0441\u0442\u044b\u0439, \u043c\u043e\u0449\u043d\u044b\u0439, \u043d\u0430\u0441\u044b\u0449\u0435\u043d\u043d\u044b\u0439 \u0437\u0432\u0443\u043a \u0431\u0435\u0437 \u0438\u0441\u043a\u0430\u0436\u0435\u043d\u0438\u0439. \u0410 \u0441 Bass Booster \u0442\u0432\u043e\u0439 \u0442\u0435\u043b\u0435\u0444\u043e\u043d \u0437\u0432\u0443\u0447\u0438\u0442 \u043a\u0430\u043a \u0441\u043e\u0432\u0435\u0440\u0448\u0435\u043d\u043d\u043e \u0434\u0440\u0443\u0433\u043e\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e.",
          "\u041e\u0442\u043a\u0440\u043e\u0439 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u043f\u0440\u044f\u043c\u043e \u0441\u0435\u0439\u0447\u0430\u0441. \u041d\u0430 \u0433\u043b\u0430\u0432\u043d\u043e\u043c \u044d\u043a\u0440\u0430\u043d\u0435 \u0443\u0432\u0438\u0434\u0438\u0448\u044c \u0431\u043e\u043b\u044c\u0448\u0443\u044e \u0440\u0443\u0447\u043a\u0443 \u0433\u0440\u043e\u043c\u043a\u043e\u0441\u0442\u0438. \u041d\u043e \u043d\u0435 \u043a\u0440\u0443\u0442\u0438 \u0441\u0440\u0430\u0437\u0443. \u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043d\u0430\u0436\u043c\u0438 \u043d\u0430 \u0438\u043a\u043e\u043d\u043a\u0443 \u044d\u043a\u0432\u0430\u043b\u0430\u0439\u0437\u0435\u0440\u0430. \u0412\u044b\u0431\u0435\u0440\u0438 \u043f\u0440\u0435\u0441\u0435\u0442 \u043f\u043e\u0434 \u0441\u0432\u043e\u044e \u043c\u0443\u0437\u044b\u043a\u0443 \u2014 \u041f\u043e\u043f, \u0420\u043e\u043a, \u042d\u043b\u0435\u043a\u0442\u0440\u043e\u043d\u0438\u043a\u0430. \u0418 \u0422\u041e\u041b\u042c\u041a\u041e \u041f\u041e\u0422\u041e\u041c \u043a\u0440\u0443\u0442\u0438 \u0433\u0440\u043e\u043c\u043a\u043e\u0441\u0442\u044c. \u0420\u0430\u0437\u043d\u0438\u0446\u0430 \u043a\u043e\u043b\u043e\u0441\u0441\u0430\u043b\u044c\u043d\u0430\u044f. \u0422\u044b \u0443\u0441\u043b\u044b\u0448\u0438\u0448\u044c \u0431\u0430\u0441\u044b, \u043e \u043a\u043e\u0442\u043e\u0440\u044b\u0445 \u0434\u0430\u0436\u0435 \u043d\u0435 \u043f\u043e\u0434\u043e\u0437\u0440\u0435\u0432\u0430\u043b.",
          "\u041d\u0430\u0436\u043c\u0438 \u043a\u043d\u043e\u043f\u043a\u0443 \u043d\u0438\u0436\u0435 \u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0441 \u043b\u044e\u0431\u0438\u043c\u043e\u0439 \u043f\u0435\u0441\u043d\u0435\u0439. \u0412\u0441\u0435\u0433\u043e \u043e\u0434\u043d\u0430 \u043f\u0435\u0441\u043d\u044f. \u041d\u0430\u0437\u0430\u0434 \u043a \u0441\u0442\u0430\u043d\u0434\u0430\u0440\u0442\u043d\u043e\u043c\u0443 \u0437\u0432\u0443\u043a\u0443 \u0442\u044b \u0443\u0436\u0435 \u043d\u0435 \u0432\u0435\u0440\u043d\u0451\u0448\u044c\u0441\u044f. P.S. \u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0432\u043a\u043b\u044e\u0447\u0438 \u0447\u0442\u043e-\u043d\u0438\u0431\u0443\u0434\u044c \u0441 \u043c\u043e\u0449\u043d\u044b\u043c \u0431\u0430\u0441\u043e\u043c. \u0422\u0432\u043e\u0451 \u043b\u0438\u0446\u043e \u0432 \u044d\u0442\u043e\u0442 \u043c\u043e\u043c\u0435\u043d\u0442 \u0431\u0443\u0434\u0435\u0442 \u0431\u0435\u0441\u0446\u0435\u043d\u043d\u044b\u043c.",
        ],
      },
    },
  },

  horse_racing: {
    name: "Horse Racing AI Predictor",
    multilingual: true,
    appStoreUrl: "",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.horse.racing.ai.predictor",
    emails: {
      en: {
        subject: "Your first race prediction is ready — here's what to do",
        cta_text: "See Today's Predictions",
        body_paragraphs: [
          "You just joined thousands of racing fans who stopped relying on gut feeling and started using data. Horse Racing AI Predictor analyzed today's card — form, track conditions, jockey stats, trainer patterns — and your first prediction is waiting inside the app.",
          "Here's what makes this different: you don't just get a tip. You get a confidence score. It's the difference between 'this horse might place' and 'this horse wins 72% of the time under these exact conditions.' One number. Built from more data than any tipster could process in a week.",
          "Open the app now. Tap today's race card on the home screen. Look at the AI prediction and the confidence score. It takes 10 seconds. Before the first race starts, you'll know something most punters don't.",
          "Your first prediction is ready. Open the app and check today's top pick. P.S. Users who check predictions before the first race are 3x more likely to spot value early. Don't miss the opening odds.",
        ],
      },
      ar: {
        subject: "\u062a\u0648\u0642\u0639\u0643 \u0627\u0644\u0623\u0648\u0644 \u0644\u0633\u0628\u0627\u0642 \u0627\u0644\u064a\u0648\u0645 \u062c\u0627\u0647\u0632",
        cta_text: "\u0634\u0627\u0647\u062f \u062a\u0648\u0642\u0639\u0627\u062a \u0627\u0644\u064a\u0648\u0645",
        body_paragraphs: [
          "\u0627\u0646\u0636\u0645\u0645\u062a \u0644\u0622\u0644\u0627\u0641 \u0645\u0634\u062c\u0639\u064a \u0633\u0628\u0627\u0642\u0627\u062a \u0627\u0644\u062e\u064a\u0644 \u0627\u0644\u0630\u064a\u0646 \u062a\u0648\u0642\u0641\u0648\u0627 \u0639\u0646 \u0627\u0644\u0627\u0639\u062a\u0645\u0627\u062f \u0639\u0644\u0649 \u0627\u0644\u062d\u062f\u0633 \u0648\u0628\u062f\u0623\u0648\u0627 \u064a\u0633\u062a\u062e\u062f\u0645\u0648\u0646 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a. \u0627\u0644\u0630\u0643\u0627\u0621 \u0627\u0644\u0627\u0635\u0637\u0646\u0627\u0639\u064a \u062d\u0644\u0644 \u0633\u0628\u0627\u0642\u0627\u062a \u0627\u0644\u064a\u0648\u0645 \u0648\u062a\u0648\u0642\u0639\u0643 \u0627\u0644\u0623\u0648\u0644 \u062c\u0627\u0647\u0632.",
          "\u0627\u0644\u0641\u0631\u0642 \u0647\u0646\u0627: \u0644\u0627 \u062a\u062d\u0635\u0644 \u0641\u0642\u0637 \u0639\u0644\u0649 \u0646\u0635\u064a\u062d\u0629\u060c \u0628\u0644 \u062a\u062d\u0635\u0644 \u0639\u0644\u0649 \u062f\u0631\u062c\u0629 \u062b\u0642\u0629. \u0627\u0644\u0641\u0631\u0642 \u0628\u064a\u0646 '\u0647\u0630\u0627 \u0627\u0644\u062d\u0635\u0627\u0646 \u0642\u062f \u064a\u0641\u0648\u0632' \u0648'\u0647\u0630\u0627 \u0627\u0644\u062d\u0635\u0627\u0646 \u064a\u0641\u0648\u0632 72% \u0641\u064a \u0647\u0630\u0647 \u0627\u0644\u0638\u0631\u0648\u0641'.",
          "\u0627\u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642 \u0627\u0644\u0622\u0646. \u0627\u0636\u063a\u0637 \u0639\u0644\u0649 \u0633\u0628\u0627\u0642\u0627\u062a \u0627\u0644\u064a\u0648\u0645. \u0627\u0646\u0638\u0631 \u0625\u0644\u0649 \u0627\u0644\u062a\u0648\u0642\u0639 \u0648\u062f\u0631\u062c\u0629 \u0627\u0644\u062b\u0642\u0629. 10 \u062b\u0648\u0627\u0646\u064d \u0641\u0642\u0637.",
          "\u062a\u0648\u0642\u0639\u0643 \u0627\u0644\u0623\u0648\u0644 \u062c\u0627\u0647\u0632. \u0627\u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642 \u0648\u0634\u0627\u0647\u062f \u0627\u062e\u062a\u064a\u0627\u0631 \u0627\u0644\u064a\u0648\u0645.",
        ],
      },
      es: {
        subject: "Tu primera predicci\u00f3n de carrera est\u00e1 lista",
        cta_text: "Ver Predicciones de Hoy",
        body_paragraphs: [
          "Te uniste a miles de aficionados a las carreras que dejaron de confiar en la intuici\u00f3n y empezaron a usar datos. La IA analiz\u00f3 las carreras de hoy y tu primera predicci\u00f3n est\u00e1 esperando.",
          "No solo recibes un pron\u00f3stico. Recibes un score de confianza. La diferencia entre 'este caballo podr\u00eda ganar' y 'este caballo gana el 72% de las veces en estas condiciones exactas'.",
          "Abre la app ahora. Toca la cartelera de hoy. Mira la predicci\u00f3n y el score de confianza. Solo toma 10 segundos.",
          "Tu primera predicci\u00f3n est\u00e1 lista. Abre la app y revisa el favorito de hoy. P.D. Los usuarios que revisan predicciones antes de la primera carrera tienen 3x m\u00e1s probabilidades de encontrar valor temprano.",
        ],
      },
      fr: {
        subject: "Ta premi\u00e8re pr\u00e9diction de course est pr\u00eate",
        cta_text: "Voir les Pr\u00e9dictions du Jour",
        body_paragraphs: [
          "Tu viens de rejoindre des milliers de fans de courses hippiques qui ont arr\u00eat\u00e9 de se fier \u00e0 leur instinct et ont commenc\u00e9 \u00e0 utiliser les donn\u00e9es. L'IA a analys\u00e9 les courses d'aujourd'hui et ta premi\u00e8re pr\u00e9diction t'attend.",
          "La diff\u00e9rence ici : tu ne re\u00e7ois pas juste un tuyau. Tu obtiens un score de confiance. La diff\u00e9rence entre 'ce cheval pourrait gagner' et 'ce cheval gagne 72% du temps dans ces conditions exactes'.",
          "Ouvre l'appli maintenant. Regarde la carte du jour. V\u00e9rifie la pr\u00e9diction et le score de confiance. \u00c7a prend 10 secondes.",
          "Ta premi\u00e8re pr\u00e9diction est pr\u00eate. Ouvre l'appli et d\u00e9couvre le favori du jour. P.S. Les utilisateurs qui v\u00e9rifient les pr\u00e9dictions avant la premi\u00e8re course ont 3x plus de chances de rep\u00e9rer de la valeur t\u00f4t.",
        ],
      },
    },
  },
};

// ── HTML BUILDER ────────────────────────────────────────────
function buildHtml(
  emailData: EmailTemplate,
  appConfig: AppConfig,
  language: string,
  senderName: string,
  utmCtx?: { app: string; emailNum: string | number; cycle: number; language: string; ref: string; kind: string }
): string {
  const isRtl = language === "ar";
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const textAlign = isRtl ? "right" : "left";

  const greetings: Record<string, string> = {
    en: "Hey there,",
    ar: "\u0645\u0631\u062d\u0628\u064b\u0627\u060c",
    es: "Hola,",
    fr: "Salut,",
    zh: "\u4f60\u597d\uff0c",
    hi: "\u0928\u092e\u0938\u094d\u0924\u0947,",
    pt: "Ol\u00e1,",
    ru: "\u041f\u0440\u0438\u0432\u0435\u0442,",
    de: "Hallo,",
    tr: "Merhaba,",
    it: "Ciao,",
    pp: "Ol\u00e1,",
    id: "Halo,",
    nl: "Hallo,",
    pl: "Cze\u015b\u0107,",
    ja: "\u3053\u3093\u306b\u3061\u306f\u3001",
  };
  const signoffs: Record<string, string> = {
    en: "Talk soon,",
    ar: "\u0625\u0644\u0649 \u0627\u0644\u0644\u0642\u0627\u0621\u060c",
    es: "Hasta pronto,",
    fr: "\u00c0 bient\u00f4t,",
    zh: "\u56de\u5934\u804a\uff0c",
    hi: "\u091c\u0932\u094d\u0926 \u092c\u093e\u0924 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902,",
    pt: "At\u00e9 logo,",
    ru: "\u0414\u043e \u0441\u043a\u043e\u0440\u043e\u0433\u043e,",
    de: "Bis bald,",
    tr: "G\u00f6r\u00fc\u015f\u00fcrz,",
    it: "A presto,",
    pp: "At\u00e9 breve,",
    id: "Sampai jumpa,",
    nl: "Tot snel,",
    pl: "Do zobaczenia,",
    ja: "\u307e\u305f\u306d\u3001",
  };
  const footers: Record<string, string> = {
    en: `You're receiving this because you signed up for ${appConfig.name}.`,
    ar: `\u062a\u062a\u0644\u0642\u0649 \u0647\u0630\u0627 \u0627\u0644\u0628\u0631\u064a\u062f \u0644\u0623\u0646\u0643 \u0633\u062c\u0644\u062a \u0641\u064a ${appConfig.name}.`,
    es: `Recibes esto porque te registraste en ${appConfig.name}.`,
    fr: `Vous recevez ceci car vous vous \u00eates inscrit(e) \u00e0 ${appConfig.name}.`,
    zh: `\u60a8\u6536\u5230\u6b64\u90ae\u4ef6\u662f\u56e0\u4e3a\u60a8\u6ce8\u518c\u4e86 ${appConfig.name}\u3002`,
    hi: `\u0906\u092a\u0915\u094b \u092f\u0939 \u0907\u0938\u0932\u093f\u090f \u092e\u093f\u0932 \u0930\u0939\u093e \u0939\u0948 \u0915\u094d\u092f\u094b\u0902\u0915\u093f \u0906\u092a\u0928\u0947 ${appConfig.name} \u092e\u0947\u0902 \u0938\u093e\u0907\u0928 \u0905\u092a \u0915\u093f\u092f\u093e\u0964`,
    pt: `Voc\u00ea est\u00e1 recebendo isso porque se cadastrou no ${appConfig.name}.`,
    ru: `\u0412\u044b \u043f\u043e\u043b\u0443\u0447\u0438\u043b\u0438 \u044d\u0442\u043e \u043f\u0438\u0441\u044c\u043c\u043e, \u043f\u043e\u0442\u043e\u043c\u0443 \u0447\u0442\u043e \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043b\u0438\u0441\u044c \u0432 ${appConfig.name}.`,
    de: `Du erh\u00e4ltst diese E-Mail, weil du dich bei ${appConfig.name} angemeldet hast.`,
    tr: `Bu e-postay\u0131 ${appConfig.name} uygulamas\u0131na kay\u0131t oldu\u011funuz i\u00e7in al\u0131yorsunuz.`,
    it: `Ricevi questa email perch\u00e9 ti sei registrato su ${appConfig.name}.`,
    pp: `Recebe este email porque se registou no ${appConfig.name}.`,
    id: `Anda menerima email ini karena mendaftar di ${appConfig.name}.`,
    nl: `Je ontvangt dit bericht omdat je je hebt aangemeld voor ${appConfig.name}.`,
    pl: `Otrzymujesz t\u0119 wiadomo\u015b\u0107, poniewa\u017c zarejestroawa\u0142e\u015b si\u0119 w ${appConfig.name}.`,
    ja: `${appConfig.name}\u306b\u3054\u767b\u9332\u3044\u305f\u3060\u3044\u305f\u305f\u3081\u3001\u3053\u306e\u30e1\u30fc\u30eb\u3092\u304a\u9001\u308a\u3057\u3066\u3044\u307e\u3059\u3002`,
  };

  const greeting = greetings[language] || greetings.en;
  const signoff = signoffs[language] || signoffs.en;
  const footerText = footers[language] || footers.en;
  const ctaText = emailData.cta_text;

  let bodyHtml = "";
  emailData.body_paragraphs.forEach((p: string, i: number) => {
    const pHtml = p.replace(/\n/g, "<br>");
    if (i === 0) {
      bodyHtml += `<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;text-align:${textAlign};">${pHtml}</p>`;
    } else if (
      p.includes("P.S.") ||
      p.includes("P.S") ||
      p.includes("P.D.") ||
      p.includes("\u0645\u0644\u0627\u062d\u0638\u0629")
    ) {
      bodyHtml += `<div style="margin:32px 0 0;padding:16px 20px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;"><p style="margin:0;font-size:16px;color:#92400e;line-height:1.7;text-align:${textAlign};">${pHtml}</p></div>`;
    } else {
      bodyHtml += `<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:${textAlign};">${pHtml}</p>`;
    }
  });

  const appStoreHref = utmCtx ? withUtm(appConfig.appStoreUrl, utmCtx) : appConfig.appStoreUrl;
  const googlePlayHref = utmCtx ? withUtm(appConfig.googlePlayUrl, utmCtx) : appConfig.googlePlayUrl;
  // Only render a store button when its URL is set. Apps live on one store
  // only (e.g. Predictify NBA = Play only) show a single clean button; if just
  // one is present we drop the platform suffix so it reads naturally.
  const hasIos = !!appConfig.appStoreUrl;
  const hasAndroid = !!appConfig.googlePlayUrl;
  const iosLabel = hasIos && hasAndroid ? `${ctaText} (iOS)` : ctaText;
  const androidLabel = hasIos && hasAndroid ? `${ctaText} (Android)` : ctaText;
  const iosBtn = hasIos
    ? `<a href="${appStoreHref}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">\ud83d\udcf1 ${iosLabel}</a>`
    : "";
  const androidBtn = hasAndroid
    ? `<a href="${googlePlayHref}" style="display:inline-block;background:linear-gradient(135deg,#34d399 0%,#10b981 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">\ud83e\udd16 ${androidLabel}</a>`
    : "";
  const ctaHtml = `
    <div style="text-align:center;margin:36px 0;">
      ${iosBtn}
      ${androidBtn}
    </div>`;

  return `<!DOCTYPE html>
<html${dirAttr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:${textAlign};">
  <div style="margin-bottom:28px;">
    <p style="margin:0 0 24px;font-size:18px;color:#6b7280;text-align:${textAlign};">${greeting}</p>
    ${bodyHtml}
  </div>
  ${ctaHtml}
  <p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:${textAlign};">
    ${signoff}<br>
    <strong style="color:#1f2937;">${senderName}</strong>
  </p>
  <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
    <p style="margin:0 0 8px;font-size:13px;color:#d1d5db;">San Francisco, CA 94117, United States</p>
    <p style="margin:0;font-size:12px;color:#d1d5db;">${footerText}</p>
  </div>
</body>
</html>`;
}

// ── MAIN HANDLER ────────────────────────────────────────────
Deno.serve(async (req: Request) => {
  // CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers":
          "authorization, x-client-info, apikey, content-type",
      },
    });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const { email, app_id: rawAppId, language } = await req.json();

    if (!email || !rawAppId) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: email, app_id" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    // Normalize app_id aliases (check-new-users may send legacy names)
    const APP_ID_ALIASES: Record<string, string> = {
      redflag_scanner: "red_flag_scanner",
      fresh_start: "breakup_therapy",
    };
    const app_id = APP_ID_ALIASES[rawAppId] || rawAppId;

    const appConfig = APP_CONFIG[app_id];
    if (!appConfig) {
      return new Response(
        JSON.stringify({
          error: `Unknown app_id: ${app_id}`,
          valid_ids: Object.keys(APP_CONFIG),
        }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    if (!RESEND_API_KEY) {
      return new Response(
        JSON.stringify({ error: "RESEND_API_KEY not configured" }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    // Pick language (with fallback to en)
    let lang = language || "en";
    if (!appConfig.emails[lang]) {
      lang = "en";
    }

    const emailData = appConfig.emails[lang];
    const sender = getRandomSender();

    // Attribution context — same shape as retention/streak/matchday sends
    const ref = await userRef(email);
    const utmCtx = {
      app: app_id,
      emailNum: 1, // welcome is always email #1, cycle 1
      cycle: 1,
      language: lang,
      ref,
      kind: "welcome",
    };
    const html = buildHtml(emailData, appConfig, lang, sender.name, utmCtx);

    const tags = [
      { name: "app", value: sanitizeTagValue(app_id) },
      { name: "kind", value: "welcome" },
      { name: "email_num", value: "1" },
      { name: "cycle", value: "1" },
      { name: "language", value: sanitizeTagValue(lang) },
      { name: "segment", value: "new" },
    ];

    // Send via Resend
    const resendRes = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: `${appConfig.name} <${sender.email}>`,
        to: [email],
        subject: emailData.subject,
        html: html,
        reply_to: sender.email,
        tags,
        headers: { "X-Entity-Ref-ID": ref },
      }),
    });

    const resendData = await resendRes.json();

    if (!resendRes.ok) {
      console.error(`Resend error [${resendRes.status}]:`, resendData);

      // Detect hard bounce (invalid/non-existent address)
      const errStr = JSON.stringify(resendData).toLowerCase();
      const bounceIndicators = ['not found', 'does not exist', 'invalid', 'rejected', 'bounce', 'undeliverable', 'mailbox', 'unknown user'];
      const isBounce = (resendRes.status === 400 || resendRes.status === 422) && bounceIndicators.some(b => errStr.includes(b));

      if (isBounce) {
        console.log(`BOUNCED: ${email} — removing from system`);
        return new Response(
          JSON.stringify({ error: "Bounced", bounced: true, details: resendData }),
          { status: 400, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ error: "Failed to send email", details: resendData }),
        { status: 500, headers: { "Content-Type": "application/json" } }
      );
    }

    console.log(`Welcome email sent: ${email} (${appConfig.name}, ${lang})`);

    return new Response(
      JSON.stringify({
        success: true,
        message_id: resendData.id,
        app: appConfig.name,
        language: lang,
      }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  } catch (err) {
    console.error("Error:", err);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
});
