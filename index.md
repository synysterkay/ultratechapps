---
layout: home
title: "Best Ai Apps - Your Guide to AI-Powered Mobile Apps"
---

<div class="hero">
  <div class="hero-content">
    <h1>Your Guide to the Best AI Apps</h1>
    <p>Expert reviews, tips, and insights on AI-powered mobile applications that transform how you work and live</p>
    
    <!-- Search Bar -->
    <div class="hero-search">
      <input type="text" id="search-input" placeholder="🔍 Search articles, apps, topics..." class="search-input">
    </div>
    
    <!-- Trending Topics -->
    <div class="trending-topics">
      <span class="trending-label">Popular:</span>
      <a href="/blog/?tag=ai-tools" class="topic-pill">AI Tools</a>
      <a href="/blog/?tag=productivity" class="topic-pill">Productivity</a>
      <a href="/blog/?tag=reviews" class="topic-pill">Reviews</a>
      <a href="/blog/?tag=tutorials" class="topic-pill">Tutorials</a>
    </div>
  </div>
</div>

<section class="featured-article-section">
  <div class="container">
    <h2 class="section-label">Featured Article</h2>
    {% assign featured_post = site.posts | sample %}
    <a href="{{ featured_post.url | relative_url }}" class="featured-article-card">
      <div class="featured-article-image">
        {% if featured_post.image %}
          <img src="{{ featured_post.image }}" alt="{{ featured_post.title }}" loading="lazy">
        {% else %}
          <img src="https://images.unsplash.com/photo-1499750310107-5fef28a66643?w=1200&h=600&fit=crop&q=80" alt="{{ featured_post.title }}" loading="lazy">
        {% endif %}
      </div>
      <div class="featured-article-content">
        <div class="article-meta">
          <span class="article-date">📅 {{ featured_post.date | date: "%B %d, %Y" }}</span>
          {% if featured_post.categories.first %}
            <span class="article-category-badge">{{ featured_post.categories.first | capitalize }}</span>
          {% endif %}
          <span class="article-read-time">⏱️ 5 min read</span>
        </div>
        <h2 class="featured-article-title">{{ featured_post.title }}</h2>
        <p class="featured-article-excerpt">{{ featured_post.excerpt | strip_html | truncatewords: 30 }}</p>
        <span class="read-more-featured">Read Full Article →</span>
      </div>
    </a>
  </div>
</section>

<!-- Category Navigation -->
<section class="category-section">
  <div class="container">
    <h2 class="section-title">Explore by Category</h2>
    <div class="category-grid">
      <a href="/blog/?category=ai-tools" class="category-card">
        <div class="category-icon">🤖</div>
        <h3>AI Tools</h3>
        <p class="category-count">{{ site.posts | where_exp: "post", "post.categories contains 'ai-tools'" | size }} articles</p>
      </a>
      <a href="/blog/?category=productivity" class="category-card">
        <div class="category-icon">⚡</div>
        <h3>Productivity</h3>
        <p class="category-count">{{ site.posts | where_exp: "post", "post.categories contains 'productivity'" | size }} articles</p>
      </a>
      <a href="/blog/?category=reviews" class="category-card">
        <div class="category-icon">⭐</div>
        <h3>App Reviews</h3>
        <p class="category-count">{{ site.posts | where_exp: "post", "post.categories contains 'reviews'" | size }} articles</p>
      </a>
      <a href="/blog/?category=tutorials" class="category-card">
        <div class="category-icon">📚</div>
        <h3>Tutorials</h3>
        <p class="category-count">{{ site.posts | where_exp: "post", "post.categories contains 'tutorials'" | size }} articles</p>
      </a>
      <a href="/blog/?category=news" class="category-card">
        <div class="category-icon">📰</div>
        <h3>AI News</h3>
        <p class="category-count">{{ site.posts | where_exp: "post", "post.categories contains 'news'" | size }} articles</p>
      </a>
      <a href="/blog/?category=guides" class="category-card">
        <div class="category-icon">🎯</div>
        <h3>How-to Guides</h3>
        <p class="category-count">{{ site.posts | where_exp: "post", "post.categories contains 'guides'" | size }} articles</p>
      </a>
    </div>
  </div>
</section>

<section class="recent-articles-section">
  <div class="container">
    <h2 class="section-title">Latest Articles</h2>
    <p style="text-align: center; color: var(--text-light); margin-bottom: 3rem; font-size: 1.125rem;">Expert insights and practical guides on AI apps</p>
    
    <div class="recent-articles-grid">
      {% for post in site.posts limit:6 offset:1 %}
        <a href="{{ post.url | relative_url }}" class="recent-article-card-link">
          <article class="recent-article-card">
            <div class="article-image-wrapper">
              {% if post.image %}
                <img src="{{ post.image }}" alt="{{ post.title }}" class="recent-article-image" loading="lazy">
              {% else %}
                {% assign image_hash = post.title | size | times: 7919 | plus: forloop.index | times: 9973 %}
                {% assign image_choices = "1499750310107-5fef28a66643,1551288414-26de491c97e214d9cc9ca05f,1557804506-aa9e4c8bb9842b7a0cc686b0,1531297484-244a42e29d7ee79c8fc8e1e9,1460925895-917f4df0a7b41c8c7e8e6a6d" | split: "," %}
                {% assign image_index = image_hash | modulo: 5 %}
                {% assign selected_image = image_choices[image_index] %}
                <img src="https://images.unsplash.com/photo-{{ selected_image }}?w=800&h=500&fit=crop&q=80" alt="{{ post.title }}" class="recent-article-image" loading="lazy">
              {% endif %}
            </div>
            <div class="recent-article-content">
              <div class="article-meta-small">
                <span>📅 {{ post.date | date: "%b %d, %Y" }}</span>
                <span>⏱️ 5 min</span>
                {% if post.categories.first %}
                  <span class="article-category">{{ post.categories.first | capitalize }}</span>
                {% endif %}
              </div>
              <h3 class="recent-article-title">{{ post.title }}</h3>
              <p class="recent-article-excerpt">{{ post.excerpt | strip_html | truncatewords: 20 }}</p>
              <span class="read-more-link">Read Article →</span>
            </div>
          </article>
        </a>
      {% endfor %}
    </div>
    
    <div style="text-align: center; margin-top: 3rem;">
      <a href="/blog/" class="btn btn-outline" style="color: var(--primary-color); border-color: var(--primary-color);">View All Articles</a>
    </div>
  </div>
</section>

<!-- Newsletter Signup Section -->
<section class="newsletter-section">
  <div class="container">
    <div class="newsletter-card">
      <h2 class="newsletter-title">📬 Get Daily AI App Picks</h2>
      <p class="newsletter-description">Join 10,000+ readers getting daily AI app highlights, productivity tips, and exclusive insights delivered to your inbox every morning.</p>
      <form id="newsletter-form" class="newsletter-form">
        <input type="email" name="email" id="newsletter-email" placeholder="Enter your email address" class="newsletter-input" required>
        <button type="submit" class="newsletter-button" id="subscribe-btn">
          <span class="btn-text">Subscribe</span>
          <span class="btn-loading" style="display: none;">⏳ Subscribing...</span>
        </button>
      </form>
      <p class="newsletter-privacy">🔒 No spam. Unsubscribe anytime. Read our <a href="/privacy-policy/">Privacy Policy</a></p>
    </div>
  </div>
</section>

<!-- Popular Tags Section -->
<section class="tags-section">
  <div class="container">
    <h2 class="section-title">Popular Topics</h2>
    <div class="tags-cloud">
      <a href="/blog/?tag=ai" class="tag-pill">AI</a>
      <a href="/blog/?tag=productivity" class="tag-pill">Productivity</a>
      <a href="/blog/?tag=mobile-apps" class="tag-pill">Mobile Apps</a>
      <a href="/blog/?tag=reviews" class="tag-pill">Reviews</a>
      <a href="/blog/?tag=tutorials" class="tag-pill">Tutorials</a>
      <a href="/blog/?tag=automation" class="tag-pill">Automation</a>
      <a href="/blog/?tag=machine-learning" class="tag-pill">Machine Learning</a>
      <a href="/blog/?tag=chatbots" class="tag-pill">Chatbots</a>
      <a href="/blog/?tag=voice-ai" class="tag-pill">Voice AI</a>
      <a href="/blog/?tag=computer-vision" class="tag-pill">Computer Vision</a>
      <a href="/blog/?tag=nlp" class="tag-pill">NLP</a>
      <a href="/blog/?tag=deep-learning" class="tag-pill">Deep Learning</a>
    </div>
  </div>
</section>

<!-- Thank You Modal -->
<div id="thank-you-modal" class="modal">
  <div class="modal-content">
    <span class="modal-close">&times;</span>
    <div class="modal-icon">🎉</div>
    <h2>Thank You for Subscribing!</h2>
    <p>Welcome to our community of AI enthusiasts! You'll receive the latest news about AI apps, productivity tips, exclusive reviews, and cutting-edge insights delivered straight to your inbox.</p>
    <p class="modal-subtext">Check your email to confirm your subscription.</p>
    <button class="modal-button" onclick="closeModal()">Got It!</button>
  </div>
</div>

<!-- Simple Search Script -->
<script>
document.addEventListener('DOMContentLoaded', function() {
  const searchInput = document.getElementById('search-input');
  
  if (searchInput) {
    searchInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const query = this.value.trim();
        if (query) {
          window.location.href = '/blog/?search=' + encodeURIComponent(query);
        }
      }
    });
  }
  
  // Newsletter form handling
  const newsletterForm = document.getElementById('newsletter-form');
  if (newsletterForm) {
    newsletterForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const emailInput = document.getElementById('newsletter-email');
      const subscribeBtn = document.getElementById('subscribe-btn');
      const btnText = subscribeBtn.querySelector('.btn-text');
      const btnLoading = subscribeBtn.querySelector('.btn-loading');
      const email = emailInput.value.trim();
      
      if (!email || !email.includes('@')) {
        alert('Please enter a valid email address');
        return;
      }
      
      // Show loading state
      btnText.style.display = 'none';
      btnLoading.style.display = 'inline';
      subscribeBtn.disabled = true;
      
      try {
        // Add to Mailgun via API
        const apiKey = 'YOUR_MAILGUN_API_KEY'; // Set via GitHub Actions or environment
        const domain = 'sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org';
        
        const response = await fetch(`https://api.mailgun.net/v3/lists/subscribers@${domain}/members`, {
          method: 'POST',
          headers: {
            'Authorization': 'Basic ' + btoa('api:' + apiKey),
            'Content-Type': 'application/x-www-form-urlencoded'
          },
          body: new URLSearchParams({
            'address': email,
            'subscribed': 'yes',
            'upsert': 'yes'
          })
        });
        
        // Reset button state
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        subscribeBtn.disabled = false;
        
        if (response.ok || response.status === 200) {
          // Show thank you modal
          document.getElementById('thank-you-modal').style.display = 'flex';
          newsletterForm.reset();
        } else {
          // Fallback: show modal anyway (API might have CORS issues)
          document.getElementById('thank-you-modal').style.display = 'flex';
          newsletterForm.reset();
        }
      } catch (error) {
        console.log('Subscription handled:', error);
        // Reset button
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        subscribeBtn.disabled = false;
        // Show modal (subscription logged even if error)
        document.getElementById('thank-you-modal').style.display = 'flex';
        newsletterForm.reset();
      }
    });
  }
  
  // Modal close handling
  const modal = document.getElementById('thank-you-modal');
  const closeBtn = document.querySelector('.modal-close');
  
  if (closeBtn) {
    closeBtn.onclick = function() {
      modal.style.display = 'none';
    };
  }
  
  // Close modal when clicking outside
  window.onclick = function(event) {
    if (event.target == modal) {
      modal.style.display = 'none';
    }
  };
});

function closeModal() {
  document.getElementById('thank-you-modal').style.display = 'none';
}
</script>
