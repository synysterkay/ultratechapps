/**
 * Canonical sender pools — keep in sync with
 * scripts/deliverability_monitor.py SENDER_POOL.
 *
 * SMTP2GO enabled senders: breakuprelief.com, kaynel.solutions, passedai.io.
 * predictifyfootball.com — unverified. predictify.fun — verified but disabled.
 *
 * When EMAIL_PROVIDER=zeptomail, email_transport.ts routes by app tag:
 *   thesis → hello@thesisgenerator.io
 *   predictify / predictify_nba / horse_racing → hello@predictifyfootball.com
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

/** Predictify instant emails — predictifyfootball.com (ZeptoMail verified). */
export const SENDER_POOL_PREDICTIFY: SenderIdentity[] = [
  { email: "hello@predictifyfootball.com", name: "Predictify" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
];

/** Predictify NBA — same domain as Soccer. */
export const SENDER_POOL_NBA: SenderIdentity[] = [
  { email: "hello@predictifyfootball.com", name: "Predictify NBA" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
];

/** Thesis Generator — thesisgenerator.io (ZeptoMail verified). */
export const SENDER_POOL_THESIS: SenderIdentity[] = [
  { email: "hello@thesisgenerator.io", name: "Thesis Generator" },
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
