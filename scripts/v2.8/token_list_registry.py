#!/usr/bin/env python3
"""Token contract identities derived only from ``data/tokens.csv`` (via ``TokenManager``).

Do not hardcode production token addresses in other modules; import helpers from here.
EVM addresses are compared lowercased; other chains keep opaque strings from the CSV.

``SOLANA_WRAPPED_SOL_MINT`` is the canonical public wrapped-SOL mint (not a user contract row).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, FrozenSet, Optional, Set

import pandas as pd

from centralized_token_manager import TokenManager, normalize_token_storage_address

# Canonical SPL native wrapped SOL mint (fixed program-derived identifier).
SOLANA_WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"

_REGISTRY_CHAIN_ALIASES: Dict[str, str] = {
    "eth": "eth",
    "ethereum": "eth",
    "mainnet": "eth",
    "erc20": "eth",
    "polygon": "polygon",
    "matic": "polygon",
    "pol": "polygon",
    "op": "op",
    "optimism": "op",
    "base": "base",
    "base-l2": "base",
    "mantle": "mantle",
    "mnt": "mantle",
    "arbitrum": "arbitrum",
    "arb": "arbitrum",
    "sonic": "sonic",
    "avax": "avax",
    "avalanche": "avax",
    "avalanche-c": "avax",
    "avaxc": "avax",
    "fantom": "fantom",
    "ftm": "fantom",
    "fantom opera": "fantom",
    "bsc": "bsc",
    "binance": "bsc",
    "bnb": "bsc",
    "binance smart chain": "bsc",
    "binance-smart-chain": "bsc",
    "linea": "linea",
    "linea-mainnet": "linea",
    "zksync": "zksync",
    "zk sync": "zksync",
    "zk-sync": "zksync",
    "zksync-era": "zksync",
    "zksync era": "zksync",
    "era": "zksync",
    "zk": "zksync",
    "sei": "sei",
    "sei-evm": "sei",
    "thorchain": "thorchain",
    "thor": "thorchain",
    "runechain": "thorchain",
    "sol": "solana",
    "solana": "solana",
    "spl": "solana",
    "tron": "tron",
    "trx": "tron",
    "trc20": "tron",
    "trc-20": "tron",
}


def normalize_registry_chain(chain: Any) -> str:
    """Map CSV / UI chain labels to canonical keys (aligned with ``normalize_chain_name`` in defi_complete)."""
    value = str(chain or "eth").strip().lower()
    return _REGISTRY_CHAIN_ALIASES.get(value, value)


_STABLECOIN_SYMBOLS: FrozenSet[str] = frozenset(
    {
        "USDT",
        "USDC",
        "DAI",
        "BUSD",
        "FRAX",
        "LUSD",
        "PAX",
        "PAXG",
        "TUSD",
        "GUSD",
        "HUSD",
        "SUSD",
        "USDP",
        "USDE",
        "USDD",
        "USDB",
        "FDUSD",
        "USDY",
        "USD0",
        "USDT0",
        "FRXUSD",
        "SCUSD",
        "EURC",
        "EUROC",
        "EURS",
        "EURE",
        "RLUSD",
    }
)

_WRAPPED_SYMBOLS: FrozenSet[str] = frozenset(
    {
        "WETH",
        "WBTC",
        "WBNB",
        "WMATIC",
        "WPOL",
        "WAVAX",
        "WSOL",
        "WFTM",
        "WTRX",
        "WGLMR",
        "WONE",
        "WMNT",
        "WSEI",
        "WROSE",
        "WKAVA",
        "WCELO",
        "WXDAI",
        "WRUNE",
        "WSTETH",
    }
)

_NATIVE_SYMBOLS_BY_CHAIN: Dict[str, FrozenSet[str]] = {
    "eth": frozenset({"ETH", "WETH"}),
    "bsc": frozenset({"BNB", "WBNB"}),
    "polygon": frozenset({"POL", "MATIC", "WMATIC", "WPOL"}),
    "op": frozenset({"OP", "ETH", "WETH"}),
    "arbitrum": frozenset({"ARB", "ETH", "WETH"}),
    "base": frozenset({"ETH", "WETH"}),
    "avax": frozenset({"AVAX", "WAVAX"}),
    "linea": frozenset({"ETH", "WETH"}),
    "mantle": frozenset({"MNT", "WMNT"}),
    "sei": frozenset({"SEI", "WSEI"}),
    "sonic": frozenset({"S", "WS"}),
    "solana": frozenset({"SOL", "WSOL"}),
    "zksync": frozenset({"ZK", "ETH", "WETH"}),
    "thorchain": frozenset({"RUNE", "THOR", "WRUNE"}),
}


@lru_cache(maxsize=1)
def _manager() -> TokenManager:
    return TokenManager()


def _row_chain_key(row: Any) -> str:
    return normalize_registry_chain(row.get("chain", ""))


def _row_symbol_upper(row: Any) -> str:
    return str(row.get("symbol") or "").strip().upper()


def _row_address_str(row: Any) -> str:
    raw = row.get("address")
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    return str(raw).strip()


@lru_cache(maxsize=1)
def stablecoin_address_keys() -> FrozenSet[str]:
    """All token addresses from CSV whose symbol is a known stablecoin."""
    tm = _manager()
    if tm.tokens_df is None or tm.tokens_df.empty:
        return frozenset()
    out: Set[str] = set()
    for _, row in tm.tokens_df.iterrows():
        if _row_symbol_upper(row) not in _STABLECOIN_SYMBOLS:
            continue
        addr = _row_address_str(row)
        if addr:
            out.add(addr)
    return frozenset(out)


def _addresses_for_chain_and_symbols(chain_key: str, symbols: FrozenSet[str]) -> FrozenSet[str]:
    tm = _manager()
    if tm.tokens_df is None or tm.tokens_df.empty:
        return frozenset()
    out: Set[str] = set()
    for _, row in tm.tokens_df.iterrows():
        if _row_chain_key(row) != chain_key:
            continue
        if _row_symbol_upper(row) not in symbols:
            continue
        addr = _row_address_str(row)
        if addr:
            out.add(addr)
    return frozenset(out)


@lru_cache(maxsize=64)
def wrapped_address_keys_for_chain(chain_key: str) -> FrozenSet[str]:
    """Wrapped-token contract addresses for ``chain_key`` from the CSV."""
    base = _addresses_for_chain_and_symbols(chain_key, _WRAPPED_SYMBOLS)
    if chain_key == "solana":
        return frozenset(set(base) | {SOLANA_WRAPPED_SOL_MINT})
    return base


@lru_cache(maxsize=64)
def native_like_address_keys_for_chain(chain_key: str) -> FrozenSet[str]:
    """Addresses for native / wrapped-native symbols on ``chain_key`` (CSV-driven)."""
    native_syms = _NATIVE_SYMBOLS_BY_CHAIN.get(chain_key, frozenset())
    sym_union = frozenset(native_syms | _WRAPPED_SYMBOLS)
    base = _addresses_for_chain_and_symbols(chain_key, sym_union)
    if chain_key == "solana":
        return frozenset(set(base) | {SOLANA_WRAPPED_SOL_MINT})
    return base


@lru_cache(maxsize=64)
def oneinch_dst_stable_for_chain(chain_key: str) -> Optional[str]:
    """Prefer USDC then USDT then DAI on ``chain_key`` for 1inch quote dst (EVM chains only)."""
    for sym in ("USDC", "USDT", "DAI"):
        tm = _manager()
        if tm.tokens_df is None or tm.tokens_df.empty:
            return None
        for _, row in tm.tokens_df.iterrows():
            if _row_chain_key(row) != chain_key:
                continue
            if _row_symbol_upper(row) != sym:
                continue
            addr = _row_address_str(row)
            if addr.startswith("0x") and len(addr) == 42:
                return addr
    return None


def registry_declared_chains_for_address(token_address: str) -> FrozenSet[str]:
    """Normalized chain keys from every CSV row matching this address."""
    key = normalize_token_storage_address(token_address)
    if not key:
        return frozenset()
    tm = _manager()
    if tm.tokens_df is None or tm.tokens_df.empty:
        return frozenset()
    chains: Set[str] = set()
    for _, row in tm.tokens_df.iterrows():
        if _row_address_str(row) != key:
            continue
        chains.add(_row_chain_key(row))
    return frozenset(chains)


def registry_primary_chain_for_address(token_address: str) -> Optional[str]:
    """First declared chain for ``token_address`` (for simple L1/L2 hints)."""
    declared = registry_declared_chains_for_address(token_address)
    if not declared:
        return None
    return next(iter(sorted(declared)))
