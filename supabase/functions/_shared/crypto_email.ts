/**
 * Shared helpers for Predictify Crypto instant emails.
 */
import { createClient, SupabaseClient } from "jsr:@supabase/supabase-js@2";
import { SENDER_POOL_CRYPTO } from "./sender_pool.ts";
import { hasEmailCredentials, resolveSender, sendEmail } from "./email_transport.ts";
import { isRecipientBlocked } from "./email_suppressions.ts";

export const CRYPTO_APP_SLUG = "predictify_crypto";
export const CRYPTO_APP_NAME = "Predictify Crypto";
export const CRYPTO_PLAY_URL =
  "https://play.google.com/store/apps/details?id=com.crypto.trading.ai.analyzer";

const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

export function corsHeaders(): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers":
      "authorization, content-type, x-client-info, apikey",
  };
}

export function pickCryptoSender(uid: string) {
  let h = 0;
  for (const c of uid) h = (h * 31 + c.charCodeAt(0)) | 0;
  return SENDER_POOL_CRYPTO[Math.abs(h) % SENDER_POOL_CRYPTO.length];
}

export async function userRef(email: string): Promise<string> {
  const data = new TextEncoder().encode(
    `${REF_SALT}:${email.toLowerCase().trim()}`,
  );
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 16);
}

export function sanitizeTagValue(v: string): string {
  return v.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 256);
}

export function interpolate(
  s: string,
  vars: Record<string, string>,
): string {
  return s.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? `{{${k}}}`);
}

export function buildHtml(opts: {
  paragraphs: string[];
  ctaText: string;
  ctaHref: string;
  senderName: string;
  signoff: string;
  footer: string;
  unsubUrl: string;
}): string {
  const { paragraphs, ctaText, ctaHref, senderName, signoff, footer, unsubUrl } =
    opts;
  const body = paragraphs.map((p, i) => {
    const ph = p.replace(/\n/g, "<br>");
    if (i === 0) {
      return `<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;">${ph}</p>`;
    }
    if (p.includes("P.S.")) {
      return `<div style="margin:32px 0 0;padding:16px 20px;background:#faf5ff;border-radius:8px;border:1px solid:#e9d5ff;"><p style="margin:0;font-size:16px;color:#6b21a8;line-height:1.7;">${ph}</p></div>`;
    }
    return `<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;">${ph}</p>`;
  }).join("");
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;">
${body}
<div style="text-align:center;margin:36px 0;">
<a href="${ctaHref}" style="display:inline-block;background:linear-gradient(135deg,#A855F7 0%,#7C3AED 100%);color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;">${ctaText}</a>
</div>
<p style="margin:32px 0 0;font-size:17px;color:#4b5563;">${signoff}<br><strong style="color:#1f2937;">${senderName}</strong></p>
<div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;">
<p style="margin:0 0 6px;font-size:12px;color:#9ca3af;">${footer}</p>
<p style="margin:0;font-size:12px;color:#9ca3af;"><a href="${unsubUrl}" style="color:#9ca3af;">Unsubscribe</a></p>
</div></body></html>`;
}

export function buildText(opts: {
  paragraphs: string[];
  ctaText: string;
  ctaHref: string;
  signoff: string;
  senderName: string;
  footer: string;
  unsubUrl: string;
}): string {
  const { paragraphs, ctaText, ctaHref, signoff, senderName, footer, unsubUrl } =
    opts;
  return [
    "PREDICTIFY CRYPTO",
    "",
    paragraphs.join("\n\n"),
    "",
    `${ctaText}: ${ctaHref}`,
    "",
    signoff,
    senderName,
    "",
    "—",
    footer,
    `Unsubscribe: ${unsubUrl}`,
  ].join("\n");
}

export async function buildUnsubUrl(email: string): Promise<string> {
  const base = Deno.env.get("PREDICTIFY_UNSUBSCRIBE_URL") ||
    "https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/predictify-unsubscribe";
  const secret = Deno.env.get("PREDICTIFY_UNSUBSCRIBE_SECRET") || "";
  const payload = `${email.toLowerCase().trim()}|${CRYPTO_APP_SLUG}`;
  const e = btoa(payload).replace(/\+/g, "-").replace(/\//g, "_").replace(
    /=+$/,
    "",
  );
  if (!secret) return `${base}?e=${e}`;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(e),
  );
  const hex = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
  return `${base}?e=${e}&s=${hex}`;
}

export type CryptoTemplate = {
  subject: string;
  body: string[];
  cta: string;
};

export async function handleCryptoInstantEmail(opts: {
  req: Request;
  kind: string;
  templates: Record<string, CryptoTemplate>;
  footer: string;
  buildVars: (payload: Record<string, unknown>) => Record<string, string>;
  ctaHref?: (payload: Record<string, unknown>, kind: string) => string;
}): Promise<Response> {
  const { req, kind, templates, footer, buildVars, ctaHref } = opts;

  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders() });
  }
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }
  if (!hasEmailCredentials()) {
    return new Response(JSON.stringify({ error: "email credentials missing" }), {
      status: 500,
    });
  }

  let payload: Record<string, unknown>;
  try {
    payload = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid JSON" }), {
      status: 400,
    });
  }

  const uid = String(payload.uid || "").trim();
  const email = String(payload.email || "").toLowerCase().trim();
  if (!uid) {
    return new Response(JSON.stringify({ error: "missing field: uid" }), {
      status: 400,
    });
  }
  if (!email) {
    return new Response(JSON.stringify({ error: "missing field: email" }), {
      status: 400,
    });
  }
  if (
    email.includes("cloudtestlabaccounts.com") ||
    email.includes("example.com")
  ) {
    return new Response(JSON.stringify({ ok: true, skipped: "test_account" }), {
      status: 200,
      headers: { "Content-Type": "application/json", ...corsHeaders() },
    });
  }

  let lang = String(payload.language || "en").toLowerCase().split(/[_-]/)[0];
  if (!(lang in templates)) lang = "en";

  const supabase: SupabaseClient = createClient(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
  );

  const { data: existing } = await supabase
    .from("instant_emails_sent")
    .select("id, sent_at")
    .eq("uid", uid)
    .eq("event_kind", kind)
    .maybeSingle();
  if (existing) {
    return new Response(
      JSON.stringify({ ok: true, duplicate: true, sent_at: existing.sent_at }),
      {
        status: 200,
        headers: { "Content-Type": "application/json", ...corsHeaders() },
      },
    );
  }

  if (await isRecipientBlocked(supabase, email, CRYPTO_APP_SLUG)) {
    return new Response(JSON.stringify({ ok: true, skipped: "suppressed" }), {
      status: 200,
      headers: { "Content-Type": "application/json", ...corsHeaders() },
    });
  }

  const vars = buildVars(payload);
  const tpl = templates[lang] || templates.en;
  const subject = interpolate(tpl.subject, vars);
  const paragraphs = tpl.body.map((p) => interpolate(p, vars));
  const sender = resolveSender(pickCryptoSender(uid), CRYPTO_APP_SLUG);
  const href = ctaHref
    ? ctaHref(payload, kind)
    : `https://play.google.com/store/apps/details?id=com.crypto.trading.ai.analyzer&ref=email&kind=${kind}`;
  const unsubUrl = await buildUnsubUrl(email);

  const html = buildHtml({
    paragraphs,
    ctaText: tpl.cta,
    ctaHref: href,
    senderName: sender.name,
    signoff: "Talk soon,",
    footer,
    unsubUrl,
  });
  const text = buildText({
    paragraphs,
    ctaText: tpl.cta,
    ctaHref: href,
    signoff: "Talk soon,",
    senderName: sender.name,
    footer,
    unsubUrl,
  });

  const tags = [
    { name: "app", value: CRYPTO_APP_SLUG },
    { name: "kind", value: kind },
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
    refId: await userRef(email),
  });

  if (!sendResult.ok) {
    return new Response(
      JSON.stringify({ error: "send_failed", details: sendResult.details }),
      {
        status: 500,
        headers: { "Content-Type": "application/json", ...corsHeaders() },
      },
    );
  }

  const messageId = sendResult.id || "";
  const { error: insertErr } = await supabase.from("instant_emails_sent").insert({
    uid,
    app_id: CRYPTO_APP_SLUG,
    event_kind: kind,
    recipient: email,
    language: lang,
    resend_id: messageId,
    metadata: {
      ...vars,
      trigger_source: payload.trigger_source ?? null,
      asset: payload.asset ?? null,
    },
  });
  if (insertErr && insertErr.code !== "23505") {
    console.error(`crypto instant dedup insert failed: ${insertErr.message}`);
  }

  return new Response(
    JSON.stringify({ ok: true, id: messageId }),
    {
      status: 200,
      headers: { "Content-Type": "application/json", ...corsHeaders() },
    },
  );
}
