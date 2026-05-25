// Supabase Edge Function: predictify-paywall-hit-email
//
// Fires INSTANTLY the first time a Predictify user sees the Pro paywall
// (and doesn't convert). Hits at peak intent — they just LOOKED at the
// upgrade screen. Cron-based upgrade nudges are hours late by then.
//
// Called by the Predictify app from the Superwall delegate / paywall
// presentation handler the first time `users/{uid}.paywallSeenAt` is
// null and the paywall is shown:
//
//   POST .../functions/v1/predictify-paywall-hit-email
//   {
//     "uid": "...",
//     "email": "user@example.com",
//     "language": "en",
//     "first_name": "Marcus",
//     "trigger_source": "match_detail"  // optional, where in the app
//   }
//
// Dedup: (uid, 'paywall_hit') lifetime. By design we only fire once —
// repeat paywall views become noise (the user already got the pitch).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

const APP_SLUG = "predictify";
const KIND = "paywall_hit";

const SENDER_POOL = [  // all 7 verified-in-Resend senders; health-based rotation picks the best
  { email: "hello@bestaiapps.site", name: "Alex" },
  { email: "hello@aibettips.io", name: "Jordan" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
  { email: "hello@thesisgenerator.io", name: "Morgan" },
  { email: "hello@passedai.io", name: "Taylor" },
  { email: "hello@academicsatire.com", name: "Riley" },
  { email: "tips@predictify.fun", name: "Drew" },
];

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

const TEMPLATES: Record<string, { subject: string; body: string[]; cta: string }> = {
  en: {
    subject: "About the Pro paywall, {{first_name}} — quick context",
    body: [
      "Hey {{first_name}},",
      "Saw you opened the Pro paywall earlier. Not pushing — just wanted to give you the short version of what's actually behind it, in case the in-app screen was too dense.",
      "Pro unlocks three things that matter: the 'Strongest Signal' calibrated call on every match (~88% hit rate historically on Elite-tier games), full coverage of every betting market (BTTS, over/under, totals, not just match result), and the prediction history that lets you watch your own accuracy climb instead of guessing.",
      "If you're picking matches anyway, Pro turns one signal into seven. If you're not picking matches yet, ignore this and the model still works.",
      "7-day free trial, no card required, cancel anytime in one tap. If it doesn't move your numbers, you walk away with the data.",
    ],
    cta: "Try Pro free for 7 days",
  },
};

function loadTemplate(lang: string) {
  return TEMPLATES[lang] || TEMPLATES.en;
}

const SIGNOFFS: Record<string, string> = { en: "Talk soon," };
const FOOTERS: Record<string, string> = {
  en: "You're receiving this because you opened the Pro paywall in Predictify.",
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
    return `<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:${align};">${ph}</p>`;
  }).join("");
  return `<!DOCTYPE html><html${dirAttr}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:${align};">
${body}
<div style="text-align:center;margin:36px 0;">
<a href="${ctaHref}" style="display:inline-block;background:linear-gradient(135deg,#FBBF24 0%,#F59E0B 100%);color:#0E1117;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;">⭐ ${ctaText}</a>
</div>
<p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:${align};">${signoff}<br><strong style="color:#1f2937;">${senderName}</strong></p>
<div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
<p style="margin:0 0 6px;font-size:12px;color:#9ca3af;">${footer}</p>
<p style="margin:0;font-size:12px;color:#9ca3af;"><a href="${unsubUrl}" style="color:#9ca3af;">Unsubscribe</a></p>
</div></body></html>`;
}

function buildText(paras: string[], cta: string, ctaHref: string, signoff: string, sender: string, footer: string, unsub: string) {
  return [
    "PREDICTIFY", "",
    paras.join("\n\n"), "",
    `${cta}: ${ctaHref}`, "",
    signoff, sender, "",
    "—", footer, `Unsubscribe: ${unsub}`,
  ].join("\n");
}

async function buildUnsubUrl(email: string): Promise<string> {
  const base = Deno.env.get("PREDICTIFY_UNSUBSCRIBE_URL") ||
    "https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-unsubscribe";
  const secret = Deno.env.get("PREDICTIFY_UNSUBSCRIBE_SECRET") || "";
  const payload = `${email.toLowerCase().trim()}|predictify`;
  const e = btoa(payload).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  if (!secret) return `${base}?e=${e}`;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(e));
  const hex = Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
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
  if (!RESEND_API_KEY) return new Response(JSON.stringify({ error: "RESEND_API_KEY missing" }), { status: 500 });

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
  };
  const triggerSource = String(payload.trigger_source || "");

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  const { data: existing } = await supabase
    .from("instant_emails_sent")
    .select("id, sent_at")
    .eq("uid", uid)
    .eq("event_kind", KIND)
    .maybeSingle();
  if (existing) {
    return new Response(JSON.stringify({ ok: true, duplicate: true, sent_at: existing.sent_at }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  }

  const { data: suppressed } = await supabase
    .from("email_suppressions")
    .select("recipient")
    .eq("recipient", email)
    .eq("app", APP_SLUG)
    .maybeSingle();
  if (suppressed) {
    return new Response(JSON.stringify({ ok: true, skipped: "suppressed" }), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  }

  const tpl = loadTemplate(lang);
  const subject = interpolate(tpl.subject, vars);
  const paragraphs = tpl.body.map((p) => interpolate(p, vars));

  const sender = pickSender(uid);
  const ref = await userRef(email);
  const deeplink = `https://predictifyfootball.com/?ref=email&kind=${KIND}`;
  const unsubUrl = await buildUnsubUrl(email);
  const isRtl = lang === "ar";
  const signoff = SIGNOFFS[lang] || SIGNOFFS.en;
  const footer = FOOTERS[lang] || FOOTERS.en;

  const html = buildHtml(paragraphs, tpl.cta, deeplink, sender.name, signoff, footer, unsubUrl, isRtl);
  const text = buildText(paragraphs, tpl.cta, deeplink, signoff, sender.name, footer, unsubUrl);

  const tags = [
    { name: "app", value: APP_SLUG },
    { name: "kind", value: KIND },
    { name: "email_num", value: "instant" },
    { name: "language", value: sanitizeTagValue(lang) },
    { name: "segment", value: "instant" },
    { name: "system", value: "instant_v1" },
  ];

  const resendRes = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: `${sender.name} <${sender.email}>`,
      to: [email],
      subject, html, text,
      reply_to: sender.email, tags,
      headers: { "X-Entity-Ref-ID": ref },
    }),
  });

  let resendData: Record<string, unknown>;
  try { resendData = await resendRes.json(); }
  catch { resendData = { raw: await resendRes.text() }; }

  if (!resendRes.ok) {
    console.error(`Resend ${resendRes.status}: ${JSON.stringify(resendData)}`);
    return new Response(JSON.stringify({ error: "send failed", details: resendData }), {
      status: 500, headers: { "Content-Type": "application/json" },
    });
  }

  const messageId = String((resendData as Record<string, unknown>).id || "");
  const { error: insertErr } = await supabase
    .from("instant_emails_sent")
    .insert({
      uid, app_id: APP_SLUG, event_kind: KIND, recipient: email,
      language: lang, resend_id: messageId,
      metadata: { trigger_source: triggerSource || null },
    });
  if (insertErr && insertErr.code !== "23505") {
    console.error(`dedup insert failed: ${insertErr.message}`);
  }

  console.log(`✅ paywall_hit sent: ${email} (${lang}) message_id=${messageId}`);
  return new Response(JSON.stringify({ ok: true, message_id: messageId, language: lang }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
});
