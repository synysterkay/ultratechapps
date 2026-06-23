// Supabase Edge Function: soulplan-silence-nudge-email
//
// Sends the "Tonight's date is still waiting 💛" email — the external trigger
// that recovers couples who haven't opened the app in ~3 days.
//
// POST body:
//   {
//     email: string,           // recipient
//     language?: string,       // BCP-47 (e.g. "pt-BR"); falls back to "en"
//     firstName?: string,      // optional greeting personalisation
//     partnerName?: string,    // optional in-body personalisation
//   }
//
// Trigger source: a server-side cron (similar to scripts/app_retention_emailer.py)
// queries `last_date_created` / `lastDateConfirmedAt` for SoulPlan users, finds
// those silent ≥ 3 days, then POSTs to this function. Frequency cap: at most
// once per silence streak (handled by the cron + email_suppressions table).

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { SENDER_POOL_FULL as SENDER_POOL } from "../_shared/sender_pool.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const FUNCTION_AUTH_KEY = Deno.env.get("FUNCTION_AUTH_KEY") || "";

function pickSender() {
  return SENDER_POOL[Math.floor(Math.random() * SENDER_POOL.length)];
}

const LANG_NORMALIZE: Record<string, string> = {
  en: "en", en_us: "en",
  ar: "ar", arabic: "ar",
  es: "es", spanish: "es",
  fr: "fr", french: "fr",
  pt: "pt", pt_br: "pt", portuguese: "pt",
  pp: "pp", pt_pt: "pp",
  de: "de", german: "de",
  it: "it", italian: "it",
  pl: "pl", polish: "pl",
  tr: "tr", turkish: "tr",
  nl: "nl", dutch: "nl",
  id: "id", indonesian: "id",
  ru: "ru", russian: "ru",
  hi: "hi", hindi: "hi",
  ja: "ja", japanese: "ja",
  ko: "ko", korean: "ko",
  zh: "zh", zh_cn: "zh", zh_hans: "zh", zh_tw: "zh", zh_hant: "zh", chinese: "zh",
};

function normalizeLang(raw?: string): string {
  if (!raw) return "en";
  const s = raw.toLowerCase().trim().replace(/-/g, "_");
  if (s in LANG_NORMALIZE) return LANG_NORMALIZE[s];
  return LANG_NORMALIZE[s.split("_")[0]] || "en";
}

// ── Templates ──────────────────────────────────────────────────────────────
type Template = { subject: string; cta_text: string; body: string };

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "Tonight's date is still waiting 💛",
    cta_text: "Open Tonight's Date",
    body: "It's been a few days. Open SoulPlan, tap a mood, and a date is ready for you and your partner in 30 seconds. No planning, just one tap — that's the whole point.",
  },
  es: {
    subject: "Tu cita de esta noche sigue esperando 💛",
    cta_text: "Abrir Tonight's Date",
    body: "Han pasado unos días. Abre SoulPlan, toca un estado de ánimo y tendrás una cita lista para ti y tu pareja en 30 segundos. Sin planificar, solo un toque — esa es toda la idea.",
  },
  fr: {
    subject: "Votre date du soir vous attend toujours 💛",
    cta_text: "Ouvrir Tonight's Date",
    body: "Quelques jours sont passés. Ouvrez SoulPlan, tapez un mood, et une date est prête pour vous deux en 30 secondes. Pas de planification, juste un tap — c'est tout l'intérêt.",
  },
  pt: {
    subject: "Seu encontro desta noite ainda está esperando 💛",
    cta_text: "Abrir Tonight's Date",
    body: "Já passaram alguns dias. Abra o SoulPlan, toque em um clima, e um encontro fica pronto para você e seu parceiro em 30 segundos. Sem planejar, só um toque — essa é toda a ideia.",
  },
  pp: {
    subject: "O teu encontro desta noite ainda espera 💛",
    cta_text: "Abrir Tonight's Date",
    body: "Já passaram alguns dias. Abre o SoulPlan, toca num mood, e um encontro está pronto para ti e o teu parceiro em 30 segundos. Sem planeamento, só um toque — é tudo o que precisas.",
  },
  it: {
    subject: "Il tuo appuntamento di stasera ti aspetta ancora 💛",
    cta_text: "Apri Tonight's Date",
    body: "Sono passati alcuni giorni. Apri SoulPlan, tocca un mood, e un appuntamento è pronto per te e il tuo partner in 30 secondi. Niente da pianificare, solo un tocco — è tutto qui.",
  },
  de: {
    subject: "Dein Date für heute Abend wartet noch 💛",
    cta_text: "Tonight's Date öffnen",
    body: "Ein paar Tage sind vergangen. Öffne SoulPlan, tippe einen Mood an, und ein Date ist in 30 Sekunden für dich und deinen Partner bereit. Keine Planung, nur ein Tipp — das ist der ganze Punkt.",
  },
  nl: {
    subject: "Je date vanavond wacht nog steeds 💛",
    cta_text: "Tonight's Date openen",
    body: "Een paar dagen geleden. Open SoulPlan, tik een mood aan, en er staat een date klaar voor jou en je partner in 30 seconden. Geen planning, gewoon één tik — dat is het hele idee.",
  },
  pl: {
    subject: "Twoja dzisiejsza randka wciąż czeka 💛",
    cta_text: "Otwórz Tonight's Date",
    body: "Minęło kilka dni. Otwórz SoulPlan, dotknij nastroju, i randka jest gotowa dla Was w 30 sekund. Bez planowania, jedno dotknięcie — o to chodzi.",
  },
  tr: {
    subject: "Bu geceki randevun seni hâlâ bekliyor 💛",
    cta_text: "Tonight's Date'i Aç",
    body: "Birkaç gün geçti. SoulPlan'i aç, bir mood seç, ve sen ve partnerin için 30 saniyede bir randevu hazır. Planlama yok, sadece bir dokunuş — tüm mesele bu.",
  },
  id: {
    subject: "Kencan malam ini masih menunggu 💛",
    cta_text: "Buka Tonight's Date",
    body: "Sudah beberapa hari. Buka SoulPlan, sentuh sebuah mood, dan kencan siap untukmu dan pasanganmu dalam 30 detik. Tanpa perencanaan, hanya satu sentuhan — itulah intinya.",
  },
  ar: {
    subject: "موعد الليلة لا يزال بانتظارك 💛",
    cta_text: "افتح Tonight's Date",
    body: "مرت بضعة أيام. افتح SoulPlan، انقر على مزاج، وموعد جاهز لك ولشريكك في 30 ثانية. لا تخطيط، فقط نقرة واحدة — هذا هو الهدف الأساسي.",
  },
  ru: {
    subject: "Ваше свидание сегодня всё ещё ждёт 💛",
    cta_text: "Открыть Tonight's Date",
    body: "Прошло несколько дней. Откройте SoulPlan, выберите настроение, и свидание для вас двоих будет готово за 30 секунд. Без планирования, всего одно касание — в этом весь смысл.",
  },
  hi: {
    subject: "आज रात की डेट अभी भी इंतज़ार कर रही है 💛",
    cta_text: "Tonight's Date खोलें",
    body: "कुछ दिन बीत गए हैं। SoulPlan खोलें, एक mood पर tap करें, और 30 सेकंड में आपके और आपके partner के लिए डेट तैयार है। कोई plan नहीं, बस एक tap — यही पूरी बात है।",
  },
  ja: {
    subject: "今夜のデートはまだ待っています 💛",
    cta_text: "Tonight's Dateを開く",
    body: "数日が経ちました。SoulPlanを開いて、ムードをタップすれば、あなたとパートナーのデートが30秒で準備できます。計画は不要、ワンタップだけ — それが全てです。",
  },
  ko: {
    subject: "오늘 밤 데이트가 여전히 기다리고 있어요 💛",
    cta_text: "Tonight's Date 열기",
    body: "며칠이 지났네요. SoulPlan을 열고 분위기를 하나 탭하면, 30초 안에 두 분을 위한 데이트가 준비돼요. 계획은 필요 없어요, 그저 한 번의 탭 — 그게 전부예요.",
  },
  zh: {
    subject: "今晚的约会还在等你 💛",
    cta_text: "打开 Tonight's Date",
    body: "已经过去几天了。打开 SoulPlan，点击一个心情，30 秒就为你和伴侣准备好一场约会。无需计划，只需一击 — 这就是全部。",
  },
};

const GREETINGS: Record<string, (n?: string) => string> = {
  en: (n) => n ? `Hey ${n},` : "Hey there,",
  ar: (n) => n ? `مرحبًا ${n}،` : "مرحبًا،",
  es: (n) => n ? `Hola ${n},` : "Hola,",
  fr: (n) => n ? `Salut ${n},` : "Salut,",
  zh: (n) => n ? `你好 ${n}，` : "你好，",
  hi: (n) => n ? `नमस्ते ${n},` : "नमस्ते,",
  pt: (n) => n ? `Olá ${n},` : "Olá,",
  ru: (n) => n ? `Привет, ${n}!` : "Привет,",
  de: (n) => n ? `Hallo ${n},` : "Hallo,",
  tr: (n) => n ? `Merhaba ${n},` : "Merhaba,",
  it: (n) => n ? `Ciao ${n},` : "Ciao,",
  pp: (n) => n ? `Olá ${n},` : "Olá,",
  id: (n) => n ? `Halo ${n},` : "Halo,",
  nl: (n) => n ? `Hallo ${n},` : "Hallo,",
  pl: (n) => n ? `Cześć ${n},` : "Cześć,",
  ja: (n) => n ? `${n}さん、こんにちは、` : "こんにちは、",
  ko: (n) => n ? `안녕하세요 ${n}님,` : "안녕하세요,",
};

function buildHtml(
  language: string,
  template: Template,
  senderName: string,
  firstName?: string,
  partnerName?: string,
): string {
  const isRtl = language === "ar";
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const textAlign = isRtl ? "right" : "left";
  const greeting = (GREETINGS[language] || GREETINGS.en)(firstName);
  const partnerLine = partnerName
    ? `<p style="margin:0 0 16px;font-size:16px;color:#374151;line-height:1.6;text-align:${textAlign};">You &amp; ${partnerName} 💛</p>`
    : "";
  const ctaUrl = "https://apps.apple.com/app/id6702018988";

  return `<!DOCTYPE html><html lang="${language}"${dirAttr}><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${template.subject}</title></head>
<body style="margin:0;padding:0;background:#FFF7F8;font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;color:#2E2E2E">
<div style="max-width:560px;margin:32px auto;background:#fff;padding:36px 28px;border-radius:18px;box-shadow:0 2px 12px rgba(0,0,0,0.04)">
  <div style="font-size:22px;font-weight:800;color:#E91C40;margin-bottom:18px">💛 SoulPlan</div>
  <p style="margin:0 0 18px;font-size:18px;color:#6b7280;text-align:${textAlign};">${greeting}</p>
  ${partnerLine}
  <p style="margin:0 0 28px;font-size:17px;color:#1a202c;line-height:1.7;font-weight:500;text-align:${textAlign};">${template.body}</p>
  <div style="text-align:center;margin:8px 0 24px">
    <a href="${ctaUrl}" style="display:inline-block;background:#E91C40;color:#fff;text-decoration:none;padding:14px 28px;border-radius:999px;font-weight:700;font-size:16px">${template.cta_text}</a>
  </div>
  <p style="margin:24px 0 4px;font-size:15px;color:#374151;text-align:${textAlign};">— ${senderName}</p>
  <div style="margin-top:28px;padding-top:18px;border-top:1px solid #FAD2DC;font-size:12px;color:#9E9E9E;text-align:center">
    SoulPlan · <a href="https://soulplan.app" style="color:#9E9E9E">soulplan.app</a>
    · <a href="%mailing_list_unsubscribe_url%" style="color:#9E9E9E">Unsubscribe</a>
  </div>
</div></body></html>`;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }
  const auth = req.headers.get("Authorization") || "";
  if (FUNCTION_AUTH_KEY && auth !== `Bearer ${FUNCTION_AUTH_KEY}`) {
    return new Response("Unauthorized", { status: 401 });
  }
  if (!RESEND_API_KEY) {
    return new Response(
      JSON.stringify({ error: "RESEND_API_KEY not configured" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  let payload: {
    email?: string;
    language?: string;
    firstName?: string;
    partnerName?: string;
  };
  try {
    payload = await req.json();
  } catch {
    return new Response(
      JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }
  if (!payload.email) {
    return new Response(
      JSON.stringify({ error: "email required" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const lang = normalizeLang(payload.language);
  const template = TEMPLATES[lang] || TEMPLATES.en;
  const sender = pickSender();
  const html = buildHtml(lang, template, sender.name, payload.firstName, payload.partnerName);

  const resendRes = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: `${sender.name} <${sender.email}>`,
      to: [payload.email],
      subject: template.subject,
      html,
      tags: [
        { name: "app", value: "soulplan" },
        { name: "kind", value: "silence_nudge" },
        { name: "language", value: lang },
      ],
    }),
  });

  const resendData = await resendRes.json().catch(() => ({}));
  if (!resendRes.ok) {
    return new Response(
      JSON.stringify({ error: "Resend failed", status: resendRes.status, data: resendData }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }
  return new Response(
    JSON.stringify({ ok: true, language: lang, id: resendData.id }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
});
