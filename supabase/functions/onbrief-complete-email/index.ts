// Supabase Edge Function: onbrief-complete-email
// Instant "brief is done — export the PDF" for Onbrief (work research writer).
//
// Called by Flutter InstantEmailService after theses.{id}.status = completed:
//   POST https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/onbrief-complete-email
//   Authorization: Bearer <SUPABASE_ANON_KEY>
// Dedup: instant_emails_sent (uid, event_kind='onbrief_complete')

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { SENDER_POOL_ONBRIEF as SENDER_POOL } from "../_shared/sender_pool.ts";
import { hasEmailCredentials, isSendFailureBounce, resolveSender, sendEmail } from "../_shared/email_transport.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

const APP_NAME = "Onbrief";
const APP_SLUG = "onbrief";
const KIND = "onbrief_complete";
const CTA_URL = Deno.env.get("ONBRIEF_CTA_URL") ||
  "https://play.google.com/store/apps/details?id=com.onbrief.research";

const TEMPLATE = {
  subject: "{{first_name}}, the brief is done — export the PDF",
  body: [
    "{{first_name}} — your {{work_type}} on {{topic}} is finished. That's the hard part.",
    "Now get it off the phone. Open Onbrief, go to Export, save the PDF. A brief that only lives in the app is a draft your team never sees.",
    "P.S. Save a copy to Files while you're there. Future-you will not want to regenerate this under a deadline.",
  ],
  cta: "Export my PDF",
};

function interpolate(s: string, vars: Record<string, string>): string {
  return s.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? `{{${k}}}`);
}

async function userRef(email: string): Promise<string> {
  const data = new TextEncoder().encode(`${REF_SALT}:${email.toLowerCase().trim()}`);
  const buf = await crypto.subtle.digest("SHA-256", data);
  const hex = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
  return hex.slice(0, 16);
}

function buildHtml(greeting: string, paragraphs: string[], ctaText: string, ctaHref: string): string {
  let body = "";
  paragraphs.forEach((p, i) => {
    const ph = p.replace(/\n/g, "<br>");
    if (p.includes("P.S.")) {
      body += `<div style="margin:24px 0 0;padding:14px 18px;background:#CCFBF1;border-radius:10px;border:1px solid #99F6E4;"><p style="margin:0;font-size:15px;color:#0F766E;line-height:1.7;">${ph}</p></div>`;
    } else {
      const size = i === 0 ? "18px" : "16px";
      const color = i === 0 ? "#0A0A0A" : "#52525B";
      const weight = i === 0 ? "font-weight:600;" : "";
      body += `<p style="margin:0 0 20px;font-size:${size};color:${color};line-height:1.7;${weight}">${ph}</p>`;
    }
  });
  return `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#FAFAFA;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:12px;border:1px solid #E4E4E7;">
        <tr><td style="padding:28px 32px 8px;text-align:center;">
          <p style="margin:0;font-size:18px;font-weight:700;color:#0A0A0A;">Onbrief</p>
          <p style="margin:4px 0 0;font-size:13px;color:#52525B;">Research writer for work</p>
        </td></tr>
        <tr><td style="padding:24px 32px 8px;">
          <p style="margin:0 0 20px;font-size:16px;color:#52525B;">${greeting}</p>
          ${body}
        </td></tr>
        <tr><td style="padding:8px 32px 32px;text-align:center;">
          <a href="${ctaHref}" style="display:inline-block;background:#0F766E;color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:15px;">${ctaText}</a>
        </td></tr>
        <tr><td style="padding:0 32px 28px;">
          <p style="margin:0;font-size:15px;color:#52525B;">Best,<br><strong style="color:#0A0A0A;">Onbrief</strong></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;
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
  if (!hasEmailCredentials()) {
    return new Response(JSON.stringify({ error: "email credentials missing" }), { status: 500 });
  }

  let payload: Record<string, unknown>;
  try { payload = await req.json(); }
  catch { return new Response(JSON.stringify({ error: "invalid JSON" }), { status: 400 }); }

  const uid = String(payload.uid || "").trim();
  const email = String(payload.email || "").toLowerCase().trim();
  if (!uid || !email) {
    return new Response(JSON.stringify({ error: "missing uid or email" }), { status: 400 });
  }

  const firstName = String(payload.first_name || "there").trim() || "there";
  const workType = String(payload.work_type || "brief").trim() || "brief";
  const topic = String(payload.topic || "your brief").trim() || "your brief";
  const language = String(payload.language || "en").slice(0, 8);

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  const { data: existing } = await supabase
    .from("instant_emails_sent")
    .select("uid")
    .eq("uid", uid)
    .eq("event_kind", KIND)
    .maybeSingle();
  if (existing) {
    return new Response(JSON.stringify({ ok: true, duplicate: true }), {
      status: 200,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }

  const vars = { first_name: firstName, work_type: workType, topic };
  const subject = interpolate(TEMPLATE.subject, vars);
  const paragraphs = TEMPLATE.body.map((p) => interpolate(p, vars));
  const sender = resolveSender(SENDER_POOL[0], APP_SLUG);
  const ref = await userRef(email);
  const html = buildHtml(`Hi ${firstName},`, paragraphs, TEMPLATE.cta, CTA_URL);

  const sendResult = await sendEmail({
    fromName: APP_NAME,
    fromEmail: sender.email,
    to: email,
    subject,
    html,
    replyTo: sender.email,
    tags: [
      { name: "app", value: APP_SLUG },
      { name: "kind", value: KIND },
      { name: "language", value: language },
    ],
    refId: ref,
  });

  if (!sendResult.ok) {
    if (isSendFailureBounce(sendResult)) {
      console.log(`BOUNCED: ${email}`);
    }
    return new Response(JSON.stringify({ error: "send failed", details: sendResult.details }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  await supabase.from("instant_emails_sent").upsert(
    {
      uid,
      app_id: APP_SLUG,
      event_kind: KIND,
      recipient: email,
      language,
      resend_id: sendResult.id || null,
      metadata: { topic, work_type: workType },
    },
    { onConflict: "uid,event_kind" },
  );

  return new Response(JSON.stringify({ ok: true, message_id: sendResult.id }), {
    status: 200,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
});
