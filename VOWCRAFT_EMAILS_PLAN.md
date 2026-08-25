# Vowcraft emails (ZeptoMail)

Firebase: `vowcraft-e4498`  
From: `hello@kaynel.solutions` (display **Vowcraft**) — Agent 2  
App tag: `vowcraft`  
CTA: `com.vowcraft.wedding.speech`

## Warm cache

```bash
cd marketing-tool
python scripts/vowcraft_orchestrator.py --warm
# → cache/vowcraft_templates/*.json
```

## Templates (Hooked)

| Kind | Trigger |
|------|---------|
| `welcome` | New signup |
| `speech_ready` | Draft generated |
| `quota_hit` | Free draft used (instant / 24h / 72h / 7d) |
| `abandoned_speech` | Draft idle 2d / 5d / 10d |
| `rehearse` | Investment nudge |

## Wiring checklist

- [x] `scripts/vowcraft_templates.py` + warm → `cache/vowcraft_templates/`
- [x] `scripts/vowcraft_email_chrome.py` / `vowcraft_send.py` / `vowcraft_orchestrator.py`
- [x] Allowlist `vowcraft` on kaynel.solutions (TS + Python)
- [x] Firebase loader + welcome APP_CONFIG + check-new-users
- [ ] Wire behavioral senders + GitHub Actions cron (same pattern as Onbrief)
- [ ] Deploy Supabase `welcome-email` / `check-new-users` after merge
