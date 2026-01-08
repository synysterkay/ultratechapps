"""
Generate social media snippets from articles
"""
import os
import random
from openai import OpenAI

class SnippetGenerator:
    def __init__(self):
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        # Platform specifications
        self.platform_specs = {
            'bluesky': {
                'max_length': 300,
                'emoji_limit': 1,
                'tone': 'friendly and conversational'
            },
            'devto': {
                'max_length': 600,
                'emoji_limit': 0,
                'tone': 'technical and community-focused',
                'tags_count': 4
            },
            'hashnode': {
                'max_length': 600,
                'emoji_limit': 0,
                'tone': 'developer-focused and technical',
                'tags_count': 4
            }
        }
    
    def generate_social_posts(self, article, platform, count=3):
        """
        Generate social media posts from article
        
        Args:
            article: Article dictionary with content
            platform: Platform name (x, bluesky, telegram, etc.)
            count: Number of posts to generate
            
        Returns:
            List of post dictionaries
        """
        if platform not in self.platform_specs:
            raise ValueError(f"Unknown platform: {platform}")
        
        spec = self.platform_specs[platform]
        
        prompt = f"""Extract {count} unique social media posts from this article for {platform}.

Article Title: {article['title']}
Article Content: {article['content'][:1000]}...

App Name: {article['app_name']}
Google Play: {article['google_play_url']}
App Store: {article['app_store_url']}

Requirements:
- Each post must be {spec['max_length']} characters or less
- Maximum {spec['emoji_limit']} emoji per post
- Tone: {spec['tone']}
- Each post should highlight a DIFFERENT insight from the article
- Naturally include ONE app store link (alternate between Google Play and App Store)
- Make posts actionable and valuable
- No hashtags unless platform is X/Twitter
- All {count} posts must be completely unique

Generate {count} posts in this JSON format:
[
  {{"text": "post text here", "link": "store_url"}},
  {{"text": "post text here", "link": "store_url"}},
  {{"text": "post text here", "link": "store_url"}}
]"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"You are a social media expert who creates engaging posts for {platform}. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            import json
            posts = json.loads(result_text)
            
            # Validate and clean posts
            validated_posts = []
            for post in posts[:count]:
                text = post.get('text', '').strip()
                link = post.get('link', article['google_play_url'])
                
                # Ensure length limit
                if len(text) > spec['max_length']:
                    text = text[:spec['max_length']-3] + '...'
                
                validated_posts.append({
                    'text': text,
                    'link': link,
                    'platform': platform,
                    'app_name': article['app_name']
                })
            
            print(f"✅ Generated {len(validated_posts)} posts for {platform}")
            return validated_posts
            
        except Exception as e:
            print(f"❌ Error generating {platform} posts: {e}")
            # Fallback to simple extraction
            return self._fallback_posts(article, platform, count)
    
    def _fallback_posts(self, article, platform, count):
        """Generate simple fallback posts if AI fails"""
        spec = self.platform_specs[platform]
        
        posts = []
        links = [article['google_play_url'], article['app_store_url']]
        
        templates = [
            f"Discover how {article['app_name']} can help with {article['topic']}. {{link}}",
            f"Looking for {article['niche']} solutions? Check out {article['app_name']}: {{link}}",
            f"New article: {article['title']} - Learn more about {article['app_name']}: {{link}}"
        ]
        
        for i in range(count):
            template = templates[i % len(templates)]
            link = links[i % len(links)]
            text = template.replace('{link}', link)
            
            # Truncate if needed
            if len(text) > spec['max_length']:
                text = text[:spec['max_length']-3] + '...'
            
            posts.append({
                'text': text,
                'link': link,
                'platform': platform,
                'app_name': article['app_name']
            })
        
        return posts
    
    def generate_blog_variant(self, article, platform):
        """
        Generate platform-specific blog post variant
        
        Args:
            article: Original article
            platform: devto or hashnode
            
        Returns:
            Dictionary with variant content and metadata
        """
        if platform not in ['devto', 'hashnode']:
            raise ValueError(f"Blog variants only supported for devto and hashnode")
        
        spec = self.platform_specs[platform]
        
        prompt = f"""Rewrite this article for {platform} with a {spec['tone']} tone.

Original Article:
{article['content']}

Requirements:
- Keep the core value and insights
- Adjust tone for {spec['tone']}
- Maintain 800-1200 words
- Keep the app links naturally integrated
- End with: "Built by an indie developer who ships apps every day."
- Make it unique, not just copy-paste
- No emojis

Also suggest {spec['tags_count']} relevant tags for this post.

Respond in this JSON format:
{{
  "content": "rewritten article here",
  "tags": ["tag1", "tag2", "tag3", "tag4"]
}}"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"You are an expert technical writer for {platform}. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            import json
            result = json.loads(result_text)
            
            variant = {
                'title': article['title'],
                'content': result['content'],
                'tags': result.get('tags', [])[:spec['tags_count']],
                'platform': platform,
                'app_name': article['app_name']
            }
            
            print(f"✅ Generated {platform} variant")
            return variant
            
        except Exception as e:
            print(f"❌ Error generating {platform} variant: {e}")
            # Fallback: use original with tags
            return {
                'title': article['title'],
                'content': article['content'],
                'tags': [article['niche'], 'mobile', 'app', 'indie'][:spec['tags_count']],
                'platform': platform,
                'app_name': article['app_name']
            }
    
    def generate_cta_lines(self, article, count=5):
        """Generate call-to-action lines"""
        cta_templates = [
            f"Try {article['app_name']} today",
            f"Download {article['app_name']} now",
            f"Get started with {article['app_name']}",
            f"Explore {article['app_name']} features",
            f"Join thousands using {article['app_name']}"
        ]
        
        return cta_templates[:count]
