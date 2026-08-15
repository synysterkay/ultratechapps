# Crosspromotion — Thesis Generator (phase 1)

Owned-list cross-sell from portfolio app users into **Thesis Generator** installs.

## What it does

1. Builds a pool of Auth emails from all Firebase apps **except** Thesis Generator.
2. Enrolls them in a **5-email sequence** (days 0 / 2 / 5 / 10 / 14).
3. Sends via **SMTP2GO** from the health-aware pool, preferring **`hello@kaynel.solutions`** (Alex).
4. Falls back to other green pool senders (`passedai.io`, `breakuprelief.com`) if kaynel is yellow/red.
5. Skips the run entirely if no green/unknown sender is available.

Product lifecycle mail for Thesis stays on ZeptoMail / `thesisgenerator.io`. Crosspromo never uses that pin.

## Sequence (EN)

| Stage | Day | Kind tag | Job |
|-------|-----|----------|-----|
| e1 | 0 | `crosspromo_thesis_e1` | Curiosity hook |
| e2 | 2 | `crosspromo_thesis_e2` | 5-minute micro-win |
| e3 | 5 | `crosspromo_thesis_e3` | Social proof |
| e4 | 10 | `crosspromo_thesis_e4` | Objection crush |
| e5 | 14 | `crosspromo_thesis_e5` | Soft close / breakup |

Copy lives in `scripts/crosspromo_thesis_sender.py` → `EN_SOURCES`.

## Commands

```bash
# Status + pool stats
python3 scripts/crosspromo_orchestrator.py --status

# Dry-run (no sends)
python3 scripts/crosspromo_orchestrator.py --dry-run --limit 20

# Cache EN templates (and optional market-adapt localization)
python3 scripts/crosspromo_thesis_sender.py --warm
python3 scripts/crosspromo_thesis_sender.py --warm --adapt   # full-content rewrite, not word-by-word

# Live send (SMTP2GO_API_KEY required)
CROSSPROMO_DAILY_CAP=50 python3 scripts/crosspromo_orchestrator.py
```

## CI

- Workflow: `.github/workflows/retention-emails.yml`
- Modes: default Mon–Sat send (after other orchestrators), or `workflow_dispatch` mode **`crosspromo`**
- Env: `CROSSPROMO_ENABLED=1`, `CROSSPROMO_DAILY_CAP=150`, `CROSSPROMO_ENROLL_CAP=150`
- State persisted: `cache/crosspromo_thesis_state.json`

## Tags (analytics)

- `app=crosspromo`
- `system=crosspromotion`
- `target=thesis`
- `kind=crosspromo_thesis_e{N}`
- `stage=e{N}`
- `language=…`

## Localization

- Send path: `get_localized(..., allow_api=False)` — uses cache or falls back to EN.
- Later: `--warm --adapt` writes market-adapted JSON to `cache/thesis_templates/crosspromo_thesis_e{N}_{lang}.json`.
- Language resolution: Firestore language caches for multilingual apps → else `en`.

## Exit / safety

- Suppressions and bounce list always win.
- Thesis Auth emails never enrolled.
- After e5 → `completed_at`; no re-enroll for **90 days**.
- Daily send cap default **150**; mid-run health re-check every 50 sends.
- Warming: `kaynel.solutions` added to `config/warming_config.json`.

## Files

| Path | Role |
|------|------|
| `scripts/crosspromo_pool.py` | Multi-app pool + affinity |
| `scripts/crosspromo_thesis_sender.py` | Sequence + send |
| `scripts/crosspromo_orchestrator.py` | Entrypoint |
| `cache/crosspromo_thesis_state.json` | Enrollment / stage state |
| `scripts/deliverability_monitor.py` | `pick_healthy_sender(prefer=kaynel)` |
| `scripts/thesis_template_translator.py` | `mode='adapt'` warm |

## Later phases

- Same orchestrator + new `EN_SOURCES` packs for Predictify / other targets.
- Hand-authored market templates or bulk `--warm --adapt`.
- Engaged-first filter (opened/clicked in last 30d) once volume is stable.
