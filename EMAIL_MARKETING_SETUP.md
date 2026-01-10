# Advanced Email Marketing System - Setup Guide

## Overview

This is a sophisticated, AI-powered email marketing system that:
- ✅ Generates personalized content using DeepSeek AI
- ✅ Tracks subscriber journey stages (newcomer → engaged → loyal)
- ✅ Sends welcome sequences (Day 0, 3, 7)
- ✅ Delivers value emails every 2 days
- ✅ Runs promotional campaigns weekly
- ✅ No emojis in subjects (professional, spam-filter friendly)
- ✅ Uses psychological triggers (curiosity, urgency, FOMO, authority)
- ✅ 70/30 value-to-promotion ratio

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GitHub Actions                        │
│            (Runs daily at 9 AM UTC)                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │  email_sequence_manager.py │
        │  (Orchestrator)            │
        └─────────┬──────────────────┘
                  │
        ┌─────────┼─────────┐
        │         │         │
        ▼         ▼         ▼
   ┌────────┐ ┌─────────┐ ┌──────────┐
   │Mailgun │ │DeepSeek │ │Config    │
   │Subs    │ │AI Gen   │ │JSON      │
   └────────┘ └─────────┘ └──────────┘
```

## File Structure

```
/Volumes/Flow/marketing-tool/
├── config/
│   └── email_config.json          # Niches, sequences, triggers
├── scripts/
│   ├── email_generator.py         # DeepSeek AI content generation
│   ├── email_sequence_manager.py  # Main orchestrator
│   ├── mailgun_subscriber.py      # Subscriber management (updated)
│   └── send_daily_email.py        # Old system (kept for reference)
├── email_templates/
│   └── README.md                  # Template documentation
├── .github/workflows/
│   └── email-campaign.yml         # Daily automation
└── apps.json                      # App database

```

## Configuration

### Niches Supported

1. **Productivity** - Smart Notes, Thesis Generator
2. **Relationships** - AI Girlfriend, Red Flag Scanner, Breakup Therapy, Date Planning, AI Boyfriend
3. **Wellness** - Dog Weight Loss
4. **Entertainment** - Reddit Downloader, Romance Novels
5. **Finance** - Crypto Trading Analyzer
6. **Lifestyle** - Volume Booster
7. **Sports** - Soccer Predictions
8. **Personal Growth** - AI Parent Life Coach

### Email Sequences

**Welcome Sequence (3 emails)**
- Day 0: Immediate value, set expectations (90% value)
- Day 3: Problem/solution, natural app mention (80% value)
- Day 7: Transformation story, featured app (70% value)

**Value Sequence (every 2 days)**
- Educational content with actionable tips
- Subtle app integration (70% value, 30% promotion)

**Promotional Sequence (once per week)**
- Direct app features and benefits
- Strong CTA with urgency (40% value, 60% promotion)

## Setup Instructions

### 1. GitHub Secrets (Already Configured)

```bash
# Verify secrets are set
gh secret list
```

Expected secrets:
- ✅ `MAILGUN_API_KEY`
- ✅ `MAILGUN_DOMAIN`
- ✅ `DEEPSEEK_API_KEY`

### 2. Test Locally

**Add a subscriber with niche tracking:**
```bash
export MAILGUN_API_KEY="your_key"
export MAILGUN_DOMAIN="bestaiapps.site"

# Add subscriber (specify niche)
python3 scripts/mailgun_subscriber.py add email@example.com "Name" productivity
```

**Test email generation:**
```bash
export DEEPSEEK_API_KEY="your_key"

# Generate welcome email (Day 0)
python3 scripts/email_generator.py productivity welcome 0

# Generate value email
python3 scripts/email_generator.py relationships value
```

**Run full campaign (dry run):**
```bash
# Make sure all env vars are set
export MAILGUN_API_KEY="..."
export MAILGUN_DOMAIN="bestaiapps.site"
export DEEPSEEK_API_KEY="..."

# Process all subscribers
python3 scripts/email_sequence_manager.py
```

### 3. Manual GitHub Actions Trigger

```bash
# Trigger workflow manually
gh workflow run email-campaign.yml

# Check status
gh run list --workflow=email-campaign.yml

# View logs
gh run view <run-id> --log
```

## Subscriber Journey

```
New Subscriber
     │
     ├─ Day 0: Welcome Email (immediate)
     │         "Your AI toolkit is ready"
     │         90% value, subtle app mention
     │
     ├─ Day 3: Problem/Solution
     │         "The mistake 87% make..."
     │         80% value, natural app mention
     │
     ├─ Day 7: Transformation Story
     │         "This changes everything..."
     │         70% value, featured app
     │
     ▼
Engaged Subscriber (Days 8-30)
     │
     ├─ Value Email every 2 days
     │   70% tips/insights, 30% app integration
     │   Subjects: curiosity, authority, problem-aware
     │
     ▼
Loyal Subscriber (Day 31+)
     │
     ├─ Value Email every 2 days
     └─ + Promotional Email once per week
         FOMO, urgency, social proof
```

## Subscriber Metadata Tracking

Each subscriber has these metadata fields:

```json
{
  "subscribed_at": "2026-01-10T20:00:00",
  "source": "bestaiapps.site",
  "status": "active",
  "niche": "productivity",
  "sequence_stage": "welcome",
  "welcome_day": 0,
  "last_email_sent": "2026-01-10T20:05:00",
  "emails_received": 1,
  "opens": 0,
  "clicks": 0
}
```

## Subject Line Strategy

**NO EMOJIS** - Professional, avoids spam filters

**Proven Patterns:**

Curiosity:
- "The productivity secret nobody's talking about"
- "What I learned spending $2000 on AI tools"

Urgency:
- "Tomorrow's too late for this"
- "Time-sensitive: Your workflow is outdated"

FOMO:
- "While others struggle, these people thrive"
- "Join 10,000+ who discovered this first"

Authority:
- "I tested 50 apps. Here's the winner"
- "After 6 months, here's what actually works"

Problem-Solution:
- "Tired of wasting 3 hours daily on this?"
- "Stop losing money to bad decisions"

## AI Content Generation

DeepSeek generates:
- Subject lines (from templates + niche keywords)
- 250-400 word email body
- 4-6 conversational paragraphs
- 3 key takeaways
- Soft CTA (invitation, not demand)
- Preview text for email clients

**Psychological Triggers Used:**
- Curiosity gap
- Loss aversion
- Social proof
- Authority
- Reciprocity
- Scarcity
- Specificity (numbers, data)

## Monitoring & Analytics

**Check campaign results:**
```bash
# View recent workflow runs
gh run list --workflow=email-campaign.yml --limit 10

# See detailed logs
gh run view <run-id> --log
```

**Mailgun Dashboard:**
- Opens, clicks, unsubscribes
- Delivery rates
- Bounce tracking
- Domain reputation

## Customization

### Add New Niche

Edit `config/email_config.json`:

```json
"new_niche": {
  "keywords": ["keyword1", "keyword2"],
  "pain_points": ["pain1", "pain2"],
  "apps": ["App Name from apps.json"]
}
```

### Add Subject Templates

Add to any sequence in `config/email_config.json`:

```json
"subject_templates": [
  "Your new subject with {niche} placeholder"
]
```

### Adjust Timing

**Welcome sequence days:**
Edit `email_sequence_manager.py` → `_should_send_email()` method

**Value sequence cadence:**
Change `days_since_last >= 2` to desired days

**Promotional frequency:**
Change `days_since_last >= 7` to desired days

## Troubleshooting

**Subscriber not receiving emails:**
```bash
# Check subscriber metadata
python3 scripts/mailgun_subscriber.py list

# Verify they're in correct sequence stage
# Check last_email_sent timestamp
```

**Email generation fails:**
- Check DEEPSEEK_API_KEY is valid
- Verify API quota not exceeded
- Review error logs in GitHub Actions

**Mailgun errors:**
- Check domain is verified
- Verify SPF/DMARC/BIMI DNS records
- Review sending quota

## Best Practices

1. **Start Small**: Test with yourself first
2. **Monitor Metrics**: Track open rates, clicks, unsubscribes
3. **Iterate Content**: Adjust templates based on performance
4. **Segment Carefully**: Use niches to personalize
5. **Respect Privacy**: Clear unsubscribe in every email
6. **Stay Valuable**: 70% value is minimum, 80-90% for new subscribers
7. **Test Subject Lines**: A/B test enabled in config
8. **Review AI Output**: Spot-check generated emails for quality

## Cost Analysis

**Mailgun:**
- Free tier: 5,000 emails/month
- Pay-as-you-go: $0.80 per 1,000 emails

**DeepSeek API:**
- Very affordable compared to OpenAI
- ~$0.14 per 1M input tokens
- ~$0.28 per 1M output tokens
- Estimated cost: ~$0.001 per email

**For 1,000 subscribers:**
- ~3,000 emails/month (welcome + value + promo)
- Mailgun: Free tier or $2.40/month
- DeepSeek: ~$3/month
- **Total: ~$5.40/month** for 1,000 engaged subscribers

## Migration from Old System

Old `send_daily_email.py` sent same app to everyone daily.

New system:
- ✅ Personalized based on niche
- ✅ Journey-aware (welcome vs value vs promo)
- ✅ AI-generated unique content
- ✅ Timing based on subscriber stage
- ✅ Value-first approach

Both systems coexist. To switch completely, the GitHub Actions workflow now uses the new `email_sequence_manager.py`.

## Support

For issues or questions:
1. Check GitHub Actions logs
2. Review Mailgun dashboard
3. Test locally with test subscribers
4. Adjust config/email_config.json

## Future Enhancements

- [ ] A/B testing implementation
- [ ] Automated niche detection from signup source
- [ ] Re-engagement campaigns for inactive subscribers
- [ ] Dynamic content blocks
- [ ] Advanced segmentation (behavior-based)
- [ ] Integration with analytics platforms
