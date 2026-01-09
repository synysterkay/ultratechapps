"""
Medium Publisher - Generates RSS feed for Medium import
Since Medium deprecated their posting API, we use their RSS import feature.
"""
import os
from datetime import datetime

class MediumPublisher:
    """
    Medium no longer has a posting API, but they support RSS feed import.
    
    How to set up:
    1. Generate RSS feed from your Jekyll blog
    2. Go to Medium.com -> Settings -> Publishing -> "Import from RSS"
    3. Add your RSS feed URL: https://synysterkay.github.io/ultratechapps/feed.xml
    4. Medium will automatically import new posts
    
    This class tracks Medium import status.
    """
    
    def __init__(self):
        self.rss_feed_url = os.getenv('MEDIUM_RSS_FEED_URL', 
                                       'https://synysterkay.github.io/ultratechapps/feed.xml')
        self.import_enabled = os.getenv('MEDIUM_IMPORT_ENABLED', 'false').lower() == 'true'
        
        if self.import_enabled:
            print("✅ Medium RSS import configured")
            print(f"   RSS feed: {self.rss_feed_url}")
            print("   → Articles will auto-import to Medium")
        else:
            print("⚠️  Medium import not configured.")
            print("   To enable: Set up RSS import in Medium settings")
    
    def publish(self, article, article_url, app_info):
        """
        Medium publishing via RSS import (no direct API action needed)
        
        Returns status indicating RSS feed is available for import
        """
        if not self.import_enabled:
            return {
                'success': False,
                'error': 'Medium RSS import not configured',
                'platform': 'medium',
                'setup_instructions': 'Visit Medium.com -> Settings -> Publishing -> Import from RSS'
            }
        
        # Since Medium pulls from RSS automatically, we just log that the article
        # is available in the feed
        return {
            'success': True,
            'message': 'Article available in RSS feed for Medium import',
            'platform': 'medium',
            'rss_feed_url': self.rss_feed_url,
            'note': 'Medium will auto-import within 24 hours'
        }
    
    def get_setup_instructions(self):
        """Return instructions for setting up Medium RSS import"""
        return {
            'platform': 'Medium',
            'method': 'RSS Import (Automatic)',
            'steps': [
                '1. Go to https://medium.com/me/settings',
                '2. Click "Publishing" in the sidebar',
                '3. Scroll to "Import from RSS"',
                '4. Add your RSS feed URL: ' + self.rss_feed_url,
                '5. Medium will automatically import new posts within 24 hours',
                '6. Set MEDIUM_IMPORT_ENABLED=true in your .env file to track status'
            ],
            'benefits': [
                '✅ Fully automated after setup',
                '✅ No API credentials needed',
                '✅ Medium handles duplicate detection',
                '✅ Preserves article formatting',
                '✅ Free tier sufficient'
            ]
        }
