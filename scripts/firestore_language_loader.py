#!/usr/bin/env python3
"""
Firestore Language Loader
Fetches user language preferences from Firestore for Predictify.
Uses Firebase Auth refresh token (FIREBASE_TOKEN) to get access token,
then queries Firestore REST API for user documents with language field.
"""
import os
import json
import requests
from pathlib import Path


# Google OAuth2 token endpoint
TOKEN_URL = 'https://securetoken.googleapis.com/v1/token'
FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'

# Predictify project
PROJECT_ID = 'predictify-3f30d'
# Firebase Web API key for predictify (needed to exchange refresh token)
# This is a public identifier, not a secret
FIREBASE_API_KEY = os.getenv('PREDICTIFY_API_KEY', '')


class FirestoreLanguageLoader:
    def __init__(self):
        self.project_id = PROJECT_ID
        self.cache_file = Path(__file__).parent.parent / 'firebase_exports' / 'predictify_languages.json'
        self.cache_file.parent.mkdir(exist_ok=True)
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

    def fetch_user_languages(self):
        """
        Fetch all Firestore user documents from 'users' collection.
        Returns: {email: language_code} mapping.
        Default language is 'en' if not set.
        """
        token = self._get_access_token()
        if not token:
            return self._load_cache()

        url = f"{FIRESTORE_BASE}/projects/{self.project_id}/databases/(default)/documents/users"
        headers = {'Authorization': f'Bearer {token}'}

        user_languages = {}
        page_token = None

        print(f"   🔍 Fetching Predictify user languages from Firestore...")

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
                        lang = fields['language'].get('stringValue', 'en').lower().strip()
                    
                    # Normalize language codes
                    if lang in ('ar', 'arabic'):
                        lang = 'ar'
                    elif lang in ('es', 'spanish', 'español'):
                        lang = 'es'
                    elif lang in ('fr', 'french', 'français'):
                        lang = 'fr'
                    else:
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

        print(f"   ✅ Got languages for {len(user_languages)} Predictify users")

        # Cache locally
        self._save_cache(user_languages)
        return user_languages

    def _save_cache(self, user_languages):
        """Save language map to local cache file."""
        with open(self.cache_file, 'w') as f:
            json.dump(user_languages, f, indent=2)

    def _load_cache(self):
        """Load cached language map if available."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                print(f"   📦 Loaded cached languages for {len(data)} users")
                return data
            except:
                pass
        return {}


if __name__ == '__main__':
    loader = FirestoreLanguageLoader()
    langs = loader.fetch_user_languages()
    print(f"\nLanguage distribution:")
    from collections import Counter
    counts = Counter(langs.values())
    for lang, count in counts.most_common():
        print(f"   {lang}: {count} users")
