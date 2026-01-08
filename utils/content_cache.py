"""
Content caching utilities to avoid regenerating the same content
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

class ContentCache:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def _get_cache_key(self, app_name, content_type):
        """Generate a cache key from app name and content type"""
        return hashlib.md5(f"{app_name}_{content_type}".encode()).hexdigest()
    
    def _get_cache_file(self, cache_key):
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, app_name, content_type, max_age_days=30):
        """
        Retrieve cached content if it exists and is not too old
        
        Args:
            app_name: Name of the app
            content_type: Type of content (niche, article, etc.)
            max_age_days: Maximum age in days before cache is considered stale
            
        Returns:
            Cached content or None if not found/expired
        """
        cache_key = self._get_cache_key(app_name, content_type)
        cache_file = self._get_cache_file(cache_key)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if cache is expired
            cached_time = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - cached_time > timedelta(days=max_age_days):
                return None
            
            return data['content']
        except Exception as e:
            print(f"Error reading cache: {e}")
            return None
    
    def set(self, app_name, content_type, content):
        """
        Store content in cache
        
        Args:
            app_name: Name of the app
            content_type: Type of content
            content: Content to cache
        """
        cache_key = self._get_cache_key(app_name, content_type)
        cache_file = self._get_cache_file(cache_key)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'app_name': app_name,
            'content_type': content_type,
            'content': content
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error writing cache: {e}")
    
    def clear_old_cache(self, max_age_days=30):
        """Remove cache files older than max_age_days"""
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                cached_time = datetime.fromisoformat(data['timestamp'])
                
                if cached_time < cutoff_time:
                    cache_file.unlink()
                    print(f"Removed old cache: {cache_file.name}")
            except Exception as e:
                print(f"Error checking cache file {cache_file}: {e}")
    
    def get_topic_history(self, app_name):
        """Get list of previously used topics for an app"""
        cache_key = self._get_cache_key(app_name, "topic_history")
        cache_file = self._get_cache_file(cache_key)
        
        if not cache_file.exists():
            return []
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('topics', [])
        except Exception as e:
            print(f"Error reading topic history: {e}")
            return []
    
    def add_topic(self, app_name, topic):
        """Add a topic to the app's history"""
        topics = self.get_topic_history(app_name)
        
        # Add topic with timestamp
        topics.append({
            'topic': topic,
            'timestamp': datetime.now().isoformat()
        })
        
        cache_key = self._get_cache_key(app_name, "topic_history")
        cache_file = self._get_cache_file(cache_key)
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'app_name': app_name,
            'topics': topics
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving topic history: {e}")
