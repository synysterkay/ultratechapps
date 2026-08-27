#!/usr/bin/env python3
"""
Firestore Plan Loader (Thesis Generator)

Fetches per-user personalization fields written by the Flutter app:
- displayName  (for first-name interpolation)
- email        (lookup key)
- language     (already used by firestore_language_loader, mirrored here)
- plan: { topic, deadline (Timestamp), workType, pain, academicLevel, field }

Used by app_retention_emailer.py to fill {{first_name}}, {{topic}},
{{days_left}}, {{work_type}}, {{pain_hook}} placeholders at send time.

Mirrors the structure of firestore_language_loader.py:
- Exchanges FIREBASE_TOKEN for an access token
- Pages through `users` collection via the Firestore REST API
- Falls back to a local cache file when the token / quota fails
"""
import os
import sys
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from firestore_quota import is_exhausted, mark_exhausted


FIRESTORE_BASE = 'https://firestore.googleapis.com/v1'


# Apps that ship UserPlan to Firestore. Add new apps here as they adopt
# the keystone-plan pattern.
PLAN_PROJECTS = {
    'Thesis Generator': {
        'project_id': 'thesis-generator-web',
        'cache_file': 'thesis_generator_plans.json',
    },
}


def _str(field):
    if not isinstance(field, dict):
        return ''
    return field.get('stringValue', '') or ''


def _ts(field):
    if not isinstance(field, dict):
        return None
    v = field.get('timestampValue')
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace('Z', '+00:00'))
    except Exception:
        return None


def _map(field):
    if not isinstance(field, dict):
        return {}
    m = field.get('mapValue', {})
    return m.get('fields', {})


class FirestorePlanLoader:
    """Loads UserPlan + displayName for personalization."""

    def __init__(self):
        self.cache_dir = Path(__file__).parent.parent / 'firebase_exports'
        self.cache_dir.mkdir(exist_ok=True)
        self._access_token = None

    def _get_access_token(self):
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
                timeout=15,
            )
            if resp.status_code == 200:
                self._access_token = resp.json()['access_token']
                return self._access_token
        except Exception as e:
            print(f"   ❌ Token exchange error: {e}")
        return None

    def fetch_user_plans(self, app_name='Thesis Generator'):
        """Returns {email: plan_dict} where plan_dict has:
        first_name, language, topic, deadline (datetime|None),
        work_type, pain, academic_level, field, days_left (int|None).
        """
        project_config = PLAN_PROJECTS.get(app_name)
        if not project_config:
            return {}

        project_id = project_config['project_id']
        cache_file = self.cache_dir / project_config['cache_file']

        if is_exhausted(project_id):
            print(f"   ⏭️ Firestore quota exhausted — using cached plans for {app_name}")
            return self._load_cache(cache_file)

        token = self._get_access_token()
        if not token:
            return self._load_cache(cache_file)

        url = f"{FIRESTORE_BASE}/projects/{project_id}/databases/(default)/documents/users"
        headers = {'Authorization': f'Bearer {token}'}

        plans = {}
        page_token = None
        now = datetime.now(timezone.utc)

        print(f"   🔍 Fetching {app_name} plans from Firestore ({project_id})...")

        while True:
            params = {'pageSize': 300}
            if page_token:
                params['pageToken'] = page_token

            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code == 429:
                    mark_exhausted(project_id)
                    print(f"   ❌ Firestore API error: {resp.status_code} {resp.text[:200]}")
                    break
                if resp.status_code != 200:
                    print(f"   ❌ Firestore API error: {resp.status_code} {resp.text[:200]}")
                    break

                data = resp.json()
                documents = data.get('documents', [])

                for doc in documents:
                    fields = doc.get('fields', {})
                    email = _str(fields.get('email', {})).lower().strip()
                    if not email:
                        continue

                    plan_fields = _map(fields.get('plan', {}))
                    display_name = _str(fields.get('displayName', {})) or _str(fields.get('name', {}))
                    first_name = display_name.split()[0] if display_name else ''
                    language = (_str(fields.get('language', {})) or 'en').split('_')[0]

                    deadline = _ts(plan_fields.get('deadline', {}))
                    days_left = None
                    if deadline:
                        delta = deadline.date() - now.date()
                        days_left = delta.days

                    plans[email] = {
                        'first_name': first_name,
                        'language': language,
                        'topic': _str(plan_fields.get('topic', {})),
                        'deadline_iso': deadline.isoformat() if deadline else '',
                        'days_left': days_left,
                        'work_type': _str(plan_fields.get('workType', {})),
                        'pain': _str(plan_fields.get('pain', {})),
                        'academic_level': _str(plan_fields.get('academicLevel', {})),
                        'field': _str(plan_fields.get('field', {})),
                    }

                page_token = data.get('nextPageToken')
                if not page_token:
                    break

            except Exception as e:
                print(f"   ❌ Firestore fetch error: {e}")
                break

        print(f"   ✅ Got plans for {len(plans)} {app_name} users")

        if plans:
            self._save_cache(plans, cache_file)
            return plans
        return self._load_cache(cache_file)

    def _save_cache(self, plans, cache_file):
        with open(cache_file, 'w') as f:
            json.dump(plans, f, indent=2, default=str)

    def _load_cache(self, cache_file):
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}


if __name__ == '__main__':
    loader = FirestorePlanLoader()
    for app_name in PLAN_PROJECTS:
        print(f"\n📱 {app_name}:")
        plans = loader.fetch_user_plans(app_name)
        with_deadline = sum(1 for p in plans.values() if p.get('days_left') is not None)
        with_topic = sum(1 for p in plans.values() if p.get('topic'))
        print(f"   total: {len(plans)}")
        print(f"   with deadline: {with_deadline}")
        print(f"   with topic:    {with_topic}")
