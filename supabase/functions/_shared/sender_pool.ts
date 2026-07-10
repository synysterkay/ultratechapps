/**
 * Canonical sender pools — keep in sync with
 * scripts/deliverability_monitor.py SENDER_POOL.
 *
 * SMTP2GO enabled senders: breakuprelief.com, kaynel.solutions, passedai.io.
 * predictifyfootball.com — unverified. predictify.fun — verified but disabled.
 *
 * When EMAIL_PROVIDER=mailgun, email_transport.ts pins all sends to
 * hello@passedai.io / selka@passedai.io regardless of pool rotation.
 * When EMAIL_PROVIDER=smtp2go, pool From addresses pass through as-is.
 */

export interface SenderIdentity {
  email: string;
  name: string;
}

/** Enabled SMTP2GO senders — welcome / cross-app instant emails. */
export const SENDER_POOL_FULL: SenderIdentity[] = [
  { email: "hello@breakuprelief.com", name: "Casey" },
  { email: "hello@kaynel.solutions", name: "Alex" },
  { email: "hello@passedai.io", name: "Taylor" },
];

/** Predictify instant emails — enabled domains only. */
export const SENDER_POOL_PREDICTIFY: SenderIdentity[] = [
  { email: "hello@kaynel.solutions", name: "Alex" },
  { email: "hello@passedai.io", name: "Taylor" },
];

/** Predictify NBA — enabled subset. */
export const SENDER_POOL_NBA: SenderIdentity[] = [
  { email: "hello@kaynel.solutions", name: "Alex" },
  { email: "hello@passedai.io", name: "Taylor" },
];

/** Thesis Generator — thesisgenerator.io pending; use general pool. */
export const SENDER_POOL_THESIS: SenderIdentity[] = [
  { email: "hello@passedai.io", name: "Taylor" },
  { email: "hello@kaynel.solutions", name: "Alex" },
];

/** Red Flag Scanner (Selka) — selka@ on enabled domains only. */
export const SENDER_POOL_SELKA: SenderIdentity[] = [
  { email: "selka@kaynel.solutions", name: "Selka" },
  { email: "selka@passedai.io", name: "Selka" },
];

/** Resend rejects newlines and subjects over 2000 characters. */
export function sanitizeSubject(subject: string, maxLen = 2000): string {
  const s = (subject || "").replace(/[\r\n]+/g, " ").trim();
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 1) + "…";
}
