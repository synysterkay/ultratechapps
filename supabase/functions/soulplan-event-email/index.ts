// Supabase Edge Function: soulplan-event-email
// Event-triggered, multilingual SoulPlan lifecycle emails (no cron — fired by
// the app at the moment they matter, so they work on Firebase Spark).
//
// POST https://<project>.supabase.co/functions/v1/soulplan-event-email
//   Authorization: Bearer <SUPABASE_ANON_KEY>
//   { uid, email, kind, language?, partner?, time?, dateRequestId? }
//
//   kind: "date_request" | "date_confirmed"
//   language: app's canonical BCP-47 tag (pt-BR, zh-Hans, …) — normalized here.
//
// Idempotent: one row per (uid, "<kind>_<dateRequestId>") in instant_emails_sent,
// so retries / both-partner sends don't duplicate. Localized to the recipient.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { CONTENT, EmailContent } from "./content.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const APP_NAME = "SoulPlan";
const APP_SLUG = "soulplan";
const APP_STORE_URL =
  "https://apps.apple.com/app/soulplan-plan-dates-together/id6702018988";

// soulplan.app is NOT verified in Resend, so sending from it 403s on every
// email (the exact failure mode that silently broke the main pipeline via
// kaynel.pl). Use verified-in-Resend domains only. Persona names are kept —
// the user sees "Mia <hello@bestaiapps.site>", which is fine. Re-point to
// hello@soulplan.app once that domain is added + verified in Resend.
const SENDER_POOL = [
  { email: "hello@bestaiapps.site", name: "Mia" },
  { email: "hello@bestaiapps.site", name: "Theo" },
];

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const GREETING: Record<string, string> = {
  en: "Hi", es: "Hola", fr: "Bonjour", pt: "Olá", de: "Hallo", it: "Ciao",
  pl: "Cześć", tr: "Merhaba", ar: "مرحبًا", ru: "Привет", hi: "नमस्ते",
  id: "Hai", ja: "こんにちは", ko: "안녕하세요", zh: "你好",
};

function pickLang(raw: string | undefined): string {
  const tag = (raw || "en").toString();
  if (CONTENT.date_request[tag]) return tag; // unlikely (we key by base)
  const base = tag.split(/[-_]/)[0].toLowerCase();
  return CONTENT.date_request[base] ? base : "en";
}

function sub(s: string, vars: Record<string, string>): string {
  return s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
}

function buildHtml(
  c: EmailContent,
  lang: string,
  vars: Record<string, string>,
): string {
  const isRtl = lang === "ar";
  const dir = isRtl ? "rtl" : "ltr";
  const greeting = GREETING[lang] || GREETING.en;
  const bodyHtml = c.body
    .map(
      (p) =>
        `<p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#3a3a3d">${sub(p, vars)}</p>`,
    )
    .join("");
  return `<!doctype html><html dir="${dir}"><body style="margin:0;background:#fffbfc;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
  <div style="max-width:520px;margin:0 auto;padding:32px 24px">
    <div style="text-align:center;font-size:22px;font-weight:700;color:#e91c40;margin-bottom:8px">💛 ${APP_NAME}</div>
    <div style="background:#ffffff;border-radius:20px;padding:28px 24px;box-shadow:0 8px 24px rgba(0,0,0,0.05)">
      <h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;color:#1c1a1d">${sub(c.heading, vars)}</h1>
      <p style="margin:0 0 16px;font-size:16px;color:#3a3a3d">${greeting},</p>
      ${bodyHtml}
      <div style="text-align:center;margin-top:24px">
        <a href="${APP_STORE_URL}" style="display:inline-block;background:#e91c40;color:#ffffff;text-decoration:none;font-weight:700;font-size:16px;padding:14px 28px;border-radius:28px">${sub(c.cta, vars)}</a>
      </div>
    </div>
    <p style="text-align:center;font-size:12px;color:#9a9aa0;margin-top:20px">${APP_NAME} — plan dates together 💛</p>
  </div></body></html>`;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const j = (b: unknown, status = 200) =>
    new Response(JSON.stringify(b), {
      status,
      headers: { ...cors, "Content-Type": "application/json" },
    });

  try {
    if (!RESEND_API_KEY) return j({ error: "RESEND_API_KEY missing" }, 500);
    const { uid, email, kind, language, partner, time, dateRequestId } =
      await req.json();
    if (!email || !kind || !CONTENT[kind]) {
      return j({ error: "missing/invalid email or kind" }, 400);
    }

    const lang = pickLang(language);
    const c: EmailContent = CONTENT[kind][lang] || CONTENT[kind].en;
    const vars = {
      partner: partner || "Your partner",
      time: time || "",
    };

    const supabase =
      SUPABASE_URL && SUPABASE_SERVICE_ROLE_KEY
        ? createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        : null;
    // Per-event idempotency: kind + dateRequestId (date events recur, so we
    // can't dedupe by lifetime kind alone).
    const eventKind = dateRequestId ? `${kind}_${dateRequestId}` : kind;

    if (supabase && uid) {
      const { data: existing } = await supabase
        .from("instant_emails_sent")
        .select("id")
        .eq("uid", uid)
        .eq("event_kind", eventKind)
        .maybeSingle();
      if (existing) return j({ ok: true, skipped: "already_sent" });
    }

    const sender = SENDER_POOL[Math.floor(Math.random() * SENDER_POOL.length)];
    const resendRes = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: `${sender.name} <${sender.email}>`,
        to: [email.toLowerCase().trim()],
        subject: sub(c.subject, vars),
        html: buildHtml(c, lang, vars),
        headers: { "X-Entity-Ref-ID": eventKind },
        tags: [
          { name: "app", value: APP_SLUG },
          { name: "kind", value: kind },
          { name: "language", value: lang },
        ],
      }),
    });
    const resendJson = await resendRes.json();
    if (!resendRes.ok) return j({ error: resendJson }, 502);

    if (supabase && uid) {
      await supabase.from("instant_emails_sent").insert({
        uid,
        app_id: APP_SLUG,
        event_kind: eventKind,
        recipient: email.toLowerCase().trim(),
        language: lang,
        resend_id: resendJson.id ?? null,
      });
    }
    return j({ ok: true, id: resendJson.id, language: lang });
  } catch (e) {
    return j({ error: String(e) }, 500);
  }
});
