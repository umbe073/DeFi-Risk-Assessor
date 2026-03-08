"""SQLite persistence for checkout sessions, subscriptions, and webhook events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import secrets
import sqlite3
from threading import Lock
from typing import Any, Dict, List, Optional

from .special_accounts import (
    SPECIAL_ENTERPRISE_PLAN_ID,
    SPECIAL_ENTERPRISE_PLAN_NAME,
    SPECIAL_ENTERPRISE_SCANS_PER_DAY,
)


FINAL_PAYMENT_STATUSES = {"finished", "confirmed"}
FAILED_OR_CANCELLED_PAYMENT_STATUSES = {"failed", "expired", "refunded", "cancelled", "canceled"}
PARTIAL_PAYMENT_STATUSES = {"partially_paid", "partially-paid", "partially paid"}
RECONCILIATION_ISSUE_TYPES = {
    "finalized_without_subscription",
    "orphan_webhooks",
    "orphan_subscriptions",
    "stale_waiting_sessions",
}
RECONCILIATION_ACTION_TYPES = {
    "reapply_webhook",
    "manual_activate_subscription",
    "close_false_positive",
}
PAY_CURRENCY_ALIASES = {
    "usdcerc20": "usdc",
}


def build_partial_payment_support_code(
    *,
    order_id: str = "",
    nowpayments_payment_id: str = "",
    nowpayments_invoice_id: str = "",
) -> str:
    seed = "|".join(
        [
            str(order_id or "").strip(),
            str(nowpayments_payment_id or "").strip(),
            str(nowpayments_invoice_id or "").strip(),
        ]
    )
    if not seed.strip():
        seed = str(order_id or "").strip()
    if not seed.strip():
        return ""
    return f"HSP-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12].upper()}"


def _normalize_currency_code(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    return PAY_CURRENCY_ALIASES.get(normalized, normalized)


def _currency_label(code: str) -> str:
    normalized = _normalize_currency_code(code)
    if not normalized:
        return ""
    if normalized == "usdttrc20":
        return "USDT (TRC-20)"
    if normalized == "usdc":
        return "USDC (ERC-20)"
    if normalized == "usdterc20":
        return "USDT (ERC-20)"
    return normalized.upper()


class BillingStore:
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
    def _now_utc() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _plus_days_utc(days: int) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=max(1, int(days)))).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _safe_amount(value: Any) -> float:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return 0.0
        if amount < 0:
            return 0.0
        return round(amount, 8)

    @staticmethod
    def _partial_support_code(session_row: Dict[str, Any]) -> str:
        return build_partial_payment_support_code(
            order_id=str(session_row.get("order_id", "")).strip(),
            nowpayments_payment_id=str(session_row.get("nowpayments_payment_id", "")).strip(),
            nowpayments_invoice_id=str(session_row.get("nowpayments_invoice_id", "")).strip(),
        )

    def _build_partial_payment_row(self, session_row: Dict[str, Any]) -> Dict[str, Any] | None:
        status = str(session_row.get("status", "")).strip().lower()
        if status not in PARTIAL_PAYMENT_STATUSES:
            return None

        payload_raw = str(session_row.get("provider_payload_json", "") or "").strip()
        payload: Dict[str, Any] = {}
        if payload_raw:
            try:
                decoded = json.loads(payload_raw)
                if isinstance(decoded, dict):
                    payload = decoded
            except json.JSONDecodeError:
                payload = {}

        total_amount = self._safe_amount(session_row.get("amount_value"))
        if total_amount <= 0:
            total_amount = self._safe_amount(payload.get("price_amount") or payload.get("invoice_total_sum"))

        paid_candidates = [
            payload.get("actually_paid_at_fiat"),
            payload.get("actually_paid"),
            payload.get("outcome_amount"),
            payload.get("pay_amount"),
            payload.get("paid_amount"),
            payload.get("amount_paid"),
        ]
        paid_amount = 0.0
        for candidate in paid_candidates:
            maybe = self._safe_amount(candidate)
            if maybe > 0:
                paid_amount = maybe
                break

        if paid_amount <= 0 and total_amount > 0:
            paid_amount = min(total_amount, self._safe_amount(payload.get("pay_amount_usd")))

        remaining_amount = max(0.0, round(total_amount - paid_amount, 8))
        currency = str(session_row.get("price_currency") or payload.get("price_currency") or "USD").strip().upper() or "USD"
        support_code = self._partial_support_code(session_row)

        partial_row = dict(session_row)
        partial_row["manual_support_code"] = support_code
        partial_row["partial_total_amount"] = round(total_amount, 8)
        partial_row["partial_paid_amount"] = round(paid_amount, 8)
        partial_row["partial_remaining_amount"] = remaining_amount
        partial_row["partial_price_currency"] = currency
        return partial_row

    @staticmethod
    def _reconciliation_issue_key_for_row(issue_type: str, row: Dict[str, Any]) -> str:
        normalized_issue_type = str(issue_type or "").strip().lower()
        order_id = str(row.get("order_id") or "").strip()
        event_id = str(row.get("event_id") or "").strip()
        user_id = int(row.get("user_id") or 0)
        user_email = str(row.get("user_email") or "").strip().lower()

        if normalized_issue_type in {"finalized_without_subscription", "stale_waiting_sessions"}:
            if order_id:
                return f"order:{order_id}"
        elif normalized_issue_type == "orphan_webhooks":
            if event_id:
                return f"event:{event_id}"
            if order_id:
                return f"order:{order_id}"
        elif normalized_issue_type == "orphan_subscriptions":
            if order_id:
                return f"order:{order_id}"
            if user_id > 0:
                return f"user:{user_id}"
            if user_email:
                return f"email:{user_email}"

        if order_id:
            return f"order:{order_id}"
        if event_id:
            return f"event:{event_id}"
        if user_id > 0:
            return f"user:{user_id}"
        return f"raw:{normalized_issue_type or 'unknown'}:{user_email or 'unknown'}"

    def _list_closed_reconciliation_issue_keys(self) -> set[tuple[str, str]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT issue_type, issue_key
                    FROM billing_reconciliation_actions
                    WHERE action_type = 'close_false_positive'
                    """
                ).fetchall()
        closed = set()
        for row in rows:
            issue_type = str(row["issue_type"] or "").strip().lower()
            issue_key = str(row["issue_key"] or "").strip()
            if issue_type and issue_key:
                closed.add((issue_type, issue_key))
        return closed

    def record_reconciliation_action(
        self,
        *,
        action_type: str,
        issue_type: str,
        issue_key: str,
        actor_user_id: int,
        actor_email: str,
        reason: str,
        result_status: str,
        order_id: str = "",
        event_id: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_action_type = str(action_type or "").strip().lower()
        if normalized_action_type not in RECONCILIATION_ACTION_TYPES:
            raise ValueError("invalid action_type")
        normalized_issue_type = str(issue_type or "").strip().lower()
        if normalized_issue_type not in RECONCILIATION_ISSUE_TYPES:
            raise ValueError("invalid issue_type")
        normalized_issue_key = str(issue_key or "").strip()
        if not normalized_issue_key:
            raise ValueError("issue_key is required")
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise ValueError("reason is required")
        normalized_result_status = str(result_status or "").strip().lower() or "unknown"
        normalized_actor_email = str(actor_email or "").strip().lower()
        if int(actor_user_id) <= 0 or not normalized_actor_email:
            raise ValueError("actor identity is required")

        now_utc = self._now_utc()
        payload_json = json.dumps(details or {}, ensure_ascii=True, sort_keys=True)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO billing_reconciliation_actions (
                        action_type, issue_type, issue_key, order_id, event_id, actor_user_id,
                        actor_email, reason, result_status, details_json, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_action_type,
                        normalized_issue_type,
                        normalized_issue_key,
                        str(order_id or "").strip() or None,
                        str(event_id or "").strip() or None,
                        int(actor_user_id),
                        normalized_actor_email,
                        normalized_reason,
                        normalized_result_status,
                        payload_json,
                        now_utc,
                    ),
                )
                conn.commit()
        return {
            "id": int(cursor.lastrowid),
            "action_type": normalized_action_type,
            "issue_type": normalized_issue_type,
            "issue_key": normalized_issue_key,
            "order_id": str(order_id or "").strip(),
            "event_id": str(event_id or "").strip(),
            "actor_user_id": int(actor_user_id),
            "actor_email": normalized_actor_email,
            "reason": normalized_reason,
            "result_status": normalized_result_status,
            "details": details or {},
            "created_at_utc": now_utc,
        }

    def list_reconciliation_actions(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 1000))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, action_type, issue_type, issue_key, order_id, event_id, actor_user_id,
                           actor_email, reason, result_status, details_json, created_at_utc
                    FROM billing_reconciliation_actions
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (normalized_limit,),
                ).fetchall()
        actions: list[dict[str, Any]] = []
        for row in rows:
            raw_details = str(row["details_json"] or "").strip()
            details: Dict[str, Any] = {}
            if raw_details:
                try:
                    parsed = json.loads(raw_details)
                    if isinstance(parsed, dict):
                        details = parsed
                except json.JSONDecodeError:
                    details = {}
            actions.append(
                {
                    "id": int(row["id"]),
                    "action_type": str(row["action_type"] or "").strip().lower(),
                    "issue_type": str(row["issue_type"] or "").strip().lower(),
                    "issue_key": str(row["issue_key"] or "").strip(),
                    "order_id": str(row["order_id"] or "").strip(),
                    "event_id": str(row["event_id"] or "").strip(),
                    "actor_user_id": int(row["actor_user_id"] or 0),
                    "actor_email": str(row["actor_email"] or "").strip().lower(),
                    "reason": str(row["reason"] or "").strip(),
                    "result_status": str(row["result_status"] or "").strip().lower(),
                    "details": details,
                    "created_at_utc": str(row["created_at_utc"] or "").strip(),
                }
            )
        return actions

    def _ensure_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_checkout_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        user_email TEXT NOT NULL,
                        plan_id TEXT NOT NULL,
                        plan_name TEXT NOT NULL,
                        scans_per_day INTEGER NOT NULL DEFAULT 0,
                        duration_days INTEGER NOT NULL DEFAULT 30,
                        amount_value REAL NOT NULL,
                        price_currency TEXT NOT NULL DEFAULT 'USD',
                        pay_currency TEXT NOT NULL,
                        order_id TEXT NOT NULL UNIQUE,
                        enterprise_code TEXT,
                        nowpayments_payment_id TEXT,
                        nowpayments_invoice_id TEXT,
                        invoice_url TEXT,
                        status TEXT NOT NULL,
                        paid_at_utc TEXT,
                        provider_payload_json TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_billing_checkout_user_created ON billing_checkout_sessions(user_id, created_at_utc)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_billing_checkout_order ON billing_checkout_sessions(order_id)"
                )

                # Migration from old schema used earlier in this project.
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(billing_checkout_sessions)").fetchall()}
                if "amount_value" not in columns and "amount_usd" in columns:
                    conn.execute("ALTER TABLE billing_checkout_sessions ADD COLUMN amount_value REAL")
                    conn.execute("UPDATE billing_checkout_sessions SET amount_value = amount_usd WHERE amount_value IS NULL")
                if "price_currency" not in columns:
                    conn.execute("ALTER TABLE billing_checkout_sessions ADD COLUMN price_currency TEXT NOT NULL DEFAULT 'USD'")
                if "plan_name" not in columns:
                    conn.execute("ALTER TABLE billing_checkout_sessions ADD COLUMN plan_name TEXT NOT NULL DEFAULT 'Plan'")
                if "scans_per_day" not in columns:
                    conn.execute("ALTER TABLE billing_checkout_sessions ADD COLUMN scans_per_day INTEGER NOT NULL DEFAULT 0")
                if "duration_days" not in columns:
                    conn.execute("ALTER TABLE billing_checkout_sessions ADD COLUMN duration_days INTEGER NOT NULL DEFAULT 30")
                if "enterprise_code" not in columns:
                    conn.execute("ALTER TABLE billing_checkout_sessions ADD COLUMN enterprise_code TEXT")

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_webhook_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        signature TEXT,
                        UNIQUE(provider, event_id)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_billing_webhooks_created ON billing_webhook_events(created_at_utc)"
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_currency_capabilities (
                        code TEXT PRIMARY KEY,
                        label TEXT NOT NULL,
                        is_enabled INTEGER NOT NULL DEFAULT 1,
                        is_detected INTEGER NOT NULL DEFAULT 0,
                        source TEXT NOT NULL DEFAULT 'sync',
                        updated_at_utc TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_billing_currency_enabled ON billing_currency_capabilities(is_enabled, code)"
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_user_subscriptions (
                        user_id INTEGER PRIMARY KEY,
                        user_email TEXT NOT NULL,
                        plan_id TEXT NOT NULL,
                        plan_name TEXT NOT NULL,
                        scans_per_day INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        amount_value REAL NOT NULL,
                        price_currency TEXT NOT NULL,
                        source TEXT NOT NULL,
                        order_id TEXT,
                        enterprise_code TEXT,
                        started_at_utc TEXT NOT NULL,
                        expires_at_utc TEXT,
                        updated_at_utc TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_billing_user_subscriptions_status ON billing_user_subscriptions(status, expires_at_utc)"
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_free_trial_claims (
                        user_id INTEGER PRIMARY KEY,
                        user_email TEXT NOT NULL,
                        claimed_at_utc TEXT NOT NULL
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_enterprise_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL UNIQUE,
                        created_at_utc TEXT NOT NULL,
                        created_by_user_id INTEGER NOT NULL,
                        created_by_email TEXT NOT NULL,
                        amount_value REAL NOT NULL,
                        price_currency TEXT NOT NULL DEFAULT 'EUR',
                        scans_per_day INTEGER NOT NULL,
                        duration_days INTEGER NOT NULL,
                        valid_until_utc TEXT NOT NULL,
                        note TEXT,
                        status TEXT NOT NULL DEFAULT 'active',
                        reserved_at_utc TEXT,
                        reserved_by_user_id INTEGER,
                        reserved_by_email TEXT,
                        reserved_order_id TEXT,
                        redeemed_at_utc TEXT,
                        redeemed_by_user_id INTEGER,
                        redeemed_by_email TEXT,
                        redeemed_order_id TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_billing_enterprise_codes_status ON billing_enterprise_codes(status, valid_until_utc)"
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS billing_reconciliation_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action_type TEXT NOT NULL,
                        issue_type TEXT NOT NULL,
                        issue_key TEXT NOT NULL,
                        order_id TEXT,
                        event_id TEXT,
                        actor_user_id INTEGER NOT NULL,
                        actor_email TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        result_status TEXT NOT NULL,
                        details_json TEXT NOT NULL DEFAULT '{}',
                        created_at_utc TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_billing_reconciliation_actions_created
                    ON billing_reconciliation_actions(created_at_utc)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_billing_reconciliation_actions_issue
                    ON billing_reconciliation_actions(issue_type, issue_key, created_at_utc)
                    """
                )

                now_utc = self._now_utc()
                conn.execute(
                    """
                    UPDATE billing_enterprise_codes
                    SET status = 'expired'
                    WHERE status IN ('active', 'reserved')
                      AND valid_until_utc < ?
                    """,
                    (now_utc,),
                )

                retention_cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute("DELETE FROM billing_webhook_events WHERE created_at_utc < ?", (retention_cutoff,))
                conn.commit()

    def create_checkout_session(
        self,
        *,
        user_id: int,
        user_email: str,
        plan_id: str,
        plan_name: str,
        scans_per_day: int,
        duration_days: int,
        amount_value: float,
        price_currency: str,
        pay_currency: str,
        order_id: str,
        checkout: Dict[str, Any],
        enterprise_code: str = "",
    ) -> Dict[str, Any]:
        created_at_utc = self._now_utc()
        payload_json = json.dumps(checkout, ensure_ascii=True, sort_keys=True)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO billing_checkout_sessions (
                        created_at_utc, updated_at_utc, user_id, user_email, plan_id, plan_name, scans_per_day,
                        duration_days, amount_value, price_currency, pay_currency, order_id, enterprise_code,
                        nowpayments_payment_id, nowpayments_invoice_id, invoice_url, status, paid_at_utc,
                        provider_payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (
                        created_at_utc,
                        created_at_utc,
                        int(user_id),
                        str(user_email).strip().lower(),
                        str(plan_id).strip(),
                        str(plan_name).strip(),
                        max(0, int(scans_per_day)),
                        max(1, int(duration_days)),
                        float(amount_value),
                        str(price_currency).strip().upper(),
                        str(pay_currency).strip().lower(),
                        str(order_id).strip(),
                        str(enterprise_code).strip().upper() or None,
                        str(checkout.get("payment_id", "")).strip() or None,
                        str(checkout.get("invoice_id", "")).strip() or None,
                        str(checkout.get("invoice_url", "")).strip() or None,
                        str(checkout.get("status", "waiting")).strip().lower() or "waiting",
                        payload_json,
                    ),
                )
                conn.commit()
        return {
            "created_at_utc": created_at_utc,
            "user_id": int(user_id),
            "user_email": str(user_email).strip().lower(),
            "plan_id": str(plan_id).strip(),
            "plan_name": str(plan_name).strip(),
            "scans_per_day": max(0, int(scans_per_day)),
            "duration_days": max(1, int(duration_days)),
            "amount_value": float(amount_value),
            "price_currency": str(price_currency).strip().upper(),
            "pay_currency": str(pay_currency).strip().lower(),
            "order_id": str(order_id).strip(),
            "enterprise_code": str(enterprise_code).strip().upper(),
            "payment_id": str(checkout.get("payment_id", "")).strip(),
            "invoice_id": str(checkout.get("invoice_id", "")).strip(),
            "invoice_url": str(checkout.get("invoice_url", "")).strip(),
            "status": str(checkout.get("status", "waiting")).strip().lower() or "waiting",
        }

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
                    FROM billing_webhook_events
                    WHERE provider = ? AND event_id = ?
                    LIMIT 1
                    """,
                    (normalized_provider, normalized_event_id),
                ).fetchone()
        return bool(row)

    def record_webhook_event(self, *, provider: str, event_id: str, payload: Dict[str, Any], signature: str = "") -> bool:
        normalized_provider = str(provider or "").strip().lower()
        normalized_event_id = str(event_id or "").strip()
        if not normalized_provider or not normalized_event_id:
            return False
        created_at_utc = self._now_utc()
        payload_json = json.dumps(payload or {}, ensure_ascii=True, sort_keys=True)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO billing_webhook_events (
                        provider, event_id, created_at_utc, payload_json, signature
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (normalized_provider, normalized_event_id, created_at_utc, payload_json, str(signature or "").strip()),
                )
                conn.commit()
                return int(cursor.rowcount) > 0

    def apply_nowpayments_webhook(self, *, payload: Dict[str, Any]) -> Dict[str, Any]:
        order_id = str(payload.get("order_id") or "").strip()
        if not order_id:
            return {"matched_order": False, "status": "missing_order"}

        status_raw = str(payload.get("payment_status") or payload.get("invoice_status") or "unknown").strip().lower()
        paid_at_utc = self._now_utc() if status_raw in FINAL_PAYMENT_STATUSES else None

        payment_id = str(payload.get("payment_id") or "").strip()
        invoice_id = str(payload.get("invoice_id") or payload.get("id") or "").strip()
        invoice_url = str(payload.get("invoice_url") or payload.get("invoice_link") or "").strip()
        payload_json = json.dumps(payload or {}, ensure_ascii=True, sort_keys=True)
        now_utc = self._now_utc()

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, user_id, user_email, plan_id, plan_name, scans_per_day, duration_days,
                           amount_value, price_currency, enterprise_code, paid_at_utc
                    FROM billing_checkout_sessions
                    WHERE order_id = ?
                    LIMIT 1
                    """,
                    (order_id,),
                ).fetchone()
                if not row:
                    return {"matched_order": False, "status": status_raw}

                existing_paid = str(row["paid_at_utc"] or "").strip()
                conn.execute(
                    """
                    UPDATE billing_checkout_sessions
                    SET updated_at_utc = ?,
                        nowpayments_payment_id = COALESCE(NULLIF(?, ''), nowpayments_payment_id),
                        nowpayments_invoice_id = COALESCE(NULLIF(?, ''), nowpayments_invoice_id),
                        invoice_url = COALESCE(NULLIF(?, ''), invoice_url),
                        status = ?,
                        paid_at_utc = ?,
                        provider_payload_json = ?
                    WHERE order_id = ?
                    """,
                    (
                        now_utc,
                        payment_id,
                        invoice_id,
                        invoice_url,
                        status_raw,
                        existing_paid or paid_at_utc,
                        payload_json,
                        order_id,
                    ),
                )

                activated = False
                if status_raw in FINAL_PAYMENT_STATUSES:
                    starts_at = existing_paid or paid_at_utc or now_utc
                    expires_at = (
                        datetime.strptime(starts_at, "%Y-%m-%dT%H:%M:%SZ") + timedelta(days=max(1, int(row["duration_days"])))
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    conn.execute(
                        """
                        INSERT INTO billing_user_subscriptions (
                            user_id, user_email, plan_id, plan_name, scans_per_day, status, amount_value,
                            price_currency, source, order_id, enterprise_code, started_at_utc, expires_at_utc, updated_at_utc
                        ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, 'nowpayments', ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            user_email=excluded.user_email,
                            plan_id=excluded.plan_id,
                            plan_name=excluded.plan_name,
                            scans_per_day=excluded.scans_per_day,
                            status='active',
                            amount_value=excluded.amount_value,
                            price_currency=excluded.price_currency,
                            source='nowpayments',
                            order_id=excluded.order_id,
                            enterprise_code=excluded.enterprise_code,
                            started_at_utc=excluded.started_at_utc,
                            expires_at_utc=excluded.expires_at_utc,
                            updated_at_utc=excluded.updated_at_utc
                        """,
                        (
                            int(row["user_id"]),
                            str(row["user_email"]).strip().lower(),
                            str(row["plan_id"]).strip(),
                            str(row["plan_name"]).strip(),
                            max(0, int(row["scans_per_day"] or 0)),
                            float(row["amount_value"] or 0),
                            str(row["price_currency"] or "USD").strip().upper(),
                            order_id,
                            str(row["enterprise_code"] or "").strip().upper() or None,
                            starts_at,
                            expires_at,
                            now_utc,
                        ),
                    )
                    enterprise_code = str(row["enterprise_code"] or "").strip().upper()
                    if enterprise_code:
                        conn.execute(
                            """
                            UPDATE billing_enterprise_codes
                            SET status = 'redeemed',
                                redeemed_at_utc = ?,
                                redeemed_by_user_id = ?,
                                redeemed_by_email = ?,
                                redeemed_order_id = ?
                            WHERE code = ?
                            """,
                            (now_utc, int(row["user_id"]), str(row["user_email"]).strip().lower(), order_id, enterprise_code),
                        )
                    activated = True
                elif status_raw in FAILED_OR_CANCELLED_PAYMENT_STATUSES:
                    enterprise_code = str(row["enterprise_code"] or "").strip().upper()
                    if enterprise_code:
                        conn.execute(
                            """
                            UPDATE billing_enterprise_codes
                            SET status = 'active',
                                reserved_at_utc = NULL,
                                reserved_by_user_id = NULL,
                                reserved_by_email = NULL,
                                reserved_order_id = NULL
                            WHERE code = ?
                              AND status = 'reserved'
                              AND reserved_order_id = ?
                              AND (redeemed_at_utc IS NULL OR redeemed_at_utc = '')
                            """,
                            (enterprise_code, order_id),
                        )
                conn.commit()
                return {"matched_order": True, "status": status_raw, "subscription_activated": activated}

    def reapply_nowpayments_webhook_event(self, *, event_id: str) -> Dict[str, Any]:
        normalized_event_id = str(event_id or "").strip()
        if not normalized_event_id:
            return {"ok": False, "error": "missing_event_id"}
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT payload_json
                    FROM billing_webhook_events
                    WHERE provider = 'nowpayments' AND event_id = ?
                    LIMIT 1
                    """,
                    (normalized_event_id,),
                ).fetchone()
        if not row:
            return {"ok": False, "error": "event_not_found", "event_id": normalized_event_id}

        payload_raw = str(row["payload_json"] or "").strip()
        try:
            payload = json.loads(payload_raw) if payload_raw else {}
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}

        apply_result = self.apply_nowpayments_webhook(payload=payload)
        order_id = str(payload.get("order_id") or "").strip()
        return {
            "ok": bool(apply_result.get("matched_order")),
            "event_id": normalized_event_id,
            "order_id": order_id,
            "apply_result": apply_result,
        }

    def reapply_nowpayments_webhook_for_order(self, *, order_id: str) -> Dict[str, Any]:
        normalized_order_id = str(order_id or "").strip()
        if not normalized_order_id:
            return {"ok": False, "error": "missing_order_id"}
        recent_events = self.list_webhook_events(provider="nowpayments", limit=1000)
        for event in recent_events:
            if str(event.get("order_id") or "").strip() != normalized_order_id:
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            apply_result = self.apply_nowpayments_webhook(payload=payload)
            return {
                "ok": bool(apply_result.get("matched_order")),
                "order_id": normalized_order_id,
                "event_id": str(event.get("event_id") or "").strip(),
                "apply_result": apply_result,
            }
        return {"ok": False, "error": "webhook_not_found", "order_id": normalized_order_id}

    def manual_activate_subscription_for_order(self, *, order_id: str, source: str = "manual_repair") -> Dict[str, Any]:
        normalized_order_id = str(order_id or "").strip()
        if not normalized_order_id:
            return {"ok": False, "error": "missing_order_id"}

        now_utc = self._now_utc()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT user_id, user_email, plan_id, plan_name, scans_per_day, duration_days,
                           amount_value, price_currency, enterprise_code, status, paid_at_utc
                    FROM billing_checkout_sessions
                    WHERE order_id = ?
                    LIMIT 1
                    """,
                    (normalized_order_id,),
                ).fetchone()
                if not row:
                    return {"ok": False, "error": "order_not_found", "order_id": normalized_order_id}

                started_at = str(row["paid_at_utc"] or "").strip() or now_utc
                try:
                    started_dt = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except ValueError:
                    started_dt = datetime.now(timezone.utc)
                    started_at = started_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                expires_at = (started_dt + timedelta(days=max(1, int(row["duration_days"] or 30)))).strftime("%Y-%m-%dT%H:%M:%SZ")
                previous_status = str(row["status"] or "").strip().lower()

                conn.execute(
                    """
                    INSERT INTO billing_user_subscriptions (
                        user_id, user_email, plan_id, plan_name, scans_per_day, status, amount_value,
                        price_currency, source, order_id, enterprise_code, started_at_utc, expires_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        user_email=excluded.user_email,
                        plan_id=excluded.plan_id,
                        plan_name=excluded.plan_name,
                        scans_per_day=excluded.scans_per_day,
                        status='active',
                        amount_value=excluded.amount_value,
                        price_currency=excluded.price_currency,
                        source=excluded.source,
                        order_id=excluded.order_id,
                        enterprise_code=excluded.enterprise_code,
                        started_at_utc=excluded.started_at_utc,
                        expires_at_utc=excluded.expires_at_utc,
                        updated_at_utc=excluded.updated_at_utc
                    """,
                    (
                        int(row["user_id"]),
                        str(row["user_email"]).strip().lower(),
                        str(row["plan_id"]).strip(),
                        str(row["plan_name"]).strip(),
                        max(0, int(row["scans_per_day"] or 0)),
                        float(row["amount_value"] or 0),
                        str(row["price_currency"] or "USD").strip().upper(),
                        str(source or "manual_repair").strip(),
                        normalized_order_id,
                        str(row["enterprise_code"] or "").strip().upper() or None,
                        started_at,
                        expires_at,
                        now_utc,
                    ),
                )

                enterprise_code = str(row["enterprise_code"] or "").strip().upper()
                if enterprise_code:
                    conn.execute(
                        """
                        UPDATE billing_enterprise_codes
                        SET status = 'redeemed',
                            redeemed_at_utc = ?,
                            redeemed_by_user_id = ?,
                            redeemed_by_email = ?,
                            redeemed_order_id = ?
                        WHERE code = ?
                        """,
                        (
                            now_utc,
                            int(row["user_id"]),
                            str(row["user_email"]).strip().lower(),
                            normalized_order_id,
                            enterprise_code,
                        ),
                    )

                conn.commit()

        return {
            "ok": True,
            "order_id": normalized_order_id,
            "user_id": int(row["user_id"]),
            "status_before": previous_status,
            "forced": previous_status not in FINAL_PAYMENT_STATUSES,
        }

    def create_enterprise_code(
        self,
        *,
        created_by_user_id: int,
        created_by_email: str,
        amount_value: float,
        scans_per_day: int,
        duration_days: int,
        valid_days: int,
        note: str = "",
        price_currency: str = "EUR",
    ) -> Dict[str, Any]:
        amount_value = round(float(amount_value), 2)
        if amount_value <= 0:
            raise ValueError("amount must be positive")
        scans_per_day = max(1, int(scans_per_day))
        duration_days = max(1, int(duration_days))
        valid_days = max(1, int(valid_days))
        created_at_utc = self._now_utc()
        valid_until_utc = self._plus_days_utc(valid_days)
        created_by_email = str(created_by_email or "").strip().lower()
        note = str(note or "").strip()
        price_currency = str(price_currency or "EUR").strip().upper() or "EUR"

        with self._lock:
            with self._connect() as conn:
                for _ in range(10):
                    code = f"HS-ENT-{secrets.token_hex(4).upper()}"
                    try:
                        cursor = conn.execute(
                            """
                            INSERT INTO billing_enterprise_codes (
                                code, created_at_utc, created_by_user_id, created_by_email, amount_value,
                                price_currency, scans_per_day, duration_days, valid_until_utc, note, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                            """,
                            (
                                code,
                                created_at_utc,
                                int(created_by_user_id),
                                created_by_email,
                                amount_value,
                                price_currency,
                                scans_per_day,
                                duration_days,
                                valid_until_utc,
                                note,
                            ),
                        )
                        conn.commit()
                        record_id = int(cursor.lastrowid or 0)
                        return {
                            "id": record_id,
                            "code": code,
                            "created_at_utc": created_at_utc,
                            "created_by_user_id": int(created_by_user_id),
                            "created_by_email": created_by_email,
                            "amount_value": amount_value,
                            "price_currency": price_currency,
                            "scans_per_day": scans_per_day,
                            "duration_days": duration_days,
                            "valid_until_utc": valid_until_utc,
                            "note": note,
                            "status": "active",
                        }
                    except sqlite3.IntegrityError:
                        continue
        raise ValueError("unable to generate unique enterprise code")

    def reserve_enterprise_code(self, *, code: str, user_id: int, user_email: str, order_id: str) -> Optional[Dict[str, Any]]:
        normalized_code = str(code or "").strip().upper()
        if not normalized_code:
            return None
        now_utc = self._now_utc()
        user_email = str(user_email or "").strip().lower()
        order_id = str(order_id or "").strip()
        if not order_id:
            return None

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, code, amount_value, price_currency, scans_per_day, duration_days, valid_until_utc, status,
                           reserved_by_user_id, reserved_by_email, reserved_at_utc, reserved_order_id, redeemed_at_utc
                    FROM billing_enterprise_codes
                    WHERE code = ?
                    LIMIT 1
                    """,
                    (normalized_code,),
                ).fetchone()
                if not row:
                    return None

                if str(row["valid_until_utc"]) < now_utc:
                    conn.execute(
                        "UPDATE billing_enterprise_codes SET status = 'expired' WHERE id = ?",
                        (int(row["id"]),),
                    )
                    conn.commit()
                    return None

                status = str(row["status"]).strip().lower()
                if status in {"redeemed", "expired"}:
                    return None

                if status == "reserved":
                    reserved_by_user_id = int(row["reserved_by_user_id"] or 0)
                    if reserved_by_user_id == int(user_id):
                        conn.execute(
                            """
                            UPDATE billing_enterprise_codes
                            SET reserved_at_utc = ?,
                                reserved_by_email = ?,
                                reserved_order_id = ?
                            WHERE id = ?
                              AND status = 'reserved'
                            """,
                            (now_utc, user_email, order_id, int(row["id"])),
                        )
                        conn.commit()
                        return {
                            "code": normalized_code,
                            "amount_value": float(row["amount_value"]),
                            "price_currency": str(row["price_currency"]).strip().upper(),
                            "scans_per_day": int(row["scans_per_day"] or 0),
                            "duration_days": int(row["duration_days"] or 30),
                            "valid_until_utc": str(row["valid_until_utc"]),
                        }

                    reserved_order_id = str(row["reserved_order_id"] or "").strip()
                    reclaimable = False
                    if not reserved_order_id:
                        reclaimable = True
                    else:
                        session_row = conn.execute(
                            "SELECT status FROM billing_checkout_sessions WHERE order_id = ? LIMIT 1",
                            (reserved_order_id,),
                        ).fetchone()
                        if not session_row:
                            reclaimable = True
                        else:
                            reserved_status = str(session_row["status"] or "").strip().lower()
                            if reserved_status in FAILED_OR_CANCELLED_PAYMENT_STATUSES:
                                reclaimable = True

                    if not reclaimable:
                        return None

                    conn.execute(
                        """
                        UPDATE billing_enterprise_codes
                        SET status = 'active',
                            reserved_at_utc = NULL,
                            reserved_by_user_id = NULL,
                            reserved_by_email = NULL,
                            reserved_order_id = NULL
                        WHERE id = ?
                          AND status = 'reserved'
                          AND (redeemed_at_utc IS NULL OR redeemed_at_utc = '')
                        """,
                        (int(row["id"]),),
                    )
                    conn.commit()
                    status = "active"

                if status != "active":
                    return None

                cursor = conn.execute(
                    """
                    UPDATE billing_enterprise_codes
                    SET status = 'reserved',
                        reserved_at_utc = ?,
                        reserved_by_user_id = ?,
                        reserved_by_email = ?,
                        reserved_order_id = ?
                    WHERE id = ?
                      AND status = 'active'
                    """,
                    (now_utc, int(user_id), user_email, order_id, int(row["id"])),
                )
                conn.commit()
                if int(cursor.rowcount) <= 0:
                    return None
                return {
                    "code": normalized_code,
                    "amount_value": float(row["amount_value"]),
                    "price_currency": str(row["price_currency"]).strip().upper(),
                    "scans_per_day": int(row["scans_per_day"] or 0),
                    "duration_days": int(row["duration_days"] or 30),
                    "valid_until_utc": str(row["valid_until_utc"]),
                }

    def release_enterprise_code_reservation(
        self,
        *,
        code: str,
        order_id: str = "",
        user_id: Optional[int] = None,
    ) -> bool:
        normalized_code = str(code or "").strip().upper()
        if not normalized_code:
            return False
        normalized_order_id = str(order_id or "").strip()
        with self._lock:
            with self._connect() as conn:
                query = [
                    """
                    UPDATE billing_enterprise_codes
                    SET status = 'active',
                        reserved_at_utc = NULL,
                        reserved_by_user_id = NULL,
                        reserved_by_email = NULL,
                        reserved_order_id = NULL
                    WHERE code = ?
                      AND status = 'reserved'
                      AND (redeemed_at_utc IS NULL OR redeemed_at_utc = '')
                    """
                ]
                params: list[Any] = [normalized_code]
                if normalized_order_id:
                    query.append("AND reserved_order_id = ?")
                    params.append(normalized_order_id)
                if user_id is not None:
                    query.append("AND reserved_by_user_id = ?")
                    params.append(int(user_id))
                cursor = conn.execute("\n".join(query), tuple(params))
                conn.commit()
                return int(cursor.rowcount or 0) > 0

    def list_enterprise_codes(self, *, include_inactive: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._lock:
            with self._connect() as conn:
                if include_inactive:
                    rows = conn.execute(
                        """
                        SELECT id, code, created_at_utc, created_by_email, amount_value, price_currency, scans_per_day,
                               duration_days, valid_until_utc, note, status, reserved_order_id, redeemed_order_id
                        FROM billing_enterprise_codes
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, code, created_at_utc, created_by_email, amount_value, price_currency, scans_per_day,
                               duration_days, valid_until_utc, note, status, reserved_order_id, redeemed_order_id
                        FROM billing_enterprise_codes
                        WHERE status IN ('active', 'reserved')
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def has_free_trial_claimed(self, *, user_id: int) -> bool:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM billing_free_trial_claims WHERE user_id = ? LIMIT 1",
                    (int(user_id),),
                ).fetchone()
        return bool(row)

    def activate_free_trial(self, *, user_id: int, user_email: str, plan_id: str, plan_name: str, scans_per_day: int, duration_days: int) -> Optional[Dict[str, Any]]:
        if self.has_free_trial_claimed(user_id=user_id):
            return None

        now_utc = self._now_utc()
        expires_at_utc = self._plus_days_utc(duration_days)
        user_email = str(user_email or "").strip().lower()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO billing_free_trial_claims (user_id, user_email, claimed_at_utc)
                    VALUES (?, ?, ?)
                    """,
                    (int(user_id), user_email, now_utc),
                )
                claim_row = conn.execute("SELECT 1 FROM billing_free_trial_claims WHERE user_id = ? LIMIT 1", (int(user_id),)).fetchone()
                if not claim_row:
                    conn.commit()
                    return None
                conn.execute(
                    """
                    INSERT INTO billing_user_subscriptions (
                        user_id, user_email, plan_id, plan_name, scans_per_day, status, amount_value, price_currency,
                        source, order_id, enterprise_code, started_at_utc, expires_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, 'active', 0, 'EUR', 'free_trial', NULL, NULL, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        user_email=excluded.user_email,
                        plan_id=excluded.plan_id,
                        plan_name=excluded.plan_name,
                        scans_per_day=excluded.scans_per_day,
                        status='active',
                        amount_value=0,
                        price_currency='EUR',
                        source='free_trial',
                        order_id=NULL,
                        enterprise_code=NULL,
                        started_at_utc=excluded.started_at_utc,
                        expires_at_utc=excluded.expires_at_utc,
                        updated_at_utc=excluded.updated_at_utc
                    """,
                    (
                        int(user_id),
                        user_email,
                        str(plan_id).strip(),
                        str(plan_name).strip(),
                        max(0, int(scans_per_day)),
                        now_utc,
                        expires_at_utc,
                        now_utc,
                    ),
                )
                conn.commit()
        return {
            "user_id": int(user_id),
            "user_email": user_email,
            "plan_id": str(plan_id).strip(),
            "plan_name": str(plan_name).strip(),
            "scans_per_day": max(0, int(scans_per_day)),
            "status": "active",
            "source": "free_trial",
            "started_at_utc": now_utc,
            "expires_at_utc": expires_at_utc,
        }

    def grant_free_trial(
        self,
        *,
        user_id: int,
        user_email: str,
        duration_days: int = 30,
        scans_per_day: int = 1,
        source: str = "manual_grant",
    ) -> Dict[str, Any]:
        now_utc = self._now_utc()
        expires_at_utc = self._plus_days_utc(duration_days)
        normalized_email = str(user_email or "").strip().lower()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO billing_free_trial_claims (user_id, user_email, claimed_at_utc)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        user_email=excluded.user_email,
                        claimed_at_utc=excluded.claimed_at_utc
                    """,
                    (int(user_id), normalized_email, now_utc),
                )
                conn.execute(
                    """
                    INSERT INTO billing_user_subscriptions (
                        user_id, user_email, plan_id, plan_name, scans_per_day, status, amount_value, price_currency,
                        source, order_id, enterprise_code, started_at_utc, expires_at_utc, updated_at_utc
                    ) VALUES (?, ?, 'free-30d', 'Free', ?, 'active', 0, 'EUR', ?, NULL, NULL, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        user_email=excluded.user_email,
                        plan_id='free-30d',
                        plan_name='Free',
                        scans_per_day=excluded.scans_per_day,
                        status='active',
                        amount_value=0,
                        price_currency='EUR',
                        source=excluded.source,
                        order_id=NULL,
                        enterprise_code=NULL,
                        started_at_utc=excluded.started_at_utc,
                        expires_at_utc=excluded.expires_at_utc,
                        updated_at_utc=excluded.updated_at_utc
                    """,
                    (
                        int(user_id),
                        normalized_email,
                        max(0, int(scans_per_day)),
                        str(source or "manual_grant").strip(),
                        now_utc,
                        expires_at_utc,
                        now_utc,
                    ),
                )
                conn.commit()
        return {
            "user_id": int(user_id),
            "user_email": normalized_email,
            "plan_id": "free-30d",
            "plan_name": "Free",
            "scans_per_day": max(0, int(scans_per_day)),
            "status": "active",
            "source": str(source or "manual_grant").strip(),
            "started_at_utc": now_utc,
            "expires_at_utc": expires_at_utc,
        }

    def assign_unlimited_enterprise(
        self,
        *,
        user_id: int,
        user_email: str,
        source: str = "special_account",
    ) -> Dict[str, Any]:
        now_utc = self._now_utc()
        normalized_email = str(user_email or "").strip().lower()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO billing_user_subscriptions (
                        user_id, user_email, plan_id, plan_name, scans_per_day, status, amount_value, price_currency,
                        source, order_id, enterprise_code, started_at_utc, expires_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, 'active', 0, 'EUR', ?, NULL, 'SYSTEM', ?, NULL, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        user_email=excluded.user_email,
                        plan_id=excluded.plan_id,
                        plan_name=excluded.plan_name,
                        scans_per_day=excluded.scans_per_day,
                        status='active',
                        amount_value=0,
                        price_currency='EUR',
                        source=excluded.source,
                        order_id=NULL,
                        enterprise_code='SYSTEM',
                        started_at_utc=excluded.started_at_utc,
                        expires_at_utc=NULL,
                        updated_at_utc=excluded.updated_at_utc
                    """,
                    (
                        int(user_id),
                        normalized_email,
                        SPECIAL_ENTERPRISE_PLAN_ID,
                        SPECIAL_ENTERPRISE_PLAN_NAME,
                        SPECIAL_ENTERPRISE_SCANS_PER_DAY,
                        str(source or "special_account").strip(),
                        now_utc,
                        now_utc,
                    ),
                )
                conn.commit()
        return {
            "user_id": int(user_id),
            "user_email": normalized_email,
            "plan_id": SPECIAL_ENTERPRISE_PLAN_ID,
            "plan_name": SPECIAL_ENTERPRISE_PLAN_NAME,
            "scans_per_day": SPECIAL_ENTERPRISE_SCANS_PER_DAY,
            "status": "active",
            "source": str(source or "special_account").strip(),
            "started_at_utc": now_utc,
            "expires_at_utc": None,
        }

    def get_user_subscription(self, *, user_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT user_id, user_email, plan_id, plan_name, scans_per_day, status, amount_value, price_currency,
                           source, order_id, enterprise_code, started_at_utc, expires_at_utc, updated_at_utc
                    FROM billing_user_subscriptions
                    WHERE user_id = ?
                    LIMIT 1
                    """,
                    (int(user_id),),
                ).fetchone()
        return {key: row[key] for key in row.keys()} if row else None

    def is_user_access_active(self, *, user_id: int) -> Dict[str, Any]:
        subscription = self.get_user_subscription(user_id=user_id)
        if not subscription:
            return {"allowed": True, "reason": "no_subscription_record"}

        status = str(subscription.get("status", "")).strip().lower()
        expires_at = str(subscription.get("expires_at_utc", "") or "").strip()
        if status != "active":
            return {"allowed": False, "reason": f"subscription_status_{status or 'inactive'}", "subscription": subscription}
        if expires_at and expires_at < self._now_utc():
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """
                        UPDATE billing_user_subscriptions
                        SET status = 'expired', updated_at_utc = ?
                        WHERE user_id = ?
                        """,
                        (self._now_utc(), int(user_id)),
                    )
                    conn.commit()
            subscription["status"] = "expired"
            return {"allowed": False, "reason": "subscription_expired", "subscription": subscription}
        return {"allowed": True, "reason": "active", "subscription": subscription}

    def get_checkout_by_order_id(self, *, order_id: str) -> Optional[Dict[str, Any]]:
        normalized_order = str(order_id or "").strip()
        if not normalized_order:
            return None
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, created_at_utc, updated_at_utc, user_id, user_email, plan_id, plan_name, scans_per_day,
                           duration_days, amount_value, price_currency, pay_currency, order_id, enterprise_code,
                           nowpayments_payment_id, nowpayments_invoice_id, invoice_url, status, paid_at_utc,
                           provider_payload_json
                    FROM billing_checkout_sessions
                    WHERE order_id = ?
                    LIMIT 1
                    """,
                    (normalized_order,),
                ).fetchone()
        return {key: row[key] for key in row.keys()} if row else None

    def list_checkout_sessions(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, created_at_utc, updated_at_utc, user_id, user_email, plan_id, plan_name, scans_per_day,
                           duration_days, amount_value, price_currency, pay_currency, order_id, enterprise_code,
                           nowpayments_payment_id, nowpayments_invoice_id, invoice_url, status, paid_at_utc,
                           provider_payload_json
                    FROM billing_checkout_sessions
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def list_webhook_events(self, *, provider: str = "nowpayments", limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        normalized_provider = str(provider or "").strip().lower()
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, provider, event_id, created_at_utc, payload_json, signature
                    FROM billing_webhook_events
                    WHERE provider = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (normalized_provider, limit),
                ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload_json = str(row["payload_json"] or "").strip()
            try:
                payload = json.loads(payload_json) if payload_json else {}
            except json.JSONDecodeError:
                payload = {}
            item = {key: row[key] for key in row.keys()}
            item["payload"] = payload
            item["order_id"] = str(payload.get("order_id", "")).strip()
            item["payment_status"] = str(payload.get("payment_status") or payload.get("invoice_status") or "").strip().lower()
            result.append(item)
        return result

    def list_subscriptions(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT user_id, user_email, plan_id, plan_name, scans_per_day, status, amount_value, price_currency,
                           source, order_id, enterprise_code, started_at_utc, expires_at_utc, updated_at_utc
                    FROM billing_user_subscriptions
                    ORDER BY updated_at_utc DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def build_reconciliation_report(self, *, limit: int = 200) -> Dict[str, Any]:
        sessions = self.list_checkout_sessions(limit=limit)
        webhooks = self.list_webhook_events(provider="nowpayments", limit=limit)
        subscriptions = self.list_subscriptions(limit=limit)
        closed_issue_keys = self._list_closed_reconciliation_issue_keys()

        session_by_order = {
            str(item.get("order_id", "")).strip(): item
            for item in sessions
            if str(item.get("order_id", "")).strip()
        }
        subscriptions_by_order = {}
        for sub in subscriptions:
            order_id = str(sub.get("order_id", "")).strip()
            if order_id:
                subscriptions_by_order[order_id] = sub

        finalized_without_subscription = []
        stale_waiting_sessions = []
        partial_payment_sessions = []
        now_dt = datetime.now(timezone.utc)
        for session in sessions:
            order_id = str(session.get("order_id", "")).strip()
            status = str(session.get("status", "")).strip().lower()
            if status in FINAL_PAYMENT_STATUSES and order_id and order_id not in subscriptions_by_order:
                finalized_without_subscription.append(session)

            partial_row = self._build_partial_payment_row(session)
            if partial_row:
                partial_payment_sessions.append(partial_row)

            if status in {"waiting", "confirming", "pending"}:
                created_at = str(session.get("created_at_utc", "")).strip()
                try:
                    created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except ValueError:
                    created_dt = None
                if created_dt and (now_dt - created_dt) > timedelta(minutes=90):
                    stale_waiting_sessions.append(session)

        orphan_webhooks = []
        for event in webhooks:
            order_id = str(event.get("order_id", "")).strip()
            if order_id and order_id not in session_by_order:
                orphan_webhooks.append(event)

        orphan_subscriptions = []
        for sub in subscriptions:
            if str(sub.get("source", "")).strip().lower() != "nowpayments":
                continue
            order_id = str(sub.get("order_id", "")).strip()
            if not order_id or order_id not in session_by_order:
                orphan_subscriptions.append(sub)

        closed_count = 0

        def _decorate_and_filter(issue_type: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            nonlocal closed_count
            result: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                issue_key = self._reconciliation_issue_key_for_row(issue_type, item)
                item["issue_key"] = issue_key
                item["issue_type"] = issue_type
                if issue_key and (issue_type, issue_key) in closed_issue_keys:
                    closed_count += 1
                    continue
                result.append(item)
            return result

        finalized_without_subscription = _decorate_and_filter("finalized_without_subscription", finalized_without_subscription)
        orphan_webhooks = _decorate_and_filter("orphan_webhooks", orphan_webhooks)
        orphan_subscriptions = _decorate_and_filter("orphan_subscriptions", orphan_subscriptions)
        stale_waiting_sessions = _decorate_and_filter("stale_waiting_sessions", stale_waiting_sessions)

        return {
            "summary": {
                "sessions_checked": len(sessions),
                "webhooks_checked": len(webhooks),
                "subscriptions_checked": len(subscriptions),
                "finalized_without_subscription": len(finalized_without_subscription),
                "orphan_webhooks": len(orphan_webhooks),
                "orphan_subscriptions": len(orphan_subscriptions),
                "stale_waiting_sessions": len(stale_waiting_sessions),
                "partial_payment_sessions": len(partial_payment_sessions),
                "false_positives_closed": closed_count,
            },
            "finalized_without_subscription": finalized_without_subscription[:50],
            "orphan_webhooks": orphan_webhooks[:50],
            "orphan_subscriptions": orphan_subscriptions[:50],
            "stale_waiting_sessions": stale_waiting_sessions[:50],
            "partial_payment_sessions": partial_payment_sessions[:50],
            "recent_sessions": sessions[:30],
            "recent_webhooks": webhooks[:30],
            "recent_subscriptions": subscriptions[:30],
        }

    def sync_nowpayments_currencies(self, *, options: List[Dict[str, str]], source: str = "sync") -> Dict[str, int]:
        now_utc = self._now_utc()
        cleaned: list[tuple[str, str]] = []
        seen = set()
        for option in options:
            code = _normalize_currency_code(str(option.get("code", "")).strip())
            if not code or code in seen:
                continue
            seen.add(code)
            label = str(option.get("label", "")).strip() or _currency_label(code)
            cleaned.append((code, label))

        if not cleaned:
            return {"inserted": 0, "updated": 0}

        inserted = 0
        updated = 0
        with self._lock:
            with self._connect() as conn:
                for code, label in cleaned:
                    existing = conn.execute(
                        "SELECT code, is_enabled FROM billing_currency_capabilities WHERE code = ? LIMIT 1",
                        (code,),
                    ).fetchone()
                    if existing:
                        conn.execute(
                            """
                            UPDATE billing_currency_capabilities
                            SET label = ?, is_detected = 1, source = ?, updated_at_utc = ?
                            WHERE code = ?
                            """,
                            (label, str(source or "sync").strip(), now_utc, code),
                        )
                        updated += 1
                    else:
                        conn.execute(
                            """
                            INSERT INTO billing_currency_capabilities (
                                code, label, is_enabled, is_detected, source, updated_at_utc
                            ) VALUES (?, ?, 1, 1, ?, ?)
                            """,
                            (code, label, str(source or "sync").strip(), now_utc),
                        )
                        inserted += 1
                conn.execute(
                    """
                    UPDATE billing_currency_capabilities
                    SET is_detected = 0, updated_at_utc = ?
                    WHERE code NOT IN (%s)
                    """
                    % ",".join("?" for _ in cleaned),
                    tuple([now_utc] + [code for code, _ in cleaned]),
                )
                conn.commit()
        return {"inserted": inserted, "updated": updated}

    def set_nowpayments_currency_enabled(self, *, code: str, label: str = "", is_enabled: bool = True, source: str = "admin") -> bool:
        normalized_code = _normalize_currency_code(code)
        if not normalized_code:
            return False
        normalized_label = str(label or "").strip() or _currency_label(normalized_code)
        now_utc = self._now_utc()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO billing_currency_capabilities (
                        code, label, is_enabled, is_detected, source, updated_at_utc
                    ) VALUES (?, ?, ?, 0, ?, ?)
                    ON CONFLICT(code) DO UPDATE SET
                        label = excluded.label,
                        is_enabled = excluded.is_enabled,
                        source = excluded.source,
                        updated_at_utc = excluded.updated_at_utc
                    """,
                    (
                        normalized_code,
                        normalized_label,
                        1 if bool(is_enabled) else 0,
                        str(source or "admin").strip(),
                        now_utc,
                    ),
                )
                conn.commit()
        return True

    def list_nowpayments_currencies(self, *, include_disabled: bool = True, limit: int = 200) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        query = """
            SELECT code, label, is_enabled, is_detected, source, updated_at_utc
            FROM billing_currency_capabilities
        """
        params: tuple[Any, ...]
        if include_disabled:
            query += " ORDER BY is_enabled DESC, code ASC LIMIT ?"
            params = (limit,)
        else:
            query += " WHERE is_enabled = 1 ORDER BY code ASC LIMIT ?"
            params = (limit,)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(query, params).fetchall()
        return [
            {
                "code": str(row["code"]).strip().lower(),
                "label": str(row["label"]).strip(),
                "is_enabled": bool(int(row["is_enabled"])),
                "is_detected": bool(int(row["is_detected"])),
                "source": str(row["source"]).strip(),
                "updated_at_utc": str(row["updated_at_utc"]).strip(),
            }
            for row in rows
        ]

    def get_effective_pay_currency_options(self, *, default_options: List[Dict[str, str]]) -> List[Dict[str, str]]:
        override_enabled = self.list_nowpayments_currencies(include_disabled=False, limit=200)
        if override_enabled:
            return [
                {
                    "code": _normalize_currency_code(row.get("code", "")),
                    "label": str(row.get("label", "")).strip() or _currency_label(row.get("code", "")),
                }
                for row in override_enabled
                if _normalize_currency_code(row.get("code", ""))
            ]

        options: list[dict[str, str]] = []
        seen = set()
        for item in default_options:
            code = _normalize_currency_code(str(item.get("code", "")).strip())
            if not code or code in seen:
                continue
            seen.add(code)
            options.append({"code": code, "label": str(item.get("label", "")).strip() or _currency_label(code)})
        return options
