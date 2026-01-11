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
        
        base_seo = """
SEO OPTIMIZATION REQUIREMENTS:
1. PRIMARY KEYWORD: Must have 500+ monthly searches, include in title and first paragraph
2. LONG-TAIL KEYWORDS: Include 4-6 secondary keywords naturally
3. LSI KEYWORDS: Use 10-15 related terms throughout
4. READABILITY: Use short paragraphs (2-3 sentences), bullet points, numbered lists
5. WORD COUNT: 1200-1500 words minimum for SEO value

FORMATTING REQUIREMENTS:
- Use H2 (##) and H3 (###) headers for structure
- Include numbered lists and bullet points
- Write conversational, engaging tone
- Use power words and emotional triggers
- Include actionable takeaways
"""
        
        if angle == "app_focused":
            return f"""Write a high-quality, SEO-optimized marketing article promoting {app_name}.

App Information:
- Name: {app_name}
- Description: {app_desc}
- Niche: {niche}
- Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: "[Number] {topic} [Power Word] in 2026"
2. INTRODUCTION: Hook with problem/pain point, present app as solution
3. MAIN BENEFITS: 5-7 key benefits with examples
4. HOW IT WORKS: Step-by-step app usage
5. USER RESULTS: Success stories, statistics
6. COMPARISON: Brief comparison to alternatives
7. CONCLUSION: Call-to-action to try the app

{base_seo}

IMPORTANT: Focus heavily on {app_name} throughout the article. This is direct app promotion.
"""
        
        elif angle == "news_related":
            return f"""Write an SEO-optimized AI news article that naturally features {app_name}.

App Information:
- Name: {app_name}
- Niche: {niche}
- Related Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: "[Recent AI Trend/Breakthrough] + How It Changes {niche} in 2026"
2. NEWS SECTION: Discuss latest AI developments, breakthroughs, or trends (250 words)
3. IMPACT ANALYSIS: What this means for users in {niche} (200 words)
4. PRACTICAL APPLICATIONS: Real-world implications (200 words)
5. APP CONNECTION: Show how {app_name} leverages this trend or helps users adapt (300 words)
6. EXPERT INSIGHTS: Quote industry predictions, add statistics
7. CONCLUSION: Future outlook + mention {app_name} as solution

{base_seo}

TONE: Authoritative news article that builds trust, then naturally introduces {app_name} as relevant tool.
EXAMPLE TITLE: "GPT-5 Launches: 5 Ways It Transforms AI Meeting Notes (+ The Best Tool Using It)"
"""
        
        elif angle == "tutorial":
            return f"""Write an SEO-optimized tutorial teaching a valuable skill, featuring {app_name} as the primary tool.

App Information:
- Name: {app_name}
- Niche: {niche}
- Tutorial Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: "How to [Achieve Specific Result] in [Timeframe] with AI - Step-by-Step Guide"
2. PROBLEM STATEMENT: Why this tutorial matters, what users will learn (150 words)
3. PREREQUISITES: What readers need to get started (100 words)
4. STEP-BY-STEP TUTORIAL: 7-10 detailed steps (600 words)
   - Steps 3-6 should involve using {app_name}
   - Describe specific features and how to use them
   - Include "what you'll see" descriptions
5. COMMON MISTAKES: 3-5 pitfalls to avoid (200 words)
6. ADVANCED TIPS: Power user features of {app_name} (150 words)
7. CONCLUSION: Summary + encourage readers to try {app_name}

{base_seo}

TONE: Helpful instructor voice. Make {app_name} essential to completing the tutorial.
EXAMPLE TITLE: "How to Build an AI Daily Routine in 15 Minutes (Step-by-Step Tutorial)"
"""
        
        elif angle == "comparison":
            return f"""Write an SEO-optimized comparison article featuring {app_name} as a top-tier option.

App Information:
- Name: {app_name}
- Niche: {niche}
- Comparison Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: "[Number] Best {niche} Apps Compared - 2026 Ultimate Guide"
2. INTRODUCTION: What to look for in {niche} apps (150 words)
3. COMPARISON CRITERIA: 5-7 factors that matter most (100 words)
4. APP REVIEWS: Compare 5-7 apps (600 words)
   - Review each app fairly (100 words each)
   - Give {app_name} slightly longer review (150 words)
   - Highlight where {app_name} excels
5. FEATURE COMPARISON: Side-by-side table or bullet comparison
6. WINNER ANNOUNCEMENT: {app_name} wins in [specific criteria] (200 words)
7. HONEST PROS/CONS: Build trust with balanced assessment
8. CONCLUSION: Final recommendation favoring {app_name}

{base_seo}

TONE: Objective reviewer who genuinely found {app_name} to be the best option. Balance fairness with preference.
EXAMPLE TITLE: "7 Best AI Companion Apps Compared: Real Testing, Honest Results (2026)"
"""
        
        elif angle == "problem_solution":
            return f"""Write an SEO-optimized problem-solving article presenting {app_name} as the solution.

App Information:
- Name: {app_name}
- Niche: {niche}
- Problem/Topic: {topic}

ARTICLE STRUCTURE:
1. TITLE: "[Painful Problem] in {niche}? Here's the Fix That Actually Works"
2. PROBLEM DEEP-DIVE: Describe the problem in detail, show empathy (300 words)
   - Use statistics, common complaints
   - Make reader feel understood
3. WHY TRADITIONAL SOLUTIONS FAIL: Explain old approaches (200 words)
4. THE NEW SOLUTION: Introduce AI-powered approach (150 words)
5. MEET {app_name}: Present as the breakthrough solution (400 words)
   - How it solves the specific problem
   - Key features that address pain points
   - User success stories
6. HOW TO GET STARTED: Quick start guide (150 words)
7. CONCLUSION: Life without the problem + CTA

{base_seo}

TONE: Empathetic problem-solver. Build up pain, then present {app_name} as relief.
EXAMPLE TITLE: "Meeting Notes Taking Too Long? This AI Tool Cut My Time by 80%"
"""
        
        else:
            # Fallback to app_focused
            return self._get_prompt_for_angle("app_focused", app_info, niche, topic)
    
    def _determine_category(self, niche, app_name, description):
        """
        Determine blog category based on niche and content
        Categories: ai-tools, productivity, reviews, tutorials, news, guides
        """
        niche_lower = niche.lower()
        app_lower = app_name.lower()
        desc_lower = description.lower()
        
        # Map niches to categories
        if any(word in niche_lower or word in app_lower or word in desc_lower 
               for word in ['ai', 'artificial intelligence', 'machine learning', 'chatbot', 'gpt']):
            return 'ai-tools'
        
        if any(word in niche_lower or word in app_lower or word in desc_lower 
               for word in ['productivity', 'notes', 'meeting', 'organize', 'planner', 'task']):
            return 'productivity'
        
        if any(word in niche_lower or word in desc_lower 
               for word in ['how to', 'guide', 'step', 'tutorial', 'learn']):
            return 'tutorials'
        
        if any(word in niche_lower or word in desc_lower 
               for word in ['review', 'best', 'top', 'comparison']):
            return 'reviews'
        
        if any(word in niche_lower or word in desc_lower 
               for word in ['tips', 'tricks', 'secret', 'hack']):
            return 'guides'
        
        # Default to ai-tools for AI-related content, otherwise guides
        return 'ai-tools' if 'ai' in app_lower else 'guides'
    
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
            from pathlib import Path
            angle_file = Path(f"cache/{cache_key.replace(' ', '_').replace('-', '_')}.json")
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
            from pathlib import Path
            cache_key = f"{app_name}_angles"
            angle_file = Path(f"cache/{cache_key.replace(' ', '_').replace('-', '_')}.json")
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

OUTPUT FORMAT:
Return JSON with:
{{
    "title": "SEO-optimized title (60 chars max)",
    "content": "Full article in Markdown with ## and ### headers",
    "meta_description": "150-160 char compelling summary",
    "primary_keyword": "Main keyword with 500+ monthly searches",
    "long_tail_keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],
    "lsi_keywords": ["term1", "term2", ...up to 15 terms]
}}

DO NOT mention download buttons or CTAs - those will be added automatically.
WRITE NATURALLY - let the value of the content speak for itself, then feature the app as a genuine solution.
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
                    meta_description = article_data.get('meta_description', '')
                    
                    # Use content as article_content for the rest of processing
                    article_content = content
                    
                except (json.JSONDecodeError, AttributeError):
                    # Not JSON format, use as-is (legacy behavior)
                    title = self._extract_title(article_content)
                
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
                
                # Extract metadata
                title = self._extract_title(article_content)
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
                    'featured_image': featured_image
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
        # Create CTA box with download buttons
        def create_cta_box(position):
            cta_messages = {
                'intro': f"**Ready to get started?** Download {app_name} now:",
                'middle': f"**Want to try it yourself?** Get {app_name} today:",
                'end': f"**Don't wait!** Download {app_name} and start now:"
            }
            
            buttons = []
            if google_play_url:
                buttons.append(f"### [📱 Download on Google Play]({google_play_url})")
            if app_store_url:
                buttons.append(f"### [🍎 Download on App Store]({app_store_url})")
            
            if not buttons:
                return ""
            
            cta = f"\n\n---\n\n## {cta_messages[position]}\n\n"
            cta += "\n\n".join(buttons)
            cta += "\n\n---\n\n"
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
        content_preview = ' '.join(article['content'].split()[:50])
        
        # Generate meta title (max 60 chars for Google SERP)
        meta_title = title[:60] if len(title) <= 60 else title[:57] + '...'
        
        # Generate meta description (150-160 chars optimal for SEO)
        meta_description = content_preview[:157] + '...' if len(content_preview) > 160 else content_preview
        
        # Get unique featured image based on niche
        featured_image = self._get_featured_image(article['niche'], article['app_name'])
        
        return {
            'meta_title': meta_title,
            'meta_description': meta_description,
            'featured_image': featured_image,
            'keywords': ', '.join(article['keywords'])
        }
