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
        topic_history = self.cache.get_topic_history(app_name)
        recent_topics = [entry['topic'] for entry in topic_history[-10:]]  # Last 10 topics
        
        available_topics = niche_info.get('content_topics', [])
        
        # Find topics not used recently
        unused_topics = [t for t in available_topics if t not in recent_topics]
        
        if not unused_topics:
            # All topics used recently, generate a new variation
            return f"{available_topics[0]} - advanced insights"
        
        return unused_topics[0]
    
    def generate_article(self, app_info, niche_info, max_retries=3):
        """
        Generate a complete marketing article
        
        Args:
            app_info: Dict with app_name, google_play_url, app_store_url
            niche_info: Dict with niche information from NicheDetector
            max_retries: Number of retries if content is duplicate
            
        Returns:
            Dictionary with article content and metadata
        """
        topic = self._get_next_topic(app_info['name'], niche_info)
        niche = niche_info['primary_niche']
        
        for attempt in range(max_retries):
            print(f"📝 Generating article for {app_info['name']} (attempt {attempt + 1}/{max_retries})...")
            
            prompt = f"""Write a high-quality, SEO-optimized marketing article for an indie app.

App Information:
- Name: {app_info['name']}
- Niche: {niche}
- Target Audience: {niche_info.get('target_audience', 'mobile users')}
- Google Play: {app_info['google_play_url']}
- App Store: {app_info['app_store_url']}

Topic: {topic}

Requirements:
1. Length: 800-1200 words
2. Provide PRACTICAL, ACTIONABLE value for users in the {niche} niche
3. Include clear headings (##), bullet points, and examples
4. Naturally integrate the Google Play and App Store links in the article body (not just at the end)
5. Include 6-12 SEO keywords related to {niche}
6. Be unique and engaging - avoid generic content
7. End with: "Built by an indie developer who ships apps every day."
8. Maximum 2 emojis in the entire article
9. Write in a helpful, authentic tone

Article Structure:
- Compelling title
- Introduction (the problem/goal)
- Main content with practical steps/advice
- Common mistakes to avoid
- How helpful tools (mention the app naturally here with links)
- Final motivation/reflection

Write the complete article in Markdown format."""

            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You are an expert content writer specializing in practical, SEO-optimized articles for indie app marketing. You write authentic, helpful content that provides real value."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=3000
                )
                
                article_content = response.choices[0].message.content.strip()
                
                # Validate content
                if not self._validate_article(article_content, app_info):
                    print(f"⚠️ Article validation failed, retrying...")
                    continue
                
                # Check for duplicates
                if not self.duplicate_checker.check_and_add(
                    article_content,
                    threshold=0.85,
                    metadata={'app_name': app_info['name'], 'topic': topic}
                ):
                    print(f"⚠️ Duplicate content detected, retrying with variation...")
                    topic = f"{topic} - {self.content_types[attempt % len(self.content_types)]}"
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
                print(f"❌ Error generating article: {e}")
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
            Dictionary with meta_title, meta_description, og_image_idea
        """
        title = article['title']
        content_preview = ' '.join(article['content'].split()[:50])
        
        # Generate meta title (max 60 chars)
        meta_title = title[:60] if len(title) <= 60 else title[:57] + '...'
        
        # Generate meta description (140-160 chars)
        meta_description = content_preview[:157] + '...' if len(content_preview) > 160 else content_preview
        
        # OG image idea
        og_image_idea = f"Banner image with {article['niche']} theme featuring the app name '{article['app_name']}'"
        
        return {
            'meta_title': meta_title,
            'meta_description': meta_description,
            'og_image_idea': og_image_idea,
            'keywords': ', '.join(article['keywords'])
        }
