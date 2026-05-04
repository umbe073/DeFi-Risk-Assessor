"""Entitlements stub for local development."""

from typing import Any, Dict

RISK_BATCH_ABS_MAX = 100


def build_risk_access(user: Dict[str, Any] | None) -> Dict[str, Any]:
    """Build risk access dict for the given user."""
    if not user:
        return {"is_admin_like": False, "live_assessment_list_mode": False}
    role = str(user.get("role", "")).lower()
    return {
        "is_admin_like": role in {"master", "admin"},
        "live_assessment_list_mode": role in {"master", "admin", "enterprise"},
    }


def effective_risk_batch_run_cap(risk_access: Dict[str, Any]) -> int:
    """Return effective batch run cap."""
    if risk_access.get("is_admin_like"):
        return RISK_BATCH_ABS_MAX
    return 10


def evaluate_feature_entitlement(user: Dict[str, Any] | None, feature: str) -> bool:
    """Evaluate if user has entitlement for a feature."""
    if not user:
        return False
    role = str(user.get("role", "")).lower()
    return role in {"master", "admin", "enterprise"}
