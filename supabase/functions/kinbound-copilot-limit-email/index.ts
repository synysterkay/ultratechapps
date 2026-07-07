import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  handleKinboundEmail,
  type KinboundTemplate,
  struggleLabel,
} from "../_shared/kinbound_email.ts";

const KIND = "kinbound_copilot_limit";
const FOOTERS = {
  en: "You're receiving this because you hit today's free coaching limit in Kinbound.",
  es: "Recibes esto porque alcanzaste el límite gratuito de hoy en Kinbound.",
  fr: "Vous recevez ceci car vous avez atteint la limite gratuite du jour dans Kinbound.",
};

const TEMPLATES: Record<string, KinboundTemplate> = {
  en: {
    subject: "{{first_name}}, you used today's free coaching — here's what unlocks",
    body: [
      "You reached for Kinbound on a hard {{struggle}} moment and hit the free daily limit. That usually means it was actually helping.",
      "Premium removes the daily cap — unlimited Help me now scripts, saved coaching history, and the full Family tools. No child data leaves your phone either way.",
      "P.S. If tonight isn't the night to upgrade, your saved scripts and streak are still there tomorrow.",
    ],
    cta: "See Kinbound Premium",
  },
  es: {
    subject: "{{first_name}}, usaste el coaching gratis de hoy — esto desbloquea",
    body: [
      "Buscaste Kinbound en un momento difícil de {{struggle}} y llegaste al límite diario gratuito. Eso suele significar que estaba ayudando.",
      "Premium quita el tope diario — Ayúdame ahora ilimitado y herramientas Family completas.",
      "P.D. Si esta noche no es para actualizar, tus guiones guardados siguen ahí mañana.",
    ],
    cta: "Ver Kinbound Premium",
  },
  fr: {
    subject: "{{first_name}}, vous avez utilisé le coaching gratuit — voici la suite",
    body: [
      "Vous avez ouvert Kinbound pour {{struggle}} et atteint la limite gratuite du jour. Ça veut souvent dire que ça aidait vraiment.",
      "Premium enlève le plafond quotidien — Aide-moi maintenant illimité et outils Family complets.",
      "P.S. Si ce n'est pas le soir pour passer à Premium, vos scripts sauvegardés seront là demain.",
    ],
    cta: "Voir Kinbound Premium",
  },
};

Deno.serve((req) =>
  handleKinboundEmail(
    req,
    { kind: KIND, appId: "kinbound", templates: TEMPLATES, footers: FOOTERS },
    (payload) => ({
      first_name: String(payload.first_name || "there"),
      struggle: struggleLabel(String(payload.situation_id || "tantrum")),
    }),
  )
);
