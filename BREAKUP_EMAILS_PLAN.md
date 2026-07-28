# Breakup Relief + Selka Email Plan

ZeptoMail retention for **[breakuprelief.com](http://breakuprelief.com)** — **Fresh Start: Breakup Therapy** and **Selka (Red Flag Scanner)**. **No 30-day drip.**

## ZeptoMail: Agent 1 vs Agent 2

| Agent | Domains | Apps | Why separate |
|-------|---------|------|--------------|
| **Agent 1** | thesisgenerator.io, predictifyfootball.com | Thesis, Predictify | High-volume product email |
| **Agent 2** (recommended) | **breakuprelief.com** | Fresh Start, Selka | Different audience + tone; isolates reputation from thesis/sports |

**Do not add breakuprelief.com to Agent 1.** Use a dedicated Agent 2 (or new mail agent) so a wellness/dating complaint spike cannot hurt thesis/predictify deliverability.

## Senders (after domain verify)

| App | From | App tag |
|-----|------|---------|
| Fresh Start | `hello@breakuprelief.com` (Casey) | `fresh_start` |
| Selka | `selka@breakuprelief.com` (Selka) | `red_flag_scanner` |

## Layers (no 30-day drip)

| Layer | Fresh Start | Selka |
|-------|-------------|-------|
| **Welcome** | Supabase `check-new-users` → `welcome-email` | Firebase `sendSelkaWelcome` (instant) |
| **Behavioral** | TBD (orchestrator / edge functions) | Firebase `email_events` dispatcher (Tracks A–E) |
| **30-day drip** | **Removed** from `ACTIVE_APPS` | **Removed** from `ACTIVE_APPS` |

## Hostinger DNS (add in ZeptoMail → Agent 2 → breakuprelief.com)

After adding the domain in ZeptoMail, copy the records Zepto shows and add them in Hostinger:

1. **SPF** — TXT on `@` (merge with existing SPF if any; only one SPF record allowed)
2. **DKIM** — CNAME/TEXT records Zepto provides
3. **Return-Path / bounce domain** — CNAME Zepto provides
4. **Optional tracking** — if you enable open/click later

Verify in ZeptoMail dashboard until status = **Verified**.

## Env vars

### Supabase (marketing project `jimcdgkwbbrxgakingtg`)

```
EMAIL_PROVIDER=zeptomail
ZEPTOMAIL_API_KEY=...              # Agent 1 (thesis/predictify) — existing
ZEPTOMAIL_BREAKUP_API_KEY=...       # Agent 2 send token for breakuprelief.com
ZEPTOMAIL_BREAKUP_SENDER_EMAIL=hello@breakuprelief.com
ZEPTOMAIL_SELKA_SENDER_EMAIL=selka@breakuprelief.com
BREAKUP_ZEPTOMAIL_DAILY_CAP=200
BREAKUP_ZEPTOMAIL_MAX_PER_RUN=20
```

### Firebase (`redflagscanner` + `breakuptherapy-e7dc0`)

Set on each project (Firebase console → Functions → environment):

```
EMAIL_PROVIDER=zeptomail
ZEPTOMAIL_BREAKUP_API_KEY=...
ZEPTOMAIL_BREAKUP_SENDER_EMAIL=hello@breakuprelief.com
ZEPTOMAIL_SELKA_SENDER_EMAIL=selka@breakuprelief.com
ZEPTOMAIL_API_URL=https://api.zeptomail.eu/v1.1/email
```

## Webhook (hard bounces)

Same Supabase URL as thesis/predictify:

```
https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/zeptomail-webhook
```

Add webhook on **Agent 2 → breakuprelief.com → Hard bounces** with the same `ZEPTOMAIL_WEBHOOK_AUTH_KEY`.

## Deploy checklist

1. Verify `breakuprelief.com` on ZeptoMail Agent 2 + DNS in Hostinger
2. Create mailboxes / sender addresses: `hello@`, `selka@`
3. Set Supabase secrets above
4. Deploy edge functions:
   ```bash
   supabase functions deploy welcome-email check-new-users zeptomail-webhook --project-ref jimcdgkwbbrxgakingtg
   ```
5. Redeploy Firebase welcome pipeline:
   ```bash
   cd firebase-welcome && ./deploy.sh redflagscanner
   cd firebase-welcome && ./deploy.sh breakuptherapy-e7dc0
   ```
6. Set `EMAIL_PROVIDER=zeptomail` on both Firebase projects

## Firebase projects

| Project | App | Welcome path |
|---------|-----|--------------|
| `breakuptherapy-e7dc0` | Fresh Start | Supabase cron (ZeptoMail); Firebase skipped when `EMAIL_PROVIDER=zeptomail` |
| `redflagscanner` | Selka | Firebase instant + lifecycle dispatcher |
