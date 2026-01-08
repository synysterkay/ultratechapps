"""
AI-powered article generation for marketing content
"""
import os
import re
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
        
        # Content types for variety
        self.content_types = [
            "how_to_guide",
            "tips_and_tricks",
            "common_mistakes",
            "best_practices",
            "problem_solving",
            "beginner_guide",
            "comparison",
            "case_study"
        ]
    
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
    
    def generate_article(self, app_info, niche_info, max_retries=1):
        """
        Generate a complete marketing article
        
        Args:
            app_info: Dict with app_name, google_play_url, app_store_url
            niche_info: Dict with niche information from NicheDetector
            max_retries: Number of retries if generation fails (default 1)
            
        Returns:
            Dictionary with article content and metadata
        """
        topic = self._get_next_topic(app_info['name'], niche_info)
        niche = niche_info['primary_niche']
        
        # Single generation attempt - no duplicate checking against self
        for attempt in range(max_retries):
            print(f"📝 Generating article for {app_info['name']}...")
            
            prompt = f"""Write a high-quality, SEO-optimized marketing article designed to RANK on Google page 1.

App Information:
- Name: {app_info['name']}
- Niche: {niche}
- Target Audience: {niche_info.get('target_audience', 'mobile users')}
- Google Play: {app_info['google_play_url']}
- App Store: {app_info['app_store_url']}

Topic: {topic}

SEO OPTIMIZATION REQUIREMENTS (CRITICAL FOR RANKING):
1. PRIMARY KEYWORD: Create a search-intent focused keyword with 500+ monthly searches
   - Examples: "best {niche} app 2026", "how to solve problem faster", "{niche} tips for beginners"
   - Place in: Title (beginning), first paragraph, at least 3 H2 headers
2. LONG-TAIL KEYWORDS (4-6 keywords): Target low-competition, high-intent searches
   - Format: "[primary keyword] + modifier" (e.g., "for Android", "free", "without account")
3. LSI KEYWORDS (10-15 terms): Semantic variations Google expects to see
   - Spread naturally across headers, lists, and body paragraphs
4. TITLE OPTIMIZATION (60 char max):
   - Formula: [Number] + [Primary Keyword] + [Power Word] + [Benefit]
   - Power words: Ultimate, Complete, Essential, Proven, Secret, Easy, Fast
   - Include year "2026" for freshness signal
   - Example: "15 AI Meeting Tools to 10x Productivity in 2026"
5. META DESCRIPTION (150-160 char): Compelling summary with primary keyword + CTA
6. HEADER HIERARCHY (H2/H3 with keywords):
   - H2: Question format ("How to...", "Why...", "What is...")
   - Include primary/LSI keywords in every H2
   - Example: "How to Choose the Best {niche} App for Your Needs"
7. FEATURED SNIPPET TARGETING:
   - Add boxed "Quick Answer" section (40-50 words)
   - Use numbered/bulleted lists for step-by-step content
   - Include comparison tables where relevant
8. INTERNAL LINKING: Mention related topics with anchor text (simulate internal links)
9. KEYWORD DENSITY: Primary 1-2%, LSI 0.5-1% (natural, not stuffed)
10. E-E-A-T SIGNALS: Add experience/expertise indicators, specific data, real examples

IMAGE REQUIREMENTS (CRITICAL FOR ENGAGEMENT):
- Include 3-4 relevant Unsplash image links throughout the article
- Format: ![Alt text with keyword](https://images.unsplash.com/photo-[id]?w=1200&q=80)
- Alt text MUST contain primary or LSI keywords
- Place images: After introduction, between major sections, before conclusion
- Choose images matching: {niche}, productivity, technology, mobile apps
- Example: ![AI note taking app dashboard](https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=1200&q=80)

CONTENT REQUIREMENTS:
- Length: 1200-1800 words (long-form ranks better)
- Include: statistics, specific numbers, timeframes (e.g., "save 5 hours weekly")
- Answer: WHO (target user), WHAT (solution), WHY (benefits), HOW (steps), WHEN (use cases)
- Use schema-friendly formats: step-by-step lists, comparison tables, FAQs
- Naturally integrate app store links 2-3 times (not just end)
- Add "Quick Takeaways" box at top (bulleted list, 3-5 points)
- End with: "Built by an indie developer who ships apps every day."
- Maximum 2 emojis total

Article Structure (SEO-Optimized):
1. TITLE: [Number] [Primary Keyword] [Power Word] [Benefit] [Year]
2. META DESCRIPTION: [Primary keyword + benefit + CTA] (150-160 char)
3. Quick Takeaways (bulleted, 3-5 key points)
4. Introduction (100-150 words)
   - Hook with relatable problem
   - Include primary keyword in first sentence
   - Promise specific outcome
5. [IMAGE 1] - Relevant hero image
6. Main Content (4-6 H2 sections with LSI keywords)
   - Section 1: "What is [Primary Keyword]?" (definition + context)
   - Section 2: "Why [LSI Keyword] Matters in 2026" (benefits + data)
   - Section 3: "How to [Action] Step-by-Step" (numbered list)
   - [IMAGE 2] - Process or example image
   - Section 4: "Common Mistakes to Avoid" (bulleted list)
   - Section 5: "[LSI Keyword]: Tips from Experts" (actionable advice)
   - [IMAGE 3] - Results or comparison image
   - Section 6: "Best Tools for [Primary Keyword]" (mention app + links naturally)
7. FAQ Section (3-5 questions with H3 headers)
8. [IMAGE 4] - Conclusion or CTA image
9. Conclusion (Call-to-action + indie developer signature)

Write the complete SEO-optimized article in Markdown format with Unsplash images."""

            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You are an expert content writer specializing in practical, SEO-optimized articles for indie app marketing. You write authentic, helpful content that provides real value."},
                        {"role": "user", "content": prompt}
                    ],0.9,
                    max_tokens=3000,
                    top_p=0.95
                )
                
                article_content = response.choices[0].message.content.strip()
                
                # Validate content quality
                if not self._validate_article(article_content, app_info):
                    print(f"⚠️ Article validation failed, retrying...")
                    continue
                
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
                )f"{topic} - {self.content_types[attempt % len(self.content_types)]}"
                    continue
                
                # Extract metadata
                title = self._extract_title(article_content)
                keywords = self._extract_keywords(article_content, niche)
                
                # Track topic usage
                self.cache.add_topic(app_info['name'], topic)
                
                article = {
                    'title': title,
                    'content': article_content,
                    'topic': topic,
                    'niche': niche,
                    'keywords': keywords,
                    'app_name': app_info['name'],
                    'word_count': len(article_content.split()),
                    'generated_at': datetime.now().isoformat(),
                    'google_play_url': app_info['google_play_url'],
                    'app_store_url': app_info['app_store_url']
                }
                
                print(f"✅ Article generated: {title} ({article['word_count']} words)")
                return article
                
            except Exception as e:
                print(f"❌ Error generating ar{e}")
                if attempt == max_retries - 1:
                    raise
        
        raise Exception(f"Failed to generate unique article after {max_retries} attempts")
    
    def _validate_article(self, content, app_info):
        """Validate article meets requirements"""
        word_count = len(content.split())
        
        checks = {
            'length': 800 <= word_count <= 1500,
            'has_title': content.startswith('#'),
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
