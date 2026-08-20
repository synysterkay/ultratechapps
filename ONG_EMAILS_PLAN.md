# ONG Email System

Firebase project: `sealed-cce0a`  
Bundle ID: `app.ong.predict`  
Landing: https://sealed-cce0a.web.app  
Sender: **ONG** `<hello@kaynel.solutions>`  
ZeptoMail: **Agent 2** (same agent as breakuprelief / passedai — not Agent 1)

No 30-day drip. Hooked-model behavioral mail only — Thesis / Predictify / Kinbound playbook.

## Why Agent 2 + kaynel.solutions

Agent 1 is thesis + Predictify (high volume). ONG is a social invite loop.
Keep that complaint profile off thesis/sports reputation.

`kaynel.solutions` is already in the open-only warming pool (`testkaynel@gmail.com`).

Leftover apps that are not on thesis / predictify / breakuprelief also send from
`hello@kaynel.solutions` (welcome + existing behavioral only). Shared cap:
`KAYNEL_DAILY_SEND_CAP` (default 50). Health gate skips the domain if status is red.

## Layers

| Layer | Path | Notes |
|-------|------|--------|
| Welcome | `check-new-users` → `welcome-email` | Auth users with a real email only |
| Behavioral | `scripts/ong_orchestrator.py` | Cron via `retention-emails.yml` |
| Founder story | `ong_founder_story_sender` | ≥14d inactive, once |
| Guests | skipped | Anonymous / `guest*` usernames have no email |

## Flutter marketing snapshot (`users/{uid}`)

Written by `MarketingSync` in the ONG app (merge, never email guests):

```
email
language
createdAt
notifyInvites / notifyReveals / notifyStreaks
usage.lastOpenMs
usage.predictionsCreated
usage.answersCount
usage.unansweredInviteCount
usage.unopenedRevealCount
usage.namesGateHit
usage.streak
subscription.isPro
```

Without `lastOpenMs`, abandoned + founder story will not fire (by design).
Without `unopenedRevealCount` / `namesGateHit`, those senders no-op until the app writes them.

## Senders (Hooked)

Templates live in `cache/ong_templates/` (English). Warm with
`python scripts/ong_orchestrator.py --warm`.

| Sender | Trigger | Lever |
|--------|---------|--------|
| Welcome | First email on the Auth account | External trigger — lock in one |
| `ong_waiting_on_you` | `unansweredInviteCount > 0`, inactive ≥1d / 3d | External trigger |
| `ong_reveal_live` | `unopenedRevealCount > 0`, once | Variable reward |
| `ong_first_lock` | `predictionsCreated ≥ 1`, once | Variable reward + investment (share sheet stays in-app) |
| `ong_streak_at_risk` | streak ≥ 3, no open today, after 18:00 UTC | Internal trigger |
| `ong_streak_milestone` | streak 3 / 7 / 14 / 30 | Variable reward |
| `ong_abandoned_app` | lastOpen ≥ 2 / 5 / 10d, free | Funnel rescue |
| `ong_weekly_recap` | Sunday UTC, active in last 14d | Investment |
| `ong_pro_gate` | `namesGateHit`, still free, once | Monetization |
| `ong_founder_story` | lastOpen ≥ 14d, once | Lapsed catch-up (signoff Alex) |

Skip for v1: monthly stats, long winback, cold “text 3 friends” in email, crosspromo into ONG.

Daily cap: `ONG_DAILY_SEND_CAP` (default 30) plus shared `KAYNEL_DAILY_SEND_CAP` (50).

## Voice

Short. Friend-group. Same as the app: lock it in, nobody sees yet, then
you find out who called it. Not sports-analyst, not academic.

Email chrome: white canvas, black ONG wordmark + red wax seal
(`assets/ong/icon-email.png`), NGL-style.

## DNS (Hostinger / Zepto Agent 2)

Add `kaynel.solutions` on Agent 2 if it is not already verified there.
Copy SPF, DKIM, bounce CNAME from Zepto. Point the Agent 2 webhook at:

`https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/zeptomail-webhook`

## Deploy checklist

1. Verify `kaynel.solutions` on ZeptoMail Agent 2
2. Point Agent 2 hard-bounce webhook at the Supabase endpoint
3. Set `ZEPTOMAIL_ONG_SENDER_EMAIL=hello@kaynel.solutions` (optional; defaulted)
4. Merge marketing-tool — retention cron runs `ong_orchestrator.py`
5. Deploy Supabase `welcome-email` + `check-new-users` + `zeptomail-webhook`
6. Ship ONG with marketing sync (`lastOpenMs`, skip guests)
7. `python scripts/ong_orchestrator.py --dry-run` once token is set
