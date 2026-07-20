#!/usr/bin/env python3
"""
Export Firebase Auth users to per-app CSV files.

Usage:
  python3 scripts/export_app_email_csvs.py
  python3 scripts/export_app_email_csvs.py --refresh
  python3 scripts/export_app_email_csvs.py --apps predictify_soccer thesis_generator
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = ROOT / "exports"
FIREBASE_EXPORTS_DIR = ROOT / "firebase_exports"

# App slug -> Firebase project + export file mapping
APP_CONFIG = {
    "predictify_soccer": {
        "project_id": "predictify-3f30d",
        "export_file": "predictify_fresh.json",
        "display_name": "Predictify Soccer",
    },
    "thesis_generator": {
        "project_id": "thesis-generator-web",
        "export_file": "thesis_web_users.json",
        "display_name": "Thesis Generator",
    },
}

CSV_FIELDS = ["email", "uid", "app", "display_name", "created_at", "last_login", "email_verified"]

SKIP_EMAIL_FRAGMENTS = (
    "cloudtestlabaccounts.com",
    "example.com",
    "test@test",
)


def _is_skipped_email(email: str) -> bool:
    lower = email.lower()
    return any(fragment in lower for fragment in SKIP_EMAIL_FRAGMENTS)


def _parse_firebase_timestamp(raw: str | int | None) -> str:
    if raw in (None, ""):
        return ""
    try:
        if isinstance(raw, str) and raw.isdigit():
            ms = int(raw)
        elif isinstance(raw, (int, float)):
            ms = int(raw)
        else:
            return str(raw)
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return str(raw)


def refresh_firebase_export(project_id: str, export_file: Path) -> bool:
    token = os.environ.get("FIREBASE_TOKEN")
    cmd = [
        "firebase",
        "auth:export",
        str(export_file),
        "--format=JSON",
        f"--project={project_id}",
    ]
    if token:
        cmd.extend(["--token", token])

    print(f"   Refreshing {project_id} → {export_file.name}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        print("   ❌ Firebase CLI not found. Install: npm install -g firebase-tools")
        return False
    except subprocess.TimeoutExpired:
        print(f"   ❌ Timed out exporting {project_id}")
        return False

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        print(f"   ❌ Export failed: {stderr[:300]}")
        return False

    print(f"   ✅ Exported {export_file.name}")
    return True


def load_users_from_export(export_file: Path, app_slug: str) -> list[dict]:
    if not export_file.exists():
        raise FileNotFoundError(f"Missing export: {export_file}")

    with export_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    raw_users = data.get("users", data) if isinstance(data, dict) else data
    if not isinstance(raw_users, list):
        raise ValueError(f"Unexpected export format in {export_file}")

    users: list[dict] = []
    seen_emails: set[str] = set()

    for user in raw_users:
        email = (user.get("email") or "").lower().strip()
        if not email or email in seen_emails or _is_skipped_email(email):
            continue

        seen_emails.add(email)
        users.append(
            {
                "email": email,
                "uid": user.get("localId") or user.get("uid") or "",
                "app": app_slug,
                "display_name": user.get("displayName") or "",
                "created_at": _parse_firebase_timestamp(user.get("createdAt")),
                "last_login": _parse_firebase_timestamp(
                    user.get("lastLoginAt") or user.get("lastSignedInAt")
                ),
                "email_verified": str(bool(user.get("emailVerified", False))).lower(),
            }
        )

    return users


def write_csv(path: Path, users: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(users)


def export_app(app_slug: str, refresh: bool) -> tuple[Path, int]:
    cfg = APP_CONFIG[app_slug]
    export_file = FIREBASE_EXPORTS_DIR / cfg["export_file"]
    csv_path = EXPORTS_DIR / f"{app_slug}.csv"

    if refresh:
        FIREBASE_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        if not refresh_firebase_export(cfg["project_id"], export_file):
            if not export_file.exists():
                raise RuntimeError(f"No export available for {app_slug}")

    users = load_users_from_export(export_file, app_slug)
    write_csv(csv_path, users)
    return csv_path, len(users)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Firebase Auth users to per-app CSV files")
    parser.add_argument(
        "--apps",
        nargs="+",
        choices=list(APP_CONFIG.keys()),
        default=list(APP_CONFIG.keys()),
        help="App slugs to export (default: all)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-export from Firebase Auth before writing CSV",
    )
    args = parser.parse_args()

    print("📧 App email CSV export")
    print("=" * 50)

    results: list[tuple[str, Path, int]] = []

    for app_slug in args.apps:
        cfg = APP_CONFIG[app_slug]
        print(f"\n📱 {cfg['display_name']} ({app_slug})")
        try:
            csv_path, count = export_app(app_slug, refresh=args.refresh)
            results.append((app_slug, csv_path, count))
            print(f"   ✅ {count} users → {csv_path.relative_to(ROOT)}")
        except Exception as exc:
            print(f"   ❌ {exc}")
            return 1

    print("\n" + "=" * 50)
    print("✅ Export complete")
    for app_slug, csv_path, count in results:
        print(f"   {app_slug}: {count} users → {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
