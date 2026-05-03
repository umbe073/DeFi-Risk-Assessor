"""Page routes for web portal UX."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets
import shutil
import socket
import ssl
import time
from typing import Any, Dict, List
from urllib.parse import urlparse
from urllib import error as urlerror
from urllib import request as urlrequest

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from ..auth import get_current_user, login_required, roles_required, validate_csrf_token
from ..billing_store import (
    RECONCILIATION_ACTION_TYPES,
    RECONCILIATION_ISSUE_TYPES,
    build_partial_payment_support_code,
)
from ..payments.nowpayments import NowPaymentsAdapter, normalize_pay_currency
from ..plans import get_checkout_plans
from ..security_context import parse_user_agent
from .support import _extract_client_ip, submit_ticket_payload
from ..turnstile import verify_turnstile_token

pages_bp = Blueprint("pages", __name__)
ALLOWED_TICKET_STATUSES = {"open", "in_progress", "resolved", "closed"}
TICKET_STATUS_ORDER = ["open", "in_progress", "resolved", "closed"]
STATUS_ALERT_CATEGORIES = {
    "website_api": {"ticket_store"},
    "script_api": {"status_probe"},
    "script_api_eth": {"status_probe"},
    "script_api_bsc": {"status_probe"},
    "script_api_tron": {"status_probe"},
    "chain_eth_rpc": {"status_probe"},
    "chain_bsc_rpc": {"status_probe"},
    "chain_tron_rpc": {"status_probe"},
    "support_services": {
        "support_smtp",
        "support_notify",
        "support_reply",
        "support_relay",
        "account_mailer",
        "trustpilot_reviews",
    },
    "billing_nowpayments": {"billing_nowpayments", "billing_webhook"},
    "inbound_webhook": {"resend_inbound"},
    "risk_worker_runtime": {"risk_worker"},
    "risk_jobs_24h": {"risk_worker"},
    "nginx_local": {"infra"},
    "public_marketing_edge": {"status_probe"},
    "public_app_edge": {"status_probe"},
    "tls_edge_cert": {"infra"},
    "storage_data": {"infra"},
}
STATUS_PROBE_ALERT_KEYS = {
    "script_api",
    "script_api_eth",
    "script_api_bsc",
    "script_api_tron",
    "chain_eth_rpc",
    "chain_bsc_rpc",
    "chain_tron_rpc",
    "public_marketing_edge",
    "public_app_edge",
}
PAY_CURRENCY_LABELS = {
    "usdttrc20": "USDT (TRC-20)",
    "usdc": "USDC (ERC-20)",
    "usdterc20": "USDT (ERC-20)",
}
FAILED_PAYMENT_STATUSES = {"failed", "expired", "refunded", "cancelled", "canceled"}
PARTIAL_PAYMENT_STATUSES = {"partially_paid", "partially-paid", "partially paid"}
USER_INFO_ACCESS_TTL_SECONDS = 5 * 60
SECURITY_SENSITIVE_OP_MARKERS = (
    "password",
    "twofa",
    "2fa",
    "email_change",
    "step_up",
    "lockout",
    "login_failed",
)
BUG_SURFACE_LABELS = {
    "website": "Website",
    "app": "App",
}
BUG_SEVERITY_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "very_high": "Very High",
}
BUG_REPRODUCIBLE_LABELS = {
    "yes": "Yes",
    "no": "No",
}
PAYMENT_CHAIN_LABELS = {
    "ethereum": "Ethereum",
    "bsc": "BNB Smart Chain",
    "tron": "Tron",
    "solana": "Solana",
    "bitcoin": "Bitcoin",
    "polygon": "Polygon",
    "arbitrum": "Arbitrum",
    "optimism": "Optimism",
    "avalanche": "Avalanche",
    "base": "Base",
    "other": "Other",
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default


def _script_probe_alert_cooldown_seconds() -> int:
    return max(0, _env_int("SCRIPT_API_STATUS_ALERT_COOLDOWN_SECONDS", 1800))


def _sanitize_ticket_refs(values: List[str]) -> List[str]:
    seen = set()
    refs: List[str] = []
    for raw in values:
        ref = str(raw or "").strip()
        if not ref or ref in seen:
            continue
        refs.append(ref)
        seen.add(ref)
    return refs


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _support_attachment_base_dir(settings) -> str:
    configured_dir = str(getattr(settings, "support_ticket_attachments_dir", "") or "").strip()
    if configured_dir:
        return os.path.abspath(configured_dir)
    return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "support_attachments"))


def _help_ticket_detail_rows(ticket: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    category_key = str(ticket.get("category", "")).strip().lower().replace(" ", "_")
    if category_key == "bug_report":
        surface = str(ticket.get("bug_surface", "")).strip().lower()
        severity = str(ticket.get("bug_severity", "")).strip().lower()
        reproducible = str(ticket.get("bug_reproducible", "")).strip().lower()
        if surface:
            rows.append({"label": "Bug Location", "value": BUG_SURFACE_LABELS.get(surface, surface.replace("_", " ").title())})
        if severity:
            rows.append({"label": "Severity", "value": BUG_SEVERITY_LABELS.get(severity, severity.replace("_", " ").title())})
        if reproducible:
            rows.append(
                {
                    "label": "Reproducible",
                    "value": BUG_REPRODUCIBLE_LABELS.get(reproducible, reproducible.replace("_", " ").title()),
                }
            )
        return rows

    if category_key == "payment_issue":
        txid = str(ticket.get("payment_txid", "")).strip()
        chain_key = str(ticket.get("payment_chain", "")).strip().lower()
        if txid:
            rows.append({"label": "TxID", "value": txid})
        if chain_key:
            rows.append({"label": "Blockchain", "value": PAYMENT_CHAIN_LABELS.get(chain_key, chain_key.replace("_", " ").title())})
    return rows


def _user_operation_type_tag(operation_type: str) -> dict[str, str]:
    normalized = str(operation_type or "").strip().lower()
    if not normalized:
        return {
            "label": "Other Activity",
            "class_name": "user-op-tag user-op-tag-neutral",
            "title": "General account activity",
        }

    if normalized.startswith("billing_"):
        return {
            "label": "Payments",
            "class_name": "user-op-tag user-op-tag-orange",
            "title": "Billing and payment workflow activity",
        }

    if normalized.startswith("support_"):
        return {
            "label": "Support / Ops",
            "class_name": "user-op-tag user-op-tag-orange",
            "title": "Support workflow and operational actions",
        }

    if normalized in {"login_success", "signup_verified"}:
        return {
            "label": "Sign-in",
            "class_name": "user-op-tag user-op-tag-green",
            "title": "Low-sensitivity authentication success events",
        }

    if normalized.startswith("admin_user_"):
        if any(marker in normalized for marker in ("password", "email_change", "set_role", "delete")):
            return {
                "label": "Admin Security",
                "class_name": "user-op-tag user-op-tag-red",
                "title": "High-sensitivity admin credential/role action",
            }
        return {
            "label": "Admin Management",
            "class_name": "user-op-tag user-op-tag-orange",
            "title": "Administrative user-management action",
        }

    if any(marker in normalized for marker in SECURITY_SENSITIVE_OP_MARKERS):
        return {
            "label": "Credential Security",
            "class_name": "user-op-tag user-op-tag-red",
            "title": "Password, 2FA, email-change, or lockout-related action",
        }

    if normalized.startswith("login_"):
        return {
            "label": "Authentication",
            "class_name": "user-op-tag user-op-tag-green",
            "title": "Authentication workflow event",
        }

    return {
        "label": "Account Activity",
        "class_name": "user-op-tag user-op-tag-neutral",
        "title": "General account operation event",
    }


def _safe_local_next(value: str, fallback_endpoint: str = "pages.homepage") -> str:
    candidate = str(value or "").strip()
    if candidate:
        parsed = urlparse(candidate)
        if not parsed.scheme and not parsed.netloc and candidate.startswith("/") and not candidate.startswith("//"):
            return candidate
    return url_for(fallback_endpoint)


def _is_manageable_user(actor: dict, target: dict) -> bool:
    actor_role = str(actor.get("role", "")).strip().lower()
    if actor_role == "master":
        return True
    if actor_role == "admin":
        target_role = str(target.get("role", "")).strip().lower()
        return target_role == "child" and int(target.get("parent_user_id") or 0) == int(actor.get("id") or 0)
    return False


def _prune_info_access_grants(raw_grants: Any, *, now_epoch: int) -> dict[str, dict[str, int]]:
    if not isinstance(raw_grants, dict):
        return {}
    cleaned: dict[str, dict[str, int]] = {}
    for token, payload in raw_grants.items():
        access_token = str(token or "").strip()
        if not access_token or not isinstance(payload, dict):
            continue
        try:
            grant_user_id = int(payload.get("user_id") or 0)
            expires_at = int(payload.get("expires_at_epoch") or 0)
        except (TypeError, ValueError):
            continue
        if grant_user_id <= 0 or expires_at <= now_epoch:
            continue
        cleaned[access_token] = {"user_id": grant_user_id, "expires_at_epoch": expires_at}
    return cleaned


def _record_operational_alert(
    *,
    category: str,
    severity: str,
    message: str,
    event_key: str = "",
    context: dict | None = None,
) -> None:
    try:
        store = current_app.config.get("SUPPORT_TICKET_STORE")
        if store is None:
            return
        normalized_category = str(category or "").strip().lower()
        normalized_event_key = str(event_key or "").strip().lower()
        # Reduce repeated Script API probe noise after resolve/retry loops.
        if normalized_category == "status_probe" and ":script_api" in normalized_event_key:
            cooldown_seconds = _script_probe_alert_cooldown_seconds()
            if cooldown_seconds > 0 and store.has_recent_operational_alert(
                event_key=normalized_event_key,
                within_seconds=cooldown_seconds,
            ):
                return
        store.create_operational_alert(
            category=category,
            severity=severity,
            message=message,
            event_key=event_key,
            context=context or {},
        )
    except Exception:
        current_app.logger.exception("operational_alert_store_failed category=%s event_key=%s", category, event_key)


def _audit_operation_context() -> dict[str, Any]:
    ip_address = _extract_client_ip()
    user_agent = str(request.headers.get("User-Agent", "")).strip()
    device = parse_user_agent(user_agent)
    country_code = str(request.headers.get("CF-IPCountry", "")).strip().upper()
    if len(country_code) != 2 or not country_code.isalpha() or country_code in {"XX", "T1"}:
        country_code = ""
    return {
        "ip_address": ip_address,
        "device_uuid": str(session.get("device_uuid", "")).strip(),
        "device_type": str(device.get("device_type", "")).strip(),
        "os_name": str(device.get("os_name", "")).strip(),
        "os_version": str(device.get("os_version", "")).strip(),
        "browser_name": str(device.get("browser_name", "")).strip(),
        "browser_version": str(device.get("browser_version", "")).strip(),
        "country_code": country_code,
    }


def _audit_privileged_operation(
    *,
    operation_type: str,
    details: dict | None = None,
    target_user_id: int | None = None,
) -> None:
    actor = get_current_user() or {}
    actor_id = int(actor.get("id") or 0)
    if actor_id <= 0:
        return
    try:
        current_app.config["USER_STORE"].record_user_operation(
            user_id=actor_id,
            operation_type=str(operation_type or "").strip().lower(),
            target_user_id=int(target_user_id) if target_user_id is not None else None,
            context=_audit_operation_context(),
            details=details or {},
        )
    except Exception:
        current_app.logger.exception("privileged_operation_audit_failed operation_type=%s", operation_type)


def _nowpayments_adapter() -> NowPaymentsAdapter:
    settings = current_app.config["SETTINGS"]
    return NowPaymentsAdapter(
        api_key=settings.nowpayments_api_key,
        ipn_secret=settings.nowpayments_ipn_secret,
        api_base=settings.nowpayments_api_base,
    )


def _pay_currency_label(code: str) -> str:
    normalized = normalize_pay_currency(code)
    if not normalized:
        return ""
    if normalized in PAY_CURRENCY_LABELS:
        return PAY_CURRENCY_LABELS[normalized]
    return normalized.upper()


def _effective_pay_currency_options(settings) -> list[dict[str, str]]:
    billing_store = current_app.config["BILLING_STORE"]
    defaults = [
        {
            "code": normalize_pay_currency(str(option.get("code", "")).strip()),
            "label": str(option.get("label", "")).strip() or _pay_currency_label(str(option.get("code", ""))),
        }
        for option in (settings.nowpayments_pay_currencies or [])
        if str(option.get("code", "")).strip()
    ]
    defaults = [item for item in defaults if item.get("code")]
    if not defaults:
        defaults = [{"code": "usdttrc20", "label": "USDT (TRC-20)"}]
    return billing_store.get_effective_pay_currency_options(default_options=defaults)


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


def _payment_state_from_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"finished", "confirmed"}:
        return "success"
    if normalized in FAILED_PAYMENT_STATUSES:
        return "failed"
    if normalized in PARTIAL_PAYMENT_STATUSES:
        return "partial"
    return "waiting"


def _receipt_id_for_order(order_id: str) -> str:
    token = "".join(ch for ch in str(order_id or "").upper() if ch.isalnum())
    if not token:
        token = "UNKNOWN"
    return f"HSR-{token[-12:]}"


def _checkout_for_view(order_id: str) -> dict | None:
    normalized_order_id = str(order_id or "").strip()
    if not normalized_order_id:
        return None
    checkout = current_app.config["BILLING_STORE"].get_checkout_by_order_id(order_id=normalized_order_id)
    if not checkout:
        return None

    actor = get_current_user() or {}
    actor_role = str(actor.get("role", "")).strip().lower()
    if actor_role in {"master", "admin"}:
        return checkout
    if int(checkout.get("user_id") or 0) != int(actor.get("id") or 0):
        return None
    return checkout


def _extract_payment_details(checkout: dict) -> Dict[str, str]:
    payload_raw = str(checkout.get("provider_payload_json", "") or "").strip()
    payload: Dict[str, Any] = {}
    if payload_raw:
        try:
            decoded = json.loads(payload_raw)
            if isinstance(decoded, dict):
                payload = decoded
        except json.JSONDecodeError:
            payload = {}

    receiving_wallet = (
        str(payload.get("pay_address") or payload.get("payment_address") or payload.get("payout_address") or "").strip()
    )
    transaction_id = str(
        payload.get("outcome_txid")
        or payload.get("payin_hash")
        or payload.get("payin_extra_id")
        or payload.get("purchase_id")
        or payload.get("id")
        or ""
    ).strip()
    operation_id = str(
        checkout.get("nowpayments_payment_id")
        or checkout.get("nowpayments_invoice_id")
        or checkout.get("order_id")
        or ""
    ).strip()
    paid_at = str(checkout.get("paid_at_utc") or checkout.get("updated_at_utc") or checkout.get("created_at_utc") or "").strip()
    return {
        "receiving_wallet": receiving_wallet,
        "transaction_id": transaction_id,
        "operation_id": operation_id,
        "paid_at_utc": paid_at,
        "receipt_id": _receipt_id_for_order(str(checkout.get("order_id", ""))),
    }


def _safe_amount(value: Any) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return 0.0
    if amount < 0:
        return 0.0
    return round(amount, 8)


def _build_partial_payment_summary(checkout: dict | None) -> dict[str, Any]:
    if not isinstance(checkout, dict):
        return {
            "total_amount": 0.0,
            "paid_amount": 0.0,
            "remaining_amount": 0.0,
            "price_currency": "USD",
            "manual_support_code": "",
        }

    payload_raw = str(checkout.get("provider_payload_json", "") or "").strip()
    payload: Dict[str, Any] = {}
    if payload_raw:
        try:
            decoded = json.loads(payload_raw)
            if isinstance(decoded, dict):
                payload = decoded
        except json.JSONDecodeError:
            payload = {}

    total_amount = _safe_amount(checkout.get("amount_value"))
    if total_amount <= 0:
        total_amount = _safe_amount(payload.get("price_amount") or payload.get("invoice_total_sum"))

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
        maybe = _safe_amount(candidate)
        if maybe > 0:
            paid_amount = maybe
            break

    if paid_amount <= 0 and total_amount > 0:
        paid_amount = min(total_amount, _safe_amount(payload.get("pay_amount_usd")))

    remaining_amount = max(0.0, round(total_amount - paid_amount, 8))
    price_currency = str(checkout.get("price_currency") or payload.get("price_currency") or "USD").strip().upper()

    manual_support_code = build_partial_payment_support_code(
        order_id=str(checkout.get("order_id", "")).strip(),
        nowpayments_payment_id=str(checkout.get("nowpayments_payment_id", "")).strip(),
        nowpayments_invoice_id=str(checkout.get("nowpayments_invoice_id", "")).strip(),
    )

    return {
        "total_amount": round(total_amount, 8),
        "paid_amount": round(paid_amount, 8),
        "remaining_amount": round(remaining_amount, 8),
        "price_currency": price_currency or "USD",
        "manual_support_code": manual_support_code,
    }


def _service_alert_counts(*, service_key: str, hours: int = 24) -> dict[str, int]:
    categories = STATUS_ALERT_CATEGORIES.get(service_key, set())
    if not categories:
        return {"info": 0, "warning": 0, "error": 0, "critical": 0}

    counts = {"info": 0, "warning": 0, "error": 0, "critical": 0}
    store = current_app.config.get("SUPPORT_TICKET_STORE")
    if store is None:
        return counts

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(hours)))
    alerts = store.list_operational_alerts(open_only=False, limit=500)
    for alert in alerts:
        category = str(alert.get("category", "")).strip().lower()
        if category not in categories:
            continue
        created = _parse_utc(str(alert.get("created_at_utc", "")))
        if created and created < cutoff:
            continue
        severity = str(alert.get("severity", "")).strip().lower()
        if severity not in counts:
            severity = "error"
        counts[severity] += 1
    return counts


def _estimate_uptime_percent(*, status: str, alert_counts: dict[str, int]) -> float:
    normalized_status = str(status or "").strip().lower()
    base = {
        "online": 99.4,
        "degraded": 94.0,
        "offline": 42.0,
        "disabled": 100.0,
        "unknown": 78.0,
    }.get(normalized_status, 78.0)
    penalty = (
        float(alert_counts.get("warning", 0)) * 1.2
        + float(alert_counts.get("error", 0)) * 3.8
        + float(alert_counts.get("critical", 0)) * 6.3
    )
    if normalized_status == "disabled":
        penalty = 0.0
    return max(0.0, min(100.0, base - penalty))


def _build_history_points(*, uptime_percent: float, alert_counts: dict[str, int]) -> list[int]:
    total_alert_weight = (
        float(alert_counts.get("warning", 0))
        + float(alert_counts.get("error", 0)) * 1.5
        + float(alert_counts.get("critical", 0)) * 2.0
    )
    amplitude = min(14.0, 2.0 + total_alert_weight)
    points: list[int] = []
    for idx in range(12):
        wave = ((idx % 4) - 1.5) * amplitude
        point = max(0.0, min(100.0, uptime_percent - wave))
        points.append(int(round(point)))
    return points


def _script_api_probe_auth_headers(payload: bytes = b"") -> dict[str, str]:
    shared_secret = str(os.getenv("SCRIPT_API_PROBE_SHARED_SECRET", "")).strip() or str(
        os.getenv("WEBHOOK_SHARED_SECRET", "")
    ).strip()
    if not shared_secret:
        return {}

    headers = {
        "Authorization": f"Bearer {shared_secret}",
        "X-Webhook-Token": shared_secret,
    }
    include_signature = _env_bool("SCRIPT_API_PROBE_SIGNED", default=True)
    if include_signature:
        timestamp = str(int(time.time()))
        signed_payload = f"{timestamp}.".encode("utf-8") + (payload or b"")
        signature = hmac.new(
            shared_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Webhook-Timestamp"] = timestamp
        headers["X-Webhook-Signature"] = f"sha256={signature}"
    return headers


def _http_get_health(
    url: str,
    *,
    timeout_seconds: int = 3,
    extra_headers: dict[str, str] | None = None,
    parse_json_detail: bool = False,
) -> tuple[str, str, int | None]:
    endpoint = str(url or "").strip()
    if not endpoint:
        return "unknown", "Not configured", None
    started = time.perf_counter()
    headers = {"Accept": "application/json", "User-Agent": "HodlerSuiteStatus/1.0"}
    if extra_headers:
        headers.update({str(key): str(value) for key, value in extra_headers.items() if str(key).strip()})
    request_obj = urlrequest.Request(
        endpoint,
        method="GET",
        headers=headers,
    )
    try:
        with urlrequest.urlopen(request_obj, timeout=timeout_seconds) as response:
            elapsed = int((time.perf_counter() - started) * 1000)
            status_code = int(response.status)
            detail = f"HTTP {status_code}"
            if parse_json_detail:
                try:
                    parsed_detail = _parse_health_detail_payload(response.read(8192), fallback=detail)
                    if parsed_detail:
                        detail = parsed_detail
                except Exception:
                    pass
            if 200 <= status_code < 300:
                return "online", detail, elapsed
            return "degraded", detail, elapsed
    except Exception as exc:  # pragma: no cover - network dependency
        if isinstance(exc, urlerror.HTTPError):
            detail = f"HTTP {int(exc.code)}"
            if parse_json_detail:
                try:
                    parsed_detail = _parse_health_detail_payload(exc.read(8192), fallback=detail)
                    if parsed_detail:
                        detail = parsed_detail
                except Exception:
                    pass
            return "degraded", detail, None
        return "offline", f"Unavailable: {str(exc)[:90]}", None


def _parse_health_detail_payload(payload_bytes: bytes, *, fallback: str = "") -> str:
    if not payload_bytes:
        return str(fallback or "")
    try:
        payload = json.loads(payload_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return str(fallback or "")
    if not isinstance(payload, dict):
        return str(fallback or "")

    detail = str(payload.get("message", "")).strip()
    status_hint = str(payload.get("status", "")).strip().lower()
    if not detail and status_hint and status_hint not in {"healthy", "online", "ok"}:
        detail = status_hint

    extras: list[str] = []
    chain = str(payload.get("chain", "")).strip().upper()
    if chain:
        extras.append(f"chain={chain}")
    for source_key, label in (
        ("cached_tokens", "cached"),
        ("fresh_tokens", "fresh"),
        ("stale_tokens", "stale"),
    ):
        if source_key in payload:
            try:
                extras.append(f"{label}={int(payload.get(source_key, 0))}")
            except Exception:
                pass
    if "max_age_seconds" in payload:
        try:
            extras.append(f"max-age={int(payload.get('max_age_seconds', 0))}s")
        except Exception:
            pass

    if detail and extras:
        return f"{detail} • {', '.join(extras)}"
    if detail:
        return detail
    if extras:
        return ", ".join(extras)
    return str(fallback or "")


def _parse_int_like(value: Any) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("s"):
        raw = raw[:-1]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _humanize_probe_reason(reason: str) -> str:
    text = str(reason or "").strip()
    if not text:
        return "Healthy"
    text = text.replace("_", " ").replace(":", " - ")
    if not text:
        return "Healthy"
    return text[0].upper() + text[1:]


def _script_probe_detail_fields(detail: str) -> dict[str, Any]:
    raw_detail = str(detail or "").strip()
    reason = raw_detail
    extras_raw = ""
    if "•" in raw_detail:
        reason, extras_raw = [segment.strip() for segment in raw_detail.split("•", 1)]

    pairs: dict[str, str] = {}
    if extras_raw:
        for chunk in extras_raw.split(","):
            part = str(chunk or "").strip()
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            normalized_key = str(key or "").strip().lower()
            normalized_value = str(value or "").strip()
            if normalized_key:
                pairs[normalized_key] = normalized_value

    chain = str(pairs.get("chain", "")).strip().upper()
    cached = _parse_int_like(pairs.get("cached", ""))
    fresh = _parse_int_like(pairs.get("fresh", ""))
    stale = _parse_int_like(pairs.get("stale", ""))
    max_age = _parse_int_like(pairs.get("max-age", ""))

    freshness_label = "n/a"
    if fresh is not None and cached is not None and stale is not None:
        freshness_label = f"{fresh}/{cached}/{stale} (fresh/cached/stale)"
    elif fresh is not None and cached is not None:
        freshness_label = f"{fresh}/{cached} (fresh/cached)"
    elif fresh is not None:
        freshness_label = str(fresh)

    coverage_label = "Unknown"
    if cached is not None:
        if cached <= 0:
            coverage_label = "Warming up (no cached tokens yet)"
        elif (fresh or 0) > 0:
            coverage_label = "Fresh data available"
        elif (stale or 0) > 0:
            coverage_label = "Stale cache only"
        else:
            coverage_label = "Cached data available"

    max_age_label = "n/a"
    if max_age is not None and max_age > 0:
        max_age_label = f"{max_age}s"

    return {
        "probe_reason_label": _humanize_probe_reason(reason),
        "probe_chain_label": chain or "n/a",
        "probe_fresh_tokens": fresh if fresh is not None else "-",
        "probe_cached_tokens": cached if cached is not None else "-",
        "probe_stale_tokens": stale if stale is not None else "-",
        "probe_freshness_label": freshness_label,
        "probe_max_age_label": max_age_label,
        "probe_coverage_label": coverage_label,
    }


def _json_post_health(
    url: str,
    payload: dict,
    *,
    timeout_seconds: int = 3,
    extra_headers: dict[str, str] | None = None,
) -> tuple[str, str, int | None]:
    endpoint = str(url or "").strip()
    if not endpoint:
        return "unknown", "Not configured", None
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    started = time.perf_counter()
    headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "HodlerSuiteStatus/1.0"}
    if extra_headers:
        headers.update({str(key): str(value) for key, value in extra_headers.items() if str(key).strip()})
    request_obj = urlrequest.Request(
        endpoint,
        method="POST",
        data=body,
        headers=headers,
    )
    try:
        with urlrequest.urlopen(request_obj, timeout=timeout_seconds) as response:
            elapsed = int((time.perf_counter() - started) * 1000)
            if 200 <= int(response.status) < 300:
                return "online", f"HTTP {int(response.status)}", elapsed
            return "degraded", f"HTTP {int(response.status)}", elapsed
    except Exception as exc:  # pragma: no cover - network dependency
        if isinstance(exc, urlerror.HTTPError):
            return "degraded", f"HTTP {int(exc.code)}", None
        return "offline", f"Unavailable: {str(exc)[:90]}", None


def _hostname_from_url(url: str) -> str:
    try:
        return str(urlparse(str(url or "").strip()).hostname or "").strip().lower()
    except Exception:
        return ""


def _tls_days_remaining(hostname: str, *, timeout_seconds: int = 4) -> tuple[str, str, int | None]:
    host = str(hostname or "").strip().lower()
    if not host:
        return "unknown", "Host not configured", None
    started = time.perf_counter()
    try:
        context = ssl.create_default_context()
        if hasattr(ssl, "TLSVersion"):
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        else:  # pragma: no cover - compatibility fallback
            context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        with socket.create_connection((host, 443), timeout=timeout_seconds) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls_sock:
                cert = tls_sock.getpeercert()
        elapsed = int((time.perf_counter() - started) * 1000)
        not_after = str(cert.get("notAfter", "")).strip()
        if not not_after:
            return "degraded", "Certificate expiry unavailable", elapsed
        expires_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        remaining_days = int((expires_dt - datetime.now(timezone.utc)).total_seconds() // 86400)
        if remaining_days <= 7:
            return "degraded", f"Certificate expires in {remaining_days}d ({host})", elapsed
        if remaining_days <= 21:
            return "degraded", f"Certificate expires in {remaining_days}d ({host})", elapsed
        return "online", f"Certificate expires in {remaining_days}d ({host})", elapsed
    except Exception as exc:  # pragma: no cover - network dependency
        return "offline", f"TLS probe failed for {host}: {str(exc)[:90]}", None


def _storage_health_detail(settings) -> tuple[str, str, int | None]:
    warn_pct = max(1, min(90, _env_int("STATUS_DISK_FREE_WARNING_PCT", 15)))
    critical_pct = max(1, min(warn_pct, _env_int("STATUS_DISK_FREE_CRITICAL_PCT", 8)))
    db_warn_mb = max(1, _env_int("STATUS_DB_SIZE_WARNING_MB", 1024))
    db_critical_mb = max(db_warn_mb, _env_int("STATUS_DB_SIZE_CRITICAL_MB", 4096))

    db_paths = [
        str(getattr(settings, "auth_db_path", "") or "").strip(),
        str(getattr(settings, "support_ticket_db_path", "") or "").strip(),
        str(getattr(settings, "billing_db_path", "") or "").strip(),
        str(getattr(settings, "status_db_path", "") or "").strip(),
        str(getattr(settings, "risk_job_db_path", "") or "").strip(),
    ]
    db_paths = [item for item in db_paths if item]
    probe_path = db_paths[0] if db_paths else "/opt/hodler-suite/web_portal/data"
    directory = probe_path if os.path.isdir(probe_path) else os.path.dirname(probe_path) or "/"
    started = time.perf_counter()
    try:
        usage = shutil.disk_usage(directory)
    except Exception as exc:
        return "offline", f"Disk usage probe failed: {str(exc)[:90]}", None
    elapsed = int((time.perf_counter() - started) * 1000)
    total = max(1, int(usage.total))
    free = max(0, int(usage.free))
    free_pct = round((float(free) / float(total)) * 100.0, 1)
    total_db_bytes = 0
    largest_db_name = ""
    largest_db_bytes = 0
    for path in db_paths:
        try:
            size = int(os.path.getsize(path))
        except OSError:
            size = 0
        total_db_bytes += max(0, size)
        if size > largest_db_bytes:
            largest_db_bytes = size
            largest_db_name = os.path.basename(path)
    total_db_mb = round(float(total_db_bytes) / (1024.0 * 1024.0), 1)
    largest_db_mb = round(float(largest_db_bytes) / (1024.0 * 1024.0), 1)

    status = "online"
    if free_pct <= float(critical_pct) or total_db_mb >= float(db_critical_mb):
        status = "degraded"
    elif free_pct <= float(warn_pct) or total_db_mb >= float(db_warn_mb):
        status = "degraded"

    detail = (
        f"disk_free={free_pct:.1f}% (warn<={warn_pct}% crit<={critical_pct}%) | "
        f"db_total={total_db_mb:.1f}MB (warn>={db_warn_mb}MB crit>={db_critical_mb}MB)"
    )
    if largest_db_name:
        detail += f" | largest={largest_db_name}:{largest_db_mb:.1f}MB"
    return status, detail, elapsed


def _build_service_card(
    *,
    service_key: str,
    name: str,
    status: str,
    detail: str,
    latency_ms: int | None,
    group: str,
) -> dict:
    counts = _service_alert_counts(service_key=service_key, hours=24)
    uptime_percent = _estimate_uptime_percent(status=status, alert_counts=counts)
    history_points = _build_history_points(uptime_percent=uptime_percent, alert_counts=counts)
    total_alerts = int(counts.get("warning", 0) + counts.get("error", 0) + counts.get("critical", 0))
    status_class = str(status or "unknown").strip().lower()
    if status_class not in {"online", "degraded", "offline", "disabled", "unknown"}:
        status_class = "unknown"
    return {
        "key": service_key,
        "name": name,
        "group": group,
        "status": status_class,
        "status_label": status_class.replace("_", " ").title(),
        "detail": str(detail or "").strip() or "No detail",
        "latency_ms": latency_ms,
        "latency_label": f"{int(latency_ms)} ms" if latency_ms is not None else "N/A",
        "uptime_percent": round(uptime_percent, 1),
        "history_points": history_points,
        "alerts_24h": total_alerts,
    }


def _apply_status_history_metrics(card: dict) -> dict:
    status_store = current_app.config.get("STATUS_STORE")
    if status_store is None:
        card["history_points"] = card.get("history_points", [])
        card["uptime_24h"] = card.get("uptime_percent", 0.0)
        card["uptime_7d"] = card.get("uptime_percent", 0.0)
        card["error_rate_24h"] = 0.0
        card["error_rate_6h"] = 0.0
        card["failure_streak"] = 0
        card["failure_streak_status"] = "none"
        card["avg_latency_24h_label"] = card.get("latency_label", "N/A")
        return card

    key = str(card.get("key", "")).strip().lower()
    if not key:
        return card
    samples_6h = status_store.list_samples(service_key=key, hours=6, limit=1200)
    failure_streak, failure_streak_status = _recent_failure_streak(samples_6h)
    summary_6h = status_store.summarize(service_key=key, hours=6)
    summary_24h = status_store.summarize(service_key=key, hours=24)
    summary_7d = status_store.summarize(service_key=key, hours=24 * 7)
    history_24h = status_store.build_history(service_key=key, hours=24, buckets=24)
    history_points = [int(round(float(item.get("online_pct", 0.0)))) for item in history_24h]

    card["history_points"] = history_points or card.get("history_points", [])
    card["uptime_24h"] = float(summary_24h.get("uptime_percent", card.get("uptime_percent", 0.0)))
    card["uptime_7d"] = float(summary_7d.get("uptime_percent", card.get("uptime_percent", 0.0)))
    card["uptime_percent"] = card["uptime_24h"]
    card["error_rate_24h"] = float(summary_24h.get("error_rate_percent", 0.0))
    card["error_rate_6h"] = float(summary_6h.get("error_rate_percent", 0.0))
    card["failure_streak"] = int(failure_streak)
    card["failure_streak_status"] = str(failure_streak_status or "none")
    avg_latency = summary_24h.get("avg_latency_ms")
    card["avg_latency_24h_label"] = f"{int(round(avg_latency))} ms" if avg_latency is not None else "N/A"
    card["samples_6h"] = int(summary_6h.get("total", 0))
    card["samples_24h"] = int(summary_24h.get("total", 0))
    return card


def _normalize_service_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"online", "degraded", "offline", "disabled", "unknown"}:
        return normalized
    return "unknown"


def _recent_failure_streak(samples: List[dict]) -> tuple[int, str]:
    streak = 0
    streak_status = "none"
    for sample in reversed(samples):
        status = _normalize_service_status(sample.get("status"))
        if status not in {"degraded", "offline"}:
            break
        streak += 1
        if status == "offline":
            streak_status = "offline"
        elif streak_status != "offline":
            streak_status = "degraded"
    return streak, streak_status


def _status_probe_thresholds() -> dict[str, int]:
    failure_streak = max(1, _env_int("STATUS_PROBE_FAILURE_STREAK_THRESHOLD", 3))
    minimum_samples = max(1, _env_int("STATUS_PROBE_MIN_SAMPLES", 6))
    window_hours = max(1, _env_int("STATUS_PROBE_WINDOW_HOURS", 6))
    error_rate_warning = max(1, min(100, _env_int("STATUS_PROBE_ERROR_RATE_WARNING_PCT", 35)))
    error_rate_critical = max(error_rate_warning, min(100, _env_int("STATUS_PROBE_ERROR_RATE_CRITICAL_PCT", 60)))
    latency_warning = max(100, _env_int("STATUS_PROBE_LATENCY_WARNING_MS", 2500))
    latency_critical = max(latency_warning, _env_int("STATUS_PROBE_LATENCY_CRITICAL_MS", 5000))
    return {
        "failure_streak": failure_streak,
        "minimum_samples": minimum_samples,
        "window_hours": window_hours,
        "error_rate_warning": error_rate_warning,
        "error_rate_critical": error_rate_critical,
        "latency_warning": latency_warning,
        "latency_critical": latency_critical,
    }


def _is_probe_card_configured(card: dict) -> bool:
    detail = str(card.get("detail", "")).strip().lower()
    if not detail:
        return False
    if "not configured" in detail:
        return False
    if detail.startswith("set script_api_"):
        return False
    return True


def _evaluate_status_probe_alerts(*, cards: List[dict]) -> None:
    status_store = current_app.config.get("STATUS_STORE")
    if status_store is None:
        return
    thresholds = _status_probe_thresholds()
    for card in cards:
        key = str(card.get("key", "")).strip().lower()
        if key not in STATUS_PROBE_ALERT_KEYS:
            continue
        if not _is_probe_card_configured(card):
            continue

        samples = status_store.list_samples(
            service_key=key,
            hours=int(thresholds["window_hours"]),
            limit=1500,
        )
        if not samples:
            continue

        failure_streak, failure_streak_status = _recent_failure_streak(samples)
        if failure_streak >= int(thresholds["failure_streak"]):
            _record_operational_alert(
                category="status_probe",
                severity="critical" if failure_streak_status == "offline" else "error",
                message=f"{card.get('name', key)} probe failure streak reached threshold",
                event_key=f"status_probe_failure_streak:{key}",
                context={
                    "service_key": key,
                    "service_name": card.get("name", key),
                    "threshold": int(thresholds["failure_streak"]),
                    "failure_streak": int(failure_streak),
                    "failure_streak_status": failure_streak_status,
                    "window_hours": int(thresholds["window_hours"]),
                },
            )

        sample_count = len(samples)
        degraded_or_offline = sum(
            1
            for sample in samples
            if _normalize_service_status(sample.get("status")) in {"degraded", "offline"}
        )
        error_rate = (float(degraded_or_offline) / float(sample_count)) * 100.0 if sample_count > 0 else 0.0
        if sample_count >= int(thresholds["minimum_samples"]) and error_rate >= float(thresholds["error_rate_warning"]):
            severity = "warning"
            if error_rate >= float(thresholds["error_rate_critical"]):
                severity = "critical"
            _record_operational_alert(
                category="status_probe",
                severity=severity,
                message=f"{card.get('name', key)} probe error rate is above threshold",
                event_key=f"status_probe_error_rate:{key}",
                context={
                    "service_key": key,
                    "service_name": card.get("name", key),
                    "window_hours": int(thresholds["window_hours"]),
                    "sample_count": int(sample_count),
                    "failed_samples": int(degraded_or_offline),
                    "error_rate_pct": round(error_rate, 1),
                    "warning_threshold_pct": int(thresholds["error_rate_warning"]),
                    "critical_threshold_pct": int(thresholds["error_rate_critical"]),
                },
            )

        latencies = [
            int(float(sample.get("latency_ms")))
            for sample in samples
            if sample.get("latency_ms") is not None
            and str(sample.get("latency_ms")).strip() != ""
            and _normalize_service_status(sample.get("status")) in {"online", "degraded"}
        ]
        if len(latencies) >= int(thresholds["minimum_samples"]):
            avg_latency = float(sum(latencies)) / float(len(latencies))
            severity = ""
            if avg_latency >= float(thresholds["latency_critical"]):
                severity = "critical"
            elif avg_latency >= float(thresholds["latency_warning"]):
                severity = "warning"
            if severity:
                _record_operational_alert(
                    category="status_probe",
                    severity=severity,
                    message=f"{card.get('name', key)} probe latency is above threshold",
                    event_key=f"status_probe_latency:{key}",
                    context={
                        "service_key": key,
                        "service_name": card.get("name", key),
                        "window_hours": int(thresholds["window_hours"]),
                        "samples_with_latency": int(len(latencies)),
                        "avg_latency_ms": round(avg_latency, 1),
                        "warning_threshold_ms": int(thresholds["latency_warning"]),
                        "critical_threshold_ms": int(thresholds["latency_critical"]),
                    },
                )


def _safe_percent(numerator: int, denominator: int) -> float:
    denom = max(0, int(denominator))
    if denom <= 0:
        return 0.0
    return round((float(max(0, int(numerator))) / float(denom)) * 100.0, 1)


def _risk_runtime_thresholds() -> dict[str, int]:
    queue_warn = max(1, _env_int("RISK_STATUS_QUEUE_WARN", 10))
    queue_critical = max(queue_warn, _env_int("RISK_STATUS_QUEUE_CRITICAL", 40))
    queue_stall_minutes = max(1, _env_int("RISK_STATUS_QUEUE_STALL_MINUTES", 10))
    stale_running_minutes = max(5, _env_int("RISK_STATUS_STALE_RUNNING_MINUTES", 20))
    window_hours = max(1, _env_int("RISK_STATUS_WINDOW_HOURS", 24))
    failure_rate_warning_pct = max(1, min(100, _env_int("RISK_STATUS_FAILURE_RATE_WARNING_PCT", 25)))
    failure_rate_critical_pct = max(
        failure_rate_warning_pct,
        min(100, _env_int("RISK_STATUS_FAILURE_RATE_CRITICAL_PCT", 50)),
    )
    failure_rate_min_completed = max(1, _env_int("RISK_STATUS_FAILURE_RATE_MIN_COMPLETED", 4))
    return {
        "queue_warn": queue_warn,
        "queue_critical": queue_critical,
        "queue_stall_minutes": queue_stall_minutes,
        "stale_running_minutes": stale_running_minutes,
        "window_hours": window_hours,
        "failure_rate_warning_pct": failure_rate_warning_pct,
        "failure_rate_critical_pct": failure_rate_critical_pct,
        "failure_rate_min_completed": failure_rate_min_completed,
    }


def _build_risk_engine_cards() -> dict[str, Any]:
    store = current_app.config.get("RISK_JOB_STORE")
    if store is None:
        fallback = _build_service_card(
            service_key="risk_worker_runtime",
            name="Risk Worker Runtime",
            status="unknown",
            detail="Risk worker store not configured.",
            latency_ms=None,
            group="Risk Engine",
        )
        return {
            "cards": [fallback],
            "metrics": {
                "counts": {"queued": 0, "running": 0, "succeeded": 0, "failed": 0, "cancelled": 0},
                "stale_running_count": 0,
                "recent": {"succeeded": 0, "failed": 0, "cancelled": 0},
            },
            "thresholds": _risk_runtime_thresholds(),
        }

    thresholds = _risk_runtime_thresholds()
    metrics = store.build_runtime_metrics(
        window_hours=int(thresholds["window_hours"]),
        stale_running_minutes=int(thresholds["stale_running_minutes"]),
    )

    counts = metrics.get("counts", {}) if isinstance(metrics.get("counts"), dict) else {}
    queued = max(0, int(counts.get("queued", 0) or 0))
    running = max(0, int(counts.get("running", 0) or 0))
    stale_running_count = max(0, int(metrics.get("stale_running_count", 0) or 0))

    now_dt = datetime.now(timezone.utc)
    oldest_queued_age_minutes = -1
    oldest_queued_created_at = _parse_utc(str(metrics.get("oldest_queued_created_at_utc", "")))
    if oldest_queued_created_at is not None:
        oldest_queued_age_minutes = max(0, int((now_dt - oldest_queued_created_at).total_seconds() // 60))

    runtime_status = "online"
    runtime_detail_parts: list[str] = [
        f"queued={queued}",
        f"running={running}",
        f"stale_running={stale_running_count}",
    ]
    if oldest_queued_age_minutes >= 0:
        runtime_detail_parts.append(f"oldest_queued_age={oldest_queued_age_minutes}m")

    if stale_running_count > 0:
        runtime_status = "offline"
        runtime_detail_parts.append(
            f"running jobs exceeded stale threshold ({int(thresholds['stale_running_minutes'])}m)"
        )
    elif queued >= int(thresholds["queue_critical"]):
        runtime_status = "degraded"
        runtime_detail_parts.append(f"queue backlog >= critical threshold ({int(thresholds['queue_critical'])})")
    elif queued >= int(thresholds["queue_warn"]):
        runtime_status = "degraded"
        runtime_detail_parts.append(f"queue backlog >= warning threshold ({int(thresholds['queue_warn'])})")
    elif queued > 0 and running <= 0 and oldest_queued_age_minutes >= int(thresholds["queue_stall_minutes"]):
        runtime_status = "degraded"
        runtime_detail_parts.append(
            f"queued jobs waiting without active worker >= {int(thresholds['queue_stall_minutes'])}m"
        )
    else:
        runtime_detail_parts.append("queue/worker conditions healthy")

    last_success = str(metrics.get("last_success_finished_at_utc", "")).strip()
    if last_success:
        runtime_detail_parts.append(f"last_success={last_success}")

    runtime_card = _build_service_card(
        service_key="risk_worker_runtime",
        name="Risk Worker Runtime",
        status=runtime_status,
        detail=" | ".join(runtime_detail_parts),
        latency_ms=None,
        group="Risk Engine",
    )

    recent = metrics.get("recent", {}) if isinstance(metrics.get("recent"), dict) else {}
    succeeded_recent = max(0, int(recent.get("succeeded", 0) or 0))
    failed_recent = max(0, int(recent.get("failed", 0) or 0))
    cancelled_recent = max(0, int(recent.get("cancelled", 0) or 0))
    completed_recent = succeeded_recent + failed_recent + cancelled_recent
    considered_recent = succeeded_recent + failed_recent
    success_rate_pct = _safe_percent(succeeded_recent, considered_recent)
    failure_rate_pct = _safe_percent(failed_recent, considered_recent)

    throughput_status = "online"
    throughput_detail = (
        f"completed_{int(thresholds['window_hours'])}h={completed_recent} "
        f"(succeeded={succeeded_recent}, failed={failed_recent}, cancelled={cancelled_recent}) "
        f"success_rate={success_rate_pct:.1f}%"
    )
    if completed_recent <= 0 and queued > 0:
        throughput_status = "degraded"
        throughput_detail += " | queued jobs pending completion"
    elif considered_recent >= int(thresholds["failure_rate_min_completed"]):
        if failure_rate_pct >= float(thresholds["failure_rate_critical_pct"]):
            throughput_status = "degraded"
            throughput_detail += (
                f" | failure rate >= critical threshold ({int(thresholds['failure_rate_critical_pct'])}%)"
            )
        elif failure_rate_pct >= float(thresholds["failure_rate_warning_pct"]):
            throughput_status = "degraded"
            throughput_detail += (
                f" | failure rate >= warning threshold ({int(thresholds['failure_rate_warning_pct'])}%)"
            )

    throughput_card = _build_service_card(
        service_key="risk_jobs_24h",
        name=f"Risk Jobs Throughput ({int(thresholds['window_hours'])}h)",
        status=throughput_status,
        detail=throughput_detail,
        latency_ms=None,
        group="Risk Engine",
    )

    enriched_metrics = dict(metrics)
    enriched_metrics["success_rate_pct"] = success_rate_pct
    enriched_metrics["failure_rate_pct"] = failure_rate_pct
    enriched_metrics["considered_recent"] = considered_recent
    return {
        "cards": [runtime_card, throughput_card],
        "metrics": enriched_metrics,
        "thresholds": thresholds,
    }


def _evaluate_risk_runtime_alerts(*, metrics: dict, thresholds: dict) -> None:
    counts = metrics.get("counts", {}) if isinstance(metrics.get("counts"), dict) else {}
    recent = metrics.get("recent", {}) if isinstance(metrics.get("recent"), dict) else {}
    stale_running_count = max(0, int(metrics.get("stale_running_count", 0) or 0))
    queued = max(0, int(counts.get("queued", 0) or 0))
    running = max(0, int(counts.get("running", 0) or 0))
    failed_recent = max(0, int(recent.get("failed", 0) or 0))
    succeeded_recent = max(0, int(recent.get("succeeded", 0) or 0))
    considered_recent = max(0, int(metrics.get("considered_recent", 0) or 0))
    failure_rate_pct = float(metrics.get("failure_rate_pct", 0.0) or 0.0)

    if stale_running_count > 0:
        _record_operational_alert(
            category="risk_worker",
            severity="critical",
            message="Risk worker has stale running jobs beyond threshold",
            event_key="risk_worker_stale_running",
            context={
                "stale_running_count": stale_running_count,
                "stale_running_minutes": int(thresholds.get("stale_running_minutes", 0) or 0),
                "queued": queued,
                "running": running,
            },
        )

    if queued >= int(thresholds.get("queue_critical", 0) or 0):
        _record_operational_alert(
            category="risk_worker",
            severity="error",
            message="Risk worker queue backlog reached critical threshold",
            event_key="risk_worker_queue_backlog_critical",
            context={
                "queued": queued,
                "queue_warn": int(thresholds.get("queue_warn", 0) or 0),
                "queue_critical": int(thresholds.get("queue_critical", 0) or 0),
            },
        )

    min_completed = int(thresholds.get("failure_rate_min_completed", 1) or 1)
    if considered_recent >= min_completed and failure_rate_pct >= float(
        thresholds.get("failure_rate_critical_pct", 100) or 100
    ):
        _record_operational_alert(
            category="risk_worker",
            severity="critical",
            message="Risk worker failure rate reached critical threshold",
            event_key="risk_worker_failure_rate_critical",
            context={
                "window_hours": int(thresholds.get("window_hours", 24) or 24),
                "succeeded": succeeded_recent,
                "failed": failed_recent,
                "considered": considered_recent,
                "failure_rate_pct": round(failure_rate_pct, 1),
                "failure_rate_warning_pct": int(thresholds.get("failure_rate_warning_pct", 0) or 0),
                "failure_rate_critical_pct": int(thresholds.get("failure_rate_critical_pct", 0) or 0),
            },
        )


def _evaluate_infra_card_alerts(*, infra_cards: List[dict]) -> None:
    for card in infra_cards:
        key = str(card.get("key", "")).strip().lower()
        status = str(card.get("status", "")).strip().lower()
        if key == "storage_data" and status in {"degraded", "offline"}:
            _record_operational_alert(
                category="infra",
                severity="critical" if status == "offline" else "warning",
                message="Storage/DB capacity thresholds reached",
                event_key="infra_storage_capacity",
                context={"service_key": key, "status": status, "detail": str(card.get("detail", ""))},
            )
        if key == "tls_edge_cert" and status in {"degraded", "offline"}:
            _record_operational_alert(
                category="infra",
                severity="critical" if status == "offline" else "warning",
                message="Public TLS certificate is near expiry or probe failed",
                event_key="infra_tls_edge",
                context={"service_key": key, "status": status, "detail": str(card.get("detail", ""))},
            )


def _extract_status_sampler_secret() -> str:
    auth_header = str(request.headers.get("Authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    header_secret = str(request.headers.get("X-Status-Sampler-Secret", "")).strip()
    if header_secret:
        return header_secret

    query_secret = str(request.args.get("secret", "")).strip()
    if query_secret:
        return query_secret
    return ""


def _authorize_status_sampler_request() -> tuple[bool, dict, int]:
    settings = current_app.config["SETTINGS"]
    configured_secret = str(settings.status_sampler_secret or "").strip()
    if not configured_secret:
        return (
            False,
            {
                "error": "status_sampler_secret_not_configured",
                "message": "Set STATUS_SAMPLER_SECRET before using the internal status sampler endpoint.",
            },
            503,
        )

    provided_secret = _extract_status_sampler_secret()
    if not provided_secret or not hmac.compare_digest(provided_secret, configured_secret):
        return (
            False,
            {
                "error": "unauthorized",
                "message": "Invalid status sampler secret.",
            },
            401,
        )
    return True, {"status": "authorized"}, 200


def _collect_services_status_snapshot(*, persist_samples: bool = True) -> dict[str, Any]:
    settings = current_app.config["SETTINGS"]
    status_store = current_app.config["STATUS_STORE"]

    website_status = _build_service_card(
        service_key="website_api",
        name="Website API",
        status="online",
        detail="/healthz responding",
        latency_ms=1,
        group="Core",
    )

    script_health_url = str(os.getenv("SCRIPT_API_HEALTH_URL", "")).strip()
    script_probe_headers = _script_api_probe_auth_headers()
    script_status, script_detail, script_latency = _http_get_health(
        script_health_url,
        timeout_seconds=3,
        extra_headers=script_probe_headers,
    )
    script_api_card = _build_service_card(
        service_key="script_api",
        name="Script API",
        status=script_status,
        detail=script_detail if script_health_url else "Set SCRIPT_API_HEALTH_URL to enable active checks",
        latency_ms=script_latency,
        group="Core",
    )

    mailer = current_app.config["SUPPORT_MAILER"]
    support_mail_card = _build_service_card(
        service_key="support_services",
        name="Support Mail Delivery",
        status="online" if bool(mailer.configured) else "degraded",
        detail="SMTP configured and ticket notifications available" if bool(mailer.configured) else "SMTP not configured",
        latency_ms=None,
        group="Messaging",
    )

    inbound_ready = bool(settings.support_inbound_webhook_secret and settings.support_resend_api_key and settings.support_inbound_routing_active)
    inbound_card = _build_service_card(
        service_key="inbound_webhook",
        name="Inbound Reply Webhook",
        status="online" if inbound_ready else "degraded",
        detail=(
            "Resend inbound webhook, secret, and routing are active"
            if inbound_ready
            else "Check SUPPORT_INBOUND_WEBHOOK_SECRET, SUPPORT_RESEND_API_KEY, SUPPORT_INBOUND_ROUTING_ACTIVE"
        ),
        latency_ms=None,
        group="Messaging",
    )

    nowpayments_status = "disabled"
    nowpayments_detail = "NOWPayments disabled in environment"
    nowpayments_latency = None
    if settings.nowpayments_enabled and settings.nowpayments_api_key:
        now_started = time.perf_counter()
        available = _nowpayments_adapter().list_available_currencies()
        nowpayments_latency = int((time.perf_counter() - now_started) * 1000)
        if available:
            nowpayments_status = "online"
            nowpayments_detail = f"{len(available)} pay currencies available"
        else:
            nowpayments_status = "degraded"
            nowpayments_detail = "Provider reachable check failed or no currencies returned"
    nowpayments_card = _build_service_card(
        service_key="billing_nowpayments",
        name="NOWPayments Provider",
        status=nowpayments_status,
        detail=nowpayments_detail,
        latency_ms=nowpayments_latency,
        group="Billing",
    )

    script_probe_cards = []
    deep_probe_configs = [
        ("script_api_eth", "Script API Deep Probe · ETH", str(os.getenv("SCRIPT_API_ETH_HEALTH_URL", "")).strip()),
        ("script_api_bsc", "Script API Deep Probe · BSC", str(os.getenv("SCRIPT_API_BSC_HEALTH_URL", "")).strip()),
        ("script_api_tron", "Script API Deep Probe · TRON", str(os.getenv("SCRIPT_API_TRON_HEALTH_URL", "")).strip()),
    ]
    for probe_key, probe_name, probe_url in deep_probe_configs:
        probe_status, probe_detail, probe_latency = _http_get_health(
            probe_url,
            timeout_seconds=3,
            extra_headers=script_probe_headers,
            parse_json_detail=True,
        )
        card = _build_service_card(
            service_key=probe_key,
            name=probe_name,
            status=probe_status,
            detail=probe_detail if probe_url else "Not configured. Set environment URL to enable active probe.",
            latency_ms=probe_latency,
            group="Script API",
        )
        if probe_url:
            card.update(_script_probe_detail_fields(str(card.get("detail", ""))))
        script_probe_cards.append(card)

    eth_url = str(os.getenv("STATUS_ETH_RPC_URL", "https://rpc.ankr.com/eth")).strip()
    bsc_url = str(os.getenv("STATUS_BSC_RPC_URL", "https://rpc.ankr.com/bsc")).strip()
    tron_url = str(os.getenv("STATUS_TRON_RPC_URL", "https://api.trongrid.io/wallet/getnowblock")).strip()

    eth_status, eth_detail, eth_latency = _json_post_health(
        eth_url,
        {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
        timeout_seconds=3,
    )
    bsc_status, bsc_detail, bsc_latency = _json_post_health(
        bsc_url,
        {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
        timeout_seconds=3,
    )
    tron_status, tron_detail, tron_latency = _json_post_health(tron_url, {}, timeout_seconds=3)

    chain_cards = [
        _build_service_card(
            service_key="chain_eth_rpc",
            name="Ethereum RPC",
            status=eth_status,
            detail=f"{eth_detail} • {eth_url}",
            latency_ms=eth_latency,
            group="Chains",
        ),
        _build_service_card(
            service_key="chain_bsc_rpc",
            name="BSC RPC",
            status=bsc_status,
            detail=f"{bsc_detail} • {bsc_url}",
            latency_ms=bsc_latency,
            group="Chains",
        ),
        _build_service_card(
            service_key="chain_tron_rpc",
            name="TRON RPC",
            status=tron_status,
            detail=f"{tron_detail} • {tron_url}",
            latency_ms=tron_latency,
            group="Chains",
        ),
    ]

    edge_timeout = max(2, _env_int("STATUS_PUBLIC_EDGE_TIMEOUT_SECONDS", 6))
    public_marketing_status, public_marketing_detail, public_marketing_latency = _http_get_health(
        str(getattr(settings, "web_portal_marketing_base_url", "")).strip(),
        timeout_seconds=edge_timeout,
    )
    public_app_status, public_app_detail, public_app_latency = _http_get_health(
        str(getattr(settings, "web_portal_app_base_url", "")).strip(),
        timeout_seconds=edge_timeout,
    )
    public_edge_cards = [
        _build_service_card(
            service_key="public_marketing_edge",
            name="Public Edge · Marketing Host",
            status=public_marketing_status,
            detail=public_marketing_detail,
            latency_ms=public_marketing_latency,
            group="Public Edge",
        ),
        _build_service_card(
            service_key="public_app_edge",
            name="Public Edge · App Host",
            status=public_app_status,
            detail=public_app_detail,
            latency_ms=public_app_latency,
            group="Public Edge",
        ),
    ]

    app_host = _hostname_from_url(str(getattr(settings, "web_portal_app_base_url", "")).strip())
    nginx_local_url = str(os.getenv("STATUS_NGINX_LOCAL_URL", "http://127.0.0.1/healthz")).strip()
    nginx_headers: dict[str, str] = {}
    if app_host:
        nginx_headers["Host"] = app_host
    nginx_local_status, nginx_local_detail, nginx_local_latency = _http_get_health(
        nginx_local_url,
        timeout_seconds=max(2, _env_int("STATUS_NGINX_LOCAL_TIMEOUT_SECONDS", 3)),
        extra_headers=nginx_headers or None,
    )

    tls_status, tls_detail, tls_latency = _tls_days_remaining(
        app_host or _hostname_from_url(str(getattr(settings, "web_portal_public_base_url", "")).strip()),
        timeout_seconds=max(2, _env_int("STATUS_TLS_TIMEOUT_SECONDS", 4)),
    )
    storage_status, storage_detail, storage_latency = _storage_health_detail(settings)
    infra_cards = [
        _build_service_card(
            service_key="nginx_local",
            name="Nginx Local Proxy",
            status=nginx_local_status,
            detail=f"{nginx_local_detail} • {nginx_local_url}",
            latency_ms=nginx_local_latency,
            group="Infrastructure",
        ),
        _build_service_card(
            service_key="tls_edge_cert",
            name="TLS Edge Certificate",
            status=tls_status,
            detail=tls_detail,
            latency_ms=tls_latency,
            group="Infrastructure",
        ),
        _build_service_card(
            service_key="storage_data",
            name="Storage & DB Footprint",
            status=storage_status,
            detail=storage_detail,
            latency_ms=storage_latency,
            group="Infrastructure",
        ),
    ]

    risk_payload = _build_risk_engine_cards()
    risk_engine_cards = list(risk_payload.get("cards", []))

    api_cards = [website_status, script_api_card, support_mail_card, inbound_card, nowpayments_card]
    all_cards = api_cards + script_probe_cards + chain_cards + public_edge_cards + risk_engine_cards + infra_cards

    if persist_samples and status_store is not None:
        status_store.record_samples(
            {
                "service_key": card["key"],
                "service_name": card["name"],
                "group_name": card["group"],
                "status": card["status"],
                "latency_ms": card["latency_ms"],
                "detail": card["detail"],
            }
            for card in all_cards
        )

    api_cards = [_apply_status_history_metrics(card) for card in api_cards]
    script_probe_cards = [_apply_status_history_metrics(card) for card in script_probe_cards]
    chain_cards = [_apply_status_history_metrics(card) for card in chain_cards]
    public_edge_cards = [_apply_status_history_metrics(card) for card in public_edge_cards]
    risk_engine_cards = [_apply_status_history_metrics(card) for card in risk_engine_cards]
    infra_cards = [_apply_status_history_metrics(card) for card in infra_cards]
    all_cards = api_cards + script_probe_cards + chain_cards + public_edge_cards + risk_engine_cards + infra_cards
    if persist_samples:
        _evaluate_status_probe_alerts(cards=all_cards)
        _evaluate_risk_runtime_alerts(
            metrics=risk_payload.get("metrics", {}),
            thresholds=risk_payload.get("thresholds", {}),
        )
        _evaluate_infra_card_alerts(infra_cards=infra_cards)

    summary = {
        "online": sum(1 for item in all_cards if item["status"] == "online"),
        "degraded": sum(1 for item in all_cards if item["status"] == "degraded"),
        "offline": sum(1 for item in all_cards if item["status"] == "offline"),
        "disabled": sum(1 for item in all_cards if item["status"] == "disabled"),
        "avg_uptime_percent": round(sum(item["uptime_percent"] for item in all_cards) / max(1, len(all_cards)), 1),
    }
    return {
        "api_cards": api_cards,
        "script_probe_cards": script_probe_cards,
        "chain_cards": chain_cards,
        "public_edge_cards": public_edge_cards,
        "risk_engine_cards": risk_engine_cards,
        "infra_cards": infra_cards,
        "summary": summary,
        "service_total": len(all_cards),
    }


def _is_script_watchdog_alert(alert: dict) -> bool:
    category = str(alert.get("category", "")).strip().lower()
    event_key = str(alert.get("event_key", "")).strip().lower()
    context = alert.get("context")
    if not isinstance(context, dict):
        context = {}
    service_key = str(context.get("service_key", "")).strip().lower()

    if service_key.startswith("script_api"):
        return True
    if event_key.startswith("status_probe_") and ":script_api" in event_key:
        return True
    if category in {"script_api", "script_api_watchdog"}:
        return True
    return False


def _script_watchdog_service_key(alert: dict) -> str:
    context = alert.get("context")
    if isinstance(context, dict):
        service_key = str(context.get("service_key", "")).strip().lower()
        if service_key:
            return service_key
    event_key = str(alert.get("event_key", "")).strip().lower()
    if ":" in event_key:
        suffix = event_key.rsplit(":", 1)[-1].strip().lower()
        if suffix.startswith("script_api"):
            return suffix
    return "script_api"


def _collect_script_watchdog_failures_24h(*, hours: int = 24, limit: int = 80) -> dict[str, Any]:
    store = current_app.config.get("SUPPORT_TICKET_STORE")
    if store is None:
        return {
            "alerts": [],
            "summary": {
                "total": 0,
                "open": 0,
                "resolved": 0,
                "critical": 0,
            },
        }

    lookback_hours = max(1, int(hours))
    max_items = max(1, min(int(limit), 250))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    candidates = store.list_operational_alerts(open_only=False, limit=max(max_items * 5, 250))

    alerts: list[dict[str, Any]] = []
    for alert in candidates:
        created_dt = _parse_utc(str(alert.get("created_at_utc", "")))
        if created_dt is None or created_dt < cutoff:
            continue
        if not _is_script_watchdog_alert(alert):
            continue

        normalized = dict(alert)
        resolved = bool(str(alert.get("resolved_at_utc", "")).strip())
        normalized["state_label"] = "resolved" if resolved else "open"
        normalized["state_class"] = "online" if resolved else "degraded"
        normalized["service_key"] = _script_watchdog_service_key(alert)
        alerts.append(normalized)
        if len(alerts) >= max_items:
            break

    summary = {
        "total": len(alerts),
        "open": sum(1 for alert in alerts if str(alert.get("state_label", "")) == "open"),
        "resolved": sum(1 for alert in alerts if str(alert.get("state_label", "")) == "resolved"),
        "critical": sum(1 for alert in alerts if str(alert.get("severity", "")).strip().lower() == "critical"),
    }
    return {"alerts": alerts, "summary": summary}


def _send_ticket_status_notice(ticket: dict, target_status: str) -> None:
    status = str(target_status or "").strip().lower()
    if status not in {"in_progress", "resolved"}:
        return
    mailer = current_app.config.get("ACCOUNT_MAILER")
    if mailer is None:
        return
    result = mailer.send_ticket_status_notice(
        email=str(ticket.get("customer_email", "")).strip().lower(),
        ticket_ref=str(ticket.get("ticket_ref", "")).strip(),
        status=status,
    )
    if not bool(result.get("sent")):
        error = str(result.get("error", "unknown_error"))
        ticket_ref = str(ticket.get("ticket_ref", ""))
        _record_operational_alert(
            category="account_mailer",
            severity="warning",
            message="Ticket status notice email failed",
            event_key=f"ticket_status_notice:{ticket_ref}:{status}",
            context={"ticket_ref": ticket_ref, "status": status, "error": error},
        )
        current_app.logger.error(
            "ticket_status_notice_failed ticket=%s status=%s detail=%s",
            str(ticket.get("ticket_ref", "")),
            status,
            result,
        )


def _get_reply_queue() -> List[str]:
    raw = session.get("support_reply_queue", [])
    if not isinstance(raw, list):
        return []
    return _sanitize_ticket_refs([str(item) for item in raw])


def _set_reply_queue(queue: List[str]) -> None:
    cleaned = _sanitize_ticket_refs(queue)
    if cleaned:
        session["support_reply_queue"] = cleaned
        return
    session.pop("support_reply_queue", None)


def _remove_from_reply_queue(ticket_refs: List[str]) -> None:
    to_remove = set(_sanitize_ticket_refs(ticket_refs))
    if not to_remove:
        return
    queue = [ref for ref in _get_reply_queue() if ref not in to_remove]
    _set_reply_queue(queue)


def _prioritize_reply_queue(ticket_refs: List[str]) -> None:
    priority = _sanitize_ticket_refs(ticket_refs)
    if not priority:
        return
    existing = _get_reply_queue()
    queue = priority + [ref for ref in existing if ref not in set(priority)]
    _set_reply_queue(queue)


def _is_admin_like_user(user: dict | None) -> bool:
    role = str((user or {}).get("role", "")).strip().lower()
    return role in {"master", "admin"}


def _can_access_risk_job(user: dict | None, job: dict | None) -> bool:
    if not user or not job:
        return False
    if _is_admin_like_user(user):
        return True
    return int(user.get("id") or 0) == int(job.get("requested_by_user_id") or 0)


def _risk_job_scope_user_id(user: dict | None) -> int | None:
    if _is_admin_like_user(user):
        return None
    try:
        user_id = int((user or {}).get("id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    return user_id if user_id > 0 else -1


def _risk_band_from_score(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _risk_band_view(band: str) -> tuple[str, str]:
    normalized = str(band or "").strip().lower()
    if normalized == "high":
        return "High Risk", "status-offline"
    if normalized == "medium":
        return "Medium Risk", "status-degraded"
    if normalized == "low":
        return "Low Risk", "status-online"
    return "Unknown", "status-unknown"


def _dashboard_signal_payload(job: dict | None) -> dict[str, Any]:
    candidate = job or {}
    artifacts = candidate.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            metadata = artifact.get("metadata")
            if not isinstance(metadata, dict) or not metadata:
                continue
            if any(key in metadata for key in {"risk_band", "risk_score", "confidence_pct", "signals", "model"}):
                return metadata
    metadata = candidate.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _dashboard_signal_snapshot(job: dict | None) -> dict[str, Any]:
    candidate = job or {}
    payload = _dashboard_signal_payload(candidate)
    risk_score = _parse_int_like(payload.get("risk_score"))
    confidence_pct = _parse_int_like(payload.get("confidence_pct"))
    risk_band = str(payload.get("risk_band", "")).strip().lower() or _risk_band_from_score(risk_score)
    risk_band_label, risk_band_class = _risk_band_view(risk_band)

    model = str(payload.get("model", "")).strip().lower() or str(candidate.get("mode", "")).strip().lower()
    token_chain = str(payload.get("token_chain", "")).strip().lower() or str(candidate.get("token_chain", "")).strip().lower()
    token_address = str(payload.get("token_address", "")).strip() or str(candidate.get("token_address", "")).strip()

    top_signals: list[dict[str, Any]] = []
    signals = payload.get("signals")
    if isinstance(signals, dict):
        for key, value in signals.items():
            score = _parse_int_like(value)
            if score is None:
                continue
            label = str(key or "").strip().replace("_", " ").title()
            if not label:
                continue
            top_signals.append({"name": label, "score": score})
        top_signals.sort(key=lambda item: (-int(item["score"]), str(item["name"]).lower()))
        top_signals = top_signals[:4]

    return {
        "risk_band": risk_band,
        "risk_band_label": risk_band_label,
        "risk_band_class": risk_band_class,
        "risk_score": risk_score,
        "risk_score_label": str(risk_score) if risk_score is not None else "n/a",
        "confidence_pct": confidence_pct,
        "confidence_label": f"{confidence_pct}%" if confidence_pct is not None else "n/a",
        "model_label": str(model).upper() if model else "n/a",
        "token_chain_label": str(token_chain).upper() if token_chain else "n/a",
        "token_address_label": token_address or "n/a",
        "top_signals": top_signals,
        "has_signal_data": bool(risk_score is not None or confidence_pct is not None or top_signals),
    }


@pages_bp.get("/")
def homepage():
    settings = current_app.config["SETTINGS"]
    donation_widget_url = str(settings.nowpayments_donation_widget_url or "").strip()
    donation_link_url = str(settings.nowpayments_donation_link_url or "").strip()
    return render_template(
        "pages/homepage.html",
        donation_widget_url=donation_widget_url,
        donation_link_url=donation_link_url,
    )


@pages_bp.route("/human-check", methods=["GET", "POST"])
def human_check():
    settings = current_app.config["SETTINGS"]
    next_target = _safe_local_next(
        str(request.values.get("next", "") or session.get("human_check_next", "")),
        fallback_endpoint="pages.homepage",
    )

    if request.method in {"GET", "HEAD"}:
        if not settings.turnstile_enforce:
            return redirect(next_target)
        if bool(session.get("human_verified")):
            try:
                verified_at_epoch = int(session.get("human_verified_at_epoch") or 0)
            except (TypeError, ValueError):
                verified_at_epoch = 0
            if verified_at_epoch > 0 and (int(time.time()) - verified_at_epoch) <= (6 * 60 * 60):
                return redirect(next_target)
            session.pop("human_verified", None)
            session.pop("human_verified_at_epoch", None)
        session["human_check_next"] = next_target
        return render_template(
            "pages/human_check.html",
            turnstile_site_key=settings.turnstile_site_key,
            next_target=next_target,
        )

    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(url_for("pages.human_check", next=next_target))

    if not settings.turnstile_enforce:
        return redirect(next_target)

    response_token = str(request.form.get("cf-turnstile-response", "")).strip()
    remote_ip = _extract_client_ip()
    verified, error_code = verify_turnstile_token(
        secret_key=settings.turnstile_secret_key,
        response_token=response_token,
        remote_ip=remote_ip,
    )
    if not verified:
        current_app.logger.warning(
            "human_check_failed error=%s host=%s next=%s",
            error_code,
            str(request.host or "").strip().lower(),
            next_target,
        )
        flash("Human verification failed. Please try again.", "error")
        return render_template(
            "pages/human_check.html",
            turnstile_site_key=settings.turnstile_site_key,
            next_target=next_target,
            turnstile_error=error_code,
        ), 400

    session["human_verified"] = True
    session["human_verified_at_epoch"] = int(time.time())
    current_app.logger.info(
        "human_check_passed host=%s next=%s",
        str(request.host or "").strip().lower(),
        next_target,
    )
    session.pop("human_check_next", None)
    flash("Human verification completed.", "success")
    return redirect(next_target)


@pages_bp.get("/dashboard")
@login_required
def dashboard():
    user = get_current_user() or {}
    store = current_app.config["RISK_JOB_STORE"]
    scoped_user_id = _risk_job_scope_user_id(user)
    jobs = store.list_jobs(requested_by_user_id=scoped_user_id, limit=250)
    counts = {"queued": 0, "running": 0, "succeeded": 0, "failed": 0, "cancelled": 0}
    recent_success = 0
    recent_failed = 0
    recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    active_job = None
    for job in jobs:
        status = str(job.get("status", "")).strip().lower()
        if status in counts:
            counts[status] += 1
        created_at = _parse_utc(str(job.get("created_at_utc", "")))
        if created_at and created_at >= recent_cutoff:
            if status == "succeeded":
                recent_success += 1
            elif status == "failed":
                recent_failed += 1
        if active_job is None and status in {"queued", "running"}:
            active_job = job
    latest_job = jobs[0] if jobs else None
    focus_seed = active_job or latest_job
    focus_job = None
    focus_events: list[dict[str, Any]] = []
    focus_signal = _dashboard_signal_snapshot({})
    if focus_seed:
        focus_job = store.get_job(
            str(focus_seed.get("job_id", "")),
            include_events=True,
            include_artifacts=True,
            event_limit=8,
            artifact_limit=8,
        ) or dict(focus_seed)
        raw_events = focus_job.get("events")
        if isinstance(raw_events, list):
            focus_events = [event for event in raw_events if isinstance(event, dict)][:8]
        focus_signal = _dashboard_signal_snapshot(focus_job)

    recent_total = recent_success + recent_failed
    recent_success_rate = round((float(recent_success) / float(recent_total)) * 100.0, 1) if recent_total > 0 else 0.0
    backlog_total = int(counts.get("queued", 0)) + int(counts.get("running", 0))
    backlog_label = "Low"
    backlog_class = "status-online"
    if backlog_total >= 25:
        backlog_label = "High"
        backlog_class = "status-offline"
    elif backlog_total >= 8:
        backlog_label = "Medium"
        backlog_class = "status-degraded"

    recent_jobs_view: list[dict[str, Any]] = []
    for job in jobs[:12]:
        row = dict(job)
        row.update(_dashboard_signal_snapshot(job))
        recent_jobs_view.append(row)

    return render_template(
        "pages/dashboard.html",
        risk_counts=counts,
        risk_recent_success=recent_success,
        risk_recent_failed=recent_failed,
        risk_recent_total=recent_total,
        risk_recent_success_rate=recent_success_rate,
        risk_backlog_total=backlog_total,
        risk_backlog_label=backlog_label,
        risk_backlog_class=backlog_class,
        latest_risk_job=latest_job,
        active_risk_job=active_job,
        focus_risk_job=focus_job,
        focus_risk_events=focus_events,
        focus_risk_signal=focus_signal,
        recent_risk_jobs=recent_jobs_view,
    )


@pages_bp.get("/live-assessment")
@login_required
def live_assessment():
    user = get_current_user() or {}
    store = current_app.config["RISK_JOB_STORE"]
    scoped_user_id = _risk_job_scope_user_id(user)
    requested_job_id = str(request.args.get("job_id", "")).strip()
    selected_job = None
    if requested_job_id:
        candidate = store.get_job(
            requested_job_id,
            include_events=True,
            include_artifacts=True,
            event_limit=120,
            artifact_limit=40,
        )
        if candidate and _can_access_risk_job(user, candidate):
            selected_job = candidate

    recent_jobs = store.list_jobs(requested_by_user_id=scoped_user_id, limit=40)
    if selected_job is None and recent_jobs:
        preferred = next((item for item in recent_jobs if str(item.get("status", "")).strip().lower() in {"queued", "running"}), None)
        selected_seed = preferred or recent_jobs[0]
        selected_job = store.get_job(
            str(selected_seed.get("job_id", "")),
            include_events=True,
            include_artifacts=True,
            event_limit=120,
            artifact_limit=40,
        )

    return render_template(
        "pages/live_assessment.html",
        selected_job=selected_job,
        recent_jobs=recent_jobs[:15],
    )


@pages_bp.get("/settings")
@roles_required("master", "admin")
def settings_page():
    return render_template("pages/settings.html")


@pages_bp.get("/services-status")
@login_required
@roles_required("master", "admin")
def services_status_page():
    billing_store = current_app.config["BILLING_STORE"]
    snapshot = _collect_services_status_snapshot(persist_samples=True)
    watchdog_snapshot = _collect_script_watchdog_failures_24h(hours=24, limit=80)

    app_started_at_utc = _parse_utc(str(current_app.config.get("APP_STARTED_AT_UTC", "")))
    app_uptime = "N/A"
    if app_started_at_utc:
        elapsed = max(0, int((datetime.now(timezone.utc) - app_started_at_utc).total_seconds()))
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        app_uptime = f"{hours}h {minutes}m"
    reconciliation = billing_store.build_reconciliation_report(limit=250)

    return render_template(
        "pages/services_status.html",
        api_cards=snapshot["api_cards"],
        script_probe_cards=snapshot["script_probe_cards"],
        chain_cards=snapshot["chain_cards"],
        public_edge_cards=snapshot["public_edge_cards"],
        risk_engine_cards=snapshot["risk_engine_cards"],
        infra_cards=snapshot["infra_cards"],
        summary=snapshot["summary"],
        watchdog_alerts_24h=watchdog_snapshot["alerts"],
        watchdog_summary=watchdog_snapshot["summary"],
        app_uptime=app_uptime,
        app_started_at_utc=str(current_app.config.get("APP_STARTED_AT_UTC", "")),
        reconciliation_summary=reconciliation["summary"],
    )


@pages_bp.post("/api/v1/internal/status-sample")
def status_sample_internal():
    authorized, error_payload, error_status = _authorize_status_sampler_request()
    if not authorized:
        return jsonify(error_payload), error_status

    snapshot = _collect_services_status_snapshot(persist_samples=True)
    sampled_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        jsonify(
            {
                "status": "ok",
                "sampled_at_utc": sampled_at_utc,
                "service_total": int(snapshot.get("service_total", 0)),
                "summary": snapshot.get("summary", {}),
            }
        ),
        200,
    )


@pages_bp.post("/services-status/nowpayments/sync")
@login_required
@roles_required("master", "admin")
def services_status_nowpayments_sync():
    next_target = _safe_local_next(str(request.form.get("next", "")), fallback_endpoint="pages.billing_reconciliation_page")
    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(next_target)

    settings = current_app.config["SETTINGS"]
    if not settings.nowpayments_enabled or not settings.nowpayments_api_key:
        flash("NOWPayments is disabled or API key is missing.", "error")
        return redirect(next_target)

    available = _nowpayments_adapter().list_available_currencies()
    if not available:
        flash("NOWPayments sync failed: no currencies returned by provider.", "error")
        return redirect(next_target)

    payload = [{"code": code, "label": _pay_currency_label(code)} for code in available]
    result = current_app.config["BILLING_STORE"].sync_nowpayments_currencies(options=payload, source="manual_sync")
    _audit_privileged_operation(
        operation_type="billing_nowpayments_currency_sync",
        details={
            "inserted": int(result.get("inserted", 0) or 0),
            "updated": int(result.get("updated", 0) or 0),
            "currency_count": len(payload),
        },
    )
    flash(
        f"NOWPayments currencies synced. Inserted {int(result.get('inserted', 0))}, updated {int(result.get('updated', 0))}.",
        "success",
    )
    return redirect(next_target)


@pages_bp.post("/services-status/nowpayments/override")
@login_required
@roles_required("master", "admin")
def services_status_nowpayments_override():
    next_target = _safe_local_next(str(request.form.get("next", "")), fallback_endpoint="pages.billing_reconciliation_page")
    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(next_target)

    code = str(request.form.get("code", "")).strip().lower()
    label = str(request.form.get("label", "")).strip()
    enabled = str(request.form.get("enabled", "")).strip().lower() in {"1", "true", "yes", "on"}
    if not code:
        flash("Currency code is required.", "error")
        return redirect(next_target)

    if not current_app.config["BILLING_STORE"].set_nowpayments_currency_enabled(
        code=code,
        label=label,
        is_enabled=enabled,
        source="admin_override",
    ):
        flash("Unable to update currency override.", "error")
        return redirect(next_target)

    _audit_privileged_operation(
        operation_type="billing_nowpayments_currency_override",
        details={"code": code, "label": label, "is_enabled": bool(enabled)},
    )
    flash(f"Currency {code.upper()} override updated ({'enabled' if enabled else 'disabled'}).", "success")
    return redirect(next_target)


@pages_bp.post("/billing-reconciliation/action")
@login_required
@roles_required("master", "admin")
def billing_reconciliation_action():
    next_target = _safe_local_next(str(request.form.get("next", "")), fallback_endpoint="pages.billing_reconciliation_page")
    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(next_target)

    actor = get_current_user() or {}
    actor_user_id = int(actor.get("id") or 0)
    actor_email = str(actor.get("email") or "").strip().lower()
    if actor_user_id <= 0 or not actor_email:
        flash("Unable to validate operator identity.", "error")
        return redirect(next_target)

    action_type = str(request.form.get("action_type", "")).strip().lower()
    issue_type = str(request.form.get("issue_type", "")).strip().lower()
    issue_key = str(request.form.get("issue_key", "")).strip()
    order_id = str(request.form.get("order_id", "")).strip()
    event_id = str(request.form.get("event_id", "")).strip()
    reason = str(request.form.get("reason", "")).strip()

    if action_type not in RECONCILIATION_ACTION_TYPES:
        flash("Unsupported reconciliation action.", "error")
        return redirect(next_target)
    if issue_type not in RECONCILIATION_ISSUE_TYPES or not issue_key:
        flash("Issue reference is missing or invalid.", "error")
        return redirect(next_target)
    if not reason:
        flash("Action reason is required.", "error")
        return redirect(next_target)

    billing_store = current_app.config["BILLING_STORE"]
    result_status = "failed"
    result_details: Dict[str, Any] = {}
    flash_message = "Reconciliation action failed."
    flash_category = "error"

    if action_type == "reapply_webhook":
        if event_id:
            outcome = billing_store.reapply_nowpayments_webhook_event(event_id=event_id)
        elif order_id:
            outcome = billing_store.reapply_nowpayments_webhook_for_order(order_id=order_id)
        else:
            outcome = {"ok": False, "error": "missing_target_ref"}
        result_details = {"outcome": outcome}
        if bool(outcome.get("ok")):
            result_status = "success"
            flash_message = "Webhook replay applied successfully."
            flash_category = "success"
        else:
            flash_message = f"Webhook replay failed: {str(outcome.get('error') or 'unknown_error')}"
    elif action_type == "manual_activate_subscription":
        outcome = billing_store.manual_activate_subscription_for_order(
            order_id=order_id,
            source=f"manual_repair:{actor_email}",
        )
        result_details = {"outcome": outcome}
        if bool(outcome.get("ok")):
            result_status = "success"
            flash_message = "Subscription manually activated."
            flash_category = "success"
        else:
            flash_message = f"Manual activation failed: {str(outcome.get('error') or 'unknown_error')}"
    else:
        result_status = "closed"
        result_details = {"outcome": {"closed": True}}
        flash_message = "Issue marked as false positive."
        flash_category = "success"

    try:
        billing_store.record_reconciliation_action(
            action_type=action_type,
            issue_type=issue_type,
            issue_key=issue_key,
            order_id=order_id,
            event_id=event_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            reason=reason,
            result_status=result_status,
            details=result_details,
        )
    except Exception:
        current_app.logger.exception(
            "billing_reconciliation_action_audit_failed action=%s issue_type=%s issue_key=%s",
            action_type,
            issue_type,
            issue_key,
        )
        flash("Action executed but audit logging failed. Check server logs.", "error")
        return redirect(next_target)

    _audit_privileged_operation(
        operation_type="billing_reconciliation_action",
        details={
            "action_type": action_type,
            "issue_type": issue_type,
            "issue_key": issue_key,
            "order_id": order_id,
            "event_id": event_id,
            "result_status": result_status,
            "reason": reason,
        },
    )
    flash(flash_message, flash_category)
    return redirect(next_target)


@pages_bp.get("/billing-reconciliation")
@login_required
@roles_required("master", "admin")
def billing_reconciliation_page():
    settings = current_app.config["SETTINGS"]
    billing_store = current_app.config["BILLING_STORE"]
    report = billing_store.build_reconciliation_report(limit=300)
    effective_currency_options = _effective_pay_currency_options(settings)
    nowpayments_currency_rows = billing_store.list_nowpayments_currencies(include_disabled=True, limit=300)
    reconciliation_actions = billing_store.list_reconciliation_actions(limit=120)

    available_nowpayments_currencies: list[str] = []
    if settings.nowpayments_enabled and settings.nowpayments_api_key:
        available_nowpayments_currencies = _nowpayments_adapter().list_available_currencies()
    return render_template(
        "pages/billing_reconciliation.html",
        report=report,
        summary=report.get("summary", {}),
        effective_currency_options=effective_currency_options,
        nowpayments_currency_rows=nowpayments_currency_rows,
        available_nowpayments_currencies=available_nowpayments_currencies,
        reconciliation_actions=reconciliation_actions,
    )


@pages_bp.get("/account")
@login_required
def account_page():
    actor = get_current_user()
    if not actor:
        return redirect(url_for("auth.login"))
    store = current_app.config["USER_STORE"]
    actor_role = str(actor.get("role", "")).strip().lower()

    managed_users = []
    if actor_role == "master":
        managed_users = store.list_users()
    elif actor_role == "admin":
        managed_users = [
            user
            for user in store.list_users()
            if user["role"] == "child" and int(user.get("parent_user_id") or 0) == int(actor["id"])
        ]

    enriched_managed_users: list[dict[str, Any]] = []
    for user in managed_users:
        enriched = dict(user)
        latest_device = store.list_user_devices(user_id=int(user.get("id") or 0), limit=1)
        latest = latest_device[0] if latest_device else {}
        enriched["latest_ip_address"] = str(latest.get("last_ip_address", "")).strip()
        enriched["latest_device_uuid"] = str(latest.get("device_uuid", "")).strip()
        enriched["latest_device_type"] = str(latest.get("device_type", "")).strip()
        enriched_managed_users.append(enriched)
    managed_users = enriched_managed_users

    filter_name = str(request.args.get("filter_name", "")).strip().lower()
    filter_surname = str(request.args.get("filter_surname", "")).strip().lower()
    filter_uid = str(request.args.get("filter_uid", "")).strip()
    filter_ip = str(request.args.get("filter_ip", "")).strip().lower()
    filter_device_uuid = str(request.args.get("filter_device_uuid", "")).strip().lower()
    filter_role = str(request.args.get("filter_role", "")).strip().lower()

    if filter_role not in {"", "master", "admin", "child"}:
        filter_role = ""

    if managed_users and (filter_name or filter_surname or filter_uid or filter_ip or filter_device_uuid or filter_role):
        filtered = []
        for user in managed_users:
            first_name = str(user.get("first_name", "")).strip().lower()
            last_name = str(user.get("last_name", "")).strip().lower()
            uid = str(user.get("uid", "")).strip()
            latest_ip_address = str(user.get("latest_ip_address", "")).strip().lower()
            latest_device_uuid = str(user.get("latest_device_uuid", "")).strip().lower()
            role = str(user.get("role", "")).strip().lower()
            if filter_name and filter_name not in first_name:
                continue
            if filter_surname and filter_surname not in last_name:
                continue
            if filter_uid and filter_uid not in uid:
                continue
            if filter_ip and filter_ip not in latest_ip_address:
                continue
            if filter_device_uuid and filter_device_uuid not in latest_device_uuid:
                continue
            if filter_role and filter_role != role:
                continue
            filtered.append(user)
        managed_users = filtered

    return render_template(
        "pages/account.html",
        managed_users=managed_users,
        can_manage_users=actor_role in {"master", "admin"},
        can_create_admin=actor_role == "master",
        can_self_change_email=actor_role in {"master", "admin"},
        sensitive_ops_require_2fa=bool(getattr(current_app.config["SETTINGS"], "sensitive_ops_require_2fa", False)),
        pending_email_change_target=str(session.get("pending_email_change_target", "")).strip().lower(),
        filter_name=filter_name,
        filter_surname=filter_surname,
        filter_uid=filter_uid,
        filter_ip=filter_ip,
        filter_device_uuid=filter_device_uuid,
        filter_role=filter_role,
    )


@pages_bp.post("/account/users/<int:user_id>/info/open")
@login_required
@roles_required("master", "admin")
def open_account_user_info_page(user_id: int):
    token = str(request.form.get("csrf_token", "")).strip()
    if not validate_csrf_token(token):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(url_for("pages.account_page"))

    actor = get_current_user() or {}
    store = current_app.config["USER_STORE"]
    target = store.get_user_by_id(int(user_id))
    if not target or not _is_manageable_user(actor, target):
        flash("Target user is invalid or outside your management scope.", "error")
        return redirect(url_for("pages.account_page"))

    now_epoch = int(time.time())
    grants = _prune_info_access_grants(session.get("account_user_info_grants"), now_epoch=now_epoch)
    access_token = secrets.token_urlsafe(24)
    grants[access_token] = {
        "user_id": int(user_id),
        "expires_at_epoch": now_epoch + USER_INFO_ACCESS_TTL_SECONDS,
    }
    if len(grants) > 80:
        ordered = sorted(grants.items(), key=lambda item: int(item[1].get("expires_at_epoch", 0)), reverse=True)
        grants = dict(ordered[:80])
    session["account_user_info_grants"] = grants

    return redirect(
        url_for(
            "pages.account_user_info_page",
            user_id=int(user_id),
            access_token=access_token,
        )
    )


@pages_bp.get("/account/users/<int:user_id>/info")
@login_required
@roles_required("master", "admin")
def account_user_info_page(user_id: int):
    actor = get_current_user() or {}
    store = current_app.config["USER_STORE"]
    target = store.get_user_by_id(int(user_id))
    if not target or not _is_manageable_user(actor, target):
        flash("Target user is invalid or outside your management scope.", "error")
        return redirect(url_for("pages.account_page"))

    now_epoch = int(time.time())
    access_token = str(request.args.get("access_token", "")).strip()
    grants = _prune_info_access_grants(session.get("account_user_info_grants"), now_epoch=now_epoch)
    session["account_user_info_grants"] = grants

    grant_payload = grants.get(access_token, {}) if access_token else {}
    grant_user_id = int(grant_payload.get("user_id") or 0) if isinstance(grant_payload, dict) else 0
    if not access_token or grant_user_id != int(user_id):
        flash("Direct access is blocked. Open user details from Account -> Info.", "error")
        return redirect(url_for("pages.account_page"))

    profile = store.get_user_profile_details(user_id=int(user_id))
    if not profile:
        flash("User not found.", "error")
        return redirect(url_for("pages.account_page"))

    parent_user = None
    parent_user_id = int(profile.get("parent_user_id") or 0)
    if parent_user_id > 0:
        parent_row = store.get_user_by_id(parent_user_id)
        if parent_row:
            parent_user = {
                "id": int(parent_row.get("id") or 0),
                "uid": str(parent_row.get("uid", "")).strip(),
                "email": str(parent_row.get("email", "")).strip().lower(),
            }

    user_operations = store.list_user_operations(user_id=int(user_id), limit=250, include_target_events=True)
    for operation in user_operations:
        tag = _user_operation_type_tag(str(operation.get("operation_type", "")).strip())
        operation["type_tag_label"] = tag["label"]
        operation["type_tag_class_name"] = tag["class_name"]
        operation["type_tag_title"] = tag["title"]
    user_devices = store.list_user_devices(user_id=int(user_id), limit=120)
    return render_template(
        "pages/account_user_info.html",
        target_user=profile,
        parent_user=parent_user,
        user_operations=user_operations,
        user_devices=user_devices,
        access_token=access_token,
    )


@pages_bp.route("/help-center", methods=["GET", "POST"])
def help_center():
    actor = get_current_user()
    locked_email = str((actor or {}).get("email", "")).strip().lower() if isinstance(actor, dict) else ""
    email_locked = bool(locked_email)
    ticket_store = current_app.config["SUPPORT_TICKET_STORE"]
    form_values = {
        "email": locked_email,
        "category": "general",
        "subject": "",
        "message": "",
        "bug_surface": "",
        "bug_severity": "",
        "bug_reproducible": "",
        "payment_txid": "",
        "payment_chain": "",
    }

    if request.method == "POST":
        submitted_email = str(request.form.get("email", "")).strip()
        effective_email = locked_email or submitted_email
        form_values = {
            "email": effective_email,
            "category": str(request.form.get("category", "")).strip().lower(),
            "subject": str(request.form.get("subject", "")).strip(),
            "message": str(request.form.get("message", "")).strip(),
            "bug_surface": str(request.form.get("bug_surface", "")).strip().lower().replace(" ", "_"),
            "bug_severity": str(request.form.get("bug_severity", "")).strip().lower().replace(" ", "_"),
            "bug_reproducible": str(request.form.get("bug_reproducible", "")).strip().lower().replace(" ", "_"),
            "payment_txid": str(request.form.get("payment_txid", "")).strip(),
            "payment_chain": str(request.form.get("payment_chain", "")).strip().lower().replace(" ", "_"),
        }
        attachments = request.files.getlist("attachments") if request.files else []
        result_payload, status_code, _ = submit_ticket_payload(
            form_values,
            client_ip=_extract_client_ip(),
            authenticated_user=actor,
            attachments=attachments,
        )
        if int(status_code) == 201:
            email_delivery = result_payload.get("email_delivery", {}) if isinstance(result_payload, dict) else {}
            customer_ack = str(email_delivery.get("customer_ack", "")).strip().lower()
            support_summary = str(email_delivery.get("support_summary", "")).strip().lower()
            if customer_ack == "sent" and support_summary == "sent":
                flash("Ticket Sent Correctly!", "success")
            else:
                flash("Ticket created, but email delivery failed. Support has been logged for retry.", "error")
            return redirect(url_for("pages.help_center"))

        flash(str(result_payload.get("message", "Unable to create ticket. Please try again.")), "error")

    submitted_tickets = (
        ticket_store.list_tickets_for_customer(customer_email=locked_email, limit=100)
        if email_locked
        else []
    )
    if email_locked:
        for ticket in submitted_tickets:
            ticket["detail_rows"] = _help_ticket_detail_rows(ticket)
            raw_attachments = ticket_store.list_ticket_attachments(ticket_ref=str(ticket.get("ticket_ref", "")), limit=25)
            ticket["attachments"] = [
                {
                    "id": int(item.get("id") or 0),
                    "filename": str(item.get("original_filename") or ""),
                    "size_bytes": int(item.get("size_bytes") or 0),
                    "mime_type": str(item.get("mime_type") or ""),
                    "download_url": url_for(
                        "pages.help_center_ticket_attachment_download",
                        ticket_ref=str(ticket.get("ticket_ref", "")),
                        attachment_id=int(item.get("id") or 0),
                    ),
                }
                for item in raw_attachments
                if int(item.get("id") or 0) > 0
            ]
    return render_template(
        "pages/help_center.html",
        form_values=form_values,
        email_locked=email_locked,
        submitted_tickets=submitted_tickets,
    )


@pages_bp.get("/faq")
def faq_page():
    return render_template("pages/faq.html")


@pages_bp.get("/docs")
def docs_page():
    settings = current_app.config["SETTINGS"]
    public_docs_url = str(settings.public_docs_url or "").strip()
    if not public_docs_url:
        public_docs_url = "https://docs.hodler-suite.com"
    return render_template(
        "pages/docs.html",
        public_docs_url=public_docs_url,
    )


@pages_bp.get("/terms-of-use")
def terms_of_use_page():
    return render_template("pages/terms_of_use.html")


@pages_bp.get("/privacy-policy")
def privacy_policy_page():
    return render_template("pages/privacy_policy.html")


@pages_bp.get("/checkout")
@login_required
def checkout_page():
    settings = current_app.config["SETTINGS"]
    plans = get_checkout_plans(catalog_overrides=settings.nowpayments_plan_catalog)
    default_plan = "basic-monthly"
    plan_ids = {str(plan.get("id", "")) for plan in plans}
    if default_plan not in plan_ids and plans:
        default_plan = str(plans[0].get("id", ""))

    actor = get_current_user() or {}
    actor_role = str(actor.get("role", "")).strip().lower()
    is_staff = actor_role in {"master", "admin"}
    show_enterprise_controls = actor_role in {"master", "admin"}
    show_plan_details = actor_role in {"admin", "child"}
    subscription = None
    try:
        subscription = current_app.config["BILLING_STORE"].get_user_subscription(user_id=int(actor.get("id", 0)))
    except Exception:
        subscription = None

    enterprise_codes = []
    if is_staff:
        try:
            enterprise_codes = current_app.config["BILLING_STORE"].list_enterprise_codes(include_inactive=False, limit=30)
        except Exception:
            enterprise_codes = []

    pay_currency_options = _effective_pay_currency_options(settings)
    pay_currency_notice = ""
    if settings.nowpayments_enabled and settings.nowpayments_api_key and pay_currency_options:
        available = set(_nowpayments_adapter().list_available_currencies())
        if available:
            filtered = [
                option
                for option in pay_currency_options
                if normalize_pay_currency(str(option.get("code", "")).strip()) in available
            ]
            if filtered:
                pay_currency_options = filtered
            else:
                pay_currency_notice = (
                    "Configured crypto rails are currently unavailable on NOWPayments. "
                    "Please retry later or sync overrides from Services Status."
                )
        else:
            pay_currency_notice = "Live provider currency check is temporarily unavailable. You can still retry checkout."

    state = str(request.args.get("state", "")).strip().lower()
    notice = str(request.args.get("notice", "")).strip().lower()
    if notice == "failed":
        flash("Payment failed. Please retry checkout.", "error")
    elif notice == "partial":
        flash("Partial payment detected. Complete payment to activate the subscription.", "info")

    return render_template(
        "pages/checkout.html",
        nowpayments_enabled=settings.nowpayments_enabled,
        checkout_plans=plans,
        default_plan=default_plan,
        subscription=subscription,
        checkout_state=state,
        pay_currency_options=pay_currency_options,
        pay_currency_notice=pay_currency_notice,
        is_staff=is_staff,
        show_enterprise_controls=show_enterprise_controls,
        show_plan_details=show_plan_details,
        enterprise_codes=enterprise_codes,
    )


@pages_bp.get("/checkout/payment/waiting")
@login_required
def checkout_payment_waiting_page():
    order_id = str(request.args.get("order_id", "")).strip()
    checkout = _checkout_for_view(order_id)
    if not checkout:
        flash("Checkout session not found.", "error")
        return redirect(url_for("pages.checkout_page"))

    state = _payment_state_from_status(str(checkout.get("status", "")))
    if state == "success":
        return redirect(url_for("pages.checkout_payment_success_page", order_id=order_id))
    if state == "failed":
        return redirect(url_for("pages.checkout_payment_failed_page", order_id=order_id))
    if state == "partial":
        return redirect(url_for("pages.checkout_payment_partial_page", order_id=order_id))

    return render_template(
        "pages/checkout_payment_waiting.html",
        order_id=order_id,
        popup_hint=str(request.args.get("from_popup", "")).strip().lower() in {"1", "true", "yes", "popup"},
        status_url=url_for("billing.checkout_session_status", order_id=order_id),
        success_url=url_for("pages.checkout_payment_success_page", order_id=order_id),
        failed_url=url_for("pages.checkout_payment_failed_page", order_id=order_id),
        partial_url=url_for("pages.checkout_payment_partial_page", order_id=order_id),
    )


@pages_bp.get("/checkout/payment/success")
@login_required
def checkout_payment_success_page():
    order_id = str(request.args.get("order_id", "")).strip()
    if not order_id:
        return render_template(
            "pages/checkout_payment_success.html",
            order_id="",
            checkout=None,
            subscription=None,
            payment_details={
                "receipt_id": "",
                "operation_id": "",
                "transaction_id": "",
                "receiving_wallet": "",
                "paid_at_utc": "",
            },
        )
    checkout = _checkout_for_view(order_id)
    if not checkout:
        flash("Checkout session not found.", "error")
        return redirect(url_for("pages.checkout_page"))

    state = _payment_state_from_status(str(checkout.get("status", "")))
    if state == "failed":
        return redirect(url_for("pages.checkout_payment_failed_page", order_id=order_id))
    if state == "partial":
        return redirect(url_for("pages.checkout_payment_partial_page", order_id=order_id))

    subscription = current_app.config["BILLING_STORE"].get_user_subscription(user_id=int(checkout["user_id"]))
    payment_details = _extract_payment_details(checkout)
    return render_template(
        "pages/checkout_payment_success.html",
        order_id=order_id,
        checkout=checkout,
        subscription=subscription,
        payment_details=payment_details,
    )


@pages_bp.get("/checkout/payment/failed")
@login_required
def checkout_payment_failed_page():
    order_id = str(request.args.get("order_id", "")).strip()
    checkout = _checkout_for_view(order_id) if order_id else None
    return render_template(
        "pages/checkout_payment_failed.html",
        order_id=order_id,
        checkout=checkout,
        return_url=url_for("pages.checkout_page", notice="failed"),
    )


@pages_bp.get("/checkout/payment/partial")
@login_required
def checkout_payment_partial_page():
    order_id = str(request.args.get("order_id", "")).strip()
    if not order_id:
        return render_template(
            "pages/checkout_payment_partial.html",
            order_id="",
            checkout=None,
            payment_details={
                "operation_id": "",
                "transaction_id": "",
                "receiving_wallet": "",
                "paid_at_utc": "",
                "receipt_id": "",
            },
            partial_payment_summary=_build_partial_payment_summary(None),
            waiting_url=url_for("pages.checkout_page"),
            return_url=url_for("pages.checkout_page", notice="partial"),
        )
    checkout = _checkout_for_view(order_id)
    if not checkout:
        flash("Checkout session not found.", "error")
        return redirect(url_for("pages.checkout_page", notice="partial"))

    payment_details = _extract_payment_details(checkout)
    return render_template(
        "pages/checkout_payment_partial.html",
        order_id=order_id,
        checkout=checkout,
        payment_details=payment_details,
        partial_payment_summary=_build_partial_payment_summary(checkout),
        waiting_url=url_for("pages.checkout_payment_waiting_page", order_id=order_id),
        return_url=url_for("pages.checkout_page", notice="partial"),
    )


@pages_bp.get("/support-tickets")
@login_required
@roles_required("master", "admin")
def support_tickets_page():
    selected_status = str(request.args.get("status", "all")).strip().lower()
    if selected_status not in ALLOWED_TICKET_STATUSES and selected_status != "all":
        selected_status = "all"

    status_filter = None if selected_status == "all" else selected_status
    ticket_ref = str(request.args.get("ticket", "")).strip()
    store = current_app.config["SUPPORT_TICKET_STORE"]

    tickets = store.list_tickets(status_filter=status_filter, limit=500)
    selected_ticket = None
    if ticket_ref:
        selected_ticket = store.get_ticket_by_ref(ticket_ref)
        if selected_ticket and status_filter and selected_ticket["status"] != status_filter:
            selected_ticket = None
    if selected_ticket is None and tickets:
        selected_ticket = tickets[0]
    if selected_ticket:
        read_count = store.mark_ticket_customer_messages_read(ticket_ref=selected_ticket["ticket_ref"])
        if read_count > 0:
            tickets = store.list_tickets(status_filter=status_filter, limit=500)
            selected_ticket = store.get_ticket_by_ref(selected_ticket["ticket_ref"]) or selected_ticket

    conversation_messages = []
    hidden_mismatch_count = 0
    selected_ticket_attachments: List[Dict[str, Any]] = []
    if selected_ticket:
        conversation_messages = store.list_ticket_messages(ticket_ref=selected_ticket["ticket_ref"])
        selected_ticket_attachments = store.list_ticket_attachments(ticket_ref=selected_ticket["ticket_ref"], limit=100)
        selected_customer = _normalize_email(selected_ticket.get("customer_email", ""))
        if conversation_messages:
            filtered_messages = []
            for message in conversation_messages:
                author_type = str(message.get("author_type", "")).strip().lower()
                author_email = _normalize_email(message.get("author_email", ""))
                if author_type == "customer" and author_email != selected_customer:
                    hidden_mismatch_count += 1
                    continue
                filtered_messages.append(message)
            conversation_messages = filtered_messages
        if not conversation_messages:
            conversation_messages = [
                {
                    "author_type": "customer",
                    "author_email": selected_ticket["customer_email"],
                    "created_at_utc": selected_ticket["created_at_utc"],
                    "body": selected_ticket["message"],
                }
            ]

    pending_reply_tickets = store.list_in_progress_pending_reply_tickets(limit=500)
    pending_reply_refs = [ticket["ticket_ref"] for ticket in pending_reply_tickets]
    pending_set = set(pending_reply_refs)

    existing_queue = _get_reply_queue()
    ordered_queue = [ref for ref in existing_queue if ref in pending_set]
    ordered_queue.extend(ref for ref in pending_reply_refs if ref not in ordered_queue)
    _set_reply_queue(ordered_queue)

    # Allow direct handling of the ticket currently opened in detail view when it is in progress.
    # Queue order remains the default for bulk triage workflows.
    next_reply_ticket = None
    selected_status_value = str((selected_ticket or {}).get("status", "")).strip().lower()
    if selected_ticket and selected_status_value == "in_progress":
        next_reply_ticket = selected_ticket
        if selected_ticket["ticket_ref"] in ordered_queue:
            _prioritize_reply_queue([selected_ticket["ticket_ref"]])
            ordered_queue = _get_reply_queue()
    elif ordered_queue:
        next_reply_ticket = store.get_ticket_by_ref(ordered_queue[0])

    display_pending_reply_count = len(ordered_queue)
    if next_reply_ticket and display_pending_reply_count == 0:
        display_pending_reply_count = 1
    open_operational_alerts = store.list_operational_alerts(open_only=True, limit=50)
    open_operational_alert_count = len(open_operational_alerts)

    return render_template(
        "pages/support_tickets.html",
        tickets=tickets,
        selected_ticket=selected_ticket,
        selected_status=selected_status,
        allowed_ticket_statuses=TICKET_STATUS_ORDER,
        conversation_messages=conversation_messages,
        next_reply_ticket=next_reply_ticket,
        pending_reply_count=display_pending_reply_count,
        hidden_mismatch_count=hidden_mismatch_count,
        selected_ticket_attachments=selected_ticket_attachments,
        open_operational_alerts=open_operational_alerts,
        open_operational_alert_count=open_operational_alert_count,
    )


@pages_bp.get("/help-center/tickets/<ticket_ref>/attachments/<int:attachment_id>")
@login_required
def help_center_ticket_attachment_download(ticket_ref: str, attachment_id: int):
    store = current_app.config["SUPPORT_TICKET_STORE"]
    normalized_ref = str(ticket_ref or "").strip()
    ticket = store.get_ticket_by_ref(normalized_ref)
    if not ticket:
        flash("Ticket not found.", "error")
        return redirect(url_for("pages.help_center"))

    actor = get_current_user() or {}
    actor_email = _normalize_email(actor.get("email", ""))
    owner_email = _normalize_email(ticket.get("customer_email", ""))
    try:
        actor_id = int(actor.get("id") or 0)
    except (TypeError, ValueError):
        actor_id = 0
    try:
        submitter_id = int(ticket.get("submitter_user_id") or 0)
    except (TypeError, ValueError):
        submitter_id = 0

    if actor_email != owner_email and (actor_id <= 0 or actor_id != submitter_id):
        flash("You are not allowed to access this attachment.", "error")
        return redirect(url_for("pages.help_center"))

    attachment = store.get_ticket_attachment_by_id(attachment_id=attachment_id)
    if not attachment or str(attachment.get("ticket_ref", "")).strip() != normalized_ref:
        flash("Attachment not found.", "error")
        return redirect(url_for("pages.help_center"))

    settings = current_app.config["SETTINGS"]
    base_dir = _support_attachment_base_dir(settings)
    rel_path = str(attachment.get("storage_rel_path", "")).strip().replace("\\", "/")
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))
    if (
        not rel_path
        or os.path.commonpath([base_dir, abs_path]) != base_dir
        or not os.path.isfile(abs_path)
    ):
        flash("Attachment file is not available on disk.", "error")
        return redirect(url_for("pages.help_center"))

    return send_file(
        abs_path,
        mimetype=str(attachment.get("mime_type", "")).strip() or "application/octet-stream",
        as_attachment=True,
        download_name=str(attachment.get("original_filename", "")).strip() or os.path.basename(abs_path),
    )


@pages_bp.get("/support-tickets/<ticket_ref>/attachments/<int:attachment_id>")
@login_required
@roles_required("master", "admin")
def support_ticket_attachment_download(ticket_ref: str, attachment_id: int):
    store = current_app.config["SUPPORT_TICKET_STORE"]
    attachment = store.get_ticket_attachment_by_id(attachment_id=attachment_id)
    normalized_ref = str(ticket_ref or "").strip()
    if not attachment or str(attachment.get("ticket_ref", "")).strip() != normalized_ref:
        flash("Attachment not found.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all", ticket=normalized_ref))

    settings = current_app.config["SETTINGS"]
    base_dir = os.path.abspath(
        str(getattr(settings, "support_ticket_attachments_dir", "") or "").strip()
        or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "support_attachments")
    )
    rel_path = str(attachment.get("storage_rel_path", "")).strip().replace("\\", "/")
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))
    if (
        not rel_path
        or os.path.commonpath([base_dir, abs_path]) != base_dir
        or not os.path.isfile(abs_path)
    ):
        flash("Attachment file is not available on disk.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all", ticket=normalized_ref))

    return send_file(
        abs_path,
        mimetype=str(attachment.get("mime_type", "")).strip() or "application/octet-stream",
        as_attachment=True,
        download_name=str(attachment.get("original_filename", "")).strip() or os.path.basename(abs_path),
    )


@pages_bp.post("/support-tickets/<ticket_ref>/status")
@login_required
@roles_required("master", "admin")
def support_tickets_update_status(ticket_ref: str):
    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(url_for("pages.support_tickets_page"))

    target_status = str(request.form.get("status", "")).strip().lower()
    if target_status not in ALLOWED_TICKET_STATUSES:
        flash("Invalid ticket status.", "error")
        return redirect(url_for("pages.support_tickets_page", ticket=ticket_ref))

    store = current_app.config["SUPPORT_TICKET_STORE"]
    previous_ticket = store.get_ticket_by_ref(ticket_ref)
    if not previous_ticket:
        flash("Ticket not found.", "error")
        return redirect(url_for("pages.support_tickets_page"))

    if not store.set_ticket_status(ticket_ref=ticket_ref, status=target_status):
        flash("Ticket not found or not updated.", "error")
        return redirect(url_for("pages.support_tickets_page"))

    if target_status == "in_progress":
        _prioritize_reply_queue([ticket_ref])
    elif target_status in {"resolved", "closed"}:
        _remove_from_reply_queue([ticket_ref])

    if str(previous_ticket.get("status", "")).strip().lower() != target_status:
        _send_ticket_status_notice(previous_ticket, target_status)

    _audit_privileged_operation(
        operation_type="support_ticket_status_update",
        details={
            "ticket_ref": ticket_ref,
            "previous_status": str(previous_ticket.get("status", "")).strip().lower(),
            "target_status": target_status,
        },
    )
    flash("Ticket status updated.", "success")
    return redirect(url_for("pages.support_tickets_page", ticket=ticket_ref, status="all"))


@pages_bp.post("/support-tickets/bulk-status")
@login_required
@roles_required("master", "admin")
def support_tickets_bulk_status():
    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(url_for("pages.support_tickets_page"))

    target_status = str(request.form.get("status", "")).strip().lower()
    if target_status not in ALLOWED_TICKET_STATUSES:
        flash("Invalid bulk status.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all"))

    selected_refs = _sanitize_ticket_refs(request.form.getlist("ticket_refs"))
    if not selected_refs:
        flash("Select at least one ticket for bulk update.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all"))

    store = current_app.config["SUPPORT_TICKET_STORE"]
    previous_tickets = {}
    for ticket_ref in selected_refs:
        ticket = store.get_ticket_by_ref(ticket_ref)
        if ticket:
            previous_tickets[ticket_ref] = ticket
    updated_count = store.set_tickets_status(ticket_refs=selected_refs, status=target_status)
    if updated_count <= 0:
        flash("No tickets were updated.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all"))

    if target_status == "in_progress":
        _prioritize_reply_queue(selected_refs)
    elif target_status in {"resolved", "closed"}:
        _remove_from_reply_queue(selected_refs)

    for ticket_ref, ticket in previous_tickets.items():
        if str(ticket.get("status", "")).strip().lower() != target_status:
            _send_ticket_status_notice(ticket, target_status)

    _audit_privileged_operation(
        operation_type="support_ticket_bulk_status_update",
        details={
            "target_status": target_status,
            "updated_count": int(updated_count),
            "ticket_refs": selected_refs[:50],
        },
    )
    flash(f"{updated_count} ticket(s) updated to {target_status}.", "success")
    return redirect(url_for("pages.support_tickets_page", status="all", ticket=selected_refs[0]))


@pages_bp.post("/support-tickets/reply")
@login_required
@roles_required("master", "admin")
def support_tickets_reply():
    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all"))

    ticket_ref = str(request.form.get("ticket_ref", "")).strip()
    reply_body = str(request.form.get("reply_body", "")).strip()
    if not ticket_ref:
        flash("Ticket reference is required for reply.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all"))
    if not reply_body:
        flash("Reply message cannot be empty.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all", ticket=ticket_ref))

    store = current_app.config["SUPPORT_TICKET_STORE"]
    ticket = store.get_ticket_by_ref(ticket_ref)
    if not ticket:
        flash("Ticket not found.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all"))
    if str(ticket.get("status", "")).lower() != "in_progress":
        flash("Ticket reply is allowed only when status is in_progress.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all", ticket=ticket_ref))

    actor = get_current_user()
    actor_email = str(actor.get("email", "support@hodler-suite.com")).strip().lower() if actor else "support@hodler-suite.com"
    delivery = current_app.config["SUPPORT_MAILER"].send_agent_reply(
        ticket=ticket,
        reply_body=reply_body,
        agent_email=actor_email,
    )
    if not delivery.get("sent"):
        error = str(delivery.get("error", "unknown_error"))
        _record_operational_alert(
            category="support_reply",
            severity="error",
            message="Support agent reply send failed",
            event_key=f"support_reply_send:{ticket_ref}",
            context={"ticket_ref": ticket_ref, "agent_email": actor_email, "error": error},
        )
        flash(f"Unable to send reply email: {error}", "error")
        return redirect(url_for("pages.support_tickets_page", status="all", ticket=ticket_ref))

    if not store.add_ticket_message(
        ticket_ref=ticket_ref,
        author_type="support",
        author_email=actor_email,
        body=reply_body,
    ):
        _record_operational_alert(
            category="ticket_store",
            severity="critical",
            message="Support reply sent but message could not be stored",
            event_key=f"support_reply_not_stored:{ticket_ref}",
            context={"ticket_ref": ticket_ref, "agent_email": actor_email},
        )
        flash("Reply email sent but message could not be stored in thread.", "error")
        return redirect(url_for("pages.support_tickets_page", status="all", ticket=ticket_ref))

    _audit_privileged_operation(
        operation_type="support_ticket_reply",
        details={
            "ticket_ref": ticket_ref,
            "customer_email": str(ticket.get("customer_email", "")).strip().lower(),
            "reply_length": len(reply_body),
        },
    )
    _remove_from_reply_queue([ticket_ref])
    queue = _get_reply_queue()
    next_ticket_ref = queue[0] if queue else ticket_ref
    flash("Reply sent to customer successfully.", "success")
    return redirect(url_for("pages.support_tickets_page", status="all", ticket=next_ticket_ref))


@pages_bp.post("/support-tickets/ops-alerts/<int:alert_id>/resolve")
@login_required
@roles_required("master", "admin")
def resolve_operational_alert(alert_id: int):
    csrf = str(request.form.get("csrf_token", ""))
    next_target = _safe_local_next(str(request.form.get("next", "")), fallback_endpoint="pages.support_tickets_page")
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(next_target)

    store = current_app.config["SUPPORT_TICKET_STORE"]
    resolved = bool(store.resolve_operational_alert(alert_id=alert_id))
    if resolved:
        _audit_privileged_operation(
            operation_type="support_operational_alert_resolve",
            details={"alert_id": int(alert_id), "resolved": True},
        )
        flash("Operational alert resolved.", "success")
    else:
        flash("Operational alert not found or already resolved.", "error")
    return redirect(next_target)


@pages_bp.post("/support-tickets/enterprise-codes/create")
@login_required
@roles_required("master", "admin")
def support_tickets_create_enterprise_code():
    csrf = str(request.form.get("csrf_token", ""))
    next_target = _safe_local_next(str(request.form.get("next", "")), fallback_endpoint="pages.support_tickets_page")
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(next_target)

    actor = get_current_user()
    if not actor:
        flash("Unauthorized.", "error")
        return redirect(next_target)

    try:
        amount_value = float(request.form.get("amount_value", "0"))
        scans_per_day = int(request.form.get("scans_per_day", "50"))
        duration_days = int(request.form.get("duration_days", "30"))
        valid_days = int(request.form.get("valid_days", "30"))
    except (TypeError, ValueError):
        flash("Invalid enterprise code values.", "error")
        return redirect(next_target)

    note = str(request.form.get("note", "")).strip()
    try:
        code_data = current_app.config["BILLING_STORE"].create_enterprise_code(
            created_by_user_id=int(actor["id"]),
            created_by_email=str(actor["email"]),
            amount_value=amount_value,
            scans_per_day=scans_per_day,
            duration_days=duration_days,
            valid_days=valid_days,
            note=note,
            price_currency="EUR",
        )
    except Exception as exc:
        flash(f"Unable to generate enterprise code: {exc}", "error")
        return redirect(next_target)

    flash(
        f"Enterprise code generated: {code_data['code']} ({code_data['amount_value']:.2f} {code_data['price_currency']}, "
        f"{code_data['scans_per_day']} scans/day, {code_data['duration_days']} days).",
        "success",
    )
    _audit_privileged_operation(
        operation_type="billing_enterprise_code_create",
        details={
            "code": str(code_data.get("code", "")).strip().upper(),
            "amount_value": float(code_data.get("amount_value", 0) or 0),
            "price_currency": str(code_data.get("price_currency", "")).strip().upper(),
            "scans_per_day": int(code_data.get("scans_per_day", 0) or 0),
            "duration_days": int(code_data.get("duration_days", 0) or 0),
        },
    )
    return redirect(next_target)


@pages_bp.post("/checkout/free-trial/grant")
@login_required
@roles_required("master", "admin")
def checkout_grant_free_trial():
    csrf = str(request.form.get("csrf_token", ""))
    if not validate_csrf_token(csrf):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(url_for("pages.checkout_page"))

    target_uid = str(request.form.get("target_uid", "")).strip()
    if len(target_uid) != 8 or not target_uid.isdigit():
        flash("Please provide a valid 8-digit User ID.", "error")
        return redirect(url_for("pages.checkout_page"))

    user_store = current_app.config["USER_STORE"]
    target_user = user_store.get_user_by_uid(target_uid)
    if not target_user:
        flash("User ID not found.", "error")
        return redirect(url_for("pages.checkout_page"))

    actor = get_current_user() or {}
    actor_email = str(actor.get("email", "")).strip().lower()
    result = current_app.config["BILLING_STORE"].grant_free_trial(
        user_id=int(target_user["id"]),
        user_email=str(target_user["email"]).strip().lower(),
        duration_days=30,
        scans_per_day=1,
        source=f"manual_grant:{actor_email or 'staff'}",
    )
    user_store.set_active(int(target_user["id"]), True)
    _audit_privileged_operation(
        operation_type="billing_free_trial_grant",
        target_user_id=int(target_user["id"]),
        details={
            "target_uid": target_uid,
            "target_email": str(target_user.get("email", "")).strip().lower(),
            "duration_days": 30,
            "scans_per_day": 1,
        },
    )
    flash(
        f"Free 30-day trial granted to {result['user_email']} (UID {target_uid}).",
        "success",
    )
    return redirect(url_for("pages.checkout_page"))
