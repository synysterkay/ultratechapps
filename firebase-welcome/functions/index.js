const { onDocumentCreated } = require("firebase-functions/v2/firestore");
const { setGlobalOptions } = require("firebase-functions/v2");
const { defineSecret } = require("firebase-functions/params");
const admin = require("firebase-admin");
const https = require("https");

admin.initializeApp();

setGlobalOptions({ region: "us-central1" });

// ── CONFIG ──────────────────────────────────────────────────
const resendApiKey = defineSecret("RESEND_API_KEY");

// Sender rotation pool — same 7 domains as the main system
const SENDER_POOL = [
  // Keep in sync with supabase/functions/_shared/sender_pool.ts
  { email: "hello@kaynel.solutions", name: "Alex" },
  { email: "hello@aibettips.io", name: "Jordan" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
  { email: "hello@thesisgenerator.io", name: "Morgan" },
  { email: "hello@passedai.io", name: "Taylor" },
  { email: "hello@academicsatire.com", name: "Riley" },
  { email: "tips@predictify.fun", name: "Drew" },
];

// Pick a random sender for each welcome email (spreads reputation)
function getRandomSender() {
  return SENDER_POOL[Math.floor(Math.random() * SENDER_POOL.length)];
}

// ── APP CONFIG (mapped by Firebase project ID) ──────────────
const APP_CONFIG = {
  "predictify-3f30d": {
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
          "\u0627\u0636\u063a\u0637 \u0627\u0644\u0632\u0631 \u0623\u062f\u0646\u0627\u0647 \u0648\u0627\u0641\u062a\u062d \u0627\u0644\u062a\u0637\u0628\u064a\u0642. \u0627\u062e\u062a\u0628\u0631 \u062a\u0648\u0642\u0639\u0627\u064b \u0648\u0627\u062d\u062f\u0627\u064b \u0641\u0642\u0637. \u0634\u0627\u0647\u062f \u0643\u064a\u0641 \u062a\u0634\u0639\u0631 \u0648\u0623\u0646\u062a \u062a\u0639\u0631\u0641 \u0645\u0627 \u0644\u0627 \u064a\u0639\u0631\u0641\u0647 \u0623\u0635\u062f\u0642\u0627\u0624\u0643. P.S.: \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u0648\u0646 \u0627\u0644\u0630\u064a\u0646 \u064a\u062c\u0631\u0628\u0648\u0646 \u0647\u0630\u0647 \u0627\u0644\u0645\u064a\u0632\u0629 \u0641\u064a \u0623\u0648\u0644 5 \u062f\u0642\u0627\u0626\u0642 \u064a\u0628\u0642\u0648\u0646 \u0623\u0643\u062b\u0631 \u0628\u062b\u0644\u0627\u062b \u0645\u0631\u0627\u062a. \u0647\u0630\u0647 \u0644\u064a\u0633\u062a \u0635\u062f\u0641\u0629."
        ],
      },
      es: {
        subject: "Confesi\u00f3n: comet\u00ed un error con tu primera predicci\u00f3n",
        cta_text: "Abrir An\u00e1lisis T\u00e1ctico",
        body_paragraphs: [
          "Acabo de revisar tu perfil y me di cuenta de algo. Cuando te diste de alta, el sistema te asign\u00f3 una predicci\u00f3n 'gen\u00e9rica' para el pr\u00f3ximo partido grande. Es el error que cometemos con todos los nuevos, pero contigo es distinto. Tu historial de b\u00fasquedas ya dice mucho.",
          "La mayor\u00eda de la gente se queda con esa predicci\u00f3n superficial y pierde la oportunidad. La que importa est\u00e1 un nivel m\u00e1s abajo. La que cruza los \u00faltimos 5 enfrentamientos entre esos equipos con el estado f\u00edsico REAL de sus 3 jugadores clave esta semana. Los n\u00fameros no mienten, y hay uno que est\u00e1 a punto de explotar.",
          "Abre la app. Ve a la pesta\u00f1a 'Hoy'. Ver\u00e1s el partido destacado. No te quedes con el porcentaje de confianza grande. Toca ah\u00ed. Se desplegar\u00e1 el 'An\u00e1lisis T\u00e1ctico Instant\u00e1neo'. En 30 segundos ver\u00e1s la variable secreta que est\u00e1 moviendo la aguja para ese encuentro. Es la diferencia entre adivinar y saber.",
          "\u00c1brelo ahora. El partido empieza pronto y esa ventana de informaci\u00f3n \u00f3ptima se cierra. Haz clic, mira el an\u00e1lisis y ver\u00e1s de lo que hablo. La app ya no es la misma despu\u00e9s de eso. P.D.: Los primeros 100 que activen el 'An\u00e1lisis T\u00e1ctico' hoy obtendr\u00e1n acceso prioritario a una funci\u00f3n nueva la pr\u00f3xima semana. Solo para los que act\u00faan."
        ],
      },
      fr: {
        subject: "Le secret que 90% des fans de foot ignorent sur les matchs",
        cta_text: "Voir mon Score de Confiance",
        body_paragraphs: [
          "Tu sais ce sentiment quand tout le monde parie sur un r\u00e9sultat, mais que ton instinct te dit que \u00e7a va mal se passer ? Et que tu as raison ? C'est ce qui est arriv\u00e9 \u00e0 mon pote Sam hier. Tout le monde voyait une victoire facile pour le PSG. Lui, non. Et il avait raison.",
          "La raison ? Il ne se fiait pas \u00e0 son instinct. Il avait juste regard\u00e9 une seule chose dans Predictify : le Score de Confiance. En 30 secondes, il a vu que la pr\u00e9diction \"victoire facile\" n'avait qu'un score de 54%. Trop bas. Trop risqu\u00e9. Il a \u00e9vit\u00e9 un mauvais pari.",
          "Cette fonction, c'est ta jauge de v\u00e9rit\u00e9. Notre IA analyse des milliers de donn\u00e9es, puis te donne un pourcentage simple : \u00e0 quel point cette pr\u00e9diction est solide. C'est la premi\u00e8re chose que je regarde maintenant. \u00c7a t'\u00e9vite de suivre le troupeau b\u00eatement.",
          "Ouvre l'appli maintenant. Regarde le Score de Confiance pour le prochain match de ton \u00e9quipe. Tu verras tout de suite les pr\u00e9dictions qui valent le coup. C'est gratuit, et \u00e7a prend 30 secondes. P.S. : La version Premium d\u00e9bloque les analyses compl\u00e8tes derri\u00e8re chaque score. Mais commence par le gratuit, tu vas d\u00e9j\u00e0 avoir un s\u00e9rieux avantage."
        ],
      },
      pt: {
        subject: "O erro que 90% dos novos usu\u00e1rios cometem imediatamente",
        cta_text: "Ver Meu Score de Confian\u00e7a",
        body_paragraphs: [
          "Voc\u00ea acabou de baixar o Predictify. E est\u00e1 prestes a cometer o mesmo erro que todo mundo comete. Vai olhar um jogo, ver a previs\u00e3o e pensar 'talvez'. Mas est\u00e1 perdendo a \u00fanica coisa que torna nossa IA mais inteligente que seu instinto.",
          "A verdade \u00e9: uma previs\u00e3o sem confian\u00e7a \u00e9 s\u00f3 um chute. Nossa IA analisa milhares de dados\u2014xG, posse de bola, forma defensiva, hist\u00f3rico de confrontos\u2014mas a m\u00e1gica real \u00e9 o score de confian\u00e7a. \u00c9 a diferen\u00e7a entre 'Flamengo pode ganhar' e 'Flamengo vence 78% das vezes nessas condi\u00e7\u00f5es exatas.'",
          "Abra o app agora. V\u00e1 direto para qualquer jogo do Brasileir\u00e3o deste fim de semana. Olhe a previs\u00e3o. Depois olhe logo abaixo. V\u00ea aquela porcentagem? Esse \u00e9 seu score de confian\u00e7a. Em 30 segundos, voc\u00ea para de adivinhar e come\u00e7a a saber.",
          "Toque no bot\u00e3o. Abra o Predictify e encontre o score de confian\u00e7a no pr\u00f3ximo jogo. Muda tudo. P.S. Usu\u00e1rios que checam esse score no primeiro dia t\u00eam 3x mais chance de acertar na primeira semana."
        ],
      },
      de: {
        subject: "Der eine Fehler, den 90% der neuen Nutzer sofort machen",
        cta_text: "Meinen Konfidenz-Score sehen",
        body_paragraphs: [
          "Du hast gerade Predictify heruntergeladen. Und du bist dabei, den gleichen Fehler zu machen wie alle anderen. Du wirst dir ein Spiel ansehen, die Vorhersage sehen und denken 'vielleicht'. Aber du \u00fcbersiehst das Einzige, was unsere KI schlauer macht als dein Bauchgef\u00fchl.",
          "Die Wahrheit: Eine Vorhersage ohne Konfidenz ist nur ein Tipp. Unsere KI analysiert tausende Datenpunkte\u2014xG, Ballbesitz, Defensivform, direkte Duelle\u2014aber die echte Magie ist der Konfidenz-Score. Es ist der Unterschied zwischen 'Bayern k\u00f6nnte gewinnen' und 'Bayern gewinnt zu 78% unter genau diesen Bedingungen.'",
          "\u00d6ffne die App. Jetzt. Geh direkt zu einem Bundesliga-Spiel am Wochenende. Schau dir die Vorhersage an. Dann schau direkt darunter. Siehst du die Prozentzahl? Das ist dein Konfidenz-Score. In 30 Sekunden h\u00f6rst du auf zu raten und f\u00e4ngst an zu wissen.",
          "Tippe auf den Button. \u00d6ffne Predictify und finde den Konfidenz-Score f\u00fcr dein n\u00e4chstes Spiel. Es ver\u00e4ndert alles. P.S. Nutzer, die diesen Score am ersten Tag pr\u00fcfen, erkennen 3x h\u00e4ufiger einen Value Bet in der ersten Woche."
        ],
      },
      tr: {
        subject: "Yeni kullan\u0131c\u0131lar\u0131n %90'\u0131n\u0131n hemen yapt\u0131\u011f\u0131 tek hata",
        cta_text: "G\u00fcven Skorumu G\u00f6r",
        body_paragraphs: [
          "Predictify'i indirdin. Ve herkesin yapt\u0131\u011f\u0131 ayn\u0131 hatay\u0131 yapmak \u00fczeresin. Bir ma\u00e7a bakacak, tahmini g\u00f6recek ve 'belki' diyeceksin. Ama yapay zekam\u0131z\u0131 sezgilerinden daha ak\u0131ll\u0131 yapan tek \u015feyi ka\u00e7\u0131r\u0131yorsun.",
          "Ger\u00e7ek \u015fu: G\u00fcven skoru olmayan bir tahmin sadece bir tahmindir. Yapay zekam\u0131z binlerce veri noktas\u0131n\u0131 analiz eder\u2014xG, top kontrolu, savunma formu, kar\u015f\u0131la\u015fma ge\u00e7mi\u015fi. Ama esas b\u00fcy\u00fc g\u00fcven skorudur. 'Galatasaray kazanabilir' ile 'Galatasaray bu ko\u015fullarda %78 kazan\u0131r' aras\u0131ndaki fark budur.",
          "Uygulamay\u0131 a\u00e7. \u015eimdi. Bu hafta sonu herhangi bir S\u00fcper Lig ma\u00e7\u0131na git. Tahmini g\u00f6r. Sonra hemen alt\u0131na bak. O y\u00fczdeyi g\u00f6r\u00fcyor musun? G\u00fcven skorun bu. 30 saniyede tahmin etmeyi b\u0131rak\u0131p bilmeye ba\u015fl\u0131yorsun.",
          "Butona dokun. Predictify'i a\u00e7 ve bir sonraki ma\u00e7\u0131n g\u00fcven skorunu bul. Her \u015feyi de\u011fi\u015ftiriyor. P.S. Bu skoru ilk g\u00fcn kontrol eden kullan\u0131c\u0131lar\u0131n ilk haftada de\u011ferli bir bahis yakallama olas\u0131l\u0131\u011f\u0131 3 kat daha fazla."
        ],
      },
      it: {
        subject: "L'unico errore che il 90% dei nuovi utenti fa subito",
        cta_text: "Vedi il Mio Punteggio di Fiducia",
        body_paragraphs: [
          "Hai appena scaricato Predictify. E stai per fare lo stesso errore di tutti. Guarderai una partita, vedrai la previsione e penserai 'forse'. Ma ti stai perdendo l'unica cosa che rende la nostra IA pi\u00f9 intelligente del tuo istinto.",
          "La verit\u00e0: una previsione senza fiducia \u00e8 solo un'ipotesi. La nostra IA analizza migliaia di dati\u2014xG, possesso, forma difensiva, scontri diretti\u2014ma la vera magia \u00e8 il punteggio di fiducia. \u00c8 la differenza tra 'la Juventus potrebbe vincere' e 'la Juventus vince il 78% delle volte in queste condizioni esatte.'",
          "Apri l'app. Adesso. Vai a qualsiasi partita di Serie A di questo weekend. Guarda la previsione. Poi guarda subito sotto. Vedi quella percentuale? Quello \u00e8 il tuo punteggio di fiducia. In 30 secondi, smetti di tirare a indovinare e inizi a sapere.",
          "Tocca il pulsante. Apri Predictify e trova il punteggio di fiducia per la tua prossima partita. Cambia tutto. P.S. Gli utenti che controllano questo punteggio il primo giorno hanno 3 volte pi\u00f9 probabilit\u00e0 di trovare una value bet nella prima settimana."
        ],
      },
      pp: {
        subject: "O erro que 90% dos novos utilizadores cometem de imediato",
        cta_text: "Ver o Meu Score de Confian\u00e7a",
        body_paragraphs: [
          "Acabaste de descarregar o Predictify. E est\u00e1s prestes a cometer o mesmo erro que toda a gente. Vais olhar para um jogo, ver a previs\u00e3o e pensar 'talvez'. Mas est\u00e1s a perder a \u00fanica coisa que torna a nossa IA mais inteligente que o teu instinto.",
          "A verdade \u00e9: uma previs\u00e3o sem confian\u00e7a \u00e9 apenas um palpite. A nossa IA analisa milhares de dados\u2014xG, posse de bola, forma defensiva, hist\u00f3rico de confrontos diretos\u2014mas a verdadeira magia \u00e9 o score de confian\u00e7a. \u00c9 a diferen\u00e7a entre 'o Benfica pode ganhar' e 'o Benfica ganha 78% das vezes nestas condi\u00e7\u00f5es exatas.'",
          "Abre a app. Agora. Vai a qualquer jogo da Liga Portugal deste fim de semana. V\u00ea a previs\u00e3o. Depois olha logo abaixo. V\u00eas aquela percentagem? Esse \u00e9 o teu score de confian\u00e7a. Em 30 segundos, deixas de adivinhar e come\u00e7as a saber.",
          "Toca no bot\u00e3o. Abre o Predictify e encontra o score de confian\u00e7a no pr\u00f3ximo jogo. Muda tudo. P.S. Utilizadores que verificam este score no primeiro dia t\u00eam 3x mais hip\u00f3teses de acertar na primeira semana."
        ],
      },
      hi: {
        subject: "90% \u0928\u090f \u092f\u0942\u091c\u0930\u094d\u0938 \u091c\u094b \u0917\u0932\u0924\u0940 \u0924\u0941\u0930\u0902\u0924 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902",
        cta_text: "\u092e\u0947\u0930\u093e \u0915\u0949\u0928\u094d\u092b\u093f\u0921\u0947\u0902\u0938 \u0938\u094d\u0915\u094b\u0930 \u0926\u0947\u0916\u0947\u0902",
        body_paragraphs: [
          "\u0906\u092a\u0928\u0947 \u0905\u092d\u0940 Predictify \u0921\u093e\u0909\u0928\u0932\u094b\u0921 \u0915\u093f\u092f\u093e\u0964 \u0914\u0930 \u0906\u092a \u0935\u0939\u0940 \u0917\u0932\u0924\u0940 \u0915\u0930\u0928\u0947 \u0935\u093e\u0932\u0947 \u0939\u0948\u0902 \u091c\u094b \u0938\u092c \u0915\u0930\u0924\u0947 \u0939\u0948\u0902\u0964 \u0906\u092a \u090f\u0915 \u092e\u0948\u091a \u0926\u0947\u0916\u0947\u0902\u0917\u0947, \u092a\u094d\u0930\u0947\u0921\u093f\u0915\u094d\u0936\u0928 \u0926\u0947\u0916\u0947\u0902\u0917\u0947 \u0914\u0930 \u0938\u094b\u091a\u0947\u0902\u0917\u0947 '\u0936\u093e\u092f\u0926'\u0964 \u0932\u0947\u0915\u093f\u0928 \u0906\u092a \u0935\u094b \u090f\u0915 \u091a\u0940\u091c\u093c \u092e\u093f\u0938 \u0915\u0930 \u0930\u0939\u0947 \u0939\u0948\u0902 \u091c\u094b \u0939\u092e\u093e\u0930\u0940 AI \u0915\u094b \u0906\u092a\u0915\u0947 \u0905\u0902\u0926\u093e\u091c\u093c\u0947 \u0938\u0947 \u0938\u094d\u092e\u093e\u0930\u094d\u091f \u092c\u0928\u093e\u0924\u0940 \u0939\u0948\u0964",
          "\u0938\u091a \u092f\u0939 \u0939\u0948: \u092c\u093f\u0928\u093e \u0915\u0949\u0928\u094d\u092b\u093f\u0921\u0947\u0902\u0938 \u0915\u0947 \u092a\u094d\u0930\u0947\u0921\u093f\u0915\u094d\u0936\u0928 \u0938\u093f\u0930\u094d\u092b \u0905\u0902\u0926\u093e\u091c\u093c\u093e \u0939\u0948\u0964 \u0939\u092e\u093e\u0930\u0940 AI \u0939\u091c\u093c\u093e\u0930\u094b\u0902 \u0921\u0947\u091f\u093e \u092a\u0949\u0907\u0902\u091f\u094d\u0938 \u0915\u093e \u0935\u093f\u0936\u094d\u0932\u0947\u0937\u0923 \u0915\u0930\u0924\u0940 \u0939\u0948\u2014xG, \u092a\u0949\u0938\u0947\u0936\u0928, \u0921\u093f\u092b\u0947\u0902\u0938\u093f\u0935 \u092b\u0949\u0930\u094d\u092e, \u0906\u092e\u0928\u0947-\u0938\u093e\u092e\u0928\u0947\u0964 \u0932\u0947\u0915\u093f\u0928 \u0905\u0938\u0932\u0940 \u091c\u093e\u0926\u0942 \u0915\u0949\u0928\u094d\u092b\u093f\u0921\u0947\u0902\u0938 \u0938\u094d\u0915\u094b\u0930 \u0939\u0948\u0964 '\u092e\u0941\u0902\u092c\u0908 \u0938\u093f\u091f\u0940 \u091c\u0940\u0924 \u0938\u0915\u0924\u0940 \u0939\u0948' \u0914\u0930 '\u092e\u0941\u0902\u092c\u0908 \u0938\u093f\u091f\u0940 \u0907\u0928 \u0939\u093e\u0932\u093e\u0924 \u092e\u0947\u0902 78% \u091c\u0940\u0924\u0924\u0940 \u0939\u0948' \u092e\u0947\u0902 \u092b\u0930\u094d\u0915 \u0939\u0948\u0964",
          "\u0905\u092d\u0940 \u0905\u092a\u094d\u0932\u093f\u0915\u0947\u0936\u0928 \u0916\u094b\u0932\u0947\u0902\u0964 ISL \u092f\u093e IPL \u0938\u0940\u091c\u0928 \u0915\u0947 \u0915\u093f\u0938\u0940 \u092d\u0940 \u092e\u0948\u091a \u092a\u0930 \u091c\u093e\u090f\u0902\u0964 \u092a\u094d\u0930\u0947\u0921\u093f\u0915\u094d\u0936\u0928 \u0926\u0947\u0916\u0947\u0902\u0964 \u092b\u093f\u0930 \u0928\u0940\u091a\u0947 \u0926\u0947\u0916\u0947\u0902\u0964 \u0935\u094b \u092a\u0930\u094d\u0938\u0947\u0902\u091f\u0947\u091c \u0926\u093f\u0916 \u0930\u0939\u093e \u0939\u0948? \u092f\u0939\u0940 \u0906\u092a\u0915\u093e \u0915\u0949\u0928\u094d\u092b\u093f\u0921\u0947\u0902\u0938 \u0938\u094d\u0915\u094b\u0930 \u0939\u0948\u0964 30 \u0938\u0947\u0915\u0902\u0921 \u092e\u0947\u0902, \u0905\u0902\u0926\u093e\u091c\u093c\u093e \u0932\u0917\u093e\u0928\u093e \u092c\u0902\u0926\u0964",
          "\u092c\u091f\u0928 \u091f\u0948\u092a \u0915\u0930\u0947\u0902\u0964 Predictify \u0916\u094b\u0932\u0947\u0902 \u0914\u0930 \u0905\u0917\u0932\u0947 \u092e\u0948\u091a \u0915\u093e \u0915\u0949\u0928\u094d\u092b\u093f\u0921\u0947\u0902\u0938 \u0938\u094d\u0915\u094b\u0930 \u0926\u0947\u0916\u0947\u0902\u0964 \u0938\u092c \u092c\u0926\u0932 \u091c\u093e\u0924\u093e \u0939\u0948\u0964 P.S. \u092a\u0939\u0932\u0947 \u0926\u093f\u0928 \u092f\u0939 \u0938\u094d\u0915\u094b\u0930 \u091a\u0947\u0915 \u0915\u0930\u0928\u0947 \u0935\u093e\u0932\u0947 \u092f\u0942\u091c\u0930\u094d\u0938 \u092a\u0939\u0932\u0947 \u0939\u092b\u094d\u0924\u0947 \u092e\u0947\u0902 3 \u0917\u0941\u0928\u093e \u091c\u094d\u092f\u093e\u0926\u093e \u0938\u0939\u0940 \u0939\u094b\u0924\u0947 \u0939\u0948\u0902\u0964"
        ],
      },
      id: {
        subject: "Satu kesalahan yang 90% pengguna baru langsung lakukan",
        cta_text: "Lihat Skor Kepercayaan Saya",
        body_paragraphs: [
          "Kamu baru saja mengunduh Predictify. Dan kamu akan membuat kesalahan yang sama seperti orang lain. Kamu akan melihat pertandingan, melihat prediksi, dan berpikir 'mungkin'. Tapi kamu melewatkan satu hal yang membuat AI kami lebih pintar dari instingmu.",
          "Kenyataannya: prediksi tanpa kepercayaan hanyalah tebakan. AI kami menganalisis ribuan data\u2014xG, penguasaan bola, form pertahanan, head-to-head\u2014tapi keajaiban sebenarnya adalah skor kepercayaan. Ini bedanya antara 'Persib mungkin menang' dan 'Persib menang 78% di kondisi persis ini.'",
          "Buka aplikasinya. Sekarang. Langsung ke pertandingan Liga 1 weekend ini. Lihat prediksinya. Lalu lihat tepat di bawahnya. Lihat persentase itu? Itu skor kepercayaanmu. Dalam 30 detik, kamu berhenti menebak dan mulai tahu.",
          "Ketuk tombolnya. Buka Predictify dan temukan skor kepercayaan di pertandingan berikutnya. Ini mengubah segalanya. P.S. Pengguna yang mengecek skor ini di hari pertama 3x lebih mungkin menemukan value bet di minggu pertama."
        ],
      },
      nl: {
        subject: "De ene fout die 90% van nieuwe gebruikers direct maakt",
        cta_text: "Bekijk Mijn Vertrouwensscore",
        body_paragraphs: [
          "Je hebt net Predictify gedownload. En je staat op het punt dezelfde fout te maken als iedereen. Je gaat naar een wedstrijd kijken, de voorspelling zien en denken 'misschien'. Maar je mist het enige dat onze AI slimmer maakt dan je onderbuikgevoel.",
          "De waarheid: een voorspelling zonder vertrouwen is gewoon een gok. Onze AI analyseert duizenden datapunten\u2014xG, balbezit, defensieve vorm, onderlinge duels\u2014maar de echte magie is de vertrouwensscore. Het is het verschil tussen 'Ajax kan winnen' en 'Ajax wint 78% van de tijd onder precies deze omstandigheden.'",
          "Open de app. Nu. Ga naar een Eredivisie-wedstrijd dit weekend. Bekijk de voorspelling. Kijk dan direct eronder. Zie je dat percentage? Dat is je vertrouwensscore. In 30 seconden stop je met gokken en begin je met weten.",
          "Tik op de knop. Open Predictify en vind de vertrouwensscore voor je volgende wedstrijd. Het verandert alles. P.S. Gebruikers die deze score op dag \u00e9\u00e9n checken, vinden 3x vaker een value bet in de eerste week."
        ],
      },
      pl: {
        subject: "Jeden b\u0142\u0105d, kt\u00f3ry 90% nowych u\u017cytkownik\u00f3w robi natychmiast",
        cta_text: "Zobacz M\u00f3j Wynik Pewno\u015bci",
        body_paragraphs: [
          "W\u0142a\u015bnie pobra\u0142e\u015b Predictify. I zaraz pope\u0142nisz ten sam b\u0142\u0105d co wszyscy. Spojrzysz na mecz, zobaczysz prognoz\u0119 i pomy\u015blisz 'mo\u017ce'. Ale omijasz jedn\u0105 rzecz, kt\u00f3ra sprawia, \u017ce nasza AI jest m\u0105drzejsza od twojego instynktu.",
          "Prawda jest taka: prognoza bez pewno\u015bci to tylko zgadywanie. Nasza AI analizuje tysi\u0105ce punkt\u00f3w danych\u2014xG, posiadanie pi\u0142ki, form\u0119 defensywn\u0105, bezpo\u015brednie mecze\u2014ale prawdziwa magia to wynik pewno\u015bci. To r\u00f3\u017cnica mi\u0119dzy 'Legia mo\u017ce wygra\u0107' a 'Legia wygrywa w 78% przypadk\u00f3w w tych dok\u0142adnie warunkach.'",
          "Otw\u00f3rz aplikacj\u0119. Teraz. Id\u017a do dowolnego meczu Ekstraklasy w ten weekend. Sprawd\u017a prognoz\u0119. Potem sp\u00f3jrz tu\u017c pod ni\u0105. Widzisz ten procent? To tw\u00f3j wynik pewno\u015bci. W 30 sekund przestajesz zgadywa\u0107 i zaczynasz wiedzie\u0107.",
          "Kliknij przycisk. Otw\u00f3rz Predictify i znajd\u017a wynik pewno\u015bci dla nast\u0119pnego meczu. To zmienia wszystko. P.S. U\u017cytkownicy, kt\u00f3rzy sprawdzaj\u0105 ten wynik pierwszego dnia, maj\u0105 3x wi\u0119ksze szanse na trafienie value bet w pierwszym tygodniu."
        ],
      },
      ja: {
        subject: "\u65b0\u898f\u30e6\u30fc\u30b6\u30fc\u306e90%\u304c\u3059\u3050\u306b\u72af\u30591\u3064\u306e\u30df\u30b9",
        cta_text: "\u4fe1\u983c\u5ea6\u30b9\u30b3\u30a2\u3092\u898b\u308b",
        body_paragraphs: [
          "Predictify\u3092\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u3057\u305f\u3070\u304b\u308a\u3067\u3059\u306d\u3002\u305d\u3057\u3066\u3001\u4ed6\u306e\u307f\u3093\u306a\u3068\u540c\u3058\u30df\u30b9\u3092\u3057\u3088\u3046\u3068\u3057\u3066\u3044\u307e\u3059\u3002\u8a66\u5408\u3092\u898b\u3066\u3001\u4e88\u6e2c\u3092\u898b\u3066\u3001\u300c\u305f\u3076\u3093\u300d\u3068\u601d\u3046\u3067\u3057\u3087\u3046\u3002\u3067\u3082\u3001AI\u3092\u3042\u306a\u305f\u306e\u52d8\u3088\u308a\u8ce2\u304f\u3059\u308b\u305f\u3060\u4e00\u3064\u306e\u3053\u3068\u3092\u898b\u843d\u3068\u3057\u3066\u3044\u307e\u3059\u3002",
          "\u771f\u5b9f\uff1a\u4fe1\u983c\u5ea6\u306a\u3057\u306e\u4e88\u6e2c\u306f\u305f\u3060\u306e\u63a8\u6e2c\u3067\u3059\u3002AI\u306f\u6570\u5343\u306e\u30c7\u30fc\u30bf\u30dd\u30a4\u30f3\u30c8\u3092\u5206\u6790\u3057\u307e\u3059\u2014xG\u3001\u30dd\u30bc\u30c3\u30b7\u30e7\u30f3\u3001\u5b88\u5099\u30d5\u30a9\u30fc\u30e0\u3001\u76f4\u63a5\u5bfe\u6c7a\u3002\u3057\u304b\u3057\u672c\u5f53\u306e\u9b54\u6cd5\u306f\u4fe1\u983c\u5ea6\u30b9\u30b3\u30a2\u3067\u3059\u3002\u300c\u6d66\u548c\u304c\u52dd\u3064\u304b\u3082\u300d\u3068\u300c\u6d66\u548c\u304c\u3053\u306e\u6761\u4ef6\u3067\u306f78%\u52dd\u3064\u300d\u306e\u9055\u3044\u3067\u3059\u3002",
          "\u30a2\u30d7\u30ea\u3092\u958b\u3044\u3066\u304f\u3060\u3055\u3044\u3002\u4eca\u3059\u3050\u3002\u4eca\u9031\u672b\u306eJ\u30ea\u30fc\u30b0\u306e\u8a66\u5408\u306b\u884c\u3063\u3066\u304f\u3060\u3055\u3044\u3002\u4e88\u6e2c\u3092\u898b\u3066\u304f\u3060\u3055\u3044\u3002\u305d\u306e\u3059\u3050\u4e0b\u3092\u898b\u3066\u304f\u3060\u3055\u3044\u3002\u305d\u306e\u30d1\u30fc\u30bb\u30f3\u30c6\u30fc\u30b8\u304c\u898b\u3048\u307e\u3059\u304b\uff1f\u305d\u308c\u304c\u4fe1\u983c\u5ea6\u30b9\u30b3\u30a2\u3067\u3059\u300230\u79d2\u3067\u3001\u63a8\u6e2c\u304c\u7d42\u308f\u308a\u3001\u77e5\u308b\u3053\u3068\u304c\u59cb\u307e\u308a\u307e\u3059\u3002",
          "\u30dc\u30bf\u30f3\u3092\u30bf\u30c3\u30d7\u3057\u3066\u304f\u3060\u3055\u3044\u3002Predictify\u3092\u958b\u3044\u3066\u3001\u6b21\u306e\u8a66\u5408\u306e\u4fe1\u983c\u5ea6\u30b9\u30b3\u30a2\u3092\u898b\u3064\u3051\u3066\u304f\u3060\u3055\u3044\u3002\u3059\u3079\u3066\u304c\u5909\u308f\u308a\u307e\u3059\u3002P.S. \u521d\u65e5\u306b\u3053\u306e\u30b9\u30b3\u30a2\u3092\u30c1\u30a7\u30c3\u30af\u3057\u305f\u30e6\u30fc\u30b6\u30fc\u306f\u3001\u6700\u521d\u306e\u9031\u3067\u30d0\u30ea\u30e5\u30fc\u30d9\u30c3\u30c8\u3092\u898b\u3064\u3051\u308b\u53ef\u80fd\u6027\u304c3\u500d\u9ad8\u3044\u3067\u3059\u3002"
        ],
      },
    },
  },
  "thesis-generator-web": {
    name: "Thesis Generator",
    multilingual: false,
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
          "Your first thesis is waiting. Open Thesis Generator and generate your first statement before you even finish this email. The clock is ticking, but now you have the hack. P.S. The first one who uses the 'Humanize' feature on their generated thesis bypasses AI detection 99% of the time. It's your secret weapon."
        ],
      },
    },
  },
  "redflagscanner": {
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
          "Open the app right now. Before you finish this email. Don't wait for 'proof.' Your gut feeling IS the proof. Hit 'Scan a Conversation' with the last text that pinged your radar. Just do it. P.S. The first scan is always the hardest. The 800+ people who avoided major heartache all started with one 30-second scan of something 'small.'"
        ],
      },
    },
  },
  "breakuptherapy-e7dc0": {
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
          "Tap the button below and try Emergency Mode once right now. Just once. So when 3AM hits tonight, you already know the escape route. P.S. The first user who tried this told me 'It felt like someone finally handed me a life raft in the middle of the ocean.' That someone is you, handing it to yourself."
        ],
      },
    },
  },
  "soulplan-dateplanner": {
    name: "SoulPlan: Plan Dates Together",
    multilingual: false,
    appStoreUrl: "https://apps.apple.com/app/soulplan-plan-dates-together/id6702018988",
    googlePlayUrl: "https://play.google.com/store/apps/details?id=com.aifun.dateideas.planadate",
    emails: {
      en: {
        subject: "The secret mistake 90% of couples make on day one",
        cta_text: "Generate Your Surprise Date Now",
        body_paragraphs: [
          "Most couples download SoulPlan, browse a few ideas, and close it. They think it's just another list. That's the mistake. The magic isn't in browsing. It's in the 30-second surprise you can create right now.",
          "The routine trap is real. You start with good intentions, but life gets busy. The spark feels like a chore to plan. That's why I built one feature to cut through all the noise and deliver a perfect, personalized date idea instantly.",
          "Open the app. Don't browse. Tap the 'Surprise Date' button. In 30 seconds, our AI will generate a complete date plan\u2014from a cozy budget-friendly evening to a local adventure\u2014tailored just for you two. No overthinking. Just a ready-to-go spark.",
          "Your first surprise date is waiting. Tap the button below, hit 'Surprise Date', and watch your partner's face light up tonight. P.S. The 8% who don't use this feature in the first 24 hours are 3x more likely to let the app collect dust. Don't be them."
        ],
      },
    },
  },
  "petmealai": {
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
          "Tap the button below, open the Calorie Calculator, and get your dog's magic number. Do it now before the next meal. You'll feel a wave of relief knowing you're finally feeding the right amount. P.S. The biggest shock for most owners? Seeing how many 'healthy' treats actually blow the daily budget. That part stings, but fixing it adds years to their life."
        ],
      },
    },
  },
  // NOTE: boyfriend-ai-f1e5e and apb412---ai-girlfriend-app intentionally
  // NOT registered here. They're on Firebase Spark (free) plan and welcomes
  // are delivered via the Supabase check-new-users Edge Function instead
  // (~5 min after signup). The boyfriend-emails.js / girlfriend-emails.js
  // template files are kept on disk for parity with the Supabase versions
  // (supabase/functions/welcome-email/{boyfriend,girlfriend}-emails.ts) so
  // re-adding either project here is just an entry's worth of work.
};

// ── HTML BUILDER ────────────────────────────────────────────
function buildHtml(emailData, appConfig, language, senderName) {
  const isRtl = language === "ar";
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const textAlign = isRtl ? "right" : "left";

  const greetings = { en: "Hey there,", ar: "\u0645\u0631\u062d\u0628\u064b\u0627\u060c", es: "Hola,", fr: "Salut,", de: "Hallo,", tr: "Merhaba,", it: "Ciao,", pp: "Ol\u00e1,", pt: "Ol\u00e1,", hi: "\u0928\u092e\u0938\u094d\u0924\u0947,", id: "Halo,", nl: "Hallo,", pl: "Cze\u015b\u0107,", ja: "\u3053\u3093\u306b\u3061\u306f\u3001" };
  const signoffs = { en: "Talk soon,", ar: "\u0625\u0644\u0649 \u0627\u0644\u0644\u0642\u0627\u0621\u060c", es: "Hasta pronto,", fr: "\u00c0 bient\u00f4t,", de: "Bis bald,", tr: "G\u00f6r\u00fc\u015f\u00fcrz,", it: "A presto,", pp: "At\u00e9 breve,", pt: "At\u00e9 logo,", hi: "\u091c\u0932\u094d\u0926 \u092c\u093e\u0924 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902,", id: "Sampai jumpa,", nl: "Tot snel,", pl: "Do zobaczenia,", ja: "\u307e\u305f\u306d\u3001" };
  const footers = {
    en: `You're receiving this because you signed up for ${appConfig.name}.`,
    ar: `\u062a\u062a\u0644\u0642\u0649 \u0647\u0630\u0627 \u0627\u0644\u0628\u0631\u064a\u062f \u0644\u0623\u0646\u0643 \u0633\u062c\u0644\u062a \u0641\u064a ${appConfig.name}.`,
    es: `Recibes esto porque te registraste en ${appConfig.name}.`,
    fr: `Vous recevez ceci car vous vous \u00eates inscrit(e) \u00e0 ${appConfig.name}.`,
    de: `Du erh\u00e4ltst diese E-Mail, weil du dich bei ${appConfig.name} angemeldet hast.`,
    tr: `Bu e-postay\u0131 ${appConfig.name} uygulamas\u0131na kay\u0131t oldu\u011funuz i\u00e7in al\u0131yorsunuz.`,
    it: `Ricevi questa email perch\u00e9 ti sei registrato su ${appConfig.name}.`,
    pp: `Recebe este email porque se registou no ${appConfig.name}.`,
    pt: `Voc\u00ea est\u00e1 recebendo isso porque se cadastrou no ${appConfig.name}.`,
    hi: `\u0906\u092a\u0915\u094b \u092f\u0939 \u0907\u0938\u0932\u093f\u090f \u092e\u093f\u0932 \u0930\u0939\u093e \u0939\u0948 \u0915\u094d\u092f\u094b\u0902\u0915\u093f \u0906\u092a\u0928\u0947 ${appConfig.name} \u092e\u0947\u0902 \u0938\u093e\u0907\u0928 \u0905\u092a \u0915\u093f\u092f\u093e\u0964`,
    id: `Anda menerima email ini karena mendaftar di ${appConfig.name}.`,
    nl: `Je ontvangt dit bericht omdat je je hebt aangemeld voor ${appConfig.name}.`,
    pl: `Otrzymujesz t\u0119 wiadomo\u015b\u0107, poniewa\u017c zarejestrowaa\u0142e\u015b si\u0119 w ${appConfig.name}.`,
    ja: `${appConfig.name}\u306b\u3054\u767b\u9332\u3044\u305f\u3060\u3044\u305f\u305f\u3081\u3001\u3053\u306e\u30e1\u30fc\u30eb\u3092\u304a\u9001\u308a\u3057\u3066\u3044\u307e\u3059\u3002`,
  };

  const greeting = greetings[language] || greetings.en;
  const signoff = signoffs[language] || signoffs.en;
  const footerText = footers[language] || footers.en;
  const ctaText = emailData.cta_text;

  let bodyHtml = "";
  emailData.body_paragraphs.forEach((p, i) => {
    const pHtml = p.replace(/\n/g, "<br>");
    if (i === 0) {
      bodyHtml += `<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;text-align:${textAlign};">${pHtml}</p>`;
    } else if (p.includes("P.S.") || p.includes("P.S") || p.includes("\u0645\u0644\u0627\u062d\u0638\u0629") || p.includes("P.D.")) {
      bodyHtml += `<div style="margin:32px 0 0;padding:16px 20px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;"><p style="margin:0;font-size:16px;color:#92400e;line-height:1.7;text-align:${textAlign};">${pHtml}</p></div>`;
    } else {
      bodyHtml += `<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:${textAlign};">${pHtml}</p>`;
    }
  });

  // CTA buttons — render whichever store URLs are configured (iOS-only apps included).
  let ctaHtml = "";
  const hasIos = !!appConfig.appStoreUrl;
  const hasAndroid = !!appConfig.googlePlayUrl;
  if (hasIos || hasAndroid) {
    const iosLabel = hasIos && hasAndroid ? `${ctaText} (iOS)` : ctaText;
    const androidLabel = hasIos && hasAndroid ? `${ctaText} (Android)` : ctaText;
    const iosBtn = hasIos
      ? `<a href="${appConfig.appStoreUrl}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">\ud83d\udcf1 ${iosLabel}</a>`
      : "";
    const androidBtn = hasAndroid
      ? `<a href="${appConfig.googlePlayUrl}" style="display:inline-block;background:linear-gradient(135deg,#34d399 0%,#10b981 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">\ud83e\udd16 ${androidLabel}</a>`
      : "";
    ctaHtml = `
    <div style="text-align:center;margin:36px 0;">
      ${iosBtn}
      ${androidBtn}
    </div>`;
  }

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

// ── RESEND SENDER ───────────────────────────────────────────
function sendViaResend(apiKey, fromEmail, fromName, toEmail, subject, html) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      from: `${fromName} <${fromEmail}>`,
      to: [toEmail],
      subject: subject,
      html: html,
      reply_to: fromEmail,
    });

    const options = {
      hostname: "api.resend.com",
      path: "/emails",
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode === 200 || res.statusCode === 201) {
          console.log(`✅ Welcome email sent to ${toEmail}`);
          resolve(JSON.parse(data));
        } else {
          console.error(`❌ Resend error [${res.statusCode}]: ${data}`);
          reject(new Error(`Resend ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.write(payload);
    req.end();
  });
}

// ── CLOUD FUNCTION: Firestore trigger on user profile creation ──
// Each app writes a user doc to "users/{uid}" on first sign-in.
// This triggers the welcome email.
//
// NOTE: redflagscanner has a richer pipeline (localized, Selka-voiced,
// event-driven retention). It's handled by `./redflag/welcome.js` instead
// and this function returns early when projectId === "redflagscanner".
exports.sendWelcomeEmail = onDocumentCreated(
  { document: "users/{userId}", secrets: [resendApiKey] },
  async (event) => {
  const projectId = process.env.GCLOUD_PROJECT || process.env.GCP_PROJECT;

  // Selka (Red Flag Scanner) owns its own welcome path — skip here.
  if (projectId === "redflagscanner") {
    return null;
  }

  const appConfig = APP_CONFIG[projectId];

  if (!appConfig) {
    console.log(`⏭️ No welcome email config for project: ${projectId}`);
    return null;
  }

  const apiKey = resendApiKey.value();
  if (!apiKey) {
    console.error("❌ RESEND_API_KEY not set");
    return null;
  }

  const snap = event.data;
  if (!snap) return null;

  const userData = snap.data();
  const userEmail = userData.email;

  if (!userEmail) {
    console.log("⏭️ No email in user document, skipping");
    return null;
  }

  // Determine language (Predictify has multilingual support)
  let language = "en";
  if (appConfig.multilingual) {
    language = userData.language || userData.lang || "en";
    const supported = Object.keys(appConfig.emails);
    if (!supported.includes(language)) {
      language = "en";
    }
  }

  const emailData = appConfig.emails[language];
  if (!emailData) {
    console.error(`❌ No email template for language: ${language}`);
    return null;
  }

  const sender = getRandomSender();
  const html = buildHtml(emailData, appConfig, language, sender.name);

  try {
    await sendViaResend(
      apiKey,
      sender.email,
      appConfig.name, // from_name = app name (like the main emailer)
      userEmail,
      emailData.subject,
      html
    );

    // Mark welcome email as sent in Firestore
    await snap.ref.update({ welcome_email_sent: true, welcome_email_at: new Date().toISOString() });

    console.log(`✅ Welcome email sent: ${userEmail} (${appConfig.name}, ${language})`);
    return null;
  } catch (error) {
    console.error(`❌ Failed to send welcome to ${userEmail}:`, error);
    return null;
  }
});

// ── REDFLAGSCANNER PIPELINE ─────────────────────────────────
// Selka has a dedicated multi-track lifecycle system (Tracks A–E from the
// email plan). These two handlers only do work when projectId === "redflagscanner";
// they're deployed alongside the generic handler but become no-ops for
// every other app, so nothing else is affected.
const redflagWelcome = require("./redflag/welcome");
const redflagDispatcher = require("./redflag/dispatcher");
exports.sendSelkaWelcome = redflagWelcome.sendSelkaWelcome;
exports.onSelkaEmailEvent = redflagDispatcher.onEmailEventCreated;
