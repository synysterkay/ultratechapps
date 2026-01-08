# Setting Up GitHub Pages for Your Website

## Quick Setup

1. **Enable GitHub Pages:**
   - Go to your repository: `https://github.com/synysterkay/marketingtool`
   - Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main` → `/ (root)`
   - Save

2. **Wait for deployment:**
   - GitHub will build your site automatically
   - Check Actions tab to see build progress
   - Site will be live at: `https://synysterkay.github.io/marketingtool/`

3. **View your website:**
   - Homepage: `https://synysterkay.github.io/marketingtool/`
   - Blog: `https://synysterkay.github.io/marketingtool/blog`
   - About: `https://synysterkay.github.io/marketingtool/about`

## Local Development (Optional)

To test the website locally before pushing:

### Install Jekyll

**macOS:**
```bash
# Install Ruby and Jekyll
brew install ruby
gem install bundler jekyll
```

### Run Locally

```bash
cd /Volumes/Flow/marketing-tool

# Install dependencies
bundle install

# Start Jekyll server
bundle exec jekyll serve

# Open in browser: http://localhost:4000/marketingtool/
```

## Website Structure

```
marketingtool/
├── _config.yml          # Jekyll configuration
├── _layouts/            # Page templates
│   ├── default.html
│   ├── home.html
│   └── post.html
├── _includes/           # Reusable components
│   ├── header.html
│   └── footer.html
├── _posts/              # Blog posts (auto-generated)
│   └── YYYY-MM-DD-title.md
├── assets/
│   └── css/
│       └── style.css    # Website styling
├── index.md             # Homepage
├── blog.md              # Blog listing page
├── about.md             # About page
└── Gemfile              # Ruby dependencies
```

## Adding Custom Domain (Optional)

1. Buy a domain (e.g., ultratechapps.com)
2. Add CNAME file to repository root:
   ```
   ultratechapps.com
   ```
3. Configure DNS:
   - Add CNAME record: `www` → `synysterkay.github.io`
   - Add A records for apex domain:
     ```
     185.199.108.153
     185.199.109.153
     185.199.110.153
     185.199.111.153
     ```
4. Update `_config.yml`:
   ```yaml
   url: "https://ultratechapps.com"
   baseurl: ""
   ```

## Customization

### Change Colors

Edit `assets/css/style.css`:
```css
:root {
  --primary-color: #2563eb;  /* Change this */
  --secondary-color: #10b981; /* And this */
}
```

### Update Site Info

Edit `_config.yml`:
```yaml
title: Your Site Title
description: Your description
author: Your Name
email: your@email.com
```

### Add More Pages

Create new `.md` files:
```markdown
---
layout: default
title: Contact
permalink: /contact/
---

# Contact Page Content
```

## How the Marketing Tool Works with the Website

1. **Automated Content Generation:**
   - Tool generates articles → saves to `_posts/`
   - Jekyll automatically includes them in blog

2. **File Format:**
   ```
   _posts/2026-01-08-article-title.md
   ```

3. **Front Matter:**
   ```yaml
   ---
   title: "Article Title"
   date: 2026-01-08
   categories: [category]
   tags: [tag1, tag2]
   description: "Brief description"
   ---
   ```

4. **Automatic Features:**
   - Blog listing page updates automatically
   - RSS feed generates at `/feed.xml`
   - SEO tags added automatically
   - Sitemap generates at `/sitemap.xml`

## Troubleshooting

### Site not showing up?
- Check GitHub Actions for build errors
- Verify GitHub Pages is enabled in Settings
- Wait 5-10 minutes after first push

### Styles not loading?
- Check `_config.yml` has correct `baseurl`
- Clear browser cache
- Check browser console for 404 errors

### Posts not appearing?
- Ensure filename format: `YYYY-MM-DD-title.md`
- Check front matter is valid YAML
- Date must be today or earlier

## Next Steps

1. ✅ Push all files to GitHub
2. ✅ Enable GitHub Pages in repository settings
3. ✅ Test the site at your GitHub Pages URL
4. ✅ Run the marketing tool to generate content
5. ✅ Share your blog URL!

## Resources

- [Jekyll Documentation](https://jekyllrb.com/docs/)
- [GitHub Pages Guide](https://docs.github.com/en/pages)
- [Markdown Guide](https://www.markdownguide.org/)

Your professional website is ready to go! 🚀
