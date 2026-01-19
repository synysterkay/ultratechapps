"""
Twitter/X Publisher using tweepy library
Posts article links to help with SEO/indexing
"""
import os
import tweepy


class TwitterPublisher:
    def __init__(self):
        # Twitter API v2 credentials
        api_key = os.getenv('TWITTER_API_KEY')
        api_secret = os.getenv('TWITTER_API_SECRET')
        access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        
        if not all([api_key, api_secret, access_token, access_token_secret]):
            print("⚠️ Twitter credentials not configured")
            self.enabled = False
            return
        
        try:
            # Initialize Twitter client (API v2)
            self.client = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            self.enabled = True
            print("✅ Twitter client initialized")
        except Exception as e:
            print(f"❌ Error initializing Twitter client: {e}")
            self.enabled = False
    
    def post(self, text, link=None):
        """
        Post a tweet
        
        Args:
            text: Tweet text (max 280 chars)
            link: Optional URL to include
            
        Returns:
            Response dictionary
        """
        if not self.enabled:
            return {'success': False, 'error': 'Twitter publisher not enabled'}
        
        try:
            # Append link if provided and not already in text
            if link and link not in text:
                full_text = f"{text}\n\n{link}"
            else:
                full_text = text
            
            # Truncate if too long (Twitter counts URLs as ~23 chars)
            if len(full_text) > 280:
                # Leave room for link
                max_text = 280 - 25 if link else 280
                full_text = text[:max_text-3] + "..."
                if link:
                    full_text += f"\n\n{link}"
            
            response = self.client.create_tweet(text=full_text)
            
            print(f"✅ Posted to Twitter: {full_text[:50]}...")
            return {
                'success': True,
                'tweet_id': response.data['id'],
                'text': full_text
            }
        except Exception as e:
            print(f"❌ Error posting to Twitter: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def post_article(self, article, article_url):
        """
        Post an article link to Twitter
        
        Args:
            article: Article dict with title, content, app_name
            article_url: URL to the blog post
            
        Returns:
            Response dictionary
        """
        # Create engaging tweet text
        title = article.get('title', '')[:100]
        
        # Various tweet formats to rotate
        tweet_formats = [
            f"📝 New article: {title}",
            f"🔥 Just published: {title}",
            f"💡 {title}",
            f"📖 Read: {title}",
        ]
        
        import random
        text = random.choice(tweet_formats)
        
        return self.post(text, article_url)


# Quick test
if __name__ == "__main__":
    publisher = TwitterPublisher()
    if publisher.enabled:
        result = publisher.post("Test tweet from marketing automation 🚀", "https://bestaiapps.site/")
        print(result)
    else:
        print("Twitter not configured. Set these environment variables:")
        print("  - TWITTER_API_KEY")
        print("  - TWITTER_API_SECRET")
        print("  - TWITTER_ACCESS_TOKEN")
        print("  - TWITTER_ACCESS_TOKEN_SECRET")
