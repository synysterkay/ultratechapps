---
layout: default
title: Blog
permalink: /blog/
---

# Blog

Practical guides, app development insights, and helpful tips for mobile users.

<div class="posts-list">
  {% for post in site.posts %}
  <article class="post-item">
    <h2><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h2>
    <p class="post-meta">
      <time datetime="{{ post.date | date_to_xmlschema }}">{{ post.date | date: "%B %d, %Y" }}</time>
      {% if post.categories %}
      <span class="separator">•</span>
      <span class="categories">
        {% for category in post.categories %}
          <span class="category">{{ category }}</span>{% unless forloop.last %}, {% endunless %}
        {% endfor %}
      </span>
      {% endif %}
    </p>
    <p class="post-excerpt">{{ post.description | default: post.excerpt | strip_html | truncatewords: 40 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Read more →</a>
  </article>
  {% endfor %}
</div>

{% if site.posts.size == 0 %}
<div class="no-posts">
  <p>No articles yet. Check back soon for helpful guides and insights!</p>
</div>
{% endif %}
