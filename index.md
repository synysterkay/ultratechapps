---
layout: home
title: Home
---

# Welcome to UltraTech Apps

**Building apps that matter. Shipping every day.**

I'm an indie developer passionate about creating mobile applications that solve real problems and enhance productivity. From innovative tools to engaging experiences, every app is crafted with attention to detail and user experience.

## Featured Apps

Browse my collection of apps designed to make your life easier:

<div class="app-links">
  <a href="https://apps.apple.com/us/developer/anas-kayssi/id1769590510" class="btn btn-primary" target="_blank">
    📱 View on App Store
  </a>
  <a href="https://play.google.com/store/apps/dev?id=5116533678587496673" class="btn btn-secondary" target="_blank">
    🤖 View on Google Play
  </a>
</div>

## Latest Articles

Explore practical tips, development insights, and helpful guides from the blog:

<div class="recent-posts">
  {% for post in site.posts limit:6 %}
  <article class="post-preview">
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-meta">{{ post.date | date: "%B %d, %Y" }}</p>
    <p>{{ post.description | default: post.excerpt | strip_html | truncatewords: 30 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Read more →</a>
  </article>
  {% endfor %}
</div>

<div class="view-all">
  <a href="{{ '/blog' | relative_url }}" class="btn btn-outline">View All Articles</a>
</div>

## What I Build

- 📱 **Mobile Apps** - iOS and Android applications
- 🚀 **Productivity Tools** - Apps that enhance your workflow
- 💡 **Innovative Solutions** - Creative approaches to everyday problems
- 🎯 **User-Focused Design** - Clean, intuitive interfaces

---

<div class="cta">
  <h2>Let's Connect</h2>
  <p>Interested in my apps or want to collaborate? Check out my work on the app stores!</p>
  <div class="app-links">
    <a href="https://apps.apple.com/us/developer/anas-kayssi/id1769590510" class="btn btn-primary" target="_blank">App Store</a>
    <a href="https://play.google.com/store/apps/dev?id=5116533678587496673" class="btn btn-secondary" target="_blank">Google Play</a>
  </div>
</div>
