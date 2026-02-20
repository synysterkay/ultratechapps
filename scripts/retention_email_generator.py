#!/usr/bin/env python3
"""
Retention Email Generator
Uses DeepSeek API to generate 30 high-conversion retention emails per app.
A full 30-day drip campaign targeting every stage of the user journey.
"""
import os
import json
import re
import requests
import time
from pathlib import Path


# 30-day retention email funnel sequence
EMAIL_SEQUENCE = [
    # ── WEEK 1: ACTIVATION & FIRST VALUE ──────────────────
    {
        "day": 0,
        "type": "welcome_quick_win",
        "goal": "Get them to open the app RIGHT NOW",
        "psychology": "Excitement + instant gratification",
        "angle": "Show the ONE feature that delivers value in 30 seconds",
    },
    {
        "day": 1,
        "type": "hidden_feature",
        "goal": "Show them something they missed",
        "psychology": "Curiosity + fear of missing out",
        "angle": "Most users skip this feature but it's the best part",
    },
    {
        "day": 2,
        "type": "quick_tip",
        "goal": "Deliver a 60-second actionable tip",
        "psychology": "Micro-commitment + competence building",
        "angle": "One tiny trick that makes a noticeable difference right away",
    },
    {
        "day": 3,
        "type": "social_proof_fomo",
        "goal": "Make them feel they're falling behind",
        "psychology": "Social proof + FOMO + belonging",
        "angle": "X users did THIS today - here's what happened",
    },
    {
        "day": 4,
        "type": "behind_the_scenes",
        "goal": "Build personal connection with the developer",
        "psychology": "Authenticity + relatability + parasocial bond",
        "angle": "Why I built this feature at 2AM - the real story",
    },
    {
        "day": 5,
        "type": "value_bomb",
        "goal": "Give a pro-level tutorial that makes the app 10x more useful",
        "psychology": "Reciprocity + competence",
        "angle": "Advanced tip/hack that transforms the experience",
    },
    {
        "day": 6,
        "type": "common_mistake",
        "goal": "Warn them about what most users get wrong",
        "psychology": "Loss aversion + authority",
        "angle": "The #1 mistake that ruins your results (and the easy fix)",
    },
    # ── WEEK 2: DEEPENING ENGAGEMENT ─────────────────────
    {
        "day": 7,
        "type": "story_emotional",
        "goal": "Emotional connection through storytelling",
        "psychology": "Narrative transportation + empathy",
        "angle": "Real user success story that mirrors their situation",
    },
    {
        "day": 8,
        "type": "challenge",
        "goal": "Get them to commit to using the app for a specific task",
        "psychology": "Gamification + commitment + consistency",
        "angle": "Try this 3-day challenge and see the difference yourself",
    },
    {
        "day": 9,
        "type": "pro_workflow",
        "goal": "Show how power users use the app differently",
        "psychology": "Aspiration + insider knowledge",
        "angle": "How our top 1% of users set up their workflow",
    },
    {
        "day": 10,
        "type": "reengagement_soft",
        "goal": "Win back users who may be losing interest",
        "psychology": "Loss aversion + curiosity",
        "angle": "We noticed you haven't tried X yet - here's why you should",
    },
    {
        "day": 11,
        "type": "myth_buster",
        "goal": "Destroy a common misconception in their domain",
        "psychology": "Surprise + authority + contrarianism",
        "angle": "Everyone thinks this is true. It's not. Here's proof.",
    },
    {
        "day": 12,
        "type": "feature_deep_dive",
        "goal": "Showcase an underused but powerful feature in detail",
        "psychology": "Discovery + mastery",
        "angle": "This buried feature changed everything for one user",
    },
    {
        "day": 13,
        "type": "comparison",
        "goal": "Show what life looks like WITH vs WITHOUT the app",
        "psychology": "Contrast principle + loss aversion",
        "angle": "Before and after: what 30 days of using this looks like",
    },
    # ── WEEK 3: HABIT FORMATION & COMMUNITY ──────────────
    {
        "day": 14,
        "type": "milestone_checkin",
        "goal": "Celebrate their 2-week mark and show progress",
        "psychology": "Achievement + sunk cost + encouragement",
        "angle": "2 weeks in - here's what you've accomplished (more than you think)",
    },
    {
        "day": 15,
        "type": "exclusive_content",
        "goal": "Deliver insider-only value they can't get anywhere else",
        "psychology": "Exclusivity + reciprocity + VIP feeling",
        "angle": "I only share this with actual users - not on social media",
    },
    {
        "day": 16,
        "type": "community_belonging",
        "goal": "Make them feel part of something bigger",
        "psychology": "Belonging + identity + tribe",
        "angle": "You're now part of a growing group of people who do THIS differently",
    },
    {
        "day": 17,
        "type": "productivity_hack",
        "goal": "Show them how to save time with the app",
        "psychology": "Time scarcity + efficiency + competence",
        "angle": "How to do in 2 minutes what used to take 20",
    },
    {
        "day": 18,
        "type": "emotional_story_2",
        "goal": "Another emotional narrative to deepen connection",
        "psychology": "Narrative transportation + vulnerability",
        "angle": "A message I got from a user last week that stopped me cold",
    },
    {
        "day": 19,
        "type": "power_user_tip",
        "goal": "Advanced trick that separates beginners from pros",
        "psychology": "Mastery + insider knowledge + aspiration",
        "angle": "The settings tweak that 95% of users don't know about",
    },
    {
        "day": 20,
        "type": "surprise_bonus",
        "goal": "Unexpected value drop to spike engagement",
        "psychology": "Surprise + delight + reciprocity",
        "angle": "I made something extra for you - wasn't planning to share this",
    },
    # ── WEEK 4: CONVERSION & LOYALTY ─────────────────────
    {
        "day": 21,
        "type": "habit_builder",
        "goal": "Help them build a daily/weekly habit around the app",
        "psychology": "Habit loop + consistency + identity",
        "angle": "The 3-minute routine that makes this app 10x more effective",
    },
    {
        "day": 22,
        "type": "advanced_feature",
        "goal": "Unlock a feature they've never tried",
        "psychology": "Discovery + competence + novelty",
        "angle": "You've been using the app for 3 weeks and still haven't tried THIS?",
    },
    {
        "day": 23,
        "type": "external_validation",
        "goal": "Share third-party credibility and press",
        "psychology": "Authority + social proof + credibility",
        "angle": "What experts/reviewers are saying about this approach",
    },
    {
        "day": 24,
        "type": "personal_note",
        "goal": "Raw, honest 1-on-1 message from the developer",
        "psychology": "Vulnerability + authenticity + connection",
        "angle": "I don't usually write emails like this, but...",
    },
    {
        "day": 25,
        "type": "case_study",
        "goal": "Detailed before/after transformation story",
        "psychology": "Proof + inspiration + possibility",
        "angle": "From skeptic to evangelist: one user's 30-day journey",
    },
    {
        "day": 26,
        "type": "sneak_peek",
        "goal": "Preview upcoming features to build excitement",
        "psychology": "Anticipation + exclusivity + investment",
        "angle": "Here's what's coming next (you heard it here first)",
    },
    {
        "day": 27,
        "type": "gratitude",
        "goal": "Thank them for being a user and reinforce value",
        "psychology": "Reciprocity + appreciation + loyalty",
        "angle": "Honestly, building this wouldn't mean anything without people like you",
    },
    {
        "day": 28,
        "type": "challenge_results",
        "goal": "Show aggregate results from the user community",
        "psychology": "Social proof + FOMO + celebration",
        "angle": "This month's numbers are in - and they're insane",
    },
    {
        "day": 29,
        "type": "vip_offer",
        "goal": "Exclusive upgrade or premium offer with real deadline",
        "psychology": "Scarcity + exclusivity + deadline + value stack",
        "angle": "I set something aside for 30-day users only - expires tomorrow",
    },
    {
        "day": 30,
        "type": "loyalty_farewell",
        "goal": "Close the loop, convert to power user or ambassador",
        "psychology": "Completion + identity shift + next chapter",
        "angle": "30 days in. You're not a new user anymore - here's what comes next",
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
        "core_pain": "Running out of date ideas, routine killing romance, partner feels neglected",
        "killer_features": [
            "AI generates personalized date ideas based on your interests",
            "Budget-friendly to luxury options",
            "Surprise date planner - one partner plans, the other is surprised",
            "Local venue and activity discovery",
            "Date history tracking - never repeat a boring date",
            "Shared wishlist for future date dreams",
        ],
        "social_proof": "230+ couples planning better dates, 92% say it improved their relationship",
        "emotional_hooks": ["keeping the spark alive", "making memories", "showing you care", "avoiding the routine trap"],
        "tone": "Like a fun, slightly romantic friend who always has the best date ideas",
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
    "Smart Notes - AI Meeting Summary": {
        "target_audience": "Professionals, students, anyone in meetings who needs to capture everything",
        "core_pain": "Missing key points in meetings, spending hours organizing notes, forgetting action items",
        "killer_features": [
            "AI transcribes meetings in real-time",
            "Auto-generates summaries with key decisions and action items",
            "Smart search across all your notes",
            "Share meeting summaries with team in one tap",
            "Voice-to-text for quick note capture",
            "Organize notes by project, meeting, or topic automatically",
        ],
        "social_proof": "100+ professionals saving 5+ hours per week on note-taking",
        "emotional_hooks": ["never miss a key point again", "look like the most organized person in the room", "reclaim your focus", "stop writing and start listening"],
        "tone": "Like a productivity-obsessed colleague sharing their secret weapon",
    },
    "Predictify": {
        "target_audience": "Soccer/football fans who want smarter predictions and data-driven insights",
        "core_pain": "Bad predictions, unreliable tips, missing value bets, no data to back up gut feelings",
        "killer_features": [
            "AI analyzes thousands of variables per match for accurate score predictions",
            "Coverage of Premier League, La Liga, Bundesliga, Serie A, Ligue 1, MLS, Champions League",
            "Deep player stats: xG, possession, defensive strength, attacking efficiency",
            "Head-to-head history and tactical analysis",
            "Confidence scores for every prediction",
            "Free credits by sharing + Premium unlimited access ($12.99/mo with 3-day trial)",
        ],
        "social_proof": "Thousands of match predictions analyzed, trusted by football fans worldwide",
        "emotional_hooks": ["stop guessing and start knowing", "be the smartest fan in the room", "never miss a winning insight", "data beats gut feeling"],
        "tone": "Like a sharp football-obsessed friend who always has the stats to back it up",
        "subscription": {
            "monthly": "$12.99/month",
            "trial": "3-day free trial",
            "cta": "Start Free Trial",
        },
    },
}


class RetentionEmailGenerator:
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.api_url = 'https://api.deepseek.com/v1/chat/completions'
        self.cache_dir = Path(__file__).parent.parent / 'cache' / 'retention_emails'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")
    
    def _get_cache_path(self, app_name, email_number, language='en'):
        """Get cache file path for a specific app's email number and language"""
        safe_name = re.sub(r'[^a-z0-9]+', '_', app_name.lower()).strip('_')
        if language and language != 'en':
            return self.cache_dir / f"{safe_name}_{language}_email_{email_number}.json"
        return self.cache_dir / f"{safe_name}_email_{email_number}.json"
    
    def _generate_email(self, app_name, email_number, language='en'):
        """Generate a single retention email using DeepSeek"""
        
        sequence = EMAIL_SEQUENCE[email_number - 1]  # 1-indexed
        context = APP_CONTEXT.get(app_name, {})
        
        if not context:
            print(f"   ⚠️ No context defined for {app_name}, using generic")
            return None
        
        # Language instructions
        lang_names = {'en': 'English', 'ar': 'Arabic', 'es': 'Spanish', 'fr': 'French'}
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

THIS IS EMAIL #{email_number} OF 30 in a retention sequence.

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

SUBJECT LINE RULES:
- Maximum clickbait, maximum curiosity gap
- 5-10 words, NO emojis
- Make them NEED to open it
- Use power words: secret, mistake, warning, discovered, confession, truth, hack
- Examples: "I made a huge mistake with this app", "Don't use this feature (until you read this)", "The one thing 90% of users skip", "I wasn't going to send this", "This changes everything about [topic]"

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
    
    def get_email(self, app_name, email_number, max_retries=3, language='en'):
        """
        Get email for app at position email_number (1-30).
        Returns cached version if exists, otherwise generates and caches.
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
        Pre-generate all 30 emails for all apps (or specified apps).
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
                app_languages = ['en', 'ar', 'es', 'fr']
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
