# Predictify + Thesis Email Plan (2026-07-20)

Four-app email system: **no 30-day drip**. ZeptoMail on **thesisgenerator.io** (Thesis)
and **predictifyfootball.com** (Predictify Soccer, NBA, Horse).

## Layers (every app)

| Layer | When | Max |
|-------|------|-----|
| Welcome | Signup | Once |
| Behavioral | Active users (picks, deadlines, streaks) | Event + cooldown |
| Founder story #1 | ≥14d inactive, no behavioral match | Once |
| Founder story #2 | ≥7d after #1, still inactive | Once |

## Soccer (`Predictify`)

- **Welcome:** `check-new-users` → `welcome-email`
- **Behavioral (P0/P1):** `streak_saver`, `match_day`, `welcome` backup, `win_back`
- **Hourly:** `streak_saver` only (`predictify-streak-hourly.yml`)
- **Lapsed:** `founder_story_soccer` → `founder_story_soccer_v2` (orchestrator fallback)
- **Templates:** `scripts/predictify_v2/templates/founder_story_soccer_*.json`
- **Backfill:** `python scripts/founder_story_predictify_sender.py --backfill`

## NBA (`Predictify: NBA AI`)

- **Welcome + behavioral:** `predictify-nba-emails.yml` (v2 NBA profile)
- **Lapsed:** `founder_story_nba` → `founder_story_nba_v2`
- **Templates:** `scripts/predictify_v2/templates_nba/founder_story_nba_*.json`
- **Env:** `PREDICTIFY_APP_NAME`, `PREDICTIFY_FIREBASE_PROJECT_ID=nba-predictify`, `PREDICTIFY_TEMPLATES_DIR=templates_nba`

## Horse (`Predictify: Horse Racing AI`)

- **Welcome:** `check-new-users`
- **Daily lapsed:** `founder_story_horse_sender.py` (v2 orchestrator, cap 50)
- **Backfill:** workflow mode `founder-story-horse` or `--backfill`
- **Templates:** `scripts/predictify_v2/templates/founder_story_horse_*.json`

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
| `founder-story` | Soccer v1 backfill |
| `founder-story-non-sub` | Soccer v2 to free users |
| `founder-story-horse` | Horse v1 backfill |
| `thesis-founder-story` | Thesis v1 backfill |
| `thesis-founder-story-2` | Thesis v2 backfill |

Legacy `founder_story_wc2026` sends count as v1 received (dedup).
