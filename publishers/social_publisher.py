"""
Social media publishers (X, Bluesky, Telegram)
"""
import os
from atproto import Client as BlueskyClient


class BlueskyPublisher:
    def __init__(self):
        username = os.getenv('BLUESKY_USERNAME')
        password = os.getenv('BLUESKY_PASSWORD')
        
        if not username or not password:
            print("⚠️ Bluesky credentials not configured")
            self.enabled = False
            return
        
        try:
            self.client = BlueskyClient()
            self.client.login(username, password)
            self.enabled = True
        except Exception as e:
            print(f"❌ Error initializing Bluesky client: {e}")
            self.enabled = False
    
    def post(self, text):
        """
        Post to Bluesky
        
        Args:
            text: Post text (max 300 chars)
            
        Returns:
            Response dictionary
        """
        if not self.enabled:
            return {'success': False, 'error': 'Bluesky publisher not enabled'}
        
        try:
            response = self.client.send_post(text=text)
            print(f"✅ Posted to Bluesky")
            return {
                'success': True,
                'uri': response.uri,
                'cid': response.cid
            }
        except Exception as e:
            print(f"❌ Error posting to Bluesky: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class SocialPublisher:
    """Unified interface for all social media platforms"""
    
    def __init__(self):
        self.bluesky = BlueskyPublisher()
    
    def post(self, platform, post_data):
        """
        Post to specified platform
        
        Args:
            platform: Platform name (bluesky)
            post_data: Dictionary with 'text' and optionally 'link'
            
        Returns:
            Response dictionary
        """
        text = post_data.get('text', '')
        link = post_data.get('link', '')
        
        # Append link if not already in text
        if link and link not in text:
            full_text = f"{text}\n\n{link}"
        else:
            full_text = text
        
        if platform == 'bluesky':
            return self.bluesky.post(full_text[:300])
        else:
            return {'success': False, 'error': f'Unknown platform: {platform}'}
