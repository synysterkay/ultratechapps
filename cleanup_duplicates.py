#!/usr/bin/env python3
"""Delete duplicate articles, keeping only the newest version of each title"""
import os
import re
from collections import defaultdict

# Find all posts and their titles
posts = []
for filename in os.listdir('_posts'):
    if filename.endswith('.md'):
        filepath = os.path.join('_posts', filename)
        with open(filepath, 'r') as f:
            content = f.read()
            # Extract title
            match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
            if match:
                title = match.group(1).strip('"\'')
                # Extract date from filename
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
                date = date_match.group(1) if date_match else '0000-00-00'
                posts.append({'file': filepath, 'filename': filename, 'title': title, 'date': date})

print(f"Found {len(posts)} total articles")

# Group by title
by_title = defaultdict(list)
for post in posts:
    by_title[post['title']].append(post)

# Find duplicates and delete older ones
deleted = 0
kept = 0
for title, group in by_title.items():
    if len(group) > 1:
        # Sort by date descending (newest first)
        group.sort(key=lambda x: x['date'], reverse=True)
        # Keep newest, delete rest
        print(f"\n📝 '{title[:50]}...' ({len(group)} copies)")
        print(f"   ✅ Keep: {group[0]['filename']}")
        kept += 1
        for old in group[1:]:
            print(f"   🗑️  Delete: {old['filename']}")
            os.remove(old['file'])
            deleted += 1

print(f"\n{'='*60}")
print(f"✅ Kept {kept} newest versions of duplicate titles")
print(f"🗑️  Deleted {deleted} duplicate articles")

# Count remaining
remaining = len([f for f in os.listdir('_posts') if f.endswith('.md')])
print(f"📊 Total unique articles remaining: {remaining}")
