/**
 * email_events dispatcher for Selka (Red Flag Scanner).
 *
 * Listens to /email_events/{eventId} writes from the app + scheduled
 * emitters and:
 *   1. Loads the user + (when relevant) partner data for personalization.
 *   2. Picks the right template from templates.js.
 *   3. Translates it into the user's locale via the cache-backed translator.
 *   4. Interpolates {placeholders} and sends via Resend.
 *   5. Marks the event sent (or sets an error code) so retries don't double-fire.
 *
 * Idempotency: each event doc has `sent: false` from the emitter. We flip it
 * to `sent: true` on success. We also dedupe on `event_key` (the scheduled
 * emitters provide it) so the same dormancy event in the same day fires once.
 */

const {onDocumentCreated} = require("firebase-functions/v2/firestore");
const {defineSecret} = require("firebase-functions/params");
const admin = require("firebase-admin");

const {TEMPLATES} = require("./templates");
const {translateTemplate, normalizeLocale} = require("./translator");
const {sendSelkaEmail} = require("./sender");

const resendApiKey = defineSecret("RESEND_API_KEY");
const mailgunApiKey = defineSecret("MAILGUN_API_KEY");
const deepseekApiKey = defineSecret("DEEPSEEK_API_KEY");

const useMailgun = (process.env.EMAIL_PROVIDER || "resend").toLowerCase() === "mailgun";
const useSmtp2go = (process.env.EMAIL_PROVIDER || "resend").toLowerCase() === "smtp2go";
const selkaSecrets = useSmtp2go
  ? [deepseekApiKey]
  : useMailgun
    ? [mailgunApiKey, deepseekApiKey]
    : [resendApiKey, mailgunApiKey, deepseekApiKey];

// event_type → template_id. Lets us map fine-grained events from the app
// (e.g. `analysis_complete` with count=1) onto specific templates without
// the app needing to know template names.
const EVENT_ROUTES = {
  // Track A
  onboarding_complete: "welcome",
  analysis_complete_first: "first_scan_followup",
  comparison_complete: "comparison_result",
  weekly_check_in: "day_7_check_in",
  level_up: "level_up",

  // Track B
  paywall_dismissed: "paywall_dismissed",
  credits_low: "credits_low",
  credits_zero: "credits_zero",
  two_week_summary: "two_week_summary",

  // Track C
  weekly_report_ready: "weekly_report",
  pattern_unlocked: "pattern_unlocked",
  partner_idle_5d: "partner_idle_5d",
  monthly_milestone: "monthly_milestone",
  selka_wrapped_ready: "selka_wrapped",

  // Track D
  referral_activated: "referral_activated",
  high_risk_share_prompt: "high_risk_share_prompt",
  streak_milestone_30: "streak_30_gift",

  // Track E
  inactive_21d: "inactive_21d",
  inactive_45d: "inactive_45d",
  inactive_90d: "inactive_90d",
};

exports.onEmailEventCreated = onDocumentCreated(
    {
      document: "email_events/{eventId}",
      secrets: selkaSecrets,
    },
    async (event) => {
      // Only Selka project — other apps in this codebase have their own
      // welcome flow and don't write to `email_events`.
      const projectId = process.env.GCLOUD_PROJECT;
      if (projectId !== "redflagscanner") {
        return null;
      }

      const snap = event.data;
      if (!snap) return null;
      const evt = snap.data() || {};

      if (evt.sent === true) return null;
      const {uid, event_type: eventType, metadata = {}, event_key: eventKey} = evt;
      if (!uid || !eventType) return null;

      const templateId = EVENT_ROUTES[eventType];
      if (!templateId) {
        await markSkipped(snap.ref, "unknown_event_type");
        return null;
      }
      const template = TEMPLATES[templateId];
      if (!template) {
        await markSkipped(snap.ref, "template_missing");
        return null;
      }

      // Dedupe on event_key — same dormancy day shouldn't email twice.
      if (eventKey) {
        const lockRef = admin.firestore()
            .collection("email_event_locks").doc(eventKey);
        const lock = await lockRef.get();
        if (lock.exists) {
          await markSkipped(snap.ref, "duplicate");
          return null;
        }
        await lockRef.set({
          locked_at: admin.firestore.FieldValue.serverTimestamp(),
          event_id: snap.id,
        });
      }

      const db = admin.firestore();
      const userSnap = await db.collection("users").doc(uid).get();
      if (!userSnap.exists) {
        await markSkipped(snap.ref, "user_missing");
        return null;
      }
      const user = userSnap.data();
      if (!user.email) {
        await markSkipped(snap.ref, "no_email");
        return null;
      }

      // Some events are subscriber-only (Track C). Skip silently for free
      // users — they get Track B variants instead.
      const isPremium = user.is_premium === true;
      if (TRACK_C_TEMPLATES.has(templateId) && !isPremium) {
        await markSkipped(snap.ref, "free_user_skipped_track_c");
        return null;
      }
      if (TRACK_B_TEMPLATES.has(templateId) && isPremium) {
        await markSkipped(snap.ref, "premium_user_skipped_track_b");
        return null;
      }

      const locale = normalizeLocale(user.language);
      const vars = await buildVars({db, uid, user, metadata});

      const localized = await translateTemplate(
          template, templateId, locale, deepseekApiKey.value(),
      );

      try {
        await sendSelkaEmail({
          template: localized,
          vars,
          toEmail: user.email,
          locale,
          resendApiKey: (useMailgun || useSmtp2go) ? "" : resendApiKey.value(),
        });
        await snap.ref.update({
          sent: true,
          sent_at: admin.firestore.FieldValue.serverTimestamp(),
          sent_lang: locale,
          template_id: templateId,
        });
      } catch (err) {
        console.error(`Selka email send failed (${templateId}, ${uid}):`, err);
        await snap.ref.update({
          sent: false,
          last_error: String(err.message || err),
          last_error_at: admin.firestore.FieldValue.serverTimestamp(),
        });
      }
      return null;
    });

const TRACK_B_TEMPLATES = new Set([
  "paywall_dismissed", "credits_low", "credits_zero",
  "hypothetical_insight", "two_week_summary",
]);
const TRACK_C_TEMPLATES = new Set([
  "weekly_report", "pattern_unlocked", "partner_idle_5d",
  "feature_spotlight", "monthly_milestone", "selka_wrapped",
  "streak_30_gift",
]);

async function markSkipped(ref, reason) {
  await ref.update({
    sent: false,
    skipped: true,
    skip_reason: reason,
    skipped_at: admin.firestore.FieldValue.serverTimestamp(),
  });
}

// Build the personalization variable bag from user doc + event metadata +
// (lazy) partner lookup. Anything that fails falls back to defaults in
// sender.js — we never throw on missing data.
async function buildVars({db, uid, user, metadata}) {
  const vars = {
    name: firstName(user.name) || "there",
    credits_remaining: user.credits ?? 0,
    streak_days: user.streak_days ?? 0,
    scan_count_total: user.analysis_count ?? 0,
    referral_code: user.referral_code || "",
    referrals_count: user.referrals_count ?? 0,
    level: user.level ?? 1,
    ...metadata,
  };

  // Partner lookup — only when event needs it. The scheduled emitter for
  // partner_idle_5d already puts partner_name into metadata; this is the
  // fallback for events that don't.
  if (!vars.partner_name) {
    try {
      const partnersSnap = await db.collection("users").doc(uid)
          .collection("partners")
          .orderBy("updated_at", "desc")
          .limit(2)
          .get();
      if (!partnersSnap.empty) {
        vars.partner_name = partnersSnap.docs[0].data().name || "them";
        vars.last_partner_risk =
            partnersSnap.docs[0].data().last_risk_level || "concerning";
        vars.partner_count = (user.partner_count) ??
            await db.collection("users").doc(uid)
                .collection("partners").count().get()
                .then((q) => q.data().count).catch(() => 0);
      }
      if (partnersSnap.size >= 2) {
        vars.partner_a = partnersSnap.docs[0].data().name;
        vars.partner_b = partnersSnap.docs[1].data().name;
      }
    } catch (_) {
      // best-effort; defaults handle missing values
    }
  }

  return vars;
}

function firstName(full) {
  if (!full) return null;
  const trimmed = String(full).trim();
  if (!trimmed) return null;
  return trimmed.split(/\s+/)[0];
}
