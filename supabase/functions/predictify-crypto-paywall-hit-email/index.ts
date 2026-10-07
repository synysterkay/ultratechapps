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
    subject: "{{first_name}}, tip before you size: write the stop first",
    body: [
      "Hey {{first_name}},",
      "You opened the AI setup step. Tip: before you chase another Telegram screenshot, get a written entry / stop / targets for the chart you actually trade.",
      "Predictify Crypto turns a screenshot into that setup so you can journal it. Your watchlist is already waiting.",
      "Open the app, scan the pair you care about, and read the stop before you size.",
      "P.S. When you're ready, unlocking removes the gate on more scans. No rush — process first: scan → setup → journal → streak. Not financial advice.",
    ],
    cta: "Open my chart setup",
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
