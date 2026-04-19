"""Sanitize risk job log lines and event ``details`` for storage and public APIs.

Worker and placeholder code must never persist full engine results or host paths inside
``risk_job_events.details_json``; artifacts already hold structured results.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

MAX_PUBLIC_MESSAGE_CHARS = 2000
MAX_DETAIL_STRING_CHARS = 800
MAX_DETAIL_DEPTH = 4
MAX_DETAIL_KEYS = 32

# Dropped entirely from persisted / public details (large or sensitive).
_DROP_DETAIL_KEYS = frozenset(
    {
        "result",
        "artifact_metadata",
        "raw",
        "raw_output",
        "traceback",
        "stack",
        "stack_trace",
        "exception",
        "env",
        "environ",
        "headers",
        "cookies",
        "authorization",
        "password",
        "secret",
        "api_key",
        "token",
    }
)

_PATH_SEGMENT = re.compile(
    r"(?:/(?:opt|usr|var|home|Users|Volumes|private|tmp|etc|workspace|Desktop|venv)[^\s,:]{0,220})"
)
_WIN_PATH = re.compile(r"(?:[A-Za-z]:\\(?:[^\s,:]|\\){1,220})")


def _clip_message(text: str) -> str:
    s = str(text or "").replace("\x00", " ")
    if len(s) > MAX_PUBLIC_MESSAGE_CHARS:
        return s[: MAX_PUBLIC_MESSAGE_CHARS - 1] + "…"
    return s


def _redact_paths(text: str) -> str:
    s = str(text or "")
    s = _PATH_SEGMENT.sub("[path]", s)
    s = _WIN_PATH.sub("[path]", s)
    return s


def sanitize_public_message(text: str) -> str:
    """User-facing log line (event ``message`` and job summary lines)."""
    return _redact_paths(_clip_message(text))


def _sanitize_primitive(value: Any, *, depth: int) -> Any:
    if depth > MAX_DETAIL_DEPTH:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        s = _redact_paths(value)
        if len(s) > MAX_DETAIL_STRING_CHARS:
            return s[: MAX_DETAIL_STRING_CHARS - 1] + "…"
        return s
    if isinstance(value, list):
        out: List[Any] = []
        for i, item in enumerate(value[:20]):
            sanitized = _sanitize_primitive(item, depth=depth + 1)
            if sanitized is not None:
                out.append(sanitized)
        return out
    if isinstance(value, dict):
        return sanitize_details_for_storage(value, depth=depth + 1)
    return None


def sanitize_details_for_storage(details: Any, *, depth: int = 0) -> Dict[str, Any]:
    """Shrink and strip worker ``details`` before SQLite insert."""
    if not isinstance(details, dict):
        return {}
    out: Dict[str, Any] = {}
    for idx, (raw_k, v) in enumerate(details.items()):
        if idx >= MAX_DETAIL_KEYS:
            out["_truncated"] = True
            break
        key = str(raw_k).strip().lower()
        if key in _DROP_DETAIL_KEYS or key.startswith("http_authorization"):
            continue
        sanitized = _sanitize_primitive(v, depth=depth)
        if sanitized is not None:
            out[key] = sanitized
    return out


def sanitize_event_for_public(event: Dict[str, Any]) -> Dict[str, Any]:
    """Copy one event row for JSON / SSE; does not mutate input."""
    base = copy.deepcopy(event)
    base["message"] = sanitize_public_message(str(base.get("message") or ""))
    det = base.get("details")
    if isinstance(det, dict):
        base["details"] = sanitize_details_for_storage(det)
    else:
        base["details"] = {}
    return base


def sanitize_job_for_public_response(job: Dict[str, Any]) -> Dict[str, Any]:
    """Copy job dict for authenticated tenant-scoped API responses."""
    out = copy.deepcopy(job)
    out["summary_message"] = sanitize_public_message(str(out.get("summary_message") or ""))
    out["error_message"] = sanitize_public_message(str(out.get("error_message") or ""))
    events = out.get("events")
    if isinstance(events, list):
        out["events"] = [sanitize_event_for_public(e) for e in events if isinstance(e, dict)]
    return out


def sanitize_job_summary_fields(job: Dict[str, Any]) -> Dict[str, Any]:
    """Light sanitization for list endpoints (no embedded events)."""
    out = copy.deepcopy(job)
    out["summary_message"] = sanitize_public_message(str(out.get("summary_message") or ""))
    out["error_message"] = sanitize_public_message(str(out.get("error_message") or ""))
    return out
