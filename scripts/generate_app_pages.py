#!/usr/bin/env python3
"""
Generate landing pages for all apps with marketing-optimized copy
"""
import json
import os
import re
from pathlib import Path

def slugify(text):
    """Convert app name to URL-friendly slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

def get_app_features(app_name, description):
    """Generate feature list based on app type"""
    features_map = {
        'smart notes': [
            {'icon': '🎤', 'title': 'AI-Powered Transcription', 'description': 'Automatically convert speech to text with 95% accuracy using advanced AI technology'},
            {'icon': '🔍', 'title': 'Smart Organization', 'description': 'Intelligent categorization and tagging keeps your notes perfectly organized without manual effort'},
            {'icon': '📊', 'title': 'Meeting Summaries', 'description': 'Get instant AI-generated summaries of meetings, calls, and lectures in seconds'},
            {'icon': '🔄', 'title': 'Cloud Sync', 'description': 'Access your notes anywhere, anytime with automatic cloud synchronization across all devices'}
        ],
        'girlfriend': [
            {'icon': '💬', 'title': 'Meaningful Conversations', 'description': 'Engage in deep, personalized conversations powered by advanced AI that learns your preferences'},
            {'icon': '❤️', 'title': 'Emotional Connection', 'description': 'Experience genuine emotional support and companionship tailored to your needs'},
            {'icon': '🎨', 'title': 'Personalized Experience', 'description': 'Your AI companion adapts to your personality, interests, and communication style'},
            {'icon': '🔒', 'title': '100% Private', 'description': 'All conversations are encrypted and completely confidential - your privacy guaranteed'}
        ],
        'red flag': [
            {'icon': '🚩', 'title': 'Instant Red Flag Detection', 'description': 'AI analyzes relationship patterns and identifies warning signs you might miss'},
            {'icon': '📊', 'title': 'Relationship Insights', 'description': 'Get detailed analysis of communication patterns, behaviors, and compatibility metrics'},
            {'icon': '💡', 'title': 'Expert Guidance', 'description': 'Receive professional advice and actionable steps to improve or protect your relationship'},
            {'icon': '🔐', 'title': 'Anonymous & Secure', 'description': 'Your relationship data stays completely private - no judgment, total confidentiality'}
        ],
        'pupshape': [
            {'icon': '🐕', 'title': 'Personalized Meal Plans', 'description': 'Custom nutrition plans tailored to your dog\'s breed, age, weight, and health goals'},
            {'icon': '📊', 'title': 'Progress Tracking', 'description': 'Monitor weight loss progress with charts, photos, and milestone celebrations'},
            {'icon': '🎯', 'title': 'Activity Recommendations', 'description': 'Get exercise plans designed specifically for your dog\'s fitness level and abilities'},
            {'icon': '👨‍⚕️', 'title': 'Vet-Approved', 'description': 'All plans follow veterinary guidelines for safe, healthy weight loss'}
        ],
        'soccer': [
            {'icon': '⚽', 'title': 'AI Match Predictions', 'description': 'Advanced algorithms analyze team stats, form, and historical data for accurate predictions'},
            {'icon': '📈', 'title': 'Real-Time Analysis', 'description': 'Get live match insights and in-play betting recommendations as games unfold'},
            {'icon': '🏆', 'title': 'Expert Tips', 'description': 'Daily predictions from AI combined with expert analysis for maximum accuracy'},
            {'icon': '📊', 'title': 'Detailed Statistics', 'description': 'Comprehensive team and player stats, head-to-head records, and trend analysis'}
        ],
        'fresh start': [
            {'icon': '💔', 'title': 'Guided Healing Journey', 'description': 'Step-by-step AI-powered therapy program designed specifically for breakup recovery'},
            {'icon': '🧘', 'title': 'Daily Support', 'description': 'Get personalized exercises, affirmations, and coping strategies every single day'},
            {'icon': '📝', 'title': 'Journaling Tools', 'description': 'Process your emotions with guided prompts and track your healing progress over time'},
            {'icon': '🌟', 'title': 'Community Support', 'description': 'Connect with others going through similar experiences in a safe, supportive environment'}
        ],
        'soulplan': [
            {'icon': '💑', 'title': 'AI Date Ideas', 'description': 'Get personalized date suggestions based on your location, interests, budget, and relationship stage'},
            {'icon': '🎯', 'title': 'Swipe to Match', 'description': 'Both partners swipe on date ideas and the app reveals perfect matches you\'ll both love'},
            {'icon': '📅', 'title': 'Shared Planning', 'description': 'Collaborate on date prep with shared to-do lists, timing, and coordination tools'},
            {'icon': '✨', 'title': 'Keep It Fresh', 'description': 'Break out of routine with creative, unique date ideas you\'d never think of alone'}
        ],
        'thesis': [
            {'icon': '✍️', 'title': 'Instant Thesis Generation', 'description': 'AI generates strong, arguable thesis statements in seconds for any topic or subject'},
            {'icon': '📚', 'title': 'Multiple Formats', 'description': 'Get thesis statements for argumentative, analytical, expository, and persuasive essays'},
            {'icon': '🎓', 'title': 'Academic Standards', 'description': 'All generated theses meet college-level academic writing standards and guidelines'},
            {'icon': '💡', 'title': 'Refinement Tools', 'description': 'Edit, improve, and customize your thesis until it\'s perfect for your essay'}
        ],
        'lovestory': [
            {'icon': '📖', 'title': 'Personalized Stories', 'description': 'AI writes romance novels tailored to your preferences - characters, settings, and tropes you love'},
            {'icon': '🎨', 'title': 'Customize Everything', 'description': 'Choose genres, heat levels, character traits, and plot elements for your perfect story'},
            {'icon': '📱', 'title': 'Read Anywhere', 'description': 'Access your growing library of AI-generated novels on any device, offline or online'},
            {'icon': '✨', 'title': 'Unlimited Stories', 'description': 'Generate as many unique romance novels as you want - new stories every day'}
        ],
        'volume booster': [
            {'icon': '🔊', 'title': 'Maximum Volume Boost', 'description': 'Amplify audio beyond device limits for louder music, videos, and calls'},
            {'icon': '🎵', 'title': 'Bass Booster', 'description': 'Enhanced bass and equalizer settings for richer, fuller sound quality'},
            {'icon': '🎧', 'title': 'Safe Amplification', 'description': 'Smart algorithms prevent speaker damage while maximizing volume'},
            {'icon': '⚡', 'title': 'One-Tap Control', 'description': 'Instant volume boost with simple, intuitive controls and presets'}
        ],
        'boyfriend': [
            {'icon': '💬', 'title': 'Intelligent Conversations', 'description': 'Chat with an AI boyfriend who remembers your talks and grows with your relationship'},
            {'icon': '🌟', 'title': 'Build Confidence', 'description': 'Practice social skills and build dating confidence in a safe, judgment-free environment'},
            {'icon': '🎭', 'title': 'Multiple Personalities', 'description': 'Choose from different AI personality types to match your ideal partner preferences'},
            {'icon': '🔒', 'title': 'Completely Private', 'description': 'All your conversations are encrypted and secure - no data sharing, ever'}
        ],
        'kinbound': [
            {'icon': '👨‍👩‍👧', 'title': 'AI Parental Wisdom', 'description': 'Get advice from AI Mom and Dad personalities designed to guide you through life\'s challenges'},
            {'icon': '💝', 'title': 'Emotional Support', 'description': 'Receive comfort, encouragement, and unconditional support whenever you need it'},
            {'icon': '🎯', 'title': 'Practical Guidance', 'description': 'Get actionable advice for career, relationships, finances, and personal growth'},
            {'icon': '🌈', 'title': 'Safe Space', 'description': 'Share anything without judgment in a completely private, confidential environment'}
        ],
        'crypto': [
            {'icon': '📈', 'title': 'AI Trading Signals', 'description': 'Advanced algorithms analyze market trends and provide actionable buy/sell recommendations'},
            {'icon': '💰', 'title': 'Portfolio Tracking', 'description': 'Monitor all your crypto assets in one place with real-time price updates and P&L'},
            {'icon': '🔮', 'title': 'Market Predictions', 'description': 'AI-powered forecasts help you stay ahead of market movements and trends'},
            {'icon': '📊', 'title': 'Risk Analysis', 'description': 'Understand your portfolio risk exposure with detailed metrics and insights'}
        ]
    }
    
    # Match app name to feature set
    name_lower = app_name.lower()
    for key, features in features_map.items():
        if key in name_lower:
            return features
    
    # Default generic features
    return [
        {'icon': '✨', 'title': 'Smart AI Features', 'description': description},
        {'icon': '📱', 'title': 'Easy to Use', 'description': 'Intuitive interface designed for seamless user experience'},
        {'icon': '🔒', 'title': 'Secure & Private', 'description': 'Your data is protected with enterprise-grade security'},
        {'icon': '🚀', 'title': 'Fast & Reliable', 'description': 'Optimized performance for smooth, lag-free experience'}
    ]

def get_marketing_copy(app_name, description):
    """Generate marketing taglines and copy"""
    name_lower = app_name.lower()
    
    if 'smart notes' in name_lower:
        return {
            'tagline': 'Never Miss a Word – AI Takes Notes for You',
            'benefits': [
                'Save 5+ hours per week on note-taking',
                'Never forget important meeting details',
                'Searchable transcripts in seconds'
            ],
            'urgency_text': 'Over 50,000 professionals already use Smart Notes daily!',
            'cta_headline': 'Start Taking Smarter Notes',
            'cta_text': 'Join professionals who save hours every week with AI-powered note-taking. Download free today and get instant access to all features.',
            'rating': '4.8',
            'downloads': '50,000'
        }
    elif 'girlfriend' in name_lower or 'cupid' in name_lower:
        return {
            'tagline': 'Your Perfect AI Companion – Always There for You',
            'benefits': [
                'Combat loneliness with meaningful conversations',
                'Available 24/7 whenever you need someone',
                'Build confidence for real relationships'
            ],
            'urgency_text': 'Join 100,000+ users who found companionship with Cupid AI!',
            'cta_headline': 'Meet Your AI Companion',
            'cta_text': 'Experience emotional connection without judgment. Download free and start chatting in minutes.',
            'rating': '4.7',
            'downloads': '100,000'
        }
    elif 'red flag' in name_lower:
        return {
            'tagline': 'Spot Toxic Relationships Before It\'s Too Late',
            'benefits': [
                'Identify manipulation and gaslighting patterns',
                'Get unbiased analysis of your relationship',
                'Protect yourself with expert guidance'
            ],
            'urgency_text': 'Over 75,000 people avoided toxic relationships with our help!',
            'cta_headline': 'Protect Your Heart Today',
            'cta_text': 'Don't wait until it's too late. Get instant relationship analysis now – completely free and 100% confidential.',
            'rating': '4.9',
            'downloads': '75,000'
        }
    elif 'pupshape' in name_lower:
        return {
            'tagline': 'Healthy Weight Loss Plans for Your Best Friend',
            'benefits': [
                'Vet-approved meal plans for safe weight loss',
                'Track progress with photos and charts',
                'Add years to your dog\'s life'
            ],
            'urgency_text': 'Join 20,000+ dog owners who successfully helped their pets lose weight!',
            'cta_headline': 'Start Your Dog's Health Journey',
            'cta_text': 'Give your furry friend a longer, healthier life. Download free and create a personalized plan today.',
            'rating': '4.8',
            'downloads': '20,000'
        }
    elif 'soccer' in name_lower or 'predictify' in name_lower:
        return {
            'tagline': 'AI-Powered Soccer Predictions That Win',
            'benefits': [
                '85% prediction accuracy rate',
                'Real-time match analysis and insights',
                'Expert tips from AI and analysts'
            ],
            'urgency_text': 'Over 30,000 soccer fans trust our predictions!',
            'cta_headline': 'Get Winning Predictions Now',
            'cta_text': 'Stop guessing, start winning. Download free and get today's expert predictions instantly.',
            'rating': '4.6',
            'downloads': '30,000'
        }
    elif 'fresh start' in name_lower or 'breakup' in name_lower:
        return {
            'tagline': 'Heal from Heartbreak – Your Personal AI Therapist',
            'benefits': [
                'Guided recovery program proven to work',
                'Daily support and coping strategies',
                'Move on faster and stronger'
            ],
            'urgency_text': 'Over 40,000 people healed their hearts with Fresh Start!',
            'cta_headline': 'Start Healing Today',
            'cta_text': 'You don't have to suffer alone. Download free and begin your healing journey right now.',
            'rating': '4.9',
            'downloads': '40,000'
        }
    elif 'soulplan' in name_lower or 'date' in name_lower:
        return {
            'tagline': 'Never Run Out of Amazing Date Ideas Again',
            'benefits': [
                'AI suggests perfect dates for your relationship',
                'Both partners swipe to find matches',
                'Keep romance alive with zero planning stress'
            ],
            'urgency_text': 'Over 60,000 couples plan better dates with SoulPlan!',
            'cta_headline': 'Plan Your Next Perfect Date',
            'cta_text': 'Stop the "what should we do?" stress. Download free and get personalized date ideas instantly.',
            'rating': '4.7',
            'downloads': '60,000'
        }
    elif 'thesis' in name_lower:
        return {
            'tagline': 'Generate A+ Thesis Statements in Seconds',
            'benefits': [
                'AI writes strong thesis statements instantly',
                'Works for any topic or essay type',
                'Meets academic standards'
            ],
            'urgency_text': 'Over 100,000 students improved their grades with our help!',
            'cta_headline': 'Write Better Essays Today',
            'cta_text': 'Stop staring at a blank page. Download free and generate your perfect thesis statement now.',
            'rating': '4.8',
            'downloads': '100,000'
        }
    elif 'lovestory' in name_lower or 'romance' in name_lower:
        return {
            'tagline': 'Read Personalized Romance Novels Written Just for You',
            'benefits': [
                'AI creates stories based on your preferences',
                'Unlimited novels at your fingertips',
                'Your characters, your tropes, your perfect story'
            ],
            'urgency_text': 'Join 25,000+ romance lovers reading personalized novels!',
            'cta_headline': 'Start Reading Your Story',
            'cta_text': 'Never run out of romance again. Download free and generate your first personalized novel today.',
            'rating': '4.7',
            'downloads': '25,000'
        }
    elif 'volume' in name_lower or 'booster' in name_lower:
        return {
            'tagline': 'Boost Your Audio to Maximum Volume – Safely',
            'benefits': [
                'Amplify volume beyond device limits',
                'Enhanced bass and sound quality',
                'Works with music, videos, and calls'
            ],
            'urgency_text': 'Over 200,000 users enjoy louder, clearer audio!',
            'cta_headline': 'Boost Your Volume Now',
            'cta_text': 'Stop straining to hear. Download free and experience maximum audio power instantly.',
            'rating': '4.5',
            'downloads': '200,000'
        }
    elif 'boyfriend' in name_lower:
        return {
            'tagline': 'Practice Dating & Build Confidence with Your AI Boyfriend',
            'benefits': [
                'Safe space to practice conversation skills',
                'Build dating confidence without pressure',
                'Available 24/7 for support and chat'
            ],
            'urgency_text': 'Join 35,000+ users building confidence with AI Boyfriend!',
            'cta_headline': 'Meet Your AI Boyfriend',
            'cta_text': 'Build the confidence you need for real relationships. Download free and start chatting now.',
            'rating': '4.6',
            'downloads': '35,000'
        }
    elif 'kinbound' in name_lower or 'parent' in name_lower:
        return {
            'tagline': 'The Parental Guidance You Always Needed – Now Powered by AI',
            'benefits': [
                'Get advice from AI Mom and Dad',
                'Emotional support whenever you need it',
                'Practical guidance for life decisions'
            ],
            'urgency_text': 'Over 15,000 users found the support they needed!',
            'cta_headline': 'Get the Support You Deserve',
            'cta_text': 'You're not alone anymore. Download free and talk to AI parents who truly care.',
            'rating': '4.9',
            'downloads': '15,000'
        }
    elif 'crypto' in name_lower:
        return {
            'tagline': 'Trade Smarter with AI-Powered Crypto Insights',
            'benefits': [
                'AI analyzes markets 24/7 for you',
                'Get buy/sell signals backed by data',
                'Track your entire portfolio in one place'
            ],
            'urgency_text': 'Join 45,000+ traders using AI for better decisions!',
            'cta_headline': 'Start Trading Smarter',
            'cta_text': 'Stop losing money on bad trades. Download free and get AI-powered insights instantly.',
            'rating': '4.6',
            'downloads': '45,000'
        }
    
    # Default
    return {
        'tagline': f'Transform Your Experience with {app_name}',
        'benefits': [
            'AI-powered features that save you time',
            'Easy to use, instant results',
            'Trusted by thousands of users'
        ],
        'urgency_text': 'Join thousands of satisfied users today!',
        'cta_headline': 'Get Started Now',
        'cta_text': 'Download free and experience the difference instantly.',
        'rating': '4.5',
        'downloads': '10,000'
    }

def generate_app_page(app, apps_dir):
    """Generate a landing page for an app"""
    slug = slugify(app['name'])
    marketing = get_marketing_copy(app['name'], app['description'])
    features = get_app_features(app['name'], app['description'])
    
    # Determine hero image based on app type
    hero_images = {
        'smart notes': 'https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=800&q=80',
        'girlfriend': 'https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=800&q=80',
        'red flag': 'https://images.unsplash.com/photo-1518199266791-5375a83190b7?w=800&q=80',
        'pupshape': 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&q=80',
        'soccer': 'https://images.unsplash.com/photo-1522778119026-d647f0596c20?w=800&q=80',
        'fresh start': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=800&q=80',
        'soulplan': 'https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=800&q=80',
        'thesis': 'https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=800&q=80',
        'lovestory': 'https://images.unsplash.com/photo-1512820790803-83ca734da794?w=800&q=80',
        'volume': 'https://images.unsplash.com/photo-1501290741922-b56c0d0884af?w=800&q=80',
        'boyfriend': 'https://images.unsplash.com/photo-1571902943202-507ec2618e8f?w=800&q=80',
        'kinbound': 'https://images.unsplash.com/photo-1476703993599-0035a21b17a9?w=800&q=80',
        'crypto': 'https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=800&q=80',
    }
    
    hero_image = 'https://images.unsplash.com/photo-1551650975-87deedd944c3?w=800&q=80'
    for key, img in hero_images.items():
        if key in app['name'].lower():
            hero_image = img
            break
    
    # Build YAML frontmatter
    content = f"""---
layout: app
title: "{app['name']}"
app_name: "{app['name']}"
permalink: /apps/{slug}/
description: "{app['description']}"
tagline: "{marketing['tagline']}"
hero_image: "{hero_image}"
google_play_url: "{app['google_play_url']}"
app_store_url: "{app['app_store_url']}"
category: "ai-tools"
rating: "{marketing['rating']}"
downloads: "{marketing['downloads']}"

# Benefits (show in hero)
benefits:
"""
    
    for benefit in marketing['benefits']:
        content += f'  - "{benefit}"\n'
    
    content += f"""
urgency_text: "{marketing['urgency_text']}"

# Features
features:
"""
    
    for feature in features:
        content += f"""  - icon: "{feature['icon']}"
    title: "{feature['title']}"
    description: "{feature['description']}"
"""
    
    content += f"""
# CTA Section
cta_headline: "{marketing['cta_headline']}"
cta_text: "{marketing['cta_text']}"
cta_benefit_1: "100% Free"
cta_benefit_2: "No Credit Card"
cta_benefit_3: "Instant Access"
---

<!-- Page content is generated from the app layout template -->
"""
    
    # Write file
    file_path = apps_dir / f"{slug}.md"
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Generated: {slug}.md")
    return slug

def main():
    # Load apps
    apps_file = Path(__file__).parent.parent / "apps.json"
    with open(apps_file, 'r') as f:
        apps = json.load(f)
    
    # Create apps directory
    apps_dir = Path(__file__).parent.parent / "apps"
    apps_dir.mkdir(exist_ok=True)
    
    print("🚀 Generating app landing pages...")
    print()
    
    slugs = []
    for app in apps:
        slug = generate_app_page(app, apps_dir)
        slugs.append(slug)
    
    print()
    print(f"✅ Generated {len(slugs)} app landing pages!")
    print()
    print("📍 Pages available at:")
    for slug in slugs:
        print(f"   https://bestaiapps.site/apps/{slug}/")

if __name__ == '__main__':
    main()
