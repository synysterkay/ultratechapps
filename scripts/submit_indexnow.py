#!/usr/bin/env python3
"""
Submit all blog URLs to IndexNow for instant indexing on Bing, Yandex, and other search engines.
Google doesn't support IndexNow, but this helps with Bing traffic.

Usage: python3 scripts/submit_indexnow.py
"""

import requests
import os
import glob
import re
from datetime import datetime

# Configuration
SITE_URL = "https://bestaiapps.site"
INDEXNOW_KEY = "60f2b8aef55e998676da5ab7c3ed2d7b"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

def get_all_blog_urls():
    """Get all blog post URLs from _posts folder"""
    posts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '_posts')
    urls = []
    
    for filepath in glob.glob(os.path.join(posts_dir, '*.md')):
        filename = os.path.basename(filepath)
        # Parse Jekyll filename format: YYYY-MM-DD-slug.md
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})-(.+)\.md', filename)
        if match:
            year, month, day, slug = match.groups()
            # Remove .md extension from slug if present
            slug = slug.replace('.md', '')
            url = f"{SITE_URL}/blog/{year}/{month}/{day}/{slug}/"
            urls.append(url)
    
    # Add important pages
    important_pages = [
        f"{SITE_URL}/",
        f"{SITE_URL}/blog/",
        f"{SITE_URL}/apps/",
        f"{SITE_URL}/about/",
    ]
    urls = important_pages + urls
    
    return urls

def submit_to_indexnow(urls):
    """Submit URLs to IndexNow API"""
    
    # IndexNow accepts max 10,000 URLs per request
    batch_size = 10000
    total_submitted = 0
    
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        
        payload = {
            "host": "bestaiapps.site",
            "key": INDEXNOW_KEY,
            "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
            "urlList": batch
        }
        
        try:
            response = requests.post(
                INDEXNOW_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 202]:
                total_submitted += len(batch)
                print(f"✅ Submitted batch {i//batch_size + 1}: {len(batch)} URLs")
            else:
                print(f"❌ Error submitting batch: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return total_submitted

def main():
    print("=" * 60)
    print("IndexNow URL Submission Tool")
    print("Submits URLs to Bing, Yandex, and other IndexNow partners")
    print("=" * 60)
    print()
    
    # Get all URLs
    urls = get_all_blog_urls()
    print(f"📄 Found {len(urls)} URLs to submit")
    print()
    
    # Show sample URLs
    print("Sample URLs:")
    for url in urls[:5]:
        print(f"  - {url}")
    print(f"  ... and {len(urls) - 5} more")
    print()
    
    # Submit to IndexNow
    print("Submitting to IndexNow...")
    submitted = submit_to_indexnow(urls)
    
    print()
    print("=" * 60)
    print(f"✅ Successfully submitted {submitted} URLs to IndexNow!")
    print()
    print("These search engines will now crawl your pages faster:")
    print("  - Bing")
    print("  - Yandex") 
    print("  - Naver")
    print("  - Seznam")
    print()
    print("Note: Google does NOT support IndexNow.")
    print("For Google, submit your sitemap in Search Console.")
    print("=" * 60)

if __name__ == "__main__":
    main()
