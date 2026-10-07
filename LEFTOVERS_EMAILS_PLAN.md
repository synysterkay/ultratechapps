# Leftover apps — welcome-only (value + soft CTA)

ZeptoMail **Agent 2** via `kaynel.solutions` (same pool as ONG / Onbrief).

## Doctrine

- **Welcome only** (Supabase `check-new-users` → `welcome-email`). No 30-day drip.
- Tip / value first; CTA = open the core action (boost / record / chat).
- Free users only for any future tip senders; do not add founder bulk.

## Apps

| Firebase project | `app_id` | Welcome |
|------------------|----------|---------|
| `volume-booster-2f7bf` | `volume_booster` | Yes |
| `boyfriend-ai-f1e5e` | `ai_boyfriend` | Yes (Supabase; Spark — no CF welcome) |
| `apb412---ai-girlfriend-app` | `ai_girlfriend` | Yes (Supabase; Spark) |
| `audio-recorder-microphone` | `smart_notes` | Yes |

Listed in `ZEPTOMAIL_PROJECT_IDS` + `KAYNEL_WELCOME_APP_IDS` in `check-new-users`.

## SoulPlan

Uses **Supabase only** (`soulplan-dateplanner` → `soulplan`), Agent 2 / breakuprelief. Not a leftover — see `BREAKUP_EMAILS_PLAN.md`.
