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
          {% if post.image %}
            <img src="{{ post.image }}" alt="{{ post.title }}" class="blog-post-image">
          {% else %}
            {% assign image_hash = post.title | size | times: 9973 | plus: forloop.index | times: 7919 %}
            {% assign image_choices = "1499750310107-5fef28a66643,1551288414-26de491c97e214d9cc9ca05f,1557804506-aa9e4c8bb9842b7a0cc686b0,1531297484-244a42e29d7ee79c8fc8e1e9,1460925895-917f4df0a7b41c8c7e8e6a6d" | split: "," %}
            {% assign image_index = image_hash | modulo: 5 %}
            {% assign selected_image = image_choices[image_index] %}
            <img src="https://images.unsplash.com/photo-{{ selected_image }}?w=800&h=500&fit=crop&q=80" alt="{{ post.title }}" class="blog-post-image">
          {% endif %}
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
