"""Billing and NOWPayments callback routes."""

from datetime import datetime, timezone
from copy import deepcopy
import uuid

from flask import Blueprint, current_app, jsonify, request

from ..auth import api_login_required, api_roles_required, get_current_user, validate_csrf_token
from ..billing_store import FINAL_PAYMENT_STATUSES
from ..payments.nowpayments import NowPaymentsAdapter, normalize_pay_currency
from ..plans import get_plan_index


billing_bp = Blueprint("billing", __name__, url_prefix="/api/v1/billing")
FAILED_PAYMENT_STATUSES = {"failed", "expired", "refunded", "cancelled", "canceled"}
PARTIAL_PAYMENT_STATUSES = {"partially_paid", "partially-paid", "partially paid"}


def _payment_state_from_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in FINAL_PAYMENT_STATUSES:
        return "success"
    if normalized in FAILED_PAYMENT_STATUSES:
        return "failed"
    if normalized in PARTIAL_PAYMENT_STATUSES:
        return "partial"
    return "waiting"


def _adapter() -> NowPaymentsAdapter:
    settings = current_app.config["SETTINGS"]
    return NowPaymentsAdapter(
        api_key=settings.nowpayments_api_key,
        ipn_secret=settings.nowpayments_ipn_secret,
        api_base=settings.nowpayments_api_base,
    )


def _record_operational_alert(*, category: str, severity: str, message: str, event_key: str = "", context: dict | None = None) -> None:
    try:
        store = current_app.config.get("SUPPORT_TICKET_STORE")
        if store is None:
            return
        store.create_operational_alert(
            category=category,
            severity=severity,
            message=message,
            event_key=event_key,
            context=context or {},
        )
    except Exception:
        current_app.logger.exception("billing_operational_alert_store_failed category=%s event_key=%s", category, event_key)


def _billing_store():
    return current_app.config["BILLING_STORE"]


def _get_checkout_plan(plan_id: str):
    settings = current_app.config["SETTINGS"]
    plan_index = get_plan_index(catalog_overrides=settings.nowpayments_plan_catalog)
    plan = plan_index.get(str(plan_id or "").strip())
    return deepcopy(plan) if plan else None


@billing_bp.post("/checkout-session")
@api_login_required
def create_checkout_session():
    settings = current_app.config["SETTINGS"]
    adapter = _adapter()

    payload = request.get_json(silent=True) or {}
    csrf_token = str(request.headers.get("X-CSRF-Token", "")).strip() or str(payload.get("csrf_token", "")).strip()
    if not validate_csrf_token(csrf_token):
        return jsonify({"error": "invalid_csrf"}), 403

    actor = get_current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401

    plan_id = str(payload.get("plan_id", "")).strip()
    default_pay_currency_options = [
        {"code": str(item.get("code", "")).strip().lower(), "label": str(item.get("label", "")).strip()}
        for item in (settings.nowpayments_pay_currencies or [])
        if str(item.get("code", "")).strip()
    ]
    effective_pay_currency_options = _billing_store().get_effective_pay_currency_options(
        default_options=default_pay_currency_options
    )
    configured_pay_currencies = [
        normalize_pay_currency(str(item.get("code", "")).strip().lower())
        for item in effective_pay_currency_options
        if str(item.get("code", "")).strip()
    ]
    configured_pay_currencies = [code for code in configured_pay_currencies if code]
    if not configured_pay_currencies:
        configured_pay_currencies = ["usdttrc20"]
    requested_pay_currency = normalize_pay_currency(str(payload.get("pay_currency", "")).strip().lower())

    if not plan_id:
        return jsonify({"error": "invalid_payload", "message": "plan_id is required"}), 400
    plan = _get_checkout_plan(plan_id)
    if not plan:
        return jsonify({"error": "invalid_plan", "message": "Unknown plan_id"}), 400

    order_id = f"plan-{plan_id}-{uuid.uuid4().hex[:10]}"
    store = _billing_store()

    if bool(plan.get("requires_enterprise_code")):
        enterprise_code = str(payload.get("enterprise_code", "")).strip().upper()
        if not enterprise_code:
            return jsonify({"error": "enterprise_code_required"}), 400
        reserved = store.reserve_enterprise_code(
            code=enterprise_code,
            user_id=int(actor["id"]),
            user_email=str(actor["email"]),
            order_id=order_id,
        )
        if not reserved:
            return jsonify({"error": "invalid_or_unavailable_enterprise_code"}), 400
        plan["amount_value"] = float(reserved["amount_value"])
        plan["price_currency"] = str(reserved["price_currency"])
        plan["scans_per_day"] = int(reserved["scans_per_day"])
        plan["duration_days"] = int(reserved["duration_days"])
        plan["enterprise_code"] = enterprise_code

    if not bool(plan.get("requires_payment")):
        target_uid = str(payload.get("target_user_uid", "")).strip()
        actor_role = str(actor.get("role", "")).strip().lower()
        if target_uid and actor_role in {"master", "admin"}:
            user_store = current_app.config["USER_STORE"]
            target_user = user_store.get_user_by_uid(target_uid)
            if not target_user:
                return jsonify({"error": "invalid_target_user_uid"}), 400
            activated = store.grant_free_trial(
                user_id=int(target_user["id"]),
                user_email=str(target_user["email"]),
                duration_days=int(plan["duration_days"]),
                scans_per_day=int(plan["scans_per_day"]),
                source=f"manual_grant:{str(actor['email']).strip().lower()}",
            )
            user_store.set_active(int(target_user["id"]), True)
        else:
            activated = store.activate_free_trial(
                user_id=int(actor["id"]),
                user_email=str(actor["email"]),
                plan_id=str(plan["id"]),
                plan_name=str(plan["name"]),
                scans_per_day=int(plan["scans_per_day"]),
                duration_days=int(plan["duration_days"]),
            )
            if not activated:
                return jsonify({"error": "free_trial_unavailable", "message": "Free trial already used for this account."}), 409
        return jsonify({
            "status": "trial_activated",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "subscription": activated,
        }), 201

    if not settings.nowpayments_enabled:
        return jsonify({
            "error": "billing_disabled",
            "message": "NOWPayments is disabled for paid checkout sessions.",
        }), 503

    available_currencies = set(adapter.list_available_currencies())
    if available_currencies:
        supported_pay_currencies = [code for code in configured_pay_currencies if code in available_currencies]
        if not supported_pay_currencies:
            _record_operational_alert(
                category="billing_nowpayments",
                severity="warning",
                message="Configured checkout currencies are unavailable on NOWPayments",
                event_key="billing_currency_unavailable",
                context={
                    "configured": configured_pay_currencies,
                    "available": sorted(available_currencies)[:50],
                },
            )
            return jsonify(
                {
                    "error": "provider_currency_unavailable",
                    "message": "Configured checkout currencies are currently unavailable. Please retry later.",
                }
            ), 503
    else:
        supported_pay_currencies = list(configured_pay_currencies)

    if requested_pay_currency and requested_pay_currency in supported_pay_currencies:
        pay_currency = requested_pay_currency
    elif supported_pay_currencies:
        pay_currency = supported_pay_currencies[0]
    else:
        pay_currency = requested_pay_currency

    callback_url = request.url_root.rstrip("/") + "/api/v1/billing/webhook"
    root_url = request.url_root.rstrip("/")
    waiting_url = f"{root_url}/checkout/payment/waiting?order_id={order_id}"
    success_url = settings.nowpayments_success_url or f"{root_url}/checkout/payment/success?order_id={order_id}"
    cancel_url = settings.nowpayments_cancel_url or f"{root_url}/checkout/payment/failed?order_id={order_id}"
    partial_url = settings.nowpayments_partial_url or f"{root_url}/checkout/payment/partial?order_id={order_id}"

    checkout = None
    provider_error = ""
    candidate_currencies = []
    seen_candidates = set()
    for candidate in [pay_currency] + supported_pay_currencies:
        normalized = normalize_pay_currency(candidate)
        if normalized in seen_candidates:
            continue
        seen_candidates.add(normalized)
        candidate_currencies.append(normalized)

    provider_errors = []
    for candidate_currency in candidate_currencies:
        try:
            checkout = adapter.create_checkout_invoice(
                order_id=order_id,
                price_amount=float(plan["amount_value"]),
                price_currency=str(plan["price_currency"]),
                pay_currency=candidate_currency,
                callback_url=callback_url,
                success_url=success_url,
                cancel_url=cancel_url,
                partial_url=partial_url,
            )
            pay_currency = normalize_pay_currency(str(checkout.get("pay_currency") or candidate_currency))
            provider_error = ""
            break
        except Exception as exc:
            provider_error = str(exc)
            provider_errors.append(
                f"currency={candidate_currency or 'auto'} -> {provider_error}"
            )

    if provider_error and provider_errors:
        provider_error = " | ".join(provider_errors[:4])

    if not isinstance(checkout, dict):
        enterprise_code = str(plan.get("enterprise_code", "")).strip().upper()
        if enterprise_code:
            store.release_enterprise_code_reservation(
                code=enterprise_code,
                order_id=order_id,
                user_id=int(actor["id"]),
            )
        _record_operational_alert(
            category="billing_nowpayments",
            severity="error",
            message="NOWPayments checkout session creation failed",
            event_key=f"billing_checkout_failed:{plan_id}",
            context={
                "plan_id": plan_id,
                "pay_currency": pay_currency,
                "amount_value": float(plan["amount_value"]),
                "price_currency": str(plan["price_currency"]),
                "error": provider_error or "unknown_error",
            },
        )
        return jsonify({"error": "provider_error", "message": provider_error or "checkout_creation_failed"}), 502
    pay_currency = normalize_pay_currency(str(checkout.get("pay_currency") or pay_currency))

    session_row = store.create_checkout_session(
        user_id=int(actor["id"]),
        user_email=str(actor["email"]),
        plan_id=str(plan["id"]),
        plan_name=str(plan["name"]),
        scans_per_day=int(plan["scans_per_day"]),
        duration_days=int(plan["duration_days"]),
        amount_value=float(plan["amount_value"]),
        price_currency=str(plan["price_currency"]),
        pay_currency=pay_currency,
        order_id=order_id,
        checkout=checkout,
        enterprise_code=str(plan.get("enterprise_code", "")),
    )

    return jsonify({
        "status": "created",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkout": checkout,
        "session": session_row,
        "urls": {
            "waiting": waiting_url,
            "success": success_url,
            "failed": cancel_url,
            "partial": partial_url,
        },
    }), 201


@billing_bp.post("/enterprise-codes")
@api_roles_required("master", "admin")
def create_enterprise_code():
    payload = request.get_json(silent=True) or {}
    csrf_token = str(request.headers.get("X-CSRF-Token", "")).strip() or str(payload.get("csrf_token", "")).strip()
    if not validate_csrf_token(csrf_token):
        return jsonify({"error": "invalid_csrf"}), 403

    actor = get_current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401

    try:
        amount_value = float(payload.get("amount_value", 0))
        scans_per_day = int(payload.get("scans_per_day", 50))
        duration_days = int(payload.get("duration_days", 30))
        valid_days = int(payload.get("valid_days", 30))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_payload", "message": "amount/scans/duration/valid values are invalid"}), 400

    note = str(payload.get("note", "")).strip()
    try:
        code_data = _billing_store().create_enterprise_code(
            created_by_user_id=int(actor["id"]),
            created_by_email=str(actor["email"]),
            amount_value=amount_value,
            scans_per_day=scans_per_day,
            duration_days=duration_days,
            valid_days=valid_days,
            note=note,
            price_currency="EUR",
        )
    except Exception:
        current_app.logger.exception("enterprise_code_create_failed")
        return jsonify({"error": "create_code_failed", "message": "unable_to_create_code"}), 400

    return jsonify({"status": "created", "enterprise_code": code_data}), 201


@billing_bp.post("/webhook")
def nowpayments_webhook():
    signature = request.headers.get("x-nowpayments-sig", "")
    raw_payload = request.get_data(cache=False)

    if not signature:
        return jsonify({"error": "missing_signature"}), 400

    adapter = _adapter()
    if not adapter.verify_webhook_signature(raw_payload, signature):
        return jsonify({"error": "invalid_signature"}), 401

    event = request.get_json(silent=True) or {}
    event_id = str(event.get("payment_id") or event.get("id") or "").strip()
    if not event_id:
        return jsonify({"error": "missing_event_id"}), 400

    store = _billing_store()
    if store.has_webhook_event(provider="nowpayments", event_id=event_id):
        return jsonify({"status": "duplicate_ignored", "event_id": event_id}), 200

    store.record_webhook_event(
        provider="nowpayments",
        event_id=event_id,
        payload=event,
        signature=signature,
    )
    result = store.apply_nowpayments_webhook(payload=event)
    if not bool(result.get("matched_order")):
        _record_operational_alert(
            category="billing_webhook",
            severity="warning",
            message="NOWPayments webhook received for unknown order_id",
            event_key=f"billing_webhook_unknown_order:{event_id}",
            context={
                "event_id": event_id,
                "order_id": str(event.get("order_id", "")).strip(),
                "payment_status": str(event.get("payment_status", "")).strip(),
            },
        )
        return jsonify({"status": "accepted_unmatched_order", "event_id": event_id}), 202

    return jsonify({"status": "accepted", "event_id": event_id, "result": result}), 200


@billing_bp.get("/checkout-session/<order_id>/status")
@api_login_required
def checkout_session_status(order_id: str):
    actor = get_current_user()
    if not actor:
        return jsonify({"error": "unauthorized"}), 401

    store = _billing_store()
    checkout = store.get_checkout_by_order_id(order_id=str(order_id or "").strip())
    if not checkout:
        return jsonify({"error": "not_found"}), 404

    actor_role = str(actor.get("role", "")).strip().lower()
    if actor_role not in {"master", "admin"} and int(checkout.get("user_id") or 0) != int(actor.get("id") or 0):
        return jsonify({"error": "forbidden"}), 403

    status = str(checkout.get("status", "")).strip().lower()
    state = _payment_state_from_status(status)
    subscription = store.get_user_subscription(user_id=int(checkout["user_id"]))
    if subscription and str(subscription.get("status", "")).strip().lower() == "active":
        if str(subscription.get("order_id", "")).strip() == str(checkout.get("order_id", "")).strip():
            state = "success"

    return jsonify(
        {
            "order_id": str(checkout.get("order_id", "")).strip(),
            "state": state,
            "status": status,
            "session": checkout,
            "subscription": subscription,
        }
    ), 200
