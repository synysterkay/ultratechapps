import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { handleKinboundEmail, type KinboundTemplate } from "../_shared/kinbound_email.ts";

const KIND = "kinbound_account_linked";
const FOOTERS = {
  en: "You're receiving this because you linked an account in Kinbound.",
  es: "Recibes esto porque vinculaste una cuenta en Kinbound.",
  fr: "Vous recevez ceci car vous avez lié un compte dans Kinbound.",
};

const TEMPLATES: Record<string, KinboundTemplate> = {
  en: {
    subject: "✅ {{first_name}}, your Kinbound journey is backed up",
    body: [
      "Your Google or Apple account is now linked. Streak, intentions, and locale sync across devices — still no child names or chat in the cloud.",
      "If you get a new phone, sign in with the same account and Kinbound restores what matters without reading your family's private notes.",
      "P.S. Help me now works the same as before — linking just means you won't lose your progress.",
    ],
    cta: "Open Kinbound",
  },
  es: {
    subject: "✅ {{first_name}}, tu camino en Kinbound está respaldado",
    body: [
      "Tu cuenta de Google o Apple ya está vinculada. Racha e intenciones se sincronizan — sin nombres de hijos ni chat en la nube.",
      "En un teléfono nuevo, inicia sesión y Kinbound restaura lo importante.",
      "P.D. Ayúdame ahora funciona igual — vincular solo evita perder tu progreso.",
    ],
    cta: "Abrir Kinbound",
  },
  fr: {
    subject: "✅ {{first_name}}, votre parcours Kinbound est sauvegardé",
    body: [
      "Votre compte Google ou Apple est lié. Série et intentions se synchronisent — toujours pas de noms d'enfants ni de chat dans le cloud.",
      "Sur un nouveau téléphone, connectez-vous et Kinbound restaure l'essentiel.",
      "P.S. Aide-moi maintenant fonctionne pareil — lier évite juste de perdre votre progression.",
    ],
    cta: "Ouvrir Kinbound",
  },
};

Deno.serve((req) =>
  handleKinboundEmail(
    req,
    { kind: KIND, appId: "kinbound", templates: TEMPLATES, footers: FOOTERS },
    (payload) => ({
      first_name: String(payload.first_name || "there"),
    }),
  )
);
