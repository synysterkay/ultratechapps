# Cloudflare Pages Deployment Guide

## Setup Instructions

### 1. Connect GitHub to Cloudflare Pages

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **Workers & Pages**
3. Click **Create Application** → **Pages** → **Connect to Git**
4. Select your GitHub repository: `synysterkay/ultratechapps`
5. Configure build settings:
   - **Framework preset**: None
   - **Build command**: `jekyll build`
   - **Build output directory**: `_site`
   - **Root directory**: (leave blank - do not enter "/" or any value)
   
6. If a deploy command is required, use:
   ```
   echo "Deployment handled by Cloudflare Pages"
   ```
   
   **IMPORTANT**: Do NOT use `npx wrangler deploy` - that's for Workers, not Pages. Pages automatically detects and deploys functions from the `/functions` directory.

### 2. Set Environment Variables

In Cloudflare Pages project settings:

1. Go to **Settings** → **Environment Variables**
2. Add these variables (for both Production and Preview):

```
MAILGUN_API_KEY = your_mailgun_api_key_here
MAILGUN_DOMAIN = bestaiapps.site
```

**Note:** Find your Mailgun API key in Mailgun Dashboard → Settings → API Keys

### 3. Deploy

- Cloudflare will automatically build and deploy on every push to `main`
- Function will be available at: `https://your-site.pages.dev/api/subscribe`

## File Structure

```
/Volumes/Flow/marketing-tool/
├── functions/
│   └── api/
│       └── subscribe.js          # Cloudflare Pages Function
├── index.md                       # Updated to call /api/subscribe
└── CLOUDFLARE_SETUP.md           # This file
```

## How It Works

1. **User submits email** on bestaiapps.site
2. **JavaScript calls** `/api/subscribe` (Cloudflare Function)
3. **Function adds subscriber** to Mailgun with journey metadata:
   - `niche: general` (or detected from page)
   - `sequence_stage: welcome`
   - `welcome_day: 0`
   - Sets up for Day 0 email
4. **GitHub Actions** (daily at 9 AM UTC) sends automated emails

## Testing Locally

You can test the function locally with Wrangler:

```bash
# Install Wrangler
npm install -g wrangler

# Run dev server
wrangler pages dev _site --binding MAILGUN_API_KEY=your_key MAILGUN_DOMAIN=bestaiapps.site

# Test endpoint
curl -X POST http://localhost:8788/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","niche":"productivity"}'
```

## Verify Deployment

1. Check Cloudflare Pages deployment logs
2. Test the form on your live site
3. Verify subscriber added to Mailgun:
   ```bash
   python3 scripts/mailgun_subscriber.py list
   ```

## Custom Domain

If using custom domain (bestaiapps.site):

1. In Cloudflare Pages → **Custom Domains**
2. Add `bestaiapps.site`
3. Cloudflare will automatically configure DNS

## Troubleshooting

**Function not found (404):**
- Ensure file is at `functions/api/subscribe.js` (not `api/subscribe.js`)
- Redeploy from Cloudflare dashboard

**CORS errors:**
- Check `Access-Control-Allow-Origin` header in function
- Verify OPTIONS handler is working

**Mailgun errors:**
- Check environment variables are set correctly
- Verify Mailgun domain is verified
- Check API key has correct permissions

## Cost

Cloudflare Pages is **FREE** for:
- Unlimited requests
- Unlimited bandwidth
- 500 builds per month

Perfect for this use case! 🎉
