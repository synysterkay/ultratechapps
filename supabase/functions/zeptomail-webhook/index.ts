// Supabase Edge Function: zeptomail-webhook
// Receives ZeptoMail bounce/open/click webhooks and writes email_events +
// email_suppressions (hard bounces only) so bad addresses are skipped everywhere.
//
// Setup (ZeptoMail dashboard → Agents → thesisgenerator.io → Webhooks):
//   URL:   https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/zeptomail-webhook
//   Events: Hard bounced (required), Soft bounced (optional)
//   Authentication Key → set same value as ZEPTOMAIL_WEBHOOK_AUTH_KEY secret

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { recordHardBounce } from "../_shared/email_suppressions.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const WEBHOOK_AUTH_KEY = Deno.env.get("ZEPTOMAIL_WEBHOOK_AUTH_KEY") || "";

function parsePayload(rawBody: string): Record<string, unknown> {
  const trimmed = rawBody.trim();
  if (!trimmed) return {};

  if (trimmed.startsWith("{")) {
    return JSON.parse(trimmed);
  }

  // ZeptoMail test payloads may arrive as application/x-www-form-urlencoded.
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

function isHardBounce(payload: Record<string, unknown>): boolean {
  const eventName = String(payload.event_name || payload.event || "").toLowerCase();
  const objectName = String(
    (payload.event_data as Record<string, unknown> | undefined)?.object ||
      (payload.event_message as Record<string, unknown> | undefined)?.object ||
      "",
  ).toLowerCase();

  return eventName.includes("hard") ||
    objectName.includes("hardbounce") ||
    objectName === "hardbounce";
}

function extractRecipient(payload: Record<string, unknown>): string {
  const eventMessage = payload.event_message as Record<string, unknown> | undefined;
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
  const eventMessage = payload.event_message as Record<string, unknown> | undefined;
  const emailInfo = eventMessage?.email_info as Record<string, unknown> | undefined;
  const from = emailInfo?.from as Record<string, unknown> | undefined;
  const address = String(from?.address || "").toLowerCase();
  const at = address.indexOf("@");
  return at >= 0 ? address.slice(at + 1) : null;
}

function inferApp(payload: Record<string, unknown>, senderDomain: string | null): string {
  const clientRef = String(
    (payload.event_message as Record<string, unknown> | undefined)?.email_info &&
      ((payload.event_message as Record<string, unknown>).email_info as Record<string, unknown>)
        .client_reference ||
      payload.client_reference ||
      "",
  );

  if (clientRef.includes("thesis") || senderDomain === "thesisgenerator.io") {
    return "thesis_generator";
  }

  return "unknown";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers":
          "authorization, content-type, producer-signature",
      },
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

  if (WEBHOOK_AUTH_KEY) {
    const headerAuth = req.headers.get("x-zeptomail-auth") ||
      req.headers.get("x-authentication-key") || "";
    const bodyAuth = authKeyFromPayload(payload);
    if (headerAuth !== WEBHOOK_AUTH_KEY && bodyAuth !== WEBHOOK_AUTH_KEY) {
      console.error("ZeptoMail webhook auth mismatch");
      return new Response("Unauthorized", { status: 401 });
    }
  }

  if (!isHardBounce(payload)) {
    return new Response(JSON.stringify({ ok: true, ignored: "not_hard_bounce" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
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
    ((payload.event_message as Record<string, unknown> | undefined)?.email_info as
      | Record<string, unknown>
      | undefined)?.client_reference || "",
  );

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
  await recordHardBounce(supabase, {
    recipient,
    app: app === "unknown" ? "thesis_generator" : app,
    eventId: `zm-${eventId}`,
    messageId,
    occurredAt,
    senderDomain: senderDomain || undefined,
    kind: "welcome",
    refId: clientRef || undefined,
    raw: payload,
  });

  console.log(`ZeptoMail hard bounce suppressed: ${recipient} (${app})`);

  return new Response(JSON.stringify({ ok: true, recipient, app }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
