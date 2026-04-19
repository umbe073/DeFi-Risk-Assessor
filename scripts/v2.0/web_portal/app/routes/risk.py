"""Risk-assessment orchestration routes."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
import hmac
import json
import os
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Dict, List

import io

import pandas as pd
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..auth import api_login_required, get_current_user
from ..chain_catalog import live_assessment_chain_options
from ..entitlements import (
    RISK_BATCH_ABS_MAX,
    build_risk_access,
    effective_risk_batch_run_cap,
    evaluate_feature_entitlement,
)
from ..hodler_chain_codes import (
    CANONICAL_TOKEN_CHAIN_CODES,
    is_allowed_token_chain_hint,
    normalize_token_chain_hint,
)
from ..risk_event_sanitize import (
    sanitize_details_for_storage,
    sanitize_event_for_public,
    sanitize_job_for_public_response,
    sanitize_job_summary_fields,
    sanitize_public_message,
)
from ..runtime_paths import resolve_api_runtime_dir
from ..token_address_validation import normalize_and_validate_token_address


risk_bp = Blueprint("risk", __name__, url_prefix="/api/v1/risk")
# Public POST /jobs* handlers only enqueue SQLite rows (and return). Heavy assessment runs in a
# separate subprocess (``risk_worker_process.py``) triggered by ``POST /internal/run-once`` / systemd,
# or a fast placeholder path—never inline inside a Gunicorn request thread for real engine work.
RISK_JOB_BATCH_MAX_ITEMS = RISK_BATCH_ABS_MAX
TOKEN_LIST_CSV_MAX_UPLOAD_BYTES = 512 * 1024
PRIMARY_VISIBLE_PROVIDERS = frozenset({"CoinGecko", "DeFiLlama", "Etherscan", "Alchemy"})


def _multi_token_batch_allowed(risk_access: Dict[str, Any]) -> bool:
    if risk_access.get("is_admin_like"):
        return True
    return bool(risk_access.get("live_assessment_list_mode"))


SOCIAL_PROVIDERS = frozenset({"Santiment", "Twitter/X", "Reddit"})
FULL_RISK_CATEGORIES = ("market", "liquidity", "behavior", "contract")
STANDARD_RUNTIME_DISABLED_SERVICES = frozenset(
    {
        "twitter",
        "telegram",
        "discord",
        "reddit",
        "coindesk",
        "theblock",
        "decrypt",
        "bitcointalk",
        "cointelegraph",
        "santiment",
    }
)
PRIMARY_RUNTIME_DISABLED_SERVICES = STANDARD_RUNTIME_DISABLED_SERVICES | frozenset(
    {
        "arkham",
        "birdeye",
        "bitquery",
        "breadcrumbs",
        "certik",
        "chainabuse",
        "coinmarketcap",
        "coincap",
        "debank",
        "defisafety",
        "dexscreener",
        "dune",
        "ethplorer",
        "lifi",
        "lukka",
        "moralis",
        "oklink",
        "oneinch",
        "opensanctions",
        "scorechain",
        "solscan",
        "solanatracker",
        "thegraph",
        "trmlabs",
        "zapper",
    }
)


def _chainabuse_cache_db_path() -> str:
    raw = str(
        os.getenv("HODLER_CHAINABUSE_CACHE_DB")
        or os.getenv("CHAINABUSE_CACHE_DB")
        or ""
    ).strip()
    if raw:
        return str(Path(raw).expanduser().resolve())
    return str(resolve_api_runtime_dir(Path(__file__).resolve()) / "chainabuse_cache.db")


def _extract_risk_worker_secret() -> str:
    auth_header = str(request.headers.get("Authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    header_secret = str(request.headers.get("X-Risk-Worker-Secret", "")).strip()
    if header_secret:
        return header_secret

    query_secret = str(request.args.get("secret", "")).strip()
    if query_secret:
        return query_secret
    return ""


def _authorize_risk_worker_request() -> tuple[bool, Dict[str, Any], int]:
    settings = current_app.config["SETTINGS"]
    configured_secret = str(getattr(settings, "risk_worker_shared_secret", "") or "").strip()
    if not configured_secret:
        return (
            False,
            {
                "error": "risk_worker_secret_not_configured",
                "message": "Set RISK_WORKER_SHARED_SECRET before using internal risk worker endpoints.",
            },
            503,
        )

    provided = _extract_risk_worker_secret()
    if not provided or not hmac.compare_digest(provided, configured_secret):
        return (
            False,
            {
                "error": "unauthorized",
                "message": "Invalid risk worker secret.",
            },
            401,
        )
    return True, {"status": "authorized"}, 200


def _extract_risk_compat_secret() -> str:
    auth_header = str(request.headers.get("Authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    for header_name in ("X-Risk-Compat-Secret", "X-Risk-Worker-Secret"):
        header_secret = str(request.headers.get(header_name, "")).strip()
        if header_secret:
            return header_secret

    for query_name in ("compat_secret", "secret"):
        query_secret = str(request.args.get(query_name, "")).strip()
        if query_secret:
            return query_secret
    return ""


def _compat_secret_is_authorized() -> bool:
    settings = current_app.config["SETTINGS"]
    configured_secret = str(
        getattr(settings, "risk_compat_shared_secret", "")
        or getattr(settings, "risk_worker_shared_secret", "")
        or ""
    ).strip()
    if not configured_secret:
        return False
    provided_secret = _extract_risk_compat_secret()
    return bool(provided_secret and hmac.compare_digest(provided_secret, configured_secret))


def _compat_request_payload() -> Dict[str, Any]:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return dict(payload)
    return {key: value for key, value in request.values.items()}


def _first_non_empty(payload: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_chain_hint(value: str) -> str:
    """Map UI/API chain text to canonical engine codes (see `hodler_chain_codes`)."""
    return normalize_token_chain_hint(value)


def _normalize_risk_job_payload(payload: Dict[str, Any], *, source_default: str) -> Dict[str, Any]:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    token_address = _first_non_empty(payload, "token_address", "address", "token", "tokenAddress").strip()
    token_chain = _normalize_chain_hint(
        _first_non_empty(payload, "token_chain", "chain", "chain_hint", "network")
    )
    mode = _first_non_empty(payload, "mode", "assessment_mode", "risk_mode").lower() or "global"
    if mode not in {"global", "eu"}:
        mode = "global"

    source = _first_non_empty(payload, "source").lower() or str(source_default or "web_portal").strip().lower()
    return {
        "token_address": token_address,
        "token_chain": token_chain,
        "mode": mode,
        "source": source,
        "metadata": dict(metadata),
    }


def _resolve_compat_submit_user(payload: Dict[str, Any]) -> tuple[Dict[str, Any] | None, bool, Dict[str, Any], int]:
    session_user = get_current_user()
    if session_user:
        return session_user, False, {}, 200

    if not _compat_secret_is_authorized():
        return None, False, {"error": "unauthorized", "message": "Compatibility secret required."}, 401

    requested_email = _first_non_empty(payload, "requested_by_email", "user_email", "email").lower()
    if not requested_email:
        return (
            None,
            True,
            {
                "error": "validation_error",
                "message": "requested_by_email is required when using the compatibility shared secret.",
            },
            400,
        )

    user = current_app.config["USER_STORE"].get_user_by_email(requested_email)
    if not user:
        return None, True, {"error": "not_found", "message": "Requested compatibility user was not found."}, 404
    return user, True, {}, 200


def _is_admin_like(user: Dict[str, Any] | None) -> bool:
    role = str((user or {}).get("role", "")).strip().lower()
    return role in {"master", "admin"}


def _can_access_job(user: Dict[str, Any] | None, job: Dict[str, Any] | None) -> bool:
    if not user or not job:
        return False
    if _is_admin_like(user):
        return True
    return int(user.get("id") or 0) == int(job.get("requested_by_user_id") or 0)


def _safe_limit(value: Any, *, default: int = 50, max_limit: int = 200) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, max_limit))


def _utc_day_window(now: datetime | None = None) -> tuple[str, str]:
    reference = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    day_start = reference.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day_start = day_start + timedelta(days=1)
    return (
        day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        next_day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _build_risk_access_snapshot(user: Dict[str, Any] | None, store: Any) -> Dict[str, Any]:
    if not user:
        return build_risk_access(user, jobs_used_today=0)
    role = str((user or {}).get("role", "")).strip().lower()
    if role in {"master", "admin"}:
        return build_risk_access(user, jobs_used_today=0)
    try:
        user_id = int((user or {}).get("id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    if user_id <= 0:
        return build_risk_access(user, jobs_used_today=0)
    created_from_utc, created_until_utc = _utc_day_window()
    succeeded_today = store.count_succeeded_jobs_for_user_between(
        requested_by_user_id=user_id,
        finished_from_utc=created_from_utc,
        finished_until_utc=created_until_utc,
    )
    active_today = store.count_active_jobs_for_user_between(
        requested_by_user_id=user_id,
        created_from_utc=created_from_utc,
        created_until_utc=created_until_utc,
    )
    return build_risk_access(
        user,
        jobs_used_today=succeeded_today,
        active_incomplete_jobs_today=active_today,
    )


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return float(default)


def _quality_to_signal(quality_score: float) -> int:
    return max(0, min(100, int(round((quality_score - 1.0) / 9.0 * 100.0))))


def _build_job_plan_snapshot(risk_access: Dict[str, Any]) -> Dict[str, Any]:
    runtime_disabled_services = _runtime_disabled_services_for_snapshot(risk_access)
    return {
        "plan_id": str(risk_access.get("plan_id", "")).strip().lower(),
        "plan_name": str(risk_access.get("plan_name", "")).strip(),
        "role": str(risk_access.get("role", "")).strip().lower(),
        "api_service_tier": str(risk_access.get("api_service_tier", "")).strip().lower(),
        "result_output_tier": str(risk_access.get("result_output_tier", "")).strip().lower(),
        "provider_visibility": str(risk_access.get("provider_visibility", "")).strip().lower(),
        "visible_categories": list(risk_access.get("visible_categories") or []),
        "can_view_red_flags": bool(risk_access.get("can_view_red_flags")),
        "can_view_component_scores": bool(risk_access.get("can_view_component_scores")),
        "social_signal_enabled": bool(risk_access.get("social_signal_enabled")),
        "runtime_disabled_services": runtime_disabled_services,
        "runtime_skip_social_fetch": not bool(risk_access.get("social_signal_enabled")),
    }


def _runtime_disabled_services_for_snapshot(plan_snapshot: Dict[str, Any]) -> list[str]:
    api_service_tier = str(plan_snapshot.get("api_service_tier", "")).strip().lower()
    social_signal_enabled = bool(plan_snapshot.get("social_signal_enabled", True))

    disabled_services: set[str] = set()
    if not social_signal_enabled:
        disabled_services.update(STANDARD_RUNTIME_DISABLED_SERVICES)
    if api_service_tier == "primary":
        disabled_services.update(PRIMARY_RUNTIME_DISABLED_SERVICES)
    return sorted(disabled_services)


def _runtime_env_overrides_for_snapshot(plan_snapshot: Dict[str, Any]) -> Dict[str, str]:
    api_service_tier = str(plan_snapshot.get("api_service_tier", "")).strip().lower()
    runtime_disabled_services = [
        str(service_id).strip().lower()
        for service_id in list(plan_snapshot.get("runtime_disabled_services") or [])
        if str(service_id).strip()
    ]
    runtime_skip_social_fetch = bool(
        plan_snapshot.get("runtime_skip_social_fetch", not bool(plan_snapshot.get("social_signal_enabled", True)))
    )

    env = {
        "HODLER_PLAN_ID": str(plan_snapshot.get("plan_id", "")).strip().lower(),
        "HODLER_PLAN_ROLE": str(plan_snapshot.get("role", "")).strip().lower(),
        "HODLER_PLAN_RUNTIME_TIER": api_service_tier,
        "HODLER_PLAN_SKIP_SOCIAL_FETCH": "1" if runtime_skip_social_fetch else "0",
        "HODLER_CHAINABUSE_CACHE_DB": _chainabuse_cache_db_path(),
    }
    if runtime_disabled_services:
        env["HODLER_PLAN_RUNTIME_DISABLED_SERVICES"] = ",".join(sorted(set(runtime_disabled_services)))
    else:
        env["HODLER_PLAN_RUNTIME_DISABLED_SERVICES"] = ""
    return env


def _plan_snapshot_from_job(job: Dict[str, Any] | None) -> Dict[str, Any]:
    metadata = job.get("metadata") if isinstance(job, dict) else None
    if not isinstance(metadata, dict):
        return {}
    plan_snapshot = metadata.get("plan_snapshot")
    if not isinstance(plan_snapshot, dict):
        return {}
    return dict(plan_snapshot)


def _output_note_for_snapshot(plan_snapshot: Dict[str, Any]) -> str:
    output_tier = str(plan_snapshot.get("result_output_tier", "")).strip().lower()
    if output_tier == "primary":
        return "Free plan output is limited to primary providers, market/behavior summaries, and no red flags."
    if output_tier == "standard":
        return "Basic plan output excludes social-provider signals while preserving the main assessment summary."
    if output_tier == "full":
        return "Full assessment output is enabled for this plan."
    return "Assessment output is restricted until an eligible plan is active."


def _filter_visible_providers(providers_used: list[str], provider_visibility: str) -> list[str]:
    visible = [str(item or "").strip() for item in providers_used if str(item or "").strip()]
    if provider_visibility == "standard":
        filtered = [item for item in visible if item not in SOCIAL_PROVIDERS]
        return filtered or visible
    if provider_visibility == "primary":
        filtered = [item for item in visible if item in PRIMARY_VISIBLE_PROVIDERS]
        if filtered:
            return filtered
        fallback = [item for item in visible if item not in SOCIAL_PROVIDERS]
        return fallback[:3] or visible[:3]
    return visible


def _rebuild_summary_from_components(
    component_scores: Dict[str, Any],
    *,
    excluded_pillars: set[str],
) -> tuple[Dict[str, int], Dict[str, int]]:
    category_totals: Dict[str, list[float]] = {category: [] for category in FULL_RISK_CATEGORIES}
    for pillar, payload in component_scores.items():
        if pillar in excluded_pillars or not isinstance(payload, dict):
            continue
        category = str(payload.get("category", "")).strip().lower()
        if category not in category_totals:
            continue
        category_totals[category].append(_safe_float(payload.get("quality_score"), default=5.0))

    signals: Dict[str, int] = {}
    category_scores: Dict[str, int] = {}
    for category, values in category_totals.items():
        if not values:
            continue
        signal = _quality_to_signal(sum(values) / len(values))
        signals[f"{category}_signal"] = signal
        category_scores[category] = signal
    return signals, category_scores


def _shape_result_payload_for_plan(result_payload: Dict[str, Any], plan_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(result_payload or {})
    output_tier = str(plan_snapshot.get("result_output_tier", "")).strip().lower() or "full"
    provider_visibility = str(plan_snapshot.get("provider_visibility", "")).strip().lower() or "full"
    visible_categories = [
        str(item).strip().lower()
        for item in list(plan_snapshot.get("visible_categories") or list(FULL_RISK_CATEGORIES))
        if str(item).strip().lower() in FULL_RISK_CATEGORIES
    ]
    if not visible_categories:
        visible_categories = list(FULL_RISK_CATEGORIES)
    can_view_red_flags = bool(plan_snapshot.get("can_view_red_flags", True))
    can_view_component_scores = bool(plan_snapshot.get("can_view_component_scores", True))
    social_signal_enabled = bool(plan_snapshot.get("social_signal_enabled", True))

    excluded_pillars: set[str] = set()
    if not social_signal_enabled:
        excluded_pillars.add("social_data")

    raw_component_scores = payload.get("component_scores")
    component_scores = raw_component_scores if isinstance(raw_component_scores, dict) else {}
    if component_scores:
        filtered_component_scores = {
            str(pillar): dict(details)
            for pillar, details in component_scores.items()
            if isinstance(details, dict) and str(pillar) not in excluded_pillars
        }
        rebuilt_signals, rebuilt_categories = _rebuild_summary_from_components(
            filtered_component_scores,
            excluded_pillars=set(),
        )
        if rebuilt_signals:
            payload["signals"] = rebuilt_signals
        if rebuilt_categories:
            payload["category_scores"] = rebuilt_categories
        if can_view_component_scores:
            payload["component_scores"] = filtered_component_scores
        else:
            payload.pop("component_scores", None)
            payload["component_scores_note"] = "Detailed pillar scores unlock on Pro and Enterprise plans."

    raw_signals = payload.get("signals")
    if isinstance(raw_signals, dict):
        payload["signals"] = {
            key: value
            for key, value in raw_signals.items()
            if key.replace("_signal", "") in visible_categories
        }
    raw_categories = payload.get("category_scores")
    if isinstance(raw_categories, dict):
        payload["category_scores"] = {
            key: value
            for key, value in raw_categories.items()
            if str(key).strip().lower() in visible_categories
        }

    providers_used = payload.get("providers_used")
    if isinstance(providers_used, list):
        payload["providers_used"] = _filter_visible_providers(providers_used, provider_visibility)

    if can_view_red_flags:
        payload["red_flags_available"] = True
        payload.pop("red_flags_note", None)
    else:
        payload["red_flags"] = []
        payload["red_flags_available"] = False
        payload["red_flags_note"] = "Red flags unlock on Basic, Pro, and Enterprise plans."

    if not social_signal_enabled:
        payload.pop("social_report_text", None)

    payload["plan_output_tier"] = output_tier
    payload["provider_visibility"] = provider_visibility
    payload["visible_categories"] = visible_categories
    payload["component_scores_available"] = can_view_component_scores
    payload["social_signal_enabled"] = social_signal_enabled
    payload["plan_output_note"] = _output_note_for_snapshot(plan_snapshot)
    return payload


def _queue_risk_job_for_user(
    user: Dict[str, Any] | None,
    payload: Dict[str, Any],
    *,
    source_default: str,
) -> tuple[Dict[str, Any], int]:
    store = current_app.config["RISK_JOB_STORE"]
    risk_access = _build_risk_access_snapshot(user, store)
    normalized_payload = _normalize_risk_job_payload(payload, source_default=source_default)
    token_address = normalized_payload["token_address"]
    if not token_address:
        return (
            {
                "error": "validation_error",
                "message": "token_address is required",
                "risk_access": risk_access,
                "normalized_request": normalized_payload,
            },
            400,
        )

    if not is_allowed_token_chain_hint(normalized_payload["token_chain"]):
        allowed = ", ".join(CANONICAL_TOKEN_CHAIN_CODES)
        return (
            {
                "error": "validation_error",
                "message": (
                    "token_chain must be empty (auto-detect) or a supported network code "
                    f"({allowed})."
                ),
                "risk_access": risk_access,
                "normalized_request": normalized_payload,
            },
            400,
        )

    normalized_token, val_err = normalize_and_validate_token_address(
        normalized_payload["token_chain"],
        token_address,
    )
    if val_err:
        return (
            {
                "error": "validation_error",
                "message": val_err,
                "risk_access": risk_access,
                "normalized_request": normalized_payload,
            },
            400,
        )
    token_address = normalized_token

    blacklist_match = current_app.config["USER_STORE"].get_active_blacklist_match(
        entry_type="wallet_address",
        value=token_address.lower(),
    )
    if blacklist_match:
        return (
            {
                "error": "blacklisted_wallet",
                "message": "This wallet or token address is blocked by policy.",
                "risk_access": risk_access,
                "normalized_request": normalized_payload,
            },
            403,
        )

    if not risk_access.get("has_scan_access"):
        return (
            {
                "error": "risk_plan_required",
                "message": str(risk_access.get("access_note") or "Your current plan cannot start live assessments."),
                "risk_access": risk_access,
                "normalized_request": normalized_payload,
            },
            403,
        )
    if not risk_access.get("can_submit_assessments"):
        return (
            {
                "error": "daily_scan_limit_reached",
                "message": str(risk_access.get("access_note") or "You reached today's scan limit."),
                "risk_access": risk_access,
                "normalized_request": normalized_payload,
            },
            429,
        )
    if normalized_payload["mode"] == "eu" and not risk_access.get("can_use_eu_mode"):
        return (
            {
                "error": "risk_mode_forbidden",
                "message": "EU mode requires an active Basic, Pro, or Enterprise plan.",
                "risk_access": risk_access,
                "normalized_request": normalized_payload,
            },
            403,
        )

    job_metadata = dict(normalized_payload["metadata"])
    job_metadata["plan_snapshot"] = _build_job_plan_snapshot(risk_access)
    job = store.create_job(
        requested_by_user_id=int((user or {}).get("id") or 0),
        requested_by_role=str((user or {}).get("role") or "").strip().lower(),
        requested_by_email=str((user or {}).get("email") or "").strip().lower(),
        token_address=token_address,
        token_chain=normalized_payload["token_chain"],
        mode=normalized_payload["mode"],
        source=normalized_payload["source"],
        metadata=job_metadata,
    )
    updated_risk_access = _build_risk_access_snapshot(user, store)
    return (
        {
            "status": "queued",
            "execution_model": "async_queue",
            "job": job,
            "risk_access": updated_risk_access,
            "normalized_request": normalized_payload,
        },
        201,
    )


def _prepare_live_list_items_for_queue(
    *,
    user: Dict[str, Any] | None,
    items: list[Dict[str, Any]],
    mode: str,
    source: str,
    effective_cap: int,
    shared_metadata: Dict[str, Any],
) -> tuple[list[Dict[str, str]], list[Dict[str, Any]], Dict[str, Any]]:
    """Validate token rows for a Live Assessment list run (single queued job, many tokens)."""
    store = current_app.config["RISK_JOB_STORE"]
    risk_access = _build_risk_access_snapshot(user, store)
    prepared: list[Dict[str, str]] = []
    rejected: list[Dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            rejected.append({"index": idx, "error": "invalid_item", "message": "Each item must be an object"})
            continue
        if len(prepared) >= effective_cap:
            rejected.append(
                {
                    "index": idx,
                    "error": "batch_limit",
                    "message": (
                        f"This run can include at most {effective_cap} token(s) for your plan and remaining quota."
                    ),
                }
            )
            continue
        item_meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        merged_meta = {**shared_metadata, **item_meta}
        row_mode = str(raw.get("mode") or mode or "global").strip().lower()
        if row_mode not in {"global", "eu"}:
            row_mode = "global"
        norm = _normalize_risk_job_payload(
            {**raw, "mode": row_mode, "metadata": merged_meta},
            source_default=source,
        )
        chain = str(norm.get("token_chain") or "").strip()
        if not chain:
            rejected.append(
                {
                    "index": idx,
                    "error": "validation_error",
                    "message": "token_chain is required for list assessments (no auto-detect).",
                    "token_address": norm.get("token_address"),
                }
            )
            continue
        addr = str(norm.get("token_address") or "").strip()
        dedupe_key = (chain.lower(), addr.lower())
        if dedupe_key in seen_keys:
            rejected.append(
                {
                    "index": idx,
                    "error": "duplicate_in_batch",
                    "message": "Duplicate chain/address in list.",
                }
            )
            continue
        seen_keys.add(dedupe_key)

        normalized_token, val_err = normalize_and_validate_token_address(chain, addr)
        if val_err:
            rejected.append(
                {
                    "index": idx,
                    "error": "validation_error",
                    "message": val_err,
                    "token_address": addr,
                    "token_chain": chain,
                }
            )
            continue

        blacklist_match = current_app.config["USER_STORE"].get_active_blacklist_match(
            entry_type="wallet_address",
            value=normalized_token.lower(),
        )
        if blacklist_match:
            rejected.append(
                {
                    "index": idx,
                    "error": "blacklisted_wallet",
                    "message": "This wallet or token address is blocked by policy.",
                    "token_address": normalized_token,
                }
            )
            continue

        prepared_item = {
            "token_address": normalized_token,
            "token_chain": chain,
            "mode": str(norm.get("mode") or row_mode),
        }
        token_symbol = str(raw.get("token_symbol") or raw.get("symbol") or "").strip()
        token_name = str(raw.get("token_name") or raw.get("name") or "").strip()
        if token_symbol:
            prepared_item["token_symbol"] = token_symbol
        if token_name:
            prepared_item["token_name"] = token_name
        prepared.append(prepared_item)

    return prepared, rejected, risk_access


def _queue_risk_jobs_batch_for_user(
    user: Dict[str, Any] | None,
    payload: Dict[str, Any],
    *,
    source_default: str,
) -> tuple[Dict[str, Any], int]:
    """Queue up to :data:`RISK_JOB_BATCH_MAX_ITEMS` jobs; each item must include an explicit ``token_chain``."""
    store = current_app.config["RISK_JOB_STORE"]
    base_access = _build_risk_access_snapshot(user, store)
    items = payload.get("items")
    if not isinstance(items, list):
        return (
            {
                "error": "validation_error",
                "message": "items must be a list",
                "risk_access": base_access,
            },
            400,
        )
    if not items:
        return (
            {
                "error": "validation_error",
                "message": "items must be a non-empty list",
                "risk_access": base_access,
            },
            400,
        )

    if not _multi_token_batch_allowed(base_access):
        return (
            {
                "error": "multi_token_batch_forbidden",
                "message": "Multi-token batch scans require Basic, Pro, or Enterprise.",
                "risk_access": base_access,
            },
            403,
        )

    effective_cap = effective_risk_batch_run_cap(base_access)
    if effective_cap <= 0:
        return (
            {
                "error": "daily_scan_limit_reached",
                "message": "No scan capacity left today for a batch run.",
                "risk_access": base_access,
            },
            429,
        )

    shared_meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    batch_source = _first_non_empty(payload, "source").lower() or str(source_default or "web_portal").strip().lower()

    prepared: list[Dict[str, Any]] = []
    rejected: list[Dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            rejected.append({"index": idx, "error": "invalid_item", "message": "Each item must be an object"})
            continue
        if len(prepared) >= effective_cap:
            rejected.append(
                {
                    "index": idx,
                    "error": "batch_limit",
                    "message": (
                        f"This batch can queue at most {effective_cap} token(s) for your plan and remaining quota."
                    ),
                }
            )
            continue
        item_meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        merged_meta = {**shared_meta, **item_meta}
        norm = _normalize_risk_job_payload({**raw, "metadata": merged_meta}, source_default=batch_source)
        chain = str(norm.get("token_chain") or "").strip()
        if not chain:
            rejected.append(
                {
                    "index": idx,
                    "error": "validation_error",
                    "message": "token_chain is required for batch assessments (no auto-detect).",
                    "token_address": norm.get("token_address"),
                }
            )
            continue
        addr = str(norm.get("token_address") or "").strip()
        dedupe_key = (chain.lower(), addr.lower())
        if dedupe_key in seen_keys:
            rejected.append(
                {
                    "index": idx,
                    "error": "duplicate_in_batch",
                    "message": "Duplicate chain/address in batch.",
                }
            )
            continue
        seen_keys.add(dedupe_key)
        prepared.append(norm)

    jobs_out: list[Dict[str, Any]] = []
    final_access = base_access
    for norm in prepared:
        item_payload = {
            "token_address": norm["token_address"],
            "token_chain": norm["token_chain"],
            "mode": norm["mode"],
            "source": batch_source,
            "metadata": norm["metadata"],
        }
        resp, code = _queue_risk_job_for_user(user, item_payload, source_default=batch_source)
        final_access = resp.get("risk_access", final_access)
        resp.pop("normalized_request", None)
        if code == 201 and resp.get("job"):
            jobs_out.append(resp["job"])
        else:
            rejected.append(
                {
                    "token_address": norm.get("token_address"),
                    "token_chain": norm.get("token_chain"),
                    "error": resp.get("error"),
                    "message": resp.get("message"),
                }
            )

    if not jobs_out:
        err = next((r for r in rejected if r.get("error") == "daily_scan_limit_reached"), None)
        if err:
            return (
                {
                    "status": "rejected",
                    "jobs": [],
                    "rejected": rejected,
                    "risk_access": final_access,
                },
                429,
            )
        return (
            {
                "status": "rejected",
                "jobs": [],
                "rejected": rejected,
                "risk_access": final_access,
            },
            400,
        )

    status_label = "ok" if not rejected else "partial"
    return (
        {
            "status": status_label,
            "jobs": jobs_out,
            "rejected": rejected,
            "risk_access": final_access,
        },
        200,
    )


def _crypto_list_api_forbidden():
    return jsonify({"error": "forbidden", "message": "You do not have access to token lists."}), 403


def _token_editor_basic_forbidden(message: str):
    return jsonify({"error": "forbidden", "message": message}), 403


def _compat_result_from_job(job: Dict[str, Any]) -> Dict[str, Any] | None:
    artifacts = job.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("artifact_kind", "")).strip().lower() != "risk_summary":
            continue
        metadata = artifact.get("metadata")
        if isinstance(metadata, dict):
            return metadata
    return None


def _build_compat_job_payload(job: Dict[str, Any], *, include_events: bool, include_artifacts: bool) -> Dict[str, Any]:
    payload = {
        "ok": True,
        "legacy_format_version": "2026-04-07",
        "job_id": str(job.get("job_id", "")).strip(),
        "status": str(job.get("status", "")).strip().lower(),
        "stage": str(job.get("stage", "")).strip().lower(),
        "progress": int(job.get("progress") or 0),
        "message": str(job.get("summary_message", "")).strip(),
        "error_code": str(job.get("error_code", "")).strip(),
        "error_message": str(job.get("error_message", "")).strip(),
        "token_address": str(job.get("token_address", "")).strip().lower(),
        "chain": str(job.get("token_chain", "")).strip().lower(),
        "mode": str(job.get("mode", "")).strip().lower(),
        "source": str(job.get("source", "")).strip().lower(),
        "queued_at_utc": str(job.get("created_at_utc", "")).strip(),
        "started_at_utc": str(job.get("started_at_utc", "")).strip(),
        "finished_at_utc": str(job.get("finished_at_utc", "")).strip(),
        "job_url": f"/api/v1/risk/jobs/{str(job.get('job_id', '')).strip()}",
        "poll_url": f"/api/v1/risk/compat/jobs/{str(job.get('job_id', '')).strip()}",
        "result": _compat_result_from_job(job),
    }
    if include_events:
        payload["events"] = job.get("events") if isinstance(job.get("events"), list) else []
    if include_artifacts:
        payload["artifacts"] = job.get("artifacts") if isinstance(job.get("artifacts"), list) else []
    return payload


def _risk_job_stale_running_minutes() -> int:
    settings = current_app.config["SETTINGS"]
    return max(5, int(getattr(settings, "risk_job_stale_running_minutes", 20) or 20))


def _normalize_runtime_risk_jobs(store: Any) -> None:
    store.mark_stale_running_jobs_failed(
        stale_running_minutes=_risk_job_stale_running_minutes(),
    )


def _build_result_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    token_address = str(job.get("token_address", "")).strip().lower()
    token_chain = str(job.get("token_chain", "")).strip().lower() or "unknown"
    mode = str(job.get("mode", "")).strip().lower() or "global"
    seed_material = f"{token_address}:{token_chain}:{mode}"
    digest = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    score = int(digest[:8], 16) % 100 + 1
    if score <= 30:
        risk_band = "low"
    elif score <= 69:
        risk_band = "medium"
    else:
        risk_band = "high"
    confidence = 70 + (int(digest[8:10], 16) % 26)

    market_signal = int(digest[10:12], 16) % 100
    liquidity_signal = int(digest[12:14], 16) % 100
    behavior_signal = int(digest[14:16], 16) % 100
    contract_signal = int(digest[16:18], 16) % 100

    red_flags: list[str] = []
    if risk_band == "high":
        red_flags.append("elevated_composite_risk")
    if contract_signal < 35:
        red_flags.append("contract_integrity_signal_low")
    if liquidity_signal < 30:
        red_flags.append("liquidity_depth_signal_low")
    if market_signal < 25:
        red_flags.append("market_momentum_signal_low")

    market_cap_usd = 500000 + (int(digest[18:24], 16) % 25000000)
    volume_24h_usd = 40000 + (int(digest[24:30], 16) % 4500000)
    liquidity_usd = 25000 + (int(digest[30:36], 16) % 5000000)
    holders = 150 + (int(digest[36:42], 16) % 250000)
    social_part = int(digest[42:44], 16) % 8
    generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result_payload = {
        "token_address": token_address,
        "token_chain": token_chain,
        "mode": mode,
        "risk_score": score,
        "total_score_minus_social": float(max(1, score - social_part)),
        "social_risk_contribution": float(min(8, social_part)),
        "risk_band": risk_band,
        "confidence_pct": confidence,
        "category_confidence_pct": {
            "market": max(0, min(100, confidence - 4)),
            "liquidity": max(0, min(100, confidence - 1)),
            "behavior": max(0, min(100, confidence - 3)),
            "contract": max(0, min(100, confidence - 2)),
        },
        "signals": {
            "market_signal": market_signal,
            "liquidity_signal": liquidity_signal,
            "behavior_signal": behavior_signal,
            "contract_signal": contract_signal,
        },
        # Desktop-parity friendly structure for downstream UI binding.
        "key_metrics": {
            "market_cap_usd": market_cap_usd,
            "volume_24h_usd": volume_24h_usd,
            "liquidity_usd": liquidity_usd,
            "holders": holders,
        },
        "category_scores": {
            "market": market_signal,
            "liquidity": liquidity_signal,
            "behavior": behavior_signal,
            "contract": contract_signal,
        },
        "red_flags": red_flags,
        "providers_used": [
            "CoinGecko",
            "Bitquery",
            "DeFiLlama",
            "Alchemy",
            "1inch",
            "Chainalysis Oracle",
            "OFAC",
            "Etherscan",
        ],
        "generated_at_utc": generated_at_utc,
    }
    return _shape_result_payload_for_plan(result_payload, _plan_snapshot_from_job(job))


def _resolve_worker_process_script() -> str:
    """Locate the out-of-process worker script."""
    candidates = [
        os.getenv("RISK_WORKER_PROCESS_SCRIPT", ""),
        os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "risk", "risk_worker_process.py"),
        "/opt/hodler-suite/web_portal/deploy/risk/risk_worker_process.py",
    ]
    for candidate in candidates:
        path = str(candidate or "").strip()
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return ""


def _resolve_engine_root() -> str:
    """Locate the legacy engine directory (scripts/v2.0)."""
    candidates = [
        os.getenv("RISK_ENGINE_ROOT", ""),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."),
        "/opt/hodler-suite/scripts/v2.0",
        "/opt/defi-risk/app/scripts/v2.0",
    ]
    for candidate in candidates:
        path = str(candidate or "").strip()
        if not path:
            continue
        abs_path = os.path.abspath(path)
        engine_file = os.path.join(abs_path, "defi_complete_risk_assessment_clean.py")
        if os.path.isfile(engine_file):
            return abs_path
    return ""


def _env_file_path() -> str:
    candidates = [
        os.getenv("RISK_ENGINE_ENV_FILE", ""),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".env"),
        "/opt/hodler-suite/.env",
    ]
    for candidate in candidates:
        path = str(candidate or "").strip()
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return ""


def _run_claimed_job(store, job: Dict[str, Any], *, worker_id: str) -> Dict[str, Any]:
    job_id = str(job.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("missing_job_id")

    token_address = str(job.get("token_address", "")).strip()
    token_chain = str(job.get("token_chain", "")).strip() or "eth"
    mode = str(job.get("mode", "")).strip() or "global"

    worker_script = _resolve_worker_process_script()
    engine_root = _resolve_engine_root()
    use_real_engine = bool(worker_script and engine_root)

    if use_real_engine:
        batch_jobs: list[Dict[str, Any]] | None = None
        meta = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
        live_entries = meta.get("live_list_entries")
        if (
            bool(meta.get("live_assessment_single_job"))
            and isinstance(live_entries, list)
            and len(live_entries) > 1
        ):
            batch_jobs = []
            for ent in live_entries:
                if not isinstance(ent, dict):
                    continue
                row = dict(job)
                row["token_address"] = str(ent.get("token_address", "")).strip()
                row["token_chain"] = str(ent.get("token_chain", "")).strip() or token_chain
                row["mode"] = str(ent.get("mode", "") or mode).strip() or mode
                row["token_symbol"] = str(ent.get("token_symbol", "")).strip()
                row["token_name"] = str(ent.get("token_name", "")).strip()
                batch_jobs.append(row)
            if len(batch_jobs) <= 1:
                batch_jobs = None
        else:
            batch_ids_raw = job.get("_worker_batch_job_ids")
            if isinstance(batch_ids_raw, list) and len(batch_ids_raw) > 1:
                batch_jobs = []
                for jid in batch_ids_raw:
                    row = store.get_job(str(jid).strip())
                    if row:
                        batch_jobs.append(row)
                if len(batch_jobs) <= 1:
                    batch_jobs = None
        return _run_real_engine(
            store=store,
            job=job,
            job_id=job_id,
            token_address=token_address,
            token_chain=token_chain,
            mode=mode,
            worker_id=worker_id,
            worker_script=worker_script,
            engine_root=engine_root,
            batch_jobs=batch_jobs,
        )

    current_app.logger.warning(
        "risk_worker_using_placeholder job=%s reason=engine_not_found "
        "worker_script=%s engine_root=%s",
        job_id, bool(worker_script), bool(engine_root),
    )
    return _run_placeholder(store=store, job=job, job_id=job_id, worker_id=worker_id)


def _run_real_engine(
    *,
    store,
    job: Dict[str, Any],
    job_id: str,
    token_address: str,
    token_chain: str,
    mode: str,
    worker_id: str,
    worker_script: str,
    engine_root: str,
    batch_jobs: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Spawn the real scoring engine as a background subprocess.

    The subprocess reports progress and results back via the events API.
    This function returns immediately so the Gunicorn worker is not blocked
    (the engine can run for minutes).

    When ``batch_jobs`` is set (same ``list_batch_id``), one subprocess imports the engine
    once and serially assesses every job in the batch.
    """
    settings = current_app.config.get("SETTINGS")
    shared_secret = str(getattr(settings, "risk_worker_shared_secret", "") or "").strip()
    base_url = str(os.getenv("RISK_WORKER_BASE_URL", "http://127.0.0.1:5050")).strip().rstrip("/")
    python_bin = str(
        os.getenv("RISK_WORKER_PYTHON", sys.executable)
    ).strip() or sys.executable
    env_file = _env_file_path()
    child_env = os.environ.copy()
    child_env.update(_runtime_env_overrides_for_snapshot(_plan_snapshot_from_job(job)))
    if settings is not None:
        vp = str(getattr(settings, "credentials_vault_path", "") or "").strip()
        if vp:
            child_env["CREDENTIALS_VAULT_PATH"] = vp
        vm = str(getattr(settings, "vault_master_password", "") or "").strip()
        if vm:
            child_env["VAULT_MASTER_PASSWORD"] = vm

    store.update_job_state(
        job_id=job_id,
        status="running",
        stage="fetching",
        progress=5,
        summary_message="Launching risk engine...",
        event_type="worker_stage",
        details={"worker_id": worker_id, "engine": "real"},
    )

    cmd = [
        python_bin,
        worker_script,
        "--job-id",
        job_id,
        "--token-address",
        token_address,
        "--chain",
        token_chain,
        "--mode",
        mode,
        "--api-base-url",
        base_url,
        "--worker-secret",
        shared_secret,
        "--engine-root",
        engine_root,
    ]
    command_meta = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
    command_token_symbol = str(
        job.get("token_symbol") or command_meta.get("token_symbol") or ""
    ).strip()
    command_token_name = str(
        job.get("token_name") or command_meta.get("token_name") or ""
    ).strip()
    if command_token_symbol:
        cmd.extend(["--token-symbol", command_token_symbol])
    if command_token_name:
        cmd.extend(["--token-name", command_token_name])
    batch_file_path = ""
    if batch_jobs:
        spec_jobs: list[Dict[str, str]] = []
        for row in batch_jobs:
            spec_jobs.append(
                {
                    "job_id": str(row.get("job_id", "")).strip(),
                    "token_address": str(row.get("token_address", "")).strip(),
                    "token_chain": str(row.get("token_chain", "")).strip() or "eth",
                    "mode": str(row.get("mode", "")).strip() or "global",
                    "token_symbol": str(row.get("token_symbol", "")).strip(),
                    "token_name": str(row.get("token_name", "")).strip(),
                }
            )
        try:
            fd, batch_file_path = tempfile.mkstemp(
                prefix="hodler-risk-batch-",
                suffix=".json",
            )
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump({"jobs": spec_jobs}, tmp, ensure_ascii=True)
            cmd.extend(["--batch-json", batch_file_path])
        except OSError as exc:
            current_app.logger.exception("risk_worker_batch_spec_write_failed error=%s", exc)
            for row in batch_jobs:
                store.update_job_state(
                    job_id=str(row.get("job_id", "")).strip(),
                    status="failed",
                    stage="failed",
                    progress=100,
                    summary_message="Batch worker launch failed",
                    error_code="worker_batch_spec_error",
                    error_message=str(exc)[:500],
                    event_type="worker_failed",
                    details={"worker_id": worker_id},
                )
            return {"job": store.get_job(job_id), "result": None, "error": str(exc)}

    if env_file:
        cmd.extend(["--env-file", env_file])

    current_app.logger.info(
        "risk_worker_subprocess_start job=%s batch=%s token=%s chain=%s",
        job_id,
        len(batch_jobs) if batch_jobs else 1,
        token_address[:12],
        token_chain,
    )

    child_env.setdefault("PYTHONUNBUFFERED", "1")
    stderr_dest: Any = subprocess.DEVNULL
    stderr_log_path = str(os.getenv("RISK_WORKER_SUBPROCESS_STDERR_LOG", "") or "").strip()
    stderr_handle = None
    if stderr_log_path:
        try:
            log_dir = os.path.dirname(stderr_log_path)
            if log_dir:
                os.makedirs(log_dir, mode=0o755, exist_ok=True)
            stderr_handle = open(stderr_log_path, "a", encoding="utf-8", errors="replace")
            batch_note = f" batch_jobs={len(batch_jobs)}" if batch_jobs else ""
            stderr_handle.write(
                f"\n--- risk_worker_subprocess job={job_id}{batch_note} token={token_address[:10]}... ---\n"
            )
            stderr_handle.flush()
            stderr_dest = stderr_handle
        except OSError as exc:
            current_app.logger.warning(
                "risk_worker_stderr_log_open_failed path=%s error=%s",
                stderr_log_path,
                exc,
            )

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=stderr_dest,
            cwd=engine_root,
            env=child_env,
            start_new_session=True,
        )
    except Exception as exc:
        fail_ids = [job_id]
        if batch_jobs:
            fail_ids = [str(r.get("job_id", "")).strip() for r in batch_jobs if r.get("job_id")]
        for fid in fail_ids:
            if fid:
                store.update_job_state(
                    job_id=fid,
                    status="failed",
                    stage="failed",
                    progress=100,
                    summary_message="Engine launch failed",
                    error_code="worker_launch_error",
                    error_message=str(exc)[:500],
                    event_type="worker_failed",
                    details={"worker_id": worker_id},
                )
        return {"job": store.get_job(job_id), "result": None, "error": str(exc)}

    return {
        "job": store.get_job(job_id),
        "result": None,
        "status": "spawned",
        "detail": "Engine subprocess launched; results will arrive via events API",
    }


def _run_placeholder(
    *, store, job: Dict[str, Any], job_id: str, worker_id: str
) -> Dict[str, Any]:
    """Deterministic placeholder results (legacy fallback)."""
    store.update_job_state(
        job_id=job_id,
        status="running",
        stage="fetching",
        progress=20,
        summary_message="Fetching token data",
        event_type="worker_stage",
        details={"worker_id": worker_id, "engine": "placeholder"},
    )
    store.update_job_state(
        job_id=job_id,
        status="running",
        stage="analyzing",
        progress=65,
        summary_message="Analyzing security & market data",
        event_type="worker_stage",
        details={"worker_id": worker_id},
    )

    result_payload = _build_result_payload(job)
    store.add_job_artifact(
        job_id=job_id,
        artifact_kind="risk_summary",
        artifact_uri=f"inline:risk_summary:{job_id}",
        content_type="application/json",
        metadata=result_payload,
    )
    store.update_job_state(
        job_id=job_id,
        status="running",
        stage="finalizing",
        progress=90,
        summary_message="Generating final reports...",
        event_type="worker_stage",
        details={"worker_id": worker_id, "risk_band": result_payload.get("risk_band")},
    )
    updated = store.update_job_state(
        job_id=job_id,
        status="succeeded",
        stage="succeeded",
        progress=100,
        summary_message="Risk assessment complete!",
        event_type="worker_completed",
        details={
            "worker_id": worker_id,
            "engine": "placeholder",
            "risk_band": result_payload.get("risk_band"),
        },
    )
    return {"job": updated, "result": result_payload}


@risk_bp.get("/access")
@api_login_required
def get_risk_access_snapshot():
    """Return current plan quota snapshot (e.g. for Live Assessment stat cards after a job completes)."""
    user = get_current_user()
    store = current_app.config["RISK_JOB_STORE"]
    return jsonify({"risk_access": _build_risk_access_snapshot(user, store)}), 200


@risk_bp.get("/chains")
def list_supported_risk_chains():
    """Return the canonical chain dropdown (value + label) for clients and future batch flows.

    Unauthenticated: this is non-sensitive product metadata aligned with ``hodler_chain_codes``
    and Live Assessment. Job submission still validates via ``is_allowed_token_chain_hint``.
    """
    return jsonify({"chains": live_assessment_chain_options()}), 200


@risk_bp.post("/jobs")
@api_login_required
def create_risk_job():
    user = get_current_user()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    response_payload, status_code = _queue_risk_job_for_user(user, payload, source_default="web_portal")
    response_payload.pop("normalized_request", None)
    return jsonify(response_payload), status_code


@risk_bp.post("/jobs/batch")
@api_login_required
def create_risk_jobs_batch():
    user = get_current_user()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    body, status_code = _queue_risk_jobs_batch_for_user(user, payload, source_default="web_portal_batch")
    return jsonify(body), status_code


@risk_bp.get("/token-lists")
@api_login_required
def api_list_token_lists():
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "crypto_list_view")
    if not ent["allowed"]:
        return _crypto_list_api_forbidden()
    tstore = current_app.config["TOKEN_LIST_STORE"]
    rows = tstore.list_lists_for_user(user_id=int(user["id"]))
    return jsonify({"lists": rows}), 200


@risk_bp.post("/token-lists")
@api_login_required
def api_create_token_list():
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    name = str(payload.get("name", "")).strip()
    tstore = current_app.config["TOKEN_LIST_STORE"]
    row = tstore.create_list(user_id=int(user["id"]), name=name)
    if row is None:
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": "Invalid name or maximum number of lists reached.",
                }
            ),
            400,
        )
    return jsonify({"list": row}), 201


@risk_bp.get("/token-lists/active-scan")
@api_login_required
def api_get_active_scan_token_list():
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "crypto_list_view")
    if not ent["allowed"]:
        return _crypto_list_api_forbidden()
    uid = int((user or {}).get("id") or 0)
    if uid <= 0:
        return jsonify({"error": "unauthorized"}), 401
    tstore = current_app.config["TOKEN_LIST_STORE"]
    active_id = tstore.get_active_scan_list_id(user_id=uid)
    if active_id is None:
        return jsonify({"list": None}), 200
    row = tstore.get_list_with_entries(user_id=uid, list_id=active_id)
    return jsonify({"list": row}), 200


@risk_bp.post("/token-lists/<int:list_id>/activate-for-live-assessment")
@api_login_required
def api_activate_token_list_for_live_assessment(list_id: int):
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    rstore = current_app.config["RISK_JOB_STORE"]
    risk_access = _build_risk_access_snapshot(user, rstore)
    if not risk_access.get("live_assessment_list_mode"):
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "message": "Only Basic, Pro, and Enterprise plans can set a Live Assessment contract list.",
                }
            ),
            403,
        )
    tstore = current_app.config["TOKEN_LIST_STORE"]
    uid = int((user or {}).get("id") or 0)
    if not tstore.set_active_scan_list_id(user_id=uid, list_id=int(list_id)):
        return jsonify({"error": "not_found", "message": "List not found."}), 404
    row = tstore.get_list_with_entries(user_id=uid, list_id=int(list_id))
    return jsonify({"status": "ok", "active_scan_list_id": int(list_id), "list": row}), 200


@risk_bp.delete("/token-lists/active-scan")
@api_login_required
def api_clear_active_scan_token_list():
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    rstore = current_app.config["RISK_JOB_STORE"]
    risk_access = _build_risk_access_snapshot(user, rstore)
    if not risk_access.get("live_assessment_list_mode"):
        return (
            jsonify(
                {
                    "error": "forbidden",
                    "message": "Only Basic, Pro, and Enterprise plans use Live Assessment contract lists.",
                }
            ),
            403,
        )
    tstore = current_app.config["TOKEN_LIST_STORE"]
    uid = int((user or {}).get("id") or 0)
    tstore.set_active_scan_list_id(user_id=uid, list_id=None)
    return jsonify({"status": "cleared"}), 200


@risk_bp.get("/token-lists/<int:list_id>")
@api_login_required
def api_get_token_list(list_id: int):
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "crypto_list_view")
    if not ent["allowed"]:
        return _crypto_list_api_forbidden()
    tstore = current_app.config["TOKEN_LIST_STORE"]
    row = tstore.get_list_with_entries(user_id=int(user["id"]), list_id=list_id)
    if row is None:
        return jsonify({"error": "not_found", "message": "List not found."}), 404
    return jsonify(row), 200


@risk_bp.patch("/token-lists/<int:list_id>")
@api_login_required
def api_rename_token_list(list_id: int):
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    name = str(payload.get("name", "")).strip()
    tstore = current_app.config["TOKEN_LIST_STORE"]
    if not tstore.rename_list(user_id=int(user["id"]), list_id=list_id, name=name):
        return jsonify({"error": "validation_error", "message": "Unable to rename list."}), 400
    row = tstore.get_list_with_entries(user_id=int(user["id"]), list_id=list_id)
    return jsonify(row or {}), 200


@risk_bp.delete("/token-lists/<int:list_id>")
@api_login_required
def api_delete_token_list(list_id: int):
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    tstore = current_app.config["TOKEN_LIST_STORE"]
    if not tstore.delete_list(user_id=int(user["id"]), list_id=list_id):
        return jsonify({"error": "not_found", "message": "List not found."}), 404
    return jsonify({"status": "deleted"}), 200


@risk_bp.post("/token-lists/<int:list_id>/entries")
@api_login_required
def api_add_token_list_entries(list_id: int):
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        return jsonify({"error": "validation_error", "message": "entries must be a list"}), 400
    tstore = current_app.config["TOKEN_LIST_STORE"]
    result = tstore.add_entries(user_id=int(user["id"]), list_id=list_id, entries=raw_entries)
    if result.get("errors") and any(str(e.get("message")) == "list_not_found" for e in result["errors"]):
        return jsonify({"error": "not_found", "message": "List not found."}), 404
    if result.get("errors") and not result.get("added"):
        first_error = result["errors"][0] if isinstance(result["errors"][0], dict) else {}
        body = dict(result)
        body["error"] = "validation_error"
        body["message"] = str(first_error.get("message") or "No valid token entries were provided.")
        return jsonify(body), 400
    return jsonify(result), 200


@risk_bp.post("/token-lists/<int:list_id>/import-csv")
@api_login_required
def api_import_token_list_csv(list_id: int):
    """Import desktop-format ``tokens.csv`` (columns ``address``, ``chain``; optional ``symbol``, ``name``)."""
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))

    upload = request.files.get("file")
    if upload is None or not str(getattr(upload, "filename", "") or "").strip():
        return jsonify({"error": "validation_error", "message": "Missing CSV file (field name: file)."}), 400

    replace_flag = str(request.form.get("replace", "")).strip().lower() in {"1", "true", "yes", "on"}
    raw = upload.read(TOKEN_LIST_CSV_MAX_UPLOAD_BYTES + 1)
    if len(raw) > TOKEN_LIST_CSV_MAX_UPLOAD_BYTES:
        return (
            jsonify(
                {
                    "error": "payload_too_large",
                    "message": f"CSV must be at most {TOKEN_LIST_CSV_MAX_UPLOAD_BYTES} bytes.",
                }
            ),
            413,
        )

    from ..token_list_csv import parse_desktop_tokens_csv

    entries, parse_errors = parse_desktop_tokens_csv(raw)
    if not entries and parse_errors:
        return (
            jsonify(
                {
                    "error": "csv_parse_failed",
                    "message": "No valid rows could be read from the CSV.",
                    "parse_errors": parse_errors,
                }
            ),
            400,
        )
    if not entries:
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": "CSV contained no token rows (need address and chain columns).",
                    "parse_errors": parse_errors,
                }
            ),
            400,
        )

    tstore = current_app.config["TOKEN_LIST_STORE"]
    uid = int(user["id"])
    validation_preview = tstore.validate_entries(entries)
    if replace_flag and not validation_preview.get("normalized"):
        validation_errors = validation_preview.get("errors") or []
        first_error = validation_errors[0] if validation_errors and isinstance(validation_errors[0], dict) else {}
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": str(first_error.get("message") or "No CSV rows passed token validation."),
                    "replace": replace_flag,
                    "parsed_row_count": len(entries),
                    "added": [],
                    "added_count": 0,
                    "skipped_duplicates": 0,
                    "validation_errors": validation_errors,
                    "parse_errors": parse_errors,
                }
            ),
            400,
        )
    if replace_flag:
        if not tstore.clear_all_entries(user_id=uid, list_id=list_id):
            return jsonify({"error": "not_found", "message": "List not found."}), 404

    result = tstore.add_entries(user_id=uid, list_id=list_id, entries=entries)
    if result.get("errors") and any(str(e.get("message")) == "list_not_found" for e in result["errors"]):
        return jsonify({"error": "not_found", "message": "List not found."}), 404
    if result.get("errors") and not result.get("added"):
        first_error = result["errors"][0] if isinstance(result["errors"][0], dict) else {}
        return (
            jsonify(
                {
                    "error": "validation_error",
                    "message": str(first_error.get("message") or "No CSV rows passed token validation."),
                    "replace": replace_flag,
                    "parsed_row_count": len(entries),
                    "added": [],
                    "added_count": 0,
                    "skipped_duplicates": int(result.get("skipped_duplicates") or 0),
                    "validation_errors": result.get("errors") or [],
                    "parse_errors": parse_errors,
                }
            ),
            400,
        )

    detail = tstore.get_list_with_entries(user_id=uid, list_id=list_id)
    return (
        jsonify(
            {
                "status": "ok",
                "replace": replace_flag,
                "parsed_row_count": len(entries),
                "added": result.get("added") or [],
                "added_count": len(result.get("added") or []),
                "skipped_duplicates": int(result.get("skipped_duplicates") or 0),
                "validation_errors": result.get("errors") or [],
                "parse_errors": parse_errors,
                "list": detail,
            }
        ),
        200,
    )


@risk_bp.delete("/token-lists/<int:list_id>/entries/<int:entry_id>")
@api_login_required
def api_delete_token_list_entry(list_id: int, entry_id: int):
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    tstore = current_app.config["TOKEN_LIST_STORE"]
    if not tstore.delete_entry(user_id=int(user["id"]), list_id=list_id, entry_id=entry_id):
        return jsonify({"error": "not_found", "message": "Entry not found."}), 404
    return jsonify({"status": "deleted"}), 200


@risk_bp.post("/token-lists/<int:list_id>/jobs")
@api_login_required
def api_queue_jobs_from_token_list(list_id: int):
    user = get_current_user()
    ent = evaluate_feature_entitlement(user, "token_editor_basic_actions")
    if not ent["allowed"]:
        return _token_editor_basic_forbidden(str(ent.get("message") or "Forbidden"))
    rstore = current_app.config["RISK_JOB_STORE"]
    risk_access = _build_risk_access_snapshot(user, rstore)
    if not _multi_token_batch_allowed(risk_access):
        return (
            jsonify(
                {
                    "error": "multi_token_batch_forbidden",
                    "message": "Multi-token queue requires Basic, Pro, or Enterprise.",
                    "risk_access": risk_access,
                }
            ),
            403,
        )
    effective_cap = effective_risk_batch_run_cap(risk_access)
    if effective_cap <= 0:
        return (
            jsonify(
                {
                    "error": "daily_scan_limit_reached",
                    "message": "No scan capacity left today.",
                    "risk_access": risk_access,
                }
            ),
            429,
        )
    tstore = current_app.config["TOKEN_LIST_STORE"]
    detail = tstore.get_list_with_entries(user_id=int(user["id"]), list_id=list_id)
    if detail is None:
        return jsonify({"error": "not_found", "message": "List not found."}), 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    mode = _first_non_empty(payload, "mode", "assessment_mode", "risk_mode").lower() or "global"
    if mode not in {"global", "eu"}:
        mode = "global"
    entries = detail.get("entries") if isinstance(detail.get("entries"), list) else []
    entries = [e for e in entries if isinstance(e, dict)]
    if not entries:
        return jsonify({"error": "validation_error", "message": "List has no tokens to queue."}), 400
    total_entries = len(entries)
    truncated = total_entries > effective_cap
    entries = entries[:effective_cap]
    items = [
        {
            "token_address": str(e.get("token_address", "")).strip(),
            "token_chain": str(e.get("token_chain", "")).strip(),
            "token_symbol": str(e.get("token_symbol", "")).strip(),
            "token_name": str(e.get("token_name", "")).strip(),
            "mode": mode,
        }
        for e in entries
    ]
    prepared, rejected, risk_access = _prepare_live_list_items_for_queue(
        user=user,
        items=items,
        mode=mode,
        source="token_list_ui",
        effective_cap=effective_cap,
        shared_metadata={"token_list_id": int(list_id)},
    )
    if not prepared:
        err429 = next((r for r in rejected if r.get("error") == "daily_scan_limit_reached"), None)
        if err429:
            return (
                jsonify(
                    {
                        "status": "rejected",
                        "jobs": [],
                        "rejected": rejected,
                        "risk_access": risk_access,
                    }
                ),
                429,
            )
        return (
            jsonify(
                {
                    "status": "rejected",
                    "jobs": [],
                    "rejected": rejected,
                    "risk_access": risk_access,
                }
            ),
            400,
        )

    list_batch_id = str(uuid.uuid4())
    first = prepared[0]
    body, status_code = _queue_risk_job_for_user(
        user,
        {
            "token_address": first["token_address"],
            "token_chain": first["token_chain"],
            "mode": first["mode"],
            "source": "token_list_ui",
            "metadata": {
                "token_list_id": int(list_id),
                "list_batch_id": list_batch_id,
                "live_list_entries": prepared,
                "live_assessment_single_job": True,
                "token_symbol": str(first.get("token_symbol", "")).strip(),
                "token_name": str(first.get("token_name", "")).strip(),
            },
        },
        source_default="token_list_ui",
    )
    if isinstance(body, dict):
        body.pop("normalized_request", None)
        body["list_entry_total"] = total_entries
        body["list_run_cap"] = effective_cap
        body["list_truncated"] = truncated
        body["rejected"] = rejected
        if status_code == 201 and body.get("job"):
            body["jobs"] = [body["job"]]
        elif "jobs" not in body:
            body["jobs"] = []
    return jsonify(body), status_code


@risk_bp.post("/compat/jobs")
def create_compat_risk_job():
    payload = _compat_request_payload()
    user, used_shared_secret, error_payload, error_status = _resolve_compat_submit_user(payload)
    if user is None:
        return jsonify(error_payload), error_status

    response_payload, status_code = _queue_risk_job_for_user(user, payload, source_default="legacy_compat")
    if status_code != 201:
        response_payload["legacy_format_version"] = "2026-04-07"
        response_payload["compat_auth"] = "shared_secret" if used_shared_secret else "session"
        return jsonify(response_payload), status_code

    job = response_payload["job"]
    compat_payload = {
        "ok": True,
        "legacy_format_version": "2026-04-07",
        "compat_auth": "shared_secret" if used_shared_secret else "session",
        "status": "accepted",
        "job_id": str(job.get("job_id", "")).strip(),
        "queue_status": str(job.get("status", "")).strip().lower(),
        "stage": str(job.get("stage", "")).strip().lower(),
        "token_address": str(job.get("token_address", "")).strip().lower(),
        "chain": str(job.get("token_chain", "")).strip().lower(),
        "mode": str(job.get("mode", "")).strip().lower(),
        "submitted_at_utc": str(job.get("created_at_utc", "")).strip(),
        "poll_url": f"/api/v1/risk/compat/jobs/{str(job.get('job_id', '')).strip()}",
        "job_url": f"/api/v1/risk/jobs/{str(job.get('job_id', '')).strip()}",
        "events_url": f"/api/v1/risk/jobs/{str(job.get('job_id', '')).strip()}?events=1",
        "artifacts_url": f"/api/v1/risk/jobs/{str(job.get('job_id', '')).strip()}?artifacts=1",
        "normalized_request": response_payload.get("normalized_request", {}),
        "risk_access": response_payload.get("risk_access", {}),
    }
    return jsonify(compat_payload), 202


@risk_bp.get("/compat/jobs/<string:job_id>")
def get_compat_risk_job(job_id: str):
    include_events = str(request.args.get("events", "")).strip().lower() in {"1", "true", "yes", "on"}
    include_artifacts = str(request.args.get("artifacts", "")).strip().lower() in {"1", "true", "yes", "on"}
    store = current_app.config["RISK_JOB_STORE"]
    _normalize_runtime_risk_jobs(store)
    job = store.get_job(
        job_id,
        include_events=include_events,
        include_artifacts=True,
        event_limit=_safe_limit(request.args.get("event_limit"), default=80, max_limit=500),
        artifact_limit=_safe_limit(request.args.get("artifact_limit"), default=40, max_limit=500),
    )
    if job is None:
        return jsonify({"ok": False, "error": "not_found", "message": "Risk job not found."}), 404

    if not _compat_secret_is_authorized():
        user = get_current_user()
        if not user:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        if not _can_access_job(user, job):
            return jsonify({"ok": False, "error": "forbidden"}), 403

    public_job = sanitize_job_for_public_response(job)
    return jsonify(_build_compat_job_payload(public_job, include_events=include_events, include_artifacts=include_artifacts)), 200


@risk_bp.get("/jobs")
@api_login_required
def list_risk_jobs():
    user = get_current_user() or {}
    include_all = str(request.args.get("all", "")).strip().lower() in {"1", "true", "yes", "on"}
    user_filter = None
    if not include_all or not _is_admin_like(user):
        user_filter = int(user.get("id") or 0)

    status = str(request.args.get("status", "")).strip().lower()
    limit = _safe_limit(request.args.get("limit"), default=50, max_limit=200)
    store = current_app.config["RISK_JOB_STORE"]
    _normalize_runtime_risk_jobs(store)
    jobs = store.list_jobs(
        requested_by_user_id=user_filter,
        status=status,
        limit=limit,
    )
    safe_jobs = [sanitize_job_summary_fields(j) for j in jobs]
    return jsonify({"count": len(safe_jobs), "jobs": safe_jobs}), 200


@risk_bp.get("/jobs/<string:job_id>")
@api_login_required
def get_risk_job(job_id: str):
    user = get_current_user()
    include_events = str(request.args.get("events", "")).strip().lower() in {"1", "true", "yes", "on"}
    include_artifacts = str(request.args.get("artifacts", "")).strip().lower() in {"1", "true", "yes", "on"}
    event_limit = _safe_limit(request.args.get("event_limit"), default=80, max_limit=500)
    artifact_limit = _safe_limit(request.args.get("artifact_limit"), default=40, max_limit=500)
    store = current_app.config["RISK_JOB_STORE"]
    _normalize_runtime_risk_jobs(store)
    job = store.get_job(
        job_id,
        include_events=include_events,
        include_artifacts=include_artifacts,
        event_limit=event_limit,
        artifact_limit=artifact_limit,
    )
    if job is None:
        return jsonify({"error": "not_found", "message": "Risk job not found."}), 404
    if not _can_access_job(user, job):
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"job": sanitize_job_for_public_response(job)}), 200


@risk_bp.get("/jobs/<string:job_id>/stream")
@api_login_required
def stream_risk_job_events(job_id: str):
    """Server-Sent Events stream of sanitized job events (same data as polling ``GET …?events=1``).

    Browser clients may use ``EventSource`` with session cookies. Events are JSON objects
    with keys ``id``, ``event`` (sanitized row), ``job_status``, ``job_stage``, ``job_progress``.
    The stream ends when the job reaches a terminal status. Sends ``: ping`` comments periodically
    for connection keepalive.
    """
    store = current_app.config["RISK_JOB_STORE"]
    user = get_current_user()
    jid = str(job_id or "").strip()
    job_probe = store.get_job(jid, include_events=False, include_artifacts=False)
    if job_probe is None:
        return jsonify({"error": "not_found", "message": "Risk job not found."}), 404
    if not _can_access_job(user, job_probe):
        return jsonify({"error": "forbidden"}), 403

    after_raw = request.args.get("after_id", "0") or "0"
    try:
        after_id = max(0, int(str(after_raw).strip()))
    except (TypeError, ValueError):
        after_id = 0

    terminal = {"succeeded", "failed", "cancelled"}

    @stream_with_context
    def event_stream():
        last_seen = after_id
        pings = 0
        while True:
            _normalize_runtime_risk_jobs(store)
            job = store.get_job(
                jid,
                include_events=True,
                include_artifacts=False,
                event_limit=300,
            )
            if job is None:
                payload = json.dumps({"error": "not_found"}, ensure_ascii=True)
                yield f"event: error\ndata: {payload}\n\n"
                break
            if not _can_access_job(get_current_user(), job):
                payload = json.dumps({"error": "forbidden"}, ensure_ascii=True)
                yield f"event: error\ndata: {payload}\n\n"
                break
            events = job.get("events") if isinstance(job.get("events"), list) else []
            ordered = sorted(
                [e for e in events if isinstance(e, dict)],
                key=lambda row: int(row.get("id") or 0),
            )
            for ev in ordered:
                eid = int(ev.get("id") or 0)
                if eid <= last_seen:
                    continue
                last_seen = max(last_seen, eid)
                safe_ev = sanitize_event_for_public(ev)
                chunk = {
                    "id": eid,
                    "event": safe_ev,
                    "job_status": str(job.get("status") or ""),
                    "job_stage": str(job.get("stage") or ""),
                    "job_progress": int(job.get("progress") or 0),
                }
                yield "data: " + json.dumps(chunk, ensure_ascii=True, default=str) + "\n\n"
            st = str(job.get("status") or "").strip().lower()
            if st in terminal:
                done = {"terminal": True, "status": st, "job_id": jid}
                yield "data: " + json.dumps(done, ensure_ascii=True) + "\n\n"
                break
            pings += 1
            if pings % 8 == 0:
                yield ": ping\n\n"
            time.sleep(2.0)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(event_stream(), mimetype="text/event-stream", headers=headers)


DESKTOP_FULL_EXCEL_COLUMN_ORDER: tuple[str, ...] = (
    "Token Name",
    "Token Address",
    "Symbol",
    "Chain",
    "Is Stablecoin",
    "EU Compliance Status",
    "Risk Score",
    "Total Score (-Social)",
    "Risk Category",
    "Market Cap",
    "Volume 24h",
    "Holders",
    "Liquidity",
    "Red Flag: Unverified Contract",
    "Red Flag: Low Liquidity",
    "Red Flag: High Concentration",
    "Red Flag: Is Proxy Contract?",
    "Red Flag: Is a Wrapped-Token?",
    "Red Flag: EU Unicensed Stablecoin",
    "Red Flag: EU Regulatory Issue",
    "Red Flag: MiCA Non-Compliant",
    "Red Flag: MiCA No Whitepaper",
    "Red Flag: Owner Change Last 24h",
    "Red Flag: Chainabuse Reported",
    "Red Flag: Chainabuse High Severity",
    "Red Flags (All)",
    "Industry Impact",
    "Tech Innovation",
    "Whitepaper Quality",
    "Roadmap Adherence",
    "Business Model",
    "Team Expertise",
    "Management Strategy",
    "Global Reach",
    "Code Security",
    "Dev Activity",
    "Aml Data",
    "Compliance Data",
    "Market Dynamics",
    "Marketing Demand",
    "Esg Impact",
    "Social Data",
    "Score Credibility %",
)

PILLAR_KEYS_FOR_DESKTOP_EXCEL: tuple[str, ...] = (
    "industry_impact",
    "tech_innovation",
    "whitepaper_quality",
    "roadmap_adherence",
    "business_model",
    "team_expertise",
    "management_strategy",
    "global_reach",
    "code_security",
    "dev_activity",
    "aml_data",
    "compliance_data",
    "market_dynamics",
    "marketing_demand",
    "esg_impact",
    "social_data",
)

PILLAR_KEY_TO_EXCEL_HEADER: Dict[str, str] = {
    "industry_impact": "Industry Impact",
    "tech_innovation": "Tech Innovation",
    "whitepaper_quality": "Whitepaper Quality",
    "roadmap_adherence": "Roadmap Adherence",
    "business_model": "Business Model",
    "team_expertise": "Team Expertise",
    "management_strategy": "Management Strategy",
    "global_reach": "Global Reach",
    "code_security": "Code Security",
    "dev_activity": "Dev Activity",
    "aml_data": "Aml Data",
    "compliance_data": "Compliance Data",
    "market_dynamics": "Market Dynamics",
    "marketing_demand": "Marketing Demand",
    "esg_impact": "Esg Impact",
    "social_data": "Social Data",
}


def _summaries_live_list_single_job(store: Any, jid: str, job_fallback: Dict[str, Any]) -> List[Dict[str, Any]]:
    hydrated = store.get_job(jid, include_events=False, include_artifacts=True, artifact_limit=500) or job_fallback
    artifacts = hydrated.get("artifacts") if isinstance(hydrated.get("artifacts"), list) else []
    summaries: list[tuple[int, Dict[str, Any]]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("artifact_kind", "")).strip().lower() != "risk_summary":
            continue
        md = artifact.get("metadata")
        if not isinstance(md, dict) or not md:
            continue
        summaries.append((int(artifact.get("id") or 0), md))
    summaries.sort(key=lambda item: item[0])
    return [md for _, md in summaries]


def gather_summaries_for_list_batch_id(
    store: Any,
    batch_id: str,
    *,
    requested_by_user_id: int,
    user: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    """All risk_summary metadata dicts for jobs sharing ``list_batch_id`` (export + dashboard averages)."""
    bid = str(batch_id or "").strip()
    if not bid:
        return []
    uid = int(requested_by_user_id or 0)
    if _is_admin_like(user):
        raw = store.list_jobs(limit=400)
    else:
        raw = store.list_jobs(requested_by_user_id=max(1, uid), limit=400)
    same: list[Dict[str, Any]] = []
    for row in raw:
        jm = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if str(jm.get("list_batch_id") or "").strip() == bid:
            same.append(row)
    same.sort(
        key=lambda x: (
            str(x.get("token_chain") or "").lower(),
            str(x.get("token_address") or "").lower(),
        )
    )
    ids = [str(r.get("job_id", "")).strip() for r in same if r.get("job_id")]
    mmap = store.fetch_latest_risk_summary_metadata_for_job_ids(ids) if ids else {}
    out: list[Dict[str, Any]] = []
    for row in same:
        rjid = str(row.get("job_id", "")).strip()
        md = mmap.get(rjid)
        if isinstance(md, dict) and md:
            out.append(md)
    return out


def _risk_summaries_ordered_for_export(
    store: Any, job: Dict[str, Any], *, user: Dict[str, Any] | None
) -> list[Dict[str, Any]]:
    """Return risk_summary metadata dicts in stable user-facing order for downloads."""
    meta = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
    jid = str(job.get("job_id", "")).strip()
    if not jid:
        return []

    if meta.get("live_assessment_single_job") and isinstance(meta.get("live_list_entries"), list):
        return _summaries_live_list_single_job(store, jid, job)

    batch_id = str(meta.get("list_batch_id") or "").strip()
    if batch_id:
        return gather_summaries_for_list_batch_id(
            store,
            batch_id,
            requested_by_user_id=int(job.get("requested_by_user_id") or 0),
            user=user,
        )

    mmap = store.fetch_latest_risk_summary_metadata_for_job_ids([jid])
    md = mmap.get(jid)
    if isinstance(md, dict) and md:
        return [md]
    return []


def _parse_component_quality_and_confidence(md: Dict[str, Any]) -> tuple[Dict[str, float], Dict[str, int]]:
    """Normalize ``component_scores`` (nested adapter shape or legacy flat floats)."""
    qualities: Dict[str, float] = {}
    confidences: Dict[str, int] = {}
    raw = md.get("component_scores")
    if not isinstance(raw, dict):
        return qualities, confidences
    for pk, v in raw.items():
        key = str(pk).strip()
        if not key:
            continue
        if isinstance(v, dict):
            try:
                qualities[key] = float(v.get("quality_score") or 0.0)
            except (TypeError, ValueError):
                qualities[key] = 0.0
            try:
                confidences[key] = int(float(v.get("confidence_pct") or 0))
            except (TypeError, ValueError):
                confidences[key] = 0
        else:
            try:
                qualities[key] = float(v)
            except (TypeError, ValueError):
                qualities[key] = 0.0
    return qualities, confidences


def _eu_compliance_excel_cell(md: Dict[str, Any]) -> str:
    raw = md.get("eu_compliance_status")
    if isinstance(raw, dict):
        for k in ("summary", "status", "label"):
            s = str(raw.get(k) or "").strip()
            if s:
                return s
        try:
            return json.dumps(raw, ensure_ascii=True, sort_keys=True)[:500]
        except Exception:
            return "Unknown"
    s = str(raw or "").strip()
    return s or "Unknown"


def _is_stablecoin_excel_cell(md: Dict[str, Any]) -> str:
    if md.get("is_stablecoin"):
        return "Yes"
    ctx = md.get("context_flags")
    if isinstance(ctx, list) and any("stable" in str(x).lower() for x in ctx if x is not None):
        return "Yes"
    return "No"


def _red_flag_yes_no(flags_lower: List[str], *needles: str) -> str:
    for f in flags_lower:
        for n in needles:
            if n in f:
                return "Yes"
    return "No"


def _desktop_full_excel_row(md: Dict[str, Any]) -> Dict[str, Any]:
    """One spreadsheet row aligned with ``defi_complete_risk_assessment_clean`` desktop export."""
    km = md.get("key_metrics") if isinstance(md.get("key_metrics"), dict) else {}
    band = str(md.get("risk_band", "") or "").strip().lower()
    risk_cat = {
        "low": "Low Risk",
        "medium": "Medium Risk",
        "high": "High Risk",
        "extreme": "Extreme Risk",
    }.get(band, band.title() or "Unknown")
    flags_raw = md.get("red_flags") if isinstance(md.get("red_flags"), list) else []
    flags_lower = [str(x).strip().lower() for x in flags_raw if x is not None and str(x).strip()]

    try:
        overall_confidence_pct = int(round(float(md.get("confidence_pct") or 0.0)))
    except (TypeError, ValueError):
        overall_confidence_pct = 0
    overall_confidence_pct = max(0, min(100, overall_confidence_pct))

    qualities, confidences = _parse_component_quality_and_confidence(md)

    def _fmt_pillar(pillar_key: str) -> str:
        q = float(qualities.get(pillar_key, 0.0))
        c = int(confidences.get(pillar_key, 0))
        c = max(0, min(100, c))
        c = min(c, overall_confidence_pct)
        return f"{q:.2f} ({c}%)"

    row: Dict[str, Any] = {
        "Token Name": str(md.get("token_name") or "").strip() or "—",
        "Token Address": str(md.get("token_address") or "").strip() or "—",
        "Symbol": str(md.get("token_symbol") or "").strip().upper() or "—",
        "Chain": str(md.get("token_chain") or "").strip(),
        "Is Stablecoin": _is_stablecoin_excel_cell(md),
        "EU Compliance Status": _eu_compliance_excel_cell(md),
        "Risk Score": md.get("risk_score"),
        "Total Score (-Social)": md.get("total_score_minus_social"),
        "Risk Category": risk_cat,
        "Market Cap": km.get("market_cap_usd"),
        "Volume 24h": km.get("volume_24h_usd"),
        "Holders": km.get("holders"),
        "Liquidity": km.get("liquidity_usd"),
        "Red Flag: Unverified Contract": _red_flag_yes_no(flags_lower, "unverified_contract", "unverified"),
        "Red Flag: Low Liquidity": _red_flag_yes_no(
            flags_lower, "low_liquidity", "liquidity_risk", "very_low_holders", "low_holders"
        ),
        "Red Flag: High Concentration": _red_flag_yes_no(flags_lower, "high_concentration", "concentration"),
        "Red Flag: Is Proxy Contract?": _red_flag_yes_no(flags_lower, "proxy", "is_proxy"),
        "Red Flag: Is a Wrapped-Token?": _red_flag_yes_no(flags_lower, "is_wrapped_token", "wrapped_token"),
        "Red Flag: EU Unicensed Stablecoin": _red_flag_yes_no(flags_lower, "eu_unlicensed", "unlicensed_stablecoin"),
        "Red Flag: EU Regulatory Issue": _red_flag_yes_no(flags_lower, "eu_regulatory"),
        "Red Flag: MiCA Non-Compliant": _red_flag_yes_no(flags_lower, "mica_non_compliant", "mica_non"),
        "Red Flag: MiCA No Whitepaper": _red_flag_yes_no(flags_lower, "mica_no_whitepaper", "no_whitepaper"),
        "Red Flag: Owner Change Last 24h": _red_flag_yes_no(flags_lower, "owner_change"),
        "Red Flag: Chainabuse Reported": _red_flag_yes_no(flags_lower, "chainabuse_reported"),
        "Red Flag: Chainabuse High Severity": _red_flag_yes_no(flags_lower, "chainabuse_high"),
        "Red Flags (All)": ", ".join(str(x) for x in flags_raw if str(x).strip()) or "None",
        "Score Credibility %": f"{overall_confidence_pct}%",
    }

    for pk in PILLAR_KEYS_FOR_DESKTOP_EXCEL:
        hdr = PILLAR_KEY_TO_EXCEL_HEADER.get(pk, pk)
        row[hdr] = _fmt_pillar(pk)

    return row


def _dataframe_desktop_full_export(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for col in DESKTOP_FULL_EXCEL_COLUMN_ORDER:
        if col not in frame.columns:
            frame[col] = ""
    frame = frame[list(DESKTOP_FULL_EXCEL_COLUMN_ORDER)]
    numeric_cols = (
        "Market Cap",
        "Volume 24h",
        "Holders",
        "Liquidity",
        "Risk Score",
        "Total Score (-Social)",
    )
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
    return frame


@risk_bp.get("/jobs/<string:job_id>/export")
@api_login_required
def export_risk_job_download(job_id: str):
    """Download completed assessment summaries (legacy desktop-style columns)."""
    user = get_current_user()
    store = current_app.config["RISK_JOB_STORE"]
    job = store.get_job(str(job_id).strip(), include_events=False, include_artifacts=False)
    if job is None:
        return jsonify({"error": "not_found", "message": "Risk job not found."}), 404
    if not _can_access_job(user, job):
        return jsonify({"error": "forbidden"}), 403
    status = str(job.get("status", "")).strip().lower()
    if status != "succeeded":
        return (
            jsonify(
                {
                    "error": "job_not_complete",
                    "message": "Exports are available after the assessment completes successfully.",
                }
            ),
            409,
        )

    fmt = str(request.args.get("format", "json") or "").strip().lower()
    summaries = _risk_summaries_ordered_for_export(store, job, user=user)
    if not summaries:
        return jsonify({"error": "no_results", "message": "No stored results found for this job."}), 404

    risk_access = _build_risk_access_snapshot(user, store)
    social_ok = bool(risk_access.get("social_signal_enabled"))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if fmt == "json":
        payload = {
            "export_version": "2026-04-16",
            "job_id": job_id,
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tokens": summaries,
        }
        body = json.dumps(payload, ensure_ascii=True, indent=2, default=str)
        return Response(
            body,
            mimetype="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="risk_report_{stamp}.json"',
            },
        )

    desktop_rows = [_desktop_full_excel_row(md) for md in summaries]
    frame = _dataframe_desktop_full_export(desktop_rows)

    if fmt == "csv":
        buf = io.StringIO()
        frame.to_csv(buf, index=False)
        return Response(
            buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="risk_report_{stamp}.csv"'},
        )

    if fmt in {"xlsx", "excel"}:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="Risk Assessment")
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="DeFi_Tokens_Risk_Assessment_Results_{stamp}.xlsx"',
            },
        )

    if fmt in {"social_txt", "social", "txt"}:
        if not social_ok:
            return (
                jsonify(
                    {
                        "error": "social_export_forbidden",
                        "message": "Social report downloads require a plan that includes social signals.",
                    }
                ),
                403,
            )
        parts: list[str] = [
            "Hodler Suite — Social report bundle",
            f"Job: {job_id}",
            f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "",
        ]
        for idx, md in enumerate(summaries, start=1):
            txt = str(md.get("social_report_text") or "").strip()
            label = str(md.get("token_symbol") or md.get("token_address") or f"token_{idx}")
            parts.append(f"--- Token {idx}: {label} ---")
            parts.append(txt or "[No social appendix recorded for this token.]")
            parts.append("")
        blob = "\n".join(parts)
        return Response(
            blob,
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="social_score_report_{stamp}.txt"'},
        )

    return jsonify({"error": "unsupported_format", "message": "Use format=json, csv, xlsx, or social_txt."}), 400


@risk_bp.post("/jobs/<string:job_id>/cancel")
@api_login_required
def cancel_risk_job(job_id: str):
    user = get_current_user()
    store = current_app.config["RISK_JOB_STORE"]
    existing = store.get_job(job_id)
    if existing is None:
        return jsonify({"error": "not_found", "message": "Risk job not found."}), 404
    if not _can_access_job(user, existing):
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    reason = str(payload.get("reason", "")).strip() or "Cancelled by user"
    cancel_entire_list_batch = bool(payload.get("cancel_entire_list_batch"))
    meta = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
    batch_id = str(meta.get("list_batch_id") or "").strip()

    # List batch: allow stopping remaining queued/running siblings even when the job in the URL
    # is already terminal (e.g. first token finished while others are still queued).
    if cancel_entire_list_batch and batch_id:
        cancelled_ids = store.cancel_jobs_for_list_batch(
            requested_by_user_id=int(user["id"]),
            list_batch_id=batch_id,
            reason=reason,
        )
        primary = store.get_job(job_id)
        if primary is None:
            return jsonify({"error": "not_found", "message": "Risk job not found."}), 404
        if not cancelled_ids:
            return (
                jsonify(
                    {
                        "error": "batch_complete",
                        "message": "No queued or running jobs remain for this list batch.",
                        "job": sanitize_job_summary_fields(primary),
                        "cancelled_job_ids": [],
                        "cancelled_count": 0,
                    }
                ),
                409,
            )
        return (
            jsonify(
                {
                    "status": "cancelled",
                    "job": sanitize_job_summary_fields(primary),
                    "cancelled_job_ids": cancelled_ids,
                    "cancelled_count": len(cancelled_ids),
                }
            ),
            200,
        )

    status = str(existing.get("status", "")).strip().lower()
    if status in {"succeeded", "failed", "cancelled"}:
        return jsonify({"error": "already_terminal", "job": sanitize_job_summary_fields(existing)}), 409

    job = store.cancel_job(job_id=job_id, reason=reason)
    if job is None:
        return jsonify({"error": "not_found", "message": "Risk job not found."}), 404
    return jsonify({"status": "cancelled", "job": sanitize_job_summary_fields(job)}), 200


@risk_bp.post("/jobs/<string:job_id>/events")
def append_risk_job_event(job_id: str):
    authorized, error_payload, error_status = _authorize_risk_worker_request()
    if not authorized:
        return jsonify(error_payload), error_status

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    store = current_app.config["RISK_JOB_STORE"]
    safe_message = sanitize_public_message(str(payload.get("message", "")).strip())
    safe_details = sanitize_details_for_storage(
        payload.get("details") if isinstance(payload.get("details"), dict) else {}
    )
    job = store.update_job_state(
        job_id=job_id,
        status=str(payload.get("status", "")).strip().lower() or None,
        stage=str(payload.get("stage", "")).strip().lower() or None,
        progress=payload.get("progress"),
        summary_message=safe_message,
        error_code=str(payload.get("error_code", "")).strip(),
        error_message=sanitize_public_message(str(payload.get("error_message", "")).strip()),
        event_type=str(payload.get("event_type", "worker_event")).strip().lower() or "worker_event",
        details=safe_details,
    )
    if job is None:
        return jsonify({"error": "not_found", "message": "Risk job not found."}), 404

    meta = job.get("metadata") or {}
    if isinstance(meta, dict):
        batch_id = str(meta.get("list_batch_id") or "").strip()
        uid = int(job.get("requested_by_user_id") or 0)
        if batch_id and uid > 0:
            store.touch_list_batch_running_peers(list_batch_id=batch_id, requested_by_user_id=uid)

    artifact_kind = str(payload.get("artifact_kind", "")).strip().lower()
    artifact_uri = str(payload.get("artifact_uri", "")).strip()
    if artifact_kind and artifact_uri:
        artifact_metadata = payload.get("artifact_metadata") if isinstance(payload.get("artifact_metadata"), dict) else {}
        if artifact_kind == "risk_summary":
            artifact_metadata = _shape_result_payload_for_plan(
                artifact_metadata,
                _plan_snapshot_from_job(job),
            )
        store.add_job_artifact(
            job_id=job_id,
            artifact_kind=artifact_kind,
            artifact_uri=artifact_uri,
            content_type=str(payload.get("artifact_content_type", "")).strip(),
            metadata=artifact_metadata,
        )

    include_events = str(request.args.get("events", "")).strip().lower() in {"1", "true", "yes", "on"}
    include_artifacts = str(request.args.get("artifacts", "")).strip().lower() in {"1", "true", "yes", "on"}
    hydrated = store.get_job(job_id, include_events=include_events, include_artifacts=include_artifacts)
    if hydrated is None:
        return jsonify({"error": "not_found", "message": "Risk job not found."}), 404
    return jsonify({"status": "ok", "job": sanitize_job_for_public_response(hydrated)}), 200


@risk_bp.post("/internal/claim")
def claim_next_risk_job():
    authorized, error_payload, error_status = _authorize_risk_worker_request()
    if not authorized:
        return jsonify(error_payload), error_status

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    worker_id = str(payload.get("worker_id", "")).strip() or "risk_worker"

    store = current_app.config["RISK_JOB_STORE"]
    claimed = store.claim_next_job(worker_id=worker_id, stage="fetching", progress=5)
    if claimed is None:
        return jsonify({"status": "idle", "claimed": False}), 200
    job_payload = dict(claimed)
    job_payload.pop("_worker_batch_job_ids", None)
    return jsonify({"status": "claimed", "claimed": True, "job": job_payload}), 200


@risk_bp.post("/internal/run-once")
def run_risk_worker_once():
    authorized, error_payload, error_status = _authorize_risk_worker_request()
    if not authorized:
        return jsonify(error_payload), error_status

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    worker_id = str(payload.get("worker_id", "")).strip() or "risk_worker"

    store = current_app.config["RISK_JOB_STORE"]
    claimed = store.claim_next_job(worker_id=worker_id, stage="fetching", progress=5)
    if claimed is None:
        return jsonify({"status": "idle", "processed": False, "claimed": False}), 200

    job_id = str(claimed.get("job_id", "")).strip()
    try:
        run_result = _run_claimed_job(store, claimed, worker_id=worker_id)
    except Exception as exc:
        updated = store.update_job_state(
            job_id=job_id,
            status="failed",
            stage="failed",
            progress=100,
            summary_message="Assessment worker failed.",
            error_code="worker_runtime_error",
            error_message=str(exc),
            event_type="worker_failed",
            details={"worker_id": worker_id},
        )
        current_app.logger.exception("risk_worker_run_once_failed job_id=%s", job_id)
        return jsonify({"status": "failed", "processed": True, "job": updated}), 200

    return (
        jsonify(
            {
                "status": "processed",
                "processed": True,
                "job": run_result.get("job"),
                "result": run_result.get("result", {}),
            }
        ),
        200,
    )


@risk_bp.get("/live-batch/<string:batch_id>/snapshot")
@api_login_required
def api_live_batch_snapshot(batch_id: str):
    """JSON rows for the Live Assessment multi-token grid (poll while a list batch is running)."""
    from . import pages as pages_routes

    user = get_current_user() or {}
    store = current_app.config["RISK_JOB_STORE"]
    scoped = pages_routes._risk_job_scope_user_id(user)
    rows = pages_routes.compute_live_tokens_grid_rows_for_batch(store, scoped, batch_id)
    safe: list[dict[str, Any]] = []
    keys = (
        "job_id",
        "grid_row_index",
        "token_explorer_url",
        "token_chain",
        "token_address",
        "token_address_short",
        "token_name_label",
        "token_symbol_label",
        "status",
        "error_message",
        "stage",
        "progress",
        "risk_band",
        "risk_band_label",
        "confidence_label",
        "risk_score_label",
        "total_score_minus_social_label",
        "market_cap_label",
        "volume_24h_label",
        "holders_label",
        "liquidity_label",
        "model_label",
        "has_signal_data",
        "top_signals",
        "grid_liq",
        "grid_ctr",
        "grid_mkt",
        "grid_beh",
    )
    for row in rows:
        jid = str(row.get("job_id", "")).strip()
        if not jid:
            continue
        job = store.get_job(jid, include_events=False, include_artifacts=False)
        if not job or not pages_routes._can_access_risk_job(user, job):
            continue
        safe.append({k: row.get(k) for k in keys})
    return jsonify({"jobs": safe}), 200
