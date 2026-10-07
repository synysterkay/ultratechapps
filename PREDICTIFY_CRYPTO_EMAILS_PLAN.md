# Predictify Crypto Email Plan (2026-10 value-first)

ZeptoMail retention for **Predictify Crypto** (`app` tag: `predictify_crypto`),
mirrored from Predictify Soccer doctrine. **No 30-day drip. No trial_ending.**

## Doctrine

Value / tip first. One CTA = scan one chart / open setup. Soft unlock only in
P.S. on paywall moments — never “Unlock AI analysis” / subscribe as primary CTA.
Founder bulk backfill is **frozen**; lapsed catch-up only (≥14d, small daily cap).

## Layers

| Layer | When | Max |
|-------|------|-----|
| Welcome | Signup (email / first profile create) | Once |
| Behavioral tips | Auth-export age bands (until Firestore activity) | Once per stage |
| Instant | Peak moments from the Flutter app | Once per kind (server dedup) |
| Founder story #1 | ≥14d signup, no prior founder send | Once (lapsed, cap 50/day) |
| Founder story #2 | Template ready; wire after activity loader | Once (later) |

## Instant emails (Flutter → Edge Functions)

Marketing Supabase: `https://jimcdgkwbbrxgakingtg.supabase.co/functions/v1/`

| Kind | Endpoint | Trigger in app |
|------|----------|----------------|
| `welcome` | `welcome-email` (`app_id=predictify_crypto`) | First user profile create |
| `first_analysis` | `predictify-crypto-first-analysis-email` | First successful chart analysis |
| `paywall_hit` | `predictify-crypto-paywall-hit-email` | `campaign_trigger` paywall shown |
| `streak_broken` | `predictify-crypto-streak-broken-email` | Analysis streak ≥3 → resets to 1 |

Paywall / streak copy is tip-first (“write the stop”, “scan one chart”).

## Cron (retention-emails.yml)

`crypto_orchestrator.py`:

1. `crypto_tip_sender.py` — stages from Auth export  
   - `welcome_backup` (day 1–3)  
   - `analysis_tip` (day 4–21)  
   - `win_back` (day 22+)  
2. `founder_story_crypto_sender.py` — lapsed ≥14d, once-ever, cap 50  

Templates: `scripts/predictify_crypto/templates/`  
(`streak_saver`, `journal_pending` reserved for Firestore activity loader)

## Founder story (lapsed)

- `founder_story_crypto` / `founder_story_crypto_v2`
- Caps: `FOUNDER_STORY_CRYPTO_DAILY_CAP` (default 50)
- `--backfill` frozen

## Env

```
EMAIL_PROVIDER=zeptomail
ZEPTOMAIL_API_KEY=...
PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL=hello@predictifyfootball.com
FOUNDER_STORY_LAPSED_DAYS=14
FOUNDER_STORY_CRYPTO_DAILY_CAP=50
CRYPTO_TIP_DAILY_CAP=40
```

Auth export: `firebase_exports/cryptopredictify_fresh.json` (project `cryptopredictify`).

## Hooked model mapping

| Hooked | Email |
|--------|-------|
| Trigger | streak_saver, paywall_hit (tip) |
| Action | CTA → open Command / scan chart |
| Variable reward | first_analysis |
| Investment | journal_pending, streak_broken, founder story, analysis_tip |

## Flutter

`lib/services/instant_email_service.dart` — fire-and-forget POSTs with local + server dedup.

Welcome is also covered by `check-new-users` cron for Firebase project `cryptopredictify`;
`welcome-email` upserts `welcomed_users` so Flutter + cron never double-send.
