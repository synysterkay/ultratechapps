import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  handleKinboundEmail,
  type KinboundTemplate,
  struggleLabel,
} from "../_shared/kinbound_email.ts";

const KIND = "kinbound_first_script";
const FOOTERS = {
  en: "You're receiving this because you loved your first Kinbound coaching script.",
  es: "Recibes esto porque te gustó tu primer guion de Kinbound.",
  fr: "Vous recevez ceci car vous avez aimé votre premier script Kinbound.",
};

const TEMPLATES: Record<string, KinboundTemplate> = {
  en: {
    subject: "🌱 That script worked, {{first_name}} — save the next one",
    body: [
      "You reacted to the words Kinbound gave you for {{struggle}}. That's the whole point — something to say when your brain is blank.",
      "Tap Help me now anytime that moment comes back. Same calm coach, new words if you need them. Save the ones that land with the bookmark.",
      "P.S. Link Google or Apple in Settings when you're ready — it backs up your streak and saved scripts without touching child names or chat.",
    ],
    cta: "Open Help me now",
  },
  es: {
    subject: "🌱 Ese guion funcionó, {{first_name}} — guarda el siguiente",
    body: [
      "Reaccionaste a las palabras que Kinbound te dio para {{struggle}}. Ese es el punto — algo que decir cuando tu mente está en blanco.",
      "Toca Ayúdame ahora cuando vuelva ese momento. El mismo coach tranquilo, nuevas palabras si las necesitas.",
      "P.D. Vincula Google o Apple en Ajustes cuando quieras — respalda tu racha sin subir nombres ni chats.",
    ],
    cta: "Abrir Ayúdame ahora",
  },
  fr: {
    subject: "🌱 Ce script a marché, {{first_name}} — gardez le suivant",
    body: [
      "Vous avez réagi aux mots que Kinbound vous a donnés pour {{struggle}}. C'est tout l'intérêt — quelque chose à dire quand votre cerveau est vide.",
      "Appuyez sur Aide-moi maintenant dès que le moment revient. Le même coach calme, de nouveaux mots si besoin.",
      "P.S. Liez Google ou Apple dans Réglages quand vous voulez — sauvegarde votre série sans envoyer de noms ni de chats.",
    ],
    cta: "Ouvrir Aide-moi",
  },
};

Deno.serve((req) =>
  handleKinboundEmail(
    req,
    { kind: KIND, appId: "kinbound", templates: TEMPLATES, footers: FOOTERS },
    (payload) => {
      const situationId = String(payload.situation_id || "tantrum");
      return {
        first_name: String(payload.first_name || "there"),
        child_name: String(payload.child_name || "your child"),
        struggle: struggleLabel(situationId),
      };
    },
  )
);
