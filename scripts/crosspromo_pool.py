#!/usr/bin/env python3
"""
Crosspromotion audience pool.

Union of Auth emails from all Firebase apps, minus Thesis Generator Auth
users. Attaches source_apps[] and an affinity rank so Thesis promo ramps
hit better-fit users first.
"""
from __future__ import annotations

import json
from pathlib import Path

from firebase_user_loader import FIREBASE_APPS, FirebaseUserLoader
from firestore_language_loader import MULTILINGUAL_PROJECTS
import localize_phrase

THESIS_APP_NAME = 'Thesis Generator'
ONBRIEF_APP_NAME = 'Onbrief'
EXPORTS_DIR = Path(__file__).parent.parent / 'firebase_exports'

# Lower rank = higher affinity for Thesis Generator installs.
# Apps not listed default to 50 (medium-low).
AFFINITY_RANK: dict[str, int] = {
    'Smart Notes - AI Meeting Summary': 10,
    'Kinbound: AI Parent Life Coach': 15,
    'Red Flag Scanner AI': 25,
    'SoulPlan: Plan Dates Together': 28,
    'Fresh Start: Breakup Therapy': 30,
    'PupShape: Dog Weight Loss Plan': 35,
    'Volume Booster - Sound Booster': 45,
    'Bass Booster': 48,
    'Loud EQ': 48,
    'Loudify': 48,
    'Volume Booster Pro': 48,
    'Predictify': 55,
    'Predictify: NBA AI': 55,
    'Predictify: Horse Racing AI': 55,
    'Crypto AI: Trading Analyzer': 60,
    'Ai Boyfriend: Virtual Love': 65,
    'Ai Girlfriend: Virtual Love': 65,
}


def _best_affinity(source_apps: list[str]) -> int:
    if not source_apps:
        return 99
    return min(AFFINITY_RANK.get(a, 50) for a in source_apps)


def _real_store_url(url: str | None) -> bool:
    u = (url or '').strip()
    if not u:
        return False
    # Placeholder / search pages are not a live store listing.
    if 'id0000000000' in u or '/search?' in u:
        return False
    return True


def source_is_android_first(source_apps: list[str] | None) -> bool:
    """True when every known source app is Play-live and has no real iOS listing.

    Volume / bass apps and ONG (iOS still in review) should see Play first on
    Research Generator crosspromo. Dual-platform sources keep App Store first.
    """
    if not source_apps:
        return False
    by_name = {info['name']: info for info in FIREBASE_APPS.values()}
    known = 0
    for name in source_apps:
        info = by_name.get(name)
        if not info:
            continue
        known += 1
        has_ios = _real_store_url(info.get('app_store_url'))
        has_play = _real_store_url(info.get('google_play_url'))
        if has_ios or not has_play:
            return False
    return known > 0


def _load_language_maps() -> dict[str, str]:
    """Best-effort email → language from on-disk Firestore language caches."""
    out: dict[str, str] = {}
    for app_name, cfg in MULTILINGUAL_PROJECTS.items():
        cache_name = cfg.get('cache_file')
        if not cache_name:
            continue
        path = EXPORTS_DIR / cache_name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        # Cache shapes vary: {email: lang} or {languages: {email: lang}}
        mapping = data.get('languages') if isinstance(data, dict) and 'languages' in data else data
        if not isinstance(mapping, dict):
            continue
        for email, lang in mapping.items():
            if not isinstance(email, str) or '@' not in email:
                continue
            if email in ('updated_at', 'saved_at', 'count'):
                continue
            code = localize_phrase.normalize_language(str(lang))
            e = email.lower().strip()
            # Prefer first non-en hit; otherwise keep existing.
            if e not in out or (out[e] == 'en' and code != 'en'):
                out[e] = code
    return out


def build_pool(
    *,
    exclude_emails: set[str] | None = None,
) -> list[dict]:
    """
    Return eligible crosspromo contacts sorted by affinity (best first).

    Each item:
      {
        'email': str,
        'source_apps': [str, ...],
        'uids': {app_name: uid},
        'affinity': int,
        'language': str,
      }
    """
    loader = FirebaseUserLoader()
    users_by_app = loader.load_users_by_app()

    thesis_emails = {
        u['email'].lower().strip()
        for u in users_by_app.get(THESIS_APP_NAME, [])
        if u.get('email')
    }

    exclude = {e.lower().strip() for e in (exclude_emails or set())}
    lang_map = _load_language_maps()

    by_email: dict[str, dict] = {}
    for app_name, users in users_by_app.items():
        if app_name == THESIS_APP_NAME or app_name == ONBRIEF_APP_NAME:
            continue
        for u in users:
            email = (u.get('email') or '').lower().strip()
            if not email or email in thesis_emails or email in exclude:
                continue
            rec = by_email.get(email)
            if rec is None:
                by_email[email] = {
                    'email': email,
                    'source_apps': [app_name],
                    'uids': {app_name: u.get('uid', '')},
                    'first_name': '',
                }
            else:
                if app_name not in rec['source_apps']:
                    rec['source_apps'].append(app_name)
                rec['uids'][app_name] = u.get('uid', '')

    pool = []
    for email, rec in by_email.items():
        rec['affinity'] = _best_affinity(rec['source_apps'])
        rec['language'] = lang_map.get(email, 'en')
        pool.append(rec)

    pool.sort(key=lambda r: (r['affinity'], r['email']))
    return pool


def pool_stats(pool: list[dict] | None = None) -> dict:
    if pool is None:
        pool = build_pool()
    by_affinity = {}
    for r in pool:
        band = 'high' if r['affinity'] <= 20 else 'medium' if r['affinity'] <= 40 else 'lower'
        by_affinity[band] = by_affinity.get(band, 0) + 1
    return {
        'eligible': len(pool),
        'by_affinity_band': by_affinity,
        'apps_in_loader': [
            info['name'] for info in FIREBASE_APPS.values()
            if info['name'] not in {THESIS_APP_NAME, ONBRIEF_APP_NAME}
        ],
    }


if __name__ == '__main__':
    p = build_pool()
    stats = pool_stats(p)
    print(json.dumps(stats, indent=2))
    print(f'Sample (top 5 by affinity):')
    for r in p[:5]:
        print(f"  {r['email']}  affinity={r['affinity']}  apps={r['source_apps']}  lang={r['language']}")
