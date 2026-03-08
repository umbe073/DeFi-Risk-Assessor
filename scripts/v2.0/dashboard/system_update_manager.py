#!/usr/bin/env python3
"""
Shared system update helpers for DeFi dashboard windows.

This module centralizes:
- Dependency update state persistence
- Auto-check interval parsing
- Human-readable elapsed-time formatting
- Safe library refresh flow (outdated check + dry-run + install + pip check)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
REQUIREMENTS_FILE = os.path.join(PROJECT_ROOT, "requirements.txt")
SYSTEM_UPDATE_STATE_FILE = os.path.join(DATA_DIR, "system_update_state.json")
API_SERVICE_REGISTRY_FILE = os.path.join(DATA_DIR, "api_runtime", "api_services_registry.json")


DEFAULT_SYSTEM_UPDATE_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "check_on_startup": True,
    "auto_check_interval": "7 days",
    "auto_check_custom_hours": 168,
    "auto_install_safe_updates": False,
    "safety_check_enabled": True,
    "max_update_timeout_seconds": 1800,
}


DEFAULT_UPDATE_STATE: Dict[str, Any] = {
    "last_check_at": None,
    "last_update_at": None,
    "last_check_status": "never",
    "last_update_status": "never",
    "last_outdated_count": 0,
    "last_outdated_packages": [],
    "last_check_duration_seconds": 0.0,
    "last_update_duration_seconds": 0.0,
    "last_error": "",
    "last_check_output_tail": "",
    "last_update_output_tail": "",
}


SETTINGS_COMMENTS: Dict[str, Any] = {
    "_note": (
        "JSON does not support // inline comments; this _comments section stores "
        "human-readable explanations for each setting."
    ),
    "cache.auto_refresh_interval": "How often to refresh cache metadata checks.",
    "cache.cache_retention": "How long fallback/cache data is retained before full replacement.",
    "cache.fallback_sync_interval": "How often fallback snapshots are synchronized to disk.",
    "cache.background_monitoring": "Runs periodic cache checks in background threads.",
    "cache.respect_48h_metric_skip": (
        "When enabled, recently fetched metrics are reused to reduce API pressure."
    ),
    "cache.metric_skip_hours": (
        "Recent-data reuse window. Lower values increase freshness and API usage."
    ),
    "cache.force_live_override_on_change": (
        "Allow fresh on-chain values to overwrite cache when value drift is detected."
    ),
    "cache.metric_drift_threshold_pct": (
        "Minimum drift percentage required to force cached-value replacement."
    ),
    "api.rate_limiting": "Enable internal throttling to reduce 429/rate-limit responses.",
    "api.fallback_data": "Use trusted fallback cache when live endpoints are unavailable.",
    "api.api_monitoring": "Track endpoint health and request behavior over time.",
    "api.conditional_requests": (
        "Use ETag/If-Modified-Since where supported to reduce bandwidth/rate usage."
    ),
    "api.adaptive_backoff": (
        "Increase retry delay when endpoints return errors or throttling signals."
    ),
    "api.max_parallel_requests": (
        "Upper bound on concurrent API calls. Lower this if you see frequent 429 responses."
    ),
    "api.retry_backoff_seconds": "Base backoff delay between retries.",
    "api.request_jitter_ms": (
        "Random request delay to avoid request bursts and synchronized spikes."
    ),
    "api.timeout": "Per-request timeout in seconds.",
    "api.retry_attempts": "How many times failed calls are retried before fallback.",
    "eu_mode.enabled": "Master switch for EU-related risk flags during assessments.",
    "eu_mode.enable_eu_unlicensed_stablecoin": "Enable/disable licensing red flag for stablecoins outside allowlist.",
    "eu_mode.enable_eu_regulatory_issues": "Enable/disable EU regulatory issue red flag (external compliance signals only).",
    "eu_mode.enable_mica_non_compliant": "Enable/disable MiCA non-compliance red flag (documentation/verification based).",
    "eu_mode.enable_mica_no_whitepaper": "Enable/disable MiCA missing whitepaper red flag.",
    "eu_mode.dynamic_allowlist_enabled": "Read regulated-stablecoin allowlist from data/<allowlist_registry_file> at runtime.",
    "eu_mode.allowlist_registry_file": "JSON filename under data/ used as dynamic regulated-stablecoin allowlist registry.",
    "eu_mode.allowlist_extra_symbols": "Optional extra regulated symbols merged into dynamic allowlist.",
    "display.theme": "Dashboard visual theme preference.",
    "display.font_size": "Dashboard UI font scale.",
    "display.notifications": "Enable/disable desktop notifications.",
    "system_update.enabled": "Enable scheduled dependency update checks.",
    "system_update.check_on_startup": "Run an update check when settings window starts.",
    "system_update.auto_check_interval": "How often automatic dependency checks run.",
    "system_update.auto_check_custom_hours": (
        "Custom interval used when auto_check_interval='Custom'."
    ),
    "system_update.auto_install_safe_updates": (
        "Automatically install updates only after safety pre-check passes."
    ),
    "system_update.safety_check_enabled": (
        "Run pip dry-run validation before real install."
    ),
    "system_update.max_update_timeout_seconds": (
        "Maximum allowed runtime for install step before timeout."
    ),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail_text(text: str, max_chars: int = 2400) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _normalized_package_name(name: Any) -> str:
    """Normalize package names for case/sep-insensitive matching."""
    try:
        value = str(name or "").strip().lower()
        return value.replace("_", "-")
    except Exception:
        return ""


def extract_failed_packages_from_pip_output(
    stdout_text: Any,
    stderr_text: Any,
    known_package_names: List[str] | None = None,
) -> List[str]:
    """
    Best-effort extraction of problematic package names from pip error output.

    Returns package names using original casing when known_package_names is provided.
    """
    stdout_s = str(stdout_text or "")
    stderr_s = str(stderr_text or "")
    combined = f"{stdout_s}\n{stderr_s}".strip()
    if not combined:
        return []

    known_names = [str(x).strip() for x in (known_package_names or []) if str(x).strip()]
    known_lookup = {_normalized_package_name(x): x for x in known_names}
    failures: set[str] = set()

    patterns = [
        r"Could not find a version that satisfies the requirement\s+([A-Za-z0-9_.-]+)",
        r"No matching distribution found for\s+([A-Za-z0-9_.-]+)",
        r"ERROR:\s+.*?depends on\s+([A-Za-z0-9_.-]+)",
        r"ERROR:\s+Cannot install\s+([A-Za-z0-9_.-]+)",
        r"Failed building wheel for\s+([A-Za-z0-9_.-]+)",
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, combined, flags=re.IGNORECASE):
            norm = _normalized_package_name(raw)
            if not norm:
                continue
            failures.add(known_lookup.get(norm, str(raw).strip()))

    # Heuristic fallback: scan error lines for known names.
    if known_lookup:
        error_lines = []
        for line in combined.splitlines():
            lower_line = line.lower()
            if any(
                marker in lower_line
                for marker in (
                    "error:",
                    "resolutionimpossible",
                    "conflict",
                    "requires",
                    "no matching distribution",
                    "could not find a version",
                )
            ):
                error_lines.append(line)
        for line in error_lines:
            lower_line = line.lower()
            for norm_name, original_name in known_lookup.items():
                if not norm_name:
                    continue
                if re.search(rf"(?<![a-z0-9_.-]){re.escape(norm_name)}(?![a-z0-9_.-])", lower_line):
                    failures.add(original_name)

    # Context fallback: if we saw a pip error, include the nearest preceding "Collecting X".
    # This catches build failures where pip doesn't explicitly print "for <pkg>".
    lines = combined.splitlines()
    error_markers = (
        "error:",
        "subprocess-exited-with-error",
        "resolutionimpossible",
        "conflict",
        "failed with status",
        "getting requirements to build wheel",
    )
    first_error_idx = None
    for idx, line in enumerate(lines):
        lower_line = line.lower()
        if any(marker in lower_line for marker in error_markers):
            first_error_idx = idx
            break
    if first_error_idx is not None:
        collecting_pattern = re.compile(r"Collecting\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
        for idx in range(first_error_idx, -1, -1):
            match = collecting_pattern.search(lines[idx])
            if not match:
                continue
            raw_pkg = match.group(1)
            norm = _normalized_package_name(raw_pkg)
            if norm:
                failures.add(known_lookup.get(norm, raw_pkg))
            break

    return sorted(failures, key=lambda x: str(x).lower())


def extract_pip_failure_highlight_lines(
    stdout_text: Any,
    stderr_text: Any,
    max_lines: int = 20,
) -> List[str]:
    """
    Return key pip failure lines (and minimal context) suitable for UI display.
    """
    stdout_s = str(stdout_text or "")
    stderr_s = str(stderr_text or "")
    combined = f"{stdout_s}\n{stderr_s}".strip()
    if not combined:
        return []

    lines = combined.splitlines()
    markers = (
        "error:",
        "subprocess-exited-with-error",
        "resolutionimpossible",
        "conflict",
        "no matching distribution",
        "could not find a version",
        "failed building wheel",
        "getting requirements to build wheel",
        "is not available on",
        "requires",
    )
    collecting_re = re.compile(r"Collecting\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)

    selected: List[str] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines):
        lower_line = line.lower()
        if not any(marker in lower_line for marker in markers):
            continue
        # Include nearest prior Collecting line to provide package context.
        for back in range(idx, max(-1, idx - 8), -1):
            m = collecting_re.search(lines[back])
            if m:
                collect_line = lines[back].strip()
                if collect_line and collect_line not in seen:
                    seen.add(collect_line)
                    selected.append(collect_line)
                break
        clean_line = line.strip()
        if clean_line and clean_line not in seen:
            seen.add(clean_line)
            selected.append(clean_line)
        if len(selected) >= max_lines:
            break

    if not selected:
        tail_lines = [line.strip() for line in lines if line.strip()]
        selected = tail_lines[-max_lines:]

    return selected[:max_lines]


def _normalize_package_specs(package_specs: List[str] | None) -> List[str]:
    specs: List[str] = []
    for item in package_specs or []:
        value = str(item or "").strip()
        if value:
            specs.append(value)
    # Preserve order while removing duplicates.
    return list(dict.fromkeys(specs))


def load_json_file(path: str, fallback: Any) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback


def save_json_file(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_update_state() -> Dict[str, Any]:
    loaded = load_json_file(SYSTEM_UPDATE_STATE_FILE, {})
    if not isinstance(loaded, dict):
        loaded = {}
    merged = dict(DEFAULT_UPDATE_STATE)
    merged.update(loaded)
    return merged


def save_update_state(state: Dict[str, Any]) -> None:
    payload = dict(DEFAULT_UPDATE_STATE)
    payload.update(state if isinstance(state, dict) else {})
    save_json_file(SYSTEM_UPDATE_STATE_FILE, payload)


def inject_settings_comments(settings: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(settings if isinstance(settings, dict) else {})
    existing = payload.get("_comments")
    merged_comments: Dict[str, Any] = {}
    if isinstance(existing, dict):
        merged_comments.update(existing)
    for key, value in SETTINGS_COMMENTS.items():
        merged_comments.setdefault(key, value)
    payload["_comments"] = merged_comments
    return payload


def parse_interval_to_seconds(interval_text: Any, custom_hours: Any = 24) -> int:
    if isinstance(interval_text, (int, float)):
        hours = float(interval_text)
        return max(300, int(hours * 3600))

    text = str(interval_text or "").strip().lower()
    if text == "custom":
        try:
            h = float(custom_hours)
        except Exception:
            h = 24.0
        return max(300, int(h * 3600))

    tokens = text.split()
    if not tokens:
        return 24 * 3600

    try:
        amount = float(tokens[0])
    except Exception:
        return 24 * 3600

    unit = tokens[1] if len(tokens) > 1 else "hours"
    if unit.startswith("minute"):
        seconds = amount * 60.0
    elif unit.startswith("hour"):
        seconds = amount * 3600.0
    elif unit.startswith("day"):
        seconds = amount * 86400.0
    elif unit.startswith("week"):
        seconds = amount * 7.0 * 86400.0
    elif unit.startswith("month"):
        seconds = amount * 30.0 * 86400.0
    else:
        seconds = amount * 3600.0

    return max(300, int(seconds))


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def humanize_elapsed(iso_time: Any) -> str:
    dt = _parse_iso(iso_time)
    if not dt:
        return "Never"
    now = datetime.now(timezone.utc)
    delta_seconds = max(0, int((now - dt).total_seconds()))
    if delta_seconds < 60:
        return f"{delta_seconds}s ago"
    if delta_seconds < 3600:
        return f"{delta_seconds // 60}m ago"
    if delta_seconds < 86400:
        return f"{delta_seconds // 3600}h ago"
    days = delta_seconds // 86400
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    return f"{months}mo ago"


def _pip_cmd(python_executable: str | None = None) -> List[str]:
    py = python_executable or sys.executable
    return [py, "-m", "pip"]


def check_outdated_packages(
    python_executable: str | None = None,
    timeout_seconds: int = 240,
) -> Dict[str, Any]:
    started = time.time()
    cmd = _pip_cmd(python_executable) + ["list", "--outdated", "--format=json"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Failed to run outdated check: {exc}",
            "packages": [],
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": "",
            "stderr_tail": "",
            "command": cmd,
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"pip list --outdated failed (exit {proc.returncode})",
            "packages": [],
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": _tail_text(stdout),
            "stderr_tail": _tail_text(stderr),
            "command": cmd,
        }

    try:
        parsed = json.loads(stdout) if stdout else []
        if not isinstance(parsed, list):
            parsed = []
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Could not parse outdated package list: {exc}",
            "packages": [],
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": _tail_text(stdout),
            "stderr_tail": _tail_text(stderr),
            "command": cmd,
        }

    packages = [p for p in parsed if isinstance(p, dict)]
    packages.sort(key=lambda x: str(x.get("name", "")).lower())
    return {
        "ok": True,
        "packages": packages,
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": _tail_text(stdout),
        "stderr_tail": _tail_text(stderr),
        "command": cmd,
    }


def run_safety_dry_run(
    requirements_path: str = REQUIREMENTS_FILE,
    python_executable: str | None = None,
    timeout_seconds: int = 900,
    package_specs: List[str] | None = None,
) -> Dict[str, Any]:
    started = time.time()
    specs = _normalize_package_specs(package_specs)
    cmd = _pip_cmd(python_executable) + [
        "install",
        "--dry-run",
        "--upgrade",
        "--upgrade-strategy",
        "eager",
    ]
    if specs:
        cmd.extend(specs)
    else:
        cmd.extend(["-r", requirements_path])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(60, int(timeout_seconds)),
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Dry-run failed to execute: {exc}",
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": "",
            "stderr_tail": "",
            "command": cmd,
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    stdout_tail = _tail_text(stdout, max_chars=6000)
    stderr_tail = _tail_text(stderr, max_chars=6000)
    return {
        "ok": proc.returncode == 0,
        "error": "" if proc.returncode == 0 else f"Dry-run failed (exit {proc.returncode})",
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "command": cmd,
    }


def install_requirements_upgrade(
    requirements_path: str = REQUIREMENTS_FILE,
    python_executable: str | None = None,
    timeout_seconds: int = 1800,
    package_specs: List[str] | None = None,
) -> Dict[str, Any]:
    started = time.time()
    specs = _normalize_package_specs(package_specs)
    cmd = _pip_cmd(python_executable) + [
        "install",
        "--upgrade",
        "--upgrade-strategy",
        "eager",
    ]
    if specs:
        cmd.extend(specs)
    else:
        cmd.extend(["-r", requirements_path])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(120, int(timeout_seconds)),
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Install failed to execute: {exc}",
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": "",
            "stderr_tail": "",
            "command": cmd,
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    return {
        "ok": proc.returncode == 0,
        "error": "" if proc.returncode == 0 else f"Install failed (exit {proc.returncode})",
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": _tail_text(stdout),
        "stderr_tail": _tail_text(stderr),
        "command": cmd,
    }


def run_pip_check(
    python_executable: str | None = None,
    timeout_seconds: int = 180,
) -> Dict[str, Any]:
    started = time.time()
    cmd = _pip_cmd(python_executable) + ["check"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": f"pip check execution failed: {exc}",
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": "",
            "stderr_tail": "",
            "command": cmd,
        }

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    return {
        "ok": proc.returncode == 0,
        "error": "" if proc.returncode == 0 else f"pip check failed (exit {proc.returncode})",
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": _tail_text(stdout),
        "stderr_tail": _tail_text(stderr),
        "command": cmd,
    }


def should_run_auto_check(
    system_update_settings: Dict[str, Any],
    state: Dict[str, Any],
) -> bool:
    if not bool(system_update_settings.get("enabled", True)):
        return False

    interval_text = system_update_settings.get("auto_check_interval", "7 days")
    custom_hours = system_update_settings.get("auto_check_custom_hours", 168)
    interval_seconds = parse_interval_to_seconds(interval_text, custom_hours)

    last_check = _parse_iso(state.get("last_check_at"))
    if last_check is None:
        if bool(system_update_settings.get("check_on_startup", True)):
            return True
        baseline = _parse_iso(state.get("scheduler_baseline_at"))
        if baseline is None:
            state["scheduler_baseline_at"] = utc_now_iso()
            save_update_state(state)
            return False
        elapsed = (datetime.now(timezone.utc) - baseline).total_seconds()
        return elapsed >= interval_seconds

    elapsed_seconds = (datetime.now(timezone.utc) - last_check).total_seconds()
    return elapsed_seconds >= interval_seconds
