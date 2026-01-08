"""
GitHub publisher for committing blog posts
"""
import os
from pathlib import Path
from datetime import datetime
from github import Github, GithubException

class GitHubPublisher:
    def __init__(self):
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GITHUB_TOKEN not found in environment variables")
        
        self.repo_name = os.getenv('GITHUB_REPO')
        if not self.repo_name:
            raise ValueError("GITHUB_REPO not found in environment variables")
        
        self.branch = os.getenv('GITHUB_BRANCH', 'main')
        self.blog_path = os.getenv('BLOG_PATH', '_posts')
        
        self.github = Github(token)
        self.repo = self.github.get_repo(self.repo_name)
    
    def _generate_filename(self, article):
        """Generate filename for article"""
        date_str = datetime.now().strftime('%Y-%m-%d')
        title_slug = article['title'].lower()
        title_slug = ''.join(c if c.isalnum() or c == ' ' else '' for c in title_slug)
        title_slug = '-'.join(title_slug.split())[:50]
        
        return f"{date_str}-{title_slug}.md"
    
    def _format_frontmatter(self, article, metadata):
        """Format Jekyll/Hugo frontmatter"""
        frontmatter = f"""---
title: "{article['title']}"
date: {datetime.now().strftime('%Y-%m-%d')}
categories: [{article['niche']}]
tags: [{', '.join(article['keywords'][:5])}]
description: "{metadata['meta_description']}"
---

"""
        return frontmatter
    
    def publish_article(self, article, metadata):
        """
        Publish article to GitHub repository
        
        Args:
            article: Article dictionary
            metadata: Metadata dictionary
            
        Returns:
            URL of published article
        """
        try:
            filename = self._generate_filename(article)
            file_path = f"{self.blog_path}/{filename}"
            
            # Format content with frontmatter
            content = self._format_frontmatter(article, metadata)
            content += article['content']
            
            # Check if file already exists
            try:
                existing = self.repo.get_contents(file_path, ref=self.branch)
                # Update existing file
                self.repo.update_file(
                    path=file_path,
                    message=f"Update: {article['title']}",
                    content=content,
                    sha=existing.sha,
                    branch=self.branch
                )
                print(f"✅ Updated article on GitHub: {file_path}")
            except GithubException as e:
                if e.status == 404:
                    # Create new file
                    self.repo.create_file(
                        path=file_path,
                        message=f"Add: {article['title']}",
                        content=content,
                        branch=self.branch
                    )
                    print(f"✅ Published article to GitHub: {file_path}")
                else:
                    raise
            
            # Return URL
            pages_url = f"https://{self.repo.owner.login}.github.io/{self.repo.name}/{filename.replace('.md', '.html')}"
            
            return {
                'success': True,
                'url': pages_url,
                'file_path': file_path
            }
            
        except Exception as e:
            print(f"❌ Error publishing to GitHub: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def save_locally(self, article, metadata, output_dir="_posts"):
        """
        Save article locally (useful for testing)
        
        Args:
            article: Article dictionary
            metadata: Metadata dictionary
            output_dir: Local directory to save to
            
        Returns:
            Path to saved file
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        filename = self._generate_filename(article)
        file_path = output_path / filename
        
        # Format content with frontmatter
        content = self._format_frontmatter(article, metadata)
        content += article['content']
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Saved article locally: {file_path}")
        return str(file_path)
