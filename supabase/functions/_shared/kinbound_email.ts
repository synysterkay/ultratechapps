// Shared handler for Kinbound instant emails (first script, copilot limit, account linked).

import { createClient } from "jsr:@supabase/supabase-js@2";
import { SENDER_POOL_FULL as SENDER_POOL } from "./sender_pool.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

export const APP_NAME = "Kinbound";
export const APP_SLUG = "kinbound";
export const APP_STORE_URL =
  "https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071";

export interface KinboundTemplate {
  subject: string;
  body: string[];
  cta: string;
}

export interface KinboundEmailConfig {
  kind: string;
  appId: string;
  templates: Record<string, KinboundTemplate>;
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

function interpolate(s: string, vars: Record<string, string>): string {
  return s.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? `{{${k}}}`);
}

function buildHtml(
  greeting: string,
  paragraphs: string[],
  ctaText: string,
  ctaHref: string,
  signoff: string,
  senderName: string,
  footer: string,
  isRtl: boolean,
): string {
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const align = isRtl ? "right" : "left";
  const body = paragraphs
    .map((p, i) => {
      const ph = p.replace(/\n/g, "<br>");
      if (p.includes("P.S.") || p.includes("P.D.")) {
        return `<div style="margin:24px 0 0;padding:14px 18px;background:#FAF6F0;border-radius:10px;border:1px solid #FDE7D2;"><p style="margin:0;font-size:15px;color:#867E76;line-height:1.7;text-align:${align};">${ph}</p></div>`;
      }
      const weight = i === 0 ? "font-weight:600;" : "";
      const color = i === 0 ? "#2A2520" : "#867E76";
      return `<p style="margin:0 0 20px;font-size:17px;color:${color};line-height:1.7;${weight}text-align:${align};">${ph}</p>`;
    })
    .join("");
  return `<!DOCTYPE html><html${dirAttr}><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2A2520;max-width:600px;margin:0 auto;padding:40px 24px;background:#FAF6F0;text-align:${align};">
<div style="text-align:center;margin:0 0 24px;"><div style="display:inline-block;width:56px;height:56px;border-radius:16px;background:linear-gradient(135deg,#E29578,#D4A24C);line-height:56px;font-size:28px;">🌱</div></div>
<p style="margin:0 0 20px;font-size:17px;color:#867E76;text-align:${align};">${greeting}</p>
${body}
<div style="text-align:center;margin:36px 0;"><a href="${ctaHref}" style="display:inline-block;background:linear-gradient(135deg,#E29578 0%,#D4A24C 100%);color:#fff;padding:14px 32px;text-decoration:none;border-radius:12px;font-weight:700;font-size:16px;">${ctaText}</a></div>
<p style="margin:32px 0 0;font-size:17px;color:#867E76;text-align:${align};">${signoff}<br><strong style="color:#2A2520;">${senderName}</strong></p>
<div style="margin-top:48px;padding-top:24px;border-top:1px solid #FDE7D2;text-align:center;"><p style="margin:0;font-size:12px;color:#C4BAB0;">${footer}</p></div>
</body></html>`;
}

const GREETINGS: Record<string, string> = {
  en: "Hey there,", es: "Hola,", fr: "Salut,", de: "Hallo,", pt: "Olá,",
  it: "Ciao,", nl: "Hallo,", ja: "こんにちは、", ko: "안녕하세요,", zh: "你好，",
  ar: "مرحبًا،", hi: "नमस्ते,", id: "Halo,", pl: "Cześć,", ru: "Привет,", tr: "Merhaba,",
};
const SIGNOFFS: Record<string, string> = {
  en: "Warmly,", es: "Con cariño,", fr: "À bientôt,", de: "Herzlich,", pt: "Com carinho,",
  it: "A presto,", nl: "Hartelijk,", ja: "ではまた、", ko: "따뜻하게,", zh: "祝好，",
  ar: "مع التحية،", hi: "सादर,", id: "Salam hangat,", pl: "Pozdrawiam,", ru: "Тепло,", tr: "Sevgilerle,",
};

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, content-type, x-client-info, apikey",
};

const STRUGGLE_LABELS: Record<string, string> = {
  tantrum: "a meltdown", bedtime: "bedtime", siblings: "a sibling fight",
  defiance: "not listening", anxious: "anxiety", screen: "screen time",
  mealtime: "mealtime", morning: "morning chaos", teen: "a shut-down teen",
  myself: "feeling overwhelmed",
};

export async function handleKinboundEmail(
  req: Request,
  cfg: KinboundEmailConfig,
  buildVars: (payload: Record<string, unknown>, lang: string) => Record<string, string>,
): Promise<Response> {
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

  let lang = String(payload.language || "en").toLowerCase();
  if (lang.startsWith("zh")) lang = "zh";
  else lang = lang.split(/[_-]/)[0];
  if (!(lang in cfg.templates)) lang = "en";

  const vars = buildVars(payload, lang);
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  const { data: existing } = await supabase
    .from("instant_emails_sent")
    .select("id, sent_at")
    .eq("uid", uid)
    .eq("event_kind", cfg.kind)
    .maybeSingle();
  if (existing) {
    return new Response(JSON.stringify({ ok: true, duplicate: true, sent_at: existing.sent_at }), {
      status: 200, headers: { "Content-Type": "application/json", ...CORS },
    });
  }

  const tpl = cfg.templates[lang] || cfg.templates.en;
  const subject = interpolate(tpl.subject, vars);
  const paragraphs = tpl.body.map((p) => interpolate(p, vars));
  const ctaText = interpolate(tpl.cta, vars);
  const sender = pickSender(uid);
  const ref = await userRef(email);
  const ctaHref = `${APP_STORE_URL}?ref=${ref}`;
  const isRtl = lang === "ar";
  const greeting = `${GREETINGS[lang] || GREETINGS.en} ${vars.first_name || ""}`.trim();
  const signoff = SIGNOFFS[lang] || SIGNOFFS.en;
  const footer = cfg.footers[lang] || cfg.footers.en;
  const html = buildHtml(greeting, paragraphs, ctaText, ctaHref, signoff, sender.name, footer, isRtl);

  const resendRes = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: `${APP_NAME} <${sender.email}>`,
      to: [email],
      subject,
      html,
      reply_to: sender.email,
      tags: [
        { name: "app", value: APP_SLUG },
        { name: "kind", value: cfg.kind },
        { name: "language", value: lang },
      ],
      headers: { "X-Entity-Ref-ID": ref },
    }),
  });

  const resendData = await resendRes.json().catch(() => ({}));
  if (!resendRes.ok) {
    return new Response(JSON.stringify({ error: "send failed", details: resendData }), {
      status: 500, headers: { "Content-Type": "application/json", ...CORS },
    });
  }

  const messageId = String((resendData as { id?: string }).id || "");
  await supabase.from("instant_emails_sent").insert({
    uid,
    app_id: cfg.appId,
    event_kind: cfg.kind,
    recipient: email,
    language: lang,
    resend_id: messageId,
    metadata: payload,
  });

  return new Response(JSON.stringify({ ok: true, message_id: messageId, language: lang }), {
    status: 200,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

export function struggleLabel(id: string): string {
  return STRUGGLE_LABELS[id] || "a hard moment";
}
