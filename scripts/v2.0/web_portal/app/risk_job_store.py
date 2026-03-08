"""SQLite persistence for risk-assessment job orchestration state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import sqlite3
from threading import Lock
from typing import Any, Dict, List, Optional


VALID_JOB_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
VALID_JOB_STAGES = {"queued", "fetching", "analyzing", "finalizing", "succeeded", "failed", "cancelled"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _normalize_status(value: str, *, default: str = "queued") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_JOB_STATUSES:
        return normalized
    return default


def _normalize_stage(value: str, *, default: str = "queued") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_JOB_STAGES:
        return normalized
    return default


def _safe_progress(value: Any, *, fallback: int = 0) -> int:
    try:
        progress = int(float(value))
    except (TypeError, ValueError):
        progress = int(fallback)
    return max(0, min(progress, 100))


class RiskJobStore:
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
    def _load_json_dict(value: str) -> Dict[str, Any]:
        raw = str(value or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
        return {}

    @staticmethod
    def _build_job_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        suffix = secrets.token_hex(4).upper()
        return f"RJ-{timestamp}-{suffix}"

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "job_id": str(row["job_id"]),
            "created_at_utc": str(row["created_at_utc"]),
            "updated_at_utc": str(row["updated_at_utc"]),
            "started_at_utc": str(row["started_at_utc"] or ""),
            "finished_at_utc": str(row["finished_at_utc"] or ""),
            "requested_by_user_id": int(row["requested_by_user_id"] or 0),
            "requested_by_role": str(row["requested_by_role"] or ""),
            "requested_by_email": str(row["requested_by_email"] or ""),
            "token_address": str(row["token_address"] or ""),
            "token_chain": str(row["token_chain"] or ""),
            "mode": str(row["mode"] or "global"),
            "source": str(row["source"] or "web_portal"),
            "status": _normalize_status(str(row["status"] or ""), default="queued"),
            "stage": _normalize_stage(str(row["stage"] or ""), default="queued"),
            "progress": _safe_progress(row["progress"], fallback=0),
            "summary_message": str(row["summary_message"] or ""),
            "error_code": str(row["error_code"] or ""),
            "error_message": str(row["error_message"] or ""),
            "metadata": RiskJobStore._load_json_dict(str(row["metadata_json"] or "")),
        }

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]),
            "job_id": str(row["job_id"]),
            "created_at_utc": str(row["created_at_utc"]),
            "event_type": str(row["event_type"] or "event"),
            "status": _normalize_status(str(row["status"] or ""), default="queued"),
            "stage": _normalize_stage(str(row["stage"] or ""), default="queued"),
            "progress": _safe_progress(row["progress"], fallback=0),
            "message": str(row["message"] or ""),
            "details": RiskJobStore._load_json_dict(str(row["details_json"] or "")),
        }

    @staticmethod
    def _row_to_artifact(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]),
            "job_id": str(row["job_id"]),
            "created_at_utc": str(row["created_at_utc"]),
            "artifact_kind": str(row["artifact_kind"] or "generic"),
            "artifact_uri": str(row["artifact_uri"] or ""),
            "content_type": str(row["content_type"] or ""),
            "metadata": RiskJobStore._load_json_dict(str(row["metadata_json"] or "")),
        }

    @staticmethod
    def _row_value(row: sqlite3.Row | None, key: str) -> Any:
        if row is None:
            return ""
        try:
            return row[key]
        except Exception:
            return ""

    def _ensure_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS risk_jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL UNIQUE,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        started_at_utc TEXT,
                        finished_at_utc TEXT,
                        requested_by_user_id INTEGER NOT NULL,
                        requested_by_role TEXT NOT NULL,
                        requested_by_email TEXT NOT NULL,
                        token_address TEXT NOT NULL,
                        token_chain TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        source TEXT NOT NULL,
                        status TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        progress INTEGER NOT NULL,
                        summary_message TEXT,
                        error_code TEXT,
                        error_message TEXT,
                        metadata_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS risk_job_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        progress INTEGER NOT NULL,
                        message TEXT,
                        details_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS risk_job_artifacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        artifact_kind TEXT NOT NULL,
                        artifact_uri TEXT NOT NULL,
                        content_type TEXT,
                        metadata_json TEXT
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_risk_jobs_job_id ON risk_jobs(job_id)")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_risk_jobs_requested_by ON risk_jobs(requested_by_user_id, created_at_utc)"
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_risk_jobs_status ON risk_jobs(status, created_at_utc)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_risk_job_events_job_id ON risk_job_events(job_id, id)")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_risk_job_artifacts_job_id ON risk_job_artifacts(job_id, id)"
                )

                cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
                stale_job_rows = conn.execute(
                    """
                    SELECT job_id
                    FROM risk_jobs
                    WHERE finished_at_utc IS NOT NULL
                      AND finished_at_utc < ?
                    """,
                    (cutoff,),
                ).fetchall()
                stale_job_ids = [str(row["job_id"]) for row in stale_job_rows]
                if stale_job_ids:
                    conn.executemany("DELETE FROM risk_job_events WHERE job_id = ?", [(job_id,) for job_id in stale_job_ids])
                    conn.executemany(
                        "DELETE FROM risk_job_artifacts WHERE job_id = ?",
                        [(job_id,) for job_id in stale_job_ids],
                    )
                    conn.executemany("DELETE FROM risk_jobs WHERE job_id = ?", [(job_id,) for job_id in stale_job_ids])

                conn.commit()

    def create_job(
        self,
        *,
        requested_by_user_id: int,
        requested_by_role: str,
        requested_by_email: str,
        token_address: str,
        token_chain: str = "",
        mode: str = "global",
        source: str = "web_portal",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_token = str(token_address or "").strip()
        if not normalized_token:
            raise ValueError("token_address is required")
        normalized_mode = str(mode or "global").strip().lower()
        if normalized_mode not in {"global", "eu"}:
            normalized_mode = "global"

        now_utc = self._now_utc()
        job_id = self._build_job_id()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True)
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO risk_jobs (
                        job_id, created_at_utc, updated_at_utc, started_at_utc, finished_at_utc,
                        requested_by_user_id, requested_by_role, requested_by_email,
                        token_address, token_chain, mode, source, status, stage, progress,
                        summary_message, error_code, error_message, metadata_json
                    ) VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, 'queued', 'queued', 0, '', '', '', ?)
                    """,
                    (
                        job_id,
                        now_utc,
                        now_utc,
                        max(1, int(requested_by_user_id)),
                        str(requested_by_role or "").strip().lower() or "child",
                        str(requested_by_email or "").strip().lower(),
                        normalized_token,
                        str(token_chain or "").strip().lower(),
                        normalized_mode,
                        str(source or "web_portal").strip().lower(),
                        metadata_json,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO risk_job_events (
                        job_id, created_at_utc, event_type, status, stage, progress, message, details_json
                    ) VALUES (?, ?, 'created', 'queued', 'queued', 0, 'Job created', ?)
                    """,
                    (job_id, now_utc, metadata_json),
                )
                conn.commit()
        created = self.get_job(job_id)
        if created is None:
            raise RuntimeError("failed_to_create_risk_job")
        return created

    def get_job(
        self,
        job_id: str,
        *,
        include_events: bool = False,
        include_artifacts: bool = False,
        event_limit: int = 80,
        artifact_limit: int = 40,
    ) -> Dict[str, Any] | None:
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            return None
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT job_id, created_at_utc, updated_at_utc, started_at_utc, finished_at_utc,
                           requested_by_user_id, requested_by_role, requested_by_email,
                           token_address, token_chain, mode, source, status, stage, progress,
                           summary_message, error_code, error_message, metadata_json
                    FROM risk_jobs
                    WHERE job_id = ?
                    LIMIT 1
                    """,
                    (normalized_job_id,),
                ).fetchone()
                if row is None:
                    return None
                job = self._row_to_job(row)
                if include_events:
                    events = conn.execute(
                        """
                        SELECT id, job_id, created_at_utc, event_type, status, stage, progress, message, details_json
                        FROM risk_job_events
                        WHERE job_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (normalized_job_id, max(1, min(int(event_limit), 500))),
                    ).fetchall()
                    job["events"] = [self._row_to_event(item) for item in events]
                if include_artifacts:
                    artifacts = conn.execute(
                        """
                        SELECT id, job_id, created_at_utc, artifact_kind, artifact_uri, content_type, metadata_json
                        FROM risk_job_artifacts
                        WHERE job_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (normalized_job_id, max(1, min(int(artifact_limit), 500))),
                    ).fetchall()
                    job["artifacts"] = [self._row_to_artifact(item) for item in artifacts]
                return job

    def list_jobs(
        self,
        *,
        requested_by_user_id: int | None = None,
        status: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        normalized_status = _normalize_status(status, default="")
        query_limit = max(1, min(int(limit), 500))
        with self._lock:
            with self._connect() as conn:
                if requested_by_user_id is not None and normalized_status:
                    rows = conn.execute(
                        """
                        SELECT job_id, created_at_utc, updated_at_utc, started_at_utc, finished_at_utc,
                               requested_by_user_id, requested_by_role, requested_by_email,
                               token_address, token_chain, mode, source, status, stage, progress,
                               summary_message, error_code, error_message, metadata_json
                        FROM risk_jobs
                        WHERE requested_by_user_id = ? AND status = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (int(requested_by_user_id), normalized_status, query_limit),
                    ).fetchall()
                elif requested_by_user_id is not None:
                    rows = conn.execute(
                        """
                        SELECT job_id, created_at_utc, updated_at_utc, started_at_utc, finished_at_utc,
                               requested_by_user_id, requested_by_role, requested_by_email,
                               token_address, token_chain, mode, source, status, stage, progress,
                               summary_message, error_code, error_message, metadata_json
                        FROM risk_jobs
                        WHERE requested_by_user_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (int(requested_by_user_id), query_limit),
                    ).fetchall()
                elif normalized_status:
                    rows = conn.execute(
                        """
                        SELECT job_id, created_at_utc, updated_at_utc, started_at_utc, finished_at_utc,
                               requested_by_user_id, requested_by_role, requested_by_email,
                               token_address, token_chain, mode, source, status, stage, progress,
                               summary_message, error_code, error_message, metadata_json
                        FROM risk_jobs
                        WHERE status = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (normalized_status, query_limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT job_id, created_at_utc, updated_at_utc, started_at_utc, finished_at_utc,
                               requested_by_user_id, requested_by_role, requested_by_email,
                               token_address, token_chain, mode, source, status, stage, progress,
                               summary_message, error_code, error_message, metadata_json
                        FROM risk_jobs
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (query_limit,),
                    ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def build_runtime_metrics(
        self,
        *,
        window_hours: int = 24,
        stale_running_minutes: int = 20,
    ) -> Dict[str, Any]:
        hours = max(1, int(window_hours))
        stale_minutes = max(1, int(stale_running_minutes))
        now_dt = datetime.now(timezone.utc)
        window_cutoff = (now_dt - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        stale_cutoff = (now_dt - timedelta(minutes=stale_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

        counts = {key: 0 for key in VALID_JOB_STATUSES}
        with self._lock:
            with self._connect() as conn:
                status_rows = conn.execute(
                    """
                    SELECT status, COUNT(*) AS cnt
                    FROM risk_jobs
                    GROUP BY status
                    """
                ).fetchall()
                for row in status_rows:
                    status = _normalize_status(str(row["status"] or ""), default="")
                    if status in counts:
                        counts[status] = int(row["cnt"] or 0)

                oldest_queued = conn.execute(
                    """
                    SELECT created_at_utc
                    FROM risk_jobs
                    WHERE status = 'queued'
                    ORDER BY id ASC
                    LIMIT 1
                    """
                ).fetchone()
                oldest_running = conn.execute(
                    """
                    SELECT started_at_utc, updated_at_utc
                    FROM risk_jobs
                    WHERE status = 'running'
                    ORDER BY id ASC
                    LIMIT 1
                    """
                ).fetchone()

                stale_running_row = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM risk_jobs
                    WHERE status = 'running'
                      AND COALESCE(updated_at_utc, started_at_utc, created_at_utc) < ?
                    """,
                    (stale_cutoff,),
                ).fetchone()
                stale_running_count = int(self._row_value(stale_running_row, "cnt") or 0)

                recent_rows = conn.execute(
                    """
                    SELECT status, COUNT(*) AS cnt
                    FROM risk_jobs
                    WHERE finished_at_utc IS NOT NULL
                      AND finished_at_utc >= ?
                    GROUP BY status
                    """,
                    (window_cutoff,),
                ).fetchall()
                recent = {"succeeded": 0, "failed": 0, "cancelled": 0}
                for row in recent_rows:
                    status = _normalize_status(str(row["status"] or ""), default="")
                    if status in recent:
                        recent[status] = int(row["cnt"] or 0)

                last_success = conn.execute(
                    """
                    SELECT finished_at_utc
                    FROM risk_jobs
                    WHERE status = 'succeeded'
                      AND finished_at_utc IS NOT NULL
                    ORDER BY finished_at_utc DESC
                    LIMIT 1
                    """
                ).fetchone()

        return {
            "counts": counts,
            "stale_running_count": stale_running_count,
            "stale_running_minutes": stale_minutes,
            "window_hours": hours,
            "oldest_queued_created_at_utc": str(self._row_value(oldest_queued, "created_at_utc") or ""),
            "oldest_running_started_at_utc": str(self._row_value(oldest_running, "started_at_utc") or ""),
            "oldest_running_updated_at_utc": str(self._row_value(oldest_running, "updated_at_utc") or ""),
            "recent": recent,
            "last_success_finished_at_utc": str(self._row_value(last_success, "finished_at_utc") or ""),
        }

    def claim_next_job(
        self,
        *,
        worker_id: str = "",
        stage: str = "fetching",
        progress: int = 5,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | None:
        now_utc = self._now_utc()
        next_stage = _normalize_stage(stage, default="fetching")
        next_progress = _safe_progress(progress, fallback=5)
        normalized_worker_id = str(worker_id or "").strip() or "risk_worker"
        event_details: Dict[str, Any] = dict(details or {})
        event_details["worker_id"] = normalized_worker_id
        details_json = json.dumps(event_details, ensure_ascii=True, sort_keys=True)

        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT job_id
                    FROM risk_jobs
                    WHERE status = 'queued'
                    ORDER BY id ASC
                    LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    conn.commit()
                    return None

                claimed_job_id = str(row["job_id"] or "").strip()
                if not claimed_job_id:
                    conn.commit()
                    return None

                cursor = conn.execute(
                    """
                    UPDATE risk_jobs
                    SET updated_at_utc = ?,
                        started_at_utc = COALESCE(started_at_utc, ?),
                        status = 'running',
                        stage = ?,
                        progress = ?,
                        summary_message = '',
                        error_code = '',
                        error_message = ''
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    (
                        now_utc,
                        now_utc,
                        next_stage,
                        next_progress,
                        claimed_job_id,
                    ),
                )
                if int(cursor.rowcount or 0) != 1:
                    conn.commit()
                    return None

                conn.execute(
                    """
                    INSERT INTO risk_job_events (
                        job_id, created_at_utc, event_type, status, stage, progress, message, details_json
                    ) VALUES (?, ?, 'claimed', 'running', ?, ?, ?, ?)
                    """,
                    (
                        claimed_job_id,
                        now_utc,
                        next_stage,
                        next_progress,
                        "Job claimed by worker",
                        details_json,
                    ),
                )
                conn.commit()

        return self.get_job(claimed_job_id)

    def update_job_state(
        self,
        *,
        job_id: str,
        status: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        summary_message: str = "",
        error_code: str = "",
        error_message: str = "",
        event_type: str = "state_update",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | None:
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            return None
        now_utc = self._now_utc()

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT status, stage, progress, started_at_utc, finished_at_utc
                    FROM risk_jobs
                    WHERE job_id = ?
                    LIMIT 1
                    """,
                    (normalized_job_id,),
                ).fetchone()
                if row is None:
                    return None

                next_status = _normalize_status(status, default=str(row["status"] or "queued")) if status is not None else _normalize_status(str(row["status"] or "queued"))
                next_stage = _normalize_stage(stage, default=str(row["stage"] or "queued")) if stage is not None else _normalize_stage(str(row["stage"] or "queued"))
                next_progress = _safe_progress(progress, fallback=int(row["progress"] or 0)) if progress is not None else _safe_progress(row["progress"], fallback=0)

                if next_stage in TERMINAL_STATUSES:
                    next_status = next_stage
                if next_status in TERMINAL_STATUSES:
                    next_stage = next_status
                    if next_progress < 100:
                        next_progress = 100

                started_at_utc = str(row["started_at_utc"] or "")
                if next_status == "running" and not started_at_utc:
                    started_at_utc = now_utc
                finished_at_utc = str(row["finished_at_utc"] or "")
                if next_status in TERMINAL_STATUSES:
                    finished_at_utc = finished_at_utc or now_utc
                elif finished_at_utc:
                    finished_at_utc = ""

                conn.execute(
                    """
                    UPDATE risk_jobs
                    SET updated_at_utc = ?,
                        started_at_utc = ?,
                        finished_at_utc = ?,
                        status = ?,
                        stage = ?,
                        progress = ?,
                        summary_message = ?,
                        error_code = ?,
                        error_message = ?
                    WHERE job_id = ?
                    """,
                    (
                        now_utc,
                        started_at_utc or None,
                        finished_at_utc or None,
                        next_status,
                        next_stage,
                        next_progress,
                        str(summary_message or "").strip(),
                        str(error_code or "").strip(),
                        str(error_message or "").strip(),
                        normalized_job_id,
                    ),
                )
                details_json = json.dumps(details or {}, ensure_ascii=True, sort_keys=True)
                conn.execute(
                    """
                    INSERT INTO risk_job_events (
                        job_id, created_at_utc, event_type, status, stage, progress, message, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_job_id,
                        now_utc,
                        str(event_type or "state_update").strip().lower() or "state_update",
                        next_status,
                        next_stage,
                        next_progress,
                        str(summary_message or "").strip(),
                        details_json,
                    ),
                )
                conn.commit()

        return self.get_job(normalized_job_id)

    def cancel_job(self, *, job_id: str, reason: str) -> Dict[str, Any] | None:
        return self.update_job_state(
            job_id=job_id,
            status="cancelled",
            stage="cancelled",
            progress=100,
            summary_message=str(reason or "Job cancelled").strip() or "Job cancelled",
            event_type="cancelled",
            details={"reason": str(reason or "").strip()},
        )

    def add_job_artifact(
        self,
        *,
        job_id: str,
        artifact_kind: str,
        artifact_uri: str,
        content_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | None:
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            return None
        normalized_artifact_uri = str(artifact_uri or "").strip()
        if not normalized_artifact_uri:
            return None

        now_utc = self._now_utc()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=True, sort_keys=True)
        with self._lock:
            with self._connect() as conn:
                existing = conn.execute(
                    "SELECT job_id FROM risk_jobs WHERE job_id = ? LIMIT 1",
                    (normalized_job_id,),
                ).fetchone()
                if existing is None:
                    return None
                cursor = conn.execute(
                    """
                    INSERT INTO risk_job_artifacts (
                        job_id, created_at_utc, artifact_kind, artifact_uri, content_type, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_job_id,
                        now_utc,
                        str(artifact_kind or "generic").strip().lower() or "generic",
                        normalized_artifact_uri,
                        str(content_type or "").strip(),
                        metadata_json,
                    ),
                )
                conn.commit()
                row = conn.execute(
                    """
                    SELECT id, job_id, created_at_utc, artifact_kind, artifact_uri, content_type, metadata_json
                    FROM risk_job_artifacts
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (int(cursor.lastrowid),),
                ).fetchone()
        if row is None:
            return None
        return self._row_to_artifact(row)
