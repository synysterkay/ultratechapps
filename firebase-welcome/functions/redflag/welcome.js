/**
 * Selka welcome email — runs only when project === redflagscanner.
 *
 * Unlike the per-app welcome in ../index.js (which sends one canned email
 * per app, English-only), this one:
 *   - Reads the user's language and translates the welcome template into it.
 *   - Personalizes with the onboarding intent the user picked (so the email
 *     sounds like Selka heard their answer).
 *   - Sends via the same Resend wrapper as the lifecycle dispatcher, for
 *     visual + sender-pool consistency.
 *
 * Other projects (Predictify, Thesis, etc) bypass this entirely — the
 * generic handler in ../index.js handles them and the projectId check
 * here is the only gate.
 */

const {onDocumentCreated} = require("firebase-functions/v2/firestore");
const {defineSecret} = require("firebase-functions/params");
const admin = require("firebase-admin");

const {TEMPLATES} = require("./templates");
const {translateTemplate, normalizeLocale} = require("./translator");
const {sendSelkaEmail} = require("./sender");

const resendApiKey = defineSecret("RESEND_API_KEY");
const deepseekApiKey = defineSecret("DEEPSEEK_API_KEY");

exports.sendSelkaWelcome = onDocumentCreated(
    {
      document: "users/{userId}",
      secrets: [resendApiKey, deepseekApiKey],
    },
    async (event) => {
      const projectId = process.env.GCLOUD_PROJECT;
      if (projectId !== "redflagscanner") {
        // Other apps go through the generic welcome handler in ../index.js.
        return null;
      }

      const snap = event.data;
      if (!snap) return null;
      const user = snap.data() || {};

      if (!user.email) return null;
      if (user.welcome_email_sent === true) return null;

      const locale = normalizeLocale(user.language);
      const template = TEMPLATES.welcome;
      const localized = await translateTemplate(
          template, "welcome", locale, deepseekApiKey.value(),
      );

      const vars = {
        name: firstName(user.name) || "there",
        credits_remaining: user.credits ?? 3,
        referral_code: user.referral_code || "",
      };

      try {
        await sendSelkaEmail({
          template: localized,
          vars,
          toEmail: user.email,
          locale,
          resendApiKey: resendApiKey.value(),
        });
        await snap.ref.update({
          welcome_email_sent: true,
          welcome_email_at: admin.firestore.FieldValue.serverTimestamp(),
          welcome_email_lang: locale,
        });
      } catch (err) {
        console.error(`Selka welcome failed (${snap.id}):`, err);
      }
      return null;
    });

function firstName(full) {
  if (!full) return null;
  const trimmed = String(full).trim();
  if (!trimmed) return null;
  return trimmed.split(/\s+/)[0];
}
