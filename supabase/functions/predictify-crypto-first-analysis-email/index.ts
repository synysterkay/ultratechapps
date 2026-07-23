// Instant: first successful chart analysis on Predictify Crypto.
// POST .../predictify-crypto-first-analysis-email
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  CRYPTO_APP_NAME,
  handleCryptoInstantEmail,
  type CryptoTemplate,
} from "../_shared/crypto_email.ts";

const KIND = "first_analysis";

const TEMPLATES: Record<string, CryptoTemplate> = {
  en: {
    subject:
      "{{first_name}}, you just got your first AI setup — don't lose the streak",
    body: [
      "Hey {{first_name}},",
      "You scanned a chart and Predictify Crypto returned a real setup{{asset_line}}. Most people never get past scrolling opinions. You just crossed the line that filters out noise.",
      "The habit that matters next is simple: one scan a day. That's how streaks form — and streak traders aren't luckier, they're consistent.",
      "Open the app tomorrow, scan the pair you actually trade, and read the stop before you size.",
      "P.S. Not financial advice. Journal the result when you close — that's how the process compounds.",
    ],
    cta: "Open my setup",
  },
};

Deno.serve((req) =>
  handleCryptoInstantEmail({
    req,
    kind: KIND,
    templates: TEMPLATES,
    footer:
      `You're receiving this because you completed your first analysis on ${CRYPTO_APP_NAME}.`,
    buildVars: (payload) => {
      const asset = String(payload.asset || "").trim();
      return {
        first_name: String(payload.first_name || "there"),
        asset_line: asset ? ` on ${asset}` : "",
      };
    },
  })
);
