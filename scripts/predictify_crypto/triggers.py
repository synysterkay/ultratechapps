"""
triggers.py — Predictify Crypto behavioral email kinds (Hooked / Soccer-style).

Wire these into a cron orchestrator once Firestore activity snapshots exist.
Lower priority number = checked first; first match wins.
"""
from __future__ import annotations

from typing import Callable

# Active kinds for Week 2+ cron (set PREDICTIFY_CRYPTO_ACTIVE_TRIGGERS=p0p1)
P0P1_KINDS: frozenset[str] = frozenset({
    'streak_saver',
    'welcome_backup',
    'journal_pending',
    'win_back',
})


# Placeholder predicates — replace with UserContext fields when loader ships.
# Each is (priority, kind, docstring).
TRIGGERS: list[tuple[int, str, str]] = [
    (10, 'streak_saver', 'streak>=3 and 18h<=hours_since_analysis<=30'),
    (30, 'welcome_backup', 'total_analyses==0 and days_since_signup in 1..3'),
    (40, 'journal_pending', 'pending_journal_count>=1 and hours_since_analysis>=12'),
    (55, 'win_back', 'not premium and 5d<=hours_since_analysis<=14d and total_analyses>=1'),
]
