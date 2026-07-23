# Predictify Crypto Email Plan

ZeptoMail retention system for **Predictify Crypto** (`app` tag: `predictify_crypto`),
mirrored from Predictify Soccer. **No 30-day drip.**

## Layers

| Layer | When | Max |
|-------|------|-----|
| Welcome | Signup (email / first profile create) | Once |
| Behavioral P0/P1 | Active users (streak, win-back, journal) | Event + cooldown |
| Instant | Peak moments from the Flutter app | Once per kind (server dedup) |
| Founder story #1 | ≥14d inactive, no behavioral match | Once |
| Founder story #2 | ≥7d after #1, still inactive | Once |

## Instant emails (Flutter → Edge Functions)

Marketing Supabase: `https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/`

| Kind | Endpoint | Trigger in app |
|------|----------|----------------|
| `welcome` | `welcome-email` (`app_id=predictify_crypto`) | First user profile create |
| `first_analysis` | `predictify-crypto-first-analysis-email` | First successful chart analysis |
| `paywall_hit` | `predictify-crypto-paywall-hit-email` | `campaign_trigger` paywall shown |
| `streak_broken` | `predictify-crypto-streak-broken-email` | Analysis streak ≥3 → resets to 1 |

## Behavioral (cron — Week 2+)

Priority (first match wins), see `scripts/predictify_crypto/triggers.py`:

1. `streak_saver` — streak ≥3, 18–30h since last analysis  
2. `welcome_backup` — 0 analyses, day 1–3  
3. `journal_pending` — open setups without win/loss  
4. `win_back` — 5–14d quiet, ≥1 analysis  

Templates: `scripts/predictify_crypto/templates/`

## Founder story (lapsed)

- `founder_story_crypto` / `founder_story_crypto_v2`  
- Sender stub: `scripts/founder_story_crypto_sender.py`  
- Caps: `FOUNDER_STORY_CRYPTO_DAILY_CAP` (default 50)

## Env

```
EMAIL_PROVIDER=zeptomail
ZEPTOMAIL_API_KEY=...
PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL=hello@predictifyfootball.com   # or dedicated crypto domain when verified
FOUNDER_STORY_LAPSED_DAYS=14
FOUNDER_STORY_V2_GAP_DAYS=7
FOUNDER_STORY_CRYPTO_DAILY_CAP=50
```

## Hooked model mapping

| Hooked | Email |
|--------|-------|
| Trigger | streak_saver, watchlist (later), paywall_hit |
| Action | CTA → open Command / scan chart |
| Variable reward | first_analysis, high-confidence (later) |
| Investment | journal_pending, streak_broken, founder story |

## Flutter

`lib/services/instant_email_service.dart` — fire-and-forget POSTs with local + server dedup.

Call sites:
- Welcome → `AuthService._createUserProfile` (new profile only)
- First analysis → `ProcessingScreen` after successful save
- Paywall → `SuperwallConfig.didPresentPaywall`
- Streak broken → `StreakService.recordAnalysis` when prior ≥3 → 1

Welcome is also covered by `check-new-users` cron for Firebase project `cryptopredictify`; `welcome-email` upserts `welcomed_users` so Flutter + cron never double-send.
