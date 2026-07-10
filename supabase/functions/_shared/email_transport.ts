/**
 * Pluggable email transport — Resend, Mailgun, or SMTP2GO.
 *
 * Set EMAIL_PROVIDER=smtp2go + SMTP2GO_API_KEY for multi-domain SMTP2GO sends.
 * Set EMAIL_PROVIDER=mailgun + MAILGUN_* to pin to passedai.io (legacy bridge).
 * Unset EMAIL_PROVIDER (or set to "resend") for Resend.
 */

import type { SenderIdentity } from "./sender_pool.ts";

export type EmailProviderName = "resend" | "mailgun" | "smtp2go";

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

export function emailProvider(): EmailProviderName {
  const p = (Deno.env.get("EMAIL_PROVIDER") || "resend").toLowerCase();
  if (p === "mailgun") return "mailgun";
  if (p === "smtp2go") return "smtp2go";
  return "resend";
}

export function isEmailSendingPaused(): boolean {
  const v = (Deno.env.get("EMAIL_SENDING_PAUSED") || "").toLowerCase();
  return v === "1" || v === "true" || v === "yes";
}

export function hasEmailCredentials(): boolean {
  const provider = emailProvider();
  if (provider === "mailgun") {
    return !!(Deno.env.get("MAILGUN_API_KEY") && Deno.env.get("MAILGUN_DOMAIN"));
  }
  if (provider === "smtp2go") {
    return !!Deno.env.get("SMTP2GO_API_KEY");
  }
  return !!Deno.env.get("RESEND_API_KEY");
}

/** Pin sender to passedai.io when Mailgun is active; pass through otherwise. */
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

function smtp2goHeaders(params: SendEmailParams): Array<{ header: string; value: string }> {
  const headers: Array<{ header: string; value: string }> = [];
  const replyTo = params.replyTo || params.fromEmail;
  if (replyTo) {
    headers.push({ header: "Reply-To", value: replyTo });
  }
  if (params.refId) {
    headers.push({ header: "X-Entity-Ref-ID", value: String(params.refId).slice(0, 256) });
  }
  for (const tag of params.tags || []) {
    headers.push({
      header: `X-Tag-${String(tag.name).slice(0, 64)}`,
      value: sanitizeTag(String(tag.value)).slice(0, 256),
    });
  }
  return headers;
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

async function sendViaSmtp2go(params: SendEmailParams): Promise<SendEmailResult> {
  const apiKey = Deno.env.get("SMTP2GO_API_KEY") || "";
  const resolved = resolveSender({ email: params.fromEmail, name: params.fromName });

  const body: Record<string, unknown> = {
    sender: `${params.fromName} <${resolved.email}>`,
    to: [params.to],
    subject: params.subject,
    html_body: params.html,
  };
  if (params.text) body.text_body = params.text;

  const customHeaders = smtp2goHeaders({ ...params, fromEmail: resolved.email });
  if (customHeaders.length) body.custom_headers = customHeaders;

  const res = await fetch("https://api.smtp2go.com/v3/email/send", {
    method: "POST",
    headers: {
      "X-Smtp2go-Api-Key": apiKey,
      "Content-Type": "application/json",
      accept: "application/json",
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

  const data = (details as Record<string, unknown>).data as Record<string, unknown> | undefined;
  if (data?.error || (typeof data?.failed === "number" && data.failed > 0)) {
    return { ok: false, status: 400, details };
  }

  const id = String(data?.email_id || "");
  return { ok: true, status: res.status, id, details };
}

export async function sendEmail(params: SendEmailParams): Promise<SendEmailResult> {
  if (isEmailSendingPaused()) {
    return { ok: false, status: 503, details: { paused: true, message: "Email sending paused" } };
  }
  const provider = emailProvider();
  if (provider === "mailgun") return sendViaMailgun(params);
  if (provider === "smtp2go") return sendViaSmtp2go(params);
  return sendViaResend(params);
}
