# Best Ai Apps - Marketing & Blog Platform

Professional marketing automation and blog website for indie app developer Best Ai Apps.

🌐 **Website:** https://synysterkay.github.io/marketingtool/

📱 **Apps:** 
- [App Store](https://apps.apple.com/us/developer/anas-kayssi/id1769590510)
- [Google Play](https://play.google.com/store/apps/dev?id=5116533678587496673)

## Features

### 🚀 Marketing Automation
- AI-powered content generation (800-1200 word articles)
- Multi-platform publishing (GitHub Pages, Dev.to, Hashnode, Bluesky)
- Smart duplicate detection & rate limiting
- Automatic niche detection per app
- SEO-optimized articles with metadata

### 🌐 Professional Website
- Modern, responsive Jekyll website
- Blog with automatic article publishing
- Clean design with mobile optimization
- SEO-friendly with automatic sitemaps
- RSS feed for subscribers

### 🤖 Automation
- GitHub Actions workflow (Mon-Fri at 9 AM UTC)
- Automatic content rotation across apps
- Built-in spam prevention
- Performance tracking & analytics

---

## Quick Start

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure apps:**
   Edit `apps.json` with your app information.

3. **Set up API keys:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Run locally:**
   ```bash
   python main.py
   ```

## Platform Setup

### Dev.to
1. Go to https://dev.to/settings/extensions
2. Generate an API key
3. Add to `.env` as `DEVTO_API_KEY`

### Hashnode
1. Go to https://hashnode.com/settings/developer
2. Generate a personal access token
3. Add to `.env` as `HASHNODE_TOKEN`

### X/Twitter
1. Apply for API access at https://developer.twitter.com/
2. Create an app and generate API keys
3. Add all Twitter credentials to `.env`

### Bluesky
1. Use your Bluesky username and password
2. Add to `.env` as `BLUESKY_USERNAME` and `BLUESKY_PASSWORD`

### Telegram
1. Create a bot via @BotFather
2. Create a channel and add your bot as admin
3. Add bot token and channel ID to `.env`

### GitHub
1. Create a personal access token with repo permissions
2. Add to `.env` as `GITHUB_TOKEN`
3. Set `GITHUB_REPO` to your repository (e.g., `username/repo`)

## GitHub Actions

The workflow runs automatically on weekdays at 9 AM UTC. To set up:

1. Go to your repository Settings → Secrets and variables → Actions
2. Add all secrets from your `.env` file
3. Push the `.github/workflows/marketing.yml` file

## Safety Features

- ✅ Duplicate content detection
- ✅ Rate limiting per platform
- ✅ Content quality validation
- ✅ Smart app rotation
- ✅ Cooldown periods between posts

## Project Structure

```
marketing-tool/
├── config/
│   ├── apps.json
│   └── content_calendar.json
├── generators/
│   ├── niche_detector.py
│   ├── article_generator.py
│   └── snippet_generator.py
├── publishers/
│   ├── github_publisher.py
│   ├── devto_publisher.py
│   ├── social_publisher.py
│   └── analytics_tracker.py
├── utils/
│   ├── content_cache.py
│   ├── duplicate_checker.py
│   └── rate_limiter.py
├── cache/
├── blog/
└── main.py
```

## License

MIT
