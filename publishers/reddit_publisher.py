"""
Reddit Publisher - Posts articles to relevant subreddits
"""
import os
import praw
from datetime import datetime
import time
import json

class RedditPublisher:
    def __init__(self):
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.username = os.getenv('REDDIT_USERNAME')
        self.password = os.getenv('REDDIT_PASSWORD')
        self.user_agent = "UltraTechApps:v1.0 (by /u/{})".format(self.username)
        
        # Subreddit mapping for different app categories
        self.subreddit_map = {
            'music': ['androidapps', 'androidgaming'],  # Safe, general subreddits
            'productivity': ['productivity', 'androidapps'],
            'dating': ['androidapps'],
            'health': ['androidapps', 'selfimprovement'],
            'social': ['androidapps'],
            'finance': ['CryptoCurrency', 'androidapps'],
            'lifestyle': ['androidapps']
        }
        
        self.reddit = None
        if all([self.client_id, self.client_secret, self.username, self.password]):
            try:
                self.reddit = praw.Reddit(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    username=self.username,
                    password=self.password,
                    user_agent=self.user_agent
                )
                print(f"✅ Reddit API initialized for user: {self.username}")
            except Exception as e:
                print(f"❌ Reddit initialization failed: {str(e)}")
                self.reddit = None
        else:
            print("⚠️  Reddit credentials not found. Skipping Reddit publishing.")
    
    def _get_post_title(self, article):
        """Create Reddit-friendly title (max 300 chars)"""
        title = article.get('title', 'Check out this app!')
        if len(title) > 280:
            title = title[:277] + "..."
        return title
    
    def _get_post_body(self, article, article_url, app_store_link):
        """Create Reddit post body with article excerpt and links"""
        description = article.get('description', '')
        
        body = f"{description}\n\n"
        body += f"**📖 Read the full article:** {article_url}\n\n"
        body += f"**📱 Download the app:** {app_store_link}\n\n"
        body += "---\n"
        body += "*Posted by an indie developer building apps daily* 🚀"
        
        return body
    
    def _select_subreddit(self, category):
        """Select appropriate subreddit based on app category"""
        # Get subreddits for this category
        subreddits = self.subreddit_map.get(category.lower(), ['androidapps'])
        
        # For now, use the first one (you can rotate or randomize)
        return subreddits[0]
    
    def publish(self, article, article_url, app_info):
        """
        Publish article to Reddit
        
        Args:
            article: Article dict with title, description, content
            article_url: Full URL to the article on your site
            app_info: App metadata including category, name, app_store_link
        
        Returns:
            dict: Publication result with success status and post URL
        """
        if not self.reddit:
            return {
                'success': False,
                'error': 'Reddit not configured',
                'platform': 'reddit'
            }
        
        try:
            # Get app details
            app_name = app_info.get('name', 'Our App')
            category = app_info.get('category', 'productivity')
            app_store_link = app_info.get('app_store_link', article_url)
            
            # Select subreddit
            subreddit_name = self._select_subreddit(category)
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Create post title and body
            title = self._get_post_title(article)
            body = self._get_post_body(article, article_url, app_store_link)
            
            # Submit as text post
            submission = subreddit.submit(
                title=title,
                selftext=body,
                send_replies=False  # Don't send reply notifications to avoid spam
            )
            
            post_url = f"https://reddit.com{submission.permalink}"
            
            print(f"✅ Published to Reddit: r/{subreddit_name}")
            print(f"   Post URL: {post_url}")
            
            return {
                'success': True,
                'url': post_url,
                'platform': 'reddit',
                'subreddit': subreddit_name,
                'post_id': submission.id
            }
            
        except praw.exceptions.RedditAPIException as e:
            error_msg = str(e)
            print(f"❌ Reddit API error: {error_msg}")
            
            # Handle rate limiting
            if 'RATELIMIT' in error_msg:
                print("⏳ Rate limited. Should wait before next post.")
            
            return {
                'success': False,
                'error': error_msg,
                'platform': 'reddit'
            }
            
        except Exception as e:
            print(f"❌ Reddit publishing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'reddit'
            }
    
    def get_karma(self):
        """Get account karma (useful for monitoring)"""
        if not self.reddit:
            return None
        
        try:
            user = self.reddit.user.me()
            return {
                'link_karma': user.link_karma,
                'comment_karma': user.comment_karma,
                'total_karma': user.link_karma + user.comment_karma
            }
        except Exception as e:
            print(f"❌ Failed to get karma: {str(e)}")
            return None
