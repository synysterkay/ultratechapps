#!/usr/bin/env python3
"""Shared free-user gate for Auth-export tip / founder senders.

Active Pro/Premium emails are skipped. Missing activity → treated as free
(same as Predictify founder-story path). Explicit isPremium/isSubscribed or
subscription.status in {active, trial, past_due} → paid.
"""
from __future__ import annotations

from typing import Iterable

from firestore_activity_loader import FirestoreActivityLoader, ACTIVITY_PROJECTS

# tip-sender slug → ACTIVITY_PROJECTS key
APP_SLUG_TO_ACTIVITY = {
    'horse_racing': 'Predictify: Horse Racing AI',
    'predictify_crypto': 'Crypto AI: Trading Analyzer',
    'fresh_start': 'Fresh Start',
    'predictify': 'Predictify',
}

_PAID_STATUS = frozenset({'active', 'trial', 'past_due'})


def activity_is_paid(activity: dict | None) -> bool:
    if not activity:
        return False
    if activity.get('isPremium') or activity.get('isSubscribed'):
        return True
    sub = activity.get('subscription')
    if isinstance(sub, dict):
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


def filter_free_users(users: list[dict], app_slug: str, email_of) -> list[dict]:
    """Drop Auth users whose email is in the paid set."""
    paid = paid_emails_for_app(app_slug, users)
    if not paid:
        return users
    out = []
    skipped = 0
    for u in users:
        email = (email_of(u) or '').lower().strip()
        if email and email in paid:
            skipped += 1
            continue
        out.append(u)
    if skipped:
        print(f'   ⏭️ skipped {skipped} paid users ({app_slug})')
    return out
