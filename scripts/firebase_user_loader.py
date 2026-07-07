#!/usr/bin/env python3
"""
Firebase User Loader
Loads users from Firebase Auth exports per app.
Maps Firebase project IDs to app names.
Supports both static exports and live re-export via Firebase CLI.
"""
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime


# Map Firebase project IDs to app names and store URLs
FIREBASE_APPS = {
    'thesis-generator-web': {
        'name': 'Thesis Generator',
        'export_file': 'thesis_web_users.json',
        'description': 'AI-powered thesis statement generator and essay writing assistant',
        'app_store_url': 'https://apps.apple.com/app/thesis-generator-essay-ai/id6739264844',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.thesis.generator.ai',
    },
    'redflagscanner': {
        'name': 'Red Flag Scanner AI',
        'export_file': 'redflagscanner_fresh.json',
        'description': 'AI-powered relationship analyzer to identify red flags and toxic patterns',
        'app_store_url': 'https://apps.apple.com/app/red-flag-scanner-ai/id6740946063',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.redflag.scanner.ai.red_flag_scanner',
    },
    'breakuptherapy-e7dc0': {
        'name': 'Fresh Start: Breakup Therapy',
        'export_file': 'breakuptherapy-e7dc0_fresh.json',
        'description': 'AI-powered breakup therapy and emotional healing support',
        'app_store_url': 'https://apps.apple.com/app/fresh-start-breakup-therapy-ai/id6749954260',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.breakup.therapy.therapyforabreakup.therapistforbreakups',
    },
    'soulplan-dateplanner': {
        'name': 'SoulPlan: Plan Dates Together',
        'export_file': 'soulplan-dateplanner_fresh.json',
        'description': 'AI-powered date planning app to discover romantic activities together',
        'app_store_url': 'https://apps.apple.com/app/soulplan-plan-dates-together/id6702018988',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.aifun.dateideas.planadate',
    },
    'petmealai': {
        'name': 'PupShape: Dog Weight Loss Plan',
        'export_file': 'petmealai_fresh.json',
        'description': 'Personalized meal plans and weight loss strategies for your dog',
        'app_store_url': 'https://apps.apple.com/app/pupshape-dog-weight-loss-plan/id6739601749',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.mealplanner.foodofdogs.petmeal',
    },
    'parents-ai-e49a8': {
        'name': 'Kinbound: AI Parent Life Coach',
        'export_file': 'parents_ai_e49a8_fresh.json',
        'description': 'AI parenting coach for meltdowns, bedtime, and hard moments — scripts when you need them',
        'app_store_url': 'https://apps.apple.com/app/kinbound-ai-parent-life-coach/id6757409071',
        'google_play_url': '',
        'multilingual': True,
        'supported_languages': [
            'en', 'es', 'fr', 'de', 'it', 'pt', 'nl', 'ja', 'ko', 'zh',
            'ar', 'hi', 'id', 'pl', 'ru', 'tr',
        ],
    },
    'predictify-3f30d': {
        'name': 'Predictify',
        'export_file': 'predictify_fresh.json',
        'description': 'AI-powered soccer predictions with advanced analytics for Premier League, La Liga, Champions League and more',
        'app_store_url': 'https://apps.apple.com/app/predictify-soccer-ai/id6756571193',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.predictify.soccer.prediction',
        'multilingual': True,
        'supported_languages': ['en', 'ar', 'es', 'fr'],
    },
    'nba-predictify': {
        'name': 'Predictify: NBA AI',
        'export_file': 'predictify_nba_fresh.json',
        'description': 'AI-powered NBA predictions with calibrated confidence — moneyline, spread, totals & player props, plus injuries and playoff analysis',
        'app_store_url': 'https://apps.apple.com/app/predictify-nba-ai/id0000000000',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.predictify.nba.prediction',
        'multilingual': True,
        'supported_languages': ['en', 'ar', 'de', 'es', 'fr', 'hi', 'id', 'it', 'ja', 'nl', 'pl', 'pp', 'pt', 'tr'],
    },
    'volume-booster-2f7bf': {
        'name': 'Volume Booster - Sound Booster',
        'export_file': 'volume_booster_fresh.json',
        'description': 'Boost volume to max! Sound amplifier, bass booster & equalizer for louder audio',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.volume.booster.free.pro',
        'app_store_url': '',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'zh', 'hi', 'pt', 'ru'],
    },
    'bass-booster-ce615': {
        'name': 'Bass Booster',
        'export_file': 'bass_booster_fresh.json',
        'description': '10-band EQ, 200% boost, real bass you feel in your chest — for Hip-Hop, EDM, Rock',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.soundamplifier.volumeboosterforandroid.volumeboostergoodev.bassboosterequalizer',
        'app_store_url': '',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'ar', 'zh', 'hi', 'pt', 'ru'],
    },
    'loud-eq': {
        'name': 'Loud EQ',
        'export_file': 'loud_eq_fresh.json',
        'description': '+200% volume, 5-band EQ, one-tap Optimize that learns your sound',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.volumebooster.equalizer.loudvolumebooster',
        'app_store_url': '',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'ar', 'zh', 'hi', 'pt', 'ru'],
    },
    'loudify-f44af': {
        'name': 'Loudify',
        'export_file': 'loudify_fresh.json',
        'description': '+200% volume, AutoEQ for your exact headphones, weekly Sound DNA recap',
        'google_play_url': 'https://play.google.com/store/apps/details?id=increase.volumebooster.volumeenhancer',
        'app_store_url': '',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'ar', 'zh', 'hi', 'pt', 'ru'],
    },
    'volume-booster-pro-5a832': {
        'name': 'Volume Booster Pro',
        'export_file': 'volume_booster_pro_fresh.json',
        'description': 'Minimal, no-ads volume boost — the pro variant of Volume Booster',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.volume.booster.free.pro.noads',
        'app_store_url': '',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'ar', 'zh', 'hi', 'pt', 'ru'],
    },
    'horse-racing-f67e8': {
        'name': 'Predictify: Horse Racing AI',
        'export_file': 'horse_racing_fresh.json',
        'description': 'AI-powered horse racing predictions with advanced analytics for Cheltenham, Royal Ascot, Kentucky Derby and more',
        'app_store_url': 'https://apps.apple.com/app/predictify-horse-racing-ai/id6760237594',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.predictify.horse.racing.prediction',
        'multilingual': True,
        'supported_languages': ['en', 'ar', 'es', 'fr'],
    },
    'cryptopredictify': {
        'name': 'Crypto AI: Trading Analyzer',
        'export_file': 'cryptopredictify_fresh.json',
        'description': 'AI-powered cryptocurrency trading signals, market analysis, and portfolio tracking',
        'app_store_url': 'https://apps.apple.com/app/crypto-ai-trading-analyzer/id6757122088',
        'google_play_url': '',
    },
    'boyfriend-ai-f1e5e': {
        'name': 'Ai Boyfriend: Virtual Love',
        'export_file': 'boyfriend_ai_fresh.json',
        'description': 'AI-powered virtual boyfriend for engaging conversations, emotional connection, and companionship',
        'app_store_url': 'https://apps.apple.com/app/ai-boyfriend-virtual-love/id6757331334',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.aiboyfriend.virtuallove',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'de', 'it', 'pt', 'ar', 'ja', 'ko', 'zh', 'ru', 'tr', 'hi', 'id', 'pl', 'nl'],
    },
    'apb412---ai-girlfriend-app': {
        'name': 'Ai Girlfriend: Virtual Love',
        'export_file': 'girlfriend_ai_fresh.json',
        'description': 'AI-powered virtual girlfriend for warm conversations, emotional connection, and companionship',
        'app_store_url': 'https://apps.apple.com/app/ai-girlfriend-virtual-love/id6757268335',
        'google_play_url': 'https://play.google.com/store/apps/details?id=com.aigirlfriend.virtuallove',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'de', 'it', 'pt', 'ar', 'ja', 'ko', 'zh', 'ru', 'tr', 'hi', 'id', 'pl', 'nl'],
    },
    'audio-recorder-microphone': {
        'name': 'Smart Notes - AI Meeting Summary',
        'export_file': 'smart_notes_fresh.json',
        'description': 'AI meeting recorder with transcription and structured summaries',
        'app_store_url': 'https://apps.apple.com/app/smart-notes-ai-meeting-summary/id6756840480',
        'google_play_url': 'https://play.google.com/store/apps/details?id=pl.audiorecorder.voicerecorder.callrecorder',
        'multilingual': True,
        'supported_languages': ['en', 'es', 'fr', 'de', 'pt', 'it', 'ar', 'hi'],
    },
}


class FirebaseUserLoader:
    def __init__(self):
        self.exports_dir = Path(__file__).parent.parent / 'firebase_exports'
        self.exports_dir.mkdir(exist_ok=True)
    
    def refresh_exports(self):
        """Re-export users from all Firebase projects using CLI.
        Supports FIREBASE_TOKEN env var for CI/CD (GitHub Actions).
        """
        print("🔄 Refreshing Firebase user exports...")
        
        token = os.environ.get('FIREBASE_TOKEN')
        
        for project_id, app_info in FIREBASE_APPS.items():
            export_file = self.exports_dir / app_info['export_file']
            print(f"   Exporting {app_info['name']} ({project_id})...")
            
            try:
                cmd = ['firebase', 'auth:export', str(export_file), '--format=JSON', f'--project={project_id}']
                if token:
                    cmd.extend(['--token', token])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    print(f"   ✅ {app_info['name']} exported")
                else:
                    # Don't fail on projects without Auth (e.g. CONFIGURATION_NOT_FOUND)
                    stderr = result.stderr.strip()
                    if 'CONFIGURATION_NOT_FOUND' in stderr:
                        print(f"   ⏭️  {app_info['name']}: No Auth configured, skipping")
                    else:
                        print(f"   ⚠️ {app_info['name']}: {stderr[:200]}")
            except FileNotFoundError:
                print("   ❌ Firebase CLI not found. Install with: npm install -g firebase-tools")
                break
            except Exception as e:
                print(f"   ❌ {app_info['name']}: {e}")
        
        print("✅ Firebase export refresh complete")
    
    def load_users_by_app(self):
        """
        Load all users grouped by app name.
        Returns: {app_name: [{'email': '...', 'uid': '...', 'created_at': '...'}]}
        """
        users_by_app = {}
        
        for project_id, app_info in FIREBASE_APPS.items():
            app_name = app_info['name']
            export_file = self.exports_dir / app_info['export_file']
            
            if not export_file.exists():
                print(f"   ⚠️ No export for {app_name}: {export_file}")
                continue
            
            try:
                with open(export_file, 'r') as f:
                    data = json.load(f)
                
                # Firebase CLI exports: {"users": [...]}
                raw_users = data.get('users', data) if isinstance(data, dict) else data
                
                users = []
                seen_emails = set()
                for user in raw_users:
                    email = user.get('email', '').lower().strip()
                    if not email or email in seen_emails:
                        continue
                    # Skip test accounts
                    if 'cloudtestlabaccounts.com' in email:
                        continue
                    if 'example.com' in email:
                        continue
                    
                    seen_emails.add(email)
                    users.append({
                        'email': email,
                        'uid': user.get('localId', user.get('uid', '')),
                        'created_at': user.get('createdAt', ''),
                        'last_login': user.get('lastLoginAt', user.get('lastSignedInAt', '')),
                    })
                
                users_by_app[app_name] = users
                print(f"   ✅ {app_name}: {len(users)} users loaded")
                
            except Exception as e:
                print(f"   ❌ Error loading {app_name}: {e}")
        
        return users_by_app
    
    def get_app_info(self, app_name):
        """Get app metadata (store URLs, description) by app name"""
        for project_id, info in FIREBASE_APPS.items():
            if info['name'] == app_name:
                return info
        return None
    
    def get_total_users(self):
        """Get total count of all users across all apps"""
        users_by_app = self.load_users_by_app()
        total = sum(len(users) for users in users_by_app.values())
        return total, users_by_app


if __name__ == '__main__':
    loader = FirebaseUserLoader()
    
    import sys
    if '--refresh' in sys.argv:
        loader.refresh_exports()
    
    total, by_app = loader.get_total_users()
    print(f"\n📊 Total: {total} users across {len(by_app)} apps")
    for app, users in sorted(by_app.items(), key=lambda x: -len(x[1])):
        print(f"   {app}: {len(users)} users")
