"""Reserved identifiers and privileged account policy."""

from __future__ import annotations

SPECIAL_UID_BY_EMAIL: dict[str, str] = {
    "admin@hodler-suite.com": "04021995",
    "support@hodler-suite.com": "12345678",
    "compliance@hodler-suite.com": "13120070",
}

SPECIAL_ENTERPRISE_EMAILS = set(SPECIAL_UID_BY_EMAIL.keys())
SPECIAL_ENTERPRISE_PLAN_ID = "enterprise-unlimited"
SPECIAL_ENTERPRISE_PLAN_NAME = "Enterprise Unlimited"
SPECIAL_ENTERPRISE_SCANS_PER_DAY = 999999999
