"""
Rate limiter to prevent hitting API limits and platform spam detection
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

class RateLimiter:
    def __init__(self, state_file="cache/rate_limits.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(exist_ok=True)
        self.state = self._load_state()
        
        # Platform posting limits (posts per day per account)
        self.platform_limits = {
            'bluesky': 3,
            'devto': 1,
            'hashnode': 1,
            'github': 50,  # Commits per day
            'reddit': 1    # 1 post per day to avoid spam detection
        }
        
        # Cooldown periods between same app posts (in hours)
        self.app_cooldowns = {
            'bluesky': 8,
            'devto': 24,
            'hashnode': 24,
            'github': 1,
            'reddit': 24   # 24 hours between posts
        }
    
    def _load_state(self):
        """Load rate limit state from file"""
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading rate limit state: {e}")
            return {}
    
    def _save_state(self):
        """Save rate limit state to file"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving rate limit state: {e}")
    
    def _get_key(self, platform, app_name=None):
        """Generate state key"""
        if app_name:
            return f"{platform}_{app_name}"
        return platform
    
    def _clean_old_entries(self):
        """Remove entries older than 7 days"""
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        
        keys_to_remove = []
        for key, entries in self.state.items():
            if isinstance(entries, list):
                # Remove old timestamps
                self.state[key] = [
                    entry for entry in entries
                    if entry.get('timestamp', '') > cutoff
                ]
                if not self.state[key]:
                    keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.state[key]
    
    def can_post(self, platform, app_name=None):
        """
        Check if we can post to platform (and optionally for specific app)
        
        Args:
            platform: Platform name (x, bluesky, devto, etc.)
            app_name: Optional app name for app-specific cooldowns
            
        Returns:
            (bool, str): (can_post, reason_if_not)
        """
        now = datetime.now()
        today = now.date().isoformat()
        
        # Check platform daily limit
        platform_key = self._get_key(platform)
        if platform_key not in self.state:
            self.state[platform_key] = []
        
        # Count today's posts
        today_posts = [
            entry for entry in self.state[platform_key]
            if entry.get('date') == today
        ]
        
        if len(today_posts) >= self.platform_limits.get(platform, 999):
            return False, f"Daily limit reached for {platform} ({len(today_posts)}/{self.platform_limits[platform]})"
        
        # Check app-specific cooldown
        if app_name:
            app_key = self._get_key(platform, app_name)
            if app_key in self.state and self.state[app_key]:
                last_post_time = datetime.fromisoformat(self.state[app_key][-1]['timestamp'])
                cooldown_hours = self.app_cooldowns.get(platform, 24)
                time_since_last = (now - last_post_time).total_seconds() / 3600
                
                if time_since_last < cooldown_hours:
                    wait_time = cooldown_hours - time_since_last
                    return False, f"Cooldown: wait {wait_time:.1f} hours before posting {app_name} to {platform}"
        
        return True, "OK"
    
    def record_post(self, platform, app_name=None):
        """
        Record a post to update rate limits
        
        Args:
            platform: Platform name
            app_name: Optional app name
        """
        now = datetime.now()
        today = now.date().isoformat()
        
        entry = {
            'timestamp': now.isoformat(),
            'date': today
        }
        
        # Record platform post
        platform_key = self._get_key(platform)
        if platform_key not in self.state:
            self.state[platform_key] = []
        self.state[platform_key].append(entry)
        
        # Record app-specific post
        if app_name:
            app_key = self._get_key(platform, app_name)
            if app_key not in self.state:
                self.state[app_key] = []
            self.state[app_key].append(entry)
        
        # Clean old entries periodically
        self._clean_old_entries()
        self._save_state()
    
    def get_stats(self, platform=None):
        """
        Get posting statistics
        
        Args:
            platform: Optional platform to filter stats
            
        Returns:
            Dictionary with stats
        """
        today = datetime.now().date().isoformat()
        
        if platform:
            platform_key = self._get_key(platform)
            today_posts = [
                entry for entry in self.state.get(platform_key, [])
                if entry.get('date') == today
            ]
            return {
                'platform': platform,
                'today_posts': len(today_posts),
                'daily_limit': self.platform_limits.get(platform, 'N/A'),
                'remaining': self.platform_limits.get(platform, 999) - len(today_posts)
            }
        
        # Stats for all platforms
        stats = {}
        for platform in self.platform_limits.keys():
            platform_key = self._get_key(platform)
            today_posts = [
                entry for entry in self.state.get(platform_key, [])
                if entry.get('date') == today
            ]
            stats[platform] = {
                'today_posts': len(today_posts),
                'daily_limit': self.platform_limits[platform],
                'remaining': self.platform_limits[platform] - len(today_posts)
            }
        
        return stats
    
    def reset_daily_limits(self):
        """Reset all daily limits (useful for testing or manual reset)"""
        self.state = {}
        self._save_state()
