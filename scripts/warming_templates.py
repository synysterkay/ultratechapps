#!/usr/bin/env python3
"""
Natural-looking email templates for domain warming.
These simulate real conversations between team members.
"""
import random

# Subjects and bodies that look like internal team communication
WARMING_CONVERSATIONS = [
    {
        "subject": "Quick question about the update",
        "body": "Hey, did you get a chance to look at the changes we discussed? Let me know what you think when you have a moment.",
        "replies": [
            "Yes, I looked at it this morning. Looks good to me — let's go ahead with it.",
            "Not yet, I'll check it later today and get back to you.",
            "I did! Had a couple of small suggestions but overall looks solid.",
        ]
    },
    {
        "subject": "Meeting notes from today",
        "body": "Just wanted to send a quick recap from our call. The main takeaway is we need to finalize the design by Friday. I'll send the doc later.",
        "replies": [
            "Thanks for the summary! I'll review the doc once you share it.",
            "Got it, Friday works. I'll have my part ready by Thursday.",
            "Appreciate the follow-up. Let me know if you need anything from my side.",
        ]
    },
    {
        "subject": "Re: Project timeline",
        "body": "Following up on the timeline — are we still on track for the end of the month? Want to make sure we're aligned before the review.",
        "replies": [
            "We're on track. I'll send a status update tomorrow morning.",
            "Mostly yes, but the API integration might need an extra few days.",
            "All good on my end. Let's sync up mid-week to double-check.",
        ]
    },
    {
        "subject": "Article link you might like",
        "body": "Found this interesting article on app development best practices. Thought you'd find it useful for the current project.",
        "replies": [
            "Great find! Really relevant to what we're working on right now.",
            "Thanks for sharing, bookmarked it for later reading.",
            "This is really helpful, especially the part about user onboarding.",
        ]
    },
    {
        "subject": "Feedback on the draft",
        "body": "I went through the draft you shared yesterday. Overall it's in great shape. Just a few minor tweaks needed in the intro section.",
        "replies": [
            "Perfect, I'll update the intro and resend it this afternoon.",
            "Thanks for reviewing! I'll make those changes now.",
            "Good catch — I wasn't sure about the intro either. Will fix it.",
        ]
    },
    {
        "subject": "Lunch plans?",
        "body": "Hey, are you free for lunch on Thursday? There's a new place downtown I've been wanting to try.",
        "replies": [
            "Thursday works! What time are you thinking?",
            "I'm in! Just send me the address.",
            "Can't do Thursday but Friday works if that's okay?",
        ]
    },
    {
        "subject": "Budget review follow-up",
        "body": "Just circling back on the budget conversation. Can you send me the latest numbers so I can update the spreadsheet?",
        "replies": [
            "Sure, I'll pull the numbers and send them over shortly.",
            "Just attached the updated file — let me know if anything looks off.",
            "On it. Give me an hour to double-check everything first.",
        ]
    },
    {
        "subject": "Weekend plans",
        "body": "Any fun plans for the weekend? I'm thinking about going hiking if the weather holds up.",
        "replies": [
            "Hiking sounds great! Which trail are you thinking?",
            "Nothing major, just catching up on some rest. Enjoy the hike!",
            "I might join you if you don't mind company!",
        ]
    },
    {
        "subject": "New tool recommendation",
        "body": "Have you tried that new project management tool? A couple of people on the team are using it and seem to really like it.",
        "replies": [
            "I've heard good things! Will check it out this week.",
            "Yes, I started using it last week. Pretty intuitive so far.",
            "Not yet but it's on my list. Thanks for the reminder.",
        ]
    },
    {
        "subject": "Quick favor",
        "body": "Could you take a look at the report I sent last week and let me know if the data looks right? Just want a second pair of eyes before I submit it.",
        "replies": [
            "Of course! I'll review it today and send you notes.",
            "Sure thing — I actually noticed one small discrepancy. Let me double-check.",
            "Happy to help. I'll get to it after my 2pm call.",
        ]
    },
    {
        "subject": "Conference next month",
        "body": "Are you planning to attend the tech conference next month? I'm thinking about going — might be good for networking.",
        "replies": [
            "I was on the fence but you've convinced me. Let's go together!",
            "Definitely going! They have some great speakers this year.",
            "Unfortunately can't make it this time, but let me know how it goes.",
        ]
    },
    {
        "subject": "App performance question",
        "body": "Quick question — have you noticed any slowdowns on the dashboard recently? A couple of users mentioned it.",
        "replies": [
            "I noticed it too yesterday. Might be worth checking the database queries.",
            "Haven't seen it on my end, but I'll keep an eye out.",
            "Could be related to the new caching changes. Let me investigate.",
        ]
    },
    {
        "subject": "Thanks for your help",
        "body": "Just wanted to say thanks for helping out with the presentation yesterday. It went really well and the client seemed happy.",
        "replies": [
            "Happy to help! Glad it went well — the client had great questions too.",
            "Anytime! It was a great presentation, you nailed it.",
            "No problem at all. Let me know when the next one comes up.",
        ]
    },
    {
        "subject": "Book recommendation",
        "body": "Just finished reading a really good book on product strategy. Want me to send you the title?",
        "replies": [
            "Yes please! I've been looking for something new to read.",
            "Absolutely, always looking for good recommendations.",
            "Sure! I'll add it to my reading list.",
        ]
    },
    {
        "subject": "Idea for the next sprint",
        "body": "Had an idea for something we could tackle in the next sprint. It's about improving the onboarding flow. Can we chat about it?",
        "replies": [
            "Love that idea! How about we discuss it at standup tomorrow?",
            "Sure, I've had some thoughts on onboarding too. Let's compare notes.",
            "Great timing — I was just looking at our onboarding metrics. Let's talk.",
        ]
    },
]


def get_warming_email():
    """Return a random warming email (subject, body)."""
    convo = random.choice(WARMING_CONVERSATIONS)
    return convo["subject"], convo["body"]


def get_reply_body(subject):
    """Return a natural reply body for a given subject."""
    for convo in WARMING_CONVERSATIONS:
        if convo["subject"] == subject:
            return random.choice(convo["replies"])
    # Fallback generic reply
    return random.choice([
        "Thanks for the update! I'll take a look.",
        "Got it, appreciate you sending this over.",
        "Makes sense — let me know if you need anything else.",
        "Sounds good to me!",
        "Perfect, thanks for following up on this.",
    ])
