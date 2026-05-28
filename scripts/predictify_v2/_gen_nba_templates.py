#!/usr/bin/env python3
"""One-shot author of the 14 NBA Hooked-model English templates.

Mirrors the soccer templates' kinds + merge fields EXACTLY (so triggers.py and
template_engine.py work unchanged), but the copy is NBA-tuned: tip-off, player
injuries/rest, calibrated AI confidence, moneyline/spread/totals, playoff
seeding, championship-pool communities. Writes to templates_nba/{kind}_en.json.
Run once: python3 scripts/predictify_v2/_gen_nba_templates.py
"""
import json
import os

OUT = os.path.join(os.path.dirname(__file__), 'templates_nba')
os.makedirs(OUT, exist_ok=True)

T = {
    "welcome": {
        "subject": "Your first NBA call starts here, {first_name}",
        "preview_text": "{top_match_line}",
        "body_paragraphs": [
            "Hey {first_name},",
            "Welcome to Predictify. Quick orientation: every NBA game in the app comes with a calibrated AI confidence score — built from team ratings, pace, rest, and injuries — that tells you exactly how reliable the call is. Numbers, not hot takes.",
            "Try it now: {top_match_line}. Tap the game, see the full breakdown — moneyline, spread, total — and lock in your call.",
            "Pro tip: make one pick a day for 5 days and you build a streak. Streak users are 3x more likely to spot the value calls before tip-off.",
        ],
        "cta_text": "Make my first pick",
        "cta_deeplink": "predictify://prediction/{fixture_id}",
    },
    "match_day": {
        "subject": "{home_team} vs {away_team} — {confidence_pct}% confidence call",
        "preview_text": "{league_name} tips off in {hours_to_kickoff}h. Your AI's pick is ready.",
        "body_paragraphs": [
            "Hey {first_name},",
            "{home_team} vs {away_team} tips off in about {hours_to_kickoff} hours. Your AI has crunched every signal — offensive & defensive ratings, pace, recent form, rest days, and the injury report — and locked in a call.",
            "\U0001F4CA The pick: {pick_label}\n\U0001F3AF Calibrated confidence: {confidence_pct}%\n\U0001F3C0 Tier: {tier_label}",
            "This is exactly what we built Predictify for. Open the app, see the full reasoning, and lock in your prediction before tip-off.",
        ],
        "cta_text": "See the full prediction",
        "cta_deeplink": "predictify://prediction/{fixture_id}",
    },
    "streak_saver": {
        "subject": "Your {streak_days}-day streak ends in {hours_to_break} hours",
        "preview_text": "One pick keeps it alive. Your AI's call is ready.",
        "body_paragraphs": [
            "Hey {first_name},",
            "You're on a {streak_days}-day prediction streak. Most users never get past 5 — you're doing something rare.",
            "But your streak ends in about {hours_to_break} hours if you don't lock in a pick today. One tap. That's all it takes.",
            "Your AI has already done the work: {top_match_line}",
        ],
        "cta_text": "Save my {streak_days}-day streak",
        "cta_deeplink": "predictify://prediction/{fixture_id}",
    },
    "login_streak_reward": {
        "subject": "\U0001F381 3 days in a row — you just unlocked 1 week of Pro",
        "preview_text": "Open the app to claim. No card, no auto-renew.",
        "body_paragraphs": [
            "Hey {first_name},",
            "You've opened Predictify three days in a row. That's rare — most users don't make it past two.",
            "Your reward: 7 days of Predictify Pro, fully unlocked, no payment needed. You'll see the Strongest Signal on every game, calibrated confidence on every market (moneyline, spread, totals, player props), and the full prediction history.",
            "Tap below to claim. It activates instantly and lasts a week — keep using the app daily and you can earn more as the streak grows.",
        ],
        "cta_text": "Claim 7-day Pro",
        "cta_deeplink": "predictify://reward/streak3",
    },
    "weekly_recap": {
        "subject": "Your week: {recent_correct}/{recent_total} predictions correct",
        "preview_text": "{accuracy_pct}% accuracy. Top pick lined up for next week.",
        "body_paragraphs": [
            "Hey {first_name},",
            "Quick recap of your week on Predictify:",
            "✅ {recent_correct} of {recent_total} predictions hit\n\U0001F4CA {accuracy_pct}% accuracy over the last 30 days\n\U0001F525 {streak_days}-day streak (your record so far)",
            "Looking ahead: the model's strongest call this week is {top_match_line}. Worth a look — open the app and we'll show you exactly why.",
        ],
        "cta_text": "See next week's top pick",
        "cta_deeplink": "predictify://prediction/{fixture_id}",
    },
    "win_back": {
        "subject": "Predictify nailed {recent_correct} of last {recent_total} picks — without you",
        "preview_text": "You've been quiet. Here's what your AI has been calling.",
        "body_paragraphs": [
            "Hey {first_name},",
            "Quick update: while you've been away, Predictify has been doing what it does best. Last {recent_total} predictions: {recent_correct} correct — that's {recent_accuracy_pct}%, on autopilot.",
            "Here's the kicker: today's top call is {top_match_line}",
            "Open the app, take 30 seconds to see the full reasoning, and decide if your AI deserves a second look.",
        ],
        "cta_text": "See today's strongest pick",
        "cta_deeplink": "predictify://prediction/{fixture_id}",
    },
    "winback_lapsed_pro": {
        "subject": "Come back to Pro on us — 30 days free, no card needed",
        "preview_text": "What happened? Was it the price, the features, or something else?",
        "body_paragraphs": [
            "Hey {first_name},",
            "Your Pro subscription expired and we noticed. We won't oversell it — you know exactly what Pro does. We just want to know if something specifically didn't work for you.",
            "If you tell us (just reply to this email — a human reads it), we'll add 30 days of Pro back to your account, no strings, no card. A real offer, not a marketing line.",
            "Whether you come back or not, thanks for the time you spent with us. Your feedback genuinely helps us build the next version.",
        ],
        "cta_text": "Restart Pro free for 30 days",
        "cta_deeplink": "predictify://winback",
    },
    "upgrade_after_hot_week": {
        "subject": "{accuracy_pct}% accuracy this week — Pro users average {pro_target_pct}%",
        "preview_text": "Here's what the model is hiding from your free tier.",
        "body_paragraphs": [
            "Hey {first_name},",
            "Your last {recent_total} picks hit {accuracy_pct}% — well above the free-tier average. You're reading the model better than most.",
            "Pro users see the Strongest Signal for every game — the one call that consistently hits {pro_target_pct}%+ — plus calibrated confidence on every market and player-prop projections (points, rebounds, assists). That's how the top accuracy tiers stay on top.",
            "Want to try it for 7 days, free? No card required, no auto-renew. If it doesn't move your numbers, you walk away.",
        ],
        "cta_text": "Start 7-day Pro trial",
        "cta_deeplink": "predictify://upgrade?ref=hot_week",
    },
    "pro_power_tip": {
        "subject": "The Strongest Signal card — what Pros actually look at",
        "preview_text": "It hits hardest on Elite-tier games. Most users never open it.",
        "body_paragraphs": [
            "Hey {first_name},",
            "Quick Pro tip you may have missed: on every prediction screen, scroll past the final-score projection and find the 'Strongest Signal' card. It's the highest-confidence, calibrated pick for that game — and on Elite-tier matchups it's historically been the safest call on the board.",
            "How to use it: when the tier badge says Elite or Premium, the Strongest Signal is your anchor. When it says Standard, treat it as a starting point and weigh the other markets and player props too.",
            "Today's example: {top_match_line}. Open it and you'll see exactly what I mean.",
        ],
        "cta_text": "Open today's top pick",
        "cta_deeplink": "predictify://prediction/{fixture_id}",
    },
    "pro_owner_pitch": {
        "subject": "Pro users can earn from communities — keep 70%",
        "preview_text": "Some owners now earn enough to cover their Pro many times over.",
        "body_paragraphs": [
            "Hey {first_name},",
            "You've been Pro for a while and your picks are consistent. Time to flip the model: open your own NBA community on Predictify, set a small monthly price, and keep 70% of every subscription.",
            "Top community owners are turning their picks into recurring income — and Predictify handles all the payment, hosting, and member management. You just keep predicting like you already do.",
            "Setup is 90 seconds: pick a name, pick your angle (a team, a betting style, DFS), set a price or keep it free. Owners with a cover image grow 3x faster — we generate one for you in a tap.",
        ],
        "cta_text": "Create my community",
        "cta_deeplink": "predictify://community/create",
    },
    "owner_marketing_kit": {
        "subject": "{community_name} needs members — here's how top owners grow",
        "preview_text": "5 places we've seen owners post that actually convert.",
        "body_paragraphs": [
            "Hey {first_name},",
            "Your community {community_name} has {member_count} member{member_plural}. Owners who hit 25+ members in week one all use the same playbook — here it is.",
            "1. WhatsApp/Telegram group chats: drop the link with a one-line tease (\"AI calls for every NBA game, free to join\")\n2. X / Twitter: post your most confident pick of the night with the join link in the reply\n3. r/nba, r/sportsbook, r/dfsports on Reddit: a pinned daily thread\n4. TikTok comments under NBA preview / parlay videos\n5. Discord servers for the teams you cover",
            "Predictify makes the cover image for you (your share link looks 3x better with one — that alone moves join rate). Open the share kit, copy the link, paste it where NBA fans gather.",
        ],
        "cta_text": "Open share kit",
        "cta_deeplink": "predictify://community/{community_id}/share",
    },
    "owner_growth": {
        "subject": "Your community {community_name} needs members",
        "preview_text": "Here's a 30-second action that 3x's your join rate.",
        "body_paragraphs": [
            "Hey {first_name},",
            "{community_name} has been live for a bit and you've got {member_count} member{member_plural} so far. Communities don't grow themselves — but the next 24 hours can change that.",
            "Your fastest lever: drop your invite link in your group chats. Communities with cover images and 5+ members grow 3x faster — and your link looks great once you have those.",
            "We've made the share image for you. One tap and it's ready for WhatsApp, Discord, or wherever your NBA people hang out.",
        ],
        "cta_text": "Open share kit",
        "cta_deeplink": "predictify://community/{community_id}/share",
    },
    "referral_invite": {
        "subject": "Get free Pro by inviting one NBA friend",
        "preview_text": "1 referral = 1 month free for both of you.",
        "body_paragraphs": [
            "Hey {first_name},",
            "You've been making picks consistently — the part most users skip. Now the easy bonus: invite one friend who watches the same games you do, and you both get a free month of Predictify Pro the moment they sign up.",
            "Why we do this: friends who predict together stick around 4x longer than solo users. Better for everyone — including us.",
            "Tap below to grab your unique invite link. Send it to one person in your group chat. Done.",
        ],
        "cta_text": "Get my invite link",
        "cta_deeplink": "predictify://referral",
    },
    "community_invite": {
        "subject": "Predict together — {recommended_community_name} is for fans like you",
        "preview_text": "{member_count} members. {league_short}. Free to join.",
        "body_paragraphs": [
            "Hey {first_name},",
            "Picking games alone is fine. Picking with people who follow the same teams? Way better.",
            "{recommended_community_name} is a Predictify community for {league_short} fans — {member_count} members, owned by {owner_name}, daily AI-assisted picks. You'll see what others are calling and how the room reacts.",
            "Join free. You don't pay a thing — just show up and predict.",
        ],
        "cta_text": "Join {recommended_community_name}",
        "cta_deeplink": "predictify://community/{community_id}",
    },
}

count = 0
for kind, data in T.items():
    doc = {"kind": kind, "language": "en", **data}
    path = os.path.join(OUT, f"{kind}_en.json")
    with open(path, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    count += 1
print(f"Wrote {count} NBA English templates to {OUT}")
