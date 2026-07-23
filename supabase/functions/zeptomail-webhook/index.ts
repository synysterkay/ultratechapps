// Supabase Edge Function: zeptomail-webhook
// Receives ZeptoMail bounce/open/click webhooks and writes email_events +
// email_suppressions (hard bounces only) so bad addresses are skipped everywhere.
//
// Setup (ZeptoMail dashboard → each verified domain → Webhooks):
//   thesisgenerator.io + predictifyfootball.com
//   URL:   https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/zeptomail-webhook
//   Events: Hard bounced (required)
//   Agent → Webhooks → Authentication Key (top right) → same as ZEPTOMAIL_WEBHOOK_AUTH_KEY
//   Verify/Send Test uses POST without auth — non-hard-bounce events return 200.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { recordHardBounce } from "../_shared/email_suppressions.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const WEBHOOK_AUTH_KEY = Deno.env.get("ZEPTOMAIL_WEBHOOK_AUTH_KEY") || "";

const KNOWN_APP_SLUGS = new Set([
  "predictify",
  "predictify_nba",
  "horse_racing",
  "thesis_generator",
  "thesis",
]);

function parsePayload(rawBody: string): Record<string, unknown> {
  const trimmed = rawBody.trim();
  if (!trimmed) return {};

  if (trimmed.startsWith("{")) {
    return JSON.parse(trimmed);
  }

  const params = new URLSearchParams(trimmed);
  const data = params.get("data") || params.get("payload");
  if (data) {
    return JSON.parse(decodeURIComponent(data));
  }

  const eq = trimmed.indexOf("=");
  if (eq > 0) {
    const value = decodeURIComponent(trimmed.slice(eq + 1));
    return JSON.parse(value);
  }

  return JSON.parse(trimmed);
}

function authKeyFromPayload(payload: Record<string, unknown>): string {
  for (const key of ["authentication_key", "auth_key", "auth", "webhook_auth_key"]) {
    const value = payload[key];
    if (typeof value === "string" && value) return value;
  }
  return "";
}

function eventNameStr(payload: Record<string, unknown>): string {
  const raw = payload.event_name ?? payload.event ?? "";
  if (Array.isArray(raw)) return raw.join(",").toLowerCase();
  return String(raw).toLowerCase();
}

function firstEventMessage(payload: Record<string, unknown>): Record<string, unknown> | undefined {
  const raw = payload.event_message;
  if (Array.isArray(raw)) {
    const first = raw[0];
    return first && typeof first === "object" ? first as Record<string, unknown> : undefined;
  }
  if (raw && typeof raw === "object") return raw as Record<string, unknown>;
  return undefined;
}

function isHardBounce(payload: Record<string, unknown>): boolean {
  const eventName = eventNameStr(payload);
  const eventMessage = firstEventMessage(payload);
  const objectName = String(
    (payload.event_data as Record<string, unknown> | undefined)?.object ||
      eventMessage?.object ||
      "",
  ).toLowerCase();

  return eventName.includes("hard") ||
    objectName.includes("hardbounce") ||
    objectName === "hardbounce";
}

function webhookAuthed(
  req: Request,
  payload: Record<string, unknown>,
  rawBody: string,
): Promise<boolean> {
  if (!WEBHOOK_AUTH_KEY) return Promise.resolve(true);

  const headerAuth = req.headers.get("x-zeptomail-auth") ||
    req.headers.get("x-authentication-key") || "";
  if (headerAuth === WEBHOOK_AUTH_KEY) return Promise.resolve(true);

  const bodyAuth = authKeyFromPayload(payload);
  if (bodyAuth === WEBHOOK_AUTH_KEY) return Promise.resolve(true);

  const producerSignature = req.headers.get("producer-signature");
  if (producerSignature) {
    return verifyProducerSignature(producerSignature, rawBody, WEBHOOK_AUTH_KEY);
  }

  return Promise.resolve(false);
}

async function verifyProducerSignature(
  producerSignature: string,
  rawBody: string,
  secretKey: string,
): Promise<boolean> {
  try {
    const decoded = decodeURIComponent(producerSignature);
    const parts: Record<string, string> = {};
    for (const segment of decoded.split(";")) {
      const eq = segment.indexOf("=");
      if (eq <= 0) continue;
      parts[segment.slice(0, eq).trim()] = segment.slice(eq + 1);
    }
    const algorithm = parts["s-algorithm"] || "HmacSHA256";
    if (algorithm !== "HmacSHA256") return false;

    const signatureReceived = parts.s;
    if (!signatureReceived) return false;

    // ZeptoMail signs the URL-decoded form value after the first '=' in the body.
    let dataValue = rawBody;
    const formEq = rawBody.indexOf("=");
    if (formEq > 0 && !rawBody.trim().startsWith("{")) {
      dataValue = decodeURIComponent(rawBody.slice(formEq + 1));
    }

    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secretKey),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(dataValue));
    const constructed = btoa(String.fromCharCode(...new Uint8Array(sig)));

    const a = Uint8Array.from(atob(signatureReceived), (c) => c.charCodeAt(0));
    const b = Uint8Array.from(atob(constructed), (c) => c.charCodeAt(0));
    if (a.length !== b.length) return false;
    let diff = 0;
    for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
    return diff === 0;
  } catch {
    return false;
  }
}

function extractRecipient(payload: Record<string, unknown>): string {
  const eventMessage = firstEventMessage(payload);
  const emailInfo = eventMessage?.email_info as Record<string, unknown> | undefined;

  const toField = emailInfo?.to;
  if (Array.isArray(toField)) {
    for (const entry of toField) {
      if (!entry || typeof entry !== "object") continue;
      const obj = entry as Record<string, unknown>;
      const nested = obj.email_address as Record<string, unknown> | undefined;
      const address = String(nested?.address || obj.address || "").toLowerCase().trim();
      if (address.includes("@")) return address;
    }
  }

  const eventData = payload.event_data as Record<string, unknown> | undefined;
  const details = eventData?.details as Record<string, unknown> | undefined;
  const fromDetails = String(details?.email || details?.recipient || "").toLowerCase().trim();
  if (fromDetails.includes("@")) return fromDetails;

  const recipient = String(payload.recipient || emailInfo?.recipient || "").toLowerCase().trim();
  if (recipient.includes("@")) return recipient;

  return "";
}

function extractSenderDomain(payload: Record<string, unknown>): string | null {
  const eventMessage = firstEventMessage(payload);
  const emailInfo = eventMessage?.email_info as Record<string, unknown> | undefined;
  const from = emailInfo?.from as Record<string, unknown> | undefined;
  const address = String(from?.address || "").toLowerCase();
  const at = address.indexOf("@");
  return at >= 0 ? address.slice(at + 1) : null;
}

function extractMimeTag(payload: Record<string, unknown>, tagName: string): string | null {
  const eventMessage = firstEventMessage(payload);
  const emailInfo = eventMessage?.email_info as Record<string, unknown> | undefined;
  const headers = emailInfo?.mime_headers || emailInfo?.headers;

  if (headers && typeof headers === "object" && !Array.isArray(headers)) {
    const key = `X-Tag-${tagName}`;
    const direct = (headers as Record<string, unknown>)[key] ||
      (headers as Record<string, unknown>)[key.toLowerCase()];
    if (direct != null && String(direct).trim()) return String(direct).trim().toLowerCase();
  }

  if (Array.isArray(headers)) {
    for (const h of headers) {
      if (!h || typeof h !== "object") continue;
      const obj = h as Record<string, unknown>;
      const name = String(obj.header || obj.name || "").toLowerCase();
      if (name === `x-tag-${tagName}` || name === tagName) {
        const value = String(obj.value || "").trim().toLowerCase();
        if (value) return value;
      }
    }
  }

  return null;
}

function normalizeAppSlug(raw: string | null): string | null {
  if (!raw) return null;
  const slug = raw.toLowerCase().trim();
  if (slug === "thesis") return "thesis_generator";
  if (KNOWN_APP_SLUGS.has(slug)) return slug;
  return null;
}

function inferApp(payload: Record<string, unknown>, senderDomain: string | null): string {
  const tagApp = normalizeAppSlug(extractMimeTag(payload, "app"));
  if (tagApp) return tagApp;

  const clientRef = String(
    (payload.event_message as Record<string, unknown> | undefined)?.email_info &&
      ((payload.event_message as Record<string, unknown>).email_info as Record<string, unknown>)
        .client_reference ||
      payload.client_reference ||
      "",
  ).toLowerCase();

  if (clientRef.includes("predictify_nba") || clientRef.includes("nba")) return "predictify_nba";
  if (clientRef.includes("horse_racing") || clientRef.includes("horse")) return "horse_racing";
  if (clientRef.includes("thesis")) return "thesis_generator";
  if (clientRef.includes("predictify")) return "predictify";

  if (senderDomain === "thesisgenerator.io") return "thesis_generator";
  if (senderDomain === "predictifyfootball.com") return "predictify";

  return "predictify";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers":
          "authorization, content-type, producer-signature, x-zeptomail-auth, x-authentication-key",
      },
    });
  }

  // ZeptoMail "Verify" may ping GET; actual events are POST.
  if (req.method === "GET") {
    return new Response(JSON.stringify({ ok: true, service: "zeptomail-webhook" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const rawBody = await req.text();

  let payload: Record<string, unknown>;
  try {
    payload = parsePayload(rawBody);
  } catch (err) {
    console.error("Invalid ZeptoMail webhook payload", err);
    return new Response("Invalid payload", { status: 400 });
  }

  if (!isHardBounce(payload)) {
    return new Response(JSON.stringify({ ok: true, ignored: "not_hard_bounce" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (WEBHOOK_AUTH_KEY) {
    const authed = await webhookAuthed(req, payload, rawBody);
    if (!authed) {
      console.error("ZeptoMail webhook auth mismatch (hard bounce)");
      return new Response("Unauthorized", { status: 401 });
    }
  }

  const recipient = extractRecipient(payload);
  if (!recipient) {
    console.error("ZeptoMail hard bounce without recipient", payload);
    return new Response(JSON.stringify({ ok: false, error: "missing recipient" }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });
  }

  const senderDomain = extractSenderDomain(payload);
  const app = inferApp(payload, senderDomain);
  const tagKind = extractMimeTag(payload, "kind");
  const eventId = String(
    payload.webhook_request_id ||
      payload.request_id ||
      `zm-${crypto.randomUUID()}`,
  );
  const messageId = String(payload.request_id || "");
  const eventData = payload.event_data as Record<string, unknown> | undefined;
  const details = eventData?.details as Record<string, unknown> | undefined;
  const occurredAt = String(details?.time || payload.processed_time || new Date().toISOString());
  const clientRef = String(
    (firstEventMessage(payload)?.email_info as Record<string, unknown> | undefined)
      ?.client_reference || "",
  );

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  await recordHardBounce(supabase, {
    recipient,
    app,
    eventId: `zm-${eventId}`,
    messageId,
    occurredAt,
    senderDomain: senderDomain || undefined,
    kind: tagKind || undefined,
    refId: clientRef || undefined,
    raw: payload,
  });

  console.log(`ZeptoMail hard bounce suppressed: ${recipient} (${app})`);

  return new Response(JSON.stringify({ ok: true, recipient, app }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
