# Kinbound Email System

Firebase project: `parents-ai-e49a8`  
App Store: [Kinbound](https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071)  
Supabase: `jimcdgkwbbrxgakingtg`

## Architecture

```
Flutter (Kinbound)
  ├─ Firestore users/{uid}     → batch senders (cron via kinbound_orchestrator.py)
  └─ Supabase Edge Functions   → instant emails (Resend, deduped in instant_emails_sent)
```

**Privacy:** Child names, chat, memories, and journal never sync. Only locale, streak, struggle id, counts, subscription, and email (after account link).

## Flutter hooks

| Event | Service | Firestore | Instant email |
|-------|---------|-----------|---------------|
| App launch | `MarketingSyncService.recordAppOpen()` | `usage.lastOpenMs` | — |
| Prefs change | `MarketingSyncService.sync()` | full snapshot | — |
| Onboarding done + love/good reaction | `onOnboardingComplete()` | `onboarding.*` | `kinbound-first-script-email` |
| Google/Apple link | `onAccountLinked()` | `email` | `kinbound-account-linked-email` |
| Copilot limit hit | `onCopilotLimitHit()` | `usage.*` | `kinbound-copilot-limit-email` |
| Premium change | `PremiumNotifier` → `sync()` | `subscription.*` | — |

Guests without linked email are skipped by batch senders (no `email` in Firestore).

## Batch senders (`scripts/kinbound_orchestrator.py`)

| Sender | Trigger | Dedup |
|--------|---------|-------|
| `kinbound_struggle_rescue_sender` | `primaryConcernId` set, onboarding done, inactive ≥1d, free | once per uid |
| `kinbound_streak_milestone_sender` | streak 3 / 7 / 14 / 30 | once per stage |
| `kinbound_streak_at_risk_sender` | streak ≥2, no check-in today, after 18:00 UTC | once per uid per day |
| `kinbound_abandoned_app_sender` | `lastOpenMs` ≥2/5/10d, free | once per stage |

## Instant Edge Functions

Deploy from `marketing-tool`:

```bash
supabase functions deploy kinbound-first-script-email
supabase functions deploy kinbound-copilot-limit-email
supabase functions deploy kinbound-account-linked-email
```

Welcome email: `welcome-email` + `check-new-users` already include `kinbound` / `parents-ai-e49a8`.

## Deploy checklist

1. **marketing-tool** — merge + push (CI runs `kinbound_orchestrator.py` on retention cron)
2. **Supabase** — deploy the three Kinbound edge functions above
3. **Kinbound IPA** — ship build with `marketing_constants.dart` + sync hooks
4. **Firebase** — ensure `parents-ai-e49a8` Auth export runs (welcome cron)

## Warm translations (optional)

```bash
cd marketing-tool
python scripts/kinbound_orchestrator.py --warm
```
