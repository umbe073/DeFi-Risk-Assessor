"""Shared ChainAbuse cache and refresh queue.

The public ChainAbuse standard quota is extremely small, so normal risk
assessments should use cached results and enqueue refreshes instead of calling
the provider directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import time
from typing import Any


CACHE_TTL_SECONDS = 365 * 24 * 60 * 60
REFRESH_AFTER_SECONDS = 30 * 24 * 60 * 60
BATCH_SIZE = 50
QUEUE_TIMEOUT_SECONDS = 72 * 60 * 60
STANDARD_MONTHLY_CALL_LIMIT = 10

ELIGIBLE_PLAN_IDS = {
    "basic-monthly",
    "pro-monthly",
    "enterprise-custom",
    "enterprise",
    "staff",
    "master",
    "admin",
}


@dataclass(frozen=True)
class ChainAbuseLookup:
    """Result of a cache/queue lookup."""

    status: str
    result: dict[str, Any] | None
    queued: bool
    queue_depth: int
    batch_ready: bool
    cache_age_seconds: int | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "result": self.result,
            "queued": self.queued,
            "queue_depth": self.queue_depth,
            "batch_ready": self.batch_ready,
            "cache_age_seconds": self.cache_age_seconds,
            "message": self.message,
        }


def normalize_chain(chain: str) -> str:
    value = str(chain or "").strip().lower()
    aliases = {
        "ethereum": "eth",
        "erc20": "eth",
        "binance": "bsc",
        "binance-smart-chain": "bsc",
        "binance smart chain": "bsc",
        "matic": "polygon",
        "optimism": "op",
        "zksync-era": "zksync",
        "era": "zksync",
    }
    return aliases.get(value, value or "eth")


def normalize_address(address: str) -> str:
    return str(address or "").strip().lower()


def _utc_iso_from_epoch(value: int | float | None) -> str:
    try:
        ts = int(value or 0)
    except (TypeError, ValueError):
        ts = 0
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_cache_db_path() -> Path:
    raw = str(
        os.getenv("HODLER_CHAINABUSE_CACHE_DB")
        or os.getenv("CHAINABUSE_CACHE_DB")
        or ""
    ).strip()
    if raw:
        return Path(raw).expanduser().resolve()

    runtime_dir = str(os.getenv("API_SERVICE_RUNTIME_DIR") or "").strip()
    if runtime_dir:
        return Path(runtime_dir).expanduser().resolve() / "chainabuse_cache.db"

    suite_root = str(os.getenv("HODLER_SUITE_ROOT") or "").strip()
    if suite_root:
        return (
            Path(suite_root).expanduser().resolve()
            / "data"
            / "api_runtime"
            / "chainabuse_cache.db"
        )

    return Path(__file__).resolve().parents[2] / "data" / "api_runtime" / "chainabuse_cache.db"


def plan_allows_chainabuse_cache(*, plan_id: str, role: str = "", runtime_tier: str = "") -> bool:
    role_key = str(role or "").strip().lower()
    if role_key in {"master", "admin"}:
        return True
    tier_key = str(runtime_tier or "").strip().lower()
    if tier_key in {"none", "primary"}:
        return False
    return str(plan_id or "").strip().lower() in ELIGIBLE_PLAN_IDS


class ChainAbuseSharedCache:
    """SQLite-backed cache and queue for ChainAbuse token results."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path).expanduser().resolve() if db_path else resolve_cache_db_path()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chainabuse_cache (
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'chainabuse',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (chain, address)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chainabuse_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    first_requested_at INTEGER NOT NULL,
                    last_requested_at INTEGER NOT NULL,
                    requested_count INTEGER NOT NULL DEFAULT 1,
                    requested_by_plan TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    locked_at INTEGER NOT NULL DEFAULT 0,
                    batch_id TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_chainabuse_queue_active
                ON chainabuse_queue(chain, address)
                WHERE status IN ('queued', 'processing')
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chainabuse_queue_status_requested
                ON chainabuse_queue(status, first_requested_at)
                """
            )

    def cleanup(self, *, now: float | None = None) -> None:
        now_i = int(now if now is not None else time.time())
        stale_queue_before = now_i - CACHE_TTL_SECONDS
        with self._connect() as conn:
            conn.execute("DELETE FROM chainabuse_cache WHERE expires_at <= ?", (now_i,))
            conn.execute(
                """
                DELETE FROM chainabuse_queue
                WHERE status IN ('fetched', 'skipped', 'error')
                  AND last_requested_at <= ?
                """,
                (stale_queue_before,),
            )

    def get_cached(
        self,
        *,
        address: str,
        chain: str,
        now: float | None = None,
        include_stale: bool = True,
    ) -> tuple[dict[str, Any] | None, int | None, bool]:
        now_i = int(now if now is not None else time.time())
        addr = normalize_address(address)
        ch = normalize_chain(chain)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT result_json, fetched_at, expires_at
                FROM chainabuse_cache
                WHERE chain = ? AND address = ?
                LIMIT 1
                """,
                (ch, addr),
            ).fetchone()
        if row is None:
            return None, None, False
        expires_at = int(row["expires_at"] or 0)
        if expires_at <= now_i:
            return None, None, False
        fetched_at = int(row["fetched_at"] or 0)
        is_fresh = fetched_at >= now_i - REFRESH_AFTER_SECONDS
        if not include_stale and not is_fresh:
            return None, None, False
        try:
            payload = json.loads(str(row["result_json"] or "{}"))
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return payload, max(0, now_i - fetched_at), is_fresh

    def store_result(
        self,
        *,
        address: str,
        chain: str,
        result: dict[str, Any],
        fetched_at: float | None = None,
        source: str = "chainabuse",
    ) -> None:
        now_i = int(fetched_at if fetched_at is not None else time.time())
        addr = normalize_address(address)
        ch = normalize_chain(chain)
        payload = json.dumps(dict(result or {}), ensure_ascii=True, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chainabuse_cache (
                    chain, address, result_json, fetched_at, expires_at,
                    source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chain, address) DO UPDATE SET
                    result_json = excluded.result_json,
                    fetched_at = excluded.fetched_at,
                    expires_at = excluded.expires_at,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (
                    ch,
                    addr,
                    payload,
                    now_i,
                    now_i + CACHE_TTL_SECONDS,
                    str(source or "chainabuse"),
                    now_i,
                    now_i,
                ),
            )
            conn.execute(
                """
                UPDATE chainabuse_queue
                SET status = 'fetched', last_requested_at = ?, locked_at = 0
                WHERE chain = ? AND address = ? AND status IN ('queued', 'processing')
                """,
                (now_i, ch, addr),
            )

    def enqueue(
        self,
        *,
        address: str,
        chain: str,
        requested_by_plan: str = "",
        now: float | None = None,
    ) -> tuple[bool, int, bool]:
        now_i = int(now if now is not None else time.time())
        addr = normalize_address(address)
        ch = normalize_chain(chain)
        inserted = False
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO chainabuse_queue (
                        chain, address, status, first_requested_at, last_requested_at,
                        requested_count, requested_by_plan
                    )
                    VALUES (?, ?, 'queued', ?, ?, 1, ?)
                    """,
                    (ch, addr, now_i, now_i, str(requested_by_plan or "")),
                )
                inserted = True
            except sqlite3.IntegrityError:
                conn.execute(
                    """
                    UPDATE chainabuse_queue
                    SET last_requested_at = ?,
                        requested_count = requested_count + 1,
                        requested_by_plan = CASE
                            WHEN requested_by_plan = '' THEN ?
                            ELSE requested_by_plan
                        END
                    WHERE chain = ? AND address = ? AND status IN ('queued', 'processing')
                    """,
                    (now_i, str(requested_by_plan or ""), ch, addr),
                )
            queue_depth, oldest = self._queue_stats(conn)
        batch_ready = queue_depth >= BATCH_SIZE or (
            oldest is not None and now_i - int(oldest) >= QUEUE_TIMEOUT_SECONDS
        )
        return inserted, queue_depth, batch_ready

    def _queue_stats(self, conn: sqlite3.Connection) -> tuple[int, int | None]:
        row = conn.execute(
            """
            SELECT COUNT(1) AS c, MIN(first_requested_at) AS oldest
            FROM chainabuse_queue
            WHERE status = 'queued'
            """
        ).fetchone()
        if row is None:
            return 0, None
        depth = int(row["c"] or 0)
        oldest = row["oldest"]
        return depth, int(oldest) if oldest is not None else None

    def queue_stats(self, *, now: float | None = None) -> dict[str, Any]:
        now_i = int(now if now is not None else time.time())
        with self._connect() as conn:
            depth, oldest = self._queue_stats(conn)
        return {
            "queue_depth": depth,
            "oldest_queued_at": oldest,
            "batch_ready": depth >= BATCH_SIZE
            or (oldest is not None and now_i - int(oldest) >= QUEUE_TIMEOUT_SECONDS),
            "batch_size": BATCH_SIZE,
            "timeout_seconds": QUEUE_TIMEOUT_SECONDS,
        }

    def dashboard_snapshot(
        self,
        *,
        now: float | None = None,
        monthly_call_limit: int = STANDARD_MONTHLY_CALL_LIMIT,
        cached_token_limit: int = 120,
    ) -> dict[str, Any]:
        """Return customer-facing queue/cache visibility for API Center."""
        now_i = int(now if now is not None else time.time())
        self.cleanup(now=now_i)
        fresh_after = now_i - REFRESH_AFTER_SECONDS
        token_limit = max(1, min(int(cached_token_limit or 120), 500))
        with self._connect() as conn:
            queue_depth, oldest = self._queue_stats(conn)
            total_row = conn.execute("SELECT COUNT(1) AS c FROM chainabuse_cache").fetchone()
            fresh_row = conn.execute(
                """
                SELECT COUNT(1) AS c
                FROM chainabuse_cache
                WHERE fetched_at >= ? AND expires_at > ?
                """,
                (fresh_after, now_i),
            ).fetchone()
            cached_rows = conn.execute(
                """
                SELECT chain, address, fetched_at, expires_at, source
                FROM chainabuse_cache
                WHERE fetched_at >= ? AND expires_at > ?
                ORDER BY fetched_at DESC, chain ASC, address ASC
                LIMIT ?
                """,
                (fresh_after, now_i, token_limit),
            ).fetchall()

        fresh_count = int(fresh_row["c"] if fresh_row else 0)
        total_count = int(total_row["c"] if total_row else 0)
        estimated_calls_used = int(math.ceil(fresh_count / BATCH_SIZE)) if fresh_count > 0 else 0
        normalized_limit = max(0, int(monthly_call_limit or 0))
        calls_left = max(0, normalized_limit - estimated_calls_used) if normalized_limit else 0
        cached_tokens = [
            {
                "chain": str(row["chain"] or ""),
                "address": str(row["address"] or ""),
                "fetched_at": _utc_iso_from_epoch(row["fetched_at"]),
                "expires_at": _utc_iso_from_epoch(row["expires_at"]),
                "source": str(row["source"] or "chainabuse"),
            }
            for row in cached_rows
        ]
        return {
            "queue_depth": queue_depth,
            "oldest_queued_at": oldest,
            "oldest_queued_at_iso": _utc_iso_from_epoch(oldest),
            "batch_ready": queue_depth >= BATCH_SIZE
            or (oldest is not None and now_i - int(oldest) >= QUEUE_TIMEOUT_SECONDS),
            "batch_size": BATCH_SIZE,
            "timeout_seconds": QUEUE_TIMEOUT_SECONDS,
            "cache_total_tokens": total_count,
            "fresh_cached_token_count": fresh_count,
            "fresh_window_seconds": REFRESH_AFTER_SECONDS,
            "monthly_call_limit": normalized_limit,
            "estimated_monthly_calls_used": estimated_calls_used,
            "monthly_calls_left": calls_left,
            "cached_recent_tokens": cached_tokens,
            "cached_recent_token_count": len(cached_tokens),
            "cached_recent_token_limit": token_limit,
        }

    def get_for_assessment(
        self,
        *,
        address: str,
        chain: str,
        plan_id: str,
        role: str = "",
        runtime_tier: str = "",
        now: float | None = None,
    ) -> ChainAbuseLookup:
        now_i = int(now if now is not None else time.time())
        self.cleanup(now=now_i)
        if not plan_allows_chainabuse_cache(
            plan_id=plan_id,
            role=role,
            runtime_tier=runtime_tier,
        ):
            stats = self.queue_stats(now=now_i)
            return ChainAbuseLookup(
                status="plan_disabled",
                result=None,
                queued=False,
                queue_depth=int(stats["queue_depth"]),
                batch_ready=bool(stats["batch_ready"]),
                message=(
                    "ChainAbuse cache is available only to Basic, Pro, "
                    "and Enterprise accounts."
                ),
            )

        payload, age, is_fresh = self.get_cached(
            address=address,
            chain=chain,
            now=now_i,
            include_stale=True,
        )
        if payload is not None and is_fresh:
            stats = self.queue_stats(now=now_i)
            return ChainAbuseLookup(
                status="cache_hit_fresh",
                result=payload,
                queued=False,
                queue_depth=int(stats["queue_depth"]),
                batch_ready=bool(stats["batch_ready"]),
                cache_age_seconds=age,
            )

        queued, depth, ready = self.enqueue(
            address=address,
            chain=chain,
            requested_by_plan=str(plan_id or role or runtime_tier),
            now=now_i,
        )
        if payload is not None:
            return ChainAbuseLookup(
                status="cache_hit_stale_refresh_queued",
                result=payload,
                queued=queued,
                queue_depth=depth,
                batch_ready=ready,
                cache_age_seconds=age,
            )
        return ChainAbuseLookup(
            status="cache_miss_queued",
            result=None,
            queued=queued,
            queue_depth=depth,
            batch_ready=ready,
            message="No shared ChainAbuse result is cached yet; token was queued for refresh.",
        )


def get_for_assessment(
    *,
    address: str,
    chain: str,
    plan_id: str,
    role: str = "",
    runtime_tier: str = "",
    db_path: str | Path | None = None,
    now: float | None = None,
) -> ChainAbuseLookup:
    return ChainAbuseSharedCache(db_path).get_for_assessment(
        address=address,
        chain=chain,
        plan_id=plan_id,
        role=role,
        runtime_tier=runtime_tier,
        now=now,
    )
