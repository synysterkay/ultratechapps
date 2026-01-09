# Reddit & Medium Setup Guide

## Reddit Setup (API Access)

### Step 1: Create Reddit App
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in the form:
   - **Name:** UltraTech Apps Marketing Bot
   - **App type:** Select "script"
   - **Description:** Automated posting for indie app marketing
   - **About URL:** https://synysterkay.github.io/ultratechapps/
   - **Redirect URI:** http://localhost:8080 (required but not used)
4. Click "Create app"

### Step 2: Get API Credentials
After creating the app, you'll see:
- **Client ID:** The string under your app name (looks like: `abc123DEF456`)
- **Client Secret:** The "secret" field (looks like: `xyz789ABC123def456GHI789`)

### Step 3: Add Secrets to GitHub
Run these commands (replace with your values):

```bash
# Reddit credentials
gh secret set REDDIT_CLIENT_ID --body "YOUR_CLIENT_ID" --repo synysterkay/ultratechapps
gh secret set REDDIT_CLIENT_SECRET --body "YOUR_CLIENT_SECRET" --repo synysterkay/ultratechapps
gh secret set REDDIT_USERNAME --body "your_reddit_username" --repo synysterkay/ultratechapps
gh secret set REDDIT_PASSWORD --body "your_reddit_password" --repo synysterkay/ultratechapps
```

Or add them manually:
1. Go to: https://github.com/synysterkay/ultratechapps/settings/secrets/actions
2. Click "New repository secret"
3. Add each secret:
   - `REDDIT_CLIENT_ID`
   - `REDDIT_CLIENT_SECRET`
   - `REDDIT_USERNAME`
   - `REDDIT_PASSWORD`

### Step 4: Important Reddit Guidelines

⚠️ **Reddit is VERY strict about spam:**

1. **Post limit:** 1 post per day (already configured)
2. **Subreddit rules:** Each subreddit has different rules
3. **Account karma:** Build karma before heavy posting
4. **Be authentic:** Provide value, not just promotion

**Recommended subreddits (already configured):**
- r/androidapps (general Android apps)
- r/productivity (for productivity apps)
- r/selfimprovement (for health/habit apps)

**Tips for success:**
- Participate in comments (build karma)
- Read subreddit rules before posting
- Don't post the same content to multiple subreddits quickly
- Consider 2-3 posts per week max, not daily

---

## Medium Setup (RSS Import - No API Key Needed)

Medium deprecated their posting API in 2021, but they have a better alternative: **automatic RSS import**.

### Step 1: Enable RSS Feed (Already Done!)
Your Jekyll blog automatically generates an RSS feed at:
```
https://synysterkay.github.io/ultratechapps/feed.xml
```

### Step 2: Connect RSS to Medium
1. Go to https://medium.com/me/settings
2. Log in to your Medium account
3. Click **"Publishing"** in the left sidebar
4. Scroll down to **"Import from RSS"**
5. Enter your RSS feed URL: `https://synysterkay.github.io/ultratechapps/feed.xml`
6. Click "Add RSS feed"

### Step 3: How It Works
- Medium checks your RSS feed **every few hours**
- When a new article appears, Medium automatically imports it
- Your articles appear as drafts first (you can review before publishing)
- Or set to auto-publish (in RSS import settings)

### Step 4: Enable in Your Automation (Optional)
If you want the automation to track Medium status:

```bash
gh secret set MEDIUM_IMPORT_ENABLED --body "true" --repo synysterkay/ultratechapps
```

This just enables logging - Medium pulls from RSS automatically.

### Benefits of RSS Import:
✅ Fully automated after initial setup
✅ No API credentials needed
✅ No rate limits
✅ Medium handles duplicate detection
✅ Preserves article formatting
✅ Free forever

---

## Testing

### Test Reddit Locally:
```bash
cd /path/to/marketing-tool
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_secret"
export REDDIT_USERNAME="your_username"
export REDDIT_PASSWORD="your_password"
python main.py
```

### Test Medium:
1. Publish an article via GitHub Actions
2. Wait 2-4 hours
3. Check Medium dashboard for imported article

---

## Rate Limits & Schedule

**Current automation schedule:**
- Posts every hour (24/7)
- Cycles through 13 apps
- Each app posts ~13 times per week

**Reddit:**
- 1 post per app per day max
- Post appears on different subreddits based on app category
- Rate limit: 1 post/10 minutes per subreddit (PRAW handles this)

**Medium:**
- Unlimited (RSS import)
- Medium pulls your RSS feed automatically
- No manual action needed after setup

---

## Monitoring

### Check Reddit Posts:
```bash
# View your Reddit posts
gh run view --log | grep "Reddit"
```

Or visit: https://github.com/synysterkay/ultratechapps/actions

### Check Medium Imports:
1. Go to https://medium.com/me/stories/drafts
2. Look for imported articles from your RSS feed

---

## Troubleshooting

### Reddit Issues:

**"RATELIMIT" error:**
- Means you're posting too fast
- Wait 10 minutes between posts
- Automation already handles this

**"POST_LOCKED" error:**
- Subreddit doesn't allow new accounts to post
- Build karma first (comment on posts)
- Or switch to r/androidapps (more permissive)

**Posts getting removed:**
- Check if you violated subreddit rules
- Reddit mods may require manual approval for new accounts
- Build reputation first

### Medium Issues:

**Articles not importing:**
- Check RSS feed is accessible: https://synysterkay.github.io/ultratechapps/feed.xml
- Wait 4-6 hours (Medium is slow)
- Check Medium settings → Publishing → RSS feeds

**Duplicate articles:**
- Medium detects duplicates automatically
- Won't import the same article twice

---

## Best Practices

### Reddit:
1. Start with 1-2 posts per week, not daily
2. Engage with comments on your posts
3. Participate in other discussions (build karma)
4. Follow subreddit rules strictly
5. Consider disabling Reddit temporarily if you get warnings

### Medium:
1. Review imported articles before publishing
2. Add tags on Medium (RSS doesn't include them)
3. Add to publications for more reach
4. Engage with comments and claps

---

## Support

- **Reddit API Docs:** https://www.reddit.com/dev/api
- **PRAW Documentation:** https://praw.readthedocs.io/
- **Medium Help:** https://help.medium.com/

For issues, check GitHub Actions logs:
https://github.com/synysterkay/ultratechapps/actions
