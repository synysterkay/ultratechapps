"""Process-wide Firestore quota flag.

Retention cron used to retry 429s for ~15 minutes per page, then every
Thesis sender started a fresh scan. One exhausted project must not stall
the rest of the 300-minute job.
"""
from __future__ import annotations

_exhausted: set[str] = set()


def is_exhausted(project_id: str) -> bool:
    return project_id in _exhausted


def mark_exhausted(project_id: str) -> None:
    if project_id in _exhausted:
        return
    _exhausted.add(project_id)
    print(
        f'   🛑 Firestore quota exhausted for {project_id} — '
        'live reads skipped for the rest of this process'
    )
