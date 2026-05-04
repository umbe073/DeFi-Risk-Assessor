"""Chain code constants stub for local development."""

from typing import Set

CANONICAL_TOKEN_CHAIN_CODES: Set[str] = {"eth", "bsc", "tron", "polygon", "arbitrum", "base", "solana"}


def is_allowed_token_chain_hint(chain: str) -> bool:
    """Return True if chain hint is valid."""
    if not chain:
        return True
    return chain.strip().lower() in CANONICAL_TOKEN_CHAIN_CODES


def normalize_token_chain_hint(chain: str) -> str:
    """Normalize a token chain hint to canonical form."""
    raw = str(chain or "").strip().lower()
    if not raw:
        return ""
    if raw in CANONICAL_TOKEN_CHAIN_CODES:
        return raw
    return ""
