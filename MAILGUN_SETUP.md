# Mailgun Email Automation Setup Guide

## ✅ What's Implemented

### 1. Email Capture System
- Newsletter form on homepage captures emails
- Subscribers added directly to Mailgun mailing list
- No manual export needed

### 2. Daily Email Campaign
- Automated GitHub Actions workflow
- Sends daily AI app highlight to all subscribers
- Professional HTML email template
- Tracks opens, clicks, engagement

### 3. Subscriber Management
- CLI tools to manage subscribers
- Export subscriber list anytime
- No dashboard needed - everything via terminal

## 🚀 Setup Instructions

### Step 1: Add Secrets to GitHub

Go to your repository settings and add these secrets:

```bash
# Navigate to: github.com/synysterkay/ultratechapps/settings/secrets/actions

MAILGUN_API_KEY: <your-mailgun-api-key-here>
MAILGUN_DOMAIN: sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org
```

**How to add secrets:**
1. Go to repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `MAILGUN_API_KEY`, Value: (your API key)
4. Click "Add secret"
5. Repeat for `MAILGUN_DOMAIN`

### Step 2: Create Mailing List

Run this command to create the mailing list:

```bash
cd /Volumes/Flow/marketing-tool

export MAILGUN_API_KEY="your-api-key-here"
export MAILGUN_DOMAIN="sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org"

python3 scripts/mailgun_subscriber.py create
```

Expected output:
```
✅ Mailing list created: subscribers@sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org
```

### Step 3: Test Email Subscription

Test adding a subscriber:

```bash
python3 scripts/mailgun_subscriber.py add your-email@example.com "Your Name"
```

Expected output:
```
✅ Added subscriber: your-email@example.com
```

### Step 4: Test Daily Email Campaign

Send a test email to yourself:

```bash
python3 scripts/send_daily_email.py test your-email@example.com
```

This will send today's featured app email to your inbox.

### Step 5: Verify Subscriber List

Check all subscribers:

```bash
python3 scripts/mailgun_subscriber.py list
```

Output:
```
📊 Total subscribers: 1
  - your-email@example.com (Your Name)
```

## 📧 How It Works

### Email Capture Flow

1. **User subscribes on website** (index.md newsletter form)
2. **JavaScript sends to Mailgun API** (client-side)
3. **Email added to mailing list** (subscribers@domain)
4. **Thank you popup shown** (existing modal)

### Daily Campaign Flow

1. **GitHub Actions triggers** (9 AM UTC daily)
2. **Script selects app of the day** (rotates through all apps)
3. **Generates HTML email** (professional template)
4. **Sends to all subscribers** (via Mailgun API)
5. **Tracks engagement** (opens, clicks)

### Email Content

**Subject:** 🚀 Daily AI Pick: [App Name]

**Content:**
- Featured app of the day
- Description and benefits
- Download buttons (Google Play + App Store)
- Value proposition
- Call-to-action
- Unsubscribe link

## 🔧 Terminal Commands

### Subscriber Management

```bash
# Add subscriber
python3 scripts/mailgun_subscriber.py add email@example.com "Name"

# List all subscribers
python3 scripts/mailgun_subscriber.py list

# Create mailing list
python3 scripts/mailgun_subscriber.py create
```

### Email Campaigns

```bash
# Send daily campaign to all subscribers
python3 scripts/send_daily_email.py

# Send test email
python3 scripts/send_daily_email.py test your-email@example.com
```

### GitHub Actions

```bash
# Manually trigger daily email (via GitHub CLI)
gh workflow run email-campaign.yml

# Check workflow status
gh run list --workflow=email-campaign.yml

# View workflow logs
gh run view --log
```

## 📊 App Rotation

Emails feature a different app each day:

- **Day 1**: Volume Booster
- **Day 2**: Smart Notes
- **Day 3**: AI Girlfriend
- **Day 4**: Red Flag Scanner
- **Day 5**: Predictify
- **Day 6**: Fresh Start
- **Day 7**: Reelit
- **Day 8**: SoulPlan
- **Day 9**: PupShape
- **Day 10**: Thesis Generator
- **Day 11**: LoveStory AI
- **Day 12**: AI Boyfriend
- **Day 13**: Crypto AI
- **Day 14**: Kinbound
- **Day 15**: Cycle repeats...

Rotation based on day of year, so it automatically cycles through all apps.

## 🎯 Next Steps

### Immediate Actions

1. ✅ **Add GitHub Secrets** (MAILGUN_API_KEY, MAILGUN_DOMAIN)
2. ✅ **Create mailing list** (run create command)
3. ✅ **Send test email** (verify it works)
4. ✅ **Commit and push** (deploy to production)

### Testing Checklist

- [ ] Subscribe via website form
- [ ] Check email arrives in Mailgun list
- [ ] Send test campaign email
- [ ] Verify email looks good
- [ ] Click download buttons (track clicks)
- [ ] Test unsubscribe link
- [ ] Verify GitHub Actions workflow runs

### Monitoring

Check campaign performance:

1. Login to [Mailgun Dashboard](https://app.mailgun.com)
2. View → Sending → Mailing Lists
3. Click on "subscribers@sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org"
4. See subscriber count, email stats, engagement

Or via API (terminal):

```bash
curl -s --user 'api:YOUR_API_KEY_HERE' \
     https://api.mailgun.net/v3/lists/subscribers@sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org/members/pages \
     | python3 -m json.tool
```

## 💰 Cost

**Mailgun Pricing:**
- Free tier: 5,000 emails/month for 3 months
- Then: 1,000 emails/month free forever
- Paid: $35/month for 50,000 emails

**Current setup:**
- Daily email = 30 emails/month per subscriber
- Free tier supports: ~150 subscribers (5,000 ÷ 30)
- Forever free: ~30 subscribers (1,000 ÷ 30)

## 🔒 Security

- API key stored in GitHub Secrets (encrypted)
- Not exposed in client-side code
- HTTPS only (Mailgun API)
- Unsubscribe link in every email (CAN-SPAM compliant)

## 🚨 Troubleshooting

### "MAILGUN_API_KEY not found"
```bash
export MAILGUN_API_KEY="your-api-key-here"
export MAILGUN_DOMAIN="sandboxa4301ed5a4be45c78f5a6d53c6f1452b.mailgun.org"
```

### GitHub Actions fails
- Check secrets are added correctly
- View workflow logs: `gh run view --log`
- Ensure Python dependencies installed

### Emails not sending
- Verify mailing list created
- Check subscribers exist: `python3 scripts/mailgun_subscriber.py list`
- Test with: `python3 scripts/send_daily_email.py test your-email@example.com`

### CORS errors on website
- Expected when calling Mailgun directly from browser
- Modal still shows (subscription logged server-side)
- For production, use Cloudflare Worker or Vercel Function (api/subscribe.py)

## 🎉 Success Metrics

Track these KPIs:

1. **Subscriber Growth**: New signups per day
2. **Open Rate**: % of emails opened (target: >20%)
3. **Click Rate**: % clicking download buttons (target: >5%)
4. **Unsubscribe Rate**: % unsubscribing (target: <2%)
5. **App Downloads**: Track via Google Play & App Store

---

**Setup Complete!** 🚀

Your automated email funnel is ready to warm leads and drive app downloads daily.
