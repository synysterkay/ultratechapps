// Supabase Edge Function: soulplan-unsubscribe
//
// One-click unsubscribe for SoulPlan retention emails. The orchestrator
// (scripts/app_retention_emailer.py) embeds a per-recipient signed link in
// every email footer:
//   {BASE}/soulplan-unsubscribe?e=<b64>&s=<hex>
//
// Where:
//   e = base64url("user@example.com|soulplan")
//   s = first 32 hex chars of HMAC-SHA256(SOULPLAN_UNSUBSCRIBE_SECRET, e)
//
// On a valid click we upsert into email_suppressions; the orchestrator
// bulk-loads this table at run start and skips matching recipients.
//
// SoulPlan-scoped: writes app='soulplan' only. Unsubscribing from SoulPlan
// has no effect on Predictify / Thesis / other apps in the platform.
//
// Setup:
//   1. The email_suppressions table already exists (used by Predictify).
//      Same migration: 20260512_email_suppressions.sql.
//   2. Set env vars on this function:
//        SUPABASE_URL                       (auto-provided by Supabase)
//        SUPABASE_SERVICE_ROLE_KEY          (auto-provided)
//        SOULPLAN_UNSUBSCRIBE_SECRET        (must match the orchestrator's
//                                            SOULPLAN_UNSUBSCRIBE_SECRET)
//   3. Set the same secret as a GitHub Actions secret so the orchestrator
//      can sign links: SOULPLAN_UNSUBSCRIBE_SECRET.
//   4. Deploy: `supabase functions deploy soulplan-unsubscribe`.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const SIGNING_SECRET = Deno.env.get("SOULPLAN_UNSUBSCRIBE_SECRET") || "";

function htmlPage(title: string, body: string): string {
  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title></head>
<body style="margin:0;padding:0;background:#FFF7F8;font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;color:#2E2E2E">
<div style="max-width:520px;margin:48px auto;background:#fff;padding:40px 28px;border-radius:16px;box-shadow:0 2px 12px rgba(0,0,0,0.04)">
<div style="font-size:22px;font-weight:800;margin-bottom:6px;color:#E91C40">💛 SoulPlan</div>
<div style="height:1px;background:#FAD2DC;margin:16px 0 24px"></div>
${body}
<div style="margin-top:32px;font-size:13px;color:#9E9E9E">SoulPlan · soulplan.app</div>
</div></body></html>`;
}

function b64urlDecode(s: string): string {
  // Pad back to multiple of 4
  const padded = s + "=".repeat((4 - (s.length % 4)) % 4);
  return atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
}

async function hmacHexShort(message: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(message),
  );
  const hex = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return hex.slice(0, 32);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const e = url.searchParams.get("e") || "";
  const s = url.searchParams.get("s") || "";

  if (!e) {
    return new Response(
      htmlPage("SoulPlan — Unsubscribe", `<p>This unsubscribe link is missing required parameters. If you reached this page directly, please use the link in your most recent SoulPlan email.</p>`),
      { status: 400, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }

  // ── Decode + verify ─────────────────────────────────────
  let payload: string;
  try {
    payload = b64urlDecode(e);
  } catch {
    return new Response(
      htmlPage("SoulPlan — Unsubscribe", `<p>This unsubscribe link is malformed. If you keep seeing this, reply to the email you received and we'll handle it manually.</p>`),
      { status: 400, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }

  const parts = payload.split("|");
  // Single-app handler — only SoulPlan is in scope.
  const ALLOWED_APPS = new Set(["soulplan"]);
  if (parts.length !== 2 || !ALLOWED_APPS.has(parts[1])) {
    return new Response(
      htmlPage("SoulPlan — Unsubscribe", `<p>This unsubscribe link is not valid for SoulPlan.</p>`),
      { status: 400, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }
  const recipient = parts[0].toLowerCase().trim();
  const appSlug = parts[1];

  if (!SIGNING_SECRET) {
    // Server is misconfigured. Render a "we received your request" page
    // but DON'T actually suppress — manual review required.
    return new Response(
      htmlPage("SoulPlan — Unsubscribe", `<p>We've received your unsubscribe request for <b>${recipient}</b>. A team member will confirm it shortly.</p>`),
      { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }

  const expected = await hmacHexShort(e, SIGNING_SECRET);
  if (!s || !timingSafeEqual(s, expected)) {
    return new Response(
      htmlPage("SoulPlan — Unsubscribe", `<p>This unsubscribe link has expired or been tampered with. Reply to the email you received and we'll remove you manually.</p>`),
      { status: 400, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }

  // ── Upsert suppression ──────────────────────────────────
  try {
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
    const { error } = await supabase
      .from("email_suppressions")
      .upsert(
        {
          recipient,
          app: appSlug,
          reason: "unsubscribe",
        },
        { onConflict: "recipient,app", ignoreDuplicates: false },
      );
    if (error) {
      console.error("suppression upsert failed", error);
      return new Response(
        htmlPage("SoulPlan — Unsubscribe", `<p>We hit a temporary error processing your request. Please reply to the email you received and we'll handle it manually.</p>`),
        { status: 500, headers: { "Content-Type": "text/html; charset=utf-8" } },
      );
    }
  } catch (err) {
    console.error("supabase error", err);
    return new Response(
      htmlPage("SoulPlan — Unsubscribe", `<p>We hit a temporary error processing your request. Please reply to the email you received and we'll handle it manually.</p>`),
      { status: 500, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }

  return new Response(
    htmlPage(
      "SoulPlan — Unsubscribed",
      `<h2 style="margin:0 0 12px;font-size:22px;font-weight:700;color:#2E2E2E">You're unsubscribed 💛</h2>
<p style="color:#374151;line-height:1.5"><b>${recipient}</b> won't receive any more retention emails from SoulPlan.</p>
<p style="color:#6b7280;font-size:14px;line-height:1.5">If you change your mind, just sign in to the app and your account will resume notifications automatically.</p>`,
    ),
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
});
