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
        {% assign image_hash = post.title | size | times: 9973 | plus: forloop.index | times: 7919 %}
        {% assign image_choices = "1484417954-9a2e-4f63-b0ce-5c4d4e8b0f5a,1551288414-6e82-4a24-9b4e-9e4f4e8d6e3b,1557804506-4e6b-4c5e-9e5f-e5d4e4f0e9b0,1531297484-5b9e-4e4f-9e9f-e6d5e5f1e0c1,1460925895-6f8a-4e5f-9f0e-e7d6e6f2e1d2" | split: "," %}
        {% assign image_index = image_hash | modulo: 5 %}
        {% assign selected_image = image_choices[image_index] %}
        <div class="blog-post-card">
          <img src="https://images.unsplash.com/photo-{{ selected_image }}?w=800&h=500&fit=crop&q=80" alt="{{ post.title }}" class="blog-post-image">
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
