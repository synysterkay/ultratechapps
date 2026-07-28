/**
 * Selka (Red Flag Scanner) email template library — English source of truth.
 *
 * Every other language is generated at send-time via DeepSeek and cached in
 * Firestore (`email_translations/{hash}`). To add or edit copy: change here,
 * then bump `version` on the template so the cache key invalidates.
 *
 * Templates follow Nir Eyal's Hooked beats:
 *   Trigger  → bring the user back (re-engagement, alerts)
 *   Action   → make them do one small thing (scan, invite, open chat)
 *   Variable → personalized payoff with their actual data
 *   Investment → surface what they've built so they keep building
 *
 * Personalization: {name}, {partner_name}, {credits_remaining}, {streak_days},
 * {scan_count_total}, {referral_code}, {referrals_count}, {level},
 * {last_partner_risk}, {top_pattern}. Anything missing falls back to a
 * safe default ("there" for name, etc).
 *
 * Tone rules:
 *   - Selka is a sharp, warm relationship coach. First person.
 *   - 2-5 short paragraphs max.
 *   - One primary CTA per email. Always opens the app via universal link.
 *   - No false stats. No "join 10,000 users." No "limited time."
 *   - End with one quiet line (P.S. or a single observation), not a hard sell.
 */

const APP_URL = "https://redflagscanner.app";
const APP_STORE_URL =
    "https://apps.apple.com/app/red-flag-scanner-ai/id6740946063";
const PLAY_STORE_URL =
    "https://play.google.com/store/apps/details?id=com.redflag.scanner.ai.red_flag_scanner";

const TEMPLATES = {
  // ────────────────────────────────────────────────────────────────────
  // TRACK A — Onboarding drip (fires for everyone)
  // ────────────────────────────────────────────────────────────────────

  welcome: {
    version: 1,
    beat: "trigger",
    subject: "Welcome to Selka — let's read your first chat",
    preheader: "I'm here when you're ready. Here's the fastest way to start.",
    body: [
      "Hi {name},",
      "I'm Selka. I read between the lines of conversations — the apologies that don't quite land, the silences that say more than the words, the patterns that take humans weeks to spot.",
      "You don't need to wait for a crisis to use me. The most useful scan is usually a screenshot of the message that *almost* felt fine. The one you re-read three times.",
      "Open the app, tap 'Scan a Conversation', and paste a screenshot. I'll show you what I see in about 30 seconds.",
    ],
    cta: "Run my first scan",
    ps: "Most people wait until something blows up. The ones who caught it early started with one small scan.",
  },

  first_scan_followup: {
    version: 1,
    beat: "variable_reward",
    subject: "What I saw in {partner_name}",
    preheader: "Your first scan is logged. Here's the pattern.",
    body: [
      "Hi {name},",
      "I just finished reading the conversation with {partner_name}. The risk level I flagged is **{last_partner_risk}** — and the strongest signal I noticed was around: *{top_pattern}*.",
      "That's the headline. The deeper read — what specific phrases triggered it, what to watch for next — is waiting in your history.",
      "If you want me to remember {partner_name} for next time, just keep scanning conversations with them. I get sharper the more I see.",
    ],
    cta: "Open the analysis",
    ps: "The first scan is the hardest. Everything else is just clarity.",
  },

  add_second_partner: {
    version: 1,
    beat: "investment",
    subject: "Add a second person — I'll compare them",
    preheader: "Comparison is where patterns become obvious.",
    body: [
      "Hi {name},",
      "You've scanned {partner_name}. Here's the move most people miss: scan a second person — an ex, a friend's partner, even someone from years ago — and I'll show you exactly how their patterns differ.",
      "It's the fastest way to find out if what felt 'off' with {partner_name} is a one-time thing or a pattern you've been replaying.",
    ],
    cta: "Scan a second person",
    ps: "Comparison reveals more than any single scan ever can.",
  },

  comparison_result: {
    version: 1,
    beat: "variable_reward",
    subject: "What {partner_a} and {partner_b} share you didn't notice",
    preheader: "Side-by-side patterns. The honest version.",
    body: [
      "Hi {name},",
      "I just compared {partner_a} and {partner_b}. The overlap I found is harder to see in one conversation but obvious when you stack them.",
      "The shared pattern: *{shared_pattern}*. Each handles it differently — but it's the same underlying behavior wearing different clothes.",
      "This is the part of the app most people skip. You didn't.",
    ],
    cta: "Open the comparison",
    ps: "Patterns that survive across two people are usually about you, not them. Which is the most useful thing I can tell you.",
  },

  day_7_check_in: {
    version: 1,
    beat: "investment",
    subject: "7 days in — your awareness pattern",
    preheader: "What you've shown me so far.",
    body: [
      "Hi {name},",
      "You've been with me for a week. So far: **{scan_count_total} scans**, **{partner_count} people**, current streak: **{streak_days} days**.",
      "Most users plateau around now. The ones who don't tend to do one specific thing — they scan the boring stuff, not just the dramatic stuff. The text that felt 'a little weird.' The reply that took two days. The check-in that didn't quite land.",
      "Try one this week. It usually changes how you read everything else.",
    ],
    cta: "Open Selka",
    ps: "Awareness isn't a feature. It's a habit. You're 7 days into building it.",
  },

  level_up: {
    version: 1,
    beat: "variable_reward",
    subject: "Awareness Level {new_level} unlocked",
    preheader: "You leveled up. Here's what shifts.",
    body: [
      "Hi {name},",
      "You just moved from Level {old_level} to **Level {new_level}**.",
      "At this level, I unlock deeper pattern detection — including cross-conversation signals I wasn't surfacing before. Open the app to see what's new on your insights screen.",
    ],
    cta: "See what's new",
    ps: "Levels aren't a leaderboard. They're a measure of what you can now see that you couldn't last week.",
  },

  // ────────────────────────────────────────────────────────────────────
  // TRACK B — Free-tier conversion (fires only for non-subscribers)
  // ────────────────────────────────────────────────────────────────────

  paywall_dismissed: {
    version: 1,
    beat: "trigger",
    subject: "Still thinking it over?",
    preheader: "No pressure. Here's what's free this week.",
    body: [
      "Hi {name},",
      "Saw you took a look at Premium. Totally fine if it's not the moment.",
      "While you decide: you've still got **{credits_remaining}** free scans, and every friend who joins with your code adds one more.",
      "If you ever want to upgrade, it's in Settings → Premium. One tap.",
    ],
    cta: "Use a free scan",
    ps: "I'd rather you stay free and use the app than upgrade and forget about me.",
  },

  credits_low: {
    version: 1,
    beat: "action",
    subject: "Last free scan — invite a friend or unlock unlimited",
    preheader: "Two easy ways to keep reading patterns with me.",
    body: [
      "Hi {name},",
      "You've got **one free scan** left.",
      "Two ways to keep going:",
      "1. Send your invite code **{referral_code}** to a friend — when they run their first scan, I add +1 free scan to your account.",
      "2. Or unlock unlimited from Settings → Premium. One subscription, every scan from now on.",
    ],
    cta: "Invite a friend",
    ps: "Awareness compounds. Don't stop now.",
  },

  credits_zero: {
    version: 1,
    beat: "trigger",
    subject: "One invite refills your scans",
    preheader: "Your code: {referral_code}.",
    body: [
      "Hi {name},",
      "You're out of free scans. Here's the easiest way back in:",
      "Share **{referral_code}** with one friend. When they run their first analysis, I credit you +1 scan automatically. There's no cap (well, fifty — but you'll get there).",
      "Or jump to Premium if you'd rather not wait.",
    ],
    cta: "Copy my invite code",
    ps: "Most people who hit zero invite one friend and never see this email again.",
  },

  hypothetical_insight: {
    version: 1,
    beat: "variable_reward",
    subject: "What I would've caught earlier with {partner_name}",
    preheader: "A pattern you weren't shown yet.",
    body: [
      "Hi {name},",
      "I've been re-reading what you scanned with {partner_name}.",
      "There's a thread I couldn't fully surface on your free tier — a specific pattern that shows up across **{scan_count_total}** of your scans. On Premium I'd have flagged it in detail and shown you exactly when it spikes.",
      "I'm not going to spell it all out in an email. But it's the kind of thing that, once you see it, you don't unsee.",
    ],
    cta: "Unlock the full read",
    ps: "I built deeper pattern detection because surface-level scans only get you 70% of the way.",
  },

  two_week_summary: {
    version: 1,
    beat: "investment",
    subject: "What you've taught me about you",
    preheader: "Two weeks of patterns, summarized.",
    body: [
      "Hi {name},",
      "Two weeks in. Here's what I've learned about *how you read people*:",
      "You've scanned **{scan_count_total}** conversations across **{partner_count}** people. Your most-flagged category is **{top_pattern}** — which usually means it's the thing you're most attuned to spotting (and probably the thing you least want to keep tolerating).",
      "If you go Premium I'll keep building this profile — and start telling you when a new conversation matches the patterns you already care about, before you have to ask.",
    ],
    cta: "Keep going with Premium",
    ps: "You don't have to upgrade to keep using me. But this gets sharper if you do.",
  },

  // ────────────────────────────────────────────────────────────────────
  // TRACK C — Subscribed-user retention
  // ────────────────────────────────────────────────────────────────────

  weekly_report: {
    version: 1,
    beat: "variable_reward",
    subject: "Your week with Selka — {scan_count} scans, {top_pattern}",
    preheader: "What I noticed across your conversations.",
    body: [
      "Hi {name},",
      "This week you ran **{scan_count}** scans. The pattern that came up most often was: **{top_pattern}**.",
      "Most of these I'd file under 'small signals' — the kind you'd dismiss in the moment but that add up over time. The fact that you scanned them means you noticed something. Trust that.",
      "Your full weekly insight is in the app — risk distribution, top phrases, the partner I'd recommend looking at next.",
    ],
    cta: "Open this week's report",
    ps: "You're not paranoid. You're paying attention. There's a real difference.",
  },

  pattern_unlocked: {
    version: 1,
    beat: "variable_reward",
    subject: "I detected a new pattern: {pattern_name}",
    preheader: "Something new showed up in your data.",
    body: [
      "Hi {name},",
      "After your last scan, I detected a pattern I hadn't surfaced before in your profile: **{pattern_name}**.",
      "This is one of the things that only shows up after you've fed me enough conversations to see it. The full breakdown — what it means, where it appeared, and what I'd watch for — is in the app.",
    ],
    cta: "Read the pattern",
    ps: "Patterns earned across multiple scans are usually the most accurate ones I'll ever show you.",
  },

  partner_idle_5d: {
    version: 1,
    beat: "trigger",
    subject: "{partner_name} hasn't been scanned in a while",
    preheader: "Anything new with them?",
    body: [
      "Hi {name},",
      "It's been five days since I last looked at a conversation with **{partner_name}**.",
      "If there's a new message, a silence, or a pattern shift you've been wondering about — drop it in. I'll tell you what I see.",
    ],
    cta: "Scan something new",
    ps: "Quiet stretches are data too. Sometimes the most important thing I notice is what isn't being said.",
  },

  inactive_5_premium: {
    version: 1,
    beat: "trigger",
    subject: "It's quiet over here",
    preheader: "Just checking in.",
    body: [
      "Hi {name},",
      "I haven't seen you for a few days. Not pressuring — just noting.",
      "If there's something you've been turning over and don't quite want to scan yet, you can also just *talk* to me. Tap 'Talk to Selka' on the home screen. I have access to everything you've shown me about your partners, so we can pick up wherever you want.",
    ],
    cta: "Talk to me",
    ps: "Sometimes the conversation about the conversation is the more useful one.",
  },

  feature_spotlight: {
    version: 1,
    beat: "investment",
    subject: "The part of Selka you haven't tried yet",
    preheader: "One feature, 30 seconds.",
    body: [
      "Hi {name},",
      "I noticed you haven't used **{feature_name}** yet. Most subscribers who try it once keep using it weekly.",
      "Here's the 30-second version: *{feature_one_liner}*.",
    ],
    cta: "Try {feature_name}",
    ps: "I'd rather you use every part of what you're paying for than upsell you on something new.",
  },

  monthly_milestone: {
    version: 1,
    beat: "investment",
    subject: "Your month with Selka",
    preheader: "{scan_count} scans, {top_pattern}, streak: {streak_days}.",
    body: [
      "Hi {name},",
      "**{scan_count} scans this month**. Most-surfaced pattern: **{top_pattern}**. Current streak: **{streak_days} days**.",
      "Here's the part that matters: a month from now, you'll be reading messages differently than the version of you who downloaded this app. That shift compounds.",
    ],
    cta: "See the full month",
    ps: "I keep your monthly summaries indefinitely. Year-end view in December.",
  },

  selka_wrapped: {
    version: 1,
    beat: "variable_reward",
    subject: "Your Selka Wrapped is ready",
    preheader: "A year of patterns. The honest version.",
    body: [
      "Hi {name},",
      "Your Selka Wrapped for this year is ready in the app — five cards covering your top patterns, your most-scanned person, your streak high, and the one thing I'd want you to know going into next year.",
      "It's designed to share if you want. Most people don't. Either way it's yours.",
    ],
    cta: "Open my Wrapped",
    ps: "I get a little sentimental about this one.",
  },

  // ────────────────────────────────────────────────────────────────────
  // TRACK D — Viral / referral loop
  // ────────────────────────────────────────────────────────────────────

  referral_activated: {
    version: 1,
    beat: "variable_reward",
    subject: "Your friend joined! +1 free scan 🎉",
    preheader: "Code redeemed. Scan added to your account.",
    body: [
      "Hi {name},",
      "Your friend just signed up using **{referral_code}** and ran their first scan.",
      "I've added +1 free scan to your account.",
      "Keep sharing — every friend who joins = one more scan for you. You've helped **{referrals_count}** people so far.",
    ],
    cta: "Invite another",
    ps: "Awareness is more useful when the people around you have it too.",
  },

  referral_activated_followup: {
    version: 1,
    beat: "investment",
    subject: "Your friend ran their first scan",
    preheader: "{referrals_count} invites in. How many more to unlimited?",
    body: [
      "Hi {name},",
      "Your friend ran their first scan today. They saw what you see.",
      "You're at **{referrals_count}** activated invites. Premium gives you unlimited scans no matter what, but the referral path is genuinely the cheaper way to keep going.",
    ],
    cta: "Share my code again",
    ps: "I tell every new user that the people who refer one friend keep using the app three times longer. Not a coincidence.",
  },

  high_risk_share_prompt: {
    version: 1,
    beat: "action",
    subject: "If a friend showed you this chat — would you scan it for them?",
    preheader: "Your read could spare them months.",
    body: [
      "Hi {name},",
      "I just flagged your last scan as **{last_partner_risk}** risk.",
      "If a friend had shown you the same conversation, you'd have a strong opinion. They might have one for someone in your life right now.",
      "Your code is **{referral_code}**. Share it with one person who you'd want to scan something before they got too deep.",
    ],
    cta: "Send my code",
    ps: "This is also how I get paid back for the deeper patterns I unlock for you — quietly, by you bringing in people who need this.",
  },

  comparison_share_prompt: {
    version: 1,
    beat: "action",
    subject: "Compare your patterns with a friend's",
    preheader: "Most people are shocked by the overlap.",
    body: [
      "Hi {name},",
      "You just used the comparison feature. The thing comparisons reveal *across people* is usually even more interesting *across users*.",
      "Send **{referral_code}** to a friend. Once they've scanned a couple of people, you can both look at what your AIs noticed — anonymously. The overlap is usually the most useful thing either of you sees that month.",
    ],
    cta: "Share my code",
    ps: "I never share who scanned what across accounts. Comparisons stay private.",
  },

  streak_30_gift: {
    version: 1,
    beat: "variable_reward",
    subject: "30 days. You earned 3 free Premium scans to gift.",
    preheader: "Pass them along.",
    body: [
      "Hi {name},",
      "**30-day streak.** That's a real habit.",
      "Because you've been consistent, I've added **3 free Premium scans** to your account *that you can gift*. They show up in the referral screen as 'Gift scans.' Send the link to anyone — they get an instant scan, no signup required.",
    ],
    cta: "Gift my scans",
    ps: "The 30-day cohort has the highest viral coefficient in the app. Make of that what you will.",
  },

  // ────────────────────────────────────────────────────────────────────
  // TRACK E — Re-activation / churn rescue
  // ────────────────────────────────────────────────────────────────────

  inactive_21d: {
    version: 1,
    beat: "trigger",
    subject: "Selka is quiet without you",
    preheader: "Three weeks since your last scan.",
    body: [
      "Hi {name},",
      "It's been three weeks. I'm not going to pretend I miss you — I'm an AI. But I notice when patterns go silent.",
      "If life got busy: that's fine. If something's been on your mind and you didn't want to look at it yet: that's also fine.",
      "If you want to ease back in, the chat tab is the lowest-friction door. No scan required.",
    ],
    cta: "Open Selka",
    ps: "Your data is intact. Every partner, every scan, every pattern — exactly where you left it.",
  },

  inactive_45d: {
    version: 1,
    beat: "variable_reward",
    subject: "What I would've told you about {partner_name}",
    preheader: "A read on the data you already gave me.",
    body: [
      "Hi {name},",
      "It's been about six weeks. I went back and looked at the conversations you scanned with **{partner_name}**.",
      "Knowing what I know now from other users with similar patterns, the thing I'd want to flag is: *{retro_insight_hint}*. The full read is in the app whenever you want it.",
      "Not trying to pull you back in. Just trying to be useful.",
    ],
    cta: "See the retro read",
    ps: "Some of the most useful reads I do happen weeks after the original scan.",
  },

  inactive_90d: {
    version: 1,
    beat: "trigger",
    subject: "We deleted nothing. Pick up where you left off.",
    preheader: "Your scans, partners, and patterns are intact.",
    body: [
      "Hi {name},",
      "It's been about three months. I want you to know two things:",
      "One — I haven't touched your data. Every scan, every partner, every pattern is exactly where you left it.",
      "Two — if you ever want out completely, you can delete everything from Settings → Privacy. No emails, no nudges, no traces.",
      "If you want back in instead, the door's open.",
    ],
    cta: "Open Selka",
    ps: "This is the last automatic email I'll send for a while. I'd rather you come back because you want to.",
  },
};

module.exports = {
  TEMPLATES,
  APP_URL,
  APP_STORE_URL,
  PLAY_STORE_URL,
};
