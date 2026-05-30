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
        'supported_languages': ['en', 'ar', 'es', 'fr', 'pt', 'de', 'tr', 'it', 'pp', 'hi', 'id', 'nl', 'pl', 'ja', 'bn', 'el', 'fa', 'ko', 'ro', 'ru', 'sv', 'th', 'uk', 'ur', 'vi', 'zh'],
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
    'Predictify: NBA AI': {
        'project_id': 'nba-predictify',
        'supported_languages': ['en', 'ar', 'es', 'fr', 'pt', 'de', 'tr', 'it', 'pp', 'hi', 'id', 'nl', 'pl', 'ja'],
        'cache_file': 'predictify_nba_languages.json',
    },
    'Thesis Generator': {
        'project_id': 'thesis-generator-web',
        'supported_languages': ['en', 'ar', 'es', 'fr', 'hi', 'zh'],
        'cache_file': 'thesis_generator_languages.json',
    },
    'SoulPlan: Plan Dates Together': {
        'project_id': 'soulplan-dateplanner',
        # Matches the retention cache (cache/retention_emails/soulplan_*_<lang>_email_*.json).
        # SoulPlan writes a BCP-47 tag to users.{uid}.language (e.g. "pt-BR", "zh-Hans");
        # see fetch_user_languages() / fetch_for_user_email() for normalization.
        'supported_languages': ['en', 'ar', 'de', 'es', 'fr', 'hi', 'id', 'it', 'ja', 'ko', 'nl', 'pl', 'pt', 'ru', 'tr', 'zh'],
        'cache_file': 'soulplan_languages.json',
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
    'de': 'de', 'german': 'de', 'deutsch': 'de',
    'tr': 'tr', 'turkish': 'tr',
    'it': 'it', 'italian': 'it', 'italiano': 'it',
    'pp': 'pp', 'pt_pt': 'pp',
    'id': 'id', 'indonesian': 'id',
    'nl': 'nl', 'dutch': 'nl', 'nederlands': 'nl',
    'pl': 'pl', 'polish': 'pl', 'polski': 'pl',
    'ja': 'ja', 'japanese': 'ja',
    'ko': 'ko', 'korean': 'ko', 'ko_kr': 'ko',
    'bn': 'bn',
    'el': 'el',
    'fa': 'fa',
    'ro': 'ro',
    'sv': 'sv',
    'th': 'th',
    'uk': 'uk',
    'ur': 'ur',
    'vi': 'vi',
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
                        # Normalize BCP-47 dashes (pt-BR -> pt_br, zh-Hans -> zh_hans)
                        # so the underscore-keyed LANGUAGE_NORMALIZE table matches.
                        raw_lang = raw_lang.replace('-', '_')
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

        if user_languages:
            # Cache locally (only if we got data — never overwrite good cache with empty)
            self._save_cache(user_languages, cache_file)
            return user_languages
        else:
            # Bulk fetch returned 0 — likely quota exhausted. Fall back to cache.
            print(f"   ⚠️ Bulk fetch returned 0 results — using cached data")
            return self._load_cache(cache_file)


    def fetch_single_user_language(self, app_name, email):
        """
        Fetch language for a single user via Firestore structured query.
        Costs only 1 Firestore read (vs thousands for bulk scan).
        Returns normalized language code or 'en' on failure.
        """
        project_config = MULTILINGUAL_PROJECTS.get(app_name)
        if not project_config:
            return 'en'

        project_id = project_config['project_id']
        supported = project_config['supported_languages']

        token = self._get_access_token()
        if not token:
            return 'en'

        url = f"{FIRESTORE_BASE}/projects/{project_id}/databases/(default)/documents:runQuery"
        try:
            resp = requests.post(url, headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }, json={
                'structuredQuery': {
                    'from': [{'collectionId': 'users'}],
                    'where': {
                        'fieldFilter': {
                            'field': {'fieldPath': 'email'},
                            'op': 'EQUAL',
                            'value': {'stringValue': email},
                        }
                    },
                    'limit': 1,
                }
            }, timeout=15)

            if resp.status_code != 200:
                return 'en'

            results = resp.json()
            if not results or not isinstance(results, list):
                return 'en'

            doc = results[0].get('document')
            if not doc or not doc.get('fields'):
                return 'en'

            raw_lang = doc['fields'].get('language', {}).get('stringValue', 'en').lower().strip()
            # Normalize BCP-47 dashes (pt-BR -> pt_br) so underscore-keyed lookup matches.
            raw_lang = raw_lang.replace('-', '_')
            if '_' in raw_lang and raw_lang not in LANGUAGE_NORMALIZE:
                raw_lang = raw_lang.split('_')[0]
            lang = LANGUAGE_NORMALIZE.get(raw_lang, 'en')
            return lang if lang in supported else 'en'
        except Exception:
            return 'en'

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
