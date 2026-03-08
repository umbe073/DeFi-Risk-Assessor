"""NOWPayments adapter with live invoice creation and webhook signature verification."""

import hashlib
import hmac
import json
from typing import Any, Dict, Iterable
from urllib import error as urlerror
from urllib import request as urlrequest

from .base import PaymentAdapter


PAY_CURRENCY_ALIASES = {
    "usdcerc20": "usdc",
}


def normalize_pay_currency(code: str) -> str:
    normalized = str(code or "").strip().lower()
    if not normalized:
        return ""
    return PAY_CURRENCY_ALIASES.get(normalized, normalized)


class NowPaymentsAdapter(PaymentAdapter):
    def __init__(self, api_key: str, ipn_secret: str, api_base: str) -> None:
        self.api_key = api_key
        self.ipn_secret = ipn_secret
        self.api_base = api_base.rstrip("/")

    def create_checkout_invoice(
        self,
        *,
        order_id: str,
        price_amount: float,
        price_currency: str,
        pay_currency: str = "",
        callback_url: str,
        success_url: str,
        cancel_url: str,
        partial_url: str = "",
    ) -> Dict[str, Any]:
        """Create a live NOWPayments invoice."""
        if not self.api_key:
            raise ValueError("NOWPAYMENTS_API_KEY is missing")
        if not callback_url:
            raise ValueError("callback_url is required")
        if not order_id:
            raise ValueError("order_id is required")
        if float(price_amount) <= 0:
            raise ValueError("price_amount must be positive")

        payload = {
            "order_id": str(order_id).strip(),
            "price_amount": round(float(price_amount), 2),
            "price_currency": str(price_currency).strip().upper(),
            "ipn_callback_url": str(callback_url).strip(),
            "is_fixed_rate": True,
        }
        normalized_pay_currency = normalize_pay_currency(pay_currency)
        if normalized_pay_currency:
            payload["pay_currency"] = normalized_pay_currency
        if success_url:
            payload["success_url"] = str(success_url).strip()
        if cancel_url:
            payload["cancel_url"] = str(cancel_url).strip()
        if partial_url:
            payload["partially_paid_url"] = str(partial_url).strip()

        response = self._request_json("POST", "/invoice", payload)
        if not isinstance(response, dict):
            raise ValueError("nowpayments_invalid_response_shape")
        invoice_id = str(response.get("id") or response.get("invoice_id") or "").strip()
        if not invoice_id:
            raise ValueError("nowpayments_invoice_missing_id")

        return {
            "provider": "nowpayments",
            "mode": "live",
            "invoice_id": invoice_id,
            "payment_id": str(response.get("payment_id") or "").strip(),
            "order_id": str(response.get("order_id") or order_id).strip(),
            "invoice_url": str(response.get("invoice_url") or response.get("invoice_link") or "").strip(),
            "status": str(response.get("invoice_status") or response.get("payment_status") or "waiting").strip().lower(),
            "price_amount": float(response.get("price_amount") or payload["price_amount"]),
            "price_currency": str(response.get("price_currency") or payload["price_currency"]).strip().upper(),
            "pay_currency": normalize_pay_currency(str(response.get("pay_currency") or payload.get("pay_currency") or "")),
            "raw": response,
        }

    def list_available_currencies(self) -> list[str]:
        """Return currently available pay currencies for this NOWPayments account."""
        if not self.api_key:
            return []
        try:
            response = self._request_json("GET", "/currencies")
        except Exception:
            return []

        raw_values: Iterable[Any]
        if isinstance(response, dict):
            payload = response.get("currencies")
            if not isinstance(payload, list):
                payload = response.get("data")
            raw_values = payload if isinstance(payload, list) else []
        elif isinstance(response, list):
            raw_values = response
        else:
            raw_values = []

        values: list[str] = []
        seen = set()
        for item in raw_values:
            token = normalize_pay_currency(str(item or ""))
            if not token or token in seen:
                continue
            seen.add(token)
            values.append(token)
        return values

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Validate x-nowpayments-sig (HMAC-SHA512 over sorted JSON body)."""
        if not self.ipn_secret or not signature:
            return False

        try:
            event = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False

        canonical = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = hmac.new(
            self.ipn_secret.encode("utf-8"),
            canonical,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected.lower(), signature.strip().lower())

    def _request_json(self, method: str, path: str, payload: Dict[str, Any] | None = None) -> Any:
        endpoint = f"{self.api_base.rstrip('/')}/{path.lstrip('/')}"
        normalized_method = str(method).strip().upper()
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        req = urlrequest.Request(
            endpoint,
            data=body,
            method=normalized_method,
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "HodlerSuiteCheckout/1.0",
            },
        )
        raw = ""
        try:
            with urlrequest.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8", "replace")
        except urlerror.HTTPError as exc:
            try:
                raw = exc.read().decode("utf-8", "replace")
            except Exception:
                raw = ""
            details = f"nowpayments_http_{exc.code}"
            if raw:
                details = f"{details}:{raw[:280]}"
            raise ValueError(details) from exc
        except Exception as exc:
            raise ValueError(f"nowpayments_request_error:{exc}") from exc

        try:
            decoded = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ValueError("nowpayments_invalid_json_response") from exc

        return decoded
