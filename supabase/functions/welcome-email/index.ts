// Supabase Edge Function: welcome-email
// Sends instant welcome email #1 when a new user signs up.
// Called by mobile apps via POST with { email, app_id, language? }
//
// Endpoint: POST https://ldxqwbkizlbanzzfvcxd.supabase.co/functions/v1/welcome-email
// Headers:  Authorization: Bearer <SUPABASE_ANON_KEY>
//           Content-Type: application/json

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";

// ── SENDER POOL (same 7 domains as main system) ────────────
const SENDER_POOL = [
  { email: "apps@kaynel.pl", name: "Ana" },
  { email: "hello@bestaiapps.site", name: "Alex" },
  { email: "apps@vitazelki.pl", name: "Casey" },
  { email: "hello@aibettips.io", name: "Jordan" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
  { email: "hello@thesisgenerator.io", name: "Morgan" },
  { email: "hello@passedai.io", name: "Taylor" },
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
        subject: "The one mistake 90% of new users make immediately",
        cta_text: "Show Me The Confidence Score",
        body_paragraphs: [
          "You just downloaded Predictify. And you're about to make the same mistake everyone else does. You're going to look at a match, see the prediction, and think 'yeah, maybe.' But you're missing the one thing that makes our AI smarter than your gut feeling.",
          "Here's the truth: a prediction without confidence is just a guess. And you've had enough of those. Our AI analyzes thousands of data points\u2014xG, possession, defensive form, head-to-head history\u2014but the real magic is the confidence score. It's the difference between 'Liverpool might win' and 'Liverpool wins 78% of the time with these exact conditions.' That's not a tip. It's a calculated insight.",
          "Open the app. Right now. Don't browse. Go straight to any Premier League match happening this weekend. Look at the prediction. Then look directly below it. See that percentage? That's your confidence score. That's the secret. That number is built from more data than you could analyze in a month. It tells you exactly how much our AI believes in its own call. In 30 seconds, you'll stop guessing and start knowing.",
          "Tap the button. Open Predictify and find that confidence score on your next match. It changes everything. P.S. The users who check this score on day one are 3x more likely to spot a value bet in their first week. Don't be the 90%.",
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
    },
  },

  thesis_generator: {
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
          "Your first thesis is waiting. Open Thesis Generator and generate your first statement before you even finish this email. The clock is ticking, but now you have the hack. P.S. The first one who uses the 'Humanize' feature on their generated thesis bypasses AI detection 99% of the time. It's your secret weapon.",
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
          "Your first surprise date is waiting. Tap the button below, hit 'Surprise Date', and watch your partner's face light up tonight. P.S. The 8% who don't use this feature in the first 24 hours are 3x more likely to let the app collect dust. Don't be them.",
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
};

// ── HTML BUILDER ────────────────────────────────────────────
function buildHtml(
  emailData: EmailTemplate,
  appConfig: AppConfig,
  language: string,
  senderName: string
): string {
  const isRtl = language === "ar";
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const textAlign = isRtl ? "right" : "left";

  const greetings: Record<string, string> = {
    en: "Hey there,",
    ar: "\u0645\u0631\u062d\u0628\u064b\u0627\u060c",
    es: "Hola,",
    fr: "Salut,",
  };
  const signoffs: Record<string, string> = {
    en: "Talk soon,",
    ar: "\u0625\u0644\u0649 \u0627\u0644\u0644\u0642\u0627\u0621\u060c",
    es: "Hasta pronto,",
    fr: "\u00c0 bient\u00f4t,",
  };
  const footers: Record<string, string> = {
    en: `You're receiving this because you signed up for ${appConfig.name}.`,
    ar: `\u062a\u062a\u0644\u0642\u0649 \u0647\u0630\u0627 \u0627\u0644\u0628\u0631\u064a\u062f \u0644\u0623\u0646\u0643 \u0633\u062c\u0644\u062a \u0641\u064a ${appConfig.name}.`,
    es: `Recibes esto porque te registraste en ${appConfig.name}.`,
    fr: `Vous recevez ceci car vous vous \u00eates inscrit(e) \u00e0 ${appConfig.name}.`,
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

  const ctaHtml = `
    <div style="text-align:center;margin:36px 0;">
      <a href="${appConfig.appStoreUrl}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
        \ud83d\udcf1 ${ctaText} (iOS)
      </a>
      <a href="${appConfig.googlePlayUrl}" style="display:inline-block;background:linear-gradient(135deg,#34d399 0%,#10b981 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
        \ud83e\udd16 ${ctaText} (Android)
      </a>
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
    const { email, app_id, language } = await req.json();

    if (!email || !app_id) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: email, app_id" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

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
    const html = buildHtml(emailData, appConfig, lang, sender.name);

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
      }),
    });

    const resendData = await resendRes.json();

    if (!resendRes.ok) {
      console.error(`Resend error [${resendRes.status}]:`, resendData);
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
