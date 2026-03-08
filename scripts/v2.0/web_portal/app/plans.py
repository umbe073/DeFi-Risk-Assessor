"""Plan definitions and checkout helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


BASE_PLANS: List[Dict[str, Any]] = [
    {
        "id": "free-30d",
        "name": "Free",
        "button_label": "Free (30d)",
        "amount_value": 0.0,
        "price_currency": "EUR",
        "scans_per_day": 1,
        "duration_days": 30,
        "requires_payment": False,
        "requires_enterprise_code": False,
        "tagline": "Kickstart risk discovery",
        "fee_note": "No payment. 30-day trial, then account access becomes inactive.",
        "description": "1 scannable token/day for 30 days (30 total), then inactive until an upgraded plan is activated.",
        "features": [
            "No Settings access",
            "No secondary/alternative API services",
            "Only market + main behavioural category scores",
            "No red flags",
            "No EU mode",
        ],
    },
    {
        "id": "basic-monthly",
        "name": "Basic",
        "button_label": "Basic",
        "amount_value": 49.99,
        "price_currency": "EUR",
        "scans_per_day": 5,
        "duration_days": 30,
        "requires_payment": True,
        "requires_enterprise_code": False,
        "tagline": "Reliable monthly coverage",
        "fee_note": "49.99 EUR / month (plus network fee).",
        "description": "5 scannable tokens/day for 1 month (up to 150 scans/month).",
        "features": [
            "Full API services except social score",
            "EU mode + basic settings",
            "No chain/fallback/cache/refresh deep controls",
            "Full market + behavioural category scores",
            "Red flags enabled",
        ],
    },
    {
        "id": "pro-monthly",
        "name": "Pro",
        "button_label": "Pro",
        "amount_value": 299.99,
        "price_currency": "EUR",
        "scans_per_day": 20,
        "duration_days": 30,
        "requires_payment": True,
        "requires_enterprise_code": False,
        "tagline": "Full analytical control",
        "fee_note": "299.99 EUR / month (plus network fee).",
        "description": "20 scannable tokens/day for 1 month (up to 600 scans/month).",
        "features": [
            "Full API services with no limitation",
            "Full settings/chains/refresh-rate controls",
            "Full market + behavioural category scores",
            "Red flags enabled",
        ],
    },
    {
        "id": "enterprise-custom",
        "name": "Enterprise",
        "button_label": "Enterprise",
        "amount_value": 0.0,
        "price_currency": "EUR",
        "scans_per_day": 0,
        "duration_days": 30,
        "requires_payment": True,
        "requires_enterprise_code": True,
        "tagline": "Custom high-touch engagement",
        "fee_note": "Amount and limits are defined by enterprise code.",
        "description": "Custom daily scans and price, agreed directly with support.",
        "features": [
            "All Pro features",
            "Dedicated VIP customer service",
            "Custom daily token limits",
            "Custom pricing by enterprise code",
        ],
    },
]


def get_checkout_plans(*, catalog_overrides: Dict[str, float] | None = None) -> List[Dict[str, Any]]:
    plans = deepcopy(BASE_PLANS)
    overrides = catalog_overrides or {}
    for plan in plans:
        plan_id = str(plan.get("id", ""))
        if plan_id in overrides and float(overrides[plan_id]) > 0:
            plan["amount_value"] = round(float(overrides[plan_id]), 2)
    return plans


def get_plan_index(*, catalog_overrides: Dict[str, float] | None = None) -> Dict[str, Dict[str, Any]]:
    plans = get_checkout_plans(catalog_overrides=catalog_overrides)
    return {str(plan["id"]): plan for plan in plans}
