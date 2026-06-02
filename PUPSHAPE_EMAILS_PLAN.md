# PupShape — Retention Email Plan

End-to-end design for the PupShape email system: who gets what, in
which language, when it fires, and which Hooked-model lever each one
pulls. **Other apps (Bass Booster, Thesis, Loud EQ, Cupid AI, etc.)
are untouched.**

PupShape is a dog weight-management app. Every email speaks to the
human caregiver about *their specific dog* — using the dog's name,
breed, target weight, and current journey week. The emotional center
of the product is the bond between owner and pup; the emails inherit
that voice (warm, never clinical, celebratory of the dog).

---

## 1. Architecture

```
Flutter app                    Firestore                          Marketing tool
──────────────                 ─────────                          ──────────────
auth (Firebase)         ───▶  users.{uid}.{email,             ───▶  every sender (segmentation)
                              displayName, language,
                              photoURL}
LocaleProvider          ───▶  users.{uid}.language (es/pt/fr…) ───▶  template language picker
DogProvider             ───▶  users.{uid}.dogs.{dogId}.{       ───▶  per-dog personalization
                                name, breed, weight,                  (every email is "${dog.name}…")
                                targetWeight, age, gender,
                                imageUrl, createdAt }
ProgressService         ───▶  users.{uid}.dogs.{dogId}          ───▶  weekly recap, milestone, plateau,
                                .weight_logs.{ts,weight,bcs}          first-weigh-in
TaskCompletionService   ───▶  users.{uid}.dogs.{dogId}          ───▶  body-check reminder, daily
                                .task_completions.{date}.{key}        engagement signal
StreakService (computed) ───▶ users.{uid}.usage.streak          ───▶  streak_milestone, streak_at_risk
SessionCounter          ───▶  users.{uid}.usage.totalSessions   ───▶  abandoned_app
                              users.{uid}.usage.lastOpenMs
SuperwallSubscription   ───▶  users.{uid}.subscription          ───▶  trial_ending, winback, paid filter
                              .{status, plan, trialEnd,
                                expiresAt, provider}
ReferralService         ───▶  users.{uid}.referrals.{           ───▶  invite_friend_reminder
                                code, invitedCount }
```

### Shared modules (`scripts/`) — same pattern as Bass Booster / Thesis

- `localize_phrase.py` — already supports `en, es, pt, fr, ar, zh, hi, ru`. **PupShape needs `de, it, nl, ja, ko` added** (the app supports 10 locales). One PR to that file.
- `app_retention_emailer.py` — the long-form welcome drip. Auto-picks up
  new apps from `apps/*.md`. **Once `apps/pup-shape-dog-weight-loss-plan.md`
  lands, it generates the 30-day welcome cycle in all 10 languages on
  next run.**
- `pupshape_email_chrome.py` — *new*, mirrors `bass_booster_email_chrome.py`.
  Warm cream palette (`#FAF8F4` background, `#FFB347 → #FF6B6B` hero
  gradient, `#FF6B00` CTA). Every email leads with the dog's photo
  (URL in `users/{uid}.dogs.{dogId}.imageUrl`) at the top of the
  hero block — that's the visceral hook.
- `pupshape_template_translator.py` — *new*, mirrors
  `bass_booster_template_translator.py`. DeepSeek-powered translator
  that turns the English source dict into 9 localized JSONs
  (`cache/pupshape_templates/{kind}_{lang}.json`).
- `pupshape_users_loader.py` — *new*. Single Firestore loader; joins
  `users/{uid}` with `users/{uid}/dogs/*` so every email has its dog
  context in one read. Normalizes legacy language values (`en_US` →
  `en`, `zh-CN` → `zh-Hans`, etc.).
- `pupshape_orchestrator.py` — *new*. Single entry point from
  `retention-emails.yml` GitHub Actions.

---

## 2. The 13 senders

| # | Sender | Trigger | Stages | Hooked lever |
|---|---|---|---|---|
| 1 | `first_weigh_in_celebration_sender` | First weight_log doc lands for any dog (dedupe per dogId) | 1 | Variable reward (engine can now adapt) |
| 2 | `abandoned_app_sender` | App installed but `usage.lastOpenMs > 48h && !subscription.active` | 2d / 5d / 10d | External trigger (funnel rescue) |
| 3 | `streak_milestone_sender` | `usage.streak.current` hits 3 / 7 / 14 / 30 / 100 | 5 | Variable reward (externalized celebration) |
| 4 | `streak_at_risk_sender` | `streak ≥ 2` && no log today && now > 18:00 user local time | 1 / day | Internal trigger (loss aversion) |
| 5 | `weekly_recap_sender` | Sunday morning, weekly cadence | 1 / week | Variable reward (delta, plateau-or-on-track, what changed) |
| 6 | `milestone_crossed_sender` | A weigh-in writes a doc whose computed % crosses 25 / 50 / 75 / 100% toward goal | 4 | Variable reward (the *big* one — peak emotional moment) |
| 7 | `plateau_detected_sender` | `CaloriePlan.plateauDetected == true` for 3 consecutive Sundays | 1 / week max | Trust + retention (engine is doing real work, not just timer-based) |
| 8 | `body_check_reminder_sender` | No `task_completions.body_condition_score` in any `task_completions.*` doc for 28+ days | 1 / month | External trigger (Path's BCS node re-engagement) |
| 9 | `at_goal_celebration_sender` | First time `dog.weight ≤ dog.targetWeight + 0.1` (loss) **or** `dog.weight ≥ dog.targetWeight - 0.1` (gain), dedupe per dogId | 1 (once) | Variable reward (peak); transition to maintenance voice |
| 10 | `trial_ending_sender` | `subscription.status == 'trial'` && `trialEnd` within 3d / 1d | 2 | Monetization (trial → paid) |
| 11 | `winback_sender` | `subscription.status == 'cancelled'` | 7 / 30 / 60 / 90 d | Monetization (lapsed-pro recovery) |
| 12 | `invite_friend_reminder_sender` | `usage.streak.current ≥ 7` && `referrals.invitedCount == 0` | 1 (one-shot) | Tribe + investment |
| 13 | `progress_card_share_nudge_sender` | A milestone fires and the user did NOT tap "Share this win" within 24h | 1 (24h after milestone) | Tribe (low-friction social distribution) |

Total: **13 senders × up to 5 stages = ~25 distinct trigger emails**,
each delivered in the user's chosen language. The generic 30-day
welcome drip is produced automatically by `app_retention_emailer.py`
once `apps/pup-shape-dog-weight-loss-plan.md` exists — **not
duplicated in this plan.**

---

## 3. Language coverage — all 10 (mirrors the app)

The app exposes exactly 10 in-app languages via `LocaleProvider` →
`SupportedLocale`. Every triggered email is generated in all 10 via
DeepSeek translation cached under `cache/pupshape_templates/`:

`en, es, pt, fr, de, it, nl, ja, ko, zh-Hans`

Language code mapping (handled in `pupshape_users_loader.py` — Flutter
writes `zh-Hans` directly; some legacy data may carry `en_US` / `zh-CN`):

| Flutter pref | Email locale |
|---|---|
| `en` | `en` |
| `es` | `es` |
| `pt` | `pt` |
| `fr` | `fr` |
| `de` | `de` (new — add to `localize_phrase.py`) |
| `it` | `it` (new — add to `localize_phrase.py`) |
| `nl` | `nl` (new — add to `localize_phrase.py`) |
| `ja` | `ja` (new — add to `localize_phrase.py`) |
| `ko` | `ko` (new — add to `localize_phrase.py`) |
| `zh-Hans`, `zh-CN`, `zh` | `zh` |

Hand-curated phrases (plural rules for *meals* / *weeks* / *days*, dog
gender pronouns where applicable, kg unit): `localize_phrase.py`.
Marketing-voice body copy: DeepSeek with strict JSON output +
placeholder preservation. Pre-warm once after deploying a new sender:

```bash
python scripts/pupshape_orchestrator.py --warm
```

---

## 4. Critical Flutter-side wiring required first

These signals must flow into Firestore before *any* triggered email
can fire. **Most already exist.** The ones that don't are flagged.

### 4.1 User mirror (highest priority) — ✅ already exists
`AuthProvider._createUserDocument` writes name + email + photoURL +
createdAt at sign-in. `LocaleProvider._syncFirestore` writes language.
No change.

### 4.2 Dog mirror — ✅ already exists
`DogProvider.addDog` / `updateDog` write the full `Dog` to
`users/{uid}/dogs/{dogId}`. The new `imageUrl` field (recently
shipped) is the email hero image.

### 4.3 Weight logs — ✅ already exists
`ProgressService.logWeight` writes to
`users/{uid}/dogs/{dogId}/weight_logs/*`.

### 4.4 Task completions — ✅ already exists
`TaskCompletionService.markComplete` mirrors to
`users/{uid}/dogs/{dogId}/task_completions/{yyyy-mm-dd}` (committed
recently). Used by `body_check_reminder_sender`.

### 4.5 Usage mirror — ⚠️ MISSING, needs ~30 lines
Bring `SessionCounter` + `StreakService` into a Firestore mirror.
Add a `UsageMirrorService` that, in `TodayScreen._refresh`:

```dart
await UsageMirrorService.write(
  dogId: dog.id,
  streak: StreakService.currentStreak(meals),
  totalSessions: sessionCount,
  lastOpenMs: DateTime.now().millisecondsSinceEpoch,
);
```

That writes:
```
users/{uid}.usage = {
  streak: { current, peak, lastSessionDay },
  totalSessions,
  lastOpenMs,
}
```

Without this, `abandoned_app_sender`, `streak_milestone_sender`,
`streak_at_risk_sender`, and `invite_friend_reminder_sender` cannot
fire — they all read from `users.{uid}.usage`.

### 4.6 Subscription mirror — ⚠️ MISSING, needs ~20 lines
Superwall's `subscriptionStatus` is reactive. Subscribe in a top-level
service (`SubscriptionMirrorService`) and write to
`users/{uid}.subscription` on every change:

```dart
Superwall.shared.subscriptionStatus.listen((status) {
  FirebaseFirestore.instance.collection('users').doc(uid).set({
    'subscription': {
      'status': status.kind,          // 'unknown' | 'active' | 'expired' | 'cancelled' | 'trial'
      'entitlements': status.entitlements.map((e) => e.id).toList(),
      'updatedAt': FieldValue.serverTimestamp(),
    },
  }, SetOptions(merge: true));
});
```

Without this, `trial_ending_sender` and `winback_sender` cannot fire,
and *every* sender has to assume `!subscription.active` (loses the
ability to filter paid users out of upsell emails).

### 4.7 Milestone events — ⚠️ MISSING, needs ~10 lines
`WeightLoggingScreen._save` already detects milestone crossings (25 /
50 / 75 / 100%). Add one extra Firestore write at that detection
point:

```dart
await FirebaseFirestore.instance
    .collection('users').doc(uid)
    .collection('dogs').doc(dog.id)
    .collection('milestones').doc(m.key).set({
  'crossedAt': FieldValue.serverTimestamp(),
  'milestoneKey': m.key,
  'milestoneTitle': m.title,
}, SetOptions(merge: true));
```

The `milestone_crossed_sender` reads this collection. The same
write enables `progress_card_share_nudge_sender` to fire 24h later
if `shareTappedAt` is still null.

---

## 5. Segmentation matrix

How every (user_state × event) pair is addressed:

```
                       FREE                      TRIAL                   PAID                    CHURNED
new (<7d)              welcome drip              trial-onboard*          thank-you*              —
first weigh-in         first_weigh_in_celeb      first_weigh_in_celeb    first_weigh_in_celeb    —
inactive 2d/5d/10d     abandoned_app             abandoned_app           abandoned_app           —
streak milestone       streak_milestone          streak_milestone        streak_milestone        —
streak at risk         streak_at_risk            streak_at_risk          streak_at_risk          —
weekly recap (Sun)     weekly_recap              weekly_recap            weekly_recap            —
milestone crossed      milestone_crossed         milestone_crossed       milestone_crossed       —
plateau                plateau_detected          plateau_detected        plateau_detected        —
no BCS in 28d          body_check_reminder       body_check_reminder     body_check_reminder     —
at goal                at_goal_celebration       at_goal_celebration     at_goal_celebration     —
trial close to end     —                         trial_ending (3d/1d)    —                       —
cancelled              —                         —                       —                       winback (7/30/60/90)
streak ≥ 7, 0 inv.     invite_friend_reminder    invite_friend_reminder  invite_friend_reminder  —
milestone, no share 24h progress_card_share_nudge progress_card_share_nudge progress_card_share_nudge —
```

`*` welcome and thank-you are handled by `app_retention_emailer.py`
(the long-form 30-day drip) — not duplicated here.

---

## 6. Hooked-model coverage

PupShape is the most loop-rich app in the marketing-tool stable — it
has every Hooked lever covered, and the email system reinforces each
one externally.

| Phase | How the email system covers it |
|---|---|
| **External trigger** | `abandoned_app`, `body_check_reminder`, `winback`, `invite_friend_reminder`, `progress_card_share_nudge` |
| **Internal trigger** | `streak_at_risk` (loss aversion — "Sir's 6-day streak ends in 3 hours"), `trial_ending` (loss aversion on price), `plateau_detected` ("we mixed up the plan — see what changed") |
| **Action** | Every CTA deep-links into the lowest-friction continue flow. E.g. `pupshape://walk` for activity nudges, `pupshape://weigh` for the weigh-in screen, `pupshape://coach` for Bailey. |
| **Variable reward** | `first_weigh_in_celebration`, `streak_milestone`, `weekly_recap` (delta is non-deterministic), `milestone_crossed` (the *big* one — pairs with in-app share sheet), `at_goal_celebration` |
| **Investment** | `weekly_recap` reinforces "you've been doing this for N weeks", `body_check_reminder` adds another data type to the history, `invite_friend_reminder` compounds social capital |

The `progress_card_share_nudge_sender` is uniquely PupShape — it
closes the loop on the in-app share sheet that fires when a milestone
crosses. If the user dismisses the in-app sheet (most do, friction
is real), an email 24h later shows the rendered card as inline HTML
with a one-tap "Share" deep-link.

---

## 7. Voice + tone guardrails

PupShape is a **caregiver-to-pet emotional** product — *not* a
self-improvement app, *not* a workout tracker. The email voice must
match:

- **Address the human, talk about the dog.** "${dog.name} dropped 0.3
  kg this week" beats "You logged a 0.3 kg loss." The reader's
  identity is "Sir's human", not "user."
- **Use the dog's name in every subject line.** Open rate lift is
  meaningful and the personalization is genuine.
- **Concrete, visceral results.** "Sir's ribs are starting to feel
  again — that's the win" beats "Body composition improving."
- **Never moralize about missed days.** A streak break is met with
  "Streak reset — happens. Log one meal today and the new streak
  starts at 1." Not "You missed yesterday." The dog deserves both.
- **Pet-parent palette in HTML:** warm cream background `#FAF8F4`,
  hero gradient `#FFB347 → #FF6B6B`, body text `#1E293B`, CTA solid
  primary `#FF6B6B` with rounded `12px` radius. Brand stamp footer
  in `#FFB347`.
- **Lead every triggered email with the dog's photo.** Pull
  `users.{uid}.dogs.{dogId}.imageUrl` and render at 240×240 inside
  a circular crop with the gradient ring. Falls back to the
  size-bucket art (`assets/dogs/*.jpg` in the app, mirror to public
  CDN for emails) if no photo set.
- **RTL not needed** — PupShape doesn't support Arabic / Hebrew in
  the app (yet). Skip the bidi wrapper.
- **Never apologize for promoting Pro.** A free user who hits a
  milestone *wants* the share artifact and the deeper analytics —
  the email should treat the upgrade as the natural next step.

---

## 8. Deploy + warm-up checklist

1. Land `apps/pup-shape-dog-weight-loss-plan.md` in this repo
   (already done in the same commit as this plan). Next nightly run
   of `app_retention_emailer.py` will produce the 30-day welcome
   drip in all 10 languages.
2. Land the **Flutter-side mirrors** flagged in §4 (UsageMirror,
   SubscriptionMirror, Milestone write). Without them, the triggered
   senders fire on empty data.
3. Add `de, it, nl, ja, ko` plural / unit handling to
   `localize_phrase.py` (one PR — see §3).
4. Implement the five new scripts (chrome / translator / users_loader
   / orchestrator + the per-sender modules) following the
   `bass_booster_*` template files line-for-line.
5. Pre-warm DeepSeek translations:
   ```bash
   python scripts/pupshape_orchestrator.py --warm
   ```
6. Add `pupshape_orchestrator.py` to `.github/workflows/retention-emails.yml`
   alongside the other apps.
7. Manually fire one of each sender at the team's own dogs for a QA
   round before enabling globally.
