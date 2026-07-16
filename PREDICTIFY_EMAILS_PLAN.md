# Predictify — Retention Email Plan (Soccer, NBA, Horse)

End-to-end design for Predictify Soccer, NBA, and Horse Racing email systems.
**30-email drip disabled** as of 2026-07-16. All sends use **ZeptoMail** on
**predictifyfootball.com** (Thesis stays on **thesisgenerator.io**).

---

## 1. Architecture

```
Flutter app              Firestore / Supabase           Marketing tool
─────────────            ────────────────────           ──────────────
signup            ───▶   users.{uid}              ───▶  check-new-users → welcome-email
pick / streak     ───▶   activity + picks         ───▶  predictify_v2 (scheduled)
app events        ───▶   webhooks                 ───▶  Supabase instant emails
```

| Layer | Soccer | NBA | Horse |
|-------|--------|-----|-------|
| Welcome | Supabase cron | v2 `welcome` trigger | Supabase cron |
| 30-email drip | **OFF** | **OFF** (never enrolled) | **OFF** |
| Behavioral | `predictify_v2` + hourly streak | `predictify_v2` (NBA profile) | Welcome only (Phase B TBD) |
| Instant | streak-broken, first-win, paywall | NBA edge functions | — |
| Domain | hello@predictifyfootball.com | hello@predictifyfootball.com | hello@predictifyfootball.com |
| Provider | ZeptoMail | ZeptoMail | ZeptoMail |

---

## 2. Active behavioral triggers (P0/P1)

Set via `PREDICTIFY_ACTIVE_TRIGGERS=p0p1` (default). Founder-story fallback
disabled via `PREDICTIFY_DISABLE_FOUNDER_FALLBACK=1`.

| Priority | Trigger | When | App |
|----------|---------|------|-----|
| **P0** | `streak_saver` | 18–30h since last pick, streak ≥3 | Soccer (+ hourly workflow) |
| **P0** | `match_day` | Followed league kickoff in 2–12h | Soccer, NBA |
| **P0** | Supabase instant | streak broken, first win, paywall | Soccer, NBA |
| **P1** | `welcome` | 0 picks, has today's top pick | Soccer, NBA (backup) |
| **P1** | `win_back` | 5–14 days lapsed, had picks | Soccer, NBA |
| **P1** | `upgrade_after_hot_week` | Free, ≥5 picks, ≥60% accuracy, Mon/Tue | Soccer, NBA |

### Deferred (do not send until deliverability stable)

- `founder_story_wc2026` (manual workflow only)
- `weekly_recap`, `referral_invite`, `community_invite`
- `owner_*`, `pro_owner_pitch`, `pro_power_tip`, `winback_lapsed_pro`
- `login_streak_reward`

---

## 3. Volume caps

| Workflow | Cap / run | Runs/day | Max/day |
|----------|-----------|----------|---------|
| Soccer v2 (retention-emails) | 250 | 2 | ~500 |
| Soccer streak hourly | 75 | 24 | ~75 effective* |
| NBA v2 | 150 | 2 | ~300 |
| Welcome (Soccer + Horse) | 15 | ~288 cron slots | 300/app/day |
| Welcome (Thesis, separate) | 10 | — | 100/day |

\*Hourly run uses `PREDICTIFY_ONLY_KINDS=streak_saver`; cooldown is 5 days per user.

---

## 4. Workflows

| Workflow | Purpose |
|----------|---------|
| `retention-emails.yml` | Other apps drip + **Soccer v2 pass** (first step in app_retention_emailer) + Thesis orchestrator |
| `predictify-nba-emails.yml` | NBA behavioral v2 |
| `predictify-streak-hourly.yml` | Soccer streak_saver only |

Manual modes still available: `founder-story`, `streak`, `matchday` (legacy v1 — prefer v2).

---

## 5. Env vars (GitHub + Supabase)

```
EMAIL_PROVIDER=zeptomail
ZEPTOMAIL_API_KEY=...

# Thesis (retention-emails thesis step + check-new-users thesis project)
ZEPTOMAIL_THESIS_SENDER_EMAIL=hello@thesisgenerator.io
ZEPTOMAIL_DAILY_CAP=100

# Predictify family (Soccer, NBA, Horse welcome + v2 + instant)
PREDICTIFY_ZEPTOMAIL_SENDER_EMAIL=hello@predictifyfootball.com
PREDICTIFY_ZEPTOMAIL_SENDER_NAME=Predictify
PREDICTIFY_ZEPTOMAIL_DAILY_CAP=300
PREDICTIFY_ACTIVE_TRIGGERS=p0p1
PREDICTIFY_DISABLE_FOUNDER_FALLBACK=1
V2_DAILY_SEND_CAP=250
```

NBA workflow additionally sets:
```
PREDICTIFY_APP_NAME=Predictify: NBA AI
PREDICTIFY_FIREBASE_PROJECT_ID=nba-predictify
PREDICTIFY_TEMPLATES_DIR=templates_nba
```

Hourly streak workflow additionally sets:
```
PREDICTIFY_ONLY_KINDS=streak_saver
```

---

## 6. Horse Racing — Phase B (not yet built)

611 users. Drip removed. Welcome via `check-new-users` → `welcome-email`.

Next steps when Horse Firestore/Supabase pick data is confirmed:
1. Wire `predictify_v2` with Horse profile (like NBA)
2. Minimal triggers: `race_day`, `welcome_nudge`, `win_back`
3. Optional Supabase instant: first-win, paywall

---

## 7. Key files

| Purpose | Path |
|---------|------|
| v2 triggers | `scripts/predictify_v2/triggers.py` |
| v2 orchestrator | `scripts/predictify_v2/orchestrator.py` |
| Drip orchestrator (Predictify removed) | `scripts/app_retention_emailer.py` |
| ZeptoMail routing (Python) | `scripts/gmail_sender.py` |
| ZeptoMail routing (Edge) | `supabase/functions/_shared/email_transport.ts` |
| Welcome cron | `supabase/functions/check-new-users/index.ts` |
| Instant Soccer | `supabase/functions/predictify-*-email/` |
| Instant NBA | `supabase/functions/predictify-nba-*-email/` |
