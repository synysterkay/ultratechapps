// Supabase Edge Function: send-push
// Sends a single FCM push to one user, server-side, so SoulPlan needs no
// Firebase Blaze plan. The device receives via FCM (free); this function does
// the sending using a Firebase service account.
//
// Endpoint: POST https://<project>.supabase.co/functions/v1/send-push
// Headers:  Authorization: Bearer <SUPABASE_ANON_KEY>
//           Content-Type: application/json
// Body:     { toUserId, fromUserId?, title, body, type?, data? }
//
// Secret required (Supabase):
//   FIREBASE_SERVICE_ACCOUNT = the full service-account JSON (one line)
//
// The recipient's FCM token is read from Firestore users/{toUserId}.fcmToken.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SA_JSON = Deno.env.get("FIREBASE_SERVICE_ACCOUNT") || "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// ── Service account → Google OAuth access token (RS256 JWT grant) ──
let _cachedToken: { token: string; exp: number } | null = null;

function pemToDer(pem: string): Uint8Array {
  const b64 = pem
    .replace(/-----BEGIN PRIVATE KEY-----/, "")
    .replace(/-----END PRIVATE KEY-----/, "")
    .replace(/\s+/g, "");
  const bin = atob(b64);
  const der = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) der[i] = bin.charCodeAt(i);
  return der;
}

function b64url(input: string | Uint8Array): string {
  const bytes =
    typeof input === "string" ? new TextEncoder().encode(input) : input;
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function getAccessToken(sa: any): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  if (_cachedToken && _cachedToken.exp - 60 > now) return _cachedToken.token;

  const header = { alg: "RS256", typ: "JWT" };
  const claim = {
    iss: sa.client_email,
    scope: "https://www.googleapis.com/auth/cloud-platform",
    aud: "https://oauth2.googleapis.com/token",
    iat: now,
    exp: now + 3600,
  };
  const unsigned = `${b64url(JSON.stringify(header))}.${b64url(
    JSON.stringify(claim),
  )}`;

  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToDer(sa.private_key),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = new Uint8Array(
    await crypto.subtle.sign(
      "RSASSA-PKCS1-v1_5",
      key,
      new TextEncoder().encode(unsigned),
    ),
  );
  const jwt = `${unsigned}.${b64url(sig)}`;

  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion: jwt,
    }),
  });
  const json = await res.json();
  if (!res.ok) throw new Error(`token: ${JSON.stringify(json)}`);
  _cachedToken = { token: json.access_token, exp: now + 3600 };
  return json.access_token;
}

async function getRecipient(
  sa: any,
  accessToken: string,
  uid: string,
): Promise<{ token: string | null; language: string }> {
  const url = `https://firestore.googleapis.com/v1/projects/${sa.project_id}/databases/(default)/documents/users/${uid}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) return { token: null, language: "en" };
  const doc = await res.json();
  return {
    token: doc?.fields?.fcmToken?.stringValue ?? null,
    language: doc?.fields?.language?.stringValue ?? "en",
  };
}

// ── Localized push templates, keyed by [type][base-language] ──────────────
// {detail} / {time} are substituted from the request `data`. If a type/lang
// isn't covered, we fall back to the title/body the app passed.
const PUSH_I18N: Record<string, Record<string, { t: string; b: string }>> = {
  thinking_of_you: {
    en: { t: "Your partner is thinking of you 💛", b: "Tap to plan something together tonight." },
    es: { t: "Tu pareja está pensando en ti 💛", b: "Toca para planear algo juntos esta noche." },
    fr: { t: "Ton/ta partenaire pense à toi 💛", b: "Touche pour planifier votre soirée." },
    pt: { t: "Seu amor está pensando em você 💛", b: "Toque para planejar algo hoje à noite." },
    de: { t: "Dein Schatz denkt an dich 💛", b: "Tippe, um etwas für heute Abend zu planen." },
    it: { t: "Il tuo partner sta pensando a te 💛", b: "Tocca per organizzare la serata insieme." },
    pl: { t: "Twoja połówka o tobie myśli 💛", b: "Dotknij, by zaplanować wieczór razem." },
    tr: { t: "Sevgilin seni düşünüyor 💛", b: "Bu akşam için bir şeyler planlamak için dokun." },
    ar: { t: "شريكك يفكر فيك 💛", b: "انقر لتخطيط شيء معًا الليلة." },
    ru: { t: "Твоя половинка думает о тебе 💛", b: "Нажми, чтобы спланировать вечер вместе." },
    hi: { t: "आपका साथी आपके बारे में सोच रहा है 💛", b: "आज रात कुछ प्लान करने के लिए टैप करें।" },
    id: { t: "Pasanganmu sedang memikirkanmu 💛", b: "Ketuk untuk merencanakan sesuatu malam ini." },
    ja: { t: "パートナーがあなたを想っています 💛", b: "今夜の予定を立てるにはタップ。" },
    ko: { t: "당신의 연인이 당신을 생각하고 있어요 💛", b: "오늘 밤 함께할 계획을 세우려면 탭하세요." },
    zh: { t: "你的另一半正在想你 💛", b: "点击一起计划今晚。" },
  },
  time_confirmed: {
    en: { t: "✅ Date confirmed!", b: "Your date is set for {time} 💛" },
    es: { t: "✅ ¡Cita confirmada!", b: "Vuestra cita es el {time} 💛" },
    fr: { t: "✅ Rendez-vous confirmé !", b: "Votre rendez-vous est prévu le {time} 💛" },
    pt: { t: "✅ Encontro confirmado!", b: "Seu encontro está marcado para {time} 💛" },
    de: { t: "✅ Date bestätigt!", b: "Euer Date ist für {time} geplant 💛" },
    it: { t: "✅ Appuntamento confermato!", b: "Il vostro appuntamento è il {time} 💛" },
    pl: { t: "✅ Randka potwierdzona!", b: "Wasza randka jest zaplanowana na {time} 💛" },
    tr: { t: "✅ Buluşma onaylandı!", b: "Buluşmanız {time} için ayarlandı 💛" },
    ar: { t: "✅ تم تأكيد الموعد!", b: "موعدكما محدد في {time} 💛" },
    ru: { t: "✅ Свидание подтверждено!", b: "Ваше свидание назначено на {time} 💛" },
    hi: { t: "✅ डेट कन्फर्म!", b: "आपकी डेट {time} के लिए तय है 💛" },
    id: { t: "✅ Kencan dikonfirmasi!", b: "Kencan kalian dijadwalkan {time} 💛" },
    ja: { t: "✅ デートが確定！", b: "デートは {time} に決まりました 💛" },
    ko: { t: "✅ 데이트 확정!", b: "데이트가 {time}으로 잡혔어요 💛" },
    zh: { t: "✅ 约会已确认！", b: "你们的约会定在 {time} 💛" },
  },
  date_suggestion: {
    en: { t: "💌 A date idea from your partner", b: "{detail}" },
    es: { t: "💌 Una idea de cita de tu pareja", b: "{detail}" },
    fr: { t: "💌 Une idée de rendez-vous de ton/ta partenaire", b: "{detail}" },
    pt: { t: "💌 Uma ideia de encontro do seu amor", b: "{detail}" },
    de: { t: "💌 Eine Date-Idee von deinem Schatz", b: "{detail}" },
    it: { t: "💌 Un'idea per un appuntamento dal tuo partner", b: "{detail}" },
    pl: { t: "💌 Pomysł na randkę od Twojej połówki", b: "{detail}" },
    tr: { t: "💌 Sevgilinden bir buluşma fikri", b: "{detail}" },
    ar: { t: "💌 فكرة موعد من شريكك", b: "{detail}" },
    ru: { t: "💌 Идея свидания от твоей половинки", b: "{detail}" },
    hi: { t: "💌 आपके साथी से एक डेट आइडिया", b: "{detail}" },
    id: { t: "💌 Ide kencan dari pasanganmu", b: "{detail}" },
    ja: { t: "💌 パートナーからのデートの提案", b: "{detail}" },
    ko: { t: "💌 연인이 보낸 데이트 아이디어", b: "{detail}" },
    zh: { t: "💌 来自另一半的约会点子", b: "{detail}" },
  },
};

function localizePush(
  type: string,
  language: string,
  data: Record<string, string> | undefined,
  fallbackTitle: string,
  fallbackBody: string,
): { title: string; body: string } {
  const base = String(language || "en").split(/[-_]/)[0].toLowerCase();
  const tmpl = PUSH_I18N[type]?.[base];
  if (!tmpl) return { title: fallbackTitle, body: fallbackBody };
  const sub = (s: string) =>
    s.replace(/\{(\w+)\}/g, (_, k) => (data?.[k] ?? ""));
  return { title: sub(tmpl.t), body: sub(tmpl.b) };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    if (!SA_JSON) throw new Error("FIREBASE_SERVICE_ACCOUNT not set");
    const sa = JSON.parse(SA_JSON);
    const { toUserId, title, body, type, data } = await req.json();
    if (!toUserId || !title) {
      return new Response(JSON.stringify({ error: "missing toUserId/title" }), {
        status: 400,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    const accessToken = await getAccessToken(sa);
    const { token: fcmToken, language } = await getRecipient(
      sa,
      accessToken,
      toUserId,
    );
    if (!fcmToken) {
      // Recipient has no registered device — not an error, just nothing to do.
      return new Response(JSON.stringify({ ok: true, skipped: "no_token" }), {
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    // Localize to the RECIPIENT's chosen language (same tag set as the app /
    // Superwall). Falls back to the title/body the app passed.
    const loc = localizePush(
      String(type ?? "general"),
      language,
      data,
      title,
      body ?? "",
    );

    const message = {
      message: {
        token: fcmToken,
        notification: { title: loc.title, body: loc.body },
        data: {
          type: String(type ?? "general"),
          ...(data ?? {}),
        },
        apns: {
          payload: { aps: { sound: "default", badge: 1 } },
        },
        android: {
          priority: "high",
          notification: { sound: "default" },
        },
      },
    };

    const sendRes = await fetch(
      `https://fcm.googleapis.com/v1/projects/${sa.project_id}/messages:send`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(message),
      },
    );
    const sendJson = await sendRes.json();
    if (!sendRes.ok) {
      return new Response(JSON.stringify({ error: sendJson }), {
        status: 502,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({ ok: true, id: sendJson.name }), {
      headers: { ...cors, "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  }
});
