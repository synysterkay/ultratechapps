#!/usr/bin/env python3
"""Fix posts with broken descriptions containing markdown headers"""
import os
import re
import glob

def fix_description(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if description starts with ##
    if 'description: "##' not in content:
        return False
    
    # Extract title for fallback
    title_match = re.search(r'^title:\s*"([^"]+)"', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Article"
    
    # Find the first real paragraph after frontmatter
    parts = content.split('---', 2)
    if len(parts) < 3:
        return False
    
    body = parts[2]
    
    # Find first paragraph that's not a header or bullet (starts with capital letter)
    paragraphs = re.findall(r'^(?!#|\*|\-|\d\.)[A-Z][^#\n]{50,200}', body, re.MULTILINE)
    
    if paragraphs:
        desc = paragraphs[0].strip()
        desc = re.sub(r'\s+', ' ', desc)
        desc = desc[:155] + '...' if len(desc) > 155 else desc
        desc = desc.replace('"', "'")
    else:
        desc = f"Learn everything about {title.lower()}. Expert tips, guides, and insights."
    
    # Replace the broken description
    new_content = re.sub(
        r'description: "##[^"]*"',
        f'description: "{desc}"',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    return True

# Find and fix all broken posts
fixed = 0
for filepath in glob.glob('_posts/*.md'):
    if fix_description(filepath):
        print(f"Fixed: {os.path.basename(filepath)}")
        fixed += 1

print(f"\nTotal fixed: {fixed}")
