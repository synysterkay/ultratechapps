#!/usr/bin/env python3
"""
Firestore Activity Loader
Fetches user activity data from Firestore for behavioral email branching.
Loads: streak, favoriteLeague, isSubscribed, lastPredictionAt.
Uses the same OAuth token flow as FirestoreLanguageLoader.
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime


FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'

# Apps that support activity-based email branching
ACTIVITY_PROJECTS = {
    'Predictify': {
        'project_id': 'predictify-3f30d',
        'cache_file': 'predictify_activity.json',
        'fields': ['streak', 'favoriteLeague', 'isSubscribed', 'lastPredictionAt', 'isPremium'],
    },
    'Predictify: NBA AI': {
        'project_id': 'nba-predictify',
        'cache_file': 'predictify_nba_activity.json',
        'fields': ['streak', 'favoriteLeague', 'isSubscribed', 'lastPredictionAt', 'isPremium'],
    },
    'Predictify: Horse Racing AI': {
        'project_id': 'horse-racing-f67e8',
        'cache_file': 'horse_racing_activity.json',
        'fields': ['streak', 'isSubscribed', 'lastPredictionAt', 'isPremium'],
    },
}


class FirestoreActivityLoader:
    def __init__(self):
        self.cache_dir = Path(__file__).parent.parent / 'firebase_exports'
        self.cache_dir.mkdir(exist_ok=True)
        self._access_token = None

    def _get_access_token(self):
        """Exchange Firebase CI refresh token for an access token."""
        if self._access_token:
            return self._access_token

        refresh_token = os.environ.get('FIREBASE_TOKEN', '')
        if not refresh_token:
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
        except Exception:
            pass
        return None

    def _extract_field(self, fields, name):
        """Extract a typed value from Firestore document fields."""
        if name not in fields:
            return None
        field = fields[name]
        if 'integerValue' in field:
            return int(field['integerValue'])
        if 'stringValue' in field:
            return field['stringValue']
        if 'booleanValue' in field:
            return field['booleanValue']
        if 'timestampValue' in field:
            return field['timestampValue']
        if 'doubleValue' in field:
            return float(field['doubleValue'])
        return None

    def fetch_user_activity(self, app_name='Predictify'):
        """
        Fetch activity fields from Firestore user documents.
        Returns: {email: {streak: int, favoriteLeague: str, isSubscribed: bool, ...}}
        Falls back to cache if Firestore unavailable.
        """
        config = ACTIVITY_PROJECTS.get(app_name)
        if not config:
            return {}

        project_id = config['project_id']
        cache_file = self.cache_dir / config['cache_file']

        token = self._get_access_token()
        if not token:
            return self._load_cache(cache_file)

        url = f"{FIRESTORE_BASE}/projects/{project_id}/databases/(default)/documents/users"
        headers = {'Authorization': f'Bearer {token}'}

        user_activity = {}
        page_token = None
        print(f"   🔍 Fetching {app_name} user activity from Firestore...")

        while True:
            params = {'pageSize': 300}
            if page_token:
                params['pageToken'] = page_token

            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code != 200:
                    print(f"   ❌ Firestore API error: {resp.status_code}")
                    break

                data = resp.json()
                for doc in data.get('documents', []):
                    fields = doc.get('fields', {})
                    email = self._extract_field(fields, 'email')
                    if not email:
                        continue
                    email = email.lower().strip()

                    activity = {}
                    for field_name in config['fields']:
                        val = self._extract_field(fields, field_name)
                        if val is not None:
                            activity[field_name] = val

                    if activity:
                        user_activity[email] = activity

                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            except Exception as e:
                print(f"   ❌ Firestore fetch error: {e}")
                break

        print(f"   ✅ Got activity data for {len(user_activity)} users")
        self._save_cache(user_activity, cache_file)
        return user_activity

    def _save_cache(self, data, cache_file):
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_cache(self, cache_file):
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                print(f"   📦 Loaded cached activity for {len(data)} users")
                return data
            except Exception:
                pass
        return {}

    def load_activity(self, app_name='Predictify', users=None):
        """Return {uid: activity_dict} keyed by Firebase uid.

        Activity is fetched by email from Firestore then joined to the auth
        export via the ``users`` list from FirebaseUserLoader.
        """
        by_email = self.fetch_user_activity(app_name)
        if not users:
            return by_email, {}
        by_uid = {}
        for u in users:
            uid = u.get('localId') or u.get('uid')
            email = (u.get('email') or '').lower().strip()
            if uid and email in by_email:
                by_uid[uid] = by_email[email]
        return by_email, by_uid


if __name__ == '__main__':
    loader = FirestoreActivityLoader()
    for app in ACTIVITY_PROJECTS:
        activity = loader.fetch_user_activity(app)
        if activity:
            # Show sample stats
            streaks = [v.get('streak', 0) for v in activity.values() if v.get('streak')]
            subscribed = sum(1 for v in activity.values() if v.get('isSubscribed') or v.get('isPremium'))
            leagues = {}
            for v in activity.values():
                league = v.get('favoriteLeague')
                if league:
                    leagues[league] = leagues.get(league, 0) + 1
            print(f"\n📊 {app} Activity Summary:")
            print(f"   Users with streaks: {len(streaks)}")
            if streaks:
                print(f"   Avg streak: {sum(streaks)/len(streaks):.1f}, Max: {max(streaks)}")
            print(f"   Subscribed/Premium: {subscribed}")
            print(f"   Top leagues: {sorted(leagues.items(), key=lambda x: -x[1])[:5]}")
