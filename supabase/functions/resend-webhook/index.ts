// Supabase Edge Function: resend-webhook
// Receives Resend event webhooks (email.delivered, opened, clicked, bounced,
// complained, etc.) and writes them into the `email_events` table for
// per-app / per-email-number / per-language analytics + auto-scaling input.
//
// Setup (one-time, in Resend dashboard):
//   Webhooks → Add Endpoint
//     URL:    https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/resend-webhook
//     Events: email.sent, email.delivered, email.delivery_delayed,
//             email.opened, email.clicked, email.bounced, email.complained
//   Copy the "Signing secret" → set as RESEND_WEBHOOK_SECRET on this function.
//
// Verifies signatures via Svix headers (svix-id, svix-timestamp, svix-signature)
// since Resend uses Svix under the hood.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { recordComplaint, recordHardBounce } from "../_shared/email_suppressions.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const WEBHOOK_SECRET = Deno.env.get("RESEND_WEBHOOK_SECRET") || "";

// Tolerate timestamps within ± this window (seconds) — guards against replay.
const TIMESTAMP_TOLERANCE_SECONDS = 5 * 60;

async function verifySvixSignature(
  rawBody: string,
  svixId: string,
  svixTimestamp: string,
  svixSignature: string,
  secret: string
): Promise<boolean> {
  // Secret is base64-encoded after the `whsec_` prefix
  const secretBytes = Uint8Array.from(
    atob(secret.replace(/^whsec_/, "")),
    (c) => c.charCodeAt(0)
  );

  const signedPayload = `${svixId}.${svixTimestamp}.${rawBody}`;
  const key = await crypto.subtle.importKey(
    "raw",
    secretBytes,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sigBuf = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(signedPayload)
  );
  const expected = btoa(String.fromCharCode(...new Uint8Array(sigBuf)));

  // svix-signature is space-separated list of "v1,<sig>" entries; any match is valid
  const candidates = svixSignature
    .split(" ")
    .map((s) => s.trim())
    .filter((s) => s.startsWith("v1,"))
    .map((s) => s.slice(3));

  return candidates.some((c) => timingSafeEqual(c, expected));
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function tagValue(tags: unknown, name: string): string | null {
  if (!tags || typeof tags !== "object") return null;
  // Resend delivers tags as an OBJECT: { app: "predictify", kind: "welcome" }.
  // (The previous code assumed an array-of-{name,value} and so wrote null to
  // every tag column — app/kind/etc. were blank for 13k+ events.)
  if (!Array.isArray(tags)) {
    const v = (tags as Record<string, unknown>)[name];
    return v == null ? null : String(v);
  }
  // Tolerate the array-of-{name,value} shape too, just in case.
  for (const t of tags) {
    if (t && typeof t === "object" && (t as Record<string, unknown>).name === name) {
      const v = (t as Record<string, unknown>).value;
      return v == null ? null : String(v);
    }
  }
  return null;
}

// Resend delivers headers as an ARRAY: [{ name, value }]. X-Entity-Ref-ID
// (our per-user attribution id) lives there.
function headerValue(headers: unknown, name: string): string {
  if (Array.isArray(headers)) {
    for (const h of headers) {
      if (h && typeof h === "object" && (h as Record<string, unknown>).name === name) {
        return String((h as Record<string, unknown>).value ?? "");
      }
    }
    return "";
  }
  if (headers && typeof headers === "object") {
    return String((headers as Record<string, unknown>)[name] ?? "");
  }
  return "";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers":
          "authorization, content-type, svix-id, svix-timestamp, svix-signature",
      },
    });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const rawBody = await req.text();

  // ── Verify signature ─────────────────────────────────────
  const svixId = req.headers.get("svix-id") || "";
  const svixTimestamp = req.headers.get("svix-timestamp") || "";
  const svixSignature = req.headers.get("svix-signature") || "";

  if (!WEBHOOK_SECRET) {
    console.error("RESEND_WEBHOOK_SECRET not configured — rejecting");
    return new Response("Webhook not configured", { status: 500 });
  }
  if (!svixId || !svixTimestamp || !svixSignature) {
    return new Response("Missing signature headers", { status: 400 });
  }

  // Replay protection
  const ts = parseInt(svixTimestamp, 10);
  if (!Number.isFinite(ts)) return new Response("Bad timestamp", { status: 400 });
  const nowSec = Math.floor(Date.now() / 1000);
  if (Math.abs(nowSec - ts) > TIMESTAMP_TOLERANCE_SECONDS) {
    return new Response("Timestamp out of tolerance", { status: 400 });
  }

  const valid = await verifySvixSignature(
    rawBody,
    svixId,
    svixTimestamp,
    svixSignature,
    WEBHOOK_SECRET
  );
  if (!valid) {
    return new Response("Invalid signature", { status: 401 });
  }

  // ── Parse + insert ───────────────────────────────────────
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  const eventType = String(payload.type || "");
  const data = (payload.data || {}) as Record<string, unknown>;
  const messageId = String(data.email_id || data.id || "");
  const occurredAt = String(payload.created_at || data.created_at || new Date().toISOString());

  // Recipient: Resend sends "to" as string[] for these events
  let recipient: string | null = null;
  const toField = data.to;
  if (Array.isArray(toField) && toField.length > 0) {
    recipient = String(toField[0]).toLowerCase();
  } else if (typeof toField === "string") {
    recipient = toField.toLowerCase();
  }

  const fromField = data.from as string | undefined;
  let senderDomain: string | null = null;
  if (fromField) {
    const m = fromField.match(/<([^>]+)>/);
    const addr = m ? m[1] : fromField;
    const at = addr.indexOf("@");
    if (at >= 0) senderDomain = addr.slice(at + 1).toLowerCase();
  }

  const tags = data.tags;
  const clickedUrl =
    eventType === "email.clicked" && data.click && typeof data.click === "object"
      ? String((data.click as Record<string, unknown>).link || "")
      : null;

  const refId =
    headerValue(data.headers, "X-Entity-Ref-ID") || tagValue(tags, "ref") || null;

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  const { error } = await supabase.from("email_events").insert({
    svix_id: svixId,
    message_id: messageId || null,
    event_type: eventType,
    occurred_at: occurredAt,
    recipient,
    sender_domain: senderDomain,
    app: tagValue(tags, "app"),
    kind: tagValue(tags, "kind"),
    email_num: tagValue(tags, "email_num"),
    cycle: tagValue(tags, "cycle"),
    language: tagValue(tags, "language"),
    segment: tagValue(tags, "segment"),
    ref_id: refId,
    clicked_url: clickedUrl,
    raw: payload,
  });

  if (error) {
    // Duplicate svix_id (replay/retry) → ack 200 so Resend stops retrying
    if (error.code === "23505") {
      return new Response(JSON.stringify({ ok: true, duplicate: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    console.error("DB insert failed", error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const appSlug = tagValue(tags, "app") || "unknown";
  if (recipient && eventType === "email.bounced") {
    await recordHardBounce(supabase, {
      recipient,
      app: appSlug,
      eventId: svixId,
      messageId: messageId || undefined,
      occurredAt,
      senderDomain: senderDomain || undefined,
      kind: tagValue(tags, "kind") || undefined,
      language: tagValue(tags, "language") || undefined,
      refId: refId || undefined,
      raw: payload,
    });
  } else if (recipient && eventType === "email.complained") {
    await recordComplaint(supabase, {
      recipient,
      app: appSlug,
      eventId: svixId,
      messageId: messageId || undefined,
      occurredAt,
      senderDomain: senderDomain || undefined,
      kind: tagValue(tags, "kind") || undefined,
      language: tagValue(tags, "language") || undefined,
      refId: refId || undefined,
      raw: payload,
    });
  }

  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
