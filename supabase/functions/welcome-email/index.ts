// Supabase Edge Function: welcome-email
// Sends instant welcome email #1 when a new user signs up.
// Called by mobile apps via POST with { email, app_id, language? }
//
// Endpoint: POST https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/welcome-email
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
    zh: "\u4f60\u597d\uff0c",
    hi: "\u0928\u092e\u0938\u094d\u0924\u0947,",
    pt: "Ol\u00e1,",
    ru: "\u041f\u0440\u0438\u0432\u0435\u0442,",
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
