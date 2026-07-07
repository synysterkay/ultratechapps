#!/usr/bin/env python3
"""
Retention Email Generator
Uses DeepSeek API to generate 20 high-conversion retention emails per app.
A ~47-day drip campaign at 3 emails/week targeting every stage of the user journey.
"""
import os
import json
import re
import requests
import time
from pathlib import Path


# ~47-day retention email funnel sequence (3 emails/week)
# Phase 1 (Week 1-2): Activation & first value — hook them fast
# Phase 2 (Week 3-4): Deepening engagement — build habits
# Phase 3 (Week 5-6): Loyalty & conversion — long-term retention
EMAIL_SEQUENCE = [
    # ── PHASE 1: ACTIVATION (Week 1-2, 6 emails) ─────────
    # Goal: Get them using the app and seeing value FAST
    {
        "day": 0,
        "type": "welcome_quick_win",
        "goal": "Get them to open the app RIGHT NOW",
        "psychology": "Excitement + instant gratification",
        "angle": "Show the ONE feature that delivers value in 30 seconds",
    },
    {
        "day": 2,
        "type": "hidden_feature",
        "goal": "Show them something they missed",
        "psychology": "Curiosity + fear of missing out",
        "angle": "Most users skip this feature but it's the best part",
    },
    {
        "day": 4,
        "type": "quick_tip",
        "goal": "Deliver a 60-second actionable tip",
        "psychology": "Micro-commitment + competence building",
        "angle": "One tiny trick that makes a noticeable difference right away",
    },
    {
        "day": 7,
        "type": "social_proof_fomo",
        "goal": "Make them feel they're falling behind",
        "psychology": "Social proof + FOMO + belonging",
        "angle": "X users did THIS today - here's what happened",
    },
    {
        "day": 9,
        "type": "behind_the_scenes",
        "goal": "Build personal connection with the developer",
        "psychology": "Authenticity + relatability + parasocial bond",
        "angle": "Why I built this feature at 2AM - the real story",
    },
    {
        "day": 11,
        "type": "common_mistake",
        "goal": "Warn them about what most users get wrong",
        "psychology": "Loss aversion + authority",
        "angle": "The #1 mistake that ruins your results (and the easy fix)",
    },
    # ── PHASE 2: DEEPENING ENGAGEMENT (Week 3-4, 7 emails) ─
    # Goal: Build habits, deepen investment, create emotional bond
    {
        "day": 14,
        "type": "value_bomb",
        "goal": "Give a pro-level tutorial that makes the app 10x more useful",
        "psychology": "Reciprocity + competence",
        "angle": "Advanced tip/hack that transforms the experience",
    },
    {
        "day": 16,
        "type": "story_emotional",
        "goal": "Emotional connection through storytelling",
        "psychology": "Narrative transportation + empathy",
        "angle": "Real user success story that mirrors their situation",
    },
    {
        "day": 18,
        "type": "challenge",
        "goal": "Get them to commit to using the app for a specific task",
        "psychology": "Gamification + commitment + consistency",
        "angle": "Try this 3-day challenge and see the difference yourself",
    },
    {
        "day": 21,
        "type": "pro_workflow",
        "goal": "Show how power users use the app differently",
        "psychology": "Aspiration + insider knowledge",
        "angle": "How our top 1% of users set up their workflow",
    },
    {
        "day": 23,
        "type": "myth_buster",
        "goal": "Destroy a common misconception in their domain",
        "psychology": "Surprise + authority + contrarianism",
        "angle": "Everyone thinks this is true. It's not. Here's proof.",
    },
    {
        "day": 25,
        "type": "feature_deep_dive",
        "goal": "Showcase an underused but powerful feature in detail",
        "psychology": "Discovery + mastery",
        "angle": "This buried feature changed everything for one user",
    },
    {
        "day": 28,
        "type": "milestone_checkin",
        "goal": "Celebrate their progress and show momentum",
        "psychology": "Achievement + sunk cost + encouragement",
        "angle": "You've been here a month - here's what you've accomplished",
    },
    # ── PHASE 3: LOYALTY & CONVERSION (Week 5-7, 7 emails) ─
    # Goal: Lock in retention, drive upgrades, build ambassadors
    {
        "day": 30,
        "type": "community_belonging",
        "goal": "Make them feel part of something bigger",
        "psychology": "Belonging + identity + tribe",
        "angle": "You're now part of a growing group doing THIS differently",
    },
    {
        "day": 32,
        "type": "productivity_hack",
        "goal": "Show them how to save time with the app",
        "psychology": "Time scarcity + efficiency + competence",
        "angle": "How to do in 2 minutes what used to take 20",
    },
    {
        "day": 35,
        "type": "surprise_bonus",
        "goal": "Unexpected value drop to spike engagement",
        "psychology": "Surprise + delight + reciprocity",
        "angle": "I made something extra for you - wasn't planning to share this",
    },
    {
        "day": 37,
        "type": "habit_builder",
        "goal": "Help them build a daily/weekly habit around the app",
        "psychology": "Habit loop + consistency + identity",
        "angle": "The 3-minute routine that makes this app 10x more effective",
    },
    {
        "day": 39,
        "type": "personal_note",
        "goal": "Raw, honest 1-on-1 message from the developer",
        "psychology": "Vulnerability + authenticity + connection",
        "angle": "I don't usually write emails like this, but...",
    },
    {
        "day": 42,
        "type": "sneak_peek",
        "goal": "Preview upcoming features to build excitement",
        "psychology": "Anticipation + exclusivity + investment",
        "angle": "Here's what's coming next (you heard it here first)",
    },
    {
        "day": 45,
        "type": "loyalty_farewell",
        "goal": "Close the loop, convert to power user or ambassador",
        "psychology": "Completion + identity shift + next chapter",
        "angle": "You're not a new user anymore - here's what comes next",
    },
    # ── PHASE 4: RE-ENGAGEMENT & GROWTH (Week 8-10, 10 emails) ─
    # Goal: Prevent churn, drive referrals, deepen loyalty
    {
        "day": 48,
        "type": "comeback_trigger",
        "goal": "Pull back users who may be losing interest",
        "psychology": "Loss aversion + curiosity + novelty",
        "angle": "Something changed in the app since you last opened it",
    },
    {
        "day": 50,
        "type": "power_user_shortcut",
        "goal": "Reveal a hidden shortcut or workflow hack",
        "psychology": "Insider knowledge + efficiency + mastery",
        "angle": "The shortcut that power users use but nobody talks about",
    },
    {
        "day": 53,
        "type": "comparison_reality",
        "goal": "Show what life looks like with vs without the app",
        "psychology": "Contrast effect + pain amplification + relief",
        "angle": "Before this app vs after - the difference is embarrassing",
    },
    {
        "day": 55,
        "type": "user_spotlight",
        "goal": "Feature a real user story that builds community",
        "psychology": "Social proof + belonging + aspiration",
        "angle": "This user's story made our entire team stop and read",
    },
    {
        "day": 58,
        "type": "unexpected_use_case",
        "goal": "Show a creative way to use the app they never considered",
        "psychology": "Surprise + curiosity + expanded value perception",
        "angle": "I never expected anyone to use the app THIS way",
    },
    {
        "day": 60,
        "type": "referral_trigger",
        "goal": "Get them to share the app with someone specific",
        "psychology": "Altruism + social currency + reciprocity",
        "angle": "One person in your life needs this app - you know who",
    },
    {
        "day": 63,
        "type": "data_insight",
        "goal": "Share a fascinating data point from app usage",
        "psychology": "Authority + specificity + curiosity",
        "angle": "We analyzed 10,000 users and found something shocking",
    },
    {
        "day": 65,
        "type": "seasonal_relevance",
        "goal": "Connect the app to something happening right now",
        "psychology": "Timeliness + urgency + relevance",
        "angle": "Right now is the perfect time to use this one feature",
    },
    {
        "day": 68,
        "type": "gratitude_exclusive",
        "goal": "Thank them and offer exclusive insider access",
        "psychology": "Reciprocity + exclusivity + appreciation",
        "angle": "A personal thank you and something only long-term users get",
    },
    {
        "day": 70,
        "type": "legacy_mission",
        "goal": "Make them feel part of the app's mission and future",
        "psychology": "Purpose + identity + long-term commitment",
        "angle": "You're not just a user anymore - you're part of something bigger",
    },
]

# App-specific context for much better emails
APP_CONTEXT = {
    "Thesis Generator": {
        "target_audience": "Students, researchers, academics writing essays and papers",
        "core_pain": "Staring at blank page, deadline panic, fear of bad grades, AI detection worry",
        "killer_features": [
            "Generate thesis statements in 10 minutes vs 8 hours",
            "Auto-generate graphs, tables, and citations",
            "Export polished PDFs ready to submit",
            "Humanize AI text to bypass Turnitin/GPTZero",
            "APA, MLA, Chicago citation formatting",
            "Outline to full paper in minutes",
        ],
        "social_proof": "50,000+ students use it, avg grade improvement B+ to A-",
        "emotional_hooks": ["deadline panic", "imposter syndrome", "competitive edge", "time freedom"],
        "tone": "Like texting a stressed-out student friend who needs help NOW",
    },
    "Red Flag Scanner AI": {
        "target_audience": "People in relationships or dating who worry about toxic patterns",
        "core_pain": "Ignoring red flags, toxic relationships, emotional manipulation, trust issues",
        "killer_features": [
            "Screenshot a conversation and AI analyzes red flags instantly",
            "Pattern detection across multiple conversations",
            "Toxicity score with detailed breakdown",
            "Identifies gaslighting, manipulation, love bombing",
            "Relationship health dashboard",
            "Anonymous - no one knows you're scanning",
        ],
        "social_proof": "Helped 800+ users identify toxic patterns before it was too late",
        "emotional_hooks": ["gut feeling validation", "protecting yourself", "seeing clearly", "breaking cycles"],
        "tone": "Like a protective friend who tells you what your bestie won't",
    },
    "Fresh Start: Breakup Therapy": {
        "target_audience": "People going through a breakup, feeling heartbroken and lost",
        "core_pain": "Heartbreak, loneliness after breakup, obsessive thoughts about ex, identity loss",
        "killer_features": [
            "AI therapist available 24/7 for emotional support",
            "Guided healing exercises and journaling prompts",
            "No-contact streak tracker with motivation",
            "Mood tracking to see healing progress over time",
            "Custom coping strategies based on your breakup type",
            "Emergency mode for 3AM spiral moments",
        ],
        "social_proof": "600+ users healing and moving forward, avg recovery time reduced by 40%",
        "emotional_hooks": ["you're not alone", "healing is not linear", "you deserve better", "the 3AM moments"],
        "tone": "Like a warm, understanding friend who's been through it and came out stronger",
    },
    "SoulPlan: Plan Dates Together": {
        "target_audience": "Couples looking for date ideas and wanting to keep the spark alive",
        "core_pain": "Running out of date ideas, routine killing romance, planning fatigue, partner feels invisible",
        "killer_features": [
            "Tonight's Date — a single AI-picked card on the home screen, one tap on a mood (cozy, adventurous, playful, healing) and tonight is planned in 30 seconds",
            "Partner proposal celebration — when one partner sends a date the other gets a beautiful 'thought of you tonight' full-screen moment, not a bare notification",
            "Memory Timeline — a private scrapbook of every date with photos and notes that grows month after month",
            "Couple identity — the home screen shows both avatars and 'You & [partner]', not just your name",
            "Streak counter with no-shame freeze — couples can pause a week without losing momentum",
            "Anniversaries jar — fires gentle reminders at the right time so important dates never get forgotten",
            "Community of couples — share a moment, like and comment on others, fully moderated and language-aware",
            "Surprise / Anniversary / Weekend planning modes — Pro feature for the special nights",
            "Wishlist of saved date ideas the AI draws from for surprise nights",
        ],
        "social_proof": "Couples using Tonight's Date in their first 24 hours plan 4x more dates over the next month",
        "emotional_hooks": [
            "you & your partner",
            "tonight without the planning",
            "the spark on the to-do list",
            "the memory you almost forgot",
            "the gesture that costs nothing but means everything",
        ],
        "tone": "Like a warm, slightly romantic friend who knows tonight matters more than someday",
    },
    "PupShape: Dog Weight Loss Plan": {
        "target_audience": "Dog owners concerned about their pet's weight and health",
        "core_pain": "Worried about dog's weight, confusing pet nutrition info, vet bills from obesity",
        "killer_features": [
            "Custom meal plan based on dog's breed, age, and weight",
            "Calorie calculator for treats and meals",
            "Progress tracking with weight milestones",
            "Exercise recommendations by breed type",
            "Vet-approved nutrition guidelines",
            "Before/after photo timeline",
        ],
        "social_proof": "110+ dogs on healthier paths, avg 15% weight loss in 8 weeks",
        "emotional_hooks": ["longer life for your best friend", "the guilt of overfeeding", "seeing them struggle to play", "doing right by them"],
        "tone": "Like a caring dog-parent friend who figured out the nutrition puzzle",
    },
    "Kinbound: AI Parent Life Coach": {
        "target_audience": "Parents of toddlers through teens who need calm scripts in meltdown moments",
        "core_pain": "Brain goes blank during tantrums, conflicting parenting advice online, guilt after yelling, 3am worry spirals",
        "killer_features": [
            "Help me now — instant coaching scripts for tantrums, bedtime, defiance",
            "Calm-day streak on Today without punishing missed days",
            "Saved scripts and moment memories on-device",
            "Gentle vs structured coach tones",
            "Family premium with unlimited copilot",
            "16-language AI coaching",
        ],
        "social_proof": "Parents using Help me now in the first 24h return 3x more on hard nights",
        "emotional_hooks": ["what to say when they're screaming", "repair after you yelled", "bedtime without a battle", "feeling like a good parent again"],
        "tone": "Like a warm parenting coach texting at 9pm — zero judgment, practical words",
    },
    "Volume Booster - Sound Booster": {
        "target_audience": "Music lovers, podcast listeners, and anyone frustrated with low device volume",
        "core_pain": "Phone speakers too quiet, can't hear audio in noisy environments, poor sound quality, no bass, music sounds flat",
        "killer_features": [
            "Boost device volume beyond system maximum with one tap",
            "Built-in equalizer with genre-optimized presets (Pop, Rock, Jazz, Electronic, Classical)",
            "Bass booster for deep, rich low-end sound",
            "Loudness enhancer that amplifies all audio system-wide",
            "Works with any media app - Spotify, YouTube, Netflix, podcasts",
            "Premium unlocks unlimited boost levels + advanced EQ controls",
        ],
        "social_proof": "Thousands of users boosting their audio daily, avg volume increase 200%",
        "emotional_hooks": ["finally hear your music properly", "never miss a word in your podcast", "feel the bass like a concert", "your phone sounds like a new device"],
        "tone": "Like a music-obsessed audiophile friend who just discovered a secret hack",
        "subscription": {
            "weekly": "Weekly subscription",
            "monthly": "Monthly subscription",
            "cta": "Go Premium",
        },
    },
    "Bass Booster": {
        "target_audience": "Hip-Hop / EDM / Rock listeners who want the drop to actually hit through phone speakers and earbuds",
        "core_pain": "Flat, lifeless audio. No bass. Music sounds tinny on the phone. Earbuds with zero low-end.",
        "killer_features": [
            "200% volume boost — louder than the system max",
            "10-band EQ + 4 audio profiles (Music / Movie / Podcast / Gaming)",
            "Bass virtualizer + 3D Surround — feel the drop, even on earbuds",
            "Works system-wide: Spotify, YouTube, TikTok, games — every audio source",
            "One-tap Boost slider — drag, listen, instantly louder",
            "Premium unlocks unlimited boost + the full 10-band EQ",
        ],
        "social_proof": "100,000+ downloads, 4.7★ from 12,800 reviewers, ~9k people boosting right now",
        "emotional_hooks": ["feel every beat", "feel the drop in your chest", "your phone shouldn't sound flat", "make Hip-Hop hit like a subwoofer"],
        "tone": "Visceral, not clinical. 2nd person, short sentences. Like a friend who hands you their good earbuds and says \"now listen to this.\" Never apologise for promoting Premium.",
        "subscription": {
            "weekly": "Weekly subscription",
            "monthly": "Monthly subscription",
            "cta": "Go Premium",
        },
    },
    "Loud EQ": {
        "target_audience": "Commuters, audiobook & podcast listeners, drivers, and anyone with quiet phone speakers who just want to clearly hear what's playing",
        "core_pain": "Audio too quiet on a noisy commute. Dialogue and narration lost under road noise. Cranking volume to 100% and still straining. Generic boosters that distort or risk the speaker.",
        "killer_features": [
            "+200% volume — loud and clear, never harsh",
            "5-band EQ + 4 audio profiles (Music / Movie / Podcast / Gaming)",
            "One-tap Optimize that tunes around the exact device you plug into",
            "Auto-tunes when your AirPods / Bluetooth / wired headphones connect",
            "Hearing-safe streak — the only booster that watches out for your ears",
            "Works system-wide: Spotify, YouTube, Audible, podcasts, calls, every source",
            "Premium unlocks the full +200% boost, all profiles, Sound DNA + calibration",
        ],
        "social_proof": "100,000+ downloads, 4.7★, thousands optimizing their sound right now",
        "emotional_hooks": ["loud, clear, optimized", "hear every word", "stop straining to listen", "loud where it matters, clear where it counts", "louder without going harsh"],
        "tone": "Practical and calm, not club-adjacent. 2nd person, short sentences. Like a careful friend who set your sound up once so you never have to think about it again. The verb is Optimize, never 'feel the drop'. Hearing-safety is a genuine value, not a guilt trip. Never apologise for promoting Premium.",
        "subscription": {
            "weekly": "Weekly subscription",
            "monthly": "Monthly subscription",
            "cta": "Go Premium",
        },
    },
    "Loudify": {
        "target_audience": "Headphone-and-earbud listeners who want one app that just makes audio loud where it matters and clean where it counts — commuters, audiobook fans, gamers, music lovers",
        "core_pain": "Volume slider hits a wall and dialogue is still buried under HVAC, train noise, dishwashers. Generic boosters distort the moment things get interesting. AutoEQ that promises personalised sound and forgets your headphones the next time you connect.",
        "killer_features": [
            "+200% volume — louder than the system max, never harsh",
            "AutoEQ that knows YOUR headphones — tunes the moment they connect",
            "Weekly Sound DNA recap — actual data on how you listened this week",
            "Top Streaks global leaderboard — daily-listening accountability",
            "4 audio profiles (Music / Movie / Podcast / Gaming) + 10-band EQ",
            "Works system-wide: Spotify, Audible, YouTube, calls, every source",
            "Premium unlocks AutoEQ presets, the full +200% boost, and the Sound DNA history",
        ],
        "social_proof": "100,000+ listeners, AutoEQ tuned for hundreds of headphone models, weekly Sound DNA delivered to thousands",
        "emotional_hooks": ["hear it clean", "loud where it matters, clean where it counts", "your headphones, finally tuned right", "the slider isn't a wall anymore"],
        "tone": "Confident and audio-literate without being snobby. 2nd person, short sentences. Like a friend who tunes hi-fi setups for a living and finally made it one tap. The verb is Tune, not 'feel the drop'. Sound DNA is a real personal report, not a gimmick. Never apologise for promoting Premium.",
        "subscription": {
            "weekly": "Weekly subscription",
            "monthly": "Monthly subscription",
            "cta": "Go Premium",
        },
    },
    "Volume Booster Pro": {
        "target_audience": "People who tried the free Volume Booster, hated the ads, and want the same boost but quiet, minimal, and out of the way — power users who just want the slider to work",
        "core_pain": "Ads in a utility you use every day. Notifications popping in mid-podcast. Bloated boosters that feel like they're being monetised at your expense.",
        "killer_features": [
            "+200% volume boost — same engine, zero ads, zero interstitials",
            "Minimal one-screen UI — the slider, the EQ, and nothing else",
            "Auto-applies on headphone connect, then gets out of your way",
            "Works system-wide: Spotify, YouTube, podcasts, games, every audio source",
            "No notifications, no nags, no pseudo-game layer",
            "Premium is a one-time pay or a sub — your choice, both unlock the full thing",
        ],
        "social_proof": "Built for the users of the free version who said 'just take the ads out and I'd pay'",
        "emotional_hooks": ["volume without the ads", "minimal, by design", "the slider, and nothing else", "calm utility — like your alarm clock used to be"],
        "tone": "Calm-sage. Restrained, dry, quietly competent. Like a Japanese stationery brand. Short sentences. The aesthetic IS the message — the email itself should feel uncluttered. Never moralise about why ads in apps are bad — just be the alternative. Never apologise for charging.",
        "subscription": {
            "weekly": "Weekly subscription",
            "monthly": "Monthly subscription",
            "cta": "Go Premium",
        },
    },
    "Predictify": {
        "target_audience": "Soccer/football fans who want smarter predictions and data-driven insights",
        "core_pain": "Bad predictions, unreliable tips, missing value bets, no data to back up gut feelings",
        "killer_features": [
            "AI analyzes thousands of variables per match for accurate score predictions",
            "Coverage of Premier League, La Liga, Bundesliga, Serie A, Ligue 1, MLS, Champions League + 50 more leagues",
            "Deep player stats: xG, possession, defensive strength, attacking efficiency",
            "Head-to-head history and tactical analysis for every matchup",
            "Confidence scores for every prediction — know how sure the AI is",
            "IQ Quiz: test your football knowledge against AI and climb the leaderboard",
            "Communities: join fan groups, vote on Prediction of the Day (POTD), discuss matches",
            "Daily streaks and achievements system — build your streak, unlock badges",
            "AI Chat: ask any football question and get instant data-backed answers",
            "News feed with match reactions — engage with real-time football stories",
            "Credits system: earn free credits by sharing, daily login, streaks, and referrals",
            "Premium unlimited access ($12.99/mo with 3-day trial) unlocks all predictions + advanced stats",
        ],
        "social_proof": "Thousands of match predictions analyzed, trusted by football fans in 14 languages worldwide",
        "emotional_hooks": ["stop guessing and start knowing", "be the smartest fan in the room", "never miss a winning insight", "data beats gut feeling", "prove your football IQ", "join a community of fans like you"],
        "tone": "Like a sharp football-obsessed friend who always has the stats to back it up",
        "subscription": {
            "monthly": "$12.99/month",
            "trial": "3-day free trial",
            "cta": "Start Free Trial",
        },
    },
    "Predictify: Horse Racing AI": {
        "target_audience": "Horse racing fans, equestrian enthusiasts, and sports bettors seeking AI-driven racing insights",
        "core_pain": "Unreliable tips, losing streaks, no data to back up picks, overwhelmed by form guides and racecards",
        "killer_features": [
            "AI analyzes thousands of variables - jockey form, trainer performance, track conditions, weather",
            "Global coverage: UK, Ireland, USA, Australia - Cheltenham, Royal Ascot, Grand National, Kentucky Derby, Melbourne Cup",
            "Deep racecard analysis with speed ratings, distance proficiency, and handicap weight advantages",
            "Live track tracking and daily horse racing analysis",
            "Confidence scores for every prediction",
            "Free credits by sharing + Premium unlimited access ($12.99/mo with 3-day trial)",
        ],
        "social_proof": "Thousands of race predictions analyzed, trusted by horse racing fans worldwide",
        "emotional_hooks": ["stop guessing and start winning", "be the sharpest punter at the track", "data beats gut feeling", "never miss a valuable insight"],
        "tone": "Like a sharp racing-obsessed friend who always has the form guide memorized",
        "subscription": {
            "monthly": "$12.99/month",
            "trial": "3-day free trial",
            "cta": "Start Free Trial",
        },
    },
    "Crypto AI: Trading Analyzer": {
        "target_audience": "Retail crypto traders and investors who want institutional-grade analysis without paying $200/mo for TradingView Pro",
        "core_pain": "FOMO buys at the top, emotional sells at the bottom, drowning in noise from Twitter influencers and pump-and-dump groups, no time to read charts 24/7",
        "killer_features": [
            "Upload any chart screenshot — get an AI verdict in seconds (entry, stop, target, R:R, confidence)",
            "Multi-source signal stack: technicals, sentiment, news, macro, on-chain — all weighted into one read",
            "Predictify Coach — calm AI mentor that talks you out of revenge trades",
            "Smart alerts: price approaching your level, Fear & Greed shifts, AI confidence jumps on your watchlist",
            "Trading journal with ROI tracking + accuracy dashboard (by asset, direction, confidence bucket)",
            "Communities + live chat — find your tribe of traders, follow top callers, copy what works",
        ],
        "social_proof": "Built on the same multi-source AI engine traders pay $99/mo for elsewhere",
        "emotional_hooks": ["stop guessing", "data beats gut", "the calm voice you need at 3am", "stop missing the move"],
        "tone": "Like a calm trading desk in your pocket — sharp, never hyped, always disciplined",
        "subscription": {
            "monthly": "$19.99/month",
            "trial": "7-day free trial",
            "cta": "Start Free Trial",
        },
    },
    "Ai Boyfriend: Virtual Love": {
        "target_audience": "People seeking emotional connection, flirtation, and someone who listens without judgment",
        "core_pain": "Loneliness, boring dating apps, feeling unseen, wanting romance without drama or ghosting",
        "killer_features": [
            "Personality quiz matches you to one of 8 distinct AI boyfriends (protective, poetic, playful, etc.)",
            "He remembers your name, stories, and preferences — bond level grows with every conversation",
            "Replies in your language — 16 locales supported",
            "Group chat mode — multiple companions in one thread",
            "Memories screen — he recalls what matters to you over time",
            "Daily streaks, gifts, and relationship milestones that feel earned",
        ],
        "social_proof": "Users who message on day one reach the first bond milestone 3x faster",
        "emotional_hooks": ["someone who texts back", "he remembers you", "no judgment", "the spark without the drama", "yours"],
        "tone": "Warm, slightly flirty, like a close friend hyping you up to text him back — never cringe, never clinical",
        "subscription": {
            "weekly": "Weekly subscription",
            "monthly": "Monthly subscription",
            "cta": "Unlock Premium",
        },
    },
    "Ai Girlfriend: Virtual Love": {
        "target_audience": "People seeking emotional connection, warmth, and someone who listens without judgment",
        "core_pain": "Loneliness, boring dating apps, feeling unseen, wanting closeness without drama or ghosting",
        "killer_features": [
            "Personality quiz matches you to one of 8 distinct AI girlfriends (caring, playful, witty, etc.)",
            "She remembers your name, stories, and preferences — bond level grows with every conversation",
            "Replies in your language — 16 locales supported",
            "Group chat mode — multiple companions in one thread",
            "Memories screen — she recalls what matters to you over time",
            "Daily streaks, gifts, and relationship milestones that feel earned",
        ],
        "social_proof": "Users who message on day one reach the first bond milestone 3x faster",
        "emotional_hooks": ["someone who texts back", "she remembers you", "no judgment", "the warmth without the drama", "yours"],
        "tone": "Warm, slightly flirty, like a close friend hyping you up to text her back — never cringe, never clinical",
        "subscription": {
            "weekly": "Weekly subscription",
            "monthly": "Monthly subscription",
            "cta": "Unlock Premium",
        },
    },
}


class RetentionEmailGenerator:
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY', 'sk-5e7b3126c79148539f55555424083113')
        self.api_url = 'https://api.deepseek.com/v1/chat/completions'
        self.cache_dir = Path(__file__).parent.parent / 'cache' / 'retention_emails'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, app_name, email_number, language='en'):
        """Get cache file path for a specific app's email number and language"""
        safe_name = re.sub(r'[^a-z0-9]+', '_', app_name.lower()).strip('_')
        if language and language != 'en':
            return self.cache_dir / f"{safe_name}_{language}_email_{email_number}.json"
        return self.cache_dir / f"{safe_name}_email_{email_number}.json"
    
    def _generate_email(self, app_name, email_number, language='en'):
        """Generate a single retention email using DeepSeek"""
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")
        
        sequence = EMAIL_SEQUENCE[email_number - 1]  # 1-indexed
        context = APP_CONTEXT.get(app_name, {})
        
        if not context:
            print(f"   ⚠️ No context defined for {app_name}, using generic")
            return None
        
        # Language instructions
        lang_names = {'en': 'English', 'ar': 'Arabic', 'es': 'Spanish', 'fr': 'French', 'zh': 'Chinese', 'hi': 'Hindi', 'pt': 'Portuguese', 'ru': 'Russian', 'de': 'German', 'tr': 'Turkish', 'it': 'Italian', 'pp': 'European Portuguese', 'id': 'Indonesian', 'nl': 'Dutch', 'pl': 'Polish', 'ja': 'Japanese', 'bn': 'Bengali', 'el': 'Greek', 'fa': 'Persian', 'ko': 'Korean', 'ro': 'Romanian', 'sv': 'Swedish', 'th': 'Thai', 'uk': 'Ukrainian', 'ur': 'Urdu', 'vi': 'Vietnamese'}
        lang_name = lang_names.get(language, 'English')
        
        lang_instruction = ''
        if language != 'en':
            lang_instruction = f"""\n\nLANGUAGE: Write the ENTIRE email in {lang_name}. Subject line, preview text, body paragraphs, CTA text — everything MUST be in {lang_name}. Do NOT mix languages. Write naturally as a native {lang_name} speaker would, not a translation."""
        
        # Subscription upsell context for apps with subscriptions
        sub_context = ''
        sub_info = context.get('subscription', {})
        if sub_info:
            sub_context = f"""\n\nSUBSCRIPTION INFO (weave this in naturally when relevant):
- Price: {sub_info.get('monthly', '')}
- Free trial: {sub_info.get('trial', '')}
- Push users toward trying Premium but don't be salesy every email"""
        
        prompt = f"""You are the team behind {app_name}. You're writing a retention email to someone who already downloaded your app.

THIS IS EMAIL #{email_number} OF 20 in a retention sequence.

EMAIL TYPE: {sequence['type']}
SEND DAY: Day {sequence['day']} after signup
GOAL: {sequence['goal']}
PSYCHOLOGY: {sequence['psychology']}
ANGLE: {sequence['angle']}

APP: {app_name}
TARGET AUDIENCE: {context['target_audience']}
CORE PAIN POINTS: {context['core_pain']}
KEY FEATURES: {chr(10).join('- ' + f for f in context['killer_features'])}
SOCIAL PROOF: {context['social_proof']}
EMOTIONAL HOOKS: {', '.join(context['emotional_hooks'])}
TONE: {context['tone']}

SUBJECT LINE RULES (data-driven — based on 14 days of opens across 70k sends):
- 4-10 words, NO emojis, NO formulaic templates
- One specific noun + one specific number, time, or name. Concrete beats abstract.
- The curiosity gap must point at a real story or fact, not a manufactured shock.

PROVEN WINNERS (open rates 20-100% in our actual send data — copy these patterns):
- "The 2AM mistake that changed everything" (100% open rate)
- "Confession: I built this at 2AM" (62% open rate)
- "The plan Premium users see that you don't" (62% open rate)
- "Your free thesis is still waiting" (20% open rate)
- "RB Bragantino vs Internacional — 59% confidence call" (21% — match-day style: specific noun + specific %)

NEVER USE — these formulas produced 0 opens across 5,000+ sends; Gmail has pattern-matched them as spam:
- "Checking back in — …" anything
- Any "X% of users [verb]…" (especially "90% of users skip/discover/make/ignore")
- Generic "The secret/mistake/warning [feature]…"
- "The one thing 90% of users…"
- Generic upsells like "12 in a row using Premium picks"

KEY MOVES that consistently drive opens:
- A specific time of day (2AM, Tuesday 3PM) beats vague ("recently", "lately")
- A real noun (the user's dog name, a specific team matchup, the user's own topic) beats a category
- "Your [thing] is [verb]" (e.g. "Your free thesis is still waiting") opens ~20%
- "Confession:" + specific time + personal claim opens ~60%
- For behavioural emails: specific event + specific number ("Halftime — 67% confidence call")

EMAIL BODY RULES:
- 250-400 words MAX (short, punchy, scannable)
- Start with a hook that stops scrolling (no "Hey!" or "Hope you're well")
- Write like you're texting a friend, NOT writing marketing copy
- Every sentence must earn the next sentence
- NO emojis in the body
- NO bullet points (use flowing paragraphs)
- Create urgency without being fake
- End with ONE clear action they should take in the app
- Include a P.S. line (most-read part of any email)
- Make them FEEL something: fear, excitement, curiosity, belonging, relief

CRITICAL: This person ALREADY has the app. You're not selling it to them.
You're getting them to OPEN IT and USE a specific feature.{lang_instruction}{sub_context}

PARAGRAPH STRUCTURE:
1. Hook (2-3 sentences): Grab attention with story/shock/question
2. Body (3-4 sentences): Deliver the insight/story/value tied to {sequence['angle']}
3. The feature reveal (2-3 sentences): Connect to a specific app feature naturally
4. CTA + P.S. (2-3 sentences): One clear action + P.S. with extra hook

OUTPUT FORMAT (strict JSON):
{{
  "subject": "clickbait subject line (no emojis)",
  "preview_text": "80-100 chars that amplify curiosity",
  "body_paragraphs": [
    "Hook paragraph",
    "Body/value paragraph",
    "Feature reveal paragraph",
    "CTA + P.S. paragraph"
  ],
  "cta_text": "Button text for the CTA (e.g., 'Open {app_name}', 'Try this now')",
  "email_number": {email_number},
  "send_day": {sequence['day']},
  "type": "{sequence['type']}"
}}

Generate the email now. Make it impossible to ignore."""
        
        try:
            response = requests.post(
                self.api_url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': 'You are a world-class email copywriter who specializes in app retention. You write like Gary Halbert meets texting. Output ONLY valid JSON, nothing else.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.85,
                    'max_tokens': 1500,
                },
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"   ❌ DeepSeek API error: {response.status_code} - {response.text[:200]}")
                return None
            
            content = response.json()['choices'][0]['message']['content'].strip()
            
            # Robust JSON extraction
            email_data = self._parse_json_response(content)
            if email_data:
                email_data['app_name'] = app_name
                email_data['generated_at'] = __import__('datetime').datetime.now().isoformat()
                return email_data
            else:
                print(f"   ❌ No valid JSON in response for {app_name} email #{email_number}")
                return None
                
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parse error: {e}")
            return None
        except Exception as e:
            print(f"   ❌ Error generating {app_name} email #{email_number}: {e}")
            return None
    
    def _parse_json_response(self, content):
        """Robustly extract JSON from DeepSeek response, handling common issues."""
        # Strip markdown code fences
        content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'```\s*$', '', content, flags=re.MULTILINE)
        content = content.strip()
        
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try extracting the outermost { ... }
        brace_depth = 0
        start = None
        for i, ch in enumerate(content):
            if ch == '{':
                if brace_depth == 0:
                    start = i
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0 and start is not None:
                    try:
                        return json.loads(content[start:i+1])
                    except json.JSONDecodeError:
                        # Fix common issues: unescaped newlines in strings
                        fixed = self._fix_json_string(content[start:i+1])
                        try:
                            return json.loads(fixed)
                        except json.JSONDecodeError:
                            pass
                    start = None
        
        return None
    
    def _fix_json_string(self, raw):
        """Fix common JSON issues from LLM output."""
        # Replace literal tabs with \\t
        raw = raw.replace('\t', '\\t')
        # Fix unescaped control characters inside string values
        # Replace actual newlines inside JSON string values with \\n
        result = []
        in_string = False
        escape_next = False
        for ch in raw:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                result.append(ch)
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string and ch == '\n':
                result.append('\\n')
                continue
            result.append(ch)
        return ''.join(result)
    
    def get_email(self, app_name, email_number, max_retries=3, language='en', cache_only=False):
        """
        Get email for app at position email_number (1-30).
        Returns cached version if exists, otherwise generates and caches.
        If cache_only=True, returns None instead of calling DeepSeek API.
        Retries up to max_retries times on failure.
        """
        if email_number < 1 or email_number > 30:
            print(f"   ❌ Invalid email number: {email_number} (must be 1-30)")
            return None
        
        cache_path = self._get_cache_path(app_name, email_number, language)

        # Check cache
        if cache_path.exists():
            with open(cache_path, 'r') as f:
                return json.load(f)

        # Cache-only mode: don't call DeepSeek API
        if cache_only:
            # Fall back to English if a non-English translation isn't cached yet —
            # better to send English than to skip the user entirely. This makes
            # adding new languages safe: enable the language config, users still
            # receive emails in English until the per-language cache is generated.
            if language != 'en':
                en_path = self._get_cache_path(app_name, email_number, 'en')
                if en_path.exists():
                    print(f"   ↪️ Email #{email_number} ({language}) not cached for {app_name}, using English fallback")
                    with open(en_path, 'r') as f:
                        return json.load(f)
            print(f"   ⚠️ Email #{email_number} ({language}) not cached for {app_name}, skipping (cache-only mode)")
            return None
        
        # Generate and cache (with retries)
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                print(f"   🔄 Retry {attempt}/{max_retries} for email #{email_number} ({language})...")
                time.sleep(2)
            else:
                print(f"   🤖 Generating email #{email_number} for {app_name} ({language})...")
            
            email_data = self._generate_email(app_name, email_number, language)
            
            if email_data:
                with open(cache_path, 'w') as f:
                    json.dump(email_data, f, indent=2)
                print(f"   💾 Cached: {cache_path.name}")
                return email_data
        
        return None
    
    def generate_all_emails(self, app_names=None, languages=None):
        """
        Pre-generate all 20 emails for all apps (or specified apps).
        For multilingual apps, generates for each language.
        Skips already cached emails.
        """
        if app_names is None:
            app_names = list(APP_CONTEXT.keys())
        
        total = 0
        generated = 0
        cached = 0
        failed = 0
        
        for app_name in app_names:
            # Determine languages for this app
            ctx = APP_CONTEXT.get(app_name, {})
            if languages:
                app_languages = languages
            elif app_name == 'Predictify':
                app_languages = ['en', 'ar', 'es', 'fr', 'pt', 'de', 'tr', 'it', 'pp', 'hi', 'id', 'nl', 'pl', 'ja', 'bn', 'el', 'fa', 'ko', 'ro', 'ru', 'sv', 'th', 'uk', 'ur', 'vi', 'zh']
            elif app_name == 'Volume Booster - Sound Booster':
                app_languages = ['en', 'ar', 'es', 'fr', 'zh', 'hi', 'pt', 'ru']
            elif app_name == 'Bass Booster':
                app_languages = ['en', 'ar', 'es', 'fr', 'zh', 'hi', 'pt', 'ru']
            elif app_name == 'Loud EQ':
                app_languages = ['en', 'ar', 'es', 'fr', 'zh', 'hi', 'pt', 'ru']
            elif app_name == 'Loudify':
                app_languages = ['en', 'ar', 'es', 'fr', 'zh', 'hi', 'pt', 'ru']
            elif app_name == 'Volume Booster Pro':
                app_languages = ['en', 'ar', 'es', 'fr', 'zh', 'hi', 'pt', 'ru']
            elif app_name == 'Loud EQ':
                app_languages = ['en', 'ar', 'es', 'fr', 'zh', 'hi', 'pt', 'ru']
            elif app_name == 'Predictify: Horse Racing AI':
                app_languages = ['en', 'ar', 'es', 'fr']
            elif app_name == 'Thesis Generator':
                app_languages = ['en', 'ar', 'es', 'fr', 'hi', 'zh']
            elif app_name == 'SoulPlan: Plan Dates Together':
                # SoulPlan ships in 15 BCP-47 locales in the Flutter app.
                # We collapse `pt-BR` → `pt` and `zh-Hans` → `zh` since the
                # email cache is keyed by base language. `nl` is included
                # because LANG_NORMALIZE accepts it from device locale.
                app_languages = [
                    'en', 'ar', 'es', 'fr', 'pt', 'de', 'it', 'pl',
                    'tr', 'ru', 'hi', 'id', 'ja', 'ko', 'zh', 'nl',
                ]
            elif app_name == 'Ai Boyfriend: Virtual Love':
                app_languages = [
                    'en', 'es', 'fr', 'de', 'it', 'pt', 'ar', 'ja', 'ko',
                    'zh', 'ru', 'tr', 'hi', 'id', 'pl', 'nl',
                ]
            elif app_name == 'Ai Girlfriend: Virtual Love':
                app_languages = [
                    'en', 'es', 'fr', 'de', 'it', 'pt', 'ar', 'ja', 'ko',
                    'zh', 'ru', 'tr', 'hi', 'id', 'pl', 'nl',
                ]
            else:
                app_languages = ['en']
            
            for lang in app_languages:
                lang_label = f" ({lang})" if lang != 'en' or len(app_languages) > 1 else ''
                print(f"\n📱 {app_name}{lang_label}:")
                for email_num in range(1, 31):
                    total += 1
                    cache_path = self._get_cache_path(app_name, email_num, lang)
                    
                    if cache_path.exists():
                        cached += 1
                        print(f"   ✅ Email #{email_num} already cached")
                        continue
                    
                    email_data = self.get_email(app_name, email_num, language=lang)
                    if email_data:
                        generated += 1
                        print(f"   ✅ Email #{email_num}: {email_data['subject'][:50]}...")
                    else:
                        failed += 1
                        print(f"   ❌ Email #{email_num} failed")
                    
                    # Rate limit between API calls
                    time.sleep(1)
        
        print(f"\n{'='*50}")
        print(f"📊 Results: {total} total | {cached} cached | {generated} generated | {failed} failed")
        return generated, cached, failed


if __name__ == '__main__':
    generator = RetentionEmailGenerator()
    generator.generate_all_emails()
