/**
 * Durable bounce / complaint suppressions — shared by welcome cron,
 * instant edge functions, and provider webhooks (Resend, ZeptoMail, …).
 *
 * Rows in email_suppressions are bulk-loaded by gmail_sender.py and
 * checked before every send. sync_suppressions.py also backfills from
 * email_events, but instant upserts here prevent retries on the next cron.
 */

import type { SupabaseClient } from "jsr:@supabase/supabase-js@2";

export async function upsertBounceSuppression(
  supabase: SupabaseClient,
  recipient: string,
  app: string,
): Promise<void> {
  const email = recipient.toLowerCase().trim();
  if (!email || !app) return;

  const rows = [
    { recipient: email, app, reason: "bounce" },
    { recipient: email, app: "*", reason: "bounce" },
  ];

  const { error } = await supabase.from("email_suppressions").upsert(rows, {
    onConflict: "recipient,app",
    ignoreDuplicates: false,
  });
  if (error) {
    console.error("upsertBounceSuppression failed", error);
  }
}

export async function loadSuppressedRecipients(
  supabase: SupabaseClient,
  app: string,
): Promise<Set<string>> {
  const suppressed = new Set<string>();
  const scopes = [app, "*", "global"];

  for (const appSlug of scopes) {
    let offset = 0;
    while (true) {
      const { data, error } = await supabase
        .from("email_suppressions")
        .select("recipient")
        .eq("app", appSlug)
        .range(offset, offset + 999);

      if (error) {
        console.error(`suppression load failed for app=${appSlug}`, error);
        break;
      }

      for (const row of data || []) {
        const recipient = (row.recipient || "").toLowerCase().trim();
        if (recipient) suppressed.add(recipient);
      }

      if (!data || data.length < 1000) break;
      offset += 1000;
    }
  }

  return suppressed;
}

export async function recordHardBounce(
  supabase: SupabaseClient,
  opts: {
    recipient: string;
    app: string;
    eventId: string;
    messageId?: string;
    occurredAt?: string;
    senderDomain?: string;
    kind?: string;
    language?: string;
    refId?: string;
    raw?: unknown;
  },
): Promise<void> {
  await upsertBounceSuppression(supabase, opts.recipient, opts.app);

  const { error } = await supabase.from("email_events").insert({
    svix_id: opts.eventId,
    message_id: opts.messageId || null,
    event_type: "email.bounced",
    occurred_at: opts.occurredAt || new Date().toISOString(),
    recipient: opts.recipient.toLowerCase().trim(),
    sender_domain: opts.senderDomain || null,
    app: opts.app,
    kind: opts.kind || null,
    email_num: opts.kind === "welcome" ? "1" : null,
    cycle: opts.kind === "welcome" ? "1" : null,
    language: opts.language || null,
    ref_id: opts.refId || null,
    raw: opts.raw ?? {},
  });

  if (error && error.code !== "23505") {
    console.error("recordHardBounce email_events insert failed", error);
  }
}
