#!/usr/bin/env python3
"""
Generate social share links to help Google discover your pages faster.
Google crawls Twitter, Reddit, LinkedIn - sharing URLs helps indexing.

Usage: python3 scripts/generate_share_links.py
"""

import os
import glob
import re
import random

SITE_URL = "https://bestaiapps.site"

def get_blog_posts():
    """Get all blog post URLs and titles"""
    posts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '_posts')
    posts = []
    
    for filepath in sorted(glob.glob(os.path.join(posts_dir, '*.md')), reverse=True):
        filename = os.path.basename(filepath)
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})-(.+)\.md', filename)
        if match:
            year, month, day, slug = match.groups()
            url = f"{SITE_URL}/blog/{year}/{month}/{day}/{slug}/"
            
            # Get title from file
            with open(filepath, 'r') as f:
                content = f.read()
                title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
                title = title_match.group(1) if title_match else slug.replace('-', ' ').title()
            
            posts.append({'url': url, 'title': title, 'slug': slug})
    
    return posts

def main():
    posts = get_blog_posts()
    
    print("=" * 70)
    print("🚀 SOCIAL SHARE LINKS - Help Google Discover Your Pages")
    print("=" * 70)
    print()
    print("Sharing URLs on social media helps Google discover and index them faster.")
    print("Pick 5-10 of your best articles and share them!")
    print()
    
    # Key pages
    print("📌 KEY PAGES TO SHARE FIRST:")
    print("-" * 50)
    key_pages = [
        (f"{SITE_URL}/", "Best AI Apps 2026 - Home"),
        (f"{SITE_URL}/blog/", "AI Apps Blog"),
        (f"{SITE_URL}/apps/", "Our AI Apps Collection"),
    ]
    for url, title in key_pages:
        print(f"\n🔗 {title}")
        print(f"   URL: {url}")
        print(f"   Twitter: https://twitter.com/intent/tweet?url={url}&text={title.replace(' ', '%20')}")
    
    print()
    print()
    print("📝 TOP 10 RECENT ARTICLES TO SHARE:")
    print("-" * 50)
    
    for i, post in enumerate(posts[:10], 1):
        title_encoded = post['title'][:80].replace(' ', '%20').replace('&', '%26')
        print(f"\n{i}. {post['title'][:60]}...")
        print(f"   URL: {post['url']}")
        print(f"   Twitter: https://twitter.com/intent/tweet?url={post['url']}&text={title_encoded}")
    
    print()
    print()
    print("=" * 70)
    print("💡 TIPS FOR FASTER INDEXING:")
    print("=" * 70)
    print("""
1. Share 2-3 articles on Twitter/X daily
2. Post your best content on Reddit (relevant subreddits)
3. Share on LinkedIn if business-related
4. Add links from any other websites you own
5. Submit to web directories (even free ones help)

Google's crawler follows links from social media!
After sharing, pages typically get indexed within 24-72 hours.
""")

if __name__ == "__main__":
    main()
