-- Dedup ledger for instant (webhook-triggered) marketing emails.
--
-- The Flutter apps call dedicated Supabase Edge Functions when high-conversion
-- events happen (thesis completion, free-quota-hit, etc.). Each function records
-- a row here keyed by (uid, event_kind) so:
--   1. The webhook itself is idempotent — duplicate POSTs from the app (network
--      retries, race conditions) don't send the email twice.
--   2. The 2×/day batch senders that previously handled these events check this
--      table before sending — if the instant path already covered the user,
--      the batch send skips them, avoiding double emails.
--
-- Stays small: one row per (user, event) lifetime. Even at 100K users × 5
-- instant event kinds = 500K rows max. Trivial for Postgres.

create table if not exists public.instant_emails_sent (
  id              bigserial primary key,
  uid             text not null,          -- Firebase UID
  app_id          text not null,          -- thesis_generator / predictify / ...
  event_kind      text not null,          -- thesis_complete / free_quota_hit / ...
  recipient       text,                   -- email address (lowercased)
  language        text,                   -- bcp47 tag used for the send
  metadata        jsonb,                  -- thesis_id, quota_chapter, etc.
  sent_at         timestamptz not null default now(),
  resend_id       text,                   -- Resend message id, if available
  constraint instant_emails_sent_uid_event_unique unique (uid, event_kind)
);

create index if not exists instant_emails_sent_app_event_idx
  on public.instant_emails_sent (app_id, event_kind, sent_at desc);

create index if not exists instant_emails_sent_recipient_idx
  on public.instant_emails_sent (recipient)
  where recipient is not null;
