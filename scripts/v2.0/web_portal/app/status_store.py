"""SQLite persistence for service-status telemetry samples."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import sqlite3
from threading import Lock
from typing import Any, Dict, Iterable, List


VALID_SERVICE_STATES = {"online", "degraded", "offline", "disabled", "unknown"}


def _parse_utc(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _normalize_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_SERVICE_STATES:
        return normalized
    return "unknown"


class StatusStore:
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

    def _ensure_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS service_status_samples (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sampled_at_utc TEXT NOT NULL,
                        service_key TEXT NOT NULL,
                        service_name TEXT NOT NULL,
                        group_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        latency_ms INTEGER,
                        detail TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_service_status_key_time ON service_status_samples(service_key, sampled_at_utc)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_service_status_group_time ON service_status_samples(group_name, sampled_at_utc)"
                )
                cutoff = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute("DELETE FROM service_status_samples WHERE sampled_at_utc < ?", (cutoff,))
                conn.commit()

    def record_samples(self, samples: Iterable[Dict[str, Any]]) -> int:
        now_utc = self._now_utc()
        rows: list[tuple] = []
        for sample in samples:
            service_key = str(sample.get("service_key") or sample.get("key") or "").strip().lower()
            if not service_key:
                continue
            service_name = str(sample.get("service_name") or sample.get("name") or service_key).strip()
            group_name = str(sample.get("group_name") or sample.get("group") or "Core").strip()
            status = _normalize_status(str(sample.get("status", "unknown")))
            latency_raw = sample.get("latency_ms")
            latency_ms = None
            if latency_raw is not None and str(latency_raw).strip() != "":
                try:
                    latency_ms = max(0, int(float(latency_raw)))
                except (TypeError, ValueError):
                    latency_ms = None
            detail = str(sample.get("detail", "")).strip()
            if len(detail) > 500:
                detail = detail[:500]
            rows.append((now_utc, service_key, service_name, group_name, status, latency_ms, detail))

        if not rows:
            return 0

        with self._lock:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO service_status_samples (
                        sampled_at_utc, service_key, service_name, group_name, status, latency_ms, detail
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                cutoff = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute("DELETE FROM service_status_samples WHERE sampled_at_utc < ?", (cutoff,))
                conn.commit()
        return len(rows)

    def list_samples(self, *, service_key: str, hours: int = 24, limit: int = 4000) -> List[Dict[str, Any]]:
        normalized_key = str(service_key or "").strip().lower()
        if not normalized_key:
            return []
        limit = max(1, min(int(limit), 20000))
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(hours)))).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT sampled_at_utc, service_key, service_name, group_name, status, latency_ms, detail
                    FROM service_status_samples
                    WHERE service_key = ? AND sampled_at_utc >= ?
                    ORDER BY sampled_at_utc ASC
                    LIMIT ?
                    """,
                    (normalized_key, cutoff, limit),
                ).fetchall()
        return [{key: row[key] for key in row.keys()} for row in rows]

    def summarize(self, *, service_key: str, hours: int = 24) -> Dict[str, Any]:
        samples = self.list_samples(service_key=service_key, hours=hours, limit=20000)
        counts = {state: 0 for state in VALID_SERVICE_STATES}
        latencies: list[int] = []
        for sample in samples:
            status = _normalize_status(str(sample.get("status", "")))
            counts[status] += 1
            latency = sample.get("latency_ms")
            if latency is not None:
                try:
                    latencies.append(max(0, int(latency)))
                except (TypeError, ValueError):
                    pass
        total = len(samples)
        online_count = counts["online"]
        degraded_count = counts["degraded"]
        offline_count = counts["offline"]
        uptime_percent = round((online_count / total) * 100, 1) if total > 0 else 0.0
        error_rate_percent = round(((degraded_count + offline_count) / total) * 100, 1) if total > 0 else 0.0
        avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else None
        return {
            "total": total,
            "counts": counts,
            "uptime_percent": uptime_percent,
            "error_rate_percent": error_rate_percent,
            "avg_latency_ms": avg_latency_ms,
            "samples": samples,
        }

    def build_history(self, *, service_key: str, hours: int = 24, buckets: int = 24) -> List[Dict[str, Any]]:
        buckets = max(4, min(int(buckets), 96))
        hours = max(1, int(hours))
        summary = self.summarize(service_key=service_key, hours=hours)
        samples = summary["samples"]
        now_dt = datetime.now(timezone.utc)
        total_seconds = float(hours * 3600)
        bucket_seconds = total_seconds / float(buckets)
        data: list[dict[str, float]] = [
            {"total": 0.0, "online": 0.0, "errors": 0.0}
            for _ in range(buckets)
        ]

        for sample in samples:
            sampled_dt = _parse_utc(str(sample.get("sampled_at_utc", "")))
            if sampled_dt is None:
                continue
            age_seconds = (now_dt - sampled_dt).total_seconds()
            if age_seconds < 0 or age_seconds > total_seconds:
                continue
            idx = buckets - 1 - int(age_seconds // bucket_seconds)
            idx = max(0, min(idx, buckets - 1))
            entry = data[idx]
            entry["total"] += 1.0
            status = _normalize_status(str(sample.get("status", "")))
            if status == "online":
                entry["online"] += 1.0
            if status in {"degraded", "offline"}:
                entry["errors"] += 1.0

        chart = []
        for idx, row in enumerate(data):
            total = row["total"]
            if total <= 0:
                online_pct = 0.0
                error_pct = 0.0
            else:
                online_pct = round((row["online"] / total) * 100.0, 1)
                error_pct = round((row["errors"] / total) * 100.0, 1)
            chart.append({"bucket": idx, "online_pct": online_pct, "error_pct": error_pct})
        return chart
