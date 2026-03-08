"""Support ticket persistence for the help-desk flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import sqlite3
from threading import Lock
import time
from typing import Any, Dict, List, Optional


class TicketStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = Lock()
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_ticket(row: sqlite3.Row) -> Dict[str, Any]:
        unread_count = 0
        if "unread_customer_count" in row.keys():
            unread_count = int(row["unread_customer_count"] or 0)
        attachment_count = 0
        if "attachment_count" in row.keys():
            attachment_count = int(row["attachment_count"] or 0)
        submitter_user_id = None
        if "submitter_user_id" in row.keys() and row["submitter_user_id"] is not None:
            submitter_user_id = int(row["submitter_user_id"])
        is_authenticated_submitter = False
        if "is_authenticated_submitter" in row.keys():
            is_authenticated_submitter = bool(int(row["is_authenticated_submitter"] or 0))
        bug_surface = str(row["bug_surface"] or "").strip() if "bug_surface" in row.keys() else ""
        bug_severity = str(row["bug_severity"] or "").strip() if "bug_severity" in row.keys() else ""
        bug_reproducible = str(row["bug_reproducible"] or "").strip() if "bug_reproducible" in row.keys() else ""
        payment_txid = str(row["payment_txid"] or "").strip() if "payment_txid" in row.keys() else ""
        payment_chain = str(row["payment_chain"] or "").strip() if "payment_chain" in row.keys() else ""
        return {
            "id": int(row["id"]),
            "ticket_ref": str(row["ticket_ref"]),
            "created_at_utc": str(row["created_at_utc"]),
            "customer_email": str(row["customer_email"]),
            "subject": str(row["subject"]),
            "message": str(row["message"]),
            "category": str(row["category"]),
            "confidence": float(row["confidence"]),
            "status": str(row["status"]),
            "unread_customer_count": unread_count,
            "attachment_count": attachment_count,
            "submitter_user_id": submitter_user_id,
            "is_authenticated_submitter": is_authenticated_submitter,
            "bug_surface": bug_surface,
            "bug_severity": bug_severity,
            "bug_reproducible": bug_reproducible,
            "payment_txid": payment_txid,
            "payment_chain": payment_chain,
        }

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Dict[str, Any]:
        support_read_at = ""
        if "support_read_at_utc" in row.keys():
            support_read_at = str(row["support_read_at_utc"] or "")
        return {
            "id": int(row["id"]),
            "ticket_ref": str(row["ticket_ref"]),
            "created_at_utc": str(row["created_at_utc"]),
            "author_type": str(row["author_type"]),
            "author_email": str(row["author_email"]),
            "body": str(row["body"]),
            "support_read_at_utc": support_read_at,
        }

    @staticmethod
    def _row_to_operational_alert(row: sqlite3.Row) -> Dict[str, Any]:
        context_raw = str(row["context_json"] or "").strip()
        context: Any = {}
        if context_raw:
            try:
                context = json.loads(context_raw)
            except json.JSONDecodeError:
                context = {"raw": context_raw}
        return {
            "id": int(row["id"]),
            "created_at_utc": str(row["created_at_utc"]),
            "category": str(row["category"]),
            "severity": str(row["severity"]),
            "event_key": str(row["event_key"] or ""),
            "message": str(row["message"]),
            "context": context,
            "resolved_at_utc": str(row["resolved_at_utc"] or ""),
        }

    @staticmethod
    def _row_to_attachment(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]),
            "ticket_ref": str(row["ticket_ref"]),
            "created_at_utc": str(row["created_at_utc"]),
            "original_filename": str(row["original_filename"] or ""),
            "stored_filename": str(row["stored_filename"] or ""),
            "storage_rel_path": str(row["storage_rel_path"] or ""),
            "mime_type": str(row["mime_type"] or ""),
            "size_bytes": int(row["size_bytes"] or 0),
            "sha256": str(row["sha256"] or ""),
            "scan_engine": str(row["scan_engine"] or ""),
            "scan_result": str(row["scan_result"] or ""),
            "scan_details_json": str(row["scan_details_json"] or ""),
        }

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_ref TEXT UNIQUE,
                    created_at_utc TEXT NOT NULL,
                    customer_email TEXT NOT NULL,
                    submitter_user_id INTEGER NULL,
                    is_authenticated_submitter INTEGER NOT NULL DEFAULT 0,
                    subject TEXT NOT NULL,
                    message TEXT NOT NULL,
                    category TEXT NOT NULL,
                    bug_surface TEXT NOT NULL DEFAULT '',
                    bug_severity TEXT NOT NULL DEFAULT '',
                    bug_reproducible TEXT NOT NULL DEFAULT '',
                    payment_txid TEXT NOT NULL DEFAULT '',
                    payment_chain TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_ticket_rate_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_epoch INTEGER NOT NULL,
                    client_ip TEXT NOT NULL,
                    customer_email TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rate_events_created ON support_ticket_rate_events(created_at_epoch)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rate_events_ip_created ON support_ticket_rate_events(client_ip, created_at_epoch)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rate_events_email_created ON support_ticket_rate_events(customer_email, created_at_epoch)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_ticket_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_ref TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    author_type TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    body TEXT NOT NULL,
                    support_read_at_utc TEXT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticket_messages_ref ON support_ticket_messages(ticket_ref, id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    email_id TEXT,
                    created_at_utc TEXT NOT NULL,
                    UNIQUE(provider, event_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_support_webhook_events_created ON support_webhook_events(created_at_utc)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_operational_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    event_key TEXT,
                    message TEXT NOT NULL,
                    context_json TEXT,
                    resolved_at_utc TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_support_ops_open ON support_operational_alerts(resolved_at_utc, created_at_utc)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_support_ops_event_key ON support_operational_alerts(event_key)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_resend_sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_utc TEXT NOT NULL,
                    checked INTEGER NOT NULL,
                    processed INTEGER NOT NULL,
                    duplicates INTEGER NOT NULL,
                    unmapped INTEGER NOT NULL,
                    failed_hard INTEGER NOT NULL,
                    threshold INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_support_resend_sync_runs_created ON support_resend_sync_runs(created_at_utc)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS support_ticket_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_ref TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    storage_rel_path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    scan_engine TEXT NOT NULL,
                    scan_result TEXT NOT NULL,
                    scan_details_json TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_support_ticket_attachments_ref ON support_ticket_attachments(ticket_ref, id)"
            )

            message_columns = {row["name"] for row in conn.execute("PRAGMA table_info(support_ticket_messages)").fetchall()}
            if "support_read_at_utc" not in message_columns:
                conn.execute("ALTER TABLE support_ticket_messages ADD COLUMN support_read_at_utc TEXT NULL")
                conn.execute(
                    """
                    UPDATE support_ticket_messages
                    SET support_read_at_utc = created_at_utc
                    WHERE lower(author_type) IN ('support', 'system')
                    """
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticket_messages_unread ON support_ticket_messages(ticket_ref, support_read_at_utc)"
            )

            # Backfill support/system messages as already read.
            conn.execute(
                """
                UPDATE support_ticket_messages
                SET support_read_at_utc = created_at_utc
                WHERE support_read_at_utc IS NULL
                  AND lower(author_type) IN ('support', 'system')
                """
            )
            # Closed/resolved tickets should not accumulate unread legacy customer messages.
            conn.execute(
                """
                UPDATE support_ticket_messages
                SET support_read_at_utc = created_at_utc
                WHERE support_read_at_utc IS NULL
                  AND lower(author_type) = 'customer'
                  AND ticket_ref IN (
                      SELECT ticket_ref
                      FROM support_tickets
                      WHERE lower(status) IN ('resolved', 'closed')
                  )
                """
            )
            conn.execute(
                """
                INSERT INTO support_ticket_messages (ticket_ref, created_at_utc, author_type, author_email, body)
                SELECT t.ticket_ref, t.created_at_utc, 'customer', t.customer_email, t.message
                FROM support_tickets t
                WHERE t.ticket_ref IS NOT NULL
                  AND t.ticket_ref != ''
                  AND NOT EXISTS (
                    SELECT 1
                    FROM support_ticket_messages m
                    WHERE m.ticket_ref = t.ticket_ref
                  )
                """
            )
            ticket_columns = {row["name"] for row in conn.execute("PRAGMA table_info(support_tickets)").fetchall()}
            if "submitter_user_id" not in ticket_columns:
                conn.execute("ALTER TABLE support_tickets ADD COLUMN submitter_user_id INTEGER NULL")
            if "is_authenticated_submitter" not in ticket_columns:
                conn.execute("ALTER TABLE support_tickets ADD COLUMN is_authenticated_submitter INTEGER NOT NULL DEFAULT 0")
            if "bug_surface" not in ticket_columns:
                conn.execute("ALTER TABLE support_tickets ADD COLUMN bug_surface TEXT NOT NULL DEFAULT ''")
            if "bug_severity" not in ticket_columns:
                conn.execute("ALTER TABLE support_tickets ADD COLUMN bug_severity TEXT NOT NULL DEFAULT ''")
            if "bug_reproducible" not in ticket_columns:
                conn.execute("ALTER TABLE support_tickets ADD COLUMN bug_reproducible TEXT NOT NULL DEFAULT ''")
            if "payment_txid" not in ticket_columns:
                conn.execute("ALTER TABLE support_tickets ADD COLUMN payment_txid TEXT NOT NULL DEFAULT ''")
            if "payment_chain" not in ticket_columns:
                conn.execute("ALTER TABLE support_tickets ADD COLUMN payment_chain TEXT NOT NULL DEFAULT ''")
            retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                "DELETE FROM support_webhook_events WHERE created_at_utc < ?",
                (retention_cutoff,),
            )
            resolved_retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                """
                DELETE FROM support_operational_alerts
                WHERE resolved_at_utc IS NOT NULL
                  AND resolved_at_utc < ?
                """,
                (resolved_retention_cutoff,),
            )
            sync_retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                "DELETE FROM support_resend_sync_runs WHERE created_at_utc < ?",
                (sync_retention_cutoff,),
            )
            conn.commit()

    def create_ticket(
        self,
        *,
        customer_email: str,
        subject: str,
        message: str,
        category: str,
        bug_surface: str = "",
        bug_severity: str = "",
        bug_reproducible: str = "",
        payment_txid: str = "",
        payment_chain: str = "",
        confidence: float,
        submitter_user_id: Optional[int] = None,
        is_authenticated_submitter: bool = False,
    ) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        created_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        normalized_bug_surface = str(bug_surface or "").strip().lower()
        normalized_bug_severity = str(bug_severity or "").strip().lower()
        normalized_bug_reproducible = str(bug_reproducible or "").strip().lower()
        normalized_payment_txid = str(payment_txid or "").strip()
        normalized_payment_chain = str(payment_chain or "").strip().lower()

        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO support_tickets (
                        created_at_utc,
                        customer_email,
                        submitter_user_id,
                        is_authenticated_submitter,
                        subject,
                        message,
                        category,
                        bug_surface,
                        bug_severity,
                        bug_reproducible,
                        payment_txid,
                        payment_chain,
                        confidence,
                        status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                    """,
                    (
                        created_at_utc,
                        customer_email,
                        int(submitter_user_id) if submitter_user_id is not None and int(submitter_user_id) > 0 else None,
                        1 if bool(is_authenticated_submitter) else 0,
                        subject,
                        message,
                        category,
                        normalized_bug_surface,
                        normalized_bug_severity,
                        normalized_bug_reproducible,
                        normalized_payment_txid,
                        normalized_payment_chain,
                        float(confidence),
                    ),
                )
                ticket_id = int(cursor.lastrowid)
                ticket_ref = f"HD-{now_utc:%Y%m%d}-{now_utc:%H%M%S%f}-{ticket_id:06d}"
                conn.execute(
                    "UPDATE support_tickets SET ticket_ref = ? WHERE id = ?",
                    (ticket_ref, ticket_id),
                )
                conn.execute(
                    """
                    INSERT INTO support_ticket_messages (ticket_ref, created_at_utc, author_type, author_email, body)
                    VALUES (?, ?, 'customer', ?, ?)
                    """,
                    (ticket_ref, created_at_utc, customer_email, message),
                )
                conn.commit()

        return {
            "id": ticket_id,
            "ticket_ref": ticket_ref,
            "created_at_utc": created_at_utc,
            "customer_email": customer_email,
            "subject": subject,
            "message": message,
            "category": category,
            "bug_surface": normalized_bug_surface,
            "bug_severity": normalized_bug_severity,
            "bug_reproducible": normalized_bug_reproducible,
            "payment_txid": normalized_payment_txid,
            "payment_chain": normalized_payment_chain,
            "confidence": float(confidence),
            "status": "open",
            "attachment_count": 0,
            "submitter_user_id": int(submitter_user_id) if submitter_user_id is not None and int(submitter_user_id) > 0 else None,
            "is_authenticated_submitter": bool(is_authenticated_submitter),
        }

    def list_tickets(self, *, status_filter: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        normalized_filter = (status_filter or "").strip().lower()
        limit = max(1, min(int(limit), 1000))

        with self._lock:
            with self._connect() as conn:
                if normalized_filter:
                    rows = conn.execute(
                        """
                        SELECT
                          t.id,
                          t.ticket_ref,
                          t.created_at_utc,
                          t.customer_email,
                          t.submitter_user_id,
                          t.is_authenticated_submitter,
                          t.subject,
                          t.message,
                          t.category,
                          t.bug_surface,
                          t.bug_severity,
                          t.bug_reproducible,
                          t.payment_txid,
                          t.payment_chain,
                          t.confidence,
                          t.status,
                          (
                            SELECT COUNT(*)
                            FROM support_ticket_messages m
                            WHERE m.ticket_ref = t.ticket_ref
                              AND lower(m.author_type) = 'customer'
                              AND m.support_read_at_utc IS NULL
                          ) AS unread_customer_count,
                          (
                            SELECT COUNT(*)
                            FROM support_ticket_attachments a
                            WHERE a.ticket_ref = t.ticket_ref
                          ) AS attachment_count
                        FROM support_tickets t
                        WHERE lower(t.status) = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (normalized_filter, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT
                          t.id,
                          t.ticket_ref,
                          t.created_at_utc,
                          t.customer_email,
                          t.submitter_user_id,
                          t.is_authenticated_submitter,
                          t.subject,
                          t.message,
                          t.category,
                          t.bug_surface,
                          t.bug_severity,
                          t.bug_reproducible,
                          t.payment_txid,
                          t.payment_chain,
                          t.confidence,
                          t.status,
                          (
                            SELECT COUNT(*)
                            FROM support_ticket_messages m
                            WHERE m.ticket_ref = t.ticket_ref
                              AND lower(m.author_type) = 'customer'
                              AND m.support_read_at_utc IS NULL
                          ) AS unread_customer_count,
                          (
                            SELECT COUNT(*)
                            FROM support_ticket_attachments a
                            WHERE a.ticket_ref = t.ticket_ref
                          ) AS attachment_count
                        FROM support_tickets t
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def list_tickets_for_customer(self, *, customer_email: str, limit: int = 200) -> List[Dict[str, Any]]:
        normalized_email = str(customer_email or "").strip().lower()
        if not normalized_email:
            return []
        limit = max(1, min(int(limit), 500))

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                      t.id,
                      t.ticket_ref,
                      t.created_at_utc,
                      t.customer_email,
                      t.submitter_user_id,
                      t.is_authenticated_submitter,
                      t.subject,
                      t.message,
                      t.category,
                      t.bug_surface,
                      t.bug_severity,
                      t.bug_reproducible,
                      t.payment_txid,
                      t.payment_chain,
                      t.confidence,
                      t.status,
                      (
                        SELECT COUNT(*)
                        FROM support_ticket_messages m
                        WHERE m.ticket_ref = t.ticket_ref
                          AND lower(m.author_type) = 'customer'
                          AND m.support_read_at_utc IS NULL
                      ) AS unread_customer_count,
                      (
                        SELECT COUNT(*)
                        FROM support_ticket_attachments a
                        WHERE a.ticket_ref = t.ticket_ref
                      ) AS attachment_count
                    FROM support_tickets t
                    WHERE lower(t.customer_email) = ?
                    ORDER BY t.id DESC
                    LIMIT ?
                    """,
                    (normalized_email, limit),
                ).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def get_ticket_by_ref(self, ticket_ref: str) -> Optional[Dict[str, Any]]:
        normalized_ref = str(ticket_ref or "").strip()
        if not normalized_ref:
            return None

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT
                      t.id,
                      t.ticket_ref,
                      t.created_at_utc,
                      t.customer_email,
                      t.submitter_user_id,
                      t.is_authenticated_submitter,
                      t.subject,
                      t.message,
                      t.category,
                      t.bug_surface,
                      t.bug_severity,
                      t.bug_reproducible,
                      t.payment_txid,
                      t.payment_chain,
                      t.confidence,
                      t.status,
                      (
                        SELECT COUNT(*)
                        FROM support_ticket_messages m
                        WHERE m.ticket_ref = t.ticket_ref
                          AND lower(m.author_type) = 'customer'
                          AND m.support_read_at_utc IS NULL
                      ) AS unread_customer_count,
                      (
                        SELECT COUNT(*)
                        FROM support_ticket_attachments a
                        WHERE a.ticket_ref = t.ticket_ref
                      ) AS attachment_count
                    FROM support_tickets t
                    WHERE t.ticket_ref = ?
                    LIMIT 1
                    """,
                    (normalized_ref,),
                ).fetchone()
        return self._row_to_ticket(row) if row else None

    def set_ticket_status(self, *, ticket_ref: str, status: str) -> bool:
        normalized_ref = str(ticket_ref or "").strip()
        normalized_status = str(status or "").strip().lower()
        if not normalized_ref or not normalized_status:
            return False

        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE support_tickets SET status = ? WHERE ticket_ref = ?",
                    (normalized_status, normalized_ref),
                )
                conn.commit()
                return int(cursor.rowcount) > 0

    def set_tickets_status(self, *, ticket_refs: List[str], status: str) -> int:
        normalized_status = str(status or "").strip().lower()
        refs = [str(ref or "").strip() for ref in ticket_refs if str(ref or "").strip()]
        if not normalized_status or not refs:
            return 0

        placeholders = ", ".join("?" for _ in refs)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    f"UPDATE support_tickets SET status = ? WHERE ticket_ref IN ({placeholders})",
                    (normalized_status, *refs),
                )
                conn.commit()
                return int(cursor.rowcount)

    def list_ticket_messages(self, *, ticket_ref: str) -> List[Dict[str, Any]]:
        normalized_ref = str(ticket_ref or "").strip()
        if not normalized_ref:
            return []

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, ticket_ref, created_at_utc, author_type, author_email, body, support_read_at_utc
                    FROM support_ticket_messages
                    WHERE ticket_ref = ?
                    ORDER BY id ASC
                    """,
                    (normalized_ref,),
                ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def mark_ticket_customer_messages_read(self, *, ticket_ref: str) -> int:
        normalized_ref = str(ticket_ref or "").strip()
        if not normalized_ref:
            return 0
        read_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE support_ticket_messages
                    SET support_read_at_utc = ?
                    WHERE ticket_ref = ?
                      AND lower(author_type) = 'customer'
                      AND support_read_at_utc IS NULL
                    """,
                    (read_at, normalized_ref),
                )
                conn.commit()
                return int(cursor.rowcount)

    def count_total_unread_customer_messages(self) -> int:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM support_ticket_messages
                    WHERE lower(author_type) = 'customer'
                      AND support_read_at_utc IS NULL
                    """
                ).fetchone()
        return int((row or {"c": 0})["c"])

    def has_webhook_event(self, *, provider: str, event_id: str) -> bool:
        normalized_provider = str(provider or "").strip().lower()
        normalized_event_id = str(event_id or "").strip()
        if not normalized_provider or not normalized_event_id:
            return False

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM support_webhook_events
                    WHERE provider = ? AND event_id = ?
                    LIMIT 1
                    """,
                    (normalized_provider, normalized_event_id),
                ).fetchone()
        return bool(row)

    def record_webhook_event(self, *, provider: str, event_id: str, email_id: str = "") -> bool:
        normalized_provider = str(provider or "").strip().lower()
        normalized_event_id = str(event_id or "").strip()
        normalized_email_id = str(email_id or "").strip()
        if not normalized_provider or not normalized_event_id:
            return False

        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO support_webhook_events (
                        provider, event_id, email_id, created_at_utc
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (normalized_provider, normalized_event_id, normalized_email_id, created_at_utc),
                )
                retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    "DELETE FROM support_webhook_events WHERE created_at_utc < ?",
                    (retention_cutoff,),
                )
                conn.commit()
                return int(cursor.rowcount) > 0

    def record_resend_sync_run(
        self,
        *,
        checked: int,
        processed: int,
        duplicates: int,
        unmapped: int,
        failed_hard: int,
        threshold: int,
    ) -> int:
        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        checked = max(0, int(checked or 0))
        processed = max(0, int(processed or 0))
        duplicates = max(0, int(duplicates or 0))
        unmapped = max(0, int(unmapped or 0))
        failed_hard = max(0, int(failed_hard or 0))
        threshold = max(0, int(threshold or 0))
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO support_resend_sync_runs (
                        created_at_utc, checked, processed, duplicates, unmapped, failed_hard, threshold
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (created_at_utc, checked, processed, duplicates, unmapped, failed_hard, threshold),
                )
                retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    "DELETE FROM support_resend_sync_runs WHERE created_at_utc < ?",
                    (retention_cutoff,),
                )
                conn.commit()
                return int(cursor.lastrowid or 0)

    def list_recent_resend_sync_runs(self, *, limit: int = 10) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, created_at_utc, checked, processed, duplicates, unmapped, failed_hard, threshold
                    FROM support_resend_sync_runs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "created_at_utc": str(row["created_at_utc"]),
                "checked": int(row["checked"] or 0),
                "processed": int(row["processed"] or 0),
                "duplicates": int(row["duplicates"] or 0),
                "unmapped": int(row["unmapped"] or 0),
                "failed_hard": int(row["failed_hard"] or 0),
                "threshold": int(row["threshold"] or 0),
            }
            for row in rows
        ]

    def has_recent_unmapped_breach(self, *, threshold: int, consecutive_runs: int) -> bool:
        threshold = max(1, int(threshold or 0))
        consecutive_runs = max(1, int(consecutive_runs or 0))
        rows = self.list_recent_resend_sync_runs(limit=consecutive_runs)
        if len(rows) < consecutive_runs:
            return False
        for row in rows:
            if int(row.get("checked") or 0) <= 0:
                return False
            if int(row.get("unmapped") or 0) < threshold:
                return False
        return True

    def create_operational_alert(
        self,
        *,
        category: str,
        severity: str,
        message: str,
        event_key: str = "",
        context: Any = None,
    ) -> int:
        normalized_category = str(category or "").strip().lower() or "general"
        normalized_severity = str(severity or "").strip().lower() or "error"
        if normalized_severity not in {"info", "warning", "error", "critical"}:
            normalized_severity = "error"
        normalized_message = str(message or "").strip()
        if not normalized_message:
            normalized_message = "operational alert"
        normalized_event_key = str(event_key or "").strip()

        context_json = ""
        if context is not None:
            try:
                context_json = json.dumps(context, ensure_ascii=True, sort_keys=True)
            except Exception:
                context_json = json.dumps({"raw": str(context)}, ensure_ascii=True)

        with self._lock:
            with self._connect() as conn:
                if normalized_event_key:
                    existing = conn.execute(
                        """
                        SELECT id
                        FROM support_operational_alerts
                        WHERE event_key = ?
                          AND resolved_at_utc IS NULL
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (normalized_event_key,),
                    ).fetchone()
                    if existing:
                        return int(existing["id"])

                created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                cursor = conn.execute(
                    """
                    INSERT INTO support_operational_alerts (
                        created_at_utc, category, severity, event_key, message, context_json, resolved_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        created_at_utc,
                        normalized_category,
                        normalized_severity,
                        normalized_event_key,
                        normalized_message,
                        context_json,
                    ),
                )
                conn.commit()
                return int(cursor.lastrowid or 0)

    def list_operational_alerts(self, *, open_only: bool = True, limit: int = 100) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            with self._connect() as conn:
                if open_only:
                    rows = conn.execute(
                        """
                        SELECT id, created_at_utc, category, severity, event_key, message, context_json, resolved_at_utc
                        FROM support_operational_alerts
                        WHERE resolved_at_utc IS NULL
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, created_at_utc, category, severity, event_key, message, context_json, resolved_at_utc
                        FROM support_operational_alerts
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
        return [self._row_to_operational_alert(row) for row in rows]

    def has_recent_operational_alert(self, *, event_key: str, within_seconds: int) -> bool:
        normalized_event_key = str(event_key or "").strip()
        if not normalized_event_key:
            return False
        window_seconds = max(0, int(within_seconds or 0))
        if window_seconds <= 0:
            return False
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id
                    FROM support_operational_alerts
                    WHERE event_key = ?
                      AND created_at_utc >= ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (normalized_event_key, cutoff),
                ).fetchone()
        return row is not None

    def count_open_operational_alerts(self) -> int:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM support_operational_alerts
                    WHERE resolved_at_utc IS NULL
                    """
                ).fetchone()
        return int((row or {"c": 0})["c"])

    def resolve_operational_alert(self, *, alert_id: int) -> bool:
        normalized_id = int(alert_id or 0)
        if normalized_id <= 0:
            return False
        resolved_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE support_operational_alerts
                    SET resolved_at_utc = ?
                    WHERE id = ?
                      AND resolved_at_utc IS NULL
                    """,
                    (resolved_at_utc, normalized_id),
                )
                conn.commit()
                return int(cursor.rowcount) > 0

    def add_ticket_message(
        self,
        *,
        ticket_ref: str,
        author_type: str,
        author_email: str,
        body: str,
    ) -> bool:
        normalized_ref = str(ticket_ref or "").strip()
        normalized_author_type = str(author_type or "").strip().lower()
        normalized_author_email = str(author_email or "").strip().lower()
        content = str(body or "").strip()
        if (
            not normalized_ref
            or normalized_author_type not in {"customer", "support", "system"}
            or not normalized_author_email
            or not content
        ):
            return False

        ticket = self.get_ticket_by_ref(normalized_ref)
        if not ticket:
            return False

        if len(content) > 8000:
            content = content[:8000]
        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        support_read_at_utc = created_at_utc if normalized_author_type in {"support", "system"} else None

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO support_ticket_messages (
                        ticket_ref, created_at_utc, author_type, author_email, body, support_read_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_ref,
                        created_at_utc,
                        normalized_author_type,
                        normalized_author_email,
                        content,
                        support_read_at_utc,
                    ),
                )
                conn.commit()
        return True

    def add_ticket_attachment(
        self,
        *,
        ticket_ref: str,
        original_filename: str,
        stored_filename: str,
        storage_rel_path: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        scan_engine: str,
        scan_result: str,
        scan_details: Any = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_ref = str(ticket_ref or "").strip()
        if not normalized_ref or not self.get_ticket_by_ref(normalized_ref):
            return None

        normalized_original = str(original_filename or "").strip()
        normalized_stored = str(stored_filename or "").strip()
        normalized_rel_path = str(storage_rel_path or "").strip()
        normalized_mime = str(mime_type or "").strip().lower()
        normalized_sha256 = str(sha256 or "").strip().lower()
        normalized_engine = str(scan_engine or "").strip().lower() or "local_heuristics"
        normalized_result = str(scan_result or "").strip().lower() or "clean"
        size = max(0, int(size_bytes or 0))
        if (
            not normalized_original
            or not normalized_stored
            or not normalized_rel_path
            or not normalized_mime
            or not normalized_sha256
            or size <= 0
        ):
            return None

        details_json = ""
        if scan_details is not None:
            try:
                details_json = json.dumps(scan_details, ensure_ascii=True, sort_keys=True)
            except Exception:
                details_json = json.dumps({"raw": str(scan_details)}, ensure_ascii=True)
        created_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO support_ticket_attachments (
                        ticket_ref,
                        created_at_utc,
                        original_filename,
                        stored_filename,
                        storage_rel_path,
                        mime_type,
                        size_bytes,
                        sha256,
                        scan_engine,
                        scan_result,
                        scan_details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_ref,
                        created_at_utc,
                        normalized_original,
                        normalized_stored,
                        normalized_rel_path,
                        normalized_mime,
                        size,
                        normalized_sha256,
                        normalized_engine,
                        normalized_result,
                        details_json,
                    ),
                )
                attachment_id = int(cursor.lastrowid or 0)
                conn.commit()
                row = conn.execute(
                    """
                    SELECT id, ticket_ref, created_at_utc, original_filename, stored_filename, storage_rel_path,
                           mime_type, size_bytes, sha256, scan_engine, scan_result, scan_details_json
                    FROM support_ticket_attachments
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (attachment_id,),
                ).fetchone()
        return self._row_to_attachment(row) if row else None

    def list_ticket_attachments(self, *, ticket_ref: str, limit: int = 50) -> List[Dict[str, Any]]:
        normalized_ref = str(ticket_ref or "").strip()
        if not normalized_ref:
            return []
        limit = max(1, min(int(limit), 500))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, ticket_ref, created_at_utc, original_filename, stored_filename, storage_rel_path,
                           mime_type, size_bytes, sha256, scan_engine, scan_result, scan_details_json
                    FROM support_ticket_attachments
                    WHERE ticket_ref = ?
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (normalized_ref, limit),
                ).fetchall()
        return [self._row_to_attachment(row) for row in rows]

    def get_ticket_attachment_by_id(self, *, attachment_id: int) -> Optional[Dict[str, Any]]:
        normalized_id = int(attachment_id or 0)
        if normalized_id <= 0:
            return None
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, ticket_ref, created_at_utc, original_filename, stored_filename, storage_rel_path,
                           mime_type, size_bytes, sha256, scan_engine, scan_result, scan_details_json
                    FROM support_ticket_attachments
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (normalized_id,),
                ).fetchone()
        return self._row_to_attachment(row) if row else None

    def list_in_progress_pending_reply_tickets(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                      t.id,
                      t.ticket_ref,
                      t.created_at_utc,
                      t.customer_email,
                      t.submitter_user_id,
                      t.is_authenticated_submitter,
                      t.subject,
                      t.message,
                      t.category,
                      t.bug_surface,
                      t.bug_severity,
                      t.bug_reproducible,
                      t.payment_txid,
                      t.payment_chain,
                      t.confidence,
                      t.status
                    FROM support_tickets t
                    LEFT JOIN (
                      SELECT m1.ticket_ref, m1.author_type
                      FROM support_ticket_messages m1
                      INNER JOIN (
                        SELECT ticket_ref, MAX(id) AS max_id
                        FROM support_ticket_messages
                        GROUP BY ticket_ref
                      ) latest
                        ON latest.ticket_ref = m1.ticket_ref AND latest.max_id = m1.id
                    ) m ON m.ticket_ref = t.ticket_ref
                    WHERE lower(t.status) = 'in_progress'
                      AND lower(COALESCE(m.author_type, 'customer')) = 'customer'
                    ORDER BY t.id ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._row_to_ticket(row) for row in rows]

    def check_and_record_rate_limit(
        self,
        *,
        client_ip: str,
        customer_email: str,
        ip_per_5m: int,
        email_per_5m: int,
        ip_per_hour: int,
        email_per_hour: int,
    ) -> Dict[str, Any]:
        now = int(time.time())
        window_5m_start = now - 300
        window_hour_start = now - 3600

        normalized_ip = (client_ip or "").strip() or "unknown"
        normalized_email = (customer_email or "").strip().lower()

        with self._lock:
            with self._connect() as conn:
                # Keep table bounded; no need to retain stale rate window events.
                conn.execute("DELETE FROM support_ticket_rate_events WHERE created_at_epoch < ?", (now - 7200,))

                ip_5m = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM support_ticket_rate_events
                    WHERE client_ip = ? AND created_at_epoch >= ?
                    """,
                    (normalized_ip, window_5m_start),
                ).fetchone()["c"]
                email_5m = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM support_ticket_rate_events
                    WHERE customer_email = ? AND created_at_epoch >= ?
                    """,
                    (normalized_email, window_5m_start),
                ).fetchone()["c"]
                ip_hour = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM support_ticket_rate_events
                    WHERE client_ip = ? AND created_at_epoch >= ?
                    """,
                    (normalized_ip, window_hour_start),
                ).fetchone()["c"]
                email_hour = conn.execute(
                    """
                    SELECT COUNT(*) AS c FROM support_ticket_rate_events
                    WHERE customer_email = ? AND created_at_epoch >= ?
                    """,
                    (normalized_email, window_hour_start),
                ).fetchone()["c"]

                if ip_5m >= int(ip_per_5m) or email_5m >= int(email_per_5m):
                    return {
                        "allowed": False,
                        "reason": "burst_limit",
                        "retry_after_seconds": 300,
                    }
                if ip_hour >= int(ip_per_hour) or email_hour >= int(email_per_hour):
                    return {
                        "allowed": False,
                        "reason": "hourly_limit",
                        "retry_after_seconds": 3600,
                    }

                conn.execute(
                    """
                    INSERT INTO support_ticket_rate_events (created_at_epoch, client_ip, customer_email)
                    VALUES (?, ?, ?)
                    """,
                    (now, normalized_ip, normalized_email),
                )
                conn.commit()

        return {"allowed": True}
