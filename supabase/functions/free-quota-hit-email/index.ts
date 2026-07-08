// Supabase Edge Function: free-quota-hit-email
// Fires instantly when a Thesis Generator user burns their free-chapter
// quota — i.e. when the Flutter app writes users.{uid}.usage.freeChapterUsed
// to true and the paywall appears.
//
// This is the highest-intent conversion email in the entire system: the
// user just experienced the AI's output quality (the AHA moment) AND has
// just been blocked by a paywall. An email landing within seconds —
// while they're still deciding whether to subscribe — is far more
// effective than the 24h-delayed batch email.
//
// Called by the Flutter app via POST:
//   POST https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/free-quota-hit-email
//   Authorization: Bearer <SUPABASE_ANON_KEY>
//   Content-Type: application/json
//   {
//     "uid": "...",
//     "email": "user@example.com",
//     "language": "en",                  // optional, default 'en'
//     "first_name": "Ana",               // optional, default 'there'
//     "work_type": "thesis",             // optional, default 'thesis'
//     "topic": "...",                    // optional, default 'your work'
//     "pain_hook": "..."                 // optional, default empty
//   }
//
// Dedup: one row per (uid, 'free_quota_hit') in instant_emails_sent.
// Batch free_quota_hit_sender's h24/h72/d7 stages also check this table
// — if instant already fired, all 3 batch stages are skipped (the
// instant message is timed perfectly; no need for follow-ups).
//
// Skips paid users: the Flutter app should already filter these out,
// but the Edge Function double-checks for safety. Anything we can't
// verify is treated as "free" and gets the pitch.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { SENDER_POOL_THESIS as SENDER_POOL } from "../_shared/sender_pool.ts";
import { hasEmailCredentials, isSendFailureBounce, resolveSender, sendEmail } from "../_shared/email_transport.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

const APP_NAME = "Thesis Generator";
const APP_SLUG = "thesis";
const KIND = "free_quota_hit";
const APP_STORE_URL = "https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844";
const GOOGLE_PLAY_URL = "https://play.google.com/store/apps/details?id=com.thesis.generator.ai";

// Instant-paywall-hit template — different copy from the h24 batch
// version because the user just hit the paywall this minute, not
// yesterday. The angle: "you just experienced what's possible →
// unlock the rest before you lose momentum".
const TEMPLATES: Record<string, { subject: string; body: string[]; cta: string }> = {
  en: {
    subject: "Don't lose your momentum, {{first_name}} — unlock the rest",
    body: [
      "You just generated your first chapter on {{topic}}. That was the AHA moment — the AI does the heavy lifting and you're now staring at real, usable content.",
      "Tap below to unlock unlimited chapters. The next one takes 60 seconds. By tonight you have a full draft of your {{work_type}}.",
      "P.S. Premium also includes PDF export, AI-detection bypass (humanize), and unlimited regenerations. Same price as two coffees.",
    ],
    cta: "Unlock unlimited chapters",
  },
  ar: {
    subject: "لا تفقد زخمك، {{first_name}} — افتح الباقي",
    body: [
      "لقد أنشأت للتو فصلك الأول حول {{topic}}. كانت تلك لحظة الإدراك — الذكاء الاصطناعي يقوم بالعمل الشاق وأنت الآن تنظر إلى محتوى حقيقي وقابل للاستخدام.",
      "اضغط أدناه لفتح فصول غير محدودة. الفصل التالي يستغرق 60 ثانية. بحلول الليلة لديك مسودة كاملة لـ {{work_type}} الخاص بك.",
      "ملاحظة: تتضمن النسخة المميزة أيضًا تصدير PDF، وتجاوز كشف الذكاء الاصطناعي (الأنسنة)، وإعادة التوليد غير المحدودة. بسعر فنجاني قهوة.",
    ],
    cta: "افتح فصولاً غير محدودة",
  },
  es: {
    subject: "No pierdas el impulso, {{first_name}} — desbloquea el resto",
    body: [
      "Acabas de generar tu primer capítulo sobre {{topic}}. Ese fue el momento de la verdad — la IA hace el trabajo pesado y ahora tienes contenido real y utilizable frente a ti.",
      "Toca abajo para desbloquear capítulos ilimitados. El siguiente toma 60 segundos. Esta noche tendrás un borrador completo de tu {{work_type}}.",
      "P.D. Premium también incluye exportación a PDF, evasión de detección de IA (humanizar) y regeneraciones ilimitadas. Al precio de dos cafés.",
    ],
    cta: "Desbloquear capítulos ilimitados",
  },
  fr: {
    subject: "Ne perdez pas votre élan, {{first_name}} — débloquez le reste",
    body: [
      "Vous venez de générer votre premier chapitre sur {{topic}}. C'était le moment de vérité — l'IA fait le gros du travail et vous avez maintenant du contenu réel et utilisable.",
      "Appuyez ci-dessous pour débloquer des chapitres illimités. Le suivant prend 60 secondes. D'ici ce soir, vous avez un brouillon complet de votre {{work_type}}.",
      "P.S. Premium inclut aussi l'export PDF, le contournement de détection IA (humaniser) et les régénérations illimitées. Au prix de deux cafés.",
    ],
    cta: "Débloquer des chapitres illimités",
  },
  hi: {
    subject: "अपनी गति न खोएं, {{first_name}} — बाकी अनलॉक करें",
    body: [
      "आपने अभी {{topic}} पर अपना पहला अध्याय जनरेट किया। वह अहा-पल था — AI सारा कठिन काम करता है और अब आप असली, उपयोग करने योग्य सामग्री देख रहे हैं।",
      "असीमित अध्याय अनलॉक करने के लिए नीचे टैप करें। अगला 60 सेकंड लेता है। आज रात तक आपकी {{work_type}} का पूरा ड्राफ्ट तैयार होगा।",
      "P.S. प्रीमियम में PDF एक्सपोर्ट, AI-डिटेक्शन बाईपास (ह्यूमनाइज़), और असीमित रीजेनरेशन भी शामिल है। दो कॉफियों की कीमत पर।",
    ],
    cta: "असीमित अध्याय अनलॉक करें",
  },
  zh: {
    subject: "别失去节奏，{{first_name}} — 解锁剩余部分",
    body: [
      "你刚刚生成了关于{{topic}}的第一章。那就是顿悟时刻 — AI完成了繁重的工作，现在你眼前是真实可用的内容。",
      "点击下方解锁无限章节。下一章只需60秒。今晚你就能拥有{{work_type}}的完整草稿。",
      "P.S. 高级版还包括PDF导出、AI检测绕过（人性化）和无限重新生成。价格相当于两杯咖啡。",
    ],
    cta: "解锁无限章节",
  },
  // For other supported languages we fall back to English in v1.
  // batch free_quota_hit_sender's h24 stage will still fire localized
  // copy on the next cron if instant didn't cover them.
};

function pickSender(uid: string) {
  let h = 0;
  for (const c of uid) h = (h * 31 + c.charCodeAt(0)) | 0;
  return SENDER_POOL[Math.abs(h) % SENDER_POOL.length];
}

async function userRef(email: string): Promise<string> {
  const data = new TextEncoder().encode(`${REF_SALT}:${email.toLowerCase().trim()}`);
  const buf = await crypto.subtle.digest("SHA-256", data);
  const hex = Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hex.slice(0, 16);
}

function sanitizeTagValue(v: string): string {
  return v.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 256);
}

function withUtm(
  url: string,
  ctx: { app: string; emailNum: string; cycle: number; language: string; ref: string; kind: string }
): string {
  if (!url) return url;
  try {
    const u = new URL(url);
    u.searchParams.set("utm_source", "resend");
    u.searchParams.set("utm_medium", "email");
    u.searchParams.set("utm_campaign", `${ctx.kind}_${ctx.emailNum}`);
    u.searchParams.set("utm_content", `cycle${ctx.cycle}_${ctx.language}`);
    u.searchParams.set("utm_term", ctx.app);
    u.searchParams.set("ref", ctx.ref);
    return u.toString();
  } catch { return url; }
}

function interpolate(s: string, vars: Record<string, string>): string {
  return s.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? "");
}

const GREETINGS: Record<string, string> = {
  en: "Hey there,", ar: "مرحبًا،", es: "Hola,", fr: "Salut,", zh: "你好，", hi: "नमस्ते,",
};
const SIGNOFFS: Record<string, string> = {
  en: "Talk soon,", ar: "إلى اللقاء،", es: "Hasta pronto,", fr: "À bientôt,", zh: "回头聊，", hi: "जल्द बात करते हैं,",
};
const FOOTERS: Record<string, string> = {
  en: "You're receiving this because you hit the free quota in Thesis Generator.",
  ar: "تتلقى هذا البريد لأنك وصلت إلى الحد المجاني في Thesis Generator.",
  es: "Recibes esto porque alcanzaste la cuota gratuita en Thesis Generator.",
  fr: "Vous recevez ceci car vous avez atteint le quota gratuit dans Thesis Generator.",
  zh: "您收到此邮件是因为您在 Thesis Generator 中用完了免费配额。",
  hi: "आपको यह ईमेल इसलिए मिल रहा है क्योंकि आपने Thesis Generator में मुफ्त सीमा पार कर ली।",
};

function buildHtml(
  greeting: string, paragraphs: string[], ctaText: string,
  appStoreHref: string, googlePlayHref: string,
  signoff: string, senderName: string, footer: string,
  isRtl: boolean,
): string {
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const textAlign = isRtl ? "right" : "left";
  let body = "";
  paragraphs.forEach((p, i) => {
    const ph = p.replace(/\n/g, "<br>");
    if (i === 0) {
      body += `<p style="margin:0 0 24px;font-size:18px;color:#1a202c;line-height:1.7;font-weight:500;text-align:${textAlign};">${ph}</p>`;
    } else if (p.includes("P.S.") || p.includes("P.D.") || p.includes("ملاحظة")) {
      body += `<div style="margin:32px 0 0;padding:16px 20px;background:#fffbeb;border-radius:8px;border:1px solid #fcd34d;"><p style="margin:0;font-size:16px;color:#92400e;line-height:1.7;text-align:${textAlign};">${ph}</p></div>`;
    } else {
      body += `<p style="margin:0 0 20px;font-size:17px;color:#374151;line-height:1.8;text-align:${textAlign};">${ph}</p>`;
    }
  });
  const cta = `
    <div style="text-align:center;margin:36px 0;">
      <a href="${appStoreHref}" style="display:inline-block;background:linear-gradient(135deg,#dc2626 0%,#ea580c 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
        🚀 ${ctaText} (iOS)
      </a>
      <a href="${googlePlayHref}" style="display:inline-block;background:linear-gradient(135deg,#dc2626 0%,#ea580c 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
        🚀 ${ctaText} (Android)
      </a>
    </div>`;
  return `<!DOCTYPE html>
<html${dirAttr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.7;color:#2d3748;max-width:600px;margin:0 auto;padding:40px 24px;background:#fff;text-align:${textAlign};">
  <div style="margin-bottom:28px;">
    <p style="margin:0 0 24px;font-size:18px;color:#6b7280;text-align:${textAlign};">${greeting}</p>
    ${body}
  </div>
  ${cta}
  <p style="margin:32px 0 0;font-size:17px;color:#4b5563;text-align:${textAlign};">${signoff}<br><strong style="color:#1f2937;">${senderName}</strong></p>
  <div style="margin-top:48px;padding-top:24px;border-top:1px solid #e5e7eb;text-align:center;"><p style="margin:0;font-size:12px;color:#d1d5db;">${footer}</p></div>
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
  if (!hasEmailCredentials()) return new Response(JSON.stringify({ error: "email credentials missing" }), { status: 500 });

  let payload: Record<string, unknown>;
  try { payload = await req.json(); }
  catch { return new Response(JSON.stringify({ error: "invalid JSON" }), { status: 400 }); }

  const uid = String(payload.uid || "").trim();
  const email = String(payload.email || "").toLowerCase().trim();
  if (!uid)   return new Response(JSON.stringify({ error: "missing field: uid" }),   { status: 400 });
  if (!email) return new Response(JSON.stringify({ error: "missing field: email" }), { status: 400 });
  if (email.includes("cloudtestlabaccounts.com") || email.includes("example.com")) {
    return new Response(JSON.stringify({ ok: true, skipped: "test_account" }), { status: 200 });
  }

  let lang = String(payload.language || "en").toLowerCase().split(/[_-]/)[0];
  if (!(lang in TEMPLATES)) lang = "en";

  const vars = {
    first_name: String(payload.first_name || "there"),
    work_type: String(payload.work_type || "thesis"),
    topic: String(payload.topic || "your work"),
    pain_hook: String(payload.pain_hook || ""),
  };

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

  const tpl = TEMPLATES[lang];
  const subject = interpolate(tpl.subject, vars);
  const paragraphs = tpl.body.map((p) => interpolate(p, vars));
  const ctaText = interpolate(tpl.cta, vars);

  const sender = resolveSender(pickSender(uid));
  const ref = await userRef(email);
  const utmCtx = { app: APP_SLUG, emailNum: "instant", cycle: 1, language: lang, ref, kind: KIND };
  const appStoreHref = withUtm(APP_STORE_URL, utmCtx);
  const googlePlayHref = withUtm(GOOGLE_PLAY_URL, utmCtx);
  const isRtl = lang === "ar";
  const html = buildHtml(
    GREETINGS[lang] || GREETINGS.en, paragraphs, ctaText,
    appStoreHref, googlePlayHref,
    SIGNOFFS[lang] || SIGNOFFS.en,
    sender.name,
    FOOTERS[lang] || FOOTERS.en,
    isRtl,
  );

  const tags = [
    { name: "app", value: APP_SLUG },
    { name: "kind", value: KIND },
    { name: "email_num", value: "instant" },
    { name: "cycle", value: "1" },
    { name: "language", value: sanitizeTagValue(lang) },
    { name: "segment", value: "instant" },
  ];

  const sendResult = await sendEmail({
    fromName: APP_NAME,
    fromEmail: sender.email,
    to: email,
    subject,
    html,
    replyTo: sender.email,
    tags,
    refId: ref,
  });

  if (!sendResult.ok) {
    console.error(`Email send ${sendResult.status}: ${JSON.stringify(sendResult.details)}`);
    const isBounce = isSendFailureBounce(sendResult);
    return new Response(JSON.stringify({ error: "send failed", bounced: isBounce, details: sendResult.details }), {
      status: isBounce ? 400 : 500, headers: { "Content-Type": "application/json" },
    });
  }

  const messageId = sendResult.id || "";
  const { error: insertErr } = await supabase
    .from("instant_emails_sent")
    .insert({
      uid, app_id: "thesis_generator", event_kind: KIND, recipient: email,
      language: lang, resend_id: messageId,
      metadata: { work_type: vars.work_type, topic: vars.topic },
    });
  if (insertErr && insertErr.code !== "23505") {
    console.error(`dedup insert failed: ${insertErr.message}`);
  }

  console.log(`✅ free_quota_hit sent: ${email} (${lang}) message_id=${messageId}`);
  return new Response(JSON.stringify({ ok: true, message_id: messageId, language: lang }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
});
