"""Chain catalog stub for local development."""

from typing import List, Dict, Any


def live_assessment_chain_options() -> List[Dict[str, Any]]:
    """Return supported chain options for live assessment."""
    return [
        {"code": "eth", "label": "Ethereum", "enabled": True},
        {"code": "bsc", "label": "BNB Chain", "enabled": True},
        {"code": "tron", "label": "TRON", "enabled": True},
    ]
