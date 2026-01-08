# Setup Instructions

## 1. Install Dependencies Locally

```bash
pip install -r requirements.txt
```

## 2. Configure Your Apps

Edit `apps.json` with your app information:

```json
[
  {
    "name": "Your App Name",
    "description": "Brief description for niche detection",
    "google_play_url": "https://play.google.com/store/apps/details?id=...",
    "app_store_url": "https://apps.apple.com/app/id..."
  }
]
```

## 3. Set Up Environment Variables

### Local Development

1. Copy the example env file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your API keys (see platform setup below)

### GitHub Actions

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:
- `DEEPSEEK_API_KEY` - Get from https://platform.deepseek.com/
- `DEVTO_API_KEY` - Get from https://dev.to/settings/extensions
- `HASHNODE_TOKEN` - Get from https://hashnode.com/settings/developer
- `HASHNODE_PUBLICATION_ID` - Your Hashnode publication ID
- `TWITTER_API_KEY` - Twitter API credentials
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_SECRET`
- `BLUESKY_USERNAME` - Your Bluesky username
- `BLUESKY_PASSWORD` - Your Bluesky password
- `TELEGRAM_BOT_TOKEN` - Get from @BotFather on Telegram
- `TELEGRAM_CHANNEL_ID` - Your channel ID (e.g., @yourchannel)
- `GH_PAT` - GitHub Personal Access Token with repo permissions

## 4. Test Locally

Test with a single app:
```bash
python main.py --test --app-index 0
```

View analytics:
```bash
python main.py --stats
```

## 5. Run Full Automation

```bash
python main.py
```

## 6. Deploy to GitHub Actions

1. Push your code to GitHub
2. The workflow will run automatically Mon-Fri at 9 AM UTC
3. You can also trigger it manually from Actions tab

## Platform-Specific Setup

### DeepSeek API
1. Sign up at https://platform.deepseek.com/
2. Generate an API key
3. Add to secrets as `DEEPSEEK_API_KEY`

### Dev.to
1. Login to Dev.to
2. Go to Settings → Extensions → Generate API Key
3. Add to secrets as `DEVTO_API_KEY`

### Hashnode
1. Login to Hashnode
2. Go to Settings → Developer
3. Generate Personal Access Token
4. Add to secrets as `HASHNODE_TOKEN`
5. Get your Publication ID from your blog settings
6. Add to secrets as `HASHNODE_PUBLICATION_ID`

### X/Twitter
1. Apply for API access at https://developer.twitter.com/
2. Create an app
3. Generate API keys and access tokens
4. Add all 4 credentials to secrets

### Bluesky
1. Use your Bluesky account credentials
2. Add username and password to secrets

### Telegram
1. Talk to @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Save the bot token
4. Create a channel and add your bot as admin
5. Add bot token and channel ID to secrets

### GitHub
1. Generate a Personal Access Token at https://github.com/settings/tokens
2. Grant `repo` permissions
3. Add to secrets as `GH_PAT`

## Troubleshooting

### "Module not found" error
```bash
pip install -r requirements.txt
```

### "API key not found" error
Make sure all required environment variables are set in `.env` or GitHub secrets

### Rate limit errors
The tool automatically handles rate limits. If you see rate limit messages, the tool is working correctly and will skip posts that exceed limits.

### GitHub push fails
Make sure `GH_PAT` has `repo` permissions and is correctly set in GitHub secrets

## Customization

### Change posting frequency
Edit the cron schedule in `.github/workflows/marketing.yml`:
```yaml
schedule:
  - cron: '0 9 * * 1-5'  # Mon-Fri at 9 AM
```

### Adjust rate limits
Edit platform limits in `utils/rate_limiter.py`:
```python
self.platform_limits = {
    'x': 3,  # Change to your desired limit
    'bluesky': 3,
    # ...
}
```

### Modify content types
Edit rotation in `generators/article_generator.py`:
```python
self.content_types = [
    "how_to_guide",
    "tips_and_tricks",
    # Add your own types
]
```
