// Instant: analysis streak ≥3 broken back to 1.
// POST .../predictify-crypto-streak-broken-email
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {
  CRYPTO_APP_NAME,
  handleCryptoInstantEmail,
  type CryptoTemplate,
} from "../_shared/crypto_email.ts";

const KIND = "streak_broken";

const TEMPLATES: Record<string, CryptoTemplate> = {
  en: {
    subject:
      "{{first_name}}, your {{prior_streak}}-day streak just reset — start day 1 again",
    body: [
      "Hey {{first_name}},",
      "Your {{prior_streak}}-day analysis streak ended. That sting is useful — it means the habit mattered.",
      "You don't need to make up for lost days. Open Predictify Crypto and scan one chart. Day 1 starts the moment you do.",
      "P.S. Traders who restart within 24 hours are far more likely to rebuild a longer streak than those who wait a week.",
    ],
    cta: "Start day 1",
  },
};

Deno.serve(async (req) => {
  if (req.method === "POST") {
    try {
      const clone = req.clone();
      const payload = await clone.json();
      const prior = Number(payload.prior_streak || 0);
      if (prior < 3) {
        return new Response(
          JSON.stringify({ ok: true, skipped: "prior_streak_lt_3" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
    } catch {
      // fall through to shared handler validation
    }
  }

  return handleCryptoInstantEmail({
    req,
    kind: KIND,
    templates: TEMPLATES,
    footer:
      `You're receiving this because an analysis streak ended on ${CRYPTO_APP_NAME}.`,
    buildVars: (payload) => ({
      first_name: String(payload.first_name || "there"),
      prior_streak: String(payload.prior_streak || "3"),
    }),
  });
});
