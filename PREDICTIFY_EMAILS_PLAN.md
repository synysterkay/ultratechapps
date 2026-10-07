# Predictify + Thesis Email Plan (2026-10 value-first)

Four-app email system: **no 30-day drip**. ZeptoMail on **thesisgenerator.io** (Thesis)
and **predictifyfootball.com** (Predictify Soccer, NBA, Tennis, Horse).

## Doctrine

Value / tip first. One CTA = open pick / continue. Soft Pro only in P.S. on
hot-week / paywall moments — never “Start 7-day Pro trial” as the primary CTA.
No trial-ending countdown. Price-change promo blasts are **not** the conversion
core (P0/P1 behavioral is).

## Layers (every app)

| Layer | When | Max |
|-------|------|-----|
| Welcome | Signup | Once |
| Behavioral | Active users (picks, deadlines, streaks) | Event + cooldown |
| Founder story #1 | ≥14d inactive, no behavioral match | Once (lapsed) |
| Founder story #2 | ≥7d after #1, still inactive | Once (lapsed) |

## Soccer (`Predictify`)

- **Welcome:** `check-new-users` → `welcome-email`
- **Behavioral (P0/P1):** `streak_saver`, `match_day`, `welcome` backup, `win_back`
- **Value (ready, not in p0p1 default):** `upgrade_after_hot_week` (tip + soft Pro P.S.), `weekly_recap`
- **Hourly:** `streak_saver` only (`predictify-streak-hourly.yml`)
- **Lapsed:** `founder_story_soccer` → `founder_story_soccer_v2` (orchestrator fallback)
- **Templates:** `scripts/predictify_v2/templates/`
- **Bulk backfill:** **FROZEN** (value-first). Daily FS1/FS2 and workflow modes no-op. Override: `FOUNDER_STORY_BULK_UNFREEZE=1`.

## NBA (`Predictify: NBA AI`)

- **Welcome + behavioral:** `predictify-nba-emails.yml` (v2 NBA profile)
- **Lapsed:** `founder_story_nba` → `founder_story_nba_v2` (v2 orchestrator only)
- **Bulk backfill:** **FROZEN** (same as Soccer)
- **Templates:** `scripts/predictify_v2/templates_nba/founder_story_nba_*.json`
- **Env:** `PREDICTIFY_APP_NAME`, `PREDICTIFY_FIREBASE_PROJECT_ID=nba-predictify`, `PREDICTIFY_TEMPLATES_DIR=templates_nba`

## Tennis (`Predictify: Tennis AI`)

- **Welcome + behavioral:** `predictify-tennis-emails.yml` (v2 Tennis profile)
- **Lapsed:** `founder_story_tennis` → `founder_story_tennis_v2` (v2 orchestrator only)
- **Bulk backfill:** **FROZEN** (same as Soccer)
- **Templates:** `scripts/predictify_v2/templates_tennis/founder_story_tennis_*.json`
- **Instant:** `predictify-tennis-first-win-email`, `predictify-tennis-streak-broken-email`, `predictify-tennis-paywall-hit-email`, `predictify-tennis-leaderboard-email`
- **Env:** `PREDICTIFY_APP_NAME='Predictify: Tennis AI'`, `PREDICTIFY_FIREBASE_PROJECT_ID=tenis-b5d4e`, `PREDICTIFY_TEMPLATES_DIR=templates_tennis`
- **From:** `hello@predictifyfootball.com` (same ZeptoMail domain as Soccer/NBA)
- **GitHub secrets:** `TENNIS_PREDICTIFY_SUPABASE_URL` / `TENNIS_PREDICTIFY_SUPABASE_SERVICE_ROLE_KEY` (app project `ozkenbwfdkmtmfvddbti`)

## Horse (`Predictify: Horse Racing AI`)

- **Welcome:** `check-new-users`
- **Value tips:** `horse_race_day_tip_sender.py` (Auth export; stages early / race_day / process)
- **Daily lapsed:** `founder_story_horse_sender.py` (v2 orchestrator, cap 50)
- **Bulk backfill:** **FROZEN** (value-first). Workflow mode `founder-story-horse` no-ops.
- **Templates:** `scripts/predictify_v2/templates/founder_story_horse_*.json`, `race_day_tip_en.json`
- **CTA doctrine:** tip → open today's card / strongest pick. Soft Pro never as primary CTA.

## Thesis Generator

- **Welcome:** `check-new-users` (thesis-generator-web)
- **Behavioral:** `thesis_orchestrator.py` — 6 P0/P1 senders
- **Lapsed catch-up:** founder story v1 + v2 at end of orchestrator (50/day each, lapsed only)
- **Templates:** `cache/thesis_templates/founder_story_thesis_*.json`

## Env vars (GitHub)

```
EMAIL_PROVIDER=zeptomail
PREDICTIFY_DISABLE_FOUNDER_FALLBACK=0
FOUNDER_STORY_LAPSED_DAYS=14
FOUNDER_STORY_V2_GAP_DAYS=7
PREDICTIFY_ACTIVE_TRIGGERS=p0p1
V2_DAILY_SEND_CAP=250          # Soccer
FOUNDER_STORY_HORSE_DAILY_CAP=50
FOUNDER_STORY_THESIS_DAILY_CAP=50
```

## Manual workflow modes

| Mode | Action |
|------|--------|
| `founder-story` | Frozen (value-first) |
| `founder-story-non-sub` | Frozen (value-first) |
| `founder-story-horse` | Frozen (value-first) |
| `thesis-founder-story` | Frozen (value-first) |
| `thesis-founder-story-2` | Frozen (value-first) |

Legacy `founder_story_wc2026` sends count as v1 received (dedup).
