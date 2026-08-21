# Onbrief Email System

Firebase project: `onbrief-185c5`  
Bundle ID: `com.onbrief.research`  
Sender: **Onbrief** `<hello@kaynel.solutions>`  
ZeptoMail: **Agent 2** (same agent as ONG / leftover apps — not Agent 1)

No 30-day drip. Hooked-model behavioral mail only — Thesis / ONG playbook,
with **work-brief copy**. Never thesis, homework, school, or assignment language.

## Why Agent 2 + kaynel.solutions

Agent 1 is thesis + Predictify (high volume, student/sports complaint profile).
Onbrief is a research writer for work. Keep that list off `thesisgenerator.io`.

`kaynel.solutions` is already verified on Agent 2 and in the open-only warming pool.

When a dedicated `onbrief.*` domain is verified on ZeptoMail, pin
`ZEPTOMAIL_ONBRIEF_SENDER_EMAIL` and move Off the kaynel catch-all.

## Product voice

Onbrief writes **briefs, memos, and research reports for work**. The emails
must sound like a calm desk — not a study app.

| Say | Don't say |
|---|---|
| brief, memo, report, desk, export PDF | thesis, essay, homework, assignment, class |
| Generate all, workspace, desk | Generate Thesis, Humanize, turn it in |
| unlock writing / export | unlimited chapters / AI-detection bypass |

Signoff: **Onbrief** (not Ana / Alex / Thesis Generator Team).

## Layers

| Layer | Path | Notes |
|-------|------|--------|
| Welcome | `check-new-users` → `welcome-email` | Auth users with a real email only |
| Instant | Flutter `InstantEmailService` → Edge Functions | First brief complete + quota hit |
| Behavioral | `scripts/onbrief_orchestrator.py` | Cron via `retention-emails.yml` |
| Guests | skipped | Anonymous / empty email never mailed |

## Flutter marketing snapshot (`users/{uid}`)

Written by `FirebaseUserService.ensureUserMirrored` + `StreakService`:

```
email
language
createdAt
lastSignInAt
usage.lastOpenMs
usage.freeChapterUsed / freeChapterUsedAt
plan.workType / topic / deadline
subscription.status
streak.current / last_active_at
```

Briefs live in `theses/{id}` (legacy collection name from the fork):
`status`, `topic`, `title`, `progressPercentage`, `lastModified`, `completedAt`, `userId`.

Without `lastOpenMs`, abandoned will not fire (by design).
Without `email`, welcome + every sender skip the user.

## Senders (Hooked)

Templates live in `cache/onbrief_templates/` (English v1). Warm with
`python scripts/onbrief_orchestrator.py --warm`.

| Sender | Trigger | Lever |
|--------|---------|--------|
| Welcome | First email on the Auth account | External trigger — lock in one brief |
| Instant `onbrief-complete-email` | `theses.status == completed`, once | Variable reward → export PDF |
| Instant `onbrief-quota-hit-email` | `usage.freeChapterUsed`, once | Monetization while paywall is open |
| `onbrief_first_complete` | Same event, batch backup | Variable reward |
| `onbrief_quota_hit` | 24h / 72h / 7d if instant missed | Monetization |
| `onbrief_stuck_on_outline` | draft, progress < 20, inactive ≥24h | Funnel rescue — tap Generate all |
| `onbrief_abandoned_brief` | unfinished, 2d / 5d / 10d | External trigger |
| `onbrief_deadline` | `plan.deadline` − today ∈ {7, 3, 1, 0} | Urgency |

Skip for v1: 30-day drip, founder story, streak mail, weekly recap, crosspromo into Onbrief.

Daily cap: `ONBRIEF_DAILY_SEND_CAP` (default 30) plus shared `KAYNEL_DAILY_SEND_CAP` (50).

## DNS / deploy

Webhook (already on Agent 2):

`https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/zeptomail-webhook`

1. Confirm `FIREBASE_REFRESH_TOKEN` can list Auth users on `onbrief-185c5`
2. Deploy Supabase `welcome-email` + `check-new-users` + `zeptomail-webhook`
   + `onbrief-complete-email` + `onbrief-quota-hit-email`
3. Merge marketing-tool — retention cron runs `onbrief_orchestrator.py`
4. Ship the Flutter InstantEmailService + `usage.lastOpenMs` mirror
5. `python scripts/onbrief_orchestrator.py --dry-run` once the token is set
