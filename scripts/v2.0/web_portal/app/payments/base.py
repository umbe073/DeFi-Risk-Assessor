"""Base interfaces for payment providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class PaymentAdapter(ABC):
    @abstractmethod
    def create_checkout_invoice(
        self,
        *,
        order_id: str,
        price_amount: float,
        price_currency: str,
        pay_currency: str,
        callback_url: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """Create or prepare a checkout invoice payload."""

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Validate the provider signature for an inbound webhook."""
