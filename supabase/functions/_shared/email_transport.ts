/**
 * Pluggable email transport — Resend (default) or Mailgun (temporary).
 *
 * Set EMAIL_PROVIDER=mailgun + MAILGUN_API_KEY + MAILGUN_DOMAIN=passedai.io
 * to pin all sends to passedai.io while Resend is under review.
 * Unset EMAIL_PROVIDER (or set to "resend") to restore multi-domain Resend.
 */

import type { SenderIdentity } from "./sender_pool.ts";

export interface EmailTag {
  name: string;
  value: string;
}

export interface SendEmailParams {
  /** Display name in From header (e.g. "Predictify" or "Taylor"). */
  fromName: string;
  fromEmail: string;
  to: string;
  subject: string;
  html: string;
  text?: string;
  replyTo?: string;
  tags?: EmailTag[];
  refId?: string;
}

export interface SendEmailResult {
  ok: boolean;
  status: number;
  id?: string;
  details?: unknown;
}

const BOUNCE_INDICATORS = [
  "not found",
  "does not exist",
  "invalid",
  "rejected",
  "bounce",
  "undeliverable",
  "mailbox",
  "unknown user",
];

export function emailProvider(): "resend" | "mailgun" {
  const p = (Deno.env.get("EMAIL_PROVIDER") || "resend").toLowerCase();
  return p === "mailgun" ? "mailgun" : "resend";
}

export function hasEmailCredentials(): boolean {
  if (emailProvider() === "mailgun") {
    return !!(Deno.env.get("MAILGUN_API_KEY") && Deno.env.get("MAILGUN_DOMAIN"));
  }
  return !!Deno.env.get("RESEND_API_KEY");
}

/** Pin sender to passedai.io when Mailgun is active; pass through on Resend. */
export function resolveSender(poolSender: SenderIdentity): SenderIdentity {
  if (emailProvider() !== "mailgun") return poolSender;

  const isSelka = poolSender.email.toLowerCase().startsWith("selka@");
  const email = isSelka
    ? (Deno.env.get("MAILGUN_SELKA_SENDER_EMAIL") || "selka@passedai.io")
    : (Deno.env.get("MAILGUN_SENDER_EMAIL") || "hello@passedai.io");

  return { email, name: poolSender.name };
}

export function isSendFailureBounce(result: SendEmailResult): boolean {
  if (result.ok) return false;
  if (result.status !== 400 && result.status !== 422) return false;
  const errStr = JSON.stringify(result.details ?? "").toLowerCase();
  return BOUNCE_INDICATORS.some((b) => errStr.includes(b));
}

function sanitizeTag(value: string): string {
  return value.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 256);
}

async function sendViaResend(params: SendEmailParams): Promise<SendEmailResult> {
  const apiKey = Deno.env.get("RESEND_API_KEY") || "";
  const resolved = resolveSender({ email: params.fromEmail, name: params.fromName });

  const body: Record<string, unknown> = {
    from: `${params.fromName} <${resolved.email}>`,
    to: [params.to],
    subject: params.subject,
    html: params.html,
    reply_to: params.replyTo || resolved.email,
  };
  if (params.text) body.text = params.text;
  if (params.tags?.length) {
    body.tags = params.tags.map((t) => ({
      name: String(t.name).slice(0, 256),
      value: sanitizeTag(String(t.value)).slice(0, 256),
    }));
  }
  if (params.refId) {
    body.headers = { "X-Entity-Ref-ID": String(params.refId).slice(0, 256) };
  }

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  let details: unknown;
  try {
    details = await res.json();
  } catch {
    details = { raw: await res.text() };
  }

  if (!res.ok) {
    return { ok: false, status: res.status, details };
  }

  const id = String((details as Record<string, unknown>).id || "");
  return { ok: true, status: res.status, id, details };
}

async function sendViaMailgun(params: SendEmailParams): Promise<SendEmailResult> {
  const apiKey = Deno.env.get("MAILGUN_API_KEY") || "";
  const domain = Deno.env.get("MAILGUN_DOMAIN") || "passedai.io";
  const resolved = resolveSender({ email: params.fromEmail, name: params.fromName });

  const form = new FormData();
  form.append("from", `${params.fromName} <${resolved.email}>`);
  form.append("to", params.to);
  form.append("subject", params.subject);
  form.append("html", params.html);
  if (params.text) form.append("text", params.text);
  form.append("h:Reply-To", params.replyTo || resolved.email);
  if (params.refId) form.append("v:ref_id", String(params.refId).slice(0, 256));

  for (const tag of params.tags || []) {
    form.append("o:tag", `${tag.name}:${sanitizeTag(tag.value)}`);
  }

  const auth = btoa(`api:${apiKey}`);
  const res = await fetch(`https://api.mailgun.net/v3/${domain}/messages`, {
    method: "POST",
    headers: { Authorization: `Basic ${auth}` },
    body: form,
  });

  let details: unknown;
  try {
    details = await res.json();
  } catch {
    details = { raw: await res.text() };
  }

  if (!res.ok) {
    return { ok: false, status: res.status, details };
  }

  const id = String((details as Record<string, unknown>).id || "");
  return { ok: true, status: res.status, id, details };
}

export async function sendEmail(params: SendEmailParams): Promise<SendEmailResult> {
  if (emailProvider() === "mailgun") {
    return sendViaMailgun(params);
  }
  return sendViaResend(params);
}
