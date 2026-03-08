#!/usr/bin/env python3
"""Purge old user telemetry rows from auth DB tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure app package is importable when script is executed from deploy/privacy path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.user_store import UserStore


def _normalize_days(value: int, *, default_days: int) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = int(default_days)
    return max(1, min(days, 3650))


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge retained user telemetry rows.")
    parser.add_argument("--db", required=True, help="Path to web_portal_auth.db")
    parser.add_argument("--operation-days", type=int, default=180, help="Retention days for user_operation_logs")
    parser.add_argument("--device-days", type=int, default=180, help="Retention days for user_devices")
    parser.add_argument("--login-context-days", type=int, default=90, help="Retention days for user_login_contexts")
    parser.add_argument("--dry-run", action="store_true", help="Report candidate deletions without deleting rows")
    parser.add_argument("--json", action="store_true", help="Print summary as JSON")
    args = parser.parse_args()

    db_path = Path(str(args.db or "").strip())
    if not db_path.exists():
        print(f"Auth DB not found: {db_path}")
        return 1

    store = UserStore(str(db_path))
    summary = store.purge_user_telemetry(
        user_operation_retention_days=_normalize_days(args.operation_days, default_days=180),
        user_device_retention_days=_normalize_days(args.device_days, default_days=180),
        user_login_context_retention_days=_normalize_days(args.login_context_days, default_days=90),
        dry_run=bool(args.dry_run),
    )

    if args.json:
        print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
        return 0

    deleted_rows = summary.get("deleted_rows", {}) if isinstance(summary, dict) else {}
    cutoffs = summary.get("cutoffs_utc", {}) if isinstance(summary, dict) else {}
    mode = "dry-run" if bool(summary.get("dry_run")) else "applied"
    print(
        "[user-telemetry-retention] "
        f"{mode} "
        f"op_deleted={int((deleted_rows or {}).get('user_operation_logs', 0) or 0)} "
        f"devices_deleted={int((deleted_rows or {}).get('user_devices', 0) or 0)} "
        f"login_contexts_deleted={int((deleted_rows or {}).get('user_login_contexts', 0) or 0)} "
        f"total_deleted={int((deleted_rows or {}).get('total', 0) or 0)} "
        f"op_cutoff={str((cutoffs or {}).get('user_operation_logs', ''))} "
        f"device_cutoff={str((cutoffs or {}).get('user_devices', ''))} "
        f"login_cutoff={str((cutoffs or {}).get('user_login_contexts', ''))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
