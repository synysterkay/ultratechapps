// Instant: Superwall campaign_trigger shown (desire peak without purchase).
// POST .../predictify-crypto-paywall-hit-email
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  CRYPTO_APP_NAME,
  handleCryptoInstantEmail,
  type CryptoTemplate,
} from "../_shared/crypto_email.ts";

const KIND = "paywall_hit";

const TEMPLATES: Record<string, CryptoTemplate> = {
  en: {
    subject: "{{first_name}}, your chart is ready — unlock the AI setup",
    body: [
      "Hey {{first_name}},",
      "You hit the unlock step for AI chart analysis. That's the moment most traders bounce back to Telegram screenshots — and lose the edge of a written stop.",
      "Predictify Crypto turns a chart into entry, stop, and targets you can journal. Subscribe once, scan whenever the setup appears.",
      "Open the app and finish unlock when you're ready. Your watchlist is already waiting.",
      "P.S. This is not financial advice — it's a process: scan → setup → journal → streak.",
    ],
    cta: "Unlock AI analysis",
  },
};

Deno.serve((req) =>
  handleCryptoInstantEmail({
    req,
    kind: KIND,
    templates: TEMPLATES,
    footer:
      `You're receiving this because you opened the Pro unlock on ${CRYPTO_APP_NAME}.`,
    buildVars: (payload) => ({
      first_name: String(payload.first_name || "there"),
      trigger_source: String(payload.trigger_source || "campaign_trigger"),
    }),
  })
);
