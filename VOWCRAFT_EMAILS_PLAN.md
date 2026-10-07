# Vowcraft emails (ZeptoMail)

Firebase: `vowcraft-e4498`  
From: `hello@kaynel.solutions` (display **Vowcraft**) — Agent 2  
App tag: `vowcraft`  
CTA: `com.vowcraft.wedding.speech`

## Doctrine (2026-10)

Value / tip first (finish → rehearse minute one aloud). Soft continue CTA.
Unlock only as P.S. on quota. No trial ending. No founder blast.

## Warm cache

```bash
cd marketing-tool
python scripts/vowcraft_orchestrator.py --warm
# → cache/vowcraft_templates/*.json
```

## Layers

| Layer | Path |
|-------|------|
| Welcome | `check-new-users` → `welcome-email` |
| Behavioral | `scripts/vowcraft_orchestrator.py` via `retention-emails.yml` |

## Senders (Hooked)

| Kind | Trigger |
|------|---------|
| `welcome` | New signup |
| `vowcraft_quota_hit` | Free draft used — 24h / 72h / 7d |
| `vowcraft_speech_ready` | Draft ready / completed — rehearse tip |
| `vowcraft_abandoned_speech` | Draft idle 2d / 5d / 10d |
| `vowcraft_rehearse` | Has draft, quiet ≥1d — tip to say minute one aloud |

Tags: `app=vowcraft`, `kind`, `language`, optional `stage`.

Daily cap: `VOWCRAFT_DAILY_SEND_CAP` (default 30) + shared kaynel cap.

## Wiring checklist

- [x] `scripts/vowcraft_templates.py` + warm → `cache/vowcraft_templates/`
- [x] `scripts/vowcraft_email_chrome.py` / `vowcraft_send.py` / `vowcraft_orchestrator.py`
- [x] Allowlist `vowcraft` on kaynel.solutions (TS + Python)
- [x] Firebase loader + welcome APP_CONFIG + check-new-users
- [x] Behavioral senders + GitHub Actions cron (after Onbrief)
- [x] `vowcraft_users_loader.py` (speeches, fallback theses)
