# Thesis Generator — Retention Email Plan

End-to-end design for the Thesis Generator email system: who gets what, in
what language, when it fires, and which Hooked-model lever each one pulls.
**Other apps (Predictify, Volume Booster, Cupid AI, etc.) are untouched.**

---

## 1. Architecture

```
Flutter app                Firestore                   Marketing tool
─────────────              ─────────                   ──────────────
mobile_auth_service ───▶  users.{uid}.language    ───▶ every sender (segmentation)
chapter_gate_service ──▶  users.{uid}.usage.*     ───▶ free_quota_hit_sender
superwall_service   ──▶  users.{uid}.subscription ───▶ trial_ending / winback / paid filter
subscription_sync   ──▶  users.{uid}.subscription ───▶ (web Stripe path)
streak_service      ──▶  users.{uid}.streak.*     ───▶ streak_at_risk / streak_milestone
background_gen      ──▶  theses.{id}.status       ───▶ first_thesis_complete / abandoned / stuck
```

### Shared modules (`scripts/`)
- `localize_phrase.py` — 20-language plural-aware phrase helper (days_left,
  streak, progress, work_type, pain_hook, greetings, signoffs, footers).
- `thesis_template_translator.py` — DeepSeek-powered translator that turns
  the English source dict of any sender into 19 localized JSON cache files
  (`cache/thesis_templates/{kind}_{lang}.json`). Idempotent; safe to re-run.
- `thesis_email_chrome.py` — single HTML renderer (RTL-aware, gradient
  presets per intent, P.S. callout boxes, footer/unsubscribe).
- `thesis_users_loader.py` — single Firestore loader. Yields normalized
  user dicts (`{email, language, plan, subscription, usage, streak, …}`)
  and theses (`{thesis_id, user_id, status, topic, progress, …}`).
  Handles legacy "English"/"Swedish" language values, multi-type
  `progressPercentage`, missing fields.
- `thesis_orchestrator.py` — runs every sender in order. Single entry
  point from the GitHub Actions workflow.

---

## 2. The 11 senders

| # | Sender | Trigger | Stages | Hooked lever |
|---|---|---|---|---|
| 1 | `first_thesis_complete_sender` | `theses.status == 'completed'`, dedupe per user | 1 | Variable reward (celebrate + monetize via PDF export gate) |
| 2 | `stuck_on_outline_sender` | `theses.status == 'draft'` + `progress in 1..4%` + 24h+ inactive | 1 | External trigger (funnel rescue) |
| 3 | `abandoned_thesis_sender` | `theses.status in {in_progress, generating, draft}` + inactive | 2d / 5d / 10d | External trigger (re-engagement) |
| 4 | `streak_milestone_sender` | `streak.current` hits 3 / 7 / 14 / 30 / 100 | 5 | Variable reward (externalized celebration) |
| 5 | `streak_at_risk_sender` | streak ≥ 3 + last_active > 18h | 1 / day | Internal trigger (loss aversion) |
| 6 | `deadline_countdown_sender` | `plan.deadline` − today ∈ {14, 7, 3, 1, 0} days | 5 | External trigger (urgency) |
| 7 | `free_quota_hit_sender` | `usage.freeChapterUsed == true` + free user | 24h / 72h / 7d | **Monetization** (upgrade) |
| 8 | `trial_ending_sender` | `subscription.status == 'trial'` + trialEnd close | 3d / 1d | Monetization (trial conversion) |
| 9 | `winback_sender` | `subscription.status == 'cancelled'` | 7 / 30 / 60 / 90 d | Monetization (lapsed-pro recovery) |
| 10 | `weekly_progress_sender` | Sundays only, last_active ≤ 14d | 1 / week | Investment (recap, social comparison) |
| 11 | `cumulative_stats_sender` | 1st of month, last_active ≤ 60d, ≥1 thesis | 1 / month | Investment (loss aversion on accumulated value) |

Total: **11 senders × up to 5 stages = ~25 distinct trigger emails**, each
delivered in the user's chosen language.

---

## 3. Language coverage — all 20

The app exposes 20 thesis languages; every email type is generated in all
20 via DeepSeek translation cached under `cache/thesis_templates/`:

`en, es, fr, ar, zh, hi, de, pt, it, ru, ja, ko, tr, nl, pl, sv, ro, id, th, vi`

Hand-curated for correctness (plural rules, RTL handling, work-type
labels, pain hooks): `localize_phrase.py`. Marketing-voice body copy:
DeepSeek with strict JSON output + placeholder preservation, vetted via
the cached JSONs in git.

Pre-warm the cache once after deploying a new sender:

```bash
python scripts/thesis_orchestrator.py --warm
```

---

## 4. Critical fixes shipped alongside

These were discovered while building the new system and are essential for
*any* of the existing emails to actually fire:

### 4.1 Flutter side — Firestore writes
- **`MobileAuthService`** now calls `FirebaseUserService.ensureUserMirrored()`
  after every sign-in/sign-up. Writes `email`, `displayName`, `language`,
  `createdAt`, `lastSignInAt`, `signupProvider` to `users/{uid}`.
  → Before: only 10% of users had a `language` field. After: 100%.
- **`SuperwallService`** writes `subscription.status = 'active', provider:
  'superwall'` whenever the paywall's `feature` callback fires (purchase
  or existing entitlement). Also calls `recordPaywallShown()` on every
  paywall presentation for funnel analytics.
- **`SubscriptionSyncService`** (web Stripe path) mirrors `subscription`
  to Firestore on `handlePaymentSuccess[Quick]` and on Stripe-confirmed
  `checkUnifiedSubscriptionStatus()`.
- **`ChapterGateService.markFirstChapterUsed()`** now also writes
  `usage.freeChapterUsed = true` + `freeChapterUsedAt = serverTimestamp()`.

### 4.2 Marketing-tool side — broken senders fixed
- `first_thesis_complete_sender.py` was filtering on `status == 'complete'`
  (production value is `'completed'`) AND expecting an `email` field on
  thesis docs (production has none). Both fixed — now resolves email by
  joining `theses.userId → users.{uid}.email`. **19 backfill candidates
  ready to send** today.

### 4.3 Loader hardening
- Legacy docs that stored `language` as the human name (`'English'`,
  `'Swedish'`) now get mapped to the 2-letter code.
- `progressPercentage` / `wordCount` get coerced to int regardless of
  whether Firestore stored them as `integerValue`, `doubleValue`, or
  `stringValue` — Flutter has at times written all three.

---

## 5. Segmentation matrix

How every (user_state × event) pair is now addressed:

```
                    FREE                TRIAL               PAID                CHURNED
new (<7d)           welcome+nudge     trial-onboard*       thank-you*          —
in-progress         abandoned_thesis  abandoned_thesis     abandoned_thesis    —
stuck on outline    stuck_on_outline  stuck_on_outline     stuck_on_outline    —
streak milestone    streak_milestone  streak_milestone     streak_milestone    —
streak at risk      streak_at_risk    streak_at_risk       streak_at_risk      —
deadline hits       deadline (5 ms)   deadline (5 ms)      deadline (5 ms)     —
thesis complete     first_complete    first_complete       first_complete      —
free chapter spent  free_quota_hit    —                    —                   —
trial close to end  —                 trial_ending (3d/1d) —                   —
cancelled           —                 —                    —                   winback (7/30/60/90)
weekly active       weekly_progress   weekly_progress      weekly_progress     —
monthly recap       cumulative_stats  cumulative_stats     cumulative_stats    —
```

`*` welcome and thank-you are handled by the existing `app_retention_emailer.py`
pipeline (the long-form drip cycle) — not duplicated here.

---

## 6. Hooked-model coverage

| Element | How the email system covers it |
|---|---|
| **External trigger** | abandoned_thesis, stuck_on_outline, deadline_countdown, winback |
| **Internal trigger** | streak_at_risk (loss aversion), free_quota_hit (sunk cost), trial_ending |
| **Action** | Every CTA deep-links into the app's lowest-friction continue flow |
| **Variable reward** | first_thesis_complete, streak_milestone, weekly_progress |
| **Investment** | weekly_progress, cumulative_stats (the missing pillar; see §7) |

---

## 7. Open follow-ups (not implemented this pass)

- **In-app referral system** — the "Investment" pillar needs a way for
  users to invest social capital. The email plumbing for a
  `referral_invite_sender` is ready but the in-app share/code generation
  doesn't exist yet. Recommended as the next product unit of work.
- **Streak mirror is silently broken in production** — `streak_service.dart`
  calls `_mirrorToFirestore()` but 0% of users have a streak field after
  300 samples. The mirror fires only inside `recordActivity()`, which only
  runs when the user creates a thesis or generates a chapter; the silent
  catchError might also be swallowing permission-denied errors.
- **`syncUserPlanToFirestore` not called reliably** — onboarding writes
  `plan` only when the user completes every step. Many users bounce
  partway. Worth either (a) writing each plan field as it's selected, or
  (b) writing whatever's filled at any forward navigation.

---

## 8. Deploying

1. Ship the Flutter changes. The `users.{uid}` doc starts populating
   `language` (every user), `subscription` (paid users), and `usage` (free
   users who burn their chapter). Allow ~1 week for the cohort to fill.
2. Set `DEEPSEEK_API_KEY` in GitHub Secrets (already in `.env` locally).
3. Pre-warm translation cache once:
   ```bash
   python scripts/thesis_orchestrator.py --warm
   ```
   Output goes to `cache/thesis_templates/*.json`. Commit those.
4. The existing `retention-emails.yml` schedule (2× daily) now invokes
   `scripts/thesis_orchestrator.py` instead of three individual senders.
   No new cron entry needed.
5. First production run will fire ~52 already-due emails (19
   first-completion + 33 abandoned-thesis backfill). Monitor bounce / spam
   rate via existing `DeliverabilityMonitor`.

---

## 9. Files of interest

```
marketing-tool/scripts/
├── localize_phrase.py            # 20-lang plural-aware phrase helper
├── thesis_email_chrome.py        # shared HTML renderer
├── thesis_users_loader.py        # shared Firestore loader
├── thesis_template_translator.py # DeepSeek translator + cache
├── thesis_orchestrator.py        # single entry point
│
├── first_thesis_complete_sender.py   # refactored
├── streak_at_risk_sender.py          # refactored
├── deadline_countdown_sender.py      # refactored
├── abandoned_thesis_sender.py        # new
├── stuck_on_outline_sender.py        # new
├── streak_milestone_sender.py        # new
├── free_quota_hit_sender.py          # new (monetization)
├── trial_ending_sender.py            # new (monetization)
├── winback_sender.py                 # new (monetization)
├── weekly_progress_sender.py         # new (Sundays)
└── cumulative_stats_sender.py        # new (monthly)
```

Flutter side:

```
lib/services/
├── mobile_auth_service.dart          # ensureUserMirrored on auth events
├── firebase_user_service.dart        # ensureUserMirrored / updateSubscriptionStatus / markFreeChapterUsed / recordPaywallShown
├── chapter_gate_service.dart         # mirrors free_chapter_used
├── superwall_service.dart            # subscription + paywall-shown mirrors
└── subscription_sync_service.dart    # web Stripe path mirror
```
