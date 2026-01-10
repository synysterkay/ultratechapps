# Email Templates Documentation

This directory contains email template documentation and examples for the Best AI Apps newsletter system.

## Email Sequence Overview

### Welcome Sequence (Days 0, 3, 7)
New subscribers receive 3 carefully timed emails to build trust and introduce value.

**Day 0 - Immediate Value**
- Goal: Set expectations, deliver quick win
- Subject style: "Your AI toolkit is ready (here's what's inside)"
- App mention: Subtle (brief reference)
- Value ratio: 90%

**Day 3 - Problem/Solution**
- Goal: Identify common problem, provide solution
- Subject style: "The mistake 87% of people make with [niche]"
- App mention: Natural (integrated into solution)
- Value ratio: 80%

**Day 7 - Transformation Story**
- Goal: Show results, feature app as key tool
- Subject style: "This changes everything about [niche]"
- App mention: Featured (highlighted role)
- Value ratio: 70%

### Value Sequence (Every 2 days)
Ongoing emails that provide consistent value with subtle app promotions.

**Email Pattern:**
- 70% valuable tips/insights
- 30% app integration
- Subject style: No emojis, curiosity/urgency-driven
- Examples:
  - "What nobody tells you about [topic]"
  - "I tested 47 solutions. Here's what actually works"
  - "3 [niche] hacks that saved me 10 hours this week"

### Promotional Sequence (Once per week)
Direct app promotion for loyal subscribers who've built trust.

**Email Pattern:**
- Primary focus on app features and benefits
- Strong value proposition
- Social proof and urgency
- Subject style: FOMO and scarcity
- Examples:
  - "Join 10,000+ who discovered this [niche] tool first"
  - "Time-sensitive: Your [niche] needs this now"

## AI-Generated Content

All email content is dynamically generated using DeepSeek API based on:
- Subscriber's niche (productivity, relationships, wellness, etc.)
- Journey stage (newcomer, engaged, loyal)
- App being featured
- Psychological triggers (curiosity, urgency, FOMO, authority)

## HTML Template Structure

All emails use consistent HTML structure:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    
    <!-- Header with branding -->
    <div style="gradient background, centered logo">
        Best AI Apps
    </div>
    
    <!-- AI-generated body content -->
    <div style="conversational paragraphs">
        [Dynamic content from DeepSeek]
    </div>
    
    <!-- Key Takeaways (if applicable) -->
    <div style="highlighted box with bullet points">
        [Optional summary points]
    </div>
    
    <!-- Call to Action -->
    <div style="centered button">
        [Soft invitation or direct CTA]
    </div>
    
    <!-- Footer with links -->
    <div style="small text, unsubscribe">
        Links, unsubscribe
    </div>
    
</body>
</html>
```

## Customization

Templates are generated dynamically by `scripts/email_sequence_manager.py` using:
- Content from `scripts/email_generator.py` (DeepSeek AI)
- Configuration from `config/email_config.json`
- Subscriber metadata from Mailgun

## Subject Line Strategy

**NO EMOJIS** - Keeps professional, avoids spam filters

**Proven Patterns:**
- Curiosity gap: "The [niche] secret nobody's talking about"
- Social proof: "Why everyone's switching to this method"
- Urgency: "Tomorrow's too late for this"
- Authority: "After testing 50 apps, here's the winner"
- Problem-aware: "Tired of wasting 3 hours daily on this?"

## Best Practices

1. **Value First**: Always lead with helpful content
2. **Natural Integration**: Apps mentioned as tools, not sales pitches
3. **Conversational Tone**: Write like talking to a friend
4. **Specific Details**: Use numbers, timeframes, concrete examples
5. **Soft CTAs**: Invitations, not demands
6. **Mobile-Friendly**: Responsive design, short paragraphs
7. **Track Everything**: Opens, clicks, unsubscribes inform future content
