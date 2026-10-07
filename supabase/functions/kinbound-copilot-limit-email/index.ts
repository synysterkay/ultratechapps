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
    subject: "{{first_name}}, tonight's {{struggle}} still needs words",
    body: [
      "You hit today's free Help me now limit on a hard {{struggle}} moment — that usually means the coach was actually useful.",
      "Tip for tonight: open your saved scripts and reuse the one that worked last time. Name the feeling before the ask. That alone often shortens the spiral.",
      "P.S. When you're ready, Premium lifts the daily cap so Help me now isn't cut mid-crisis. No rush — your streak and scripts stay either way.",
    ],
    cta: "Open my saved scripts",
  },
  es: {
    subject: "{{first_name}}, esta noche {{struggle}} aún necesita palabras",
    body: [
      "Llegaste al límite gratuito de Ayúdame ahora en un momento difícil de {{struggle}} — suele significar que el coach estaba ayudando.",
      "Consejo: abre tus guiones guardados y reutiliza el que funcionó la última vez. Nombra el sentimiento antes de pedir. Eso acorta la espiral.",
      "P.D. Cuando quieras, Premium quita el tope diario. Sin prisa — tu racha y guiones siguen ahí.",
    ],
    cta: "Abrir mis guiones",
  },
  fr: {
    subject: "{{first_name}}, ce soir {{struggle}} a encore besoin de mots",
    body: [
      "Vous avez atteint la limite gratuite d'Aide-moi maintenant sur un moment difficile de {{struggle}} — signe que le coach aidait vraiment.",
      "Astuce: ouvrez vos scripts sauvegardés et réutilisez celui qui a marché. Nommez le sentiment avant la demande. Ça raccourcit souvent la spirale.",
      "P.S. Quand vous serez prêt, Premium enlève le plafond du jour. Sans pression — votre série et vos scripts restent.",
    ],
    cta: "Ouvrir mes scripts",
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
