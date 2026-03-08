#!/usr/bin/env python3
"""Emergency account password reset helper for server-side recovery."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path
from sqlite3 import IntegrityError
import sys

from werkzeug.security import generate_password_hash

# Ensure app package is importable when script is executed from deploy/ path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.user_store import UserStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset or create a web-portal user password.")
    parser.add_argument("--db", required=True, help="Path to web_portal_auth.db")
    parser.add_argument("--email", required=True, help="Account email")
    parser.add_argument("--password", default="", help="New password (omit to prompt securely)")
    parser.add_argument("--create-if-missing", action="store_true", help="Create the account if it does not exist")
    parser.add_argument("--role", default="child", choices=["master", "admin", "child"], help="Role for new account")
    args = parser.parse_args()

    password = str(args.password or "").strip()
    if not password:
        password = getpass.getpass("New password: ").strip()
        confirm = getpass.getpass("Confirm password: ").strip()
        if password != confirm:
            print("Password confirmation mismatch.")
            return 1

    if len(password) < 12:
        print("Password must be at least 12 characters.")
        return 1

    store = UserStore(args.db)
    email = str(args.email).strip().lower()
    user = store.get_user_by_email(email)

    if not user and not args.create_if_missing:
        print(f"User {email} not found. Re-run with --create-if-missing to create it.")
        return 1

    if not user and args.create_if_missing:
        try:
            user_id = store.create_user(
                email=email,
                password_hash=generate_password_hash(password),
                role=args.role,
                parent_user_id=None,
                created_by_user_id=None,
                email_verified=True,
            )
            print(f"Created user {email} (id={user_id}, role={args.role}).")
            return 0
        except (IntegrityError, ValueError) as exc:
            print(f"Unable to create user: {exc}")
            return 1

    assert user is not None
    store.update_password_hash(int(user["id"]), generate_password_hash(password))
    store.set_active(int(user["id"]), True)
    print(f"Password updated and account re-enabled for {email} (id={user['id']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
