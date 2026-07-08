// Supabase Edge Function: predictify-first-win-email
//
// Fires INSTANTLY when a Predictify user's first prediction resolves
// correct. Hits the user at the emotional peak — the moment they prove
// (to themselves) that the model + their judgment can call a match.
// Hooked-model identity reward: "I'm a person who calls matches now."
//
// Called by the Predictify prediction-resolution job (Supabase function
// or cron) the moment user_picks.is_correct flips to true AND it's that
// user's first ever correct row:
//
//   POST https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-first-win-email
//   Authorization: Bearer <SUPABASE_ANON_KEY>
//   Content-Type: application/json
//   {
//     "uid": "...",
//     "email": "user@example.com",
//     "language": "en",            // optional, default 'en'
//     "first_name": "Marcus",      // optional
//     "home_team": "Arsenal",      // optional
//     "away_team": "Liverpool",    // optional
//     "league_name": "Premier League", // optional
//     "fixture_id": 12345          // optional, only used in the deeplink
//   }
//
// Dedup: lifetime (uid, 'first_correct') via instant_emails_sent. By
// definition this is a once-ever event so the unique key is correct.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { SENDER_POOL_PREDICTIFY as SENDER_POOL } from "../_shared/sender_pool.ts";
import { hasEmailCredentials, resolveSender, sendEmail } from "../_shared/email_transport.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

const APP_NAME = "Predictify";
const APP_SLUG = "predictify";
const KIND = "first_correct";

function pickSender(uid: string) {
  let h = 0;
  for (const c of uid) h = (h * 31 + c.charCodeAt(0)) | 0;
  return SENDER_POOL[Math.abs(h) % SENDER_POOL.length];
}

async function userRef(email: string): Promise<string> {
  const data = new TextEncoder().encode(`${REF_SALT}:${email.toLowerCase().trim()}`);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 16);
}

function sanitizeTagValue(v: string): string {
  return v.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 256);
}

function interpolate(s: string, vars: Record<string, string>): string {
  return s.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? `{{${k}}}`);
}

// English-only inline template. TO LOCALIZE later: add lang keys to
// TEMPLATES below following the thesis-complete-email pattern (each
// lang entry is { subject, body[], cta }). Same merge fields, same
// structure — no Edge Function logic changes needed.
const TEMPLATES: Record<string, { subject: string; body: string[]; cta: string }> = {
  en: {
    subject: "🎯 You called your first one, {{first_name}} — here's how to do it again",
    body: [
      "Hey {{first_name}},",
      "{{home_team}} vs {{away_team}} — you picked it, the model picked it, and the match agreed. That's your first correct prediction logged.",
      "Here's why this is the email worth reading: most users download a prediction app, scroll twice, and bounce before they ever see a confirmed call. You made it past the line that filters out 90% of football fans.",
      "Now the part that turns one call into a habit: open the app tomorrow and pick again. Predictify gets sharper the more you use it — your model now has one confirmed data point from you, and that's how the personalisation actually starts.",
      "P.S. Your accuracy stats are live in the app — watch them climb.",
    ],
    cta: "See today's matches",
  },
};

function loadTemplate(lang: string) {
  return TEMPLATES[lang] || TEMPLATES.en;
}

const GREETINGS: Record<string, string> = { en: "Hey there," };
const SIGNOFFS: Record<string, string> = { en: "Talk soon," };
const FOOTERS: Record<string, string> = {
  en: "You're receiving this because your first prediction on Predictify just resolved correct.",
};

function buildHtml(
  paragraphs: string[],
  ctaText: string,
  ctaHref: string,
  senderName: string,
  signoff: string,
  footer: string,
  unsubUrl: string,
  isRtl: boolean,
): string {
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const align = isRtl ? "right" : "left";
  const body = paragraphs.map((p, i) => {
    const ph = p.replace(/\n/g, "<br>");
    if (i === 0) {
      return `<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;text-align:${align};">${ph}</p>`;
    }
    if (p.includes("P.S.")) {
      return `<div style="margin:32px 0 0;padding:16px 20px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;"><p style="margin:0;font-size:16px;color:#92400e;line-height:1.7;text-align:${align};">${ph}</p></div>`;
    }
    return `<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:${align};">${ph}</p>`;
  }).join("");
  return `<!DOCTYPE html><html${dirAttr}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:${align};">
${body}
<div style="text-align:center;margin:36px 0;">
<a href="${ctaHref}" style="display:inline-block;background:linear-gradient(135deg,#3B82F6 0%,#2563EB 100%);color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;">⚽ ${ctaText}</a>
</div>
<p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:${align};">${signoff}<br><strong style="color:#1f2937;">${senderName}</strong></p>
<div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
<p style="margin:0 0 6px;font-size:12px;color:#9ca3af;">${footer}</p>
<p style="margin:0;font-size:12px;color:#9ca3af;"><a href="${unsubUrl}" style="color:#9ca3af;">Unsubscribe</a></p>
</div></body></html>`;
}

function buildText(
  paragraphs: string[],
  ctaText: string,
  ctaHref: string,
  signoff: string,
  senderName: string,
  footer: string,
  unsubUrl: string,
): string {
  return [
    "PREDICTIFY",
    "",
    paragraphs.join("\n\n"),
    "",
    `${ctaText}: ${ctaHref}`,
    "",
    `${signoff}`,
    senderName,
    "",
    "—",
    footer,
    `Unsubscribe: ${unsubUrl}`,
  ].join("\n");
}

async function buildUnsubUrl(email: string): Promise<string> {
  const base = Deno.env.get("PREDICTIFY_UNSUBSCRIBE_URL") ||
    "https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-unsubscribe";
  const secret = Deno.env.get("PREDICTIFY_UNSUBSCRIBE_SECRET") || "";
  const payload = `${email.toLowerCase().trim()}|predictify`;
  const e = btoa(payload).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  if (!secret) return `${base}?e=${e}`;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(e));
  const hex = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
  return `${base}?e=${e}&s=${hex}`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "authorization, content-type, x-client-info, apikey",
      },
    });
  }
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  if (!hasEmailCredentials()) return new Response(JSON.stringify({ error: "email credentials missing" }), { status: 500 });

  let payload: Record<string, unknown>;
  try { payload = await req.json(); }
  catch { return new Response(JSON.stringify({ error: "invalid JSON" }), { status: 400 }); }

  const uid = String(payload.uid || "").trim();
  const email = String(payload.email || "").toLowerCase().trim();
  if (!uid)   return new Response(JSON.stringify({ error: "missing field: uid" }), { status: 400 });
  if (!email) return new Response(JSON.stringify({ error: "missing field: email" }), { status: 400 });
  if (email.includes("cloudtestlabaccounts.com") || email.includes("example.com")) {
    return new Response(JSON.stringify({ ok: true, skipped: "test_account" }), { status: 200 });
  }

  let lang = String(payload.language || "en").toLowerCase().split(/[_-]/)[0];
  if (!(lang in TEMPLATES)) lang = "en";

  const vars = {
    first_name: String(payload.first_name || "there"),
    home_team: String(payload.home_team || "your match"),
    away_team: String(payload.away_team || ""),
    league_name: String(payload.league_name || ""),
  };
  const fixtureId = String(payload.fixture_id || "");

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  // Dedup check.
  const { data: existing } = await supabase
    .from("instant_emails_sent")
    .select("id, sent_at")
    .eq("uid", uid)
    .eq("event_kind", KIND)
    .maybeSingle();
  if (existing) {
    return new Response(JSON.stringify({ ok: true, duplicate: true, sent_at: existing.sent_at }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Suppression check — don't email users who unsubscribed.
  const { data: suppressed } = await supabase
    .from("email_suppressions")
    .select("recipient")
    .eq("recipient", email)
    .eq("app", APP_SLUG)
    .maybeSingle();
  if (suppressed) {
    return new Response(JSON.stringify({ ok: true, skipped: "suppressed" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const tpl = loadTemplate(lang);
  const subject = interpolate(tpl.subject, vars);
  const paragraphs = tpl.body.map((p) => interpolate(p, vars));
  const ctaText = tpl.cta;

  const sender = resolveSender(pickSender(uid));
  const ref = await userRef(email);
  const deeplink = fixtureId
    ? `https://predictifyfootball.com/?ref=email&kind=${KIND}&fixture=${fixtureId}`
    : `https://predictifyfootball.com/?ref=email&kind=${KIND}`;

  const unsubUrl = await buildUnsubUrl(email);
  const isRtl = lang === "ar";
  const greeting = GREETINGS[lang] || GREETINGS.en;
  const signoff = SIGNOFFS[lang] || SIGNOFFS.en;
  const footer = FOOTERS[lang] || FOOTERS.en;
  void greeting;

  const html = buildHtml(paragraphs, ctaText, deeplink, sender.name, signoff, footer, unsubUrl, isRtl);
  const text = buildText(paragraphs, ctaText, deeplink, signoff, sender.name, footer, unsubUrl);

  const tags = [
    { name: "app", value: APP_SLUG },
    { name: "kind", value: KIND },
    { name: "email_num", value: "instant" },
    { name: "language", value: sanitizeTagValue(lang) },
    { name: "segment", value: "instant" },
    { name: "system", value: "instant_v1" },
  ];

  const sendResult = await sendEmail({
    fromName: sender.name,
    fromEmail: sender.email,
    to: email,
    subject,
    html,
    text,
    replyTo: sender.email,
    tags,
    refId: ref,
  });

  if (!sendResult.ok) {
    console.error(`Email send ${sendResult.status}: ${JSON.stringify(sendResult.details)}`);
    return new Response(JSON.stringify({ error: "send failed", details: sendResult.details }), {
      status: 500, headers: { "Content-Type": "application/json" },
    });
  }

  const messageId = sendResult.id || "";
  const { error: insertErr } = await supabase
    .from("instant_emails_sent")
    .insert({
      uid, app_id: APP_SLUG, event_kind: KIND, recipient: email,
      language: lang, resend_id: messageId,
      metadata: {
        fixture_id: fixtureId || null,
        home_team: vars.home_team,
        away_team: vars.away_team,
      },
    });
  if (insertErr && insertErr.code !== "23505") {
    console.error(`dedup insert failed: ${insertErr.message}`);
  }

  console.log(`✅ first_correct sent: ${email} (${lang}) message_id=${messageId}`);
  return new Response(JSON.stringify({ ok: true, message_id: messageId, language: lang }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
});
