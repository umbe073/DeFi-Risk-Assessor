"""Token address validation stub for local development."""

import re
from typing import Tuple


def normalize_and_validate_token_address(address: str, chain: str = "") -> Tuple[str, str]:
    """Normalize and validate a token address.

    Returns (normalized_address, error_message).
    error_message is empty string on success.
    """
    raw = str(address or "").strip()
    if not raw:
        return "", "Token address is required."

    if raw.startswith("0x") or raw.startswith("0X"):
        if len(raw) != 42:
            return "", "EVM address must be 42 characters (including 0x prefix)."
        if not re.match(r"^0x[0-9a-fA-F]{40}$", raw):
            return "", "Invalid EVM address format."
        return raw.lower(), ""

    if raw.startswith("T") and len(raw) == 34:
        return raw, ""

    return raw, ""
