// Supabase Edge Function: thesis-complete-email
// Fires instantly when a Thesis Generator user marks a thesis as completed.
//
// Called by the Flutter app via POST after writing theses.{id}.status = 'completed':
//   POST https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/thesis-complete-email
//   Authorization: Bearer <SUPABASE_ANON_KEY>
//   Content-Type: application/json
//   {
//     "uid": "...",
//     "email": "user@example.com",
//     "language": "en",                // optional, defaults to 'en'
//     "first_name": "Ana",             // optional, defaults to 'there'
//     "work_type": "thesis",           // optional, defaults to 'thesis'
//     "topic": "...",                  // optional, defaults to 'your work'
//     "thesis_id": "..."               // for metadata only
//   }
//
// Dedup: one email per (uid, 'thesis_complete') lifetime via the
// public.instant_emails_sent Supabase table (unique constraint on
// uid+event_kind). The 23 candidates currently queued by the batch
// first_thesis_complete_sender also check this table before sending so
// instant-path users don't get a second email on the next cron run.
//
// Response:
//   200 { ok: true, message_id: "..." }          on send
//   200 { ok: true, duplicate: true }            if already sent
//   400 { error: "missing field: email" }        on bad input
//   500 { error: "send failed", details: ... }   on Resend / DB error

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const REF_SALT = Deno.env.get("EMAIL_REF_SALT") || "marketing-tool-v1";

const APP_NAME = "Thesis Generator";
const APP_SLUG = "thesis";
const KIND = "thesis_complete";
const APP_STORE_URL = "https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844";
const GOOGLE_PLAY_URL = "https://play.google.com/store/apps/details?id=com.thesis.generator.ai";

const SENDER_POOL = [
  { email: "hello@thesisgenerator.io", name: "Morgan" },
  { email: "hello@passedai.io",        name: "Taylor" },
  { email: "hello@academicsatire.com", name: "Riley" },
];

function pickSender(uid: string) {
  // Hash-stable: same user → same sender on every send.
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
  return s.replace(/\{\{(\w+)\}\}/g, (_m, k) => vars[k] ?? `{{${k}}}`);
}

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
      <a href="${appStoreHref}" style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
        📱 ${ctaText} (iOS)
      </a>
      <a href="${googlePlayHref}" style="display:inline-block;background:linear-gradient(135deg,#34d399 0%,#10b981 100%);color:#fff;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;margin:0 6px;">
        🤖 ${ctaText} (Android)
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

const GREETINGS: Record<string, string> = {
  en: "Hey there,", ar: "مرحبًا،", es: "Hola,", fr: "Salut,", zh: "你好，",
  hi: "नमस्ते,", pt: "Olá,", de: "Hallo,", tr: "Merhaba,", it: "Ciao,",
  id: "Halo,", nl: "Hallo,", pl: "Cześć,", ja: "こんにちは、", ko: "안녕하세요,",
  ru: "Привет,", ro: "Salut,", sv: "Hej,", vi: "Xin chào,", th: "สวัสดี,",
};
const SIGNOFFS: Record<string, string> = {
  en: "Talk soon,", ar: "إلى اللقاء،", es: "Hasta pronto,", fr: "À bientôt,", zh: "回头聊，",
  hi: "जल्द बात करते हैं,", pt: "Até logo,", de: "Bis bald,", tr: "Görüşürüz,", it: "A presto,",
  id: "Sampai jumpa,", nl: "Tot snel,", pl: "Do zobaczenia,", ja: "またね、", ko: "곧 이야기해요,",
  ru: "До скорого,", ro: "Pe curând,", sv: "Vi hörs,", vi: "Hẹn gặp lại,", th: "แล้วเจอกัน,",
};
const FOOTERS: Record<string, string> = {
  en: "You're receiving this because you completed a thesis in Thesis Generator.",
  ar: "تتلقى هذا البريد لأنك أكملت أطروحة في Thesis Generator.",
  es: "Recibes esto porque completaste una tesis en Thesis Generator.",
  fr: "Vous recevez ceci car vous avez terminé une thèse dans Thesis Generator.",
  zh: "您收到此邮件是因为您在 Thesis Generator 中完成了一篇论文。",
  hi: "आपको यह ईमेल इसलिए मिल रहा है क्योंकि आपने Thesis Generator में एक थीसिस पूरी की।",
  pt: "Você está recebendo isso porque concluiu uma tese no Thesis Generator.",
  de: "Du erhältst diese E-Mail, weil du in Thesis Generator eine Arbeit fertiggestellt hast.",
  tr: "Bu e-postayı Thesis Generator'da bir tez tamamladığınız için alıyorsunuz.",
  it: "Ricevi questa email perché hai completato una tesi in Thesis Generator.",
  id: "Anda menerima email ini karena menyelesaikan tesis di Thesis Generator.",
  nl: "Je ontvangt dit bericht omdat je een thesis hebt voltooid in Thesis Generator.",
  pl: "Otrzymujesz tę wiadomość, ponieważ ukończyłeś pracę w Thesis Generator.",
  ja: "Thesis Generatorで論文を完成させたため、このメールをお送りしています。",
  ko: "Thesis Generator에서 논문을 완료하셨기 때문에 이 이메일을 보내드립니다.",
  ru: "Вы получили это письмо, потому что завершили работу в Thesis Generator.",
  ro: "Primești acest mesaj pentru că ai finalizat o lucrare în Thesis Generator.",
  sv: "Du får detta för att du slutförde en uppsats i Thesis Generator.",
  vi: "Bạn nhận được email này vì đã hoàn thành luận văn trong Thesis Generator.",
  th: "คุณได้รับอีเมลนี้เพราะคุณทำวิทยานิพนธ์เสร็จใน Thesis Generator",
};
const TEMPLATES = {
  "ar": {
    "subject": "🎓 لقد فعلتها، {{first_name}} — قم بتصدير {{work_type}} الخاص بك",
    "body": [
      "{{first_name}}، لقد اكتمل {{work_type}} الخاص بك حول {{topic}}. هذا إنجاز حقيقي.",
      "الآن الجزء المهم حقًا: قم بتصديره كملف PDF وسلّمه. اضغط أدناه لفتح شاشة التصدير.",
      "ملاحظة: احفظ الملف في مكان خارج التطبيق أيضًا — مستقبلك سيشكرك."
    ],
    "cta": "تصدير ملف PDF الخاص بي"
  },
  "de": {
    "subject": "🎓 Du hast es geschafft, {{first_name}} — exportiere deine {{work_type}}",
    "body": [
      "{{first_name}}, deine {{work_type}} über {{topic}} ist fertig. Das ist eine echte Leistung.",
      "Jetzt kommt der Teil, der wirklich zählt: Exportiere sie als PDF und reiche sie ein. Tippe unten, um den Export-Bildschirm zu öffnen.",
      "P.S. Speichere die Datei auch außerhalb der App ab — das zukünftige Ich wird es dir danken."
    ],
    "cta": "Mein PDF exportieren"
  },
  "es": {
    "subject": "🎓 ¡Lo lograste, {{first_name}}! Exporta tu {{work_type}}",
    "body": [
      "{{first_name}}, tu {{work_type}} sobre {{topic}} está completa. Eso es un verdadero logro.",
      "Ahora la parte que realmente cuenta: expórtalo como PDF y entrégalo. Toca abajo para abrir la pantalla de exportación.",
      "P.D. Guarda el archivo también fuera de la aplicación — tu yo del futuro te lo agradecerá."
    ],
    "cta": "Exportar mi PDF"
  },
  "fr": {
    "subject": "🎓 Vous l'avez fait, {{first_name}} — exportez votre {{work_type}}",
    "body": [
      "{{first_name}}, votre {{work_type}} sur {{topic}} est terminé. C'est un véritable accomplissement.",
      "Maintenant, la partie qui compte vraiment : exportez-le en PDF et remettez-le. Appuyez ci-dessous pour ouvrir l'écran d'exportation.",
      "P.S. Enregistrez le fichier ailleurs que dans l'application aussi — votre futur vous remerciera."
    ],
    "cta": "Exporter mon PDF"
  },
  "hi": {
    "subject": "🎓 आपने कर दिखाया, {{first_name}} — अपना {{work_type}} एक्सपोर्ट करें",
    "body": [
      "{{first_name}}, {{topic}} पर आपका {{work_type}} पूरा हो गया है। यह वास्तव में एक उपलब्धि है।",
      "अब वह हिस्सा जो वास्तव में मायने रखता है: इसे PDF के रूप में एक्सपोर्ट करें और जमा करें। नीचे टैप करके एक्सपोर्ट स्क्रीन खोलें।",
      "P.S. फ़ाइल को ऐप के बाहर भी सेव कर लें — भविष्य में आप खुद को धन्यवाद देंगे।"
    ],
    "cta": "मेरा PDF एक्सपोर्ट करें"
  },
  "id": {
    "subject": "🎓 Kamu berhasil, {{first_name}} — ekspor {{work_type}} kamu",
    "body": [
      "{{first_name}}, {{work_type}} kamu tentang {{topic}} sudah selesai. Itu pencapaian yang nyata.",
      "Sekarang bagian yang benar-benar penting: ekspor sebagai PDF dan serahkan. Ketuk di bawah untuk membuka layar ekspor.",
      "P.S. Simpan file di luar aplikasi juga — dirimu di masa depan akan berterima kasih."
    ],
    "cta": "Ekspor PDF saya"
  },
  "it": {
    "subject": "🎓 Ce l'hai fatta, {{first_name}} — esporta il tuo {{work_type}}",
    "body": [
      "{{first_name}}, il tuo {{work_type}} su {{topic}} è completo. È un vero traguardo.",
      "Ora la parte che conta davvero: esportalo come PDF e consegnalo. Tocca qui sotto per aprire la schermata di esportazione.",
      "P.S. Salva il file anche fuori dall'app — il te del futuro ti ringrazierà."
    ],
    "cta": "Esporta il mio PDF"
  },
  "ja": {
    "subject": "🎓 やりましたね、{{first_name}}さん — {{work_type}}をエクスポートしましょう",
    "body": [
      "{{first_name}}さん、{{topic}}に関する{{work_type}}が完成しました。本当に素晴らしい成果です。",
      "ここからが本番です：PDFとしてエクスポートして提出しましょう。下のボタンをタップしてエクスポート画面を開いてください。",
      "P.S. アプリ外にもファイルを保存しておくことをおすすめします — 将来の自分が感謝しますよ。"
    ],
    "cta": "PDFをエクスポート"
  },
  "ko": {
    "subject": "🎓 해냈어요, {{first_name}}님 — {{work_type}}를 내보내세요",
    "body": [
      "{{first_name}}님, {{topic}}에 관한 {{work_type}}가 완료되었습니다. 정말 대단한 성과예요.",
      "이제 실제로 중요한 단계입니다: PDF로 내보내서 제출하세요. 아래를 탭하여 내보내기 화면을 여세요.",
      "P.S. 앱 외부에도 파일을 저장해 두세요 — 미래의 당신이 고마워할 거예요."
    ],
    "cta": "PDF 내보내기"
  },
  "nl": {
    "subject": "🎓 Je hebt het gedaan, {{first_name}} — exporteer je {{work_type}}",
    "body": [
      "{{first_name}}, je {{work_type}} over {{topic}} is voltooid. Dat is een echte prestatie.",
      "Nu het deel dat er echt toe doet: exporteer het als PDF en dien het in. Tik hieronder om het exportschema te openen.",
      "P.S. Bewaar het bestand ook ergens buiten de app — de toekomstige jij zal je dankbaar zijn."
    ],
    "cta": "Exporteer mijn PDF"
  },
  "pl": {
    "subject": "🎓 Udało Ci się, {{first_name}} — wyeksportuj swoją {{work_type}}",
    "body": [
      "{{first_name}}, Twoja {{work_type}} na temat {{topic}} jest gotowa. To prawdziwe osiągnięcie.",
      "Teraz część, która się naprawdę liczy: wyeksportuj ją jako PDF i oddaj. Kliknij poniżej, aby otworzyć ekran eksportu.",
      "PS. Zapisz plik również poza aplikacją — przyszły Ty Ci podziękuje."
    ],
    "cta": "Eksportuj mój PDF"
  },
  "pt": {
    "subject": "🎓 Você conseguiu, {{first_name}} — exporte seu {{work_type}}",
    "body": [
      "{{first_name}}, seu {{work_type}} sobre {{topic}} está completo. Isso é uma verdadeira conquista.",
      "Agora a parte que realmente importa: exporte como PDF e entregue. Toque abaixo para abrir a tela de exportação.",
      "P.S. Salve o arquivo também fora do aplicativo — seu eu do futuro agradecerá."
    ],
    "cta": "Exportar meu PDF"
  },
  "ro": {
    "subject": "🎓 Ai reușit, {{first_name}} — exportă-ți {{work_type}}",
    "body": [
      "{{first_name}}, {{work_type}} tău pe tema {{topic}} este complet. Este o adevărată realizare.",
      "Acum partea care contează cu adevărat: exportă-l ca PDF și predă-l. Atinge mai jos pentru a deschide ecranul de export.",
      "P.S. Salvează fișierul și în afara aplicației — viitorul tău îți va mulțumi."
    ],
    "cta": "Exportă PDF-ul meu"
  },
  "ru": {
    "subject": "🎓 {{first_name}}, вы сделали это — экспортируйте свою {{work_type}}",
    "body": [
      "{{first_name}}, ваша {{work_type}} на тему {{topic}} готова. Это настоящее достижение.",
      "Теперь самое важное: экспортируйте её в PDF и сдайте. Нажмите ниже, чтобы открыть экран экспорта.",
      "P.S. Сохраните файл и за пределами приложения — будущий вы скажет спасибо."
    ],
    "cta": "Экспортировать мой PDF"
  },
  "sv": {
    "subject": "🎓 Du klarade det, {{first_name}} — exportera din {{work_type}}",
    "body": [
      "{{first_name}}, din {{work_type}} om {{topic}} är klar. Det är en riktig prestation.",
      "Nu kommer delen som verkligen räknas: exportera den som PDF och lämna in den. Tryck nedan för att öppna exportskärmen.",
      "P.S. Spara filen även utanför appen — framtida du kommer att tacka dig."
    ],
    "cta": "Exportera min PDF"
  },
  "th": {
    "subject": "🎓 {{first_name}} คุณทำสำเร็จแล้ว — ส่งออก {{work_type}} ของคุณ",
    "body": [
      "{{first_name}} {{work_type}} ของคุณในหัวข้อ {{topic}} เสร็จสมบูรณ์แล้ว นั่นคือความสำเร็จที่ยิ่งใหญ่",
      "ตอนนี้ถึงส่วนที่สำคัญจริงๆ: ส่งออกเป็น PDF และส่งมอบ แตะด้านล่างเพื่อเปิดหน้าจอส่งออก",
      "ป.ล. บันทึกไฟล์ไว้ที่อื่นนอกแอปด้วย — อนาคตของคุณจะขอบคุณ"
    ],
    "cta": "ส่งออก PDF ของฉัน"
  },
  "tr": {
    "subject": "🎓 Başardın, {{first_name}} — {{work_type}}'nı dışa aktar",
    "body": [
      "{{first_name}}, {{topic}} konulu {{work_type}}'n tamamlandı. Bu gerçek bir başarı.",
      "Şimdi asıl önemli kısım: PDF olarak dışa aktar ve teslim et. Aşağıya dokunarak dışa aktarma ekranını aç.",
      "Not: Dosyayı uygulama dışında da bir yere kaydet — gelecekteki sana teşekkür edecek."
    ],
    "cta": "PDF'imi dışa aktar"
  },
  "vi": {
    "subject": "🎓 Bạn đã làm được, {{first_name}} — hãy xuất {{work_type}} của bạn",
    "body": [
      "{{first_name}}, {{work_type}} của bạn về chủ đề {{topic}} đã hoàn thành. Đó là một thành tích thực sự.",
      "Bây giờ là phần thực sự quan trọng: xuất nó dưới dạng PDF và nộp. Nhấn vào bên dưới để mở màn hình xuất.",
      "P.S. Hãy lưu tệp ở đâu đó bên ngoài ứng dụng nữa — bạn trong tương lai sẽ cảm ơn bạn."
    ],
    "cta": "Xuất PDF của tôi"
  },
  "zh": {
    "subject": "🎓 你做到了，{{first_name}} — 导出你的{{work_type}}",
    "body": [
      "{{first_name}}，你关于{{topic}}的{{work_type}}已经完成。这真是一项了不起的成就。",
      "现在到了真正关键的部分：将其导出为PDF并提交。点击下方打开导出界面。",
      "P.S. 也请将文件保存在应用之外的地方——未来的你会感谢自己的。"
    ],
    "cta": "导出我的PDF"
  },
  "en": {
    "subject": "🎓 You did it, {{first_name}} — export your {{work_type}}",
    "body": [
      "{{first_name}}, your {{work_type}} on {{topic}} is complete. That's a real accomplishment.",
      "Now the part that actually counts: export it as a PDF and turn it in. Tap below to open the export screen.",
      "P.S. Save the file somewhere outside the app too — future you will thank you."
    ],
    "cta": "Export my PDF"
  }
}
;

function loadTemplate(lang: string) {
  return (TEMPLATES as any)[lang] || TEMPLATES.en;
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
  };

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  // Dedup check — has this user already received this kind?
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

  const tpl = loadTemplate(lang);
  const subject = interpolate(tpl.subject, vars);
  const paragraphs = (tpl.body as string[]).map((p) => interpolate(p, vars));
  const ctaText = tpl.cta;

  const sender = pickSender(uid);
  const ref = await userRef(email);
  const utmCtx = { app: APP_SLUG, emailNum: "instant", cycle: 1, language: lang, ref, kind: KIND };
  const appStoreHref = withUtm(APP_STORE_URL, utmCtx);
  const googlePlayHref = withUtm(GOOGLE_PLAY_URL, utmCtx);
  const isRtl = lang === "ar";
  const greeting = GREETINGS[lang] || GREETINGS.en;
  const signoff  = SIGNOFFS[lang]  || SIGNOFFS.en;
  const footer   = FOOTERS[lang]   || FOOTERS.en;
  const html = buildHtml(greeting, paragraphs, ctaText, appStoreHref, googlePlayHref, signoff, sender.name, footer, isRtl);

  const tags = [
    { name: "app", value: APP_SLUG },
    { name: "kind", value: KIND },
    { name: "email_num", value: "instant" },
    { name: "cycle", value: "1" },
    { name: "language", value: sanitizeTagValue(lang) },
    { name: "segment", value: "instant" },
  ];

  const resendRes = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: `${APP_NAME} <${sender.email}>`,
      to: [email],
      subject,
      html,
      reply_to: sender.email,
      tags,
      headers: { "X-Entity-Ref-ID": ref },
    }),
  });

  let resendData: Record<string, unknown>;
  try { resendData = await resendRes.json(); }
  catch { resendData = { raw: await resendRes.text() }; }

  if (!resendRes.ok) {
    console.error(`Resend ${resendRes.status}: ${JSON.stringify(resendData)}`);
    const errStr = JSON.stringify(resendData).toLowerCase();
    const isBounce = (resendRes.status === 400 || resendRes.status === 422) &&
      ["not found","does not exist","invalid","rejected","bounce","undeliverable","mailbox","unknown user"].some((b) => errStr.includes(b));
    return new Response(JSON.stringify({ error: "send failed", bounced: isBounce, details: resendData }), {
      status: isBounce ? 400 : 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const messageId = String((resendData as any).id || "");
  const { error: insertErr } = await supabase
    .from("instant_emails_sent")
    .insert({
      uid, app_id: "thesis_generator", event_kind: KIND, recipient: email,
      language: lang, resend_id: messageId,
      metadata: { thesis_id: payload.thesis_id || null, work_type: vars.work_type, topic: vars.topic },
    });
  if (insertErr && insertErr.code !== "23505") {
    console.error(`dedup insert failed: ${insertErr.message}`);
  }

  console.log(`✅ thesis_complete sent: ${email} (${lang}) message_id=${messageId}`);
  return new Response(JSON.stringify({ ok: true, message_id: messageId, language: lang }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
