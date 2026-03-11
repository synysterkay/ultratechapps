#!/usr/bin/env python3
"""
Firestore Language Loader
Fetches user language preferences from Firestore for multilingual apps.
Uses Firebase Auth refresh token (FIREBASE_TOKEN) to get access token,
then queries Firestore REST API for user documents with language field.
Supports multiple Firebase projects (Predictify, Volume Booster, etc.)
"""
import os
import json
import requests
from pathlib import Path


# Google OAuth2 token endpoint
TOKEN_URL = 'https://securetoken.googleapis.com/v1/token'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'

# Multilingual app projects
MULTILINGUAL_PROJECTS = {
    'Predictify': {
        'project_id': 'predictify-3f30d',
        'supported_languages': ['en', 'ar', 'es', 'fr'],
        'cache_file': 'predictify_languages.json',
    },
    'Volume Booster - Sound Booster': {
        'project_id': 'volume-booster-2f7bf',
        'supported_languages': ['en', 'ar', 'es', 'fr', 'zh', 'hi', 'pt', 'ru'],
        'cache_file': 'volume_booster_languages.json',
    },
    'Predictify: Horse Racing AI': {
        'project_id': 'horse-racing-f67e8',
        'supported_languages': ['en', 'ar', 'es', 'fr'],
        'cache_file': 'horse_racing_languages.json',
    },
}

# Language code normalization map
LANGUAGE_NORMALIZE = {
    'ar': 'ar', 'arabic': 'ar',
    'es': 'es', 'spanish': 'es', 'español': 'es',
    'fr': 'fr', 'french': 'fr', 'français': 'fr',
    'zh': 'zh', 'chinese': 'zh', 'zh_cn': 'zh', 'zh_tw': 'zh',
    'hi': 'hi', 'hindi': 'hi',
    'pt': 'pt', 'portuguese': 'pt', 'pt_br': 'pt',
    'ru': 'ru', 'russian': 'ru',
    'en': 'en', 'english': 'en', 'en_us': 'en',
}


class FirestoreLanguageLoader:
    def __init__(self):
        self.cache_dir = Path(__file__).parent.parent / 'firebase_exports'
        self.cache_dir.mkdir(exist_ok=True)
        self._access_token = None

    def _get_access_token(self):
        """Exchange Firebase CI refresh token for an access token via Google OAuth."""
        if self._access_token:
            return self._access_token

        refresh_token = os.environ.get('FIREBASE_TOKEN', '')
        if not refresh_token:
            print("   ⚠️ FIREBASE_TOKEN not set, cannot access Firestore")
            return None

        try:
            resp = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': '563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com',
                    'client_secret': 'j9iVZfS8kkCEFUPaAeJV0sAi',
                },
                timeout=15
            )
            if resp.status_code == 200:
                self._access_token = resp.json()['access_token']
                return self._access_token
            else:
                print(f"   ❌ Token exchange failed: {resp.status_code} {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"   ❌ Token exchange error: {e}")
            return None

    def fetch_user_languages(self, app_name='Predictify'):
        """
        Fetch all Firestore user documents from 'users' collection.
        Returns: {email: language_code} mapping.
        Default language is 'en' if not set.
        """
        project_config = MULTILINGUAL_PROJECTS.get(app_name)
        if not project_config:
            print(f"   ⚠️ No multilingual config for {app_name}")
            return {}

        project_id = project_config['project_id']
        supported = project_config['supported_languages']
        cache_file = self.cache_dir / project_config['cache_file']

        token = self._get_access_token()
        if not token:
            return self._load_cache(cache_file)

        url = f"{FIRESTORE_BASE}/projects/{project_id}/databases/(default)/documents/users"
        headers = {'Authorization': f'Bearer {token}'}

        user_languages = {}
        page_token = None

        print(f"   🔍 Fetching {app_name} user languages from Firestore ({project_id})...")

        while True:
            params = {'pageSize': 300}
            if page_token:
                params['pageToken'] = page_token

            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code != 200:
                    print(f"   ❌ Firestore API error: {resp.status_code} {resp.text[:200]}")
                    break

                data = resp.json()
                documents = data.get('documents', [])

                for doc in documents:
                    fields = doc.get('fields', {})
                    # Extract email
                    email = ''
                    if 'email' in fields:
                        email = fields['email'].get('stringValue', '').lower().strip()
                    
                    # Extract language (default 'en')
                    lang = 'en'
                    if 'language' in fields:
                        raw_lang = fields['language'].get('stringValue', 'en').lower().strip()
                        # Strip locale suffixes (e.g. en_US -> en)
                        raw_lang = raw_lang.split('_')[0] if '_' in raw_lang and raw_lang not in LANGUAGE_NORMALIZE else raw_lang
                        lang = LANGUAGE_NORMALIZE.get(raw_lang, 'en')

                    # Only keep languages this app supports
                    if lang not in supported:
                        lang = 'en'

                    if email:
                        user_languages[email] = lang

                # Check for next page
                page_token = data.get('nextPageToken')
                if not page_token:
                    break

            except Exception as e:
                print(f"   ❌ Firestore fetch error: {e}")
                break

        print(f"   ✅ Got languages for {len(user_languages)} {app_name} users")

        # Cache locally
        self._save_cache(user_languages, cache_file)
        return user_languages

    def _save_cache(self, user_languages, cache_file):
        """Save language map to local cache file."""
        with open(cache_file, 'w') as f:
            json.dump(user_languages, f, indent=2)

    def _load_cache(self, cache_file):
        """Load cached language map if available."""
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                print(f"   📦 Loaded cached languages for {len(data)} users")
                return data
            except:
                pass
        return {}


if __name__ == '__main__':
    loader = FirestoreLanguageLoader()
    for app_name in MULTILINGUAL_PROJECTS:
        print(f"\n📱 {app_name}:")
        langs = loader.fetch_user_languages(app_name)
        print(f"Language distribution:")
        from collections import Counter
        counts = Counter(langs.values())
        for lang, count in counts.most_common():
            print(f"   {lang}: {count} users")
