#!/usr/bin/env python3
"""
Marketing Automation Tool
Automated content generation and multi-platform publishing for indie apps
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import modules
from generators.niche_detector import NicheDetector
from generators.article_generator import ArticleGenerator
from generators.snippet_generator import SnippetGenerator
from publishers.github_publisher import GitHubPublisher
from publishers.devto_publisher import DevToPublisher, HashnodePublisher
from publishers.social_publisher import SocialPublisher
from publishers.analytics_tracker import AnalyticsTracker
from utils.rate_limiter import RateLimiter
from utils.content_cache import ContentCache


class MarketingAutomation:
    def __init__(self):
        print("🚀 Initializing Marketing Automation Tool...")
        
        # Initialize components
        self.niche_detector = NicheDetector()
        self.article_generator = ArticleGenerator()
        self.snippet_generator = SnippetGenerator()
        
        self.github_publisher = GitHubPublisher()
        self.devto_publisher = DevToPublisher()
        self.hashnode_publisher = HashnodePublisher()
        self.social_publisher = SocialPublisher()
        
        self.analytics = AnalyticsTracker()
        self.rate_limiter = RateLimiter()
        self.cache = ContentCache()
        
        # Load apps
        self.apps = self._load_apps()
        print(f"✅ Loaded {len(self.apps)} apps")
    
    def _load_apps(self):
        """Load apps from apps.json"""
        apps_file = Path("apps.json")
        if not apps_file.exists():
            print("❌ apps.json not found!")
            sys.exit(1)
        
        with open(apps_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def process_app(self, app):
        """
        Process a single app: generate content and publish
        
        Args:
            app: App dictionary
        """
        app_name = app['name']
        print(f"\n{'='*60}")
        print(f"Processing: {app_name}")
        print(f"{'='*60}")
        
        # Step 1: Detect niche (cached after first run)
        print("\n1️⃣ Detecting niche...")
        niche_info = self.niche_detector.detect_niche(
            app_name=app_name,
            description=app.get('description', ''),
            google_play_url=app['google_play_url'],
            app_store_url=app['app_store_url']
        )
        
        # Step 2: Generate article
        print("\n2️⃣ Generating article...")
        article = self.article_generator.generate_article(app, niche_info)
        metadata = self.article_generator.generate_metadata(article)
        
        # Step 3: Publish to GitHub Pages
        print("\n3️⃣ Publishing to GitHub Pages...")
        can_post, reason = self.rate_limiter.can_post('github', app_name)
        if can_post:
            github_result = self.github_publisher.publish_article(article, metadata)
            self.analytics.track_post('github', app_name, 'article', github_result)
            self.rate_limiter.record_post('github', app_name)
            
            # Also save locally
            self.github_publisher.save_locally(article, metadata)
        else:
            print(f"⏸️ Skipping GitHub: {reason}")
        
        # Step 4: Generate and publish Dev.to variant
        print("\n4️⃣ Publishing to Dev.to...")
        can_post, reason = self.rate_limiter.can_post('devto', app_name)
        if can_post:
            devto_variant = self.snippet_generator.generate_blog_variant(article, 'devto')
            devto_result = self.devto_publisher.publish(devto_variant)
            self.analytics.track_post('devto', app_name, 'article', devto_result)
            if devto_result['success']:
                self.rate_limiter.record_post('devto', app_name)
        else:
            print(f"⏸️ Skipping Dev.to: {reason}")
        
        # Step 5: Generate and publish Hashnode variant
        print("\n5️⃣ Publishing to Hashnode...")
        can_post, reason = self.rate_limiter.can_post('hashnode', app_name)
        if can_post:
            hashnode_variant = self.snippet_generator.generate_blog_variant(article, 'hashnode')
            hashnode_result = self.hashnode_publisher.publish(hashnode_variant)
            self.analytics.track_post('hashnode', app_name, 'article', hashnode_result)
            if hashnode_result['success']:
                self.rate_limiter.record_post('hashnode', app_name)
        else:
            print(f"⏸️ Skipping Hashnode: {reason}")
        
        # Step 6: Generate and publish social media posts
        self._publish_social_posts(article, app_name)
        
        print(f"\n✅ Completed processing {app_name}")
    
    def _publish_social_posts(self, article, app_name):
        """Publish social media posts for an article"""
        social_platforms = ['bluesky']
        
        for platform in social_platforms:
            print(f"\n📱 Publishing to {platform.upper()}...")
            
            can_post, reason = self.rate_limiter.can_post(platform, app_name)
            if not can_post:
                print(f"⏸️ Skipping {platform}: {reason}")
                continue
            
            # Generate posts for this platform
            posts = self.snippet_generator.generate_social_posts(
                article, 
                platform,
                count=1  # Generate 1 post per run to avoid spam
            )
            
            for post in posts:
                result = self.social_publisher.post(platform, post)
                self.analytics.track_post(platform, app_name, 'social', result)
                
                if result['success']:
                    self.rate_limiter.record_post(platform, app_name)
                    time.sleep(2)  # Small delay between posts
                else:
                    print(f"⚠️ Failed to post to {platform}")
                    break  # Stop if posting fails
    
    def run_daily_automation(self):
        """
        Run daily automation with smart app rotation
        """
        print("\n" + "="*60)
        print("🤖 Starting Daily Marketing Automation")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Show rate limiter stats
        print("\n📊 Today's Posting Limits:")
        stats = self.rate_limiter.get_stats()
        for platform, data in stats.items():
            print(f"  {platform}: {data['today_posts']}/{data['daily_limit']} (remaining: {data['remaining']})")
        
        # Process apps with rotation
        apps_to_process = self._select_apps_for_today()
        
        print(f"\n📋 Processing {len(apps_to_process)} apps today")
        
        for i, app in enumerate(apps_to_process, 1):
            print(f"\n[{i}/{len(apps_to_process)}]")
            
            try:
                self.process_app(app)
                
                # Delay between apps to avoid rate limits
                if i < len(apps_to_process):
                    delay = 60  # 1 minute between apps
                    print(f"\n⏱️ Waiting {delay} seconds before next app...")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"\n❌ Error processing {app['name']}: {e}")
                continue
        
        # Final summary
        print("\n" + "="*60)
        print("🎉 Daily Automation Complete!")
        print("="*60)
        
        self.analytics.print_summary(days=1)
        
        # Show updated rate limits
        print("\n📊 Final Posting Stats:")
        stats = self.rate_limiter.get_stats()
        for platform, data in stats.items():
            print(f"  {platform}: {data['today_posts']}/{data['daily_limit']}")
    
    def _select_apps_for_today(self):
        """
        Select which apps to process today
        Supports environment variable APP_INDEX for scheduled runs
        """
        # Check if APP_INDEX is set (from GitHub Actions)
        app_index = os.getenv('APP_INDEX')
        
        if app_index is not None:
            try:
                index = int(app_index)
                if 0 <= index < len(self.apps):
                    print(f"📍 Processing app at index {index}")
                    return [self.apps[index]]
                else:
                    print(f"⚠️ Invalid APP_INDEX {index}, defaulting to first app")
                    return self.apps[:1]
            except ValueError:
                print(f"⚠️ Invalid APP_INDEX format, defaulting to first app")
                return self.apps[:1]
        
        # Default: Process only first app for testing
        return self.apps[:1]
    
    def test_single_app(self, app_index=0):
        """
        Test mode: process a single app
        
        Args:
            app_index: Index of app in apps.json to process
        """
        if app_index >= len(self.apps):
            print(f"❌ Invalid app index. Available: 0-{len(self.apps)-1}")
            return
        
        app = self.apps[app_index]
        print(f"\n🧪 Test Mode: Processing {app['name']}")
        
        try:
            self.process_app(app)
            print("\n✅ Test completed successfully!")
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Marketing Automation Tool')
    parser.add_argument('--test', action='store_true', help='Run in test mode (single app)')
    parser.add_argument('--app-index', type=int, default=0, help='App index for test mode')
    parser.add_argument('--stats', action='store_true', help='Show analytics stats')
    
    args = parser.parse_args()
    
    try:
        automation = MarketingAutomation()
        
        if args.stats:
            automation.analytics.print_summary(days=7)
        elif args.test:
            automation.test_single_app(args.app_index)
        else:
            automation.run_daily_automation()
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
