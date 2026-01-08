"""
Analytics tracker for monitoring post performance
"""
import json
from pathlib import Path
from datetime import datetime

class AnalyticsTracker:
    def __init__(self, analytics_file="cache/analytics.json"):
        self.analytics_file = Path(analytics_file)
        self.analytics_file.parent.mkdir(exist_ok=True)
        self.data = self._load_data()
    
    def _load_data(self):
        """Load analytics data from file"""
        if not self.analytics_file.exists():
            return {
                'posts': [],
                'stats': {
                    'total_posts': 0,
                    'by_platform': {},
                    'by_app': {}
                }
            }
        
        try:
            with open(self.analytics_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading analytics: {e}")
            return {'posts': [], 'stats': {}}
    
    def _save_data(self):
        """Save analytics data to file"""
        try:
            with open(self.analytics_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving analytics: {e}")
    
    def track_post(self, platform, app_name, post_type, result):
        """
        Track a post
        
        Args:
            platform: Platform name
            app_name: App name
            post_type: Type of post (article, social, etc.)
            result: Result dictionary from publisher
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'platform': platform,
            'app_name': app_name,
            'post_type': post_type,
            'success': result.get('success', False),
            'url': result.get('url', ''),
            'error': result.get('error', '')
        }
        
        self.data['posts'].append(entry)
        
        # Update stats
        stats = self.data.get('stats', {})
        stats['total_posts'] = stats.get('total_posts', 0) + 1
        
        # Platform stats
        by_platform = stats.get('by_platform', {})
        by_platform[platform] = by_platform.get(platform, 0) + 1
        stats['by_platform'] = by_platform
        
        # App stats
        by_app = stats.get('by_app', {})
        by_app[app_name] = by_app.get(app_name, 0) + 1
        stats['by_app'] = by_app
        
        self.data['stats'] = stats
        self._save_data()
        
        print(f"📊 Tracked {platform} post for {app_name}")
    
    def get_stats(self, days=7):
        """
        Get statistics for the last N days
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with statistics
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        recent_posts = [
            post for post in self.data['posts']
            if post['timestamp'] >= cutoff_str
        ]
        
        stats = {
            'total_posts': len(recent_posts),
            'successful_posts': len([p for p in recent_posts if p['success']]),
            'failed_posts': len([p for p in recent_posts if not p['success']]),
            'by_platform': {},
            'by_app': {}
        }
        
        for post in recent_posts:
            platform = post['platform']
            app = post['app_name']
            
            stats['by_platform'][platform] = stats['by_platform'].get(platform, 0) + 1
            stats['by_app'][app] = stats['by_app'].get(app, 0) + 1
        
        return stats
    
    def print_summary(self, days=7):
        """Print a summary of recent activity"""
        stats = self.get_stats(days)
        
        print(f"\n📊 Analytics Summary (Last {days} Days)")
        print("=" * 50)
        print(f"Total Posts: {stats['total_posts']}")
        print(f"Successful: {stats['successful_posts']}")
        print(f"Failed: {stats['failed_posts']}")
        
        if stats['by_platform']:
            print("\nBy Platform:")
            for platform, count in sorted(stats['by_platform'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {platform}: {count}")
        
        if stats['by_app']:
            print("\nBy App:")
            for app, count in sorted(stats['by_app'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {app}: {count}")
        
        print("=" * 50)
