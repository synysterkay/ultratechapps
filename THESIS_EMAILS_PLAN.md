# Thesis Generator — Retention Email Plan

End-to-end design for the Thesis Generator email system: who gets what, in
what language, when it fires, and which Hooked-model lever each one pulls.
**Other apps (Predictify, Volume Booster, Cupid AI, etc.) are untouched**
until their turn in the portfolio roadmap.

**Doctrine (2026-10):** value / advice first, one soft CTA, freemium conversion
via unfinished work + free-quota — **no `trial_ending`**. Founder-story bulk
backfill is frozen; lapsed catch-up only.

---

## 1. Architecture

```
Flutter app                Firestore                   Marketing tool
─────────────              ─────────                   ──────────────
mobile_auth_service ───▶  users.{uid}.language    ───▶ every sender (segmentation)
chapter_gate_service ──▶  users.{uid}.usage.*     ───▶ free_quota_hit_sender
superwall_service   ──▶  users.{uid}.subscription ───▶ paid filter (skip monetization)
subscription_sync   ──▶  users.{uid}.subscription ───▶ (web Stripe path)
background_gen      ──▶  theses.{id}.status       ───▶ first_thesis / abandoned / stuck / tips
```

### Shared modules (`scripts/`)
- `localize_phrase.py` — 20-language plural-aware phrase helper
- `thesis_template_translator.py` — DeepSeek translator → `cache/thesis_templates/`
- `thesis_email_chrome.py` — HTML renderer (RTL-aware)
- `thesis_users_loader.py` — Firestore loader
- `thesis_orchestrator.py` — single cron entry point

---

## 2. Active senders (orchestrator)

| # | Sender | Trigger | Stages | Role |
|---|---|---|---|---|
| 1 | `free_quota_hit_sender` | `usage.freeChapterUsed` + free user | h24 / h72 / d7 | Soft monetization (continue / unlock) |
| 2 | `first_thesis_complete_sender` | `theses.status == 'completed'`, once per user | 1 | Celebrate + revise tip + export CTA |
| 3 | `deadline_countdown_sender` | `plan.deadline` − today ∈ {14, 7, 3, 1, 0} | 5 | Real deadline advice |
| 4 | `abandoned_thesis_sender` | in_progress/generating/draft + inactive | 2d / 5d | Resume tips |
| 5 | `stuck_on_outline_sender` | draft progress 1–4% + 24h+ | 1 | Easiest-chapter tip |
| 6 | `writing_tip_sender` | free only — see stages below | outline / chapter / revise | Value tips |

Then: **founder story lapsed catch-up** (`FOUNDER_STORY_THESIS_DAILY_CAP`, default 50).
**Founder bulk backfill is frozen.**

### Writing tip stages (`kind=writing_tip`)

| Stage | When | CTA |
|---|---|---|
| `outline` | Free, has topic, 1–3d since signup, no outline/chapters yet | Start my outline |
| `chapter` | Outline ready (progress 1–4%), no chapters yet | Generate a chapter |
| `revise` | Chapter work started, quiet ≥2d | Open my latest chapter |

Tags: `app=thesis`, `kind=writing_tip`, `stage`, `language`, `paid=0`.

### Retired / not wired in orchestrator

| Sender | Status |
|---|---|
| `trial_ending_sender` | **Retired** — file kept, not in `SENDERS` |
| `winback_sender`, `streak_*`, `weekly_progress`, `cumulative_stats` | Exist on disk; **not** in cron |
| Founder story blast / price-change | Not conversion core |
| Founder daily backfill | **Frozen** in orchestrator |

---

## 3. Language coverage — all 20

`en, es, fr, ar, zh, hi, de, pt, it, ru, ja, ko, tr, nl, pl, sv, ro, id, th, vi`

```bash
python scripts/thesis_orchestrator.py --warm   # refresh=True for all active kinds
```

Requires `DEEPSEEK_API_KEY`. Until warm completes, missing langs fall back to EN
at send time (or translate on first send when the key is present in CI).

---

## 4. Segmentation matrix (active)

```
                    FREE                PAID                CHURNED
new (1–3d)          welcome + writing_tip_outline   thank-you*   —
outline stuck       stuck_on_outline / tip_chapter  same tip*    —
in-progress quiet   abandoned_thesis                abandoned    —
chapter quiet       writing_tip_revise              —            —
deadline hits       deadline (5)                    deadline     —
thesis complete     first_complete                  first_complete —
free chapter spent  free_quota_hit                  —            —
lapsed ≥14d         founder story catch-up (cap)    —            founder if eligible
```

`*` welcome via `check-new-users` → `welcome-email`. Paid users skip
`free_quota_hit` and `writing_tip` (free-only).

---

## 5. Copy doctrine

- Body = tip / advice / micro-win
- One CTA = continue work or export (not “Buy Pro” as subject)
- Soft unlock only on `free_quota_hit` (P.S. / continue framing)
- Never trial countdown urgency

---

## 6. Deploying

1. Flutter mirrors (`language`, `subscription`, `usage`) already required.
2. Set `DEEPSEEK_API_KEY` in GitHub Secrets.
3. Warm: `python scripts/thesis_orchestrator.py --warm` and commit
   `cache/thesis_templates/writing_tip_*` (+ refreshed kinds).
4. `retention-emails.yml` already runs `thesis_orchestrator.py`.
5. Monitor bounce / spam via deliverability + ZeptoMail.

---

## 7. Files of interest

```
scripts/
├── thesis_orchestrator.py
├── writing_tip_sender.py          # new value tips
├── free_quota_hit_sender.py
├── first_thesis_complete_sender.py
├── deadline_countdown_sender.py
├── abandoned_thesis_sender.py
├── stuck_on_outline_sender.py
├── trial_ending_sender.py         # retired (not in SENDERS)
└── founder_story_thesis{_2}_sender.py  # lapsed catch-up only
```
