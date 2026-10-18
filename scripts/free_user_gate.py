#!/usr/bin/env python3
"""Shared free-user gate for Auth-export tip / founder senders.

Conversion doctrine: tip + founder emails go to free users only.
Paying / Superwall subscribers are skipped via Firestore activity
(isPremium / isSubscribed / subscription map).

Live sends require FIREBASE_TOKEN so we can read Superwall mirrors —
never blast the full Auth list when we cannot check paid status.
Missing per-user activity (never opened app / no mirror yet) → free.
"""
from __future__ import annotations

import os
from typing import Iterable

from firestore_activity_loader import FirestoreActivityLoader, ACTIVITY_PROJECTS

# tip/founder slug → ACTIVITY_PROJECTS key
APP_SLUG_TO_ACTIVITY = {
    'horse_racing': 'Predictify: Horse Racing AI',
    'predictify_crypto': 'Crypto AI: Trading Analyzer',
    'fresh_start': 'Fresh Start',
    'predictify': 'Predictify',
    'red_flag_scanner': 'Red Flag Scanner AI',
    'soulplan': 'SoulPlan',
    'kinbound': 'Kinbound',
    'pupshape': 'PupShape',
    'smart_notes': 'Smart Notes',
    'ai_girlfriend': 'Ai Girlfriend: Virtual Love',
}

_PAID_STATUS = frozenset({'active', 'trial', 'past_due'})


def activity_is_paid(activity: dict | None) -> bool:
    if not activity:
        return False
    if activity.get('isPremium') or activity.get('isSubscribed'):
        return True
    sub = activity.get('subscription')
    if isinstance(sub, dict):
        if sub.get('isPremium') is True or sub.get('isSubscribed') is True:
            return True
        status = (sub.get('status') or '').lower()
        return status in _PAID_STATUS
    if isinstance(sub, str):
        return sub.lower() in _PAID_STATUS
    return False


def paid_emails_for_app(app_slug: str, users: Iterable[dict] | None = None) -> set[str]:
    """Return lowercase emails known to be paid for this app. Empty if unknown."""
    activity_name = APP_SLUG_TO_ACTIVITY.get(app_slug)
    if not activity_name or activity_name not in ACTIVITY_PROJECTS:
        print(f'   ⚠️ free_user_gate: no activity project for {app_slug}')
        return set()
    user_list = list(users) if users else None
    loader = FirestoreActivityLoader()
    by_email, by_uid = loader.load_activity(activity_name, users=user_list)
    paid = {e for e, act in by_email.items() if '@' in e and activity_is_paid(act)}
    # Explicit Auth join: uid-keyed Firestore docs → email
    if user_list:
        for u in user_list:
            uid = u.get('localId') or u.get('uid') or ''
            email = (u.get('email') or u.get('Email') or '').lower().strip()
            if not email or '@' not in email:
                continue
            act = by_uid.get(uid) or by_email.get(email)
            if activity_is_paid(act):
                paid.add(email)
    print(f'   🎯 free_user_gate[{app_slug}]: {len(paid)} paid emails to skip')
    return paid


def filter_free_users(
    users: list[dict],
    app_slug: str,
    email_of,
    *,
    require_firebase: bool = False,
) -> list[dict]:
    """Drop Auth users whose email is in the paid set (Firebase Superwall).

    If require_firebase=True and FIREBASE_TOKEN is missing, return [] so we
    never send tip/founder conversion mail without a live paid check.
    """
    activity_name = APP_SLUG_TO_ACTIVITY.get(app_slug)
    if require_firebase and activity_name and activity_name in ACTIVITY_PROJECTS:
        if not os.environ.get('FIREBASE_TOKEN'):
            print(
                f'❌ free_user_gate[{app_slug}]: FIREBASE_TOKEN required — '
                'refusing tip/founder (cannot verify free-only via Firebase)'
            )
            return []

    paid = paid_emails_for_app(app_slug, users)
    out = []
    skipped = 0
    for u in users:
        email = (email_of(u) or '').lower().strip()
        if email and email in paid:
            skipped += 1
            continue
        out.append(u)
    if skipped:
        print(f'   ⏭️ skipped {skipped} paid users ({app_slug}) — free only')
    else:
        print(f'   ✅ free-only audience: {len(out)} users ({app_slug})')
    return out
