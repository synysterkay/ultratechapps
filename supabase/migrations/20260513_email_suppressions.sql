-- Email suppression table — explicit user-driven opt-outs.
--
-- Separate from email_events (which is the raw Resend feed) because:
--   1. Unsubscribe is a user action, not a delivery event.
--   2. We want a clean (recipient, app) primary key with no nulls so the
--      orchestrator's bulk-load query stays O(rows) and dedup-free.
--   3. Different apps may have different opt-out policies, so the
--      `app` column lets us scope per Predictify / Thesis / etc.
--
-- The orchestrator already reads this table via the Predictify
-- suppression path (orchestrator.py:_load_suppressed_emails) and
-- tolerates its absence with a 404 — so creating it is a strict
-- improvement, never a breaking change.

create table if not exists public.email_suppressions (
  recipient    text not null,                          -- lowercased
  app          text not null,                          -- 'predictify' / 'thesis' / ...
  reason       text not null default 'unsubscribe',    -- 'unsubscribe' / 'bounce' / 'complaint' / 'manual'
  created_at   timestamptz not null default now(),
  primary key (recipient, app)
);

-- App scan: orchestrator bulk-loads all rows for one app at run start.
create index if not exists email_suppressions_app_idx
  on public.email_suppressions (app);

-- Recipient lookup: per-user "am I suppressed?" check (used by the
-- unsubscribe Edge Function to render a friendly confirmation page).
create index if not exists email_suppressions_recipient_idx
  on public.email_suppressions (recipient);
