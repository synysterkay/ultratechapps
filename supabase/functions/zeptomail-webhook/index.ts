// Supabase Edge Function: zeptomail-webhook
// Receives ZeptoMail webhooks and writes email_events (+ suppressions for
// hard bounces / feedback-loop complaints) for health + auto-ramp.
//
// Setup (ZeptoMail dashboard → each Agent → Webhooks):
//   Agent 1: thesisgenerator.io + predictifyfootball.com
//   Agent 2: passedai.io + breakuprelief.com + kaynel.solutions
//   URL:   https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/zeptomail-webhook
//   Events: Hard bounced, Soft bounced, Delivered, Open, Click, Feedback loop
//   Agent → Webhooks → Authentication Key → same as ZEPTOMAIL_WEBHOOK_AUTH_KEY
//
// Note: ZeptoMail has no "sent" webhook — successful API sends write email.sent
// from gmail_sender.py / email_transport.ts. Open/click require track_opens /
// track_clicks enabled on the send payload.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import {
  recordComplaint,
  recordHardBounce,
} from "../_shared/email_suppressions.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const WEBHOOK_AUTH_KEY = Deno.env.get("ZEPTOMAIL_WEBHOOK_AUTH_KEY") || "";

const KNOWN_APP_SLUGS = new Set([
  "predictify",
  "predictify_nba",
  "predictify_tennis",
  "horse_racing",
  "thesis_generator",
  "thesis",
  "fresh_start",
  "breakup_therapy",
  "red_flag_scanner",
  "redflag",
  "soulplan",
  "ong",
  "sealed",
  "pupshape",
  "kinbound",
  "volume_booster",
  "volume_booster_pro",
  "bass_booster",
  "loud_eq",
  "loudify",
  "ai_boyfriend",
  "ai_girlfriend",
  "smart_notes",
  "onbrief",
  "vowcraft",
  "crosspromo",
]);

type MappedEvent = {
  eventType: string;
  suppress: "bounce" | "complaint" | null;
};

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

function firstEventData(payload: Record<string, unknown>): Record<string, unknown> | undefined {
  const eventMessage = firstEventMessage(payload);
  const nested = eventMessage?.event_data;
  if (Array.isArray(nested)) {
    const first = nested[0];
    return first && typeof first === "object" ? first as Record<string, unknown> : undefined;
  }
  if (nested && typeof nested === "object") return nested as Record<string, unknown>;

  const top = payload.event_data;
  if (Array.isArray(top)) {
    const first = top[0];
    return first && typeof first === "object" ? first as Record<string, unknown> : undefined;
  }
  if (top && typeof top === "object") return top as Record<string, unknown>;
  return undefined;
}

function objectName(payload: Record<string, unknown>): string {
  const eventData = firstEventData(payload);
  const eventMessage = firstEventMessage(payload);
  return String(
    eventData?.object ||
      eventMessage?.object ||
      "",
  ).toLowerCase();
}

function firstDetail(payload: Record<string, unknown>): Record<string, unknown> | undefined {
  const eventData = firstEventData(payload);
  const details = eventData?.details;
  if (Array.isArray(details)) {
    const first = details[0];
    return first && typeof first === "object" ? first as Record<string, unknown> : undefined;
  }
  if (details && typeof details === "object") return details as Record<string, unknown>;
  return undefined;
}

/** Map ZeptoMail event → Resend-compatible email_events.event_type. */
function mapZeptoEvent(payload: Record<string, unknown>): MappedEvent | null {
  const name = eventNameStr(payload);
  const obj = objectName(payload);
  const blob = `${name} ${obj}`;

  if (
    blob.includes("hardbounce") ||
    blob.includes("hard bounce") ||
    (blob.includes("hard") && blob.includes("bounce"))
  ) {
    return { eventType: "email.bounced", suppress: "bounce" };
  }

  if (
    blob.includes("softbounce") ||
    blob.includes("soft bounce") ||
    (blob.includes("soft") && blob.includes("bounce"))
  ) {
    // Temporary failure — do not suppress; avoid inflating hard-bounce health.
    return { eventType: "email.delivery_delayed", suppress: null };
  }

  if (
    blob.includes("email_open") ||
    blob.includes("email open") ||
    blob.includes("opened") ||
    /\bopen\b/.test(blob)
  ) {
    return { eventType: "email.opened", suppress: null };
  }

  if (
    blob.includes("email_link_click") ||
    blob.includes("link click") ||
    blob.includes("clicked") ||
    /\bclick\b/.test(blob)
  ) {
    return { eventType: "email.clicked", suppress: null };
  }

  if (blob.includes("delivered") || blob.includes("email_deliver")) {
    return { eventType: "email.delivered", suppress: null };
  }

  if (
    blob.includes("feedback") ||
    blob.includes("fbl") ||
    blob.includes("complaint") ||
    blob.includes("spam")
  ) {
    return { eventType: "email.complained", suppress: "complaint" };
  }

  return null;
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
  const detail = firstDetail(payload);
  const bounced = String(detail?.bounced_recipient || detail?.email || detail?.recipient || "")
    .toLowerCase()
    .trim();
  if (bounced.includes("@")) return bounced;

  const fblFrom = String(detail?.fblFrom || "").toLowerCase().trim();
  if (fblFrom.includes("@")) return fblFrom;

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

function extractClickedUrl(payload: Record<string, unknown>): string | null {
  const detail = firstDetail(payload);
  for (const key of ["clicked_link", "link", "url", "target_link"]) {
    const value = detail?.[key];
    if (value != null && String(value).trim()) return String(value).trim();
  }
  return null;
}

function extractClientReference(payload: Record<string, unknown>): string {
  const eventMessage = firstEventMessage(payload);
  const emailInfo = eventMessage?.email_info as Record<string, unknown> | undefined;
  return String(
    emailInfo?.client_reference ||
      payload.client_reference ||
      "",
  );
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

  const clientRef = extractClientReference(payload).toLowerCase();

  if (clientRef.includes("predictify_nba") || clientRef.includes("nba")) return "predictify_nba";
  if (clientRef.includes("predictify_tennis") || clientRef.includes("tennis") || clientRef.includes("tenis")) {
    return "predictify_tennis";
  }
  if (clientRef.includes("horse_racing") || clientRef.includes("horse")) return "horse_racing";
  if (clientRef.includes("thesis")) return "thesis_generator";
  if (clientRef.includes("crosspromo") || clientRef.includes("passed")) return "crosspromo";
  if (clientRef.includes("onbrief")) return "onbrief";
  if (clientRef.includes("vowcraft")) return "vowcraft";
  if (clientRef.includes("ong") || clientRef.includes("sealed")) return "ong";
  if (clientRef.includes("pupshape")) return "pupshape";
  if (clientRef.includes("kinbound")) return "kinbound";
  if (clientRef.includes("volume_booster")) return "volume_booster";
  if (clientRef.includes("smart_notes")) return "smart_notes";
  if (clientRef.includes("ai_boyfriend") || clientRef.includes("boyfriend")) return "ai_boyfriend";
  if (clientRef.includes("ai_girlfriend") || clientRef.includes("girlfriend")) return "ai_girlfriend";
  if (clientRef.includes("predictify")) return "predictify";
  if (clientRef.includes("soulplan")) return "soulplan";
  if (clientRef.includes("fresh_start") || clientRef.includes("breakup")) return "fresh_start";
  if (clientRef.includes("red_flag") || clientRef.includes("redflag") || clientRef.includes("selka")) {
    return "red_flag_scanner";
  }

  if (senderDomain === "thesisgenerator.io") return "thesis_generator";
  if (senderDomain === "predictifyfootball.com") return "predictify";
  if (senderDomain === "passedai.io") return "crosspromo";
  if (senderDomain === "kaynel.solutions") return "ong";
  if (senderDomain === "breakuprelief.com") {
    const fromAddr = String(
      (firstEventMessage(payload)?.email_info as Record<string, unknown> | undefined)
        ?.from &&
        ((firstEventMessage(payload)?.email_info as Record<string, unknown>).from as
          Record<string, unknown>).address || "",
    ).toLowerCase();
    if (fromAddr.startsWith("selka@")) return "red_flag_scanner";
    return "fresh_start";
  }

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

  const mapped = mapZeptoEvent(payload);
  if (!mapped) {
    // Unknown / empty verify payload — ack so Zepto dashboard tests stay green.
    return new Response(JSON.stringify({ ok: true, ignored: "unmapped_event" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (WEBHOOK_AUTH_KEY) {
    const authed = await webhookAuthed(req, payload, rawBody);
    if (!authed) {
      // Destructive events must be authenticated. Engagement events without auth
      // are ignored with 200 so Zepto "Send Test" does not fail the UI.
      if (mapped.suppress) {
        console.error(`ZeptoMail webhook auth mismatch (${mapped.eventType})`);
        return new Response("Unauthorized", { status: 401 });
      }
      return new Response(JSON.stringify({ ok: true, ignored: "unauthenticated" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
  }

  const recipient = extractRecipient(payload);
  if (!recipient) {
    console.error(`ZeptoMail ${mapped.eventType} without recipient`, payload);
    return new Response(JSON.stringify({ ok: false, error: "missing recipient" }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });
  }

  const senderDomain = extractSenderDomain(payload);
  const app = inferApp(payload, senderDomain);
  const tagKind = extractMimeTag(payload, "kind");
  const tagEmailNum = extractMimeTag(payload, "email_num");
  const tagCycle = extractMimeTag(payload, "cycle");
  const tagLanguage = extractMimeTag(payload, "language");
  const eventId = String(
    payload.webhook_request_id ||
      payload.request_id ||
      `zm-${crypto.randomUUID()}`,
  );
  const messageId = String(
    payload.request_id ||
      firstEventMessage(payload)?.request_id ||
      "",
  );
  const detail = firstDetail(payload);
  const occurredAt = String(
    detail?.time ||
      detail?.modified_time ||
      payload.processed_time ||
      new Date().toISOString(),
  );
  const clientRef = extractClientReference(payload);
  const clickedUrl = mapped.eventType === "email.clicked" ? extractClickedUrl(payload) : null;

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  const svixId = `zm-${mapped.eventType.replace("email.", "")}-${eventId}`;

  if (mapped.suppress === "bounce") {
    await recordHardBounce(supabase, {
      recipient,
      app,
      eventId: svixId,
      messageId,
      occurredAt,
      senderDomain: senderDomain || undefined,
      kind: tagKind || undefined,
      language: tagLanguage || undefined,
      refId: clientRef || undefined,
      raw: payload,
    });
  } else if (mapped.suppress === "complaint") {
    await recordComplaint(supabase, {
      recipient,
      app,
      eventId: svixId,
      messageId,
      occurredAt,
      senderDomain: senderDomain || undefined,
      kind: tagKind || undefined,
      language: tagLanguage || undefined,
      refId: clientRef || undefined,
      raw: payload,
    });
  } else {
    const { error } = await supabase.from("email_events").insert({
      svix_id: svixId,
      message_id: messageId || null,
      event_type: mapped.eventType,
      occurred_at: occurredAt,
      recipient,
      sender_domain: senderDomain,
      app,
      kind: tagKind,
      email_num: tagEmailNum,
      cycle: tagCycle,
      language: tagLanguage,
      ref_id: clientRef || null,
      clicked_url: clickedUrl,
      raw: payload,
    });

    if (error && error.code !== "23505") {
      console.error("ZeptoMail email_events insert failed", error);
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }
  }

  console.log(`ZeptoMail ${mapped.eventType}: ${recipient} (${app})`);

  return new Response(
    JSON.stringify({ ok: true, recipient, app, event_type: mapped.eventType }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
});
