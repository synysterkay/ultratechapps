/**
 * Canonical sender pools — keep in sync with
 * scripts/deliverability_monitor.py SENDER_POOL.
 *
 * When EMAIL_PROVIDER=mailgun, email_transport.ts pins all sends to
 * hello@passedai.io / selka@passedai.io regardless of pool rotation.
 *
 * bestaiapps.site removed 2026-06-18 — domain retired.
 */

export interface SenderIdentity {
  email: string;
  name: string;
}

/** Full 7-domain pool for welcome / cross-app instant emails. */
export const SENDER_POOL_FULL: SenderIdentity[] = [
  { email: "hello@kaynel.solutions", name: "Alex" },
  { email: "hello@aibettips.io", name: "Jordan" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
  { email: "hello@thesisgenerator.io", name: "Morgan" },
  { email: "hello@passedai.io", name: "Taylor" },
  { email: "hello@academicsatire.com", name: "Riley" },
  { email: "tips@predictify.fun", name: "Drew" },
];

/** Predictify instant emails — sports-adjacent domains (no thesisgenerator). */
export const SENDER_POOL_PREDICTIFY: SenderIdentity[] = [
  { email: "hello@kaynel.solutions", name: "Alex" },
  { email: "hello@aibettips.io", name: "Jordan" },
  { email: "tips@predictifyfootball.com", name: "Sam" },
  { email: "tips@predictify.fun", name: "Drew" },
  { email: "hello@passedai.io", name: "Taylor" },
  { email: "hello@academicsatire.com", name: "Riley" },
];

/** Predictify NBA — smaller subset. */
export const SENDER_POOL_NBA: SenderIdentity[] = [
  { email: "hello@kaynel.solutions", name: "Alex" },
  { email: "hello@aibettips.io", name: "Jordan" },
  { email: "hello@academicsatire.com", name: "Riley" },
];

/** Thesis Generator instant emails. */
export const SENDER_POOL_THESIS: SenderIdentity[] = [
  { email: "hello@thesisgenerator.io", name: "Morgan" },
  { email: "hello@passedai.io", name: "Taylor" },
  { email: "hello@academicsatire.com", name: "Riley" },
];

/** Red Flag Scanner (Selka) — selka@ prefix on each domain. */
export const SENDER_POOL_SELKA: SenderIdentity[] = [
  { email: "selka@kaynel.solutions", name: "Selka" },
  { email: "selka@aibettips.io", name: "Selka" },
  { email: "selka@predictifyfootball.com", name: "Selka" },
  { email: "selka@thesisgenerator.io", name: "Selka" },
  { email: "selka@passedai.io", name: "Selka" },
  { email: "selka@academicsatire.com", name: "Selka" },
];

/** Resend rejects newlines and subjects over 2000 characters. */
export function sanitizeSubject(subject: string, maxLen = 2000): string {
  const s = (subject || "").replace(/[\r\n]+/g, " ").trim();
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 1) + "…";
}
