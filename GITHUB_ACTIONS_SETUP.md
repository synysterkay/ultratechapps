# GitHub Actions Setup Guide

## Overview
The marketing automation runs automatically Monday-Friday at 9 AM UTC via GitHub Actions.

## Setting Up GitHub Secrets

You need to add your API keys as GitHub Secrets. Go to:
`https://github.com/synysterkay/marketingtool/settings/secrets/actions`

### Required Secrets

Add these secrets (click "New repository secret" for each):

1. **DEEPSEEK_API_KEY**
   - Value: Your DeepSeek API key
   - Get it from: https://platform.deepseek.com/api_keys

2. **DEVTO_API_KEY**
   - Value: Your Dev.to API key
   - Get it from: https://dev.to/settings/extensions

3. **HASHNODE_API_KEY**
   - Value: Your Hashnode API key
   - Get it from: https://hashnode.com/settings/developer

4. **HASHNODE_PUBLICATION_ID** *(optional)*
   - Value: Your Hashnode publication ID
   - Leave empty to post to your personal blog

5. **BLUESKY_HANDLE**
   - Value: Your Bluesky username (e.g., `yourusername.bsky.social`)

6. **BLUESKY_PASSWORD**
   - Value: Your Bluesky password or app password
   - Get app password from: https://bsky.app/settings/app-passwords

### Note on GITHUB_TOKEN
`GITHUB_TOKEN` is automatically provided by GitHub Actions - you don't need to add it manually.

## Manual Trigger

To manually trigger the workflow:
1. Go to: `https://github.com/synysterkay/marketingtool/actions`
2. Click "Marketing Automation" workflow
3. Click "Run workflow" button
4. Select the branch (main)
5. Click "Run workflow"

## Monitoring

View workflow runs and logs at:
`https://github.com/synysterkay/marketingtool/actions`

## Schedule

The automation runs:
- **When**: Monday-Friday at 9:00 AM UTC
- **Time Zones**:
  - PST: 1:00 AM
  - EST: 4:00 AM
  - CET: 10:00 AM
  
## What It Does

1. Checks out the repository
2. Sets up Python environment
3. Installs dependencies from `requirements.txt`
4. Runs `main.py` to generate and publish content
5. Commits generated blog posts to `_posts/`
6. Pushes changes back to GitHub
7. GitHub Pages automatically rebuilds the website

## Troubleshooting

### Workflow fails with "API key not found"
- Check that all required secrets are added
- Secret names must match exactly (case-sensitive)

### Content not publishing
- Check the Actions tab for error logs
- Verify rate limits in `cache/rate_limits.json`
- Check `cache/content_cache.json` for duplicate detection

### Website not updating
- GitHub Pages rebuild can take 2-5 minutes
- Check Pages settings are enabled
- Verify branch is set to `main`

## Disabling Automation

To temporarily disable:
1. Go to: `.github/workflows/marketing.yml`
2. Comment out the `schedule:` section
3. Commit and push

Or disable the workflow entirely in:
`https://github.com/synysterkay/marketingtool/actions`
