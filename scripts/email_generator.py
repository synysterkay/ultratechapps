#!/usr/bin/env python3
"""
AI Email Content Generator using DeepSeek API
Generates personalized, high-value email content based on niche and sequence stage
"""
import os
import sys
import json
import random
import requests
from pathlib import Path
from datetime import datetime

class EmailGenerator:
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.api_url = 'https://api.deepseek.com/v1/chat/completions'
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")
        
        # Load configuration
        config_file = Path(__file__).parent.parent / "config" / "email_config.json"
        with open(config_file, 'r') as f:
            self.config = json.load(f)
    
    def _build_prompt(self, niche, app_data, sequence_type, day=None):
        """Build DeepSeek prompt for email generation"""
        
        # Get niche information
        niche_info = self.config['niches'].get(niche, self.config['niches']['productivity'])
        pain_points = niche_info.get('pain_points', [])
        keywords = niche_info.get('keywords', [])
        
        # Get sequence configuration
        if sequence_type == 'welcome' and day is not None:
            sequence_config = self.config['sequences']['welcome'].get(f'day_{day}', self.config['sequences']['welcome']['day_0'])
        elif sequence_type == 'value':
            sequence_config = self.config['sequences']['value_sequence']
        else:
            sequence_config = self.config['sequences']['promotional']
        
        # Select random subject template
        subject_templates = sequence_config.get('subject_templates', [])
        subject_template = random.choice(subject_templates) if subject_templates else "Improve Your {niche}"
        
        # Replace placeholders in subject
        subject = subject_template.replace('{niche}', niche).replace('{topic}', random.choice(keywords))
        if '{pain_point}' in subject:
            subject = subject.replace('{pain_point}', random.choice(pain_points))
        if '{old_method}' in subject:
            subject = subject.replace('{old_method}', f'traditional {niche} methods')
        
        # Get email type structure
        email_type = sequence_config.get('type', 'tips_value')
        type_config = self.config['email_types'].get(email_type, self.config['email_types']['tips_value'])
        
        # Get app mention style
        app_mention = sequence_config.get('app_mention', 'integrated')
        value_ratio = sequence_config.get('value_ratio', 70)
        
        # Build comprehensive prompt
        prompt = f"""You are an expert email marketer writing for Best AI Apps.

TARGET AUDIENCE: People interested in {niche}
NICHE PAIN POINTS: {', '.join(pain_points)}
KEYWORDS TO USE: {', '.join(keywords)}

APP TO FEATURE:
Name: {app_data['name']}
Description: {app_data['description']}

EMAIL TYPE: {email_type}
SEQUENCE STAGE: {sequence_type}
EMAIL STRUCTURE: {' → '.join(type_config['structure'])}
TONE: {type_config['tone']}

APP MENTION STYLE:
- "{app_mention}" (subtle = brief mention, natural = integrated into content, featured = main focus, primary = direct promotion)
- Value/Promotion Ratio: {value_ratio}% value content

PSYCHOLOGICAL TRIGGERS TO USE: {', '.join(sequence_config.get('psychological_triggers', []))}

SUBJECT LINE (already generated): {subject}

REQUIREMENTS:
1. Write {self.config['content_generation']['word_count_range'][0]}-{self.config['content_generation']['word_count_range'][1]} words
2. {self.config['content_generation']['paragraph_count'][0]}-{self.config['content_generation']['paragraph_count'][1]} paragraphs
3. NO EMOJIS in body text
4. Conversational, authentic tone - write like a helpful friend
5. Include specific, actionable tips/insights
6. Personal anecdotes or data points for credibility
7. Natural app integration (don't be pushy or salesy)
8. Soft CTA at end (invitation, not demand)
9. Write in first person ("I tested", "Here's what I discovered")
10. Start with a hook that creates curiosity or addresses pain point
11. NEVER use the word "newsletter" - this is an email series from Best AI Apps
12. Don't say "you subscribed to our newsletter" - say "you joined Best AI Apps" or similar

STRUCTURE GUIDELINE:
{self._get_structure_guide(type_config['structure'], app_data['name'], app_mention)}

OUTPUT FORMAT (JSON):
{{
  "subject": "{subject}",
  "preview_text": "80-100 character preview text for email clients",
  "body_paragraphs": [
    "paragraph 1 (opening hook)",
    "paragraph 2 (context/problem)",
    "paragraph 3 (value/tips)",
    "paragraph 4 (more value/solution)",
    "paragraph 5 (app mention if applicable)",
    "paragraph 6 (closing/CTA)"
  ],
  "cta_text": "Soft invitation CTA text",
  "cta_url": "{app_data.get('google_play_url') or app_data.get('app_store_url', '')}",
  "key_takeaways": ["takeaway 1", "takeaway 2", "takeaway 3"]
}}

Generate the email content now:"""
        
        return prompt
    
    def _get_structure_guide(self, structure, app_name, app_mention):
        """Get detailed structure guidance based on email type"""
        guides = {
            "warm_welcome": f"Start with warm, personal welcome. Make subscriber feel they made right choice.",
            "expectation_setting": f"Tell them what to expect: valuable tips, app recommendations, no spam.",
            "quick_win_tip": f"Give immediately actionable tip they can use today.",
            "subtle_app_intro": f"Briefly mention {app_name} as 'tool I use' without pushing.",
            "relatable_problem": f"Open with problem statement subscriber will nod along to.",
            "why_it_matters": f"Explain impact/cost of not solving this problem.",
            "common_mistakes": f"List 2-3 mistakes people make (builds authority).",
            "solution_framework": f"Provide clear, actionable solution steps.",
            "app_as_tool": f"Introduce {app_name} as helpful tool for implementing solution.",
            "before_state": f"Paint picture of struggle/frustration (relatable).",
            "struggle_points": f"Specific pain points experienced.",
            "discovery_moment": f"How you discovered the solution.",
            "results": f"Concrete results/improvements achieved.",
            "app_role": f"How {app_name} played a role in transformation.",
            "attention_hook": f"Bold statement or question that grabs attention.",
            "tip_1": f"First actionable insight with specific details.",
            "tip_2": f"Second insight that builds on first.",
            "tip_3": f"Third insight or bonus tip.",
            "bonus_tool": f"Mention {app_name} as bonus resource.",
            "strong_hook": f"Urgent or curiosity-driven opening.",
            "pain_point_amplification": f"Make problem feel acute and timely.",
            "app_introduction": f"Introduce {app_name} as THE solution.",
            "feature_benefits": f"Specific features and their benefits.",
            "social_proof": f"Mention user count or success stories.",
            "urgent_cta": f"Time-sensitive call to action."
        }
        
        guide_parts = [guides.get(part, f"{part}") for part in structure]
        return "\n".join([f"- {part}" for part in guide_parts])
    
    def generate_email(self, niche, app_data, sequence_type='value', day=None):
        """Generate email content using DeepSeek API"""
        
        prompt = self._build_prompt(niche, app_data, sequence_type, day)
        
        try:
            response = requests.post(
                self.api_url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'You are an expert email copywriter specializing in value-driven marketing that builds trust and engagement.'
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    'temperature': 0.8,
                    'max_tokens': 2000
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parse JSON response
                try:
                    # Extract JSON from markdown code blocks if present
                    if '```json' in content:
                        content = content.split('```json')[1].split('```')[0].strip()
                    elif '```' in content:
                        content = content.split('```')[1].split('```')[0].strip()
                    
                    # Clean up common JSON issues
                    content = content.strip()
                    
                    # Try to parse as-is first
                    try:
                        email_data = json.loads(content, strict=False)
                    except json.JSONDecodeError as e:
                        # If direct parse fails, try to find and extract valid JSON
                        import re
                        # Find the JSON object (from first { to last })
                        json_match = re.search(r'\{[\s\S]*\}', content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group()
                            # Try to fix common issues
                            json_str = json_str.replace('\n', ' ')  # Remove newlines in strings
                            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
                            email_data = json.loads(json_str, strict=False)
                        else:
                            print(f"Debug - Full content:\n{content}")
                            raise json.JSONDecodeError("No valid JSON found", content, 0)
                    
                    # Add metadata
                    email_data['niche'] = niche
                    email_data['app_name'] = app_data['name']
                    email_data['sequence_type'] = sequence_type
                    email_data['generated_at'] = datetime.now().isoformat()
                    
                    return email_data
                    
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse JSON response: {e}")
                    print(f"Raw content: {content}")
                    return None
            else:
                print(f"❌ DeepSeek API error: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Exception calling DeepSeek API: {str(e)}")
            return None
    
    def generate_subject_variants(self, niche, sequence_type='value', count=2):
        """Generate multiple subject line variants for A/B testing"""
        
        if sequence_type == 'welcome':
            sequence_config = self.config['sequences']['welcome']['day_0']
        else:
            sequence_config = self.config['sequences'].get(f'{sequence_type}_sequence', self.config['sequences']['value_sequence'])
        
        templates = sequence_config.get('subject_templates', [])
        
        # Get niche keywords for replacement
        niche_info = self.config['niches'].get(niche, self.config['niches']['productivity'])
        keywords = niche_info.get('keywords', [niche])
        pain_points = niche_info.get('pain_points', ['challenges'])
        
        variants = []
        selected_templates = random.sample(templates, min(count, len(templates)))
        
        for template in selected_templates:
            subject = template.replace('{niche}', niche)
            subject = subject.replace('{topic}', random.choice(keywords))
            
            if '{pain_point}' in subject:
                subject = subject.replace('{pain_point}', random.choice(pain_points))
            if '{old_method}' in subject:
                subject = subject.replace('{old_method}', f'traditional {niche}')
            
            variants.append(subject)
        
        return variants


def main():
    """Test email generation"""
    if len(sys.argv) < 3:
        print("Usage: python3 email_generator.py <niche> <sequence_type> [day]")
        print("Example: python3 email_generator.py productivity welcome 0")
        print("Example: python3 email_generator.py relationships value")
        sys.exit(1)
    
    niche = sys.argv[1]
    sequence_type = sys.argv[2]
    day = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    generator = EmailGenerator()
    
    # Load sample app
    apps_file = Path(__file__).parent.parent / "apps.json"
    with open(apps_file, 'r') as f:
        apps = json.load(f)
    
    # Select app from niche
    niche_config = generator.config['niches'].get(niche)
    if niche_config and 'apps' in niche_config:
        matching_apps = [app for app in apps if app['name'] in niche_config['apps']]
        app = matching_apps[0] if matching_apps else apps[0]
    else:
        app = apps[0]
    
    print(f"🤖 Generating {sequence_type} email for {niche} niche...")
    print(f"📱 Featuring: {app['name']}")
    print()
    
    email_data = generator.generate_email(niche, app, sequence_type, day)
    
    if email_data:
        print("✅ Email generated successfully!")
        print()
        print("=" * 60)
        print(f"SUBJECT: {email_data['subject']}")
        print(f"PREVIEW: {email_data['preview_text']}")
        print("=" * 60)
        print()
        for i, para in enumerate(email_data['body_paragraphs'], 1):
            print(f"Paragraph {i}:")
            print(para)
            print()
        print("=" * 60)
        print(f"CTA: {email_data['cta_text']}")
        print(f"URL: {email_data['cta_url']}")
        print("=" * 60)
    else:
        print("❌ Failed to generate email")
        sys.exit(1)


if __name__ == '__main__':
    main()
