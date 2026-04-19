"""Tests for risk job log / event sanitization."""

from __future__ import annotations

from app.risk_event_sanitize import (
    sanitize_details_for_storage,
    sanitize_event_for_public,
    sanitize_job_for_public_response,
    sanitize_public_message,
)


def test_sanitize_public_message_truncates_and_strips_paths() -> None:
    long = "x" * 3000
    out = sanitize_public_message(long)
    assert len(out) < 2100
    assert out.endswith("…")
    mixed = "See /opt/hodler-suite/scripts/v2.0/foo.py for details"
    assert "[path]" in sanitize_public_message(mixed)


def test_sanitize_details_drops_result_blobs() -> None:
    raw = {
        "worker_id": "w1",
        "result": {"risk_score": 99, "nested": {"x": "y" * 900}},
        "token": "should_drop_key",
    }
    out = sanitize_details_for_storage(raw)
    assert "result" not in out
    assert "token" not in out
    assert out.get("worker_id") == "w1"


def test_sanitize_event_for_public_roundtrip() -> None:
    ev = {
        "id": 1,
        "message": "/home/user/secret/project",
        "details": {"worker_id": "w", "stack": "no"},
    }
    safe = sanitize_event_for_public(ev)
    assert "[path]" in safe["message"]
    assert "stack" not in safe["details"]


def test_sanitize_job_strips_event_details() -> None:
    job = {
        "job_id": "RJ-test",
        "summary_message": "ok",
        "events": [
            {
                "id": 1,
                "message": "done",
                "details": {"result": {"a": 1}},
            }
        ],
    }
    pub = sanitize_job_for_public_response(job)
    assert "result" not in pub["events"][0]["details"]
