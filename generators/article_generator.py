"""
AI-powered article generation for marketing content
"""
import os
import re
import json
import random
from datetime import datetime
from openai import OpenAI
from utils.content_cache import ContentCache
from utils.duplicate_checker import DuplicateChecker

class ArticleGenerator:
    def __init__(self):
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.cache = ContentCache()
        self.duplicate_checker = DuplicateChecker()
        
        # Load app images
        with open('app_images.json', 'r') as f:
            self.app_images_data = json.load(f)
        
        # Content angles for variety (mixes marketing with value)
        self.content_angles = [
            "app_focused",      # Direct app promotion with benefits
            "news_related",     # AI news/trends + how app fits in
            "tutorial",         # Teach something + use app as tool
            "comparison",       # Compare solutions + feature your app
            "problem_solution", # Start with problem + app as solution
        ]
    
    def _get_app_image(self, app_index):
        """Get a random image from the 3 available images for this app"""
        for app in self.app_images_data['app_images']:
            if app['app_index'] == app_index:
                # Rotate through the 3 images randomly
                return random.choice(app['images'])
        # Fallback image
        return "https://images.unsplash.com/photo-1551650975-87deedd944c3?w=800&h=500&fit=crop&q=80"
    
    def _get_prompt_for_angle(self, angle, app_info, niche, topic):
        """
        Generate appropriate prompt based on content angle.
        Each angle has a different structure while maintaining app promotion.
        """
        app_name = app_info['name']
        app_desc = app_info.get('description', '')
        
        # Generate a random unique ID to force title variation
        import random
        import time
        unique_seed = f"{int(time.time()) % 10000}{random.randint(1000, 9999)}"
        
        base_seo = f"""
SEO OPTIMIZATION REQUIREMENTS:
1. PRIMARY KEYWORD: Must have 500+ monthly searches, include in title and first paragraph
2. LONG-TAIL KEYWORDS: Include 4-6 secondary keywords naturally
3. LSI KEYWORDS: Use 10-15 related terms throughout
4. READABILITY: Use short paragraphs (2-3 sentences), bullet points, numbered lists
5. WORD COUNT: 1200-1800 words minimum for SEO value
6. META DESCRIPTION: 150-160 chars with primary keyword and emotional hook - MUST BE COMPLETE, NO TRUNCATION
7. FEATURED SNIPPET: Format one section as a direct answer (40-60 words)

TITLE UNIQUENESS REQUIREMENTS (CRITICAL):
- NEVER use these overused patterns: "X Best Apps Compared", "The Secret Nobody Tells You About", "This Changes Everything"
- Add SPECIFIC details: exact numbers, years, timeframes, locations
- Use UNIQUE angles: case studies, experiments, personal stories, data-driven insights
- Include SPECIFICITY: "How I Saved 47 Minutes Daily" vs "How to Save Time"
- Add UNIQUE IDENTIFIERS to titles using seed #{unique_seed} to ensure no duplicates
- Title MUST be different from any previous article - add specific details, dates, or numbers

FORMATTING REQUIREMENTS:
- Use H2 (##) and H3 (###) headers for structure
- Include numbered lists and bullet points
- Write conversational, engaging tone
- Use power words and emotional triggers
- Include actionable takeaways
- Add a **Quick Takeaways** section at the start (bullet points)

CONTENT QUALITY REQUIREMENTS:
- Include REAL statistics and data points (cite sources)
- Add SPECIFIC examples with names, numbers, and outcomes
- Include ORIGINAL insights not found in typical listicles
- Write ACTIONABLE advice that readers can implement immediately
- Add EXPERT perspectives or research citations
- Include CASE STUDIES or real-world examples

EMOTIONAL MARKETING HOOKS:
- Open with a relatable pain point or story ("Ever felt..." "You know that moment when...")
- Use curiosity gaps ("The secret most people miss..." "What nobody tells you about...")
- Add urgency where natural ("Before it's too late" "While it's still free")
- Include social proof language ("Thousands have discovered..." "Join 50,000+ users...")
- Create FOMO ("Don't be the last to..." "Everyone's already using...")
"""
        
        if angle == "app_focused":
            return f"""Write a high-quality, SEO-optimized marketing article promoting {app_name}.

App Information:
- Name: {app_name}
- Description: {app_desc}
- Niche: {niche}
- Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: Create a UNIQUE title using one of these patterns (NEVER repeat previous titles):
   - "I Tested {app_name} for [X Days/Weeks] - Here's What Happened"
   - "From [Specific Problem] to [Specific Solution]: My {app_name} Journey"
   - "[Specific Metric] Improved by [X]% After Using {app_name} (Real Data)"
   - "Why [Specific Group] Are Switching to {app_name} in [Month] 2026"
   - "The [Specific Feature] in {app_name} That Changed How I [Action]"
   Add unique details like dates, numbers, or specific outcomes to make title one-of-a-kind.
2. OPENING HOOK: Start with a SPECIFIC personal story or data point (not generic "Picture this...")
3. QUICK TAKEAWAYS: 4-5 bullet points summarizing key benefits with specific numbers
4. MAIN BENEFITS: 5-7 key benefits with SPECIFIC examples, metrics, and real outcomes
5. HOW IT WORKS: Step-by-step app usage with detailed descriptions
6. USER RESULTS: Specific success stories with names/numbers/timeframes
7. COMPARISON: Data-driven comparison to alternatives
8. CONCLUSION: Urgency + specific call-to-action

{base_seo}

IMPORTANT: Focus heavily on {app_name} throughout the article. Make it SPECIFIC and DATA-DRIVEN.
"""
        
        elif angle == "news_related":
            return f"""Write an SEO-optimized AI news article that naturally features {app_name}.

App Information:
- Name: {app_name}
- Niche: {niche}
- Related Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: Create a UNIQUE news-style title (avoid generic patterns):
   - "[Specific AI Development] in [Month] 2026: What [User Group] Need to Know"
   - "Breaking: [Specific Trend] Is Reshaping [Industry] - Here's the Data"
   - "[X]% of [Group] Now Use AI for [Action]: Inside the Shift"
   - "The [Specific Technology] Breakthrough That's Changing [Specific Use Case]"
   Add specific dates, percentages, or tech names to make unique.
2. OPENING HOOK: Start with a SPECIFIC news event, stat, or development
3. QUICK TAKEAWAYS: 4-5 bullet points on what this means for readers
4. NEWS SECTION: Discuss SPECIFIC AI developments with dates and sources (300 words)
5. IMPACT ANALYSIS: Data-driven analysis for {niche} users (250 words)
6. PRACTICAL APPLICATIONS: Real-world use cases with specific examples (200 words)
7. APP CONNECTION: How {app_name} leverages this trend with specific features (300 words)
8. EXPERT INSIGHTS: Quote industry predictions with sources and statistics
9. CONCLUSION: Future outlook with specific predictions + mention {app_name}

{base_seo}

TONE: Authoritative, data-driven news article. Include specific dates, stats, and sources.
"""
        
        elif angle == "tutorial":
            return f"""Write an SEO-optimized tutorial teaching a valuable skill, featuring {app_name} as the primary tool.

App Information:
- Name: {app_name}
- Niche: {niche}
- Tutorial Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: Create a UNIQUE tutorial title (avoid generic "How to X" patterns):
   - "[Skill Level] Guide: Achieve [Specific Result] in [Exact Timeframe]"
   - "From [Starting Point] to [End Result]: Complete [Topic] Walkthrough"
   - "[Your Role]'s Playbook: [Specific Technique] That Saves [X Hours/Dollars]"
   - "The [X]-Minute [Task] Method I Use Every [Day/Week]"
   Include specific outcomes, timeframes, or user roles.
2. PROBLEM STATEMENT: Why this tutorial matters with specific pain points (150 words)
3. PREREQUISITES: What readers need with specific versions/requirements (100 words)
4. STEP-BY-STEP TUTORIAL: 7-10 detailed steps with screenshots descriptions (700 words)
   - Each step: What to do, what you'll see, common errors
   - Steps 3-6 should involve using {app_name} features
   - Include specific settings and configurations
5. COMMON MISTAKES: 5 specific pitfalls with solutions (200 words)
6. ADVANCED TIPS: Power user features of {app_name} with use cases (150 words)
7. CONCLUSION: Summary of what was learned + next steps with {app_name}

{base_seo}

TONE: Helpful instructor with real experience. Include "when I first tried this" moments.
"""
        
        elif angle == "comparison":
            return f"""Write an SEO-optimized comparison article featuring {app_name} as a top-tier option.

App Information:
- Name: {app_name}
- Niche: {niche}
- Comparison Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: Create a UNIQUE comparison title (avoid generic "X Best Apps" patterns):
   - "I Spent [X Hours] Testing [Specific Apps] - Here's What Actually Works"
   - "[Specific Feature] Face-Off: [App A] vs [App B] vs {app_name} Real Results"
   - "After [X] Months Using [Category] Apps: My Honest Rankings"
   - "[User Type]'s Guide: Which [Category] App Delivers on [Specific Promise]?"
   Make each title specific with timeframes, features, or user perspectives.
2. INTRODUCTION: Your testing methodology and criteria used (150 words)
3. COMPARISON CRITERIA: 5-7 factors with weighted importance (150 words)
4. APP REVIEWS: Compare 5-7 apps with SPECIFIC test results (700 words)
   - Include actual metrics from testing (speed, accuracy, etc.)
   - Provide specific use case scenarios
   - Give {app_name} detailed feature breakdown
5. FEATURE COMPARISON: Data-driven comparison with specific numbers
6. WINNER BY CATEGORY: {app_name} excels in [specific areas] with evidence (200 words)
7. HONEST LIMITATIONS: Build trust with balanced assessment including {app_name}'s weaknesses
8. CONCLUSION: Recommendation based on user type + specific scenarios

{base_seo}

TONE: Experienced reviewer with real testing data. Show methodology, not just opinions.
"""
        
        elif angle == "problem_solution":
            return f"""Write an SEO-optimized problem-solving article presenting {app_name} as the solution.

App Information:
- Name: {app_name}
- Niche: {niche}
- Problem/Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: Create a UNIQUE problem-solution title (avoid generic patterns):
   - "I Fixed My [Specific Problem] in [Timeframe] - Here's the [Metric] Improvement"
   - "From [Hours/Days] Wasted to [Specific Result]: My [Problem] Solution"
   - "[Specific Frustration] Cost Me [Specific Loss] - Until I Found This"
   - "The [Problem] Trap: Why [X%] of [Group] Struggle (And the Fix)"
   Use specific metrics, timeframes, and personal angles.
2. OPENING HOOK: Start with a SPECIFIC personal story with details (time, place, exact situation)
3. QUICK TAKEAWAYS: 4 bullets with specific promises and metrics
4. PROBLEM DEEP-DIVE: Describe with empathy, statistics, and real examples (300 words)
   - Use second person with specific scenarios
   - Include 2-3 statistics with sources
   - Add emotional validation
5. WHY TRADITIONAL SOLUTIONS FAIL: Specific examples of what doesn't work (200 words)
6. THE BREAKTHROUGH: Explain AI-powered approach with technical details (150 words)
7. MEET {app_name}: Present as solution with specific features and results (400 words)
   - Feature-to-benefit mapping
   - Before/after scenarios with metrics
   - Specific user transformation stories
8. HOW TO GET STARTED: Step-by-step quick start (150 words)
9. CONCLUSION: Paint specific future picture + clear next action

{base_seo}

TONE: Empathetic problem-solver with real experience. Show don't tell - use specific numbers and stories.
"""
        
        else:
            # Fallback to app_focused
            return self._get_prompt_for_angle("app_focused", app_info, niche, topic)
    
    def _determine_category(self, niche, app_name, description):
        """
        Determine blog category based on niche and content
        Categories: ai-tools, productivity, reviews, tutorials, news, guides
        Distribute across all 6 categories for balanced homepage
        """
        import random
        
        niche_lower = niche.lower()
        app_lower = app_name.lower()
        desc_lower = description.lower()
        
        # Get category distribution to balance content
        category_counts = self._get_category_counts()
        
        # Priority keywords for specific categories (checked first)
        if any(word in niche_lower or word in desc_lower 
               for word in ['how to', 'step-by-step', 'guide to', 'learn how']):
            return 'tutorials'
        
        if any(word in niche_lower or word in desc_lower 
               for word in ['review', 'best app', 'top app', 'vs', 'comparison', 'rating']):
            return 'reviews'
        
        if any(word in niche_lower or word in desc_lower 
               for word in ['tips', 'tricks', 'secrets', 'hacks', 'ways to']):
            return 'guides'
        
        if any(word in niche_lower or word in app_lower or word in desc_lower 
               for word in ['productivity', 'notes', 'meeting', 'organize', 'planner', 'task', 'efficient']):
            return 'productivity'
        
        # AI tools gets most content but check if we need to balance
        if any(word in app_lower or word in desc_lower 
               for word in ['ai', 'artificial intelligence', 'machine learning', 'chatbot', 'gpt']):
            # If ai-tools has too many, occasionally switch to related categories
            if category_counts.get('ai-tools', 0) > category_counts.get('reviews', 0) + 3:
                return random.choice(['reviews', 'guides'])
            return 'ai-tools'
        
        # Balance distribution - pick category with least articles
        if category_counts:
            min_category = min(category_counts.items(), key=lambda x: x[1])[0]
            if min_category in ['reviews', 'tutorials', 'news', 'guides']:
                return min_category
        
        # Default fallback
        return random.choice(['ai-tools', 'guides', 'reviews'])
    
    def _get_category_counts(self):
        """Get current article count per category"""
        from pathlib import Path
        import re
        
        posts_dir = Path(__file__).parent.parent / '_posts'
        category_counts = {'ai-tools': 0, 'productivity': 0, 'reviews': 0, 
                          'tutorials': 0, 'news': 0, 'guides': 0}
        
        if posts_dir.exists():
            for post_file in posts_dir.glob('*.md'):
                content = post_file.read_text()
                # Extract category from frontmatter
                match = re.search(r'categories:\s*\[([^\]]+)\]', content)
                if match:
                    categories = match.group(1).strip()
                    if categories in category_counts:
                        category_counts[categories] += 1
        
        return category_counts
    
    def _get_next_topic(self, app_name, niche_info):
        """Get next topic to write about, avoiding recent topics"""
        import random
        
        topic_history = self.cache.get_topic_history(app_name)
        recent_topics = [entry['topic'] for entry in topic_history[-10:]]  # Last 10 topics
        
        available_topics = niche_info.get('content_topics', [])
        
        # Find topics not used recently
        unused_topics = [t for t in available_topics if t not in recent_topics]
        
        if not unused_topics:
            # All topics used recently, generate a new variation with randomness
            return f"{available_topics[0]} - {random.choice(['expert tips', 'advanced guide', 'complete walkthrough', 'essential strategies'])}"
        
        # Return random unused topic for variety
        return random.choice(unused_topics)
    
    def _select_content_angle(self, app_name):
        """
        Select content angle for this article, rotating through different types.
        Ensures variety across articles for the same app.
        """
        import random
        
        # Get angle history for this app (stored as custom data, not standard cache)
        cache_key = f"{app_name}_angles"
        angle_history = []
        
        # Try to load from a simple state file
        try:
            import json
            import re
            from pathlib import Path
            safe_name = re.sub(r'[^\w\-]', '_', app_name)  # Remove all non-word chars except dash
            angle_file = Path(f"cache/{safe_name}_angles.json")
            if angle_file.exists():
                with open(angle_file, 'r') as f:
                    data = json.load(f)
                    angle_history = data.get('angles', [])
        except Exception:
            pass
        
        # Find angles not used in last 5 articles
        recent_angles = angle_history[-5:] if len(angle_history) >= 5 else angle_history
        
        # Available angles not used recently
        available_angles = [a for a in self.content_angles if a not in recent_angles]
        
        # If all angles used recently, pick the oldest one
        if not available_angles:
            selected_angle = self.content_angles[0]
        else:
            selected_angle = random.choice(available_angles)
        
        # Update history and save
        angle_history.append(selected_angle)
        
        # Save updated history
        try:
            import json
            import re
            from pathlib import Path
            safe_name = re.sub(r'[^\w\-]', '_', app_name)  # Remove all non-word chars except dash
            angle_file = Path(f"cache/{safe_name}_angles.json")
            angle_file.parent.mkdir(exist_ok=True)
            with open(angle_file, 'w') as f:
                json.dump({'angles': angle_history[-20:]}, f)  # Keep last 20
        except Exception:
            pass
        
        return selected_angle
    
    def generate_article(self, app_info, niche_info, app_index=0, max_retries=2):
        """
        Generate a complete marketing article
        
        Args:
            app_info: Dict with app_name, google_play_url, app_store_url
            niche_info: Dict with niche information from NicheDetector
            app_index: Index of the app (0-12) to select correct images
            max_retries: Number of retries if generation fails (default 1)
            
        Returns:
            Dictionary with article content and metadata
        """
        topic = self._get_next_topic(app_info['name'], niche_info)
        niche = niche_info['primary_niche']
        
        # Select content angle (app_focused, news_related, tutorial, comparison, problem_solution)
        content_angle = self._select_content_angle(app_info['name'])
        print(f"📐 Content angle: {content_angle}")
        
        # Get featured image for this app
        featured_image = self._get_app_image(app_index)
        
        # Single generation attempt - no duplicate checking against self
        for attempt in range(max_retries):
            print(f"📝 Generating article for {app_info['name']}...")
            
            # Get angle-specific prompt
            prompt = self._get_prompt_for_angle(content_angle, app_info, niche, topic)
            
            # Add common instructions to all prompts
            prompt += f"""

TARGET AUDIENCE: {niche_info.get('target_audience', 'mobile users')}
APP LINKS: 
- Google Play: {app_info['google_play_url']}
- App Store: {app_info['app_store_url']}

CRITICAL REQUIREMENTS:
1. Make the article naturally engaging and valuable first
2. Integrate {app_info['name']} seamlessly into the content
3. Use conversational, authoritative tone
4. Include statistics, examples, real scenarios
5. End with strong CTA encouraging readers to try the app

OUTPUT FORMAT - MANDATORY JSON STRUCTURE:
You MUST return ONLY a valid JSON object (no markdown, no code blocks, no extra text).
The JSON must have these exact fields:
{{
    "title": "SEO-optimized title (60 chars max) - REQUIRED",
    "content": "Full article in Markdown with ## and ### headers - start with ## not #",
    "meta_description": "150-160 char compelling summary",
    "primary_keyword": "Main keyword with 500+ monthly searches",
    "long_tail_keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],
    "lsi_keywords": ["term1", "term2", ...up to 15 terms]
}}

CRITICAL: 
- Return ONLY the JSON object, nothing else
- Do NOT wrap in ```json or ``` code blocks
- Title field is MANDATORY and must be compelling
- Content should start with ## heading, NOT # (single hash)
- DO NOT include download buttons or CTAs in content - those will be added automatically

WRITE NATURALLY - let the value of the content speak for itself, then feature the app a. You MUST return valid JSON objects ONLY, with no markdown formatting, no code blocks, and no extra text. Follow the exact JSON structure specified in the prompt
"""
            
            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You are an expert content writer specializing in practical, SEO-optimized articles for indie app marketing. You write authentic, helpful content that provides real value."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.9,
                    max_tokens=3000,
                    top_p=0.95
                )
                
                article_content = response.choices[0].message.content.strip()
                
                # Initialize meta_description (will be set from JSON if available)
                extracted_meta_description = ''
                
                # Try to parse JSON response if wrapped in code blocks
                import json
                try:
                    # Remove code block markers if present
                    if article_content.startswith('```'):
                        # Extract content between ``` markers
                        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', article_content, re.DOTALL)
                        if json_match:
                            article_content = json_match.group(1).strip()
                    
                    # Try parsing as JSON
                    article_data = json.loads(article_content)
                    
                    # Extract fields from JSON
                    title = article_data.get('title', 'Untitled Article')
                    content = article_data.get('content', '')
                    extracted_meta_description = article_data.get('meta_description', '')
                    
                    # Use content as article_content for the rest of processing
                    article_content = content
                    
                except (json.JSONDecodeError, AttributeError):
                    # Not JSON format, use as-is (legacy behavior)
                    # Try to extract title from markdown content
                    title = self._extract_title(article_content)
                    
                    # If still no title, try to create one from the first heading or content
                    if title == "Untitled Article":
                        # Try to find any heading in the content
                        lines = article_content.split('\n')
                        for line in lines[:10]:  # Check first 10 lines
                            line = line.strip()
                            if line.startswith('##'):
                                title = line.replace('##', '').replace('#', '').strip()
                                break
                        
                        # If still no title, generate one from app name and topic
                        if title == "Untitled Article":
                            title = f"{topic[:60]}"  # Use topic as title
                
                # Skip validation - let DeepSeek generate freely
                # Validation was too strict and caused unnecessary retries
                
                # Only check against HISTORICAL content, not current attempts
                # This prevents false duplicates when generating for the same app
                if self.duplicate_checker.is_duplicate(article_content, threshold=0.85):
                    print(f"⚠️ Content too similar to previous articles")
                    if attempt == max_retries - 1:
                        raise Exception("Content too similar to historical articles")
                    continue
                
                # Add to history ONLY if we're keeping this article
                self.duplicate_checker.add_content(
                    article_content,
                    metadata={'app_name': app_info['name'], 'topic': topic}
                )
                
                # Extract keywords (title already extracted from JSON above)
                keywords = self._extract_keywords(article_content, niche)
                
                # Add download CTAs to article content
                article_content = self._inject_download_ctas(
                    article_content, 
                    app_info['name'],
                    app_info.get('google_play_url'),
                    app_info.get('app_store_url')
                )
                
                # Track topic usage
                self.cache.add_topic(app_info['name'], topic)
                
                # Determine category for blog organization
                category = self._determine_category(niche, app_info['name'], app_info.get('description', ''))
                
                article = {
                    'title': title,
                    'content': article_content,
                    'topic': topic,
                    'niche': niche,
                    'category': category,  # Add category field
                    'keywords': keywords,
                    'app_name': app_info['name'],
                    'word_count': len(article_content.split()),
                    'generated_at': datetime.now().isoformat(),
                    'google_play_url': app_info['google_play_url'],
                    'app_store_url': app_info['app_store_url'],
                    'featured_image': featured_image,
                    'meta_description': extracted_meta_description  # Store AI-generated meta description
                }
                
                print(f"✅ Article generated: {title} ({article['word_count']} words) [Category: {category}]")
                return article
                
            except Exception as e:
                print(f"❌ Error generating ar{e}")
                if attempt == max_retries - 1:
                    raise
        
        raise Exception(f"Failed to generate unique article after {max_retries} attempts")
    
    def _validate_article(self, content, app_info):
        """Validate article meets requirements"""
        word_count = len(content.split())
        
        # Check if title exists (flexible - starts with # or first line contains uppercase words)
        has_title = content.startswith('#') or (len(content.split('\n')[0]) > 10 and content.split('\n')[0][0].isupper())
        
        checks = {
            'length': 800 <= word_count <= 1500,
            'has_title': has_title,
            'has_play_link': app_info['google_play_url'] in content,
            'has_store_link': app_info['app_store_url'] in content,
            'has_indie_footer': 'indie developer' in content.lower(),
            'emoji_count': content.count('👍') + content.count('✅') + content.count('💡') + content.count('🚀') + content.count('📱') <= 3
        }
        
        if not all(checks.values()):
            print(f"⚠️ Validation failed: {checks}")
            return False
        
        return True
    
    def _get_featured_image(self, niche, app_name):
        """Get unique featured image URL based on niche"""
        # Map niches to relevant Unsplash search queries
        niche_images = {
            'productivity': 'https://images.unsplash.com/photo-1484480974693-6ca0a78fb36b?w=1200&q=80',
            'health': 'https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1200&q=80',
            'fitness': 'https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=1200&q=80',
            'education': 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=1200&q=80',
            'entertainment': 'https://images.unsplash.com/photo-1522869635100-9f4c5e86aa37?w=1200&q=80',
            'social': 'https://images.unsplash.com/photo-1611162616305-c69b3fa7fbe0?w=1200&q=80',
            'relationships': 'https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=1200&q=80',
            'sports': 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1200&q=80',
            'audio': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200&q=80',
            'pets': 'https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=1200&q=80',
            'tools': 'https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=1200&q=80',
            'ai': 'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=1200&q=80',
            'crypto': 'https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=1200&q=80'
        }
        return niche_images.get(niche.lower(), 'https://images.unsplash.com/photo-1551650975-87deedd944c3?w=1200&q=80')
    
    def _inject_download_ctas(self, content, app_name, google_play_url, app_store_url):
        """
        Inject 3 prominent download CTAs throughout the article:
        - After introduction (first H2)
        - In the middle (after 50% of content)
        - At the end (before conclusion)
        """
        # Create CTA box with styled HTML download buttons
        def create_cta_box(position):
            cta_messages = {
                'intro': f"Ready to get started? Download {app_name} now:",
                'middle': f"Want to try it yourself? Get {app_name} today:",
                'end': f"Don't wait! Download {app_name} and start now:"
            }
            
            buttons = []
            if google_play_url:
                buttons.append(f'<a href="{google_play_url}" class="download-btn android-btn" target="_blank" rel="noopener">📱 Download on Google Play</a>')
            if app_store_url:
                buttons.append(f'<a href="{app_store_url}" class="download-btn ios-btn" target="_blank" rel="noopener">🍎 Download on App Store</a>')
            
            if not buttons:
                return ""
            
            cta = f'\n\n<div class="app-cta-box">\n'
            cta += f'<p class="cta-headline">🚀 {cta_messages[position]}</p>\n'
            cta += '<div class="cta-buttons">\n'
            cta += '\n'.join(buttons)
            cta += '\n</div>\n</div>\n\n'
            return cta
        
        # Split content into sections by H2 headers
        lines = content.split('\n')
        h2_positions = []
        
        for i, line in enumerate(lines):
            if line.startswith('## ') and not line.startswith('###'):
                h2_positions.append(i)
        
        if len(h2_positions) < 3:
            # If not enough H2s, just add CTAs at beginning, middle, end
            total_lines = len(lines)
            positions = [
                int(total_lines * 0.15),  # After intro
                int(total_lines * 0.5),   # Middle
                int(total_lines * 0.85)   # Before conclusion
            ]
        else:
            # Place after 1st H2, middle H2, and 2nd to last H2
            positions = [
                h2_positions[0] + 5,      # After first section
                h2_positions[len(h2_positions)//2] + 5,  # Middle section
                h2_positions[-2] + 5      # Near end
            ]
        
        # Insert CTAs in reverse order to maintain line numbers
        positions.sort(reverse=True)
        cta_types = ['end', 'middle', 'intro']
        
        for pos, cta_type in zip(positions, cta_types):
            if pos < len(lines):
                cta_box = create_cta_box(cta_type)
                lines.insert(pos, cta_box)
        
        return '\n'.join(lines)
    
    def _extract_title(self, content):
        """Extract title from markdown content"""
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                return line.replace('# ', '').strip()
        return "Untitled Article"
    
    def _extract_keywords(self, content, niche):
        """Extract SEO keywords from content"""
        # Simple keyword extraction based on frequency
        words = re.findall(r'\b[a-z]{4,}\b', content.lower())
        word_freq = {}
        
        for word in words:
            if word not in ['this', 'that', 'with', 'from', 'have', 'will', 'your', 'they', 'what', 'when']:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency and take top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, freq in sorted_words[:12] if freq >= 3]
        
        # Always include niche as keyword
        if niche not in keywords:
            keywords.insert(0, niche)
        
        return keywords[:12]
    
    def generate_metadata(self, article):
        """
        Generate SEO metadata for article
        
        Args:
            article: Article dictionary
            
        Returns:
            Dictionary with meta_title, meta_description, featured_image, keywords
        """
        title = article['title']
        
        # Generate meta title (max 60 chars for Google SERP)
        meta_title = title[:60] if len(title) <= 60 else title[:57] + '...'
        
        # Use AI-generated meta description if available, otherwise generate from content
        if article.get('meta_description') and len(article['meta_description']) > 50:
            # Clean up meta description - remove markdown headers and extra whitespace
            meta_description = article['meta_description']
            meta_description = re.sub(r'^#+\s*', '', meta_description)  # Remove # headers
            meta_description = re.sub(r'\*\*([^*]+)\*\*', r'\1', meta_description)  # Remove bold
            meta_description = meta_description.strip()[:160]
        else:
            # Fallback: generate from content (skip markdown headers)
            content_lines = article['content'].split('\n')
            # Find first non-header line with actual content
            content_preview = ''
            for line in content_lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('*'):
                    content_preview = line
                    break
            if not content_preview:
                content_preview = ' '.join(article['content'].split()[:50])
            meta_description = content_preview[:157] + '...' if len(content_preview) > 160 else content_preview
        
        # Sanitize meta_description for YAML frontmatter
        # Replace double quotes with single quotes to avoid YAML parsing issues
        meta_description = meta_description.replace('"', "'")
        # Remove any trailing incomplete quotes or text after ellipsis
        if '...' in meta_description:
            meta_description = meta_description.split('...')[0] + '...'
        # Remove any newlines or extra whitespace
        meta_description = ' '.join(meta_description.split())
        
        # Get unique featured image based on niche
        featured_image = self._get_featured_image(article['niche'], article['app_name'])
        
        return {
            'meta_title': meta_title,
            'meta_description': meta_description,
            'featured_image': featured_image,
            'keywords': ', '.join(article['keywords'])
        }
