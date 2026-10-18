# Portfolio email ops — lanes, ceilings, health

Value-first doctrine: tip / behavioral / emotional founder / niche crosspromo.
Free / non-sub only (Firestore Superwall mirror via `free_user_gate` +
`firestore_activity_loader`: `isPremium` / `isSubscribed` /
`subscription.status|isPremium`). ZeptoMail. Soft open CTA. One marketing
mail per user per day per brand when `EMAIL_ONE_PER_DAY=1`.

## Send lanes (daily ceilings while health ≠ red)

| Lane | Domain | Agent | Ceiling | Notes |
|------|--------|-------|---------|--------|
| A | thesisgenerator.io | 1 | 400–550 | Thesis behavioral + FS lapsed |
| B | predictifyfootball.com | 1 | 250–400 | Sports tips + P0/P1 + Horse FS |
| C | breakuprelief.com | 2 | 150–250 | Fresh Start, Red Flag, SoulPlan |
| D | passedai.io | 2 | ≤240 | Crosspromo (`CROSSPROMO_DAILY_CAP`) |
| E | kaynel.solutions | 2 | 50→80 (ramp) | KinBound, PupShape, Smart Notes, AI GF, ONG… |

Unknown health status = treat as yellow (moderate caps). **Red From = skip.**

## Health rules

1. Refresh `cache/sender_health.json` before retention sends.
2. Assert `EMAIL_PROVIDER=zeptomail` in retention workflow.
3. If complaints/bounces spike on a domain → cut that lane ~50% for 3–7 days.
4. Suppressions and one-per-day always win over caps.

## Founder volume

Phase 1 free-user batches: **50–100 / app / day** (env caps per sender).
Do not unfreeze unlimited Predictify/Thesis bulk FS.

## Crosspromo budget split (shared daily cap)

Default when all packs enabled: Thesis ~50%, FS→Red Flag ~25%, Red Flag→SoulPlan ~25% of `CROSSPROMO_DAILY_CAP`.
