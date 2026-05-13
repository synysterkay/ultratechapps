# Selka (Red Flag Scanner) email pipeline — deploy guide

Two Cloud Functions ship together to the `redflagscanner` Firebase project:

| Function | Trigger | Purpose |
|---|---|---|
| `sendSelkaWelcome` | `users/{uid}` create | Localized Selka-voiced welcome |
| `onSelkaEmailEvent` | `email_events/{eventId}` create | Track A–E lifecycle emails |

Other apps in this codebase (Predictify, Thesis, etc.) are unaffected — both functions early-return when `process.env.GCLOUD_PROJECT !== "redflagscanner"`.

---

## One-time setup

### 1. Secrets

Set both secrets in the `redflagscanner` Firebase project:

```bash
firebase functions:secrets:set RESEND_API_KEY --project redflagscanner
firebase functions:secrets:set DEEPSEEK_API_KEY --project redflagscanner
```

The Resend key needs send access for all sender domains listed in `functions/redflag/sender.js`. The DeepSeek key is used only for translate-at-send (write-through cache to `email_translations/{hash}`).

### 2. Verify sender domains

The sender pool in `functions/redflag/sender.js` rotates across 8 Flow domains. Each needs to be verified in Resend, with DKIM + SPF set, before sending will succeed:

- `hello@selka.app`  ← **needs adding** (canonical Selka domain)
- `selka@kaynel.pl`
- `selka@bestaiapps.site`
- `selka@vitazelki.pl`
- `selka@aibettips.io`
- `selka@predictifyfootball.com`
- `selka@thesisgenerator.io`
- `selka@passedai.io`

If `hello@selka.app` isn't ready, comment it out of the `SENDER_POOL` array — the rotation will fall back to the seven other domains.

### 3. Install deps + deploy

```bash
cd /Volumes/Flow/marketing-tool/firebase-welcome
cd functions && npm install && cd ..
./deploy.sh redflagscanner
```

The first run installs the `resend` npm package + bumps to Node 20.

---

## App-side scheduled emitters

Three new scheduled functions live in the **app's** Firebase project (not this one):

| Function | Schedule (UTC) | Source |
|---|---|---|
| `emitInactiveUserEvents` | daily 09:30 | `functions/lifecycle_emitter.js` |
| `emitIdlePartnerEvents` | daily 10:00 | `functions/lifecycle_emitter.js` |
| `emitMonthlyMilestone` | 1st of month 09:00 | `functions/lifecycle_emitter.js` |

Deploy them from the app repo:

```bash
cd "/Volumes/Flow/Flutter IOS/red_flag_scanner"
firebase deploy --only functions:emitInactiveUserEvents,functions:emitIdlePartnerEvents,functions:emitMonthlyMilestone --project redflagscanner
```

They write to `email_events/{eventId}` which this codebase's `onSelkaEmailEvent` picks up.

---

## Editing copy

All template content lives in [`functions/redflag/templates.js`](functions/redflag/templates.js) as English source-of-truth. To change a template:

1. Edit `subject`, `preheader`, `body`, `cta`, or `ps` in English.
2. **Bump the `version` field on that template.** This invalidates the translation cache so the next non-English send re-translates with the new copy.
3. Redeploy.

No need to translate manually — DeepSeek does it at first send per locale, with the result cached forever (per version) in Firestore.

---

## Cost notes

- **Resend**: $0.001/email at the current plan (~$1 per 1k sends).
- **DeepSeek translate cost**: One call per (template × non-English locale × version), shared across all users. ~$0.0003 per call. Total ~$0.10 to translate the full template library into all 17 non-English locales — paid as users land in each locale, not upfront.
- **Firestore**: 1 read + 0–1 write per email send for the translation cache.

---

## Event reference

| `event_type` written to `email_events/` | Template | Beat |
|---|---|---|
| `onboarding_complete` | `welcome` | trigger |
| `analysis_complete_first` | `first_scan_followup` | variable_reward |
| `comparison_complete` | `comparison_result` | variable_reward |
| `level_up` | `level_up` | variable_reward |
| `paywall_dismissed` | `paywall_dismissed` | trigger |
| `credits_low` | `credits_low` | action |
| `credits_zero` | `credits_zero` | trigger |
| `weekly_report_ready` | `weekly_report` | variable_reward |
| `pattern_unlocked` | `pattern_unlocked` | variable_reward |
| `partner_idle_5d` | `partner_idle_5d` | trigger |
| `monthly_milestone` | `monthly_milestone` | investment |
| `selka_wrapped_ready` | `selka_wrapped` | variable_reward |
| `referral_activated` | `referral_activated` | variable_reward |
| `streak_milestone_30` | `streak_30_gift` | variable_reward |
| `inactive_21d` | `inactive_21d` | trigger |
| `inactive_45d` | `inactive_45d` | variable_reward |
| `inactive_90d` | `inactive_90d` | trigger |

Track B templates auto-skip for premium users; Track C templates auto-skip for free users. See `dispatcher.js:TRACK_B_TEMPLATES` and `TRACK_C_TEMPLATES`.

---

## Personalization variables

All templates can use these — missing values fall back to safe defaults in `sender.js:DEFAULTS`:

`{name}` `{partner_name}` `{partner_a}` `{partner_b}` `{last_partner_risk}` `{top_pattern}` `{shared_pattern}` `{scan_count_total}` `{scan_count}` `{partner_count}` `{streak_days}` `{credits_remaining}` `{referral_code}` `{referrals_count}` `{level}` `{new_level}` `{old_level}` `{pattern_name}` `{feature_name}` `{feature_one_liner}` `{retro_insight_hint}`

Event-specific extras come from `event_doc.metadata` and are merged on top of the user-doc-derived vars.

---

## Troubleshooting

```bash
# Tail Cloud Function logs for Selka
firebase functions:log --only sendSelkaWelcome,onSelkaEmailEvent --project redflagscanner -n 100

# Manually trigger a test event (replace UID + event_type)
firebase firestore:set "email_events/test_$(date +%s)" \
  --data '{"uid":"USER_UID","event_type":"welcome","metadata":{},"sent":false}' \
  --project redflagscanner

# Force re-translate (delete a cache doc; next send re-fills it)
firebase firestore:delete email_translations/HASH --project redflagscanner
```

Common failure modes:

- **`skip_reason: "user_missing"`** — event written before user doc was created. Race in onboarding; safe to ignore.
- **`skip_reason: "no_email"`** — anonymous user; user must add email before they're emailable.
- **`skip_reason: "free_user_skipped_track_c"`** — Track C is premium-only by design.
- **`last_error: "DeepSeek translate 429"`** — DeepSeek rate-limit; the next event will retry from cache or re-fetch.
- **Resend `from_address_not_verified`** — verify the domain in Resend or remove it from `SENDER_POOL`.
