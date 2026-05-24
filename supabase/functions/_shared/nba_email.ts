// Shared core for Predictify NBA instant emails.
//
// Three thin entrypoints (predictify-nba-first-win-email,
// predictify-nba-paywall-hit-email, predictify-nba-streak-broken-email)
// import handleNbaEmail() and pass their own multilingual template table.
// All the Resend plumbing, sender rotation, dedup, suppression, unsubscribe
// signing, and HTML/text rendering lives here so the three functions stay
// tiny and consistent.
//
// App scope: app_slug = "predictify_nba". Suppressions and dedup are keyed
// on this slug so NBA and soccer Predictify never cross-contaminate.

import { createClient } from "jsr:@supabase/supabase-js@2";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

export const APP_NAME = "Predictify NBA";
export const APP_SLUG = "predictify_nba";
const DEEPLINK_BASE = "https://predictifynba.com";

// Neutral sender pool (no soccer-specific domains). Hash-routed per uid so
// each user always sees a consistent "from", which protects deliverability.
const SENDER_POOL = [
  { email: "apps@kaynel.pl", name: "Ana" },
  { email: "hello@bestaiapps.site", name: "Alex" },
  { email: "apps@vitazelki.pl", name: "Casey" },
  { email: "hello@aibettips.io", name: "Jordan" },
];

export interface Template {
  subject: string;
  body: string[];
  cta: string;
}
export interface EmailConfig {
  kind: string; // event_kind for dedup, e.g. "first_correct"
  templates: Record<string, Template>;
  greetings: Record<string, string>;
  signoffs: Record<string, string>;
  footers: Record<string, string>;
}

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
  const body = paragraphs
    .map((p, i) => {
      const ph = p.replace(/\n/g, "<br>");
      if (i === 0) {
        return `<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;text-align:${align};">${ph}</p>`;
      }
      if (p.includes("P.S.") || p.includes("ملاحظة") || p.includes("P.D.") || p.includes("P.-S.")) {
        return `<div style="margin:32px 0 0;padding:16px 20px;background:#fff7ed;border-radius:8px;border:1px solid #fdba74;"><p style="margin:0;font-size:16px;color:#9a3412;line-height:1.7;text-align:${align};">${ph}</p></div>`;
      }
      return `<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:${align};">${ph}</p>`;
    })
    .join("");
  // NBA burnt-ember gradient on the CTA (matches the app's #E8491E primary).
  return `<!DOCTYPE html><html${dirAttr}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:${align};">
${body}
<div style="text-align:center;margin:36px 0;">
<a href="${ctaHref}" style="display:inline-block;background:linear-gradient(135deg,#FF753B 0%,#E8491E 100%);color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;">🏀 ${ctaText}</a>
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
    "PREDICTIFY NBA",
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
  // app slug encoded in the payload so the unsubscribe function scopes the
  // suppression to predictify_nba, not soccer predictify.
  const payload = `${email.toLowerCase().trim()}|${APP_SLUG}`;
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

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, content-type, x-client-info, apikey",
};

/// Main handler. Each NBA email entrypoint calls this with its config.
export async function handleNbaEmail(req: Request, cfg: EmailConfig): Promise<Response> {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405, headers: CORS });
  if (!RESEND_API_KEY) {
    return new Response(JSON.stringify({ error: "RESEND_API_KEY missing" }), { status: 500, headers: CORS });
  }

  let payload: Record<string, unknown>;
  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid JSON" }), { status: 400, headers: CORS });
  }

  const uid = String(payload.uid || "").trim();
  const email = String(payload.email || "").toLowerCase().trim();
  if (!uid) return new Response(JSON.stringify({ error: "missing field: uid" }), { status: 400, headers: CORS });
  if (!email) return new Response(JSON.stringify({ error: "missing field: email" }), { status: 400, headers: CORS });
  if (email.includes("cloudtestlabaccounts.com") || email.includes("example.com")) {
    return new Response(JSON.stringify({ ok: true, skipped: "test_account" }), { status: 200, headers: CORS });
  }

  // Normalise language: app sends 'pp' for European Portuguese — collapse to
  // 'pt' for email copy (we keep one Portuguese variant in templates).
  let lang = String(payload.language || "en").toLowerCase().split(/[_-]/)[0];
  if (lang === "pp") lang = "pt";
  if (!(lang in cfg.templates)) lang = "en";

  const vars = {
    first_name: String(payload.first_name || cfg.greetings[lang] || "there"),
    home_team: String(payload.home_team || "your team"),
    away_team: String(payload.away_team || ""),
    league_name: String(payload.league_name || "the NBA"),
    streak_length: String(payload.streak_length || ""),
    rank: String(payload.rank || ""),
  };
  const fixtureId = String(payload.fixture_id || "");

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  // Optional per-occurrence dedup. Recurring senders (e.g. the game-day cron)
  // pass a `dedup_date` so the dedup key becomes `${kind}_YYYY-MM-DD` — once
  // per user per day instead of once per lifetime. Distinct keys per day also
  // sidestep any UNIQUE(uid, event_kind) constraint on the table. Lifetime
  // senders omit it and keep the original once-ever behaviour.
  const dedupDate = String(payload.dedup_date || "").trim();
  const eventKind = dedupDate ? `${cfg.kind}_${dedupDate}` : cfg.kind;

  // Dedup — once per (uid, eventKind).
  const { data: existing } = await supabase
    .from("instant_emails_sent")
    .select("id, sent_at")
    .eq("uid", uid)
    .eq("event_kind", eventKind)
    .maybeSingle();
  if (existing) {
    return new Response(JSON.stringify({ ok: true, duplicate: true, sent_at: existing.sent_at }), {
      status: 200,
      headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  // Suppression — never email unsubscribed NBA users.
  const { data: suppressed } = await supabase
    .from("email_suppressions")
    .select("recipient")
    .eq("recipient", email)
    .eq("app", APP_SLUG)
    .maybeSingle();
  if (suppressed) {
    return new Response(JSON.stringify({ ok: true, skipped: "suppressed" }), {
      status: 200,
      headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  const tpl = cfg.templates[lang] || cfg.templates.en;
  const subject = interpolate(tpl.subject, vars);
  const paragraphs = tpl.body.map((p) => interpolate(p, vars));
  const ctaText = tpl.cta;

  const sender = pickSender(uid);
  const ref = await userRef(email);
  const deeplink = fixtureId
    ? `${DEEPLINK_BASE}/?ref=email&kind=${cfg.kind}&fixture=${fixtureId}`
    : `${DEEPLINK_BASE}/?ref=email&kind=${cfg.kind}`;

  const unsubUrl = await buildUnsubUrl(email);
  const isRtl = lang === "ar";
  const signoff = cfg.signoffs[lang] || cfg.signoffs.en;
  const footer = cfg.footers[lang] || cfg.footers.en;

  const html = buildHtml(paragraphs, ctaText, deeplink, sender.name, signoff, footer, unsubUrl, isRtl);
  const text = buildText(paragraphs, ctaText, deeplink, signoff, sender.name, footer, unsubUrl);

  const tags = [
    { name: "app", value: APP_SLUG },
    { name: "kind", value: cfg.kind },
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
      subject,
      html,
      text,
      reply_to: sender.email,
      tags,
      headers: { "X-Entity-Ref-ID": ref },
    }),
  });

  let resendData: Record<string, unknown>;
  try {
    resendData = await resendRes.json();
  } catch {
    resendData = { raw: await resendRes.text() };
  }

  if (!resendRes.ok) {
    console.error(`Resend ${resendRes.status}: ${JSON.stringify(resendData)}`);
    return new Response(JSON.stringify({ error: "send failed", details: resendData }), {
      status: 500,
      headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  const messageId = String((resendData as Record<string, unknown>).id || "");
  await supabase.from("instant_emails_sent").insert({
    uid,
    app_id: APP_SLUG,
    event_kind: eventKind,
    recipient: email,
    language: lang,
    resend_id: messageId,
    metadata: {
      fixture_id: fixtureId || null,
      home_team: vars.home_team,
      away_team: vars.away_team,
    },
  });

  return new Response(JSON.stringify({ ok: true, id: messageId, language: lang }), {
    status: 200,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}
