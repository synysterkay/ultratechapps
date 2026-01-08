"""
Automatic niche detection using AI
"""
import os
from openai import OpenAI
from utils.content_cache import ContentCache

class NicheDetector:
    def __init__(self):
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.cache = ContentCache()
        
        # Predefined niche categories
        self.niche_categories = {
            'dating': ['dating', 'relationships', 'romance', 'matchmaking', 'singles'],
            'fitness': ['fitness', 'workout', 'exercise', 'health', 'gym', 'training'],
            'finance': ['finance', 'money', 'budget', 'investing', 'banking', 'crypto'],
            'productivity': ['productivity', 'task', 'todo', 'organize', 'planning', 'time management'],
            'ai_tools': ['ai', 'artificial intelligence', 'machine learning', 'chatbot', 'gpt'],
            'games': ['game', 'gaming', 'puzzle', 'arcade', 'entertainment'],
            'social': ['social', 'chat', 'messaging', 'community', 'friends'],
            'education': ['education', 'learning', 'study', 'courses', 'tutoring'],
            'travel': ['travel', 'trip', 'vacation', 'booking', 'hotel', 'flight'],
            'food': ['food', 'recipe', 'cooking', 'restaurant', 'delivery'],
            'shopping': ['shopping', 'ecommerce', 'store', 'marketplace', 'deals'],
            'photo_video': ['photo', 'video', 'camera', 'editing', 'filter'],
            'music': ['music', 'audio', 'podcast', 'streaming', 'player'],
            'news': ['news', 'media', 'articles', 'reading'],
            'lifestyle': ['lifestyle', 'wellness', 'meditation', 'mindfulness']
        }
    
    def detect_niche(self, app_name, description, google_play_url="", app_store_url=""):
        """
        Detect app niche using AI
        
        Args:
            app_name: Name of the app
            description: App description
            google_play_url: Google Play store URL (optional)
            app_store_url: App Store URL (optional)
            
        Returns:
            Dictionary with niche info
        """
        # Check cache first
        cached = self.cache.get(app_name, "niche_detection", max_age_days=365)
        if cached:
            print(f"✅ Using cached niche for {app_name}: {cached['primary_niche']}")
            return cached
        
        prompt = f"""Analyze this app and determine its primary niche/category.

App Name: {app_name}
Description: {description}

Based on the app name and description, identify:
1. Primary niche (choose from: dating, fitness, finance, productivity, ai_tools, games, social, education, travel, food, shopping, photo_video, music, news, lifestyle, or other)
2. Secondary niche (if applicable)
3. Target audience
4. Key features/use cases
5. 3-5 content topic ideas for marketing articles

Respond in this exact JSON format:
{{
  "primary_niche": "niche_name",
  "secondary_niche": "niche_name or null",
  "target_audience": "brief description",
  "key_features": ["feature1", "feature2", "feature3"],
  "content_topics": ["topic1", "topic2", "topic3", "topic4", "topic5"]
}}"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing mobile apps and identifying their target market and niche. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON if wrapped in code blocks
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            import json
            result = json.loads(result_text)
            
            # Add app info
            result['app_name'] = app_name
            result['description'] = description
            
            # Cache the result
            self.cache.set(app_name, "niche_detection", result)
            
            print(f"✅ Detected niche for {app_name}: {result['primary_niche']}")
            return result
            
        except Exception as e:
            print(f"❌ Error detecting niche: {e}")
            # Fallback to simple keyword matching
            return self._fallback_niche_detection(app_name, description)
    
    def _fallback_niche_detection(self, app_name, description):
        """Simple keyword-based niche detection as fallback"""
        text = f"{app_name} {description}".lower()
        
        scores = {}
        for niche, keywords in self.niche_categories.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[niche] = score
        
        primary_niche = max(scores, key=scores.get) if scores else 'lifestyle'
        
        result = {
            'app_name': app_name,
            'description': description,
            'primary_niche': primary_niche,
            'secondary_niche': None,
            'target_audience': 'mobile users',
            'key_features': ['user-friendly interface', 'mobile optimization', 'reliable performance'],
            'content_topics': [
                f'how to use {app_name}',
                f'benefits of {app_name}',
                f'tips for {primary_niche}',
                f'{primary_niche} best practices',
                f'{primary_niche} common mistakes'
            ]
        }
        
        # Cache fallback result too
        self.cache.set(app_name, "niche_detection", result)
        
        print(f"✅ Fallback niche detection for {app_name}: {primary_niche}")
        return result
    
    def get_topic_suggestions(self, niche_info):
        """
        Get fresh topic suggestions based on niche
        
        Args:
            niche_info: Niche information dictionary
            
        Returns:
            List of topic suggestions
        """
        return niche_info.get('content_topics', [])
