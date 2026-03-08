"""SQLite-backed user/account store for web portal auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import secrets
import sqlite3
import time
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from .special_accounts import SPECIAL_UID_BY_EMAIL


ALLOWED_ROLES = {"master", "admin", "child"}


class UserStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _is_valid_uid(value: Any) -> bool:
        text = str(value or "").strip()
        return len(text) == 8 and text.isdigit()

    def _uid_exists(self, conn: sqlite3.Connection, uid: str, *, exclude_user_id: Optional[int] = None) -> bool:
        normalized_uid = str(uid or "").strip()
        if not self._is_valid_uid(normalized_uid):
            return False
        params: List[Any] = [normalized_uid]
        query = "SELECT id FROM users WHERE uid = ?"
        if exclude_user_id is not None:
            query += " AND id != ?"
            params.append(int(exclude_user_id))
        row = conn.execute(query + " LIMIT 1", tuple(params)).fetchone()
        return bool(row)

    def _generate_random_uid(self, conn: sqlite3.Connection, *, exclude_user_id: Optional[int] = None) -> str:
        for _ in range(5000):
            candidate = f"{secrets.randbelow(100_000_000):08d}"
            if not self._uid_exists(conn, candidate, exclude_user_id=exclude_user_id):
                return candidate
        raise RuntimeError("unable to allocate unique UID")

    def _allocate_uid_for_email(
        self,
        conn: sqlite3.Connection,
        *,
        email: str,
        exclude_user_id: Optional[int] = None,
    ) -> str:
        normalized_email = str(email or "").strip().lower()
        preferred_uid = SPECIAL_UID_BY_EMAIL.get(normalized_email)
        if preferred_uid and self._is_valid_uid(preferred_uid):
            conflict_row = conn.execute(
                "SELECT id FROM users WHERE uid = ? AND id != ? LIMIT 1",
                (preferred_uid, int(exclude_user_id or -1)),
            ).fetchone()
            if conflict_row is not None:
                conflict_id = int(conflict_row["id"])
                replacement = self._generate_random_uid(conn, exclude_user_id=conflict_id)
                conn.execute(
                    "UPDATE users SET uid = ?, updated_at = ? WHERE id = ?",
                    (replacement, self._now(), conflict_id),
                )
            return preferred_uid
        return self._generate_random_uid(conn, exclude_user_id=exclude_user_id)

    def _enforce_uid_policy(self, conn: sqlite3.Connection) -> None:
        now = self._now()
        rows = conn.execute("SELECT id, email, uid FROM users ORDER BY id").fetchall()
        for row in rows:
            user_id = int(row["id"])
            email = str(row["email"] or "").strip().lower()
            uid = str(row["uid"] or "").strip()
            if uid and not self._is_valid_uid(uid):
                conn.execute("UPDATE users SET uid = NULL, updated_at = ? WHERE id = ?", (now, user_id))
                uid = ""

            desired_uid = SPECIAL_UID_BY_EMAIL.get(email)
            if desired_uid and uid != desired_uid:
                if self._uid_exists(conn, desired_uid, exclude_user_id=user_id):
                    conflict_row = conn.execute(
                        "SELECT id FROM users WHERE uid = ? AND id != ? LIMIT 1",
                        (desired_uid, user_id),
                    ).fetchone()
                    if conflict_row:
                        conflict_id = int(conflict_row["id"])
                        replacement_uid = self._generate_random_uid(conn, exclude_user_id=conflict_id)
                        conn.execute(
                            "UPDATE users SET uid = ?, updated_at = ? WHERE id = ?",
                            (replacement_uid, now, conflict_id),
                        )
                conn.execute("UPDATE users SET uid = ?, updated_at = ? WHERE id = ?", (desired_uid, now, user_id))
                uid = desired_uid

            if uid and self._uid_exists(conn, uid, exclude_user_id=user_id):
                replacement_uid = self._generate_random_uid(conn, exclude_user_id=user_id)
                conn.execute("UPDATE users SET uid = ?, updated_at = ? WHERE id = ?", (replacement_uid, now, user_id))
                uid = replacement_uid

            if not uid:
                generated_uid = self._generate_random_uid(conn, exclude_user_id=user_id)
                conn.execute("UPDATE users SET uid = ?, updated_at = ? WHERE id = ?", (generated_uid, now, user_id))

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> Dict[str, Any]:
        user = dict(row)
        user["first_name"] = str(user.get("first_name", "") or "").strip()
        user["last_name"] = str(user.get("last_name", "") or "").strip()
        user["date_of_birth"] = str(user.get("date_of_birth", "") or "").strip()
        user["gender"] = str(user.get("gender", "") or "").strip()
        user["base_region"] = str(user.get("base_region", "") or "").strip().upper()
        user["is_corporate_account"] = bool(user.get("is_corporate_account", 0))
        user["is_active"] = bool(user.get("is_active", 0))
        user["totp_enabled"] = bool(user.get("totp_enabled", 0))
        user["email_verified"] = bool(user.get("email_verified", 1))
        user["session_version"] = max(1, int(user.get("session_version") or 1))
        return user

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    first_name TEXT NOT NULL DEFAULT '',
                    last_name TEXT NOT NULL DEFAULT '',
                    date_of_birth TEXT NULL,
                    gender TEXT NULL,
                    is_corporate_account INTEGER NOT NULL DEFAULT 0,
                    base_region TEXT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    parent_user_id INTEGER NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    totp_secret TEXT NULL,
                    totp_enabled INTEGER NOT NULL DEFAULT 0,
                    session_version INTEGER NOT NULL DEFAULT 1,
                    registration_ip TEXT NULL,
                    registration_country_code TEXT NULL,
                    registration_country_name TEXT NULL,
                    registration_country_flag TEXT NULL,
                    registration_ip_is_vpn INTEGER NULL,
                    registration_ip_is_residential_proxy INTEGER NULL,
                    registration_ip_is_other_proxy INTEGER NULL,
                    registration_ip_is_datacenter INTEGER NULL,
                    registration_ip_is_hosting INTEGER NULL,
                    registration_device_uuid TEXT NULL,
                    registration_device_type TEXT NULL,
                    registration_os_name TEXT NULL,
                    registration_os_version TEXT NULL,
                    registration_browser_name TEXT NULL,
                    registration_browser_version TEXT NULL,
                    registration_recorded_at TEXT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 1,
                    email_verified_at TEXT NULL,
                    created_by_user_id INTEGER NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (role IN ('master', 'admin', 'child')),
                    FOREIGN KEY (parent_user_id) REFERENCES users(id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_parent ON users(parent_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS email_verification_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    expires_at_epoch INTEGER NOT NULL,
                    used_at_epoch INTEGER NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_email_verification_email ON email_verification_codes(email)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_email_verification_expiry ON email_verification_codes(expires_at_epoch)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_action_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NULL,
                    email TEXT NULL,
                    purpose TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    metadata_json TEXT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    expires_at_epoch INTEGER NOT NULL,
                    used_at_epoch INTEGER NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_security_action_user_purpose ON security_action_codes(user_id, purpose, id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_security_action_email_purpose ON security_action_codes(email, purpose, id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    expires_at_epoch INTEGER NOT NULL,
                    used_at_epoch INTEGER NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_password_reset_email ON password_reset_tokens(email, id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_login_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    first_failure_epoch INTEGER NOT NULL,
                    last_failure_epoch INTEGER NOT NULL,
                    locked_until_epoch INTEGER NOT NULL DEFAULT 0,
                    last_reason TEXT NULL,
                    last_user_id INTEGER NULL,
                    updated_at_utc TEXT NOT NULL,
                    UNIQUE(email, ip_address)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_login_failures_locked ON auth_login_failures(locked_until_epoch)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_login_failures_last_failure ON auth_login_failures(last_failure_epoch)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_login_contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    fingerprint_hash TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    user_agent TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    login_count INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(user_id, fingerprint_hash),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_login_context_user_last_seen ON user_login_contexts(user_id, last_seen_at)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    device_uuid TEXT NOT NULL,
                    device_type TEXT NOT NULL DEFAULT '',
                    os_name TEXT NOT NULL DEFAULT '',
                    os_version TEXT NOT NULL DEFAULT '',
                    browser_name TEXT NOT NULL DEFAULT '',
                    browser_version TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_ip_address TEXT NULL,
                    last_country_code TEXT NULL,
                    last_country_name TEXT NULL,
                    last_country_flag TEXT NULL,
                    UNIQUE(user_id, device_uuid),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_devices_user_last_seen ON user_devices(user_id, last_seen_at)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL UNIQUE,
                    created_at_utc TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    actor_email TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    target_user_id INTEGER NULL,
                    ip_address TEXT NULL,
                    device_uuid TEXT NULL,
                    device_type TEXT NULL,
                    os_name TEXT NULL,
                    os_version TEXT NULL,
                    browser_name TEXT NULL,
                    browser_version TEXT NULL,
                    country_code TEXT NULL,
                    country_name TEXT NULL,
                    country_flag TEXT NULL,
                    is_vpn INTEGER NULL,
                    is_residential_proxy INTEGER NULL,
                    is_other_proxy INTEGER NULL,
                    is_datacenter INTEGER NULL,
                    is_hosting INTEGER NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_operation_user_created ON user_operation_logs(user_id, created_at_utc)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_operation_target_created ON user_operation_logs(target_user_id, created_at_utc)"
            )

            # Schema migration for existing deployments.
            column_names = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
            if "uid" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN uid TEXT")
            if "email_verified" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
            if "email_verified_at" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT NULL")
            if "first_name" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN first_name TEXT NOT NULL DEFAULT ''")
            if "last_name" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
            if "session_version" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")
            if "date_of_birth" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN date_of_birth TEXT NULL")
            if "gender" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN gender TEXT NULL")
            if "is_corporate_account" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN is_corporate_account INTEGER NOT NULL DEFAULT 0")
            if "base_region" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN base_region TEXT NULL")
            if "registration_ip" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_ip TEXT NULL")
            if "registration_country_code" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_country_code TEXT NULL")
            if "registration_country_name" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_country_name TEXT NULL")
            if "registration_country_flag" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_country_flag TEXT NULL")
            if "registration_ip_is_vpn" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_ip_is_vpn INTEGER NULL")
            if "registration_ip_is_residential_proxy" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_ip_is_residential_proxy INTEGER NULL")
            if "registration_ip_is_other_proxy" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_ip_is_other_proxy INTEGER NULL")
            if "registration_ip_is_datacenter" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_ip_is_datacenter INTEGER NULL")
            if "registration_ip_is_hosting" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_ip_is_hosting INTEGER NULL")
            if "registration_device_uuid" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_device_uuid TEXT NULL")
            if "registration_device_type" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_device_type TEXT NULL")
            if "registration_os_name" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_os_name TEXT NULL")
            if "registration_os_version" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_os_version TEXT NULL")
            if "registration_browser_name" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_browser_name TEXT NULL")
            if "registration_browser_version" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_browser_version TEXT NULL")
            if "registration_recorded_at" not in column_names:
                conn.execute("ALTER TABLE users ADD COLUMN registration_recorded_at TEXT NULL")
            conn.execute("UPDATE users SET session_version = 1 WHERE session_version IS NULL OR session_version < 1")
            self._enforce_uid_policy(conn)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_uid_unique ON users(uid)")
            conn.commit()

    def ensure_master_account(self, email: str, password_hash: str) -> None:
        normalized = email.strip().lower()
        now = self._now()
        with self._connect() as conn:
            row = conn.execute("SELECT id, role, is_active, uid FROM users WHERE email = ?", (normalized,)).fetchone()
            if row is None:
                uid = self._allocate_uid_for_email(conn, email=normalized)
                conn.execute(
                    """
                    INSERT INTO users (uid, email, first_name, last_name, password_hash, role, parent_user_id, is_active, totp_secret,
                                       totp_enabled, email_verified, email_verified_at, created_by_user_id, created_at, updated_at)
                    VALUES (?, ?, '', '', ?, 'master', NULL, 1, NULL, 0, 1, ?, NULL, ?, ?)
                    """,
                    (uid, normalized, password_hash, now, now, now),
                )
                return

            if row["role"] != "master" or int(row["is_active"]) == 0:
                conn.execute(
                    "UPDATE users SET role = 'master', is_active = 1, updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
            if not self._is_valid_uid(row["uid"]):
                uid = self._allocate_uid_for_email(conn, email=normalized, exclude_user_id=int(row["id"]))
                conn.execute("UPDATE users SET uid = ?, updated_at = ? WHERE id = ?", (uid, now, int(row["id"])))
            conn.commit()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        normalized = email.strip().lower()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
            if row is None:
                return None
            return self._row_to_user(row)

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if row is None:
                return None
            return self._row_to_user(row)

    def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        normalized_uid = str(uid or "").strip()
        if not self._is_valid_uid(normalized_uid):
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE uid = ?", (normalized_uid,)).fetchone()
            if row is None:
                return None
            return self._row_to_user(row)

    def list_users(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY CASE role WHEN 'master' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, id"
            ).fetchall()
            return [self._row_to_user(row) for row in rows]

    def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: str,
        parent_user_id: Optional[int],
        created_by_user_id: Optional[int],
        email_verified: bool = True,
        first_name: str = "",
        last_name: str = "",
    ) -> int:
        role = str(role).strip().lower()
        if role not in ALLOWED_ROLES:
            raise ValueError("Invalid role")

        normalized = email.strip().lower()
        normalized_first_name = str(first_name or "").strip()
        normalized_last_name = str(last_name or "").strip()
        now = self._now()
        with self._connect() as conn:
            uid = self._allocate_uid_for_email(conn, email=normalized)
            cursor = conn.execute(
                """
                INSERT INTO users (uid, email, first_name, last_name, password_hash, role, parent_user_id, is_active, totp_secret,
                                   totp_enabled, email_verified, email_verified_at, created_by_user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL, 0, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    normalized,
                    normalized_first_name,
                    normalized_last_name,
                    password_hash,
                    role,
                    parent_user_id,
                    1 if email_verified else 0,
                    now if email_verified else None,
                    int(created_by_user_id) if created_by_user_id is not None else None,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_email(self, user_id: int, email: str) -> None:
        normalized = email.strip().lower()
        with self._connect() as conn:
            row = conn.execute("SELECT uid FROM users WHERE id = ? LIMIT 1", (int(user_id),)).fetchone()
            next_uid = str(row["uid"] or "").strip() if row else ""
            reserved_uid = SPECIAL_UID_BY_EMAIL.get(normalized)
            if reserved_uid:
                next_uid = self._allocate_uid_for_email(conn, email=normalized, exclude_user_id=int(user_id))
            elif not self._is_valid_uid(next_uid):
                next_uid = self._generate_random_uid(conn, exclude_user_id=int(user_id))
            conn.execute(
                "UPDATE users SET email = ?, uid = ?, updated_at = ? WHERE id = ?",
                (normalized, next_uid, self._now(), int(user_id)),
            )
            conn.commit()

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, self._now(), int(user_id)),
            )

    def set_totp(self, user_id: int, secret: Optional[str], enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET totp_secret = ?, totp_enabled = ?, updated_at = ? WHERE id = ?",
                (secret, 1 if enabled else 0, self._now(), int(user_id)),
            )

    def set_active(self, user_id: int, active: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                (1 if active else 0, self._now(), int(user_id)),
            )

    def set_role(self, user_id: int, role: str) -> None:
        role = str(role).strip().lower()
        if role not in ALLOWED_ROLES:
            raise ValueError("Invalid role")
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                (role, self._now(), int(user_id)),
            )

    def set_parent(self, user_id: int, parent_user_id: Optional[int]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET parent_user_id = ?, updated_at = ? WHERE id = ?",
                (parent_user_id, self._now(), int(user_id)),
            )

    def count_children(self, *, parent_user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM users WHERE parent_user_id = ?",
                (int(parent_user_id),),
            ).fetchone()
        if row is None:
            return 0
        return int(row["total"] or 0)

    def delete_user(self, *, user_id: int) -> bool:
        target_user_id = int(user_id)
        with self._connect() as conn:
            existing = conn.execute("SELECT id FROM users WHERE id = ? LIMIT 1", (target_user_id,)).fetchone()
            if existing is None:
                return False

            # Keep referential integrity for local auth DB tables before removing the user row.
            conn.execute(
                "DELETE FROM user_operation_logs WHERE user_id = ? OR target_user_id = ?",
                (target_user_id, target_user_id),
            )
            conn.execute("DELETE FROM user_devices WHERE user_id = ?", (target_user_id,))
            conn.execute("DELETE FROM user_login_contexts WHERE user_id = ?", (target_user_id,))
            conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (target_user_id,))
            conn.execute("DELETE FROM security_action_codes WHERE user_id = ?", (target_user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (target_user_id,))
            conn.commit()
        return True

    def get_session_version(self, *, user_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_version FROM users WHERE id = ? LIMIT 1",
                (int(user_id),),
            ).fetchone()
        if row is None:
            return 1
        return max(1, int(row["session_version"] or 1))

    def bump_session_version(self, *, user_id: int) -> int:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET session_version = COALESCE(session_version, 1) + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, int(user_id)),
            )
            row = conn.execute(
                "SELECT session_version FROM users WHERE id = ? LIMIT 1",
                (int(user_id),),
            ).fetchone()
        if row is None:
            return 1
        return max(1, int(row["session_version"] or 1))

    def record_login_context(self, *, user_id: int, ip_address: str = "", user_agent: str = "") -> Dict[str, Any]:
        normalized_ip = str(ip_address or "").strip()[:64] or "unknown"
        normalized_ua = str(user_agent or "").strip()[:255] or "unknown"
        fingerprint_input = f"{normalized_ip}|{normalized_ua}"
        fingerprint_hash = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()
        now = self._now()

        with self._connect() as conn:
            known_context_count_row = conn.execute(
                "SELECT COUNT(*) AS total FROM user_login_contexts WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()
            known_ip_row = conn.execute(
                "SELECT 1 FROM user_login_contexts WHERE user_id = ? AND ip_address = ? LIMIT 1",
                (int(user_id), normalized_ip),
            ).fetchone()
            existing = conn.execute(
                """
                SELECT id, login_count
                FROM user_login_contexts
                WHERE user_id = ? AND fingerprint_hash = ?
                LIMIT 1
                """,
                (int(user_id), fingerprint_hash),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO user_login_contexts (
                        user_id, fingerprint_hash, ip_address, user_agent, first_seen_at, last_seen_at, login_count
                    ) VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (int(user_id), fingerprint_hash, normalized_ip, normalized_ua, now, now),
                )
            else:
                conn.execute(
                    """
                    UPDATE user_login_contexts
                    SET ip_address = ?, user_agent = ?, last_seen_at = ?, login_count = ?
                    WHERE id = ?
                    """,
                    (
                        normalized_ip,
                        normalized_ua,
                        now,
                        max(1, int(existing["login_count"] or 0)) + 1,
                        int(existing["id"]),
                    ),
                )

            conn.execute(
                """
                DELETE FROM user_login_contexts
                WHERE user_id = ?
                  AND id NOT IN (
                    SELECT id FROM user_login_contexts WHERE user_id = ? ORDER BY last_seen_at DESC LIMIT 30
                  )
                """,
                (int(user_id), int(user_id)),
            )

        known_contexts_before = int(known_context_count_row["total"] or 0) if known_context_count_row else 0
        return {
            "user_id": int(user_id),
            "known_contexts_before": known_contexts_before,
            "is_new_device": existing is None and known_contexts_before > 0,
            "is_new_ip": known_ip_row is None and known_contexts_before > 0,
            "ip_address": normalized_ip,
            "user_agent": normalized_ua,
        }

    @staticmethod
    def _to_db_nullable_bool(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return 1 if value else 0
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return 1
        if text in {"0", "false", "no", "off"}:
            return 0
        return None

    @staticmethod
    def _from_db_nullable_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        return bool(int(value))

    @staticmethod
    def _normalize_retention_days(value: Any, *, default_days: int) -> int:
        try:
            days = int(value)
        except (TypeError, ValueError):
            days = int(default_days)
        return max(1, min(days, 3650))

    @staticmethod
    def _retention_cutoff(days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _normalize_auth_email(value: str) -> str:
        return str(value or "").strip().lower()[:320]

    @staticmethod
    def _normalize_auth_ip(value: str) -> str:
        return str(value or "").strip()[:64] or "unknown"

    def _cleanup_auth_failures(
        self,
        conn: sqlite3.Connection,
        *,
        window_seconds: int,
        lockout_seconds: int,
    ) -> None:
        now_epoch = int(time.time())
        retention_seconds = max(7 * 24 * 60 * 60, int(window_seconds) * 8, int(lockout_seconds) * 8)
        cutoff_epoch = now_epoch - retention_seconds
        conn.execute(
            """
            DELETE FROM auth_login_failures
            WHERE last_failure_epoch < ?
              AND locked_until_epoch < ?
            """,
            (cutoff_epoch, now_epoch),
        )

    def get_login_lockout_state(
        self,
        *,
        email: str,
        ip_address: str,
        window_seconds: int,
        max_failures: int,
        lockout_seconds: int,
    ) -> Dict[str, Any]:
        normalized_email = self._normalize_auth_email(email)
        normalized_ip = self._normalize_auth_ip(ip_address)
        window_seconds = max(60, int(window_seconds))
        max_failures = max(1, int(max_failures))
        lockout_seconds = max(30, int(lockout_seconds))
        now_epoch = int(time.time())

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT failure_count, first_failure_epoch, last_failure_epoch, locked_until_epoch
                FROM auth_login_failures
                WHERE email = ? AND ip_address = ?
                LIMIT 1
                """,
                (normalized_email, normalized_ip),
            ).fetchone()

        if row is None:
            return {
                "locked": False,
                "retry_after_seconds": 0,
                "failure_count": 0,
                "window_seconds": window_seconds,
                "max_failures": max_failures,
                "lockout_seconds": lockout_seconds,
                "email": normalized_email,
                "ip_address": normalized_ip,
            }

        locked_until_epoch = int(row["locked_until_epoch"] or 0)
        is_locked = locked_until_epoch > now_epoch
        retry_after_seconds = max(0, locked_until_epoch - now_epoch) if is_locked else 0
        failure_count = int(row["failure_count"] or 0)
        last_failure_epoch = int(row["last_failure_epoch"] or 0)
        if not is_locked and (now_epoch - last_failure_epoch) > window_seconds:
            failure_count = 0

        return {
            "locked": bool(is_locked),
            "retry_after_seconds": int(retry_after_seconds),
            "failure_count": int(failure_count),
            "window_seconds": window_seconds,
            "max_failures": max_failures,
            "lockout_seconds": lockout_seconds,
            "email": normalized_email,
            "ip_address": normalized_ip,
        }

    def register_login_failure(
        self,
        *,
        email: str,
        ip_address: str,
        reason: str = "",
        user_id: Optional[int] = None,
        window_seconds: int,
        max_failures: int,
        lockout_seconds: int,
    ) -> Dict[str, Any]:
        normalized_email = self._normalize_auth_email(email)
        normalized_ip = self._normalize_auth_ip(ip_address)
        normalized_reason = str(reason or "").strip().lower()[:120]
        window_seconds = max(60, int(window_seconds))
        max_failures = max(1, int(max_failures))
        lockout_seconds = max(30, int(lockout_seconds))
        now_epoch = int(time.time())
        now_utc = self._now()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, failure_count, first_failure_epoch, last_failure_epoch, locked_until_epoch
                FROM auth_login_failures
                WHERE email = ? AND ip_address = ?
                LIMIT 1
                """,
                (normalized_email, normalized_ip),
            ).fetchone()

            if row is None:
                failure_count = 1
                first_failure_epoch = now_epoch
                last_failure_epoch = now_epoch
                locked_until_epoch = 0
                row_id: Optional[int] = None
            else:
                row_id = int(row["id"])
                failure_count = int(row["failure_count"] or 0)
                first_failure_epoch = int(row["first_failure_epoch"] or now_epoch)
                last_failure_epoch = int(row["last_failure_epoch"] or now_epoch)
                locked_until_epoch = int(row["locked_until_epoch"] or 0)

                if (now_epoch - last_failure_epoch) > window_seconds:
                    failure_count = 1
                    first_failure_epoch = now_epoch
                else:
                    failure_count += 1
                last_failure_epoch = now_epoch

            if failure_count >= max_failures:
                locked_until_epoch = max(locked_until_epoch, now_epoch + lockout_seconds)

            if row is None:
                conn.execute(
                    """
                    INSERT INTO auth_login_failures (
                        email, ip_address, failure_count, first_failure_epoch, last_failure_epoch,
                        locked_until_epoch, last_reason, last_user_id, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_email,
                        normalized_ip,
                        failure_count,
                        first_failure_epoch,
                        last_failure_epoch,
                        locked_until_epoch,
                        normalized_reason or None,
                        int(user_id) if user_id is not None else None,
                        now_utc,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE auth_login_failures
                    SET failure_count = ?,
                        first_failure_epoch = ?,
                        last_failure_epoch = ?,
                        locked_until_epoch = ?,
                        last_reason = ?,
                        last_user_id = ?,
                        updated_at_utc = ?
                    WHERE id = ?
                    """,
                    (
                        failure_count,
                        first_failure_epoch,
                        last_failure_epoch,
                        locked_until_epoch,
                        normalized_reason or None,
                        int(user_id) if user_id is not None else None,
                        now_utc,
                        int(row_id),
                    ),
                )

            self._cleanup_auth_failures(
                conn,
                window_seconds=window_seconds,
                lockout_seconds=lockout_seconds,
            )
            conn.commit()

        is_locked = locked_until_epoch > now_epoch
        return {
            "locked": bool(is_locked),
            "retry_after_seconds": max(0, int(locked_until_epoch - now_epoch)) if is_locked else 0,
            "failure_count": int(failure_count),
            "window_seconds": window_seconds,
            "max_failures": max_failures,
            "lockout_seconds": lockout_seconds,
            "email": normalized_email,
            "ip_address": normalized_ip,
            "reason": normalized_reason,
        }

    def clear_login_failures(self, *, email: str, ip_address: str) -> int:
        normalized_email = self._normalize_auth_email(email)
        normalized_ip = self._normalize_auth_ip(ip_address)
        if not normalized_email:
            return 0

        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM auth_login_failures WHERE email = ? AND ip_address = ?",
                (normalized_email, normalized_ip),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def purge_user_telemetry(
        self,
        *,
        user_operation_retention_days: int = 180,
        user_device_retention_days: int = 180,
        user_login_context_retention_days: int = 90,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        op_days = self._normalize_retention_days(user_operation_retention_days, default_days=180)
        device_days = self._normalize_retention_days(user_device_retention_days, default_days=180)
        login_days = self._normalize_retention_days(user_login_context_retention_days, default_days=90)

        op_cutoff = self._retention_cutoff(op_days)
        device_cutoff = self._retention_cutoff(device_days)
        login_cutoff = self._retention_cutoff(login_days)

        with self._connect() as conn:
            if dry_run:
                op_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM user_operation_logs WHERE created_at_utc < ?",
                    (op_cutoff,),
                ).fetchone()
                device_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM user_devices WHERE last_seen_at < ?",
                    (device_cutoff,),
                ).fetchone()
                login_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM user_login_contexts WHERE last_seen_at < ?",
                    (login_cutoff,),
                ).fetchone()
                deleted_operation_logs = int((op_row or {"c": 0})["c"] or 0)
                deleted_devices = int((device_row or {"c": 0})["c"] or 0)
                deleted_login_contexts = int((login_row or {"c": 0})["c"] or 0)
            else:
                op_cursor = conn.execute(
                    "DELETE FROM user_operation_logs WHERE created_at_utc < ?",
                    (op_cutoff,),
                )
                device_cursor = conn.execute(
                    "DELETE FROM user_devices WHERE last_seen_at < ?",
                    (device_cutoff,),
                )
                login_cursor = conn.execute(
                    "DELETE FROM user_login_contexts WHERE last_seen_at < ?",
                    (login_cutoff,),
                )
                conn.commit()
                deleted_operation_logs = int(op_cursor.rowcount or 0)
                deleted_devices = int(device_cursor.rowcount or 0)
                deleted_login_contexts = int(login_cursor.rowcount or 0)

        return {
            "dry_run": bool(dry_run),
            "retention_days": {
                "user_operation_logs": op_days,
                "user_devices": device_days,
                "user_login_contexts": login_days,
            },
            "cutoffs_utc": {
                "user_operation_logs": op_cutoff,
                "user_devices": device_cutoff,
                "user_login_contexts": login_cutoff,
            },
            "deleted_rows": {
                "user_operation_logs": deleted_operation_logs,
                "user_devices": deleted_devices,
                "user_login_contexts": deleted_login_contexts,
                "total": deleted_operation_logs + deleted_devices + deleted_login_contexts,
            },
        }

    def update_registration_profile(
        self,
        *,
        user_id: int,
        date_of_birth: str = "",
        gender: str = "",
        is_corporate_account: bool = False,
        base_region: str = "",
        registration_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = registration_context or {}
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET date_of_birth = ?,
                    gender = ?,
                    is_corporate_account = ?,
                    base_region = ?,
                    registration_ip = ?,
                    registration_country_code = ?,
                    registration_country_name = ?,
                    registration_country_flag = ?,
                    registration_ip_is_vpn = ?,
                    registration_ip_is_residential_proxy = ?,
                    registration_ip_is_other_proxy = ?,
                    registration_ip_is_datacenter = ?,
                    registration_ip_is_hosting = ?,
                    registration_device_uuid = ?,
                    registration_device_type = ?,
                    registration_os_name = ?,
                    registration_os_version = ?,
                    registration_browser_name = ?,
                    registration_browser_version = ?,
                    registration_recorded_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    str(date_of_birth or "").strip() or None,
                    str(gender or "").strip().lower() or None,
                    1 if bool(is_corporate_account) else 0,
                    str(base_region or "").strip().upper() or None,
                    str(ctx.get("ip_address", "")).strip() or None,
                    str(ctx.get("country_code", "")).strip().upper() or None,
                    str(ctx.get("country_name", "")).strip() or None,
                    str(ctx.get("country_flag", "")).strip() or None,
                    self._to_db_nullable_bool(ctx.get("is_vpn")),
                    self._to_db_nullable_bool(ctx.get("is_residential_proxy")),
                    self._to_db_nullable_bool(ctx.get("is_other_proxy")),
                    self._to_db_nullable_bool(ctx.get("is_datacenter")),
                    self._to_db_nullable_bool(ctx.get("is_hosting")),
                    str(ctx.get("device_uuid", "")).strip() or None,
                    str(ctx.get("device_type", "")).strip() or None,
                    str(ctx.get("os_name", "")).strip() or None,
                    str(ctx.get("os_version", "")).strip() or None,
                    str(ctx.get("browser_name", "")).strip() or None,
                    str(ctx.get("browser_version", "")).strip() or None,
                    self._now(),
                    self._now(),
                    int(user_id),
                ),
            )

    def record_user_operation(
        self,
        *,
        user_id: int,
        operation_type: str,
        context: Optional[Dict[str, Any]] = None,
        target_user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_operation_type = str(operation_type or "").strip().lower()
        if not normalized_operation_type:
            raise ValueError("operation_type is required")

        actor = self.get_user_by_id(int(user_id))
        if not actor:
            raise ValueError("user not found")
        actor_email = str(actor.get("email", "")).strip().lower()
        ctx = context or {}
        operation_id = f"op-{secrets.token_hex(10)}"
        created_at = self._now()
        details_json = json.dumps(details or {}, ensure_ascii=True, sort_keys=True)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_operation_logs (
                    operation_id, created_at_utc, user_id, actor_email, operation_type, target_user_id,
                    ip_address, device_uuid, device_type, os_name, os_version, browser_name, browser_version,
                    country_code, country_name, country_flag,
                    is_vpn, is_residential_proxy, is_other_proxy, is_datacenter, is_hosting,
                    details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    created_at,
                    int(user_id),
                    actor_email,
                    normalized_operation_type,
                    int(target_user_id) if target_user_id is not None else None,
                    str(ctx.get("ip_address", "")).strip() or None,
                    str(ctx.get("device_uuid", "")).strip() or None,
                    str(ctx.get("device_type", "")).strip() or None,
                    str(ctx.get("os_name", "")).strip() or None,
                    str(ctx.get("os_version", "")).strip() or None,
                    str(ctx.get("browser_name", "")).strip() or None,
                    str(ctx.get("browser_version", "")).strip() or None,
                    str(ctx.get("country_code", "")).strip().upper() or None,
                    str(ctx.get("country_name", "")).strip() or None,
                    str(ctx.get("country_flag", "")).strip() or None,
                    self._to_db_nullable_bool(ctx.get("is_vpn")),
                    self._to_db_nullable_bool(ctx.get("is_residential_proxy")),
                    self._to_db_nullable_bool(ctx.get("is_other_proxy")),
                    self._to_db_nullable_bool(ctx.get("is_datacenter")),
                    self._to_db_nullable_bool(ctx.get("is_hosting")),
                    details_json,
                ),
            )
            device_uuid = str(ctx.get("device_uuid", "")).strip()
            if device_uuid:
                conn.execute(
                    """
                    INSERT INTO user_devices (
                        user_id, device_uuid, device_type, os_name, os_version, browser_name, browser_version,
                        first_seen_at, last_seen_at, last_ip_address, last_country_code, last_country_name, last_country_flag
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, device_uuid) DO UPDATE SET
                        device_type = excluded.device_type,
                        os_name = excluded.os_name,
                        os_version = excluded.os_version,
                        browser_name = excluded.browser_name,
                        browser_version = excluded.browser_version,
                        last_seen_at = excluded.last_seen_at,
                        last_ip_address = excluded.last_ip_address,
                        last_country_code = excluded.last_country_code,
                        last_country_name = excluded.last_country_name,
                        last_country_flag = excluded.last_country_flag
                    """,
                    (
                        int(user_id),
                        device_uuid,
                        str(ctx.get("device_type", "")).strip(),
                        str(ctx.get("os_name", "")).strip(),
                        str(ctx.get("os_version", "")).strip(),
                        str(ctx.get("browser_name", "")).strip(),
                        str(ctx.get("browser_version", "")).strip(),
                        created_at,
                        created_at,
                        str(ctx.get("ip_address", "")).strip() or None,
                        str(ctx.get("country_code", "")).strip().upper() or None,
                        str(ctx.get("country_name", "")).strip() or None,
                        str(ctx.get("country_flag", "")).strip() or None,
                    ),
                )

        return {
            "operation_id": operation_id,
            "created_at_utc": created_at,
            "user_id": int(user_id),
            "operation_type": normalized_operation_type,
            "target_user_id": int(target_user_id) if target_user_id is not None else None,
        }

    def list_user_operations(self, *, user_id: int, limit: int = 200, include_target_events: bool = True) -> List[Dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 1000))
        if include_target_events:
            query = """
                SELECT id, operation_id, created_at_utc, user_id, actor_email, operation_type, target_user_id,
                       ip_address, device_uuid, device_type, os_name, os_version, browser_name, browser_version,
                       country_code, country_name, country_flag,
                       is_vpn, is_residential_proxy, is_other_proxy, is_datacenter, is_hosting, details_json
                FROM user_operation_logs
                WHERE user_id = ? OR target_user_id = ?
                ORDER BY id DESC
                LIMIT ?
            """
            params: tuple[Any, ...] = (int(user_id), int(user_id), normalized_limit)
        else:
            query = """
                SELECT id, operation_id, created_at_utc, user_id, actor_email, operation_type, target_user_id,
                       ip_address, device_uuid, device_type, os_name, os_version, browser_name, browser_version,
                       country_code, country_name, country_flag,
                       is_vpn, is_residential_proxy, is_other_proxy, is_datacenter, is_hosting, details_json
                FROM user_operation_logs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            """
            params = (int(user_id), normalized_limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        operations: list[dict[str, Any]] = []
        for row in rows:
            details = self._decode_metadata(row["details_json"])
            operations.append(
                {
                    "id": int(row["id"]),
                    "operation_id": str(row["operation_id"] or "").strip(),
                    "created_at_utc": str(row["created_at_utc"] or "").strip(),
                    "user_id": int(row["user_id"] or 0),
                    "actor_email": str(row["actor_email"] or "").strip().lower(),
                    "operation_type": str(row["operation_type"] or "").strip().lower(),
                    "target_user_id": int(row["target_user_id"]) if row["target_user_id"] is not None else None,
                    "ip_address": str(row["ip_address"] or "").strip(),
                    "device_uuid": str(row["device_uuid"] or "").strip(),
                    "device_type": str(row["device_type"] or "").strip(),
                    "os_name": str(row["os_name"] or "").strip(),
                    "os_version": str(row["os_version"] or "").strip(),
                    "browser_name": str(row["browser_name"] or "").strip(),
                    "browser_version": str(row["browser_version"] or "").strip(),
                    "country_code": str(row["country_code"] or "").strip().upper(),
                    "country_name": str(row["country_name"] or "").strip(),
                    "country_flag": str(row["country_flag"] or "").strip(),
                    "is_vpn": self._from_db_nullable_bool(row["is_vpn"]),
                    "is_residential_proxy": self._from_db_nullable_bool(row["is_residential_proxy"]),
                    "is_other_proxy": self._from_db_nullable_bool(row["is_other_proxy"]),
                    "is_datacenter": self._from_db_nullable_bool(row["is_datacenter"]),
                    "is_hosting": self._from_db_nullable_bool(row["is_hosting"]),
                    "details": details,
                }
            )
        return operations

    def list_user_devices(self, *, user_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, device_uuid, device_type, os_name, os_version, browser_name, browser_version,
                       first_seen_at, last_seen_at, last_ip_address, last_country_code, last_country_name, last_country_flag
                FROM user_devices
                WHERE user_id = ?
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (int(user_id), normalized_limit),
            ).fetchall()
        return [
            {
                "user_id": int(row["user_id"] or 0),
                "device_uuid": str(row["device_uuid"] or "").strip(),
                "device_type": str(row["device_type"] or "").strip(),
                "os_name": str(row["os_name"] or "").strip(),
                "os_version": str(row["os_version"] or "").strip(),
                "browser_name": str(row["browser_name"] or "").strip(),
                "browser_version": str(row["browser_version"] or "").strip(),
                "first_seen_at": str(row["first_seen_at"] or "").strip(),
                "last_seen_at": str(row["last_seen_at"] or "").strip(),
                "last_ip_address": str(row["last_ip_address"] or "").strip(),
                "last_country_code": str(row["last_country_code"] or "").strip().upper(),
                "last_country_name": str(row["last_country_name"] or "").strip(),
                "last_country_flag": str(row["last_country_flag"] or "").strip(),
            }
            for row in rows
        ]

    def get_user_profile_details(self, *, user_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, uid, email, first_name, last_name, date_of_birth, gender, is_corporate_account, base_region,
                       role, parent_user_id, is_active, totp_enabled, created_at, updated_at,
                       registration_ip, registration_country_code, registration_country_name, registration_country_flag,
                       registration_ip_is_vpn, registration_ip_is_residential_proxy, registration_ip_is_other_proxy,
                       registration_ip_is_datacenter, registration_ip_is_hosting,
                       registration_device_uuid, registration_device_type, registration_os_name, registration_os_version,
                       registration_browser_name, registration_browser_version, registration_recorded_at
                FROM users
                WHERE id = ?
                LIMIT 1
                """,
                (int(user_id),),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "uid": str(row["uid"] or "").strip(),
            "email": str(row["email"] or "").strip().lower(),
            "first_name": str(row["first_name"] or "").strip(),
            "last_name": str(row["last_name"] or "").strip(),
            "date_of_birth": str(row["date_of_birth"] or "").strip(),
            "gender": str(row["gender"] or "").strip().lower(),
            "is_corporate_account": bool(row["is_corporate_account"] or 0),
            "base_region": str(row["base_region"] or "").strip().upper(),
            "role": str(row["role"] or "").strip().lower(),
            "parent_user_id": int(row["parent_user_id"]) if row["parent_user_id"] is not None else None,
            "is_active": bool(row["is_active"] or 0),
            "totp_enabled": bool(row["totp_enabled"] or 0),
            "created_at": str(row["created_at"] or "").strip(),
            "updated_at": str(row["updated_at"] or "").strip(),
            "registration_ip": str(row["registration_ip"] or "").strip(),
            "registration_country_code": str(row["registration_country_code"] or "").strip().upper(),
            "registration_country_name": str(row["registration_country_name"] or "").strip(),
            "registration_country_flag": str(row["registration_country_flag"] or "").strip(),
            "registration_ip_is_vpn": self._from_db_nullable_bool(row["registration_ip_is_vpn"]),
            "registration_ip_is_residential_proxy": self._from_db_nullable_bool(row["registration_ip_is_residential_proxy"]),
            "registration_ip_is_other_proxy": self._from_db_nullable_bool(row["registration_ip_is_other_proxy"]),
            "registration_ip_is_datacenter": self._from_db_nullable_bool(row["registration_ip_is_datacenter"]),
            "registration_ip_is_hosting": self._from_db_nullable_bool(row["registration_ip_is_hosting"]),
            "registration_device_uuid": str(row["registration_device_uuid"] or "").strip(),
            "registration_device_type": str(row["registration_device_type"] or "").strip(),
            "registration_os_name": str(row["registration_os_name"] or "").strip(),
            "registration_os_version": str(row["registration_os_version"] or "").strip(),
            "registration_browser_name": str(row["registration_browser_name"] or "").strip(),
            "registration_browser_version": str(row["registration_browser_version"] or "").strip(),
            "registration_recorded_at": str(row["registration_recorded_at"] or "").strip(),
        }

    def verification_send_retry_after(self, *, email: str, cooldown_seconds: int) -> int:
        normalized = email.strip().lower()
        cooldown_seconds = max(0, int(cooldown_seconds))
        if cooldown_seconds == 0:
            return 0

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT created_at_epoch
                FROM email_verification_codes
                WHERE email = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()

        if row is None:
            return 0

        now = int(time.time())
        elapsed = now - int(row["created_at_epoch"])
        return max(0, cooldown_seconds - elapsed)

    def create_email_verification_code(self, *, email: str, code: str, expiry_minutes: int = 30) -> Dict[str, Any]:
        normalized = email.strip().lower()
        now = int(time.time())
        expires_at = now + max(5, int(expiry_minutes)) * 60
        code_hash = generate_password_hash(str(code))

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE email_verification_codes
                SET used_at_epoch = ?
                WHERE email = ? AND used_at_epoch IS NULL
                """,
                (now, normalized),
            )
            conn.execute(
                """
                INSERT INTO email_verification_codes (email, code_hash, created_at_epoch, expires_at_epoch, used_at_epoch)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (normalized, code_hash, now, expires_at),
            )

        return {"email": normalized, "expires_at_epoch": expires_at}

    def consume_email_verification_code(self, *, email: str, code: str) -> Dict[str, Any]:
        normalized = email.strip().lower()
        candidate = str(code or "").strip()
        now = int(time.time())

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, code_hash, expires_at_epoch
                FROM email_verification_codes
                WHERE email = ? AND used_at_epoch IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()

            if row is None:
                return {"status": "missing"}

            if int(row["expires_at_epoch"]) < now:
                conn.execute(
                    "UPDATE email_verification_codes SET used_at_epoch = ? WHERE id = ?",
                    (now, int(row["id"])),
                )
                return {"status": "expired"}

            if not check_password_hash(str(row["code_hash"]), candidate):
                return {"status": "invalid"}

            conn.execute(
                "UPDATE email_verification_codes SET used_at_epoch = ? WHERE id = ?",
                (now, int(row["id"])),
            )
            return {"status": "verified"}

    @staticmethod
    def _encode_metadata(metadata: Optional[Dict[str, Any]]) -> str:
        if not metadata:
            return "{}"
        try:
            return json.dumps(metadata, separators=(",", ":"))
        except Exception:
            return "{}"

    @staticmethod
    def _decode_metadata(value: Any) -> Dict[str, Any]:
        text = str(value or "").strip()
        if not text:
            return {}
        try:
            decoded = json.loads(text)
        except Exception:
            return {}
        return decoded if isinstance(decoded, dict) else {}

    def security_code_retry_after(
        self,
        *,
        purpose: str,
        cooldown_seconds: int,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
    ) -> int:
        normalized_purpose = str(purpose or "").strip().lower()
        normalized_email = str(email or "").strip().lower()
        cooldown_seconds = max(0, int(cooldown_seconds))
        if not normalized_purpose or cooldown_seconds == 0:
            return 0
        if user_id is None and not normalized_email:
            return 0

        query = [
            "SELECT created_at_epoch FROM security_action_codes",
            "WHERE lower(purpose) = ?",
        ]
        params: List[Any] = [normalized_purpose]
        if user_id is not None:
            query.append("AND user_id = ?")
            params.append(int(user_id))
        if normalized_email:
            query.append("AND lower(email) = ?")
            params.append(normalized_email)
        query.append("ORDER BY id DESC LIMIT 1")

        with self._connect() as conn:
            row = conn.execute(" ".join(query), tuple(params)).fetchone()

        if row is None:
            return 0
        now = int(time.time())
        elapsed = now - int(row["created_at_epoch"])
        return max(0, cooldown_seconds - elapsed)

    def create_security_action_code(
        self,
        *,
        purpose: str,
        code: str,
        expiry_minutes: int,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_purpose = str(purpose or "").strip().lower()
        normalized_email = str(email or "").strip().lower() if email else None
        code_hash = generate_password_hash(str(code))
        now = int(time.time())
        expires_at = now + max(5, int(expiry_minutes)) * 60
        metadata_json = self._encode_metadata(metadata)

        if not normalized_purpose:
            raise ValueError("purpose is required")
        if user_id is None and not normalized_email:
            raise ValueError("user_id or email is required")

        with self._connect() as conn:
            where_clauses = ["lower(purpose) = ? AND used_at_epoch IS NULL"]
            params: List[Any] = [normalized_purpose]
            if user_id is not None:
                where_clauses.append("user_id = ?")
                params.append(int(user_id))
            if normalized_email:
                where_clauses.append("lower(email) = ?")
                params.append(normalized_email)

            conn.execute(
                f"UPDATE security_action_codes SET used_at_epoch = ? WHERE {' AND '.join(where_clauses)}",
                (now, *params),
            )
            conn.execute(
                """
                INSERT INTO security_action_codes (
                    user_id, email, purpose, code_hash, metadata_json, created_at_epoch, expires_at_epoch, used_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    int(user_id) if user_id is not None else None,
                    normalized_email,
                    normalized_purpose,
                    code_hash,
                    metadata_json,
                    now,
                    expires_at,
                ),
            )

        return {
            "purpose": normalized_purpose,
            "expires_at_epoch": expires_at,
            "user_id": int(user_id) if user_id is not None else None,
            "email": normalized_email,
        }

    def consume_security_action_code(
        self,
        *,
        purpose: str,
        code: str,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_purpose = str(purpose or "").strip().lower()
        candidate = str(code or "").strip()
        normalized_email = str(email or "").strip().lower()
        if not normalized_purpose or not candidate:
            return {"status": "invalid"}
        if user_id is None and not normalized_email:
            return {"status": "missing"}

        query = [
            "SELECT id, user_id, email, code_hash, metadata_json, expires_at_epoch",
            "FROM security_action_codes",
            "WHERE lower(purpose) = ? AND used_at_epoch IS NULL",
        ]
        params: List[Any] = [normalized_purpose]
        if user_id is not None:
            query.append("AND user_id = ?")
            params.append(int(user_id))
        if normalized_email:
            query.append("AND lower(email) = ?")
            params.append(normalized_email)
        query.append("ORDER BY id DESC LIMIT 1")

        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute(" ".join(query), tuple(params)).fetchone()
            if row is None:
                return {"status": "missing"}

            if int(row["expires_at_epoch"]) < now:
                conn.execute(
                    "UPDATE security_action_codes SET used_at_epoch = ? WHERE id = ?",
                    (now, int(row["id"])),
                )
                return {"status": "expired"}

            if not check_password_hash(str(row["code_hash"]), candidate):
                return {"status": "invalid"}

            conn.execute(
                "UPDATE security_action_codes SET used_at_epoch = ? WHERE id = ?",
                (now, int(row["id"])),
            )

        return {
            "status": "verified",
            "user_id": int(row["user_id"]) if row["user_id"] is not None else None,
            "email": str(row["email"] or "").strip().lower() or None,
            "metadata": self._decode_metadata(row["metadata_json"]),
        }

    def password_reset_retry_after(self, *, email: str, cooldown_seconds: int) -> int:
        normalized = email.strip().lower()
        cooldown_seconds = max(0, int(cooldown_seconds))
        if cooldown_seconds == 0:
            return 0

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT created_at_epoch
                FROM password_reset_tokens
                WHERE lower(email) = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()

        if row is None:
            return 0
        now = int(time.time())
        elapsed = now - int(row["created_at_epoch"])
        return max(0, cooldown_seconds - elapsed)

    def create_password_reset_token(
        self,
        *,
        user_id: int,
        email: str,
        token_secret: str,
        expiry_minutes: int,
    ) -> Dict[str, Any]:
        normalized_email = email.strip().lower()
        now = int(time.time())
        expires_at = now + max(5, int(expiry_minutes)) * 60
        token_hash = generate_password_hash(str(token_secret))

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE password_reset_tokens
                SET used_at_epoch = ?
                WHERE user_id = ? AND used_at_epoch IS NULL
                """,
                (now, int(user_id)),
            )
            cursor = conn.execute(
                """
                INSERT INTO password_reset_tokens (
                    user_id, email, token_hash, created_at_epoch, expires_at_epoch, used_at_epoch
                ) VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (int(user_id), normalized_email, token_hash, now, expires_at),
            )
            token_id = int(cursor.lastrowid)

        return {"id": token_id, "expires_at_epoch": expires_at, "email": normalized_email}

    def consume_password_reset_token(self, *, token: str) -> Dict[str, Any]:
        token_value = str(token or "").strip()
        if "." not in token_value:
            return {"status": "invalid"}
        id_part, secret_part = token_value.split(".", 1)
        if not id_part.isdigit() or not secret_part:
            return {"status": "invalid"}
        token_id = int(id_part)
        now = int(time.time())

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, email, token_hash, expires_at_epoch
                FROM password_reset_tokens
                WHERE id = ? AND used_at_epoch IS NULL
                LIMIT 1
                """,
                (token_id,),
            ).fetchone()

            if row is None:
                return {"status": "missing"}

            if int(row["expires_at_epoch"]) < now:
                conn.execute(
                    "UPDATE password_reset_tokens SET used_at_epoch = ? WHERE id = ?",
                    (now, token_id),
                )
                return {"status": "expired"}

            if not check_password_hash(str(row["token_hash"]), secret_part):
                return {"status": "invalid"}

            conn.execute(
                "UPDATE password_reset_tokens SET used_at_epoch = ? WHERE id = ?",
                (now, token_id),
            )

        return {
            "status": "verified",
            "user_id": int(row["user_id"]),
            "email": str(row["email"]).strip().lower(),
        }
