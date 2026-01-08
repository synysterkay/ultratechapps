---
layout: default
title: Blog
permalink: /blog/
---

<div class="blog-section">
  <div class="container">
    <h1 class="section-title">Latest Articles</h1>
    <p style="text-align: center; color: var(--text-light); margin-bottom: 3rem; font-size: 1.125rem;">Insights, tips, and guides to help you make the most of our apps</p>
    
    <div class="blog-grid">
      {% for post in site.posts %}
        <div class="blog-post-card">
          <img src="https://images.unsplash.com/photo-1499750310107-5fef28a66643?w=600&q=80" alt="{{ post.title }}" class="blog-post-image">
          <div class="blog-post-content">
            <h2 class="blog-post-title">
              <a href="{{ post.url | relative_url }}" style="text-decoration: none; color: inherit;">{{ post.title }}</a>
            </h2>
            <div class="blog-post-meta">
              <span>📅 {{ post.date | date: "%B %d, %Y" }}</span>
              {% if post.categories %}
                <span>📂 {{ post.categories | join: ", " }}</span>
              {% endif %}
            </div>
            <p class="blog-post-excerpt">{{ post.excerpt | strip_html | truncatewords: 30 }}</p>
            <a href="{{ post.url | relative_url }}" class="read-more">
              Read Full Article →
            </a>
          </div>
        </div>
      {% endfor %}
    </div>
  </div>
</div>
