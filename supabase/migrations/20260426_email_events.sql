-- Email events table — stores every Resend webhook event for analytics + auto-scaling.
-- Indexed for the queries we run hot:
--   1) Per-sender 7-day open/bounce rate (drives sender_health.json status).
--   2) Per-app per-email-number conversion funnels.
--   3) Per-user engagement (joined via ref_id) for churning classifier.

create table if not exists public.email_events (
  id              bigserial primary key,
  svix_id         text not null,
  message_id      text,
  event_type      text not null,           -- email.delivered / opened / clicked / bounced / complained / sent / delivery_delayed
  occurred_at     timestamptz not null,
  recipient       text,                    -- lowercased
  sender_domain   text,                    -- e.g. kaynel.pl
  app             text,                    -- tag: predictify / thesis / ...
  kind            text,                    -- tag: retention / welcome / streak / matchday
  email_num       text,                    -- tag: 1..30 (or league name for matchday)
  cycle           text,                    -- tag: 1 / 2 / 3
  language        text,                    -- tag: en / ar / es / ...
  segment         text,                    -- tag: new / normal / churning / streak / matchday
  ref_id          text,                    -- hashed user identifier (X-Entity-Ref-ID)
  clicked_url     text,                    -- only for email.clicked
  raw             jsonb not null,
  inserted_at     timestamptz not null default now(),
  constraint email_events_svix_id_unique unique (svix_id)
);

create index if not exists email_events_sender_event_time_idx
  on public.email_events (sender_domain, event_type, occurred_at desc);

create index if not exists email_events_app_email_num_idx
  on public.email_events (app, email_num, event_type);

create index if not exists email_events_ref_id_idx
  on public.email_events (ref_id, occurred_at desc)
  where ref_id is not null;

create index if not exists email_events_recipient_idx
  on public.email_events (recipient, occurred_at desc)
  where recipient is not null;

-- Helpful 7-day per-sender aggregate view used by sender_health updater.
-- Excludes warming traffic so reputation metrics reflect only marketing sends.
create or replace view public.sender_health_7d as
with windowed as (
  select
    sender_domain,
    event_type,
    count(*) as n
  from public.email_events
  where occurred_at >= now() - interval '7 days'
    and sender_domain is not null
    and (kind is null or kind <> 'warming')
  group by sender_domain, event_type
)
select
  sender_domain,
  coalesce(sum(n) filter (where event_type = 'email.delivered'), 0) as delivered,
  coalesce(sum(n) filter (where event_type = 'email.opened'),    0) as opens,
  coalesce(sum(n) filter (where event_type = 'email.clicked'),   0) as clicks,
  coalesce(sum(n) filter (where event_type = 'email.bounced'),   0) as bounces,
  coalesce(sum(n) filter (where event_type = 'email.complained'),0) as complaints
from windowed
group by sender_domain;
