// Supabase Edge Function: soulplan-wrapped-ready-email
//
// Sends the "Your SoulPlan Wrapped is ready 🎁" email — the variable-reward
// trigger that pulls the couple back to the share moment (the in-app viral
// loop we built around the 9:16 share card).
//
// POST body:
//   {
//     email: string,           // recipient
//     language?: string,       // BCP-47 (e.g. "pt-BR"); falls back to "en"
//     firstName?: string,      // optional greeting personalisation
//     partnerName?: string,    // optional in-body personalisation
//     streakWeeks?: number,    // optional — surfaced when > 0
//     topVibe?: string,        // optional — surfaced when present (e.g. "cozy")
//   }
//
// Trigger source: a server-side cron / webhook decides when a couple's Wrapped
// is "fresh" (e.g. 30+ days since last send AND they have something to celebrate
// — see notification_strategy_service.dart for the equivalent in-app gate).
// That trigger POSTs to this function; this function only renders + sends.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const FUNCTION_AUTH_KEY = Deno.env.get("FUNCTION_AUTH_KEY") || "";

// Same verified Resend domains used by welcome-email (deliverability_monitor
// rotates these). Keep in sync if welcome-email's SENDER_POOL changes.
const SENDER_POOL = [
  { email: "alex@bestaiapps.site", name: "Alex" },
  { email: "jordan@aibettips.io", name: "Jordan" },
  { email: "sam@predictifyfootball.com", name: "Sam" },
  { email: "taylor@thesisgenerator.io", name: "Taylor" },
  { email: "morgan@passedai.io", name: "Morgan" },
  { email: "casey@academicsatire.com", name: "Casey" },
  { email: "riley@predictify.fun", name: "Riley" },
];

function pickSender() {
  return SENDER_POOL[Math.floor(Math.random() * SENDER_POOL.length)];
}

// ── BCP-47 → base language (matches LANG_NORMALIZE in check-new-users) ──
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
  let s = raw.toLowerCase().trim().replace(/-/g, "_");
  if (s in LANG_NORMALIZE) return LANG_NORMALIZE[s];
  const base = s.split("_")[0];
  return LANG_NORMALIZE[base] || "en";
}

// ── Templates — one entry per supported language ───────────────────────────
type Template = { subject: string; cta_text: string; body: string };

const TEMPLATES: Record<string, Template> = {
  en: {
    subject: "Your SoulPlan Wrapped is ready 🎁",
    cta_text: "See Your Wrapped",
    body: "Your last 3 months on SoulPlan are wrapped up — streak, top vibe, dates planned, memories saved. Open the app to see them, and share it as a beautiful card in one tap.",
  },
  es: {
    subject: "Tu SoulPlan Wrapped ya está listo 🎁",
    cta_text: "Ver tu Wrapped",
    body: "Tus últimos 3 meses en SoulPlan ya están listos: racha, vibe favorito, citas planeadas y recuerdos guardados. Abre la app para verlo — y compártelo como una tarjeta preciosa con un solo toque.",
  },
  fr: {
    subject: "Votre SoulPlan Wrapped est prêt 🎁",
    cta_text: "Voir votre Wrapped",
    body: "Vos 3 derniers mois sur SoulPlan sont prêts : streak, vibe préféré, dates planifiées et souvenirs sauvegardés. Ouvrez l'app pour le voir — et partagez-le comme une carte magnifique en un tap.",
  },
  pt: {
    subject: "Seu SoulPlan Wrapped está pronto 🎁",
    cta_text: "Ver seu Wrapped",
    body: "Seus últimos 3 meses no SoulPlan estão prontos: streak, vibe favorito, encontros planejados e memórias salvas. Abra o app para ver — e compartilhe como um cartão lindo com um toque.",
  },
  pp: {
    subject: "O teu SoulPlan Wrapped está pronto 🎁",
    cta_text: "Ver o teu Wrapped",
    body: "Os teus últimos 3 meses no SoulPlan estão prontos: streak, vibe favorito, encontros planeados e memórias guardadas. Abre a app para veres — e partilha como um cartão lindo com um toque.",
  },
  it: {
    subject: "Il tuo SoulPlan Wrapped è pronto 🎁",
    cta_text: "Vedi il tuo Wrapped",
    body: "Gli ultimi 3 mesi su SoulPlan sono pronti: streak, vibe preferito, appuntamenti pianificati e ricordi salvati. Apri l'app per vederlo — e condividilo come una bellissima cartolina con un tocco.",
  },
  de: {
    subject: "Dein SoulPlan Wrapped ist bereit 🎁",
    cta_text: "Wrapped ansehen",
    body: "Deine letzten 3 Monate auf SoulPlan sind bereit: Streak, Top-Vibe, geplante Dates und gespeicherte Erinnerungen. Öffne die App, um es zu sehen — und teile es als wunderschöne Karte mit einem Tap.",
  },
  nl: {
    subject: "Jouw SoulPlan Wrapped is klaar 🎁",
    cta_text: "Bekijk je Wrapped",
    body: "Je laatste 3 maanden op SoulPlan zijn klaar: streak, favoriete vibe, geplande dates en opgeslagen herinneringen. Open de app om het te zien — en deel het als een mooie kaart met één tik.",
  },
  pl: {
    subject: "Twój SoulPlan Wrapped jest gotowy 🎁",
    cta_text: "Zobacz swój Wrapped",
    body: "Twoje ostatnie 3 miesiące na SoulPlan są gotowe: streak, ulubiony vibe, zaplanowane randki i zapisane wspomnienia. Otwórz aplikację, aby zobaczyć — i podziel się tym jako pięknym obrazkiem jednym dotknięciem.",
  },
  tr: {
    subject: "SoulPlan Wrapped'in hazır 🎁",
    cta_text: "Wrapped'i Gör",
    body: "Son 3 ayın SoulPlan'da hazır: streak, en sevdiğin vibe, planlanmış randevular ve kaydedilmiş anılar. Görmek için uygulamayı aç — ve tek dokunuşla güzel bir kart olarak paylaş.",
  },
  id: {
    subject: "SoulPlan Wrapped-mu sudah siap 🎁",
    cta_text: "Lihat Wrapped-mu",
    body: "3 bulan terakhirmu di SoulPlan sudah siap: streak, vibe favorit, kencan terjadwal, dan kenangan tersimpan. Buka aplikasi untuk melihatnya — dan bagikan sebagai kartu indah dengan satu sentuhan.",
  },
  ar: {
    subject: "ملخص SoulPlan الخاص بك جاهز 🎁",
    cta_text: "شاهد ملخصك",
    body: "آخر 3 أشهر على SoulPlan جاهزة: السلسلة، الأجواء المفضلة، المواعيد المخططة، والذكريات المحفوظة. افتح التطبيق لرؤيتها — وشاركها كبطاقة جميلة بنقرة واحدة.",
  },
  ru: {
    subject: "Ваш SoulPlan Wrapped готов 🎁",
    cta_text: "Посмотреть Wrapped",
    body: "Ваши последние 3 месяца в SoulPlan готовы: серия, любимая атмосфера, запланированные свидания и сохранённые воспоминания. Откройте приложение, чтобы увидеть — и поделитесь красивой карточкой одним касанием.",
  },
  hi: {
    subject: "आपका SoulPlan Wrapped तैयार है 🎁",
    cta_text: "अपना Wrapped देखें",
    body: "SoulPlan पर आपके पिछले 3 महीने तैयार हैं: streak, पसंदीदा vibe, प्लान की हुई dates, सहेजी हुई यादें। इसे देखने के लिए ऐप खोलें — और एक टैप में सुंदर कार्ड के रूप में शेयर करें।",
  },
  ja: {
    subject: "SoulPlan Wrappedの準備ができました 🎁",
    cta_text: "Wrappedを見る",
    body: "SoulPlanでの過去3ヶ月がまとまりました：ストリーク、お気に入りのムード、計画したデート、保存した思い出。アプリを開いて確認 — そして美しいカードとしてワンタップでシェアしましょう。",
  },
  ko: {
    subject: "SoulPlan Wrapped가 준비되었어요 🎁",
    cta_text: "Wrapped 보기",
    body: "SoulPlan에서의 지난 3개월이 완성되었어요: 스트릭, 좋아하는 분위기, 계획한 데이트, 저장된 추억. 앱을 열어 확인하세요 — 그리고 아름다운 카드로 한 번에 공유하세요.",
  },
  zh: {
    subject: "你的 SoulPlan Wrapped 已就绪 🎁",
    cta_text: "查看你的 Wrapped",
    body: "你在 SoulPlan 上的过去 3 个月已就绪：连续天数、最爱氛围、计划的约会和保存的回忆。打开应用查看 — 并一键分享为一张精美卡片。",
  },
};

// ── Localised greetings (mirror welcome-email) ─────────────────────────────
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

// ── HTML render ────────────────────────────────────────────────────────────
function buildHtml(
  language: string,
  template: Template,
  senderName: string,
  firstName?: string,
  partnerName?: string,
  streakWeeks?: number,
  topVibe?: string,
): string {
  const isRtl = language === "ar";
  const dirAttr = isRtl ? ' dir="rtl"' : "";
  const textAlign = isRtl ? "right" : "left";
  const greeting = (GREETINGS[language] || GREETINGS.en)(firstName);

  // Optional in-body personalisation (partner name + a stat line if present).
  // Kept gentle — never fabricates a number; only surfaces what was passed in.
  const partnerLine = partnerName
    ? `<p style="margin:0 0 16px;font-size:16px;color:#374151;line-height:1.6;text-align:${textAlign};">You &amp; ${partnerName} 💛</p>`
    : "";
  const statBits: string[] = [];
  if (streakWeeks && streakWeeks > 0) statBits.push(`🔥 ${streakWeeks}-week streak`);
  if (topVibe) statBits.push(`🎭 Top vibe: ${topVibe}`);
  const statsLine = statBits.length
    ? `<p style="margin:0 0 20px;font-size:15px;color:#E91C40;font-weight:600;text-align:${textAlign};">${statBits.join(" · ")}</p>`
    : "";

  const ctaUrl = "https://apps.apple.com/app/id6702018988";

  return `<!DOCTYPE html><html lang="${language}"${dirAttr}><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>${template.subject}</title></head>
<body style="margin:0;padding:0;background:#FFF7F8;font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;color:#2E2E2E">
<div style="max-width:560px;margin:32px auto;background:#fff;padding:36px 28px;border-radius:18px;box-shadow:0 2px 12px rgba(0,0,0,0.04)">
  <div style="font-size:22px;font-weight:800;color:#E91C40;margin-bottom:18px">💛 SoulPlan</div>
  <p style="margin:0 0 18px;font-size:18px;color:#6b7280;text-align:${textAlign};">${greeting}</p>
  ${partnerLine}
  ${statsLine}
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

// ── Handler ────────────────────────────────────────────────────────────────
Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }
  // Simple shared-secret auth (matches welcome-email's pattern).
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
    streakWeeks?: number;
    topVibe?: string;
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
  const html = buildHtml(
    lang,
    template,
    sender.name,
    payload.firstName,
    payload.partnerName,
    payload.streakWeeks,
    payload.topVibe,
  );

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
        { name: "kind", value: "wrapped_ready" },
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
