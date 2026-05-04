"""Load optional Ethereum test addresses from the environment (never hardcode contracts in repo).

Set before running manual API/cache scripts, for example:

  export TEST_ETHEREUM_ERC20_CONTRACT=0x...   # single ERC-20 for CoinGecko/Ethplorer/Etherscan snippets
  export TEST_ETHEREUM_ERC20_ADDRESSES=0x...,0x...   # comma-separated for cache loops
  export TEST_ETHEREUM_ERC20_PAIRS=0x...:UNI,0x...:LINK   # address:label for dashboard-style loops
  export TEST_ETHEREUM_WALLET=0x...   # optional wallet for Dune-style tests
  export TEST_ETHEREUM_ERC20_TOKEN=0x...   # optional token contract for Dune token calls
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

_ADDR = re.compile(r"^0x[a-fA-F0-9]{40}$")


def normalize_erc20(addr: str) -> Optional[str]:
    """Return lowercased 0x+40 hex if valid, else None."""
    s = (addr or "").strip()
    if not _ADDR.match(s):
        return None
    return s.lower()


def get_single_erc20_contract() -> Optional[str]:
    """Checksummed/lowercase ERC-20 from ``TEST_ETHEREUM_ERC20_CONTRACT``."""
    return normalize_erc20(os.getenv("TEST_ETHEREUM_ERC20_CONTRACT", ""))


def get_erc20_address_list() -> List[str]:
    """ERC-20 contracts from ``TEST_ETHEREUM_ERC20_ADDRESSES`` (comma-separated)."""
    raw = os.getenv("TEST_ETHEREUM_ERC20_ADDRESSES", "").strip()
    if not raw:
        return []
    out: List[str] = []
    for part in raw.split(","):
        n = normalize_erc20(part)
        if n:
            out.append(n)
    return out


def get_erc20_pairs() -> List[Tuple[str, str]]:
    """Pairs ``(address, label)`` from ``TEST_ETHEREUM_ERC20_PAIRS`` (``0x...:LABEL`` comma-separated)."""
    raw = os.getenv("TEST_ETHEREUM_ERC20_PAIRS", "").strip()
    if not raw:
        return []
    out: List[Tuple[str, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        addr, label = part.split(":", 1)
        n = normalize_erc20(addr)
        if n and label.strip():
            out.append((n, label.strip()))
    return out


def get_test_wallet() -> Optional[str]:
    """Optional EOA from ``TEST_ETHEREUM_WALLET``."""
    return normalize_erc20(os.getenv("TEST_ETHEREUM_WALLET", ""))


def get_test_erc20_token() -> Optional[str]:
    """Optional ERC-20 from ``TEST_ETHEREUM_ERC20_TOKEN``."""
    return normalize_erc20(os.getenv("TEST_ETHEREUM_ERC20_TOKEN", ""))
