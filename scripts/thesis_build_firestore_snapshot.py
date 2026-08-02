#!/usr/bin/env python3
"""Build or refresh cache/thesis_users_snapshot.json for Thesis blast sends."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from thesis_users_loader import USERS_SNAPSHOT_CACHE, build_firestore_snapshot, get_access_token


def main() -> None:
    parser = argparse.ArgumentParser(description='Build Thesis Firestore user snapshot')
    parser.add_argument('--force', action='store_true', help='Ignore fresh snapshot and re-fetch')
    parser.add_argument('--min-users', type=int, default=int(os.getenv('THESIS_FIRESTORE_SNAPSHOT_MIN', '1000')))
    args = parser.parse_args()

    token = get_access_token()
    if not token:
        raise SystemExit('FIREBASE_TOKEN not set — cannot build snapshot')

    count = build_firestore_snapshot(token, force=args.force, min_users=args.min_users)
    if count < args.min_users:
        raise SystemExit(f'Snapshot too small ({count} users, need {args.min_users})')

    print(f'✅ Snapshot ready: {count:,} users → {USERS_SNAPSHOT_CACHE}')


if __name__ == '__main__':
    main()
