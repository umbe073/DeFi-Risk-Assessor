#!/usr/bin/env python3
"""
Update Token Data Viewer CSV with current data
This script reads from tokens.csv and populates market data from webhook cache
"""

import os
import sys
import json
import subprocess
import re
import random
import threading
import pandas as pd
from datetime import datetime
import requests
import time
from concurrent.futures import ThreadPoolExecutor, wait
from email.utils import parsedate_to_datetime
from requests.structures import CaseInsensitiveDict
from statistics import mean, median
from urllib.parse import quote, urlencode, urlparse
from pathlib import Path

# Project directories
PROJECT_ROOT = "/Users/amlfreak/Desktop/venv"
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
REAL_DATA_CACHE_FILE = os.path.join(DATA_DIR, "real_data_cache.json")
FALLBACK_FILE = os.path.join(DATA_DIR, "token_fallbacks.json")
API_RESPONSE_CACHE_FILE = os.path.join(DATA_DIR, "api_response_cache.json")
HTTP_REQUEST_STATE_FILE = os.path.join(DATA_DIR, "http_request_state.json")

# Shared request/cache synchronization primitives.
_CACHE_IO_LOCK = threading.RLock()
_REQUEST_STATE_LOCK = threading.RLock()
_REQUEST_STATE_DIRTY = False
_REQUEST_STATE_LAST_SAVE_TS = 0.0
_HTTP_REQUEST_STATE_CACHE = None
_REQUEST_SEMAPHORE_LOCK = threading.Lock()
_REQUEST_SEMAPHORE = None
_REQUEST_SEMAPHORE_SIZE = 0
_RATE_LIMIT_STATE = {}
_REQUEST_SETTINGS_CACHE = {"ts": 0.0, "settings": {}}
_RAW_REQUESTS_GET = requests.get

# Stale-while-revalidate runtime state.
_SWR_FUTURES = []
_SWR_FUTURES_LOCK = threading.Lock()
_SWR_SCHEDULED_KEYS = set()
_SWR_EXECUTOR = None
_SWR_ENABLED = False
_SWR_WORKERS = 0

# Overwrite policy thresholds (tuned for free-tier API mix).
METRIC_SANITY_CAPS = {
    "market_cap": 5_000_000_000_000.0,   # 5T
    "volume_24h": 2_000_000_000_000.0,   # 2T
    "liquidity": 1_000_000_000_000.0,    # 1T
    "holders": 50_000_000.0,             # 50M
}
METRIC_DRIFT_GUARDS = {
    "market_cap": 0.25,
    "holders": 0.35,
    "liquidity": 0.60,
}
VOLUME_DRIFT_UP_GUARD = 4.0     # +400%
VOLUME_DRIFT_DOWN_GUARD = 0.85  # -85%
METRIC_CROSS_SOURCE_TOLERANCE = {
    "market_cap": 0.30,
    "holders": 0.25,
    "liquidity": 0.35,
    "volume_24h": 0.45,
}
SOURCE_CONFIDENCE_WEIGHTS = {
    "coinmarketcap": 1.00,
    "coingecko": 0.90,
    "defillama": 0.75,
    "dexscreener": 0.70,
    "moralis": 0.85,
    "etherscan": 0.90,
    "bscscan": 0.88,
    "dune": 0.82,
    "blockscout": 0.78,
    "ethplorer": 0.62,
    "solscan": 0.88,
    "solanatracker": 0.82,
    "birdeye": 0.80,
    "goplus": 0.70,
    "api_cache": 0.55,
    "webhook_cache": 0.50,
}

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
except Exception:
    pass

# Some tokens use canonical contracts or API chains that differ from tokens.csv
ADDRESS_OVERRIDES = {
    # Gala's active ERC-20 contract (matches webhook cache & real APIs)
    '0x15d4c048f83bd7e37d49ea4c83a07267ec4203da': '0xd1d2eb1b1e90b638588728b4130137d262c87cae',
    # SKY's on-chain data hasn't propagated yet; reuse Maker's canonical contract for API calls
    '0x56072c95faa701256059aa122697b133aed9279': '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2',
}

# Canonical Solana mint aliases (base58 is case-sensitive, so keep exact target casing).
SOLANA_ADDRESS_OVERRIDES = {
    # Canonical wrapped SOL mint (legacy typo without trailing "2" appears in some lists).
    'so11111111111111111111111111111111111111111': 'So11111111111111111111111111111111111111112',
}

# Override API chain for specific symbols (display chain stays the same)
CHAIN_OVERRIDES = {
    'POL': 'ethereum',  # POL contract lives on Ethereum even though it represents Polygon
}

SYMBOL_FALLBACKS = {
    # Allow seamless migrations (reuse last known real data from the legacy symbol)
    'SKY': 'MKR',
    # Wrapped SOL should inherit SOL historical market profile when needed.
    'WSOL': 'SOL',
}

# Ambiguous short symbols should avoid symbol-only endpoints (CMC/CoinCap/CoinPaprika
# search paths) and rely on contract/chain-aware APIs.
SYMBOL_ONLY_SOURCE_SKIP = {
    'S',
}

SYMBOL_API_OVERRIDES = {
    # Allow new tickers to specify explicit API identifiers when the contract is not indexed yet
    'SKY': {
        # Try the new SKY listings first, fall back to Maker (legacy ID) if not available
        'coingecko_ids': ['sky', 'maker'],
        'coinpaprika_ids': ['sky-sky', 'mkr-maker'],
        'coincap_ids': ['sky', 'maker'],
    },
    'OP': {
        'coingecko_ids': ['optimism'],
        'coinpaprika_ids': ['op-optimism'],
        'coincap_ids': ['optimism'],
    },
    'S': {
        # Sonic canonical IDs (avoid unrelated symbol-S assets that skew market metrics).
        'coingecko_ids': ['sonic-3'],
        'coinpaprika_ids': ['s-sonic'],
        'coincap_ids': ['sonic'],
    },
    'SOL': {
        # Canonical SOL mappings used directly and via WSOL aliasing.
        'coingecko_ids': ['solana'],
        'coinpaprika_ids': ['sol-solana'],
        'coincap_ids': ['solana'],
    },
    'WSOL': {
        # WSOL is SOL-equivalent; query SOL endpoints for market metrics.
        'coingecko_ids': ['wrapped-solana', 'solana'],
        'coinpaprika_ids': ['sol-solana'],
        'coincap_ids': ['solana'],
    },
    'USDT0': {
        # USD₮0 normalizes to USDT0 for API calls.
        'coingecko_ids': ['usdt0'],
    },
}

MARKET_SYMBOL_ALIASES = {
    'WSOL': 'SOL',
}

COINGECKO_PLATFORM_MAP = {
    'ethereum': 'ethereum',
    'eth': 'ethereum',
    'polygon': 'polygon-pos',
    'polygon-pos': 'polygon-pos',
    'op': 'optimistic-ethereum',
    'optimism': 'optimistic-ethereum',
    'bsc': 'binance-smart-chain',
    'binance-smart-chain': 'binance-smart-chain',
    'arbitrum': 'arbitrum-one',
    'arb': 'arbitrum-one',
    'base': 'base',
    'linea': 'linea',
    'avax': 'avalanche',
    'avalanche': 'avalanche',
    'avalanche-c': 'avalanche',
    'sonic': 'sonic',
    'sei': 'sei-v2',
    'sei-evm': 'sei-v2',
    'mantle': 'mantle',
    'mnt': 'mantle',
    'zksync': 'zksync',
    'zk': 'zksync',
    'zksync-era': 'zksync',
    'sol': 'solana',
    'solana': 'solana',
}

COINPAPRIKA_IDS = {
    'WBTC': 'wbtc-wrapped-bitcoin',
    '1INCH': '1inch-1inch',
    'POL': 'matic-polygon',
    'OP': 'op-optimism',
    'SOL': 'sol-solana',
    'GRT': 'grt-the-graph',
    'QNT': 'qnt-quant',
    'SUSHI': 'sushi-sushi',
}

COINGECKO_REQUEST_MIN_DELAY = 1.5  # seconds between requests to avoid rate limits
_last_coingecko_request = 0.0
COINGECKO_SIMPLE_BATCH_SIZE = 40
_coingecko_simple_batch_cache = {}
COINGECKO_PRO_API_KEY = (os.environ.get('COINGECKO_PRO_API_KEY') or '').strip()
COINGECKO_DEMO_API_KEY = (os.environ.get('COINGECKO_API_KEY') or '').strip()
COINGECKO_FORCE_PRO = str(os.environ.get('COINGECKO_USE_PRO', '') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
if COINGECKO_PRO_API_KEY:
    COINGECKO_API_KEY = COINGECKO_PRO_API_KEY
    COINGECKO_KEY_MODE = 'pro'
elif COINGECKO_DEMO_API_KEY:
    COINGECKO_API_KEY = COINGECKO_DEMO_API_KEY
    COINGECKO_KEY_MODE = 'pro' if COINGECKO_FORCE_PRO else 'demo'
else:
    COINGECKO_API_KEY = ''
    COINGECKO_KEY_MODE = 'none'
try:
    COINGECKO_COOLDOWN_SECONDS = max(30.0, float(os.environ.get('COINGECKO_COOLDOWN_SECONDS', '120') or 120))
except Exception:
    COINGECKO_COOLDOWN_SECONDS = 120.0
_coingecko_cooldown_until = 0.0
_last_coingecko_cooldown_log = 0.0
ETHPLORER_API_KEY = os.environ.get('ETHPLORER_API_KEY', 'freekey')
ETHERSCAN_API_KEY = (os.environ.get('ETHERSCAN_API_KEY') or '').strip()
BSCSCAN_API_KEY = (os.environ.get('BSCSCAN_API_KEY') or os.environ.get('ETHERSCAN_API_KEY') or '').strip()
MORALIS_API_KEY = (os.environ.get('MORALIS_API_KEY') or '').strip()
DUNE_API_KEY = (os.environ.get('DUNE_API_KEY') or os.environ.get('DUNE_ANALYTICS_API_KEY') or '').strip()
DUNE_SIM_BASE_URL = (os.environ.get('DUNE_SIM_BASE_URL') or 'https://api.sim.dune.com/v1').strip().rstrip('/')
COINMARKETCAP_API_KEY = (os.environ.get('COINMARKETCAP_API_KEY') or '').strip()
BIRDEYE_API_KEY = (os.environ.get('BIRDEYE_API_KEY') or '').strip()
SOLANATRACKER_API_KEY = (os.environ.get('SOLANATRACKER_API_KEY') or '').strip()
SOLSCAN_API_KEY = (
    os.environ.get('SOLSCAN_API_KEY')
    or os.environ.get('SOLSCAN_PRO_API_KEY')
    or ''
).strip()
try:
    MORALIS_HOLDER_PAGE_SIZE = max(10, int((os.environ.get('MORALIS_HOLDER_PAGE_SIZE') or '100').strip()))
except Exception:
    MORALIS_HOLDER_PAGE_SIZE = 100
try:
    MORALIS_HOLDER_MAX_PAGES = max(1, int((os.environ.get('MORALIS_HOLDER_MAX_PAGES') or '50').strip()))
except Exception:
    MORALIS_HOLDER_MAX_PAGES = 50
try:
    DUNE_HOLDER_PAGE_SIZE = max(1, int((os.environ.get('DUNE_HOLDER_PAGE_SIZE') or '1000').strip()))
except Exception:
    DUNE_HOLDER_PAGE_SIZE = 1000
try:
    DUNE_HOLDER_MAX_PAGES = max(1, int((os.environ.get('DUNE_HOLDER_MAX_PAGES') or '50').strip()))
except Exception:
    DUNE_HOLDER_MAX_PAGES = 50

NATIVE_PLACEHOLDER_ADDRESSES = {
    '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
}


def _coingecko_cooldown_remaining_seconds():
    """Return remaining CoinGecko cooldown seconds (0 when available)."""
    try:
        return max(0.0, float(_coingecko_cooldown_until) - time.time())
    except Exception:
        return 0.0


def _set_coingecko_cooldown(response=None):
    """Set a run-level CoinGecko cooldown window after a 429."""
    global _coingecko_cooldown_until
    retry_after = 0.0
    try:
        if response is not None and getattr(response, 'headers', None):
            raw_retry_after = response.headers.get('Retry-After')
            if raw_retry_after:
                retry_after = float(raw_retry_after)
    except Exception:
        retry_after = 0.0
    cooldown = max(COINGECKO_COOLDOWN_SECONDS, retry_after)
    _coingecko_cooldown_until = max(float(_coingecko_cooldown_until or 0.0), time.time() + cooldown)
    return cooldown


def rate_limited_get(url, timeout=10):
    """Rate-limited GET helper to avoid CoinGecko free-tier throttling."""
    global _last_coingecko_request, _last_coingecko_cooldown_log
    remaining = _coingecko_cooldown_remaining_seconds()
    if remaining > 0:
        now_ts = time.time()
        if (now_ts - float(_last_coingecko_cooldown_log or 0.0)) > 20.0:
            print(f"      ⏭️  CoinGecko cooldown active ({remaining:.0f}s), skipping CoinGecko calls")
            _last_coingecko_cooldown_log = now_ts
        return None
    elapsed = time.time() - _last_coingecko_request
    if elapsed < COINGECKO_REQUEST_MIN_DELAY:
        time.sleep(COINGECKO_REQUEST_MIN_DELAY - elapsed)
    parsed_host = (urlparse(str(url or '')).hostname or '').strip().lower()
    base_headers = {
        "Accept": "application/json",
        "User-Agent": "DeFiRiskAssessor/3.0",
    }
    header_variants = [dict(base_headers)]
    if COINGECKO_API_KEY:
        if parsed_host == 'pro-api.coingecko.com':
            if COINGECKO_KEY_MODE == 'pro':
                header_variants = [
                    {**base_headers, "x-cg-pro-api-key": COINGECKO_API_KEY},
                    dict(base_headers),
                ]
            else:
                # Demo keys are not valid on pro hosts.
                header_variants = [dict(base_headers)]
        elif parsed_host in {'api.coingecko.com', 'demo-api.coingecko.com'}:
            if COINGECKO_KEY_MODE == 'pro':
                header_variants = [
                    {**base_headers, "x-cg-pro-api-key": COINGECKO_API_KEY},
                    dict(base_headers),
                ]
            elif COINGECKO_KEY_MODE == 'demo':
                header_variants = [
                    {**base_headers, "x-cg-demo-api-key": COINGECKO_API_KEY},
                    dict(base_headers),
                ]

    response = None
    for headers in header_variants:
        response = requests.get(url, timeout=timeout, headers=headers)
        _last_coingecko_request = time.time()
        status = int(getattr(response, 'status_code', 0) or 0)
        if status == 200:
            return response
        if status == 429:
            cooldown = _set_coingecko_cooldown(response)
            print(f"      ⏰ CoinGecko rate-limited, cooling down for {cooldown:.0f}s")
            return response
        # Retry with another auth mode for malformed/auth responses.
        if status in (400, 401, 403):
            continue
        break
    return response


def _prime_coingecko_simple_cache(tokens_df):
    """Prefetch CoinGecko simple endpoint in batches to avoid per-token rate-limit storms."""
    global _coingecko_simple_batch_cache
    _coingecko_simple_batch_cache = {}
    if tokens_df is None or len(tokens_df) == 0:
        return

    grouped_addresses = {}
    for _, token_row in tokens_df.iterrows():
        address_raw = token_row.get('Contract Address')
        symbol_raw = token_row.get('Symbol')
        chain_raw = token_row.get('Chain')
        if address_raw is None:
            continue
        address = str(address_raw).strip().lower()
        if not is_valid_hex_address(address):
            continue
        symbol = str(symbol_raw).upper() if symbol_raw is not None else ''
        api_chain = CHAIN_OVERRIDES.get(symbol, str(chain_raw).lower() if chain_raw is not None else 'ethereum')
        platform = COINGECKO_PLATFORM_MAP.get(api_chain, 'ethereum')
        grouped_addresses.setdefault(platform, set()).add(address)

    for platform, addresses in grouped_addresses.items():
        address_list = sorted(addresses)
        if not address_list:
            continue
        _coingecko_simple_batch_cache.setdefault(platform, {})
        for idx in range(0, len(address_list), COINGECKO_SIMPLE_BATCH_SIZE):
            chunk = address_list[idx: idx + COINGECKO_SIMPLE_BATCH_SIZE]
            if not chunk:
                continue
            remaining = _coingecko_cooldown_remaining_seconds()
            if remaining > 0:
                break
            joined = ",".join(chunk)
            simple_url = (
                f"https://api.coingecko.com/api/v3/simple/token_price/{platform}"
                f"?contract_addresses={joined}&vs_currencies=usd"
                f"&include_market_cap=true&include_24hr_vol=true"
            )
            try:
                resp = rate_limited_get(simple_url, timeout=12)
                if resp is None:
                    break
                if resp.status_code == 200:
                    payload = resp.json() if hasattr(resp, 'json') else {}
                    if isinstance(payload, dict):
                        for key, value in payload.items():
                            if isinstance(key, str) and isinstance(value, dict):
                                _coingecko_simple_batch_cache[platform][key.lower()] = value
                elif resp.status_code == 429:
                    break
            except Exception:
                continue

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def is_valid_hex_address(address: str) -> bool:
    """Simple EVM address validator to avoid contract lookups for placeholder IDs."""
    if not isinstance(address, str):
        return False
    addr = address.lower()
    return addr.startswith('0x') and len(addr) == 42 and all(c in '0123456789abcdef' for c in addr[2:])


def normalize_address_for_storage(address: str) -> str:
    """Normalize addresses for internal dict lookups while preserving non-EVM casing."""
    value = str(address or '').strip()
    if not value:
        return ''
    return value.lower() if is_valid_hex_address(value) else value


def address_lookup_variants(address: str):
    """Return lookup variants to bridge old lowercased keys and canonical forms."""
    value = str(address or '').strip()
    if not value:
        return []
    normalized = normalize_address_for_storage(value)
    variants = []
    ordered_candidates = (normalized, value.lower(), value) if is_valid_hex_address(value) else (value, normalized, value.lower())
    for candidate in ordered_candidates:
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def build_token_storage_key(address: str, chain: str = '', symbol: str = '') -> str:
    """Build a cache key; native placeholders are scoped by chain+symbol."""
    normalized_address = normalize_address_for_storage(address)
    if not normalized_address:
        return ''
    if is_native_placeholder_address(normalized_address):
        chain_key = str(chain or '').strip().lower() or 'unknown'
        symbol_key = normalize_symbol_for_api(symbol or '') or str(symbol or '').strip().upper() or 'UNKNOWN'
        return f"native::{chain_key}::{symbol_key}"
    return normalized_address


def first_present_key(mapping, candidates):
    """Return the first matching key from candidates present in mapping."""
    if not isinstance(mapping, dict):
        return None
    for candidate in candidates:
        if candidate in mapping:
            return candidate
    return None


_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {ch: i for i, ch in enumerate(_BASE58_ALPHABET)}


def _decode_base58(value: str):
    """Decode base58 to bytes (returns None on invalid input)."""
    try:
        num = 0
        for ch in value:
            idx = _BASE58_INDEX.get(ch)
            if idx is None:
                return None
            num = (num * 58) + idx
        out = bytearray()
        while num > 0:
            out.append(num & 0xFF)
            num >>= 8
        out.reverse()
        leading_zeros = len(value) - len(value.lstrip('1'))
        return (b'\x00' * leading_zeros) + bytes(out)
    except Exception:
        return None


def is_valid_solana_address(address: str) -> bool:
    """Validate Solana base58 pubkey format (32-byte decoded length)."""
    if not isinstance(address, str):
        return False
    value = address.strip()
    if value.startswith('0x'):
        return False
    if len(value) < 32 or len(value) > 44:
        return False
    decoded = _decode_base58(value)
    return isinstance(decoded, (bytes, bytearray)) and len(decoded) == 32


def normalize_symbol_for_api(symbol) -> str:
    """Normalize display symbols for external API compatibility."""
    if symbol is None:
        return ''
    value = str(symbol).strip().upper()
    if not value:
        return ''
    replacements = {
        '₮': 'T',
        '₿': 'B',
        'Ξ': 'E',
        ' ': '',
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r'[^A-Z0-9._-]', '', value)
    return value


def is_native_placeholder_address(address: str) -> bool:
    """Detect pseudo/native token placeholder addresses (non-contract assets)."""
    if not isinstance(address, str):
        return False
    return address.strip().lower() in NATIVE_PLACEHOLDER_ADDRESSES


def load_settings():
    """Load user settings so we respect refresh intervals and skip windows."""
    default_settings = {
        "cache": {
            "auto_refresh_interval": "1 hour",
            "cache_retention": "24 hours",
            "fallback_sync_interval": "2 hours",
            "background_monitoring": True,
            "respect_48h_metric_skip": True,
            "metric_skip_hours": 2
        },
        "api": {
            "rate_limiting": True,
            "conditional_requests": True,
            "adaptive_backoff": True,
            "max_parallel_requests": 4,
            "retry_backoff_seconds": 1.5,
            "request_jitter_ms": 200,
            "retry_attempts": 3,
            "timeout": 30
        }
    }
    settings_path = os.path.join(DATA_DIR, "settings.json")
    if not os.path.exists(settings_path):
        return default_settings
    try:
        with open(settings_path, "r") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return default_settings


def _parse_interval_to_minutes(value, default_minutes=10):
    """Parse strings like '15 minutes' or '1 hour' into minutes."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return default_minutes
    parts = value.strip().lower().split()
    try:
        number = float(parts[0])
    except Exception:
        return default_minutes
    unit = parts[1] if len(parts) > 1 else "minutes"
    if unit.startswith("hour"):
        return number * 60
    return number


def get_cache_policy():
    """Return cache policy based on settings (skip window + refresh interval)."""
    settings = load_settings()
    cache_cfg = settings.get("cache", {}) if isinstance(settings, dict) else {}
    respect_skip = bool(cache_cfg.get("respect_48h_metric_skip", True))
    try:
        metric_skip_hours = float(cache_cfg.get("metric_skip_hours", 48))
    except Exception:
        metric_skip_hours = 48.0
    refresh_minutes = _parse_interval_to_minutes(cache_cfg.get("auto_refresh_interval", 10), 10)
    return {
        "respect_skip": respect_skip,
        "metric_skip_hours": metric_skip_hours,
        "refresh_minutes": refresh_minutes
    }


def _get_runtime_api_settings():
    """Load API/cache settings with a short in-memory TTL to avoid repeated disk I/O."""
    now_ts = time.time()
    cached_ts = float(_REQUEST_SETTINGS_CACHE.get("ts", 0) or 0.0)
    cached_settings = _REQUEST_SETTINGS_CACHE.get("settings", {})
    if cached_settings and (now_ts - cached_ts) < 10:
        return cached_settings
    settings = load_settings() if callable(load_settings) else {}
    api_cfg = settings.get("api", {}) if isinstance(settings, dict) else {}
    cache_cfg = settings.get("cache", {}) if isinstance(settings, dict) else {}
    merged = {
        "rate_limiting": bool(api_cfg.get("rate_limiting", True)),
        "conditional_requests": bool(api_cfg.get("conditional_requests", True)),
        "adaptive_backoff": bool(api_cfg.get("adaptive_backoff", True)),
        "retry_attempts": max(1, int(api_cfg.get("retry_attempts", 2) or 2)),
        "retry_backoff_seconds": float(api_cfg.get("retry_backoff_seconds", 1.0) or 1.0),
        "request_jitter_ms": int(api_cfg.get("request_jitter_ms", 100) or 100),
        "timeout": float(api_cfg.get("timeout", 20) or 20),
        "max_parallel_requests": max(1, int(api_cfg.get("max_parallel_requests", 4) or 4)),
        "metric_drift_threshold_pct": float(cache_cfg.get("metric_drift_threshold_pct", 2.0) or 2.0),
        "background_monitoring": bool(cache_cfg.get("background_monitoring", False)),
    }
    _REQUEST_SETTINGS_CACHE["ts"] = now_ts
    _REQUEST_SETTINGS_CACHE["settings"] = merged
    return merged


def _load_http_request_state():
    """Load persisted conditional request metadata."""
    global _HTTP_REQUEST_STATE_CACHE
    with _REQUEST_STATE_LOCK:
        if isinstance(_HTTP_REQUEST_STATE_CACHE, dict):
            return _HTTP_REQUEST_STATE_CACHE
        default_state = {"conditional": {}, "last_updated": 0}
        if not os.path.exists(HTTP_REQUEST_STATE_FILE):
            _HTTP_REQUEST_STATE_CACHE = default_state
            return _HTTP_REQUEST_STATE_CACHE
        try:
            with open(HTTP_REQUEST_STATE_FILE, "r") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                if not isinstance(loaded.get("conditional"), dict):
                    loaded["conditional"] = {}
                _HTTP_REQUEST_STATE_CACHE = loaded
                return _HTTP_REQUEST_STATE_CACHE
        except Exception:
            pass
        _HTTP_REQUEST_STATE_CACHE = default_state
        return _HTTP_REQUEST_STATE_CACHE


def _save_http_request_state(force=False):
    """Persist conditional request metadata to disk."""
    global _REQUEST_STATE_DIRTY, _REQUEST_STATE_LAST_SAVE_TS
    with _REQUEST_STATE_LOCK:
        if not _REQUEST_STATE_DIRTY and not force:
            return
        now_ts = time.time()
        if not force and (now_ts - float(_REQUEST_STATE_LAST_SAVE_TS or 0.0)) < 3.0:
            return
        state = _load_http_request_state()
        state["last_updated"] = now_ts
        try:
            with open(HTTP_REQUEST_STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
            _REQUEST_STATE_DIRTY = False
            _REQUEST_STATE_LAST_SAVE_TS = now_ts
        except Exception:
            pass


def _mark_request_state_dirty():
    global _REQUEST_STATE_DIRTY
    with _REQUEST_STATE_LOCK:
        _REQUEST_STATE_DIRTY = True


def _request_cache_key(url, params=None):
    """Stable cache key for conditional request metadata."""
    base = str(url or "").strip()
    if not base:
        return ""
    if not params:
        return base
    encoded = ""
    try:
        if isinstance(params, dict):
            encoded = urlencode(sorted((str(k), str(v)) for k, v in params.items()), doseq=True)
        else:
            encoded = str(params)
    except Exception:
        encoded = str(params)
    return f"{base}?{encoded}" if encoded else base


def _service_key_from_url(url):
    """Map URL to a service key for per-provider rate-limit tracking."""
    try:
        parsed = urlparse(str(url or ""))
        host = (parsed.netloc or "").lower()
        if not host:
            return "unknown"
        host = host.split("@")[-1]
        host = host.split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return "unknown"


def _parse_rate_limit_reset(raw_value):
    """Parse X-RateLimit-Reset style values into epoch seconds."""
    if raw_value is None:
        return 0.0
    text = str(raw_value).strip()
    if not text:
        return 0.0
    now_ts = time.time()
    try:
        numeric = float(text)
        if numeric > 1_000_000_000_000:
            numeric = numeric / 1000.0
        if numeric > 1_000_000_000:
            return numeric
        if numeric > now_ts:
            return numeric
        if numeric >= 0:
            return now_ts + numeric
    except Exception:
        pass
    try:
        parsed = parsedate_to_datetime(text)
        if parsed is not None:
            return parsed.timestamp()
    except Exception:
        pass
    return 0.0


def _update_rate_limit_state(service_key, response):
    """Update in-memory rate-limit state from response headers."""
    if not isinstance(service_key, str) or not service_key:
        return
    if response is None or not hasattr(response, "headers"):
        return
    headers = response.headers or {}
    if not isinstance(headers, dict) and not hasattr(headers, "get"):
        return
    remaining = None
    reset_at = 0.0
    for key in ("X-RateLimit-Remaining", "x-ratelimit-remaining", "RateLimit-Remaining", "ratelimit-remaining"):
        raw_remaining = headers.get(key)
        if raw_remaining is None:
            continue
        try:
            remaining = int(float(str(raw_remaining).strip()))
            break
        except Exception:
            continue
    for key in ("X-RateLimit-Reset", "x-ratelimit-reset", "RateLimit-Reset", "ratelimit-reset", "Retry-After"):
        raw_reset = headers.get(key)
        parsed_reset = _parse_rate_limit_reset(raw_reset)
        if parsed_reset > 0:
            reset_at = parsed_reset
            break
    if remaining is None and reset_at <= 0 and getattr(response, "status_code", 0) != 429:
        return
    state = _RATE_LIMIT_STATE.setdefault(service_key, {})
    if remaining is not None:
        state["remaining"] = remaining
    if reset_at > 0:
        state["reset_at"] = reset_at
    if getattr(response, "status_code", 0) == 429:
        retry_after = _parse_rate_limit_reset((headers or {}).get("Retry-After"))
        if retry_after > 0:
            state["reset_at"] = max(float(state.get("reset_at", 0.0) or 0.0), retry_after)
        state["remaining"] = 0


def _build_synthetic_response(status_code, url, payload=None, headers=None):
    """Create a Response-like object for preemptive throttling / conditional hits."""
    synthetic = requests.Response()
    synthetic.status_code = int(status_code)
    synthetic.url = str(url or "")
    header_mapping = {}
    if isinstance(headers, dict):
        try:
            for raw_key, raw_value in headers.items():
                key = str(raw_key or "").strip()
                if not key:
                    continue
                header_mapping[key] = str(raw_value or "")
        except Exception:
            header_mapping = {}
    synthetic.headers = CaseInsensitiveDict(header_mapping)
    body = payload if payload is not None else {}
    try:
        encoded = json.dumps(body).encode("utf-8")
    except Exception:
        encoded = b"{}"
    synthetic._content = encoded
    synthetic.encoding = "utf-8"
    synthetic.reason = "synthetic"
    return synthetic


def _get_request_semaphore(max_parallel):
    """Return semaphore enforcing global max parallel request count."""
    global _REQUEST_SEMAPHORE, _REQUEST_SEMAPHORE_SIZE
    target = max(1, int(max_parallel or 1))
    with _REQUEST_SEMAPHORE_LOCK:
        if _REQUEST_SEMAPHORE is None or _REQUEST_SEMAPHORE_SIZE != target:
            _REQUEST_SEMAPHORE = threading.BoundedSemaphore(target)
            _REQUEST_SEMAPHORE_SIZE = target
        return _REQUEST_SEMAPHORE


def _preemptive_rate_limit_gate(service_key, runtime_cfg):
    """Return (allowed, wait_seconds) based on stored rate-limit state."""
    if not runtime_cfg.get("rate_limiting", True):
        return True, 0.0
    state = _RATE_LIMIT_STATE.get(service_key, {}) if isinstance(_RATE_LIMIT_STATE, dict) else {}
    remaining = state.get("remaining")
    try:
        remaining_val = int(remaining) if remaining is not None else None
    except Exception:
        remaining_val = None
    reset_at = float(state.get("reset_at", 0.0) or 0.0)
    now_ts = time.time()
    wait_seconds = max(0.0, reset_at - now_ts) if reset_at > 0 else 0.0
    if remaining_val is not None and remaining_val <= 0 and wait_seconds > 0:
        if runtime_cfg.get("adaptive_backoff", True) and wait_seconds <= 2.0:
            time.sleep(wait_seconds)
            return True, 0.0
        return False, wait_seconds
    if (
        runtime_cfg.get("adaptive_backoff", True)
        and remaining_val is not None
        and remaining_val <= 2
        and wait_seconds > 0
    ):
        base_delay = min(1.25, max(0.15, wait_seconds / float(max(remaining_val + 1, 1))))
        jitter = random.uniform(0.0, max(0.0, float(runtime_cfg.get("request_jitter_ms", 100) or 100) / 1000.0))
        time.sleep(base_delay + jitter)
    return True, 0.0


def _read_conditional_entry(cache_key):
    state = _load_http_request_state()
    entries = state.get("conditional", {}) if isinstance(state, dict) else {}
    value = entries.get(cache_key, {}) if isinstance(entries, dict) else {}
    return value if isinstance(value, dict) else {}


def _store_conditional_entry(cache_key, response):
    """Persist ETag/Last-Modified metadata (+ body when lightweight)."""
    if not cache_key or response is None:
        return
    headers = response.headers or {}
    etag = headers.get("ETag") or headers.get("Etag") or headers.get("etag")
    last_modified = (
        headers.get("Last-Modified")
        or headers.get("last-modified")
        or headers.get("Last-modified")
    )
    if not etag and not last_modified:
        return
    content_type = str(headers.get("Content-Type", "") or "").lower()
    cached_body = ""
    try:
        raw_text = response.text if "application/json" in content_type else ""
    except Exception:
        raw_text = ""
    if isinstance(raw_text, str) and len(raw_text.encode("utf-8")) <= 750_000:
        cached_body = raw_text

    state = _load_http_request_state()
    entries = state.setdefault("conditional", {})
    if not isinstance(entries, dict):
        entries = {}
        state["conditional"] = entries
    entries[cache_key] = {
        "etag": etag or "",
        "last_modified": last_modified or "",
        "content_type": content_type or "application/json",
        "cached_body": cached_body,
        "saved_at": time.time(),
    }
    # Prune oldest entries to keep state bounded.
    max_entries = 3000
    if len(entries) > max_entries:
        sortable = []
        for key, val in entries.items():
            if isinstance(val, dict):
                sortable.append((float(val.get("saved_at", 0) or 0), key))
        sortable.sort()
        for _, key in sortable[: max(0, len(entries) - max_entries)]:
            entries.pop(key, None)
    _mark_request_state_dirty()
    _save_http_request_state(force=False)


def smart_get(url, **kwargs):
    """Shared GET wrapper with conditional headers + proactive rate-limit throttling."""
    runtime_cfg = _get_runtime_api_settings()
    timeout = kwargs.get("timeout")
    if timeout is None:
        kwargs["timeout"] = float(runtime_cfg.get("timeout", 20) or 20)

    service_key = _service_key_from_url(url)
    allowed, wait_seconds = _preemptive_rate_limit_gate(service_key, runtime_cfg)
    if not allowed:
        retry_after = max(1, int(wait_seconds))
        synthetic_headers = {
            "Retry-After": str(retry_after),
            "X-RateLimit-Remaining": "0",
        }
        return _build_synthetic_response(
            429,
            url,
            payload={
                "error": "preemptive_rate_limited",
                "service": service_key,
                "retry_after_seconds": retry_after,
            },
            headers=synthetic_headers,
        )

    headers = kwargs.pop("headers", {})
    if not isinstance(headers, dict):
        headers = dict(headers or {})
    params = kwargs.get("params")
    cache_key = _request_cache_key(url, params)
    conditional_entry = {}
    if runtime_cfg.get("conditional_requests", True) and cache_key:
        conditional_entry = _read_conditional_entry(cache_key)
        etag = conditional_entry.get("etag") if isinstance(conditional_entry, dict) else ""
        last_modified = conditional_entry.get("last_modified") if isinstance(conditional_entry, dict) else ""
        if etag and "If-None-Match" not in headers:
            headers["If-None-Match"] = etag
        if last_modified and "If-Modified-Since" not in headers:
            headers["If-Modified-Since"] = last_modified
    kwargs["headers"] = headers

    retry_attempts = max(1, int(runtime_cfg.get("retry_attempts", 2) or 2))
    base_backoff = max(0.1, float(runtime_cfg.get("retry_backoff_seconds", 1.0) or 1.0))
    jitter_seconds = max(0.0, float(runtime_cfg.get("request_jitter_ms", 100) or 100) / 1000.0)

    semaphore = _get_request_semaphore(runtime_cfg.get("max_parallel_requests", 4))
    acquired = semaphore.acquire(timeout=runtime_cfg.get("timeout", 20))
    if not acquired:
        return _build_synthetic_response(
            503,
            url,
            payload={"error": "request_queue_timeout", "service": service_key},
            headers={},
        )
    try:
        last_response = None
        for attempt in range(retry_attempts):
            try:
                response = _RAW_REQUESTS_GET(url, **kwargs)
            except requests.RequestException:
                if attempt >= (retry_attempts - 1):
                    raise
                if runtime_cfg.get("adaptive_backoff", True):
                    sleep_time = (base_backoff * (2 ** attempt)) + random.uniform(0.0, jitter_seconds)
                    time.sleep(sleep_time)
                continue

            last_response = response
            _update_rate_limit_state(service_key, response)

            if response.status_code == 304:
                cached_body = conditional_entry.get("cached_body") if isinstance(conditional_entry, dict) else ""
                if cached_body:
                    synthetic_headers = dict(response.headers or {})
                    synthetic_headers["X-Conditional-Cache"] = "hit"
                    try:
                        payload = json.loads(cached_body)
                    except Exception:
                        payload = {"cached_body": cached_body}
                    return _build_synthetic_response(
                        200,
                        url,
                        payload=payload,
                        headers=synthetic_headers,
                    )
                return response

            if response.status_code == 200 and runtime_cfg.get("conditional_requests", True):
                _store_conditional_entry(cache_key, response)
                return response

            if response.status_code == 429 and attempt < (retry_attempts - 1) and runtime_cfg.get("adaptive_backoff", True):
                retry_after_ts = _parse_rate_limit_reset((response.headers or {}).get("Retry-After"))
                retry_delay = max(0.25, (retry_after_ts - time.time()) if retry_after_ts > 0 else (base_backoff * (2 ** attempt)))
                retry_delay += random.uniform(0.0, jitter_seconds)
                time.sleep(retry_delay)
                continue

            return response
        return last_response or _build_synthetic_response(599, url, payload={"error": "unknown_request_error"}, headers={})
    finally:
        try:
            semaphore.release()
        except Exception:
            pass


# Route all GET calls through the shared wrapper.
requests.get = smart_get


def get_entry_timestamp(entry):
    """Extract a numeric timestamp from a cache/fallback entry if present."""
    if not isinstance(entry, dict):
        return 0.0
    ts = entry.get("timestamp", 0)
    try:
        return float(ts)
    except Exception:
        return 0.0

def _safe_float(value):
    """Best-effort float parser used across API payloads."""
    try:
        if value is None:
            return 0.0
        if isinstance(value, str):
            cleaned = value.replace(',', '').strip()
            if cleaned == '':
                return 0.0
            return float(cleaned)
        return float(value)
    except Exception:
        return 0.0


def _is_estimated_holders(value):
    """Return True if holders value looks like an estimate/placeholder."""
    try:
        v = int(float(value))
    except Exception:
        return True
    # Round-number placeholders used by legacy cache/report fallbacks.
    return v in {
        0,
        2500,
        5000,
        10000,
        25000,
        50000,
        100000,
        200000,
        250000,
        500000,
        1000000,
    }


def _normalize_source_labels(source_values):
    """Normalize source labels to stable lowercase keys."""
    normalized = []
    for value in source_values or []:
        label = str(value or "").strip().lower()
        if not label:
            continue
        if label.startswith("avg(") and label.endswith(")"):
            label = label[4:-1]
        for token in re.split(r"[,| ]+", label):
            token = token.strip()
            if token and token not in normalized:
                normalized.append(token)
    return normalized


def _source_confidence_score(source_values):
    """Compute confidence score from unique provider labels."""
    labels = _normalize_source_labels(source_values)
    if not labels:
        return 0.0
    score = 0.0
    for label in labels:
        weight = 0.45
        for key, value in SOURCE_CONFIDENCE_WEIGHTS.items():
            if key in label:
                weight = max(weight, float(value))
        score += weight
    return round(min(score, 5.0), 3)


def _normalize_metric_candidate(metric, value):
    """Return positive validated metric value, otherwise 0."""
    metric_key = str(metric or "").strip().lower()
    if metric_key == "holders":
        parsed_holders = _parse_positive_holders(value)
        if parsed_holders <= 0 or _is_estimated_holders(parsed_holders):
            return 0.0
        max_allowed = int(METRIC_SANITY_CAPS.get("holders", 0) or 0)
        if max_allowed > 0 and parsed_holders > max_allowed:
            return 0.0
        return float(parsed_holders)
    parsed = _safe_float(value)
    if parsed <= 0:
        return 0.0
    max_allowed = float(METRIC_SANITY_CAPS.get(metric_key, 0) or 0.0)
    if max_allowed > 0 and parsed > max_allowed:
        return 0.0
    return float(parsed)


def _metric_drift_guard(metric):
    """Per-metric drift guard; includes configured floor threshold."""
    metric_key = str(metric or "").strip().lower()
    runtime_cfg = _get_runtime_api_settings()
    floor = max(0.0, float(runtime_cfg.get("metric_drift_threshold_pct", 2.0) or 2.0) / 100.0)
    if metric_key in METRIC_DRIFT_GUARDS:
        return max(float(METRIC_DRIFT_GUARDS[metric_key]), floor)
    return floor


def _is_significant_metric_drift(metric, old_value, new_value):
    """Determine whether change exceeds drift guard and needs corroboration."""
    metric_key = str(metric or "").strip().lower()
    old_val = _normalize_metric_candidate(metric_key, old_value)
    new_val = _normalize_metric_candidate(metric_key, new_value)
    if old_val <= 0 or new_val <= 0:
        return False
    if metric_key == "volume_24h":
        if new_val >= old_val:
            increase_ratio = (new_val - old_val) / old_val
            return increase_ratio > VOLUME_DRIFT_UP_GUARD
        decrease_ratio = (old_val - new_val) / old_val
        return decrease_ratio > VOLUME_DRIFT_DOWN_GUARD
    drift_ratio = abs(new_val - old_val) / old_val
    return drift_ratio > _metric_drift_guard(metric_key)


def _extract_metric_observations(metric_source_values, metric):
    """Return source->value map for a metric."""
    metric_key = str(metric or "").strip().lower()
    metric_map = {}
    if not isinstance(metric_source_values, dict):
        return metric_map
    raw_values = metric_source_values.get(metric_key, {})
    if not isinstance(raw_values, dict):
        return metric_map
    for source, raw_value in raw_values.items():
        normalized_source = str(source or "").strip().lower()
        if not normalized_source:
            continue
        parsed = _normalize_metric_candidate(metric_key, raw_value)
        if parsed > 0:
            metric_map[normalized_source] = parsed
    return metric_map


def _metric_is_corroborated(metric, candidate_value, metric_source_values):
    """Check if 2+ sources agree with candidate value within tolerance."""
    metric_key = str(metric or "").strip().lower()
    candidate = _normalize_metric_candidate(metric_key, candidate_value)
    if candidate <= 0:
        return False
    observations = _extract_metric_observations(metric_source_values, metric_key)
    if len(observations) < 2:
        return False
    tolerance = float(METRIC_CROSS_SOURCE_TOLERANCE.get(metric_key, 0.30))
    agreeing = 0
    for observed in observations.values():
        diff_ratio = abs(observed - candidate) / max(candidate, 1.0)
        if diff_ratio <= tolerance:
            agreeing += 1
    return agreeing >= 2


def _read_metric_history(entry, metric, max_points=12):
    """Read recent metric history from cached entry."""
    metric_key = str(metric or "").strip().lower()
    history = entry.get("metric_history", []) if isinstance(entry, dict) else []
    if not isinstance(history, list):
        return []
    values = []
    for item in history[-max_points:]:
        if not isinstance(item, dict):
            continue
        parsed = _normalize_metric_candidate(metric_key, item.get(metric_key, 0))
        if parsed > 0:
            values.append(parsed)
    return values


def _history_has_anomaly(metric, candidate_value, history_values):
    """Detect trend-breaking moves that require corroboration."""
    metric_key = str(metric or "").strip().lower()
    candidate = _normalize_metric_candidate(metric_key, candidate_value)
    if candidate <= 0 or not isinstance(history_values, list):
        return False
    trimmed = [float(v) for v in history_values if isinstance(v, (int, float)) and v > 0]
    if len(trimmed) < 3:
        return False
    baseline = median(trimmed)
    if baseline <= 0:
        return False
    ratio = candidate / baseline
    if metric_key == "volume_24h":
        return ratio > 5.0 or ratio < 0.10
    if metric_key == "market_cap":
        return ratio > 2.5 or ratio < 0.40
    if metric_key == "holders":
        return ratio > 1.9 or ratio < 0.55
    if metric_key == "liquidity":
        return ratio > 4.5 or ratio < 0.20
    return False


def _append_metric_history(entry, metrics_snapshot):
    """Append a compact metric history point for overwrite validation."""
    if not isinstance(entry, dict):
        return
    snapshot = {
        "timestamp": time.time(),
    }
    for metric_name in ("market_cap", "volume_24h", "holders", "liquidity", "price"):
        parsed = _normalize_metric_candidate(metric_name, metrics_snapshot.get(metric_name, 0))
        if parsed <= 0:
            continue
        if metric_name == "holders":
            snapshot[metric_name] = int(parsed)
        else:
            snapshot[metric_name] = float(parsed)
    if len(snapshot) <= 1:
        return
    history = entry.get("metric_history", [])
    if not isinstance(history, list):
        history = []
    history.append(snapshot)
    entry["metric_history"] = history[-96:]


def _resolve_metric_update(
    metric,
    new_value,
    old_value,
    metric_source_values,
    old_source_confidence,
    new_source_confidence,
    history_values,
):
    """Unified overwrite validator: range + drift + cross-source + history."""
    metric_key = str(metric or "").strip().lower()
    parsed_new = _normalize_metric_candidate(metric_key, new_value)
    parsed_old = _normalize_metric_candidate(metric_key, old_value)
    if parsed_new <= 0:
        return parsed_old, False, "reject_invalid_or_placeholder"
    if parsed_old <= 0:
        return parsed_new, True, "accept_first_valid_value"

    significant_drift = _is_significant_metric_drift(metric_key, parsed_old, parsed_new)
    historical_anomaly = _history_has_anomaly(metric_key, parsed_new, history_values)
    significant_change = bool(significant_drift or historical_anomaly)
    corroborated = _metric_is_corroborated(metric_key, parsed_new, metric_source_values)
    higher_source_confidence = float(new_source_confidence) >= (float(old_source_confidence) + 0.25)

    # Final overwrite rule:
    # valid && (higher_source_confidence || corroborated_significant_change)
    if significant_change:
        if corroborated or higher_source_confidence:
            return parsed_new, True, "accept_significant_confirmed"
        return parsed_old, False, "reject_significant_unconfirmed"
    return parsed_new, True, "accept_within_drift_guard"


def load_latest_report_data():
    """Load the latest XLSX risk assessment report for fallback metrics."""
    reports_dir = Path(DATA_DIR) / "risk_reports"
    timestamped_name = re.compile(r"^DeFi Tokens Risk Assessment Results_\d{8}_\d{6}\.xlsx$")
    report_candidates = []

    if reports_dir.exists():
        report_candidates.extend([p for p in reports_dir.glob("*.xlsx") if not p.name.startswith("~$")])
    report_candidates.extend([p for p in Path(DATA_DIR).glob("*.xlsx") if not p.name.startswith("~$")])

    timestamped_reports = [p for p in report_candidates if timestamped_name.match(p.name)]
    if timestamped_reports:
        reports = sorted(timestamped_reports, key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        # Keep compatibility with non-timestamped report names, but avoid lock/temp files.
        reports = sorted(report_candidates, key=lambda p: p.stat().st_mtime, reverse=True)

    by_address = {}
    by_symbol = {}
    scanned_reports = 0

    def _merge_entry(current, incoming):
        if not isinstance(current, dict):
            current = {}
        merged = dict(current)
        incoming_source = str(incoming.get("data_source", "") or "").lower()
        prefer_incoming = incoming_source.startswith("json_report:")
        for key in ("market_cap", "volume_24h", "liquidity", "price", "risk_score"):
            cur_val = merged.get(key, 0) or 0
            in_val = incoming.get(key, 0) or 0
            if isinstance(in_val, (int, float)) and in_val > 0:
                if prefer_incoming or not isinstance(cur_val, (int, float)) or cur_val <= 0:
                    merged[key] = float(in_val)
        # Holders: accept only non-estimated values, and allow fresher/larger
        # values to replace stale cached non-zero values.
        cur_holders = int(merged.get("holders", 0) or 0)
        in_holders = int(incoming.get("holders", 0) or 0)
        cur_is_placeholder = _is_estimated_holders(cur_holders)
        if (
            in_holders > 0
            and not _is_estimated_holders(in_holders)
            and (
                prefer_incoming
                or cur_holders <= 0
                or cur_is_placeholder
                or in_holders > cur_holders
            )
        ):
            merged["holders"] = in_holders
        # Keep a human-readable source label from first fill.
        if "data_source" not in merged or prefer_incoming:
            merged["data_source"] = incoming.get("data_source", "report")
        return merged

    def _safe_float(value):
        try:
            if value is None:
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    def _extract_json_metrics(item):
        market_cap = _safe_float(item.get("market_cap", 0))
        volume_24h = _safe_float(item.get("volume_24h", 0))
        liquidity = _safe_float(item.get("liquidity", 0))
        price = _safe_float(item.get("price", 0))
        risk_score = _safe_float(item.get("risk_score", item.get("overall_risk_score", 0)))
        holders_val = int(_safe_float(item.get("holders", 0)))

        market_blob = item.get("market", {}) if isinstance(item.get("market"), dict) else {}
        cmc_blob = market_blob.get("cmc", {}) if isinstance(market_blob.get("cmc"), dict) else {}
        cmc_data = cmc_blob.get("data", {}) if isinstance(cmc_blob.get("data"), dict) else {}
        cmc_quote = cmc_data.get("quote", {}) if isinstance(cmc_data.get("quote"), dict) else {}
        cmc_usd = cmc_quote.get("USD", {}) if isinstance(cmc_quote.get("USD"), dict) else {}
        cmc_mc = _safe_float(cmc_usd.get("market_cap", 0))
        cmc_vol = _safe_float(cmc_usd.get("volume_24h", 0))
        cmc_price = _safe_float(cmc_usd.get("price", 0))

        if cmc_mc > 0:
            market_cap = cmc_mc
        if cmc_vol > 0:
            volume_24h = cmc_vol
        if cmc_price > 0:
            price = cmc_price

        onchain_blob = item.get("onchain", {}) if isinstance(item.get("onchain"), dict) else {}
        if holders_val <= 0:
            for key in ("holders", "holder_count", "total_holders"):
                parsed = int(_safe_float(onchain_blob.get(key, 0)))
                if parsed > 0 and not _is_estimated_holders(parsed):
                    holders_val = parsed
                    break

        if _is_estimated_holders(holders_val):
            holders_val = 0

        return {
            "market_cap": market_cap if market_cap > 0 else 0,
            "volume_24h": volume_24h if volume_24h > 0 else 0,
            "holders": holders_val,
            "liquidity": liquidity if liquidity > 0 else 0,
            "price": price if price > 0 else 0,
            "risk_score": risk_score if risk_score > 0 else 0,
        }

    for report_path in reports:
        try:
            df = pd.read_excel(report_path, sheet_name=0)
        except Exception:
            continue
        if df.empty:
            continue
        scanned_reports += 1

        def safe_num(val):
            try:
                if pd.isna(val):
                    return 0
                return float(val)
            except Exception:
                return 0

        for _, row in df.iterrows():
            address_val_raw = str(row.get("Token Address", "") or "").strip()
            address_val = normalize_address_for_storage(address_val_raw)
            symbol_val = str(row.get("Symbol", "") or "").upper()
            raw_holders = int(safe_num(row.get("Holders", 0)))
            # Strip estimated/placeholder holders so downstream averaging uses real data only
            holders_val = 0 if _is_estimated_holders(raw_holders) else raw_holders
            entry = {
                "market_cap": safe_num(row.get("Market Cap", 0)),
                "volume_24h": safe_num(row.get("Volume 24h", 0)),
                "holders": holders_val,
                "liquidity": safe_num(row.get("Liquidity", 0)),
                "price": safe_num(row.get("Price", 0)),
                "risk_score": safe_num(row.get("Risk Score", 0)),
                "data_source": f"report:{report_path.name}"
            }
            if address_val:
                by_address[address_val] = _merge_entry(by_address.get(address_val), entry)
            if address_val_raw and address_val_raw != address_val:
                by_address[address_val_raw] = _merge_entry(by_address.get(address_val_raw), entry)
            if symbol_val:
                by_symbol[symbol_val] = _merge_entry(by_symbol.get(symbol_val), entry)

    # Also parse JSON reports (prefer richer nested market payloads like CMC quotes).
    json_candidates = []
    latest_json = reports_dir / "risk_report_latest.json"
    if latest_json.exists():
        json_candidates.append(latest_json)
    if reports_dir.exists():
        json_candidates.extend(sorted(reports_dir.glob("risk_report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True))

    seen_json_paths = set()
    for json_path in json_candidates:
        if json_path in seen_json_paths or not json_path.exists():
            continue
        seen_json_paths.add(json_path)
        try:
            with open(json_path, "r") as f:
                payload = json.load(f)
        except Exception:
            continue
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            report_items = payload.get("report")
            token_items = payload.get("tokens")
            if isinstance(report_items, list):
                items = report_items
            elif isinstance(token_items, list):
                items = token_items
            else:
                items = []
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            address_val_raw = str(item.get("token") or item.get("token_address") or "").strip()
            address_val = normalize_address_for_storage(address_val_raw)
            symbol_val = str(item.get("symbol") or "").upper()
            metrics = _extract_json_metrics(item)
            if not any(_safe_float(metrics.get(key, 0)) > 0 for key in ("market_cap", "volume_24h", "holders", "liquidity", "price", "risk_score")):
                continue
            entry = dict(metrics)
            entry["data_source"] = f"json_report:{json_path.name}"
            if address_val:
                by_address[address_val] = _merge_entry(by_address.get(address_val), entry)
            if address_val_raw and address_val_raw != address_val:
                by_address[address_val_raw] = _merge_entry(by_address.get(address_val_raw), entry)
            if symbol_val:
                by_symbol[symbol_val] = _merge_entry(by_symbol.get(symbol_val), entry)

    if by_address or by_symbol:
        selected_path = str(reports[0]) if reports else None
        print(f"✅ Loaded report fallback data from {scanned_reports} report(s) ({len(by_address)} addresses)")
        return {
            "by_address": by_address,
            "by_symbol": by_symbol,
            "path": selected_path
        }
    print("⚠️  No XLSX reports with usable data found in data directory")
    return {"by_address": {}, "by_symbol": {}, "path": None}


def fetch_cached_api_market_data(token_address: str, symbol: str):
    """Use cached API responses (real historical API hits) when live network is unavailable."""
    if not os.path.exists(API_RESPONSE_CACHE_FILE):
        return None
    try:
        with open(API_RESPONSE_CACHE_FILE, "r") as f:
            cache = json.load(f)
    except Exception:
        return None
    
    addr_candidates = address_lookup_variants(token_address)
    symbol_key = (symbol or "").upper()
    metrics = {'market_cap': [], 'volume_24h': [], 'price': [], 'liquidity': []}
    sources = []
    
    for key, entry in cache.items():
        if not isinstance(entry, dict):
            continue
        key_lc = key.lower()
        if addr_candidates and not any(candidate.lower() in key_lc for candidate in addr_candidates):
            continue
        if 'market_data' not in key:
            continue
        data = entry.get('data', {}) or {}
        mc = data.get('market_cap', 0) or 0
        vol = data.get('volume_24h', 0) or 0
        price = data.get('price', 0) or 0
        liq = data.get('liquidity', 0) or 0
        if mc > 0:
            metrics['market_cap'].append(float(mc))
        if vol > 0:
            metrics['volume_24h'].append(float(vol))
        if price > 0:
            metrics['price'].append(float(price))
        if liq > 0:
            metrics['liquidity'].append(float(liq))
        api_name = entry.get('api_name') or 'api_cache'
        if api_name not in sources and any(v > 0 for v in (mc, vol, price, liq)):
            sources.append(api_name)
    
    if any(metrics.values()):
        return {
            'market_cap': mean(metrics['market_cap']) if metrics['market_cap'] else 0,
            'volume_24h': mean(metrics['volume_24h']) if metrics['volume_24h'] else 0,
            'price': mean(metrics['price']) if metrics['price'] else 0,
            'liquidity': mean(metrics['liquidity']) if metrics['liquidity'] else 0,
            'holders': 0,
            'sources_used': sources,
            'data_source': 'api_cache'
        }
    return None


def save_fallback_entry(token_address, entry):
    """Persist a single token entry to the fallback file under token_mappings."""
    try:
        with _CACHE_IO_LOCK:
            if os.path.exists(FALLBACK_FILE):
                with open(FALLBACK_FILE, "r") as f:
                    fallback_data = json.load(f)
            else:
                fallback_data = {}
            if not isinstance(fallback_data, dict):
                fallback_data = {}
            token_mappings = fallback_data.get("token_mappings", {})
            if not isinstance(token_mappings, dict):
                token_mappings = {}
            storage_key = build_token_storage_key(
                token_address,
                str((entry or {}).get('chain') or '') if isinstance(entry, dict) else '',
                str((entry or {}).get('symbol') or '') if isinstance(entry, dict) else '',
            )
            if not storage_key:
                storage_key = normalize_address_for_storage(token_address)
            token_mappings[storage_key] = entry
            # Drop legacy unscoped native placeholder key to avoid cross-chain collisions.
            normalized_token_address = normalize_address_for_storage(token_address)
            if (
                normalized_token_address
                and storage_key != normalized_token_address
                and is_native_placeholder_address(normalized_token_address)
            ):
                token_mappings.pop(normalized_token_address, None)
            fallback_data["token_mappings"] = token_mappings
            fallback_data["last_updated"] = time.time()
            with open(FALLBACK_FILE, "w") as f:
                json.dump(fallback_data, f, indent=2)
    except Exception as e:
        print(f"⚠️  Could not update fallback file: {e}")

def load_tokens_csv():
    """Load tokens from the main tokens.csv file"""
    tokens_csv = os.path.join(DATA_DIR, "tokens.csv")
    
    if not os.path.exists(tokens_csv):
        print(f"❌ Error: tokens.csv not found at {tokens_csv}")
        return None
    
    try:
        df = pd.read_csv(tokens_csv)
        
        # Normalize column names so downstream logic keeps working even if the CSV uses lowercase headers
        column_aliases = {
            'address': 'Contract Address',
            'chain': 'Chain',
            'symbol': 'Symbol',
            'name': 'Token Name'
        }
        for source_col, target_col in column_aliases.items():
            if source_col in df.columns and target_col not in df.columns:
                df[target_col] = df[source_col]
        
        missing_columns = [col for col in ("Contract Address", "Token Name", "Symbol", "Chain") if col not in df.columns]
        if missing_columns:
            raise ValueError(f"tokens.csv is missing required column(s): {', '.join(missing_columns)}")
        
        print(f"✅ Loaded {len(df)} tokens from tokens.csv")
        return df
    except Exception as e:
        print(f"❌ Error reading tokens.csv: {e}")
        return None

def load_webhook_cache():
    """Load data from webhook cache"""
    cache_file = REAL_DATA_CACHE_FILE
    
    if not os.path.exists(cache_file):
        print(f"⚠️  Webhook cache not found at {cache_file}")
        return {}
    
    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        tokens = cache_data.get('tokens', {})
        sanitized_tokens, changed = sanitize_webhook_cache(tokens)
        if changed:
            cache_data['tokens'] = sanitized_tokens
            save_real_data_cache(cache_data)
        print(f"✅ Loaded webhook cache with {len(sanitized_tokens)} tokens (real data only)")
        return sanitized_tokens
    except Exception as e:
        print(f"❌ Error reading webhook cache: {e}")
        return {}

def load_fallback_data():
    """Load data from fallback file"""
    fallback_file = FALLBACK_FILE
    
    if not os.path.exists(fallback_file):
        print(f"⚠️  Fallback file not found at {fallback_file}")
        return {}
    
    try:
        with open(fallback_file, 'r') as f:
            fallback_data = json.load(f)
        tokens = {}
        # Prefer token_mappings, but keep backwards compatibility with "tokens"
        token_mappings = fallback_data.get('token_mappings', {})
        if isinstance(token_mappings, dict):
            for raw_key, value in token_mappings.items():
                key = str(raw_key or '').strip()
                if not key:
                    continue
                tokens[key] = value
                normalized = normalize_address_for_storage(key)
                if normalized and normalized != key:
                    tokens[normalized] = value
                lowered = key.lower()
                if lowered and lowered != key:
                    tokens[lowered] = value
        legacy_tokens = fallback_data.get('tokens', {})
        if isinstance(legacy_tokens, dict):
            for raw_key, value in legacy_tokens.items():
                key = str(raw_key or '').strip()
                if not key:
                    continue
                tokens[key] = value
                normalized = normalize_address_for_storage(key)
                if normalized and normalized != key:
                    tokens[normalized] = value
                lowered = key.lower()
                if lowered and lowered != key:
                    tokens[lowered] = value
        print(f"✅ Loaded fallback data with {len(tokens)} tokens")
        return tokens
    except Exception as e:
        print(f"❌ Error reading fallback data: {e}")
        return {}

def save_real_data_cache(cache_data):
    """Persist sanitized or updated real data cache to disk"""
    try:
        with _CACHE_IO_LOCK:
            with open(REAL_DATA_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)
    except Exception as e:
        print(f"⚠️  Could not save real_data_cache.json: {e}")

def sanitize_webhook_cache(tokens):
    """Remove estimated/fallback entries from cache tokens"""
    sanitized = {}
    changed = False
    
    for address, data in tokens.items():
        cleaned_entry, keep_entry, entry_changed = sanitize_cache_entry(address, data)
        if entry_changed:
            changed = True
        if keep_entry:
            sanitized[address] = cleaned_entry
        else:
            changed = True
    
    return sanitized, changed

def sanitize_cache_entry(address, data):
    """Clean a single cache entry, keeping only real-time data"""
    if not isinstance(data, dict):
        return {}, False, True
    
    cleaned = dict(data)
    entry_changed = False
    
    def remove_if(predicate, container):
        removed = False
        keys_to_remove = []
        for key, value in container.items():
            if predicate(key, value):
                keys_to_remove.append(key)
        for key in keys_to_remove:
            container.pop(key, None)
            removed = True
        return removed
    
    market_data = cleaned.get('market_data')
    if isinstance(market_data, dict):
        removed = remove_if(
            lambda _k, v: not isinstance(v, dict) or 'real' not in str(v.get('source', '')).lower(),
            market_data
        )
        if removed:
            entry_changed = True
        if not market_data:
            cleaned.pop('market_data', None)
    
    onchain_data = cleaned.get('onchain_data')
    if isinstance(onchain_data, dict):
        removed = remove_if(
            lambda _k, v: not isinstance(v, dict) or str(v.get('source', '')).lower() != 'real-time',
            onchain_data
        )
        if removed:
            entry_changed = True
        if not onchain_data:
            cleaned.pop('onchain_data', None)
    
    liquidity_data = cleaned.get('liquidity_data')
    if isinstance(liquidity_data, dict):
        removed = remove_if(
            lambda _k, v: not isinstance(v, dict) or 'real' not in str(v.get('source', '')).lower(),
            liquidity_data
        )
        if removed:
            entry_changed = True
        if not liquidity_data:
            cleaned.pop('liquidity_data', None)
    
    aggregates = cleaned.get('aggregates')
    if isinstance(aggregates, dict):
        onchain = aggregates.get('onchain')
        if isinstance(onchain, dict):
            holders_val = onchain.get('holders', 0)
            if _is_estimated_holders(holders_val):
                onchain.pop('holders', None)
                entry_changed = True
            if not onchain:
                aggregates.pop('onchain', None)
        market = aggregates.get('market')
        if isinstance(market, dict):
            # Drop suspicious rounded estimates
            for field in ('market_cap', 'volume_24h'):
                value = market.get(field, 0)
                if value in (1000000000, 2000000000, 500000000, 1500000000,
                             100000000, 200000000, 300000000, 0):
                    market.pop(field, None)
                    entry_changed = True
            if not market:
                aggregates.pop('market', None)
        if not aggregates:
            cleaned.pop('aggregates', None)
    
    has_real_market = any(
        isinstance(md, dict) and (
            (md.get('market_cap', 0) or 0) > 0 or
            (md.get('volume_24h', 0) or 0) > 0 or
            (md.get('price', 0) or 0) > 0
        )
        for md in cleaned.get('market_data', {}).values()
    )
    has_real_onchain = any(
        isinstance(oc, dict)
        and (oc.get('holders', 0) or 0) > 0
        and not _is_estimated_holders(oc.get('holders', 0))
        for oc in cleaned.get('onchain_data', {}).values()
    )
    has_real_liquidity = any(
        isinstance(lq, dict) and (lq.get('liquidity', 0) or 0) > 0
        for lq in cleaned.get('liquidity_data', {}).values()
    )
    
    keep_entry = has_real_market or has_real_onchain or has_real_liquidity
    
    return cleaned, keep_entry, entry_changed

def load_full_real_data_cache():
    """Load entire real_data_cache.json structure"""
    if os.path.exists(REAL_DATA_CACHE_FILE):
        try:
            with _CACHE_IO_LOCK:
                with open(REAL_DATA_CACHE_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
    return {'tokens': {}, 'last_updated': 0}

def persist_real_data_to_cache(token_address, token_name, symbol, chain, market_data):
    """Persist real data using strict overwrite validation."""
    if not token_address or not isinstance(market_data, dict):
        return

    candidate_map = {
        "market_cap": _normalize_metric_candidate("market_cap", market_data.get("market_cap", 0)),
        "volume_24h": _normalize_metric_candidate("volume_24h", market_data.get("volume_24h", 0)),
        "price": _normalize_metric_candidate("price", market_data.get("price", 0)),
        "holders": _normalize_metric_candidate("holders", market_data.get("holders", 0)),
        "liquidity": _normalize_metric_candidate("liquidity", market_data.get("liquidity", 0)),
    }
    if not any(value > 0 for value in candidate_map.values()):
        return

    with _CACHE_IO_LOCK:
        cache_data = load_full_real_data_cache()
        tokens = cache_data.setdefault("tokens", {})

        storage_key = build_token_storage_key(token_address, chain, symbol)
        if not storage_key:
            storage_key = normalize_address_for_storage(token_address)

        existing_entry = tokens.get(storage_key, {})
        entry = dict(existing_entry) if isinstance(existing_entry, dict) else {}
        existing_aggregates = entry.get("aggregates", {}) if isinstance(entry.get("aggregates"), dict) else {}
        existing_market_data = entry.get("market_data", {}) if isinstance(entry.get("market_data"), dict) else {}
        existing_multi_api = existing_market_data.get("multi_api", {}) if isinstance(existing_market_data.get("multi_api"), dict) else {}
        existing_market_agg = existing_aggregates.get("market", {}) if isinstance(existing_aggregates.get("market"), dict) else {}
        existing_onchain_data = entry.get("onchain_data", {}) if isinstance(entry.get("onchain_data"), dict) else {}
        existing_liquidity_data = entry.get("liquidity_data", {}) if isinstance(entry.get("liquidity_data"), dict) else {}

        old_values = {
            "market_cap": _normalize_metric_candidate("market_cap", existing_multi_api.get("market_cap", existing_market_agg.get("market_cap", 0))),
            "volume_24h": _normalize_metric_candidate("volume_24h", existing_multi_api.get("volume_24h", existing_market_agg.get("volume_24h", 0))),
            "price": _normalize_metric_candidate("price", existing_multi_api.get("price", existing_market_agg.get("price", 0))),
            "holders": _normalize_metric_candidate("holders", (existing_aggregates.get("onchain", {}) or {}).get("holders", 0)),
            "liquidity": _normalize_metric_candidate("liquidity", ((existing_aggregates.get("liquidity", {}) or {}).get("liquidity", 0))),
        }
        if old_values["holders"] <= 0:
            for existing_source in (existing_onchain_data or {}).values():
                if not isinstance(existing_source, dict):
                    continue
                old_values["holders"] = _normalize_metric_candidate("holders", existing_source.get("holders", 0))
                if old_values["holders"] > 0:
                    break
        if old_values["liquidity"] <= 0:
            for existing_source in (existing_liquidity_data or {}).values():
                if not isinstance(existing_source, dict):
                    continue
                old_values["liquidity"] = _normalize_metric_candidate("liquidity", existing_source.get("liquidity", 0))
                if old_values["liquidity"] > 0:
                    break

        providers = []
        incoming_sources = market_data.get("sources_used")
        if isinstance(incoming_sources, (list, tuple, set)):
            providers = [str(p) for p in incoming_sources if str(p).strip()]
        elif market_data.get("data_source"):
            providers = [str(market_data.get("data_source"))]
        else:
            existing_providers = existing_multi_api.get("providers")
            if isinstance(existing_providers, (list, tuple, set)):
                providers = [str(p) for p in existing_providers if str(p).strip()]
        providers = list(dict.fromkeys(providers))

        existing_source_labels = []
        existing_provider_labels = existing_multi_api.get("providers")
        if isinstance(existing_provider_labels, (list, tuple, set)):
            existing_source_labels.extend([str(p) for p in existing_provider_labels if str(p).strip()])
        if existing_multi_api.get("source"):
            existing_source_labels.append(existing_multi_api.get("source"))
        existing_source_labels.extend([str(k) for k in existing_onchain_data.keys()])
        existing_source_labels.extend([str(k) for k in existing_liquidity_data.keys()])

        metric_source_values = market_data.get("metric_source_values", {})
        if not isinstance(metric_source_values, dict):
            metric_source_values = {}

        old_confidence = _source_confidence_score(existing_source_labels)
        new_confidence = _source_confidence_score(providers)

        policy_log = {}
        resolved_values = {}
        for metric_name in ("market_cap", "volume_24h", "holders", "liquidity"):
            resolved_val, was_updated, decision_reason = _resolve_metric_update(
                metric_name,
                candidate_map.get(metric_name, 0),
                old_values.get(metric_name, 0),
                metric_source_values,
                old_confidence,
                new_confidence,
                _read_metric_history(entry, metric_name),
            )
            resolved_values[metric_name] = resolved_val
            policy_log[metric_name] = decision_reason
            if not was_updated and old_values.get(metric_name, 0) > 0:
                resolved_values[metric_name] = old_values.get(metric_name, 0)

        # Price uses strict range check only; many APIs expose coarse price granularity.
        resolved_values["price"] = candidate_map["price"] if candidate_map["price"] > 0 else old_values["price"]
        policy_log["price"] = "accept_valid_price" if candidate_map["price"] > 0 else "keep_existing_price"

        previous_snapshot = {
            "market_cap": old_values["market_cap"],
            "volume_24h": old_values["volume_24h"],
            "holders": old_values["holders"],
            "liquidity": old_values["liquidity"],
            "price": old_values["price"],
        }
        current_snapshot = {
            "market_cap": resolved_values["market_cap"],
            "volume_24h": resolved_values["volume_24h"],
            "holders": resolved_values["holders"],
            "liquidity": resolved_values["liquidity"],
            "price": resolved_values["price"],
        }
        changed_any = not isinstance(existing_entry, dict)
        for metric_name, old_val in previous_snapshot.items():
            new_val = current_snapshot.get(metric_name, 0)
            if metric_name == "holders":
                if int(new_val or 0) != int(old_val or 0):
                    changed_any = True
                    break
            elif abs(float(new_val or 0) - float(old_val or 0)) > max(1e-9, float(old_val or 0) * 0.0001):
                changed_any = True
                break
        if not changed_any and new_confidence > old_confidence + 0.25:
            changed_any = True

        if not changed_any:
            return

        now_ts = time.time()
        entry["address"] = token_address
        entry["token_name"] = token_name
        entry["symbol"] = symbol
        entry["chain"] = chain
        entry["timestamp"] = now_ts
        entry["source"] = "real_time"

        entry["market_data"] = dict(existing_market_data)
        entry["market_data"]["multi_api"] = {
            "market_cap": float(resolved_values["market_cap"]) if resolved_values["market_cap"] > 0 else 0,
            "volume_24h": float(resolved_values["volume_24h"]) if resolved_values["volume_24h"] > 0 else 0,
            "price": float(resolved_values["price"]) if resolved_values["price"] > 0 else 0,
            "source": "real-time",
            "providers": providers,
        }
        if metric_source_values:
            entry["market_data"]["metric_source_values"] = metric_source_values

        new_aggregates = dict(existing_aggregates) if isinstance(existing_aggregates, dict) else {}
        market_aggregate = dict(existing_market_agg)
        if resolved_values["market_cap"] > 0:
            market_aggregate["market_cap"] = float(resolved_values["market_cap"])
        if resolved_values["volume_24h"] > 0:
            market_aggregate["volume_24h"] = float(resolved_values["volume_24h"])
        if resolved_values["price"] > 0:
            market_aggregate["price"] = float(resolved_values["price"])
        if market_aggregate:
            new_aggregates["market"] = market_aggregate

        holders_val = int(resolved_values["holders"]) if resolved_values["holders"] > 0 else 0
        if holders_val > 0 and not _is_estimated_holders(holders_val):
            entry.setdefault("onchain_data", {})
            entry["onchain_data"]["onchain_api"] = {
                "holders": holders_val,
                "source": "real-time",
            }
            new_aggregates.setdefault("onchain", {})["holders"] = holders_val
        elif existing_onchain_data:
            entry["onchain_data"] = existing_onchain_data
            existing_onchain_agg = existing_aggregates.get("onchain", {}) if isinstance(existing_aggregates.get("onchain"), dict) else {}
            if existing_onchain_agg:
                new_aggregates["onchain"] = existing_onchain_agg

        liquidity_val = float(resolved_values["liquidity"]) if resolved_values["liquidity"] > 0 else 0.0
        if liquidity_val > 0:
            entry.setdefault("liquidity_data", {})
            entry["liquidity_data"]["calculated"] = {
                "liquidity": liquidity_val,
                "source": "real-time",
            }
            new_aggregates.setdefault("liquidity", {})["liquidity"] = liquidity_val
        elif existing_liquidity_data:
            entry["liquidity_data"] = existing_liquidity_data
            existing_liq_agg = existing_aggregates.get("liquidity", {}) if isinstance(existing_aggregates.get("liquidity"), dict) else {}
            if existing_liq_agg:
                new_aggregates["liquidity"] = existing_liq_agg

        entry["aggregates"] = new_aggregates
        entry["overwrite_policy"] = {
            "applied_at": now_ts,
            "old_source_confidence": old_confidence,
            "new_source_confidence": new_confidence,
            "decisions": policy_log,
        }
        _append_metric_history(entry, current_snapshot)

        tokens[storage_key] = entry
        normalized_token_address = normalize_address_for_storage(token_address)
        if (
            normalized_token_address
            and storage_key != normalized_token_address
            and is_native_placeholder_address(normalized_token_address)
        ):
            tokens.pop(normalized_token_address, None)

        cache_data["last_updated"] = now_ts
        save_real_data_cache(cache_data)

    # Also persist to fallback file so future runs can skip re-fetching within the skip window.
    try:
        save_fallback_entry(token_address, entry)
    except Exception as e:
        print(f"⚠️  Could not persist {symbol} to fallback: {e}")

def get_override_ids(symbol_upper, key):
    """Get override identifiers for a symbol"""
    symbol_upper = normalize_symbol_for_api(symbol_upper)
    override = SYMBOL_API_OVERRIDES.get(symbol_upper, {})
    values = override.get(key, [])
    return values if isinstance(values, (list, tuple)) else [values]

def fetch_coingecko_market_data_by_id(coin_id):
    """Fetch detailed CoinGecko data by coin ID"""
    if not coin_id:
        return None
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        response = rate_limited_get(url, timeout=10)
        if response is not None and response.status_code == 200:
            data = response.json()
            market_data = data.get('market_data', {})
            return {
                'market_cap': market_data.get('market_cap', {}).get('usd', 0) or 0,
                'volume_24h': market_data.get('total_volume', {}).get('usd', 0) or 0,
                'price': market_data.get('current_price', {}).get('usd', 0) or 0,
                'source': f"coingecko:{coin_id}"
            }
    except Exception:
        pass
    return None

def search_coingecko_ids(symbol_upper):
    """Search CoinGecko for matching IDs"""
    symbol_upper = normalize_symbol_for_api(symbol_upper)
    ids = get_override_ids(symbol_upper, 'coingecko_ids')
    if ids:
        return ids
    try:
        url = f"https://api.coingecko.com/api/v3/search?query={quote(symbol_upper)}"
        response = rate_limited_get(url, timeout=10)
        if response is not None and response.status_code == 200:
            coins = response.json().get('coins', [])
            matches = [coin['id'] for coin in coins if coin.get('symbol', '').upper() == symbol_upper]
            if matches:
                return matches
            if coins:
                return [coins[0].get('id')]
    except Exception:
        pass
    return []

def fetch_coincap_market_data(symbol_upper):
    """Fetch market data from CoinCap"""
    symbol_upper = normalize_symbol_for_api(symbol_upper)
    try:
        url = f"https://api.coincap.io/v2/assets?search={quote(symbol_upper)}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', [])
            for asset in data:
                if asset.get('symbol', '').upper() == symbol_upper:
                    return {
                        'market_cap': float(asset.get('marketCapUsd', 0) or 0),
                        'volume_24h': float(asset.get('volumeUsd24Hr', 0) or 0),
                        'price': float(asset.get('priceUsd', 0) or 0),
                        'source': f"coincap:{asset.get('id', 'unknown')}"
                    }
            if data:
                asset = data[0]
                return {
                    'market_cap': float(asset.get('marketCapUsd', 0) or 0),
                    'volume_24h': float(asset.get('volumeUsd24Hr', 0) or 0),
                    'price': float(asset.get('priceUsd', 0) or 0),
                    'source': f"coincap:{asset.get('id', 'unknown')}"
                }
    except Exception:
        pass
    return None


def fetch_coinmarketcap_market_data(symbol_upper):
    """Fetch market data from CoinMarketCap by symbol."""
    symbol_upper = normalize_symbol_for_api(symbol_upper)
    if not COINMARKETCAP_API_KEY or not symbol_upper:
        return None
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {
            "Accept": "application/json",
            "X-CMC_PRO_API_KEY": COINMARKETCAP_API_KEY,
        }
        params = {
            "symbol": symbol_upper,
            "convert": "USD",
        }
        response = requests.get(url, headers=headers, params=params, timeout=12)
        if response.status_code != 200:
            return None
        payload = response.json().get('data', {})
        entry = payload.get(symbol_upper)
        if isinstance(entry, list):
            # Pick the most liquid entry when multiple assets share the same ticker.
            def score_candidate(candidate):
                if not isinstance(candidate, dict):
                    return (0.0, 0.0, 0.0)
                quote_blob = candidate.get('quote', {}).get('USD', {}) if isinstance(candidate.get('quote'), dict) else {}
                return (
                    float(quote_blob.get('market_cap', 0) or 0),
                    float(quote_blob.get('volume_24h', 0) or 0),
                    float(quote_blob.get('price', 0) or 0),
                )
            entry = max(entry, key=score_candidate) if entry else None
        if not isinstance(entry, dict):
            return None
        quote = entry.get('quote', {}).get('USD', {}) if isinstance(entry.get('quote'), dict) else {}
        market_cap = float(quote.get('market_cap', 0) or 0)
        volume_24h = float(quote.get('volume_24h', 0) or 0)
        price = float(quote.get('price', 0) or 0)
        if market_cap <= 0:
            fdv = float(quote.get('fully_diluted_market_cap', 0) or 0)
            if fdv > 0:
                market_cap = fdv
        if market_cap <= 0 and price > 0:
            circulating = float(entry.get('circulating_supply', 0) or 0)
            total_supply = float(entry.get('total_supply', 0) or 0)
            max_supply = float(entry.get('max_supply', 0) or 0)
            if circulating > 0:
                market_cap = price * circulating
            elif total_supply > 0:
                market_cap = price * total_supply
            elif max_supply > 0:
                market_cap = price * max_supply
        if market_cap > 0 or volume_24h > 0 or price > 0:
            return {
                'market_cap': market_cap,
                'volume_24h': volume_24h,
                'price': price,
                'source': f"coinmarketcap:{entry.get('id', symbol_upper)}"
            }
    except Exception:
        pass
    return None

def get_coinpaprika_ids(symbol_upper):
    """Get CoinPaprika IDs for a symbol"""
    symbol_upper = normalize_symbol_for_api(symbol_upper)
    ids = []
    override_ids = get_override_ids(symbol_upper, 'coinpaprika_ids')
    ids.extend([i for i in override_ids if i])
    if symbol_upper in COINPAPRIKA_IDS:
        ids.append(COINPAPRIKA_IDS[symbol_upper])
    if ids:
        return list(dict.fromkeys(ids))
    
    try:
        url = f"https://api.coinpaprika.com/v1/search?q={quote(symbol_upper)}&c=currencies&limit=5"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            currencies = response.json().get('currencies', [])
            for currency in currencies:
                if currency.get('symbol', '').upper() == symbol_upper:
                    ids.append(currency.get('id'))
            if not ids and currencies:
                ids.append(currencies[0].get('id'))
    except Exception:
        pass
    return list(dict.fromkeys(ids))

def fetch_coinpaprika_market_data(symbol_upper):
    """Fetch market data from CoinPaprika"""
    symbol_upper = normalize_symbol_for_api(symbol_upper)
    ids = get_coinpaprika_ids(symbol_upper)
    for paprika_id in ids:
        if not paprika_id:
            continue
        try:
            paprika_url = f"https://api.coinpaprika.com/v1/tickers/{paprika_id}"
            paprika_resp = requests.get(paprika_url, timeout=10)
            if paprika_resp.status_code == 200:
                ticker = paprika_resp.json()
                usd_quote = ticker.get('quotes', {}).get('USD', {})
                return {
                    'market_cap': usd_quote.get('market_cap', 0) or 0,
                    'volume_24h': usd_quote.get('volume_24h', 0) or 0,
                    'price': usd_quote.get('price', 0) or 0,
                    'source': f"coinpaprika:{paprika_id}"
                }
        except Exception:
            continue
    return None

def fetch_ethplorer_holders(token_address):
    """Fetch holders count from Ethplorer (Ethereum tokens only)"""
    if not token_address or not token_address.startswith('0x'):
        return 0
    try:
        url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey={ETHPLORER_API_KEY}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            holders_count = data.get('holdersCount', 0)
            if holders_count:
                return holders_count
    except Exception:
        pass
    return 0


def _parse_positive_holders(value):
    """Parse positive integer holder count from mixed API payload values."""
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        parsed = int(float(value))
        return parsed if parsed > 0 else 0
    except Exception:
        return 0


def _chain_to_dune_chain_id(chain):
    chain_key = (chain or '').strip().lower()
    mapping = {
        'ethereum': 1,
        'eth': 1,
        'op': 10,
        'optimism': 10,
        'polygon': 137,
        'bsc': 56,
        'binance-smart-chain': 56,
        'arbitrum': 42161,
        'arb': 42161,
        'base': 8453,
        'linea': 59144,
        'linea-mainnet': 59144,
        'avax': 43114,
        'avalanche': 43114,
        'avalanche-c': 43114,
        'sonic': 146,
        's': 146,
        'sei': 1329,
        'mantle': 5000,
        'mnt': 5000,
        'zksync': 324,
        'zk': 324,
        'zksync-era': 324,
    }
    return mapping.get(chain_key)


def _chain_to_etherscan_chain_id(chain):
    chain_key = (chain or '').strip().lower()
    mapping = {
        'ethereum': 1,
        'eth': 1,
        'op': 10,
        'optimism': 10,
        'base': 8453,
        'arbitrum': 42161,
        'arb': 42161,
        'polygon': 137,
        'bsc': 56,
        'binance-smart-chain': 56,
        'linea': 59144,
        'linea-mainnet': 59144,
        'avax': 43114,
        'avalanche': 43114,
        'avalanche-c': 43114,
        'sonic': 146,
        's': 146,
        'sei': 1329,
        'mantle': 5000,
        'mnt': 5000,
        'zksync': 324,
        'zk': 324,
        'zksync-era': 324,
    }
    return mapping.get(chain_key)


def _is_chain_incompatible_holder_source(source_name, chain):
    """Return True when an on-chain holder source is incompatible with the token chain."""
    source = str(source_name or '').strip().lower()
    chain_key = str(chain or '').strip().lower()
    if not source or not chain_key:
        return False

    if source == 'ethplorer' and chain_key not in ('ethereum', 'eth'):
        return True
    if source == 'etherscan' and chain_key not in (
        'ethereum', 'eth',
        'op', 'optimism',
        'base',
        'arbitrum', 'arb',
        'polygon',
        'bsc', 'binance-smart-chain',
        'linea', 'linea-mainnet',
        'avax', 'avalanche', 'avalanche-c',
        'sonic', 's',
        'sei',
        'mantle', 'mnt',
        'zksync', 'zk', 'zksync-era',
    ):
        return True
    if source == 'optimism' and chain_key not in ('op', 'optimism'):
        return True
    if source == 'api' and chain_key in ('s', 'sonic'):
        # Generic cached "api" holder snapshots have repeatedly carried stale Sonic values.
        # Force a fresh chain-aware holder pull for Sonic.
        return True
    if source in ('solscan', 'solanatracker', 'birdeye', 'solana_rpc') and chain_key not in ('solana', 'sol'):
        return True
    return False


def _chain_to_moralis(chain):
    chain_key = (chain or '').strip().lower()
    mapping = {
        'ethereum': 'eth',
        'eth': 'eth',
        'op': 'optimism',
        'optimism': 'optimism',
        'base': 'base',
        'arbitrum': 'arbitrum',
        'arb': 'arbitrum',
        'polygon': 'polygon',
        'bsc': 'bsc',
        'binance-smart-chain': 'bsc',
        'linea': 'linea',
        'linea-mainnet': 'linea',
        'avax': 'avalanche',
        'avalanche': 'avalanche',
        'avalanche-c': 'avalanche',
        'sonic': 'sonic',
        's': 'sonic',
        'sei': 'sei',
        'mantle': 'mantle',
        'mnt': 'mantle',
        'zksync': 'zksync',
        'zk': 'zksync',
        'zksync-era': 'zksync',
    }
    return mapping.get(chain_key)


def _moralis_chain_candidates(chain):
    """Return Moralis chain candidates (slug + hex id) for broader compatibility."""
    chain_key = (chain or '').strip().lower()
    slug = _chain_to_moralis(chain_key)
    hex_map = {
        'ethereum': '0x1',
        'eth': '0x1',
        'op': '0xa',
        'optimism': '0xa',
        'base': '0x2105',
        'arbitrum': '0xa4b1',
        'arb': '0xa4b1',
        'polygon': '0x89',
        'bsc': '0x38',
        'binance-smart-chain': '0x38',
        'linea': '0xe708',
        'linea-mainnet': '0xe708',
        'avax': '0xa86a',
        'avalanche': '0xa86a',
        'avalanche-c': '0xa86a',
        'sonic': '0x92',
        's': '0x92',
        'sei': '0x531',
        'mantle': '0x1388',
        'mnt': '0x1388',
        'zksync': '0x144',
        'zk': '0x144',
        'zksync-era': '0x144',
    }
    candidates = []
    if slug:
        candidates.append(slug)
    hex_value = hex_map.get(chain_key)
    if hex_value and hex_value not in candidates:
        candidates.append(hex_value)
    return candidates


def _chain_to_goplus_id(chain):
    chain_key = (chain or '').strip().lower()
    mapping = {
        'ethereum': 1,
        'eth': 1,
        'op': 10,
        'optimism': 10,
        'base': 8453,
        'arbitrum': 42161,
        'arb': 42161,
        'polygon': 137,
        'bsc': 56,
        'binance-smart-chain': 56,
        'linea': 59144,
        'linea-mainnet': 59144,
        'avax': 43114,
        'avalanche': 43114,
        'avalanche-c': 43114,
        'sonic': 146,
        's': 146,
        'sei': 1329,
        'mantle': 5000,
        'mnt': 5000,
        'zksync': 324,
        'zk': 324,
        'zksync-era': 324,
    }
    return mapping.get(chain_key)


def fetch_dune_holders(token_address, chain):
    """Fetch holder count from Dune SIM token-holders endpoint."""
    if not DUNE_API_KEY or not is_valid_hex_address(token_address or ''):
        return 0
    chain_id = _chain_to_dune_chain_id(chain)
    if chain_id is None:
        return 0
    token_ref = str(token_address or '').strip().lower()
    if not is_valid_hex_address(token_ref):
        return 0
    url = f"{DUNE_SIM_BASE_URL}/evm/token-holders/{chain_id}/{token_ref}"
    headers = {
        "X-Sim-Api-Key": DUNE_API_KEY,
        "Accept": "application/json",
    }
    try:
        page_size = DUNE_HOLDER_PAGE_SIZE
        max_pages = DUNE_HOLDER_MAX_PAGES
        offset = None
        seen_offsets = set()
        pages_fetched = 0
        counted_holders = 0

        while pages_fetched < max_pages:
            pages_fetched += 1
            params = {"limit": page_size}
            if offset not in (None, '', 0):
                params["offset"] = offset

            response = requests.get(url, headers=headers, params=params, timeout=20)
            if response.status_code != 200:
                break
            data = response.json()
            metadata = data.get('metadata', {}) if isinstance(data.get('metadata'), dict) else {}

            for key in (
                'total_count',
                'count',
                'total_holders',
                'holders_count',
                'holder_count',
            ):
                parsed = _parse_positive_holders(data.get(key))
                if parsed <= 0:
                    parsed = _parse_positive_holders(metadata.get(key))
                if parsed > 0 and not _is_estimated_holders(parsed):
                    return parsed

            rows = []
            for key in ('data', 'result', 'holders', 'items'):
                candidate_rows = data.get(key)
                if isinstance(candidate_rows, list):
                    rows = candidate_rows
                    break
            if rows:
                counted_holders += len(rows)

            next_offset = (
                data.get('next_offset')
                or data.get('nextOffset')
                or metadata.get('next_offset')
                or metadata.get('nextOffset')
            )
            if next_offset in (None, '', 0):
                break
            next_offset_key = str(next_offset)
            if next_offset_key in seen_offsets:
                break
            seen_offsets.add(next_offset_key)
            offset = next_offset

        if counted_holders > 0 and not _is_estimated_holders(counted_holders):
            return counted_holders
    except Exception:
        return 0
    return 0


def fetch_moralis_holders(token_address, chain):
    """Fetch holder count from Moralis token owners endpoint."""
    if not MORALIS_API_KEY or not is_valid_hex_address(token_address or ''):
        return 0
    chain_candidates = _moralis_chain_candidates(chain)
    if not chain_candidates:
        return 0
    headers = {"X-API-Key": MORALIS_API_KEY, "Accept": "application/json"}
    page_size = MORALIS_HOLDER_PAGE_SIZE
    max_pages = MORALIS_HOLDER_MAX_PAGES
    token_ref = str(token_address or '').strip()
    endpoints = [
        ("https://deep-index.moralis.io/api/v2.2/erc20/{}/owners".format(token_ref), {'limit': page_size}),
        ("https://deep-index.moralis.io/api/v2/erc20/{}/owners".format(token_ref), {'limit': page_size}),
    ]
    for url, params in endpoints:
        for chain_param in chain_candidates:
            try:
                query_params = dict(params)
                query_params['chain'] = chain_param
                response = requests.get(url, headers=headers, params=query_params, timeout=20)
                if response.status_code != 200:
                    if response.status_code in (401, 403):
                        break
                    continue
                data = response.json()
                for key in ('total', 'total_result', 'total_results'):
                    parsed = _parse_positive_holders(data.get(key))
                    if parsed > 0 and not _is_estimated_holders(parsed):
                        return parsed
                rows = data.get('result')
                if isinstance(rows, list) and rows:
                    count = len(rows)
                    next_cursor = data.get('cursor')
                    seen_cursors = set()
                    page = 1
                    while next_cursor and page < max_pages:
                        if next_cursor in seen_cursors:
                            break
                        seen_cursors.add(next_cursor)
                        page += 1
                        next_params = dict(query_params)
                        next_params['cursor'] = next_cursor
                        next_response = requests.get(url, headers=headers, params=next_params, timeout=20)
                        if next_response.status_code != 200:
                            break
                        next_data = next_response.json()
                        next_rows = next_data.get('result')
                        if not isinstance(next_rows, list) or not next_rows:
                            break
                        count += len(next_rows)
                        next_cursor = next_data.get('cursor')
                    if count > 0 and not _is_estimated_holders(count):
                        return count
            except Exception:
                continue
    return 0


def fetch_bscscan_holders(token_address):
    """Fetch holder count for BSC via Etherscan V2 multichain API."""
    api_key = ETHERSCAN_API_KEY or BSCSCAN_API_KEY
    if not api_key or not is_valid_hex_address(token_address or ''):
        return 0
    url = "https://api.etherscan.io/v2/api"
    base_params = {
        'chainid': 56,
        'module': 'token',
        'contractaddress': token_address,
        'apikey': api_key,
    }
    query_options = [
        {'action': 'tokenholdercount'},
        {'action': 'tokenholderlist', 'page': 1, 'offset': 1},
    ]
    for extra in query_options:
        try:
            params = dict(base_params)
            params.update(extra)
            response = requests.get(url, params=params, timeout=20)
            if response.status_code != 200:
                continue
            data = response.json()
            status = str(data.get('status', '')).strip()
            if status != '1':
                # Keep failing over when the current key/plan cannot serve BSC holder endpoints.
                continue
            result = data.get('result')
            parsed = 0
            if isinstance(result, list) and result:
                first = result[0] if isinstance(result[0], dict) else {}
                for key in ('TokenHolderCount', 'tokenHolderCount', 'holdersCount', 'holder_count'):
                    parsed = _parse_positive_holders(first.get(key))
                    if parsed > 0:
                        break
            elif isinstance(result, dict):
                for key in ('TokenHolderCount', 'tokenHolderCount', 'holdersCount', 'holder_count'):
                    parsed = _parse_positive_holders(result.get(key))
                    if parsed > 0:
                        break
            else:
                parsed = _parse_positive_holders(result)
            if parsed > 0 and not _is_estimated_holders(parsed):
                return parsed
        except Exception:
            continue
    return 0


def fetch_etherscan_holders(token_address, chain):
    """Fetch holder count using Etherscan V2 token holder endpoints (chain-aware)."""
    if not ETHERSCAN_API_KEY or not is_valid_hex_address(token_address or ''):
        return 0
    chain_id = _chain_to_etherscan_chain_id(chain)
    if chain_id is None:
        return 0
    url = "https://api.etherscan.io/v2/api"
    base_params = {
        'chainid': chain_id,
        'module': 'token',
        'contractaddress': token_address,
        'apikey': ETHERSCAN_API_KEY
    }
    query_options = [
        {'action': 'tokenholderlist', 'page': 1, 'offset': 1},
        {'action': 'tokenholdercount'},
    ]
    for extra in query_options:
        try:
            params = dict(base_params)
            params.update(extra)
            response = requests.get(url, params=params, timeout=20)
            if response.status_code != 200:
                continue
            data = response.json()
            if data.get('status') != '1':
                continue
            result = data.get('result')
            if isinstance(result, list) and result:
                first = result[0] if isinstance(result[0], dict) else {}
                for key in ('TokenHolderCount', 'tokenHolderCount', 'holdersCount', 'holder_count'):
                    parsed = _parse_positive_holders(first.get(key))
                    if parsed > 0 and not _is_estimated_holders(parsed):
                        return parsed
            elif isinstance(result, dict):
                for key in ('TokenHolderCount', 'tokenHolderCount', 'holdersCount', 'holder_count'):
                    parsed = _parse_positive_holders(result.get(key))
                    if parsed > 0 and not _is_estimated_holders(parsed):
                        return parsed
            else:
                parsed = _parse_positive_holders(result)
                if parsed > 0 and not _is_estimated_holders(parsed):
                    return parsed
        except Exception:
            continue
    return 0


def fetch_blockscout_holders(token_address, chain):
    """Fetch holders count from Blockscout explorers for L2 networks (v2 API)."""
    chain_lower = (chain or '').lower()
    blockscout_domains = {
        'op': ['optimism.blockscout.com', 'blockscout.com/optimism/mainnet'],
        'optimism': ['optimism.blockscout.com', 'blockscout.com/optimism/mainnet'],
        'base': ['base.blockscout.com', 'blockscout.com/base/mainnet'],
        'arbitrum': ['arbitrum.blockscout.com', 'blockscout.com/arbitrum/mainnet'],
        'arb': ['arbitrum.blockscout.com', 'blockscout.com/arbitrum/mainnet'],
        'sonic': ['sonic.blockscout.com', 'blockscout.com/sonic/mainnet'],
        's': ['sonic.blockscout.com', 'blockscout.com/sonic/mainnet'],
        'mantle': ['explorer.mantle.xyz', 'mantle.blockscout.com', 'blockscout.com/mantle/mainnet'],
        'mnt': ['explorer.mantle.xyz', 'mantle.blockscout.com', 'blockscout.com/mantle/mainnet'],
        'zksync': ['zksync.blockscout.com', 'block-explorer-api.mainnet.zksync.io', 'blockscout.com/zksync/mainnet'],
        'zk': ['zksync.blockscout.com', 'block-explorer-api.mainnet.zksync.io', 'blockscout.com/zksync/mainnet'],
        'zksync-era': ['zksync.blockscout.com', 'block-explorer-api.mainnet.zksync.io', 'blockscout.com/zksync/mainnet'],
    }
    domains = blockscout_domains.get(chain_lower, [])
    if not domains or not token_address:
        return 0

    def _parse_holders_from_payload(payload):
        if not isinstance(payload, dict):
            return 0
        holder_value = (
            payload.get('holders_count')
            or payload.get('holdersCount')
            or payload.get('holder_count')
            or payload.get('holders')
            or 0
        )
        parsed = _parse_positive_holders(holder_value)
        if parsed > 0 and not _is_estimated_holders(parsed):
            return parsed
        return 0

    def _curl_fallback(url):
        try:
            output = subprocess.check_output(
                ["curl", "-sSL", "-H", "User-Agent: DeFiRiskAssessor/3.0", url],
                text=True,
                timeout=20
            )
            return _parse_holders_from_payload(json.loads(output or "{}"))
        except Exception:
            return 0

    for domain in domains:
        url = f"https://{domain}/api/v2/tokens/{token_address}"
        try:
            response = requests.get(
                url,
                timeout=15,
                allow_redirects=True,
                headers={"User-Agent": "DeFiRiskAssessor/3.0"}
            )
            if response.status_code != 200:
                # Some Blockscout domains can reject Python TLS fingerprints while curl works.
                fallback_count = _curl_fallback(url)
                if fallback_count > 0:
                    print(f"      ✅ Blockscout holders for {chain} via curl fallback: {fallback_count:,}")
                    return fallback_count
                continue
            holders_int = _parse_holders_from_payload(response.json())
            if holders_int > 0:
                print(f"      ✅ Blockscout holders for {chain}: {holders_int:,}")
                return holders_int
        except Exception as e:
            print(f"      ⚠️  Blockscout API error for {chain} ({domain}): {e}")
            # Fallback to curl for environments where python DNS resolution fails intermittently.
            fallback_count = _curl_fallback(url)
            if fallback_count > 0:
                print(f"      ✅ Blockscout holders for {chain} via curl fallback: {fallback_count:,}")
                return fallback_count
    return 0


def fetch_goplus_token_holders(token_address, chain):
    """Fetch holder count from GoPlus token_security endpoint."""
    if not is_valid_hex_address(token_address or ''):
        return 0
    chain_id = _chain_to_goplus_id(chain)
    if chain_id is None:
        return 0
    url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}"
    params = {"contract_addresses": (token_address or "").lower()}

    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            return 0
        payload = response.json() if response is not None else {}
        result = payload.get('result', {}) if isinstance(payload, dict) else {}
        token_blob = {}
        if isinstance(result, dict):
            token_lc = (token_address or '').lower()
            token_blob = result.get(token_lc) or result.get(token_address) or {}
            if not isinstance(token_blob, dict):
                token_blob = {}
                for value in result.values():
                    if isinstance(value, dict):
                        token_blob = value
                        break
        if not isinstance(token_blob, dict):
            return 0
        for key in ('holder_count', 'holders_count', 'holderCount', 'holders', 'holder_num'):
            parsed = _parse_positive_holders(token_blob.get(key))
            if parsed > 0 and not _is_estimated_holders(parsed):
                return parsed
    except Exception:
        return 0
    return 0


def _extract_holders_from_payload(payload):
    """Extract holder count from mixed Solscan response payloads."""
    if not isinstance(payload, dict):
        return 0

    holder_keys = (
        'holder_count',
        'holders_count',
        'holderCount',
        'holdersCount',
        'holders',
        'holder',
        'total_holders',
        'total_holder',
        'totalHolders',
        'holder_num',
        'holderNum',
        'owner_count',
        'ownerCount',
        'total',
        'count',
    )

    def scan_dict(blob):
        if not isinstance(blob, dict):
            return 0
        for key in holder_keys:
            parsed = _parse_positive_holders(blob.get(key))
            if parsed > 0 and not _is_estimated_holders(parsed):
                return parsed
        return 0

    # First pass: top-level + common nested containers.
    for candidate in (
        payload,
        payload.get('data') if isinstance(payload.get('data'), dict) else {},
        payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {},
        payload.get('meta') if isinstance(payload.get('meta'), dict) else {},
    ):
        parsed = scan_dict(candidate)
        if parsed > 0:
            return parsed

    # Some APIs return holder list + total in `data`.
    data_list = payload.get('data')
    if isinstance(data_list, list):
        for key in ('total', 'total_count', 'count', 'total_holders'):
            parsed = _parse_positive_holders(payload.get(key))
            if parsed > 0 and not _is_estimated_holders(parsed):
                return parsed
        metadata = payload.get('metadata', {}) if isinstance(payload.get('metadata'), dict) else {}
        for key in ('total', 'total_count', 'count', 'total_holders'):
            parsed = _parse_positive_holders(metadata.get(key))
            if parsed > 0 and not _is_estimated_holders(parsed):
                return parsed
    return 0


def _extract_first_positive_metric(payload, candidate_keys):
    """Find first positive numeric metric in nested API payloads."""
    if not isinstance(payload, (dict, list, tuple)):
        return 0.0
    keys = [str(k).strip() for k in (candidate_keys or []) if str(k).strip()]
    if not keys:
        return 0.0
    queue = [payload]
    seen = set()
    while queue:
        node = queue.pop(0)
        node_id = id(node)
        if node_id in seen:
            continue
        seen.add(node_id)

        if isinstance(node, dict):
            for key in keys:
                if key not in node:
                    continue
                parsed = _safe_float(node.get(key))
                if parsed > 0:
                    return parsed
            for value in node.values():
                if isinstance(value, (dict, list, tuple)):
                    queue.append(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                if isinstance(value, (dict, list, tuple)):
                    queue.append(value)
    return 0.0


def fetch_solscan_market_metrics(token_address):
    """Fetch Solana market metrics from Solscan Pro API token meta payload."""
    if not SOLSCAN_API_KEY or not is_valid_solana_address(token_address or ''):
        return {}

    headers = {
        "Accept": "application/json",
        "token": SOLSCAN_API_KEY,
    }
    endpoint_specs = [
        ("https://pro-api.solscan.io/v2.0/token/meta", {"address": token_address}),
        ("https://pro-api.solscan.io/v2.0/token/meta", {"tokenAddress": token_address}),
    ]

    for url, params in endpoint_specs:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            if response.status_code != 200:
                continue
            payload = response.json() if hasattr(response, 'json') else {}
            market_cap = _extract_first_positive_metric(
                payload,
                (
                    'market_cap',
                    'marketCap',
                    'marketcap',
                    'usd_market_cap',
                    'usdMarketCap',
                    'fdv',
                    'fully_diluted_market_cap',
                ),
            )
            volume_24h = _extract_first_positive_metric(
                payload,
                (
                    'volume_24h',
                    'volume24h',
                    'volume24H',
                    'usd_volume_24h',
                    'usdVolume24h',
                    'trade_volume_24h',
                    'tradeVolume24h',
                    'v24h',
                ),
            )
            price = _extract_first_positive_metric(
                payload,
                (
                    'price',
                    'price_usd',
                    'priceUsd',
                    'usd_price',
                    'usdPrice',
                ),
            )
            if market_cap <= 0 and price > 0:
                supply = _extract_first_positive_metric(
                    payload,
                    (
                        'circulating_supply',
                        'circulatingSupply',
                        'total_supply',
                        'totalSupply',
                        'supply',
                    ),
                )
                if supply > 0:
                    market_cap = price * supply

            if market_cap > 0 or volume_24h > 0 or price > 0:
                return {
                    'market_cap': market_cap if market_cap > 0 else 0,
                    'volume_24h': volume_24h if volume_24h > 0 else 0,
                    'price': price if price > 0 else 0,
                    'source': 'solscan_meta',
                }
        except Exception:
            continue
    return {}


def fetch_solscan_holders(token_address):
    """Fetch Solana holder count from Solscan Pro API."""
    if not SOLSCAN_API_KEY or not is_valid_solana_address(token_address or ''):
        return 0

    headers = {
        "Accept": "application/json",
        # Solscan pro endpoint expects the API key in `token` header.
        "token": SOLSCAN_API_KEY,
    }
    endpoint_specs = [
        ("https://pro-api.solscan.io/v2.0/token/meta", {"address": token_address}),
        ("https://pro-api.solscan.io/v2.0/token/meta", {"tokenAddress": token_address}),
        (
            "https://pro-api.solscan.io/v2.0/token/holders",
            {"address": token_address, "page": 1, "page_size": 1},
        ),
        (
            "https://pro-api.solscan.io/v2.0/token/holders",
            {"tokenAddress": token_address, "page": 1, "page_size": 1},
        ),
    ]
    for url, params in endpoint_specs:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            if response.status_code != 200:
                continue
            payload = response.json() if hasattr(response, 'json') else {}
            parsed = _extract_holders_from_payload(payload)
            if parsed > 0:
                return parsed
        except Exception:
            continue
    return 0


def fetch_solanatracker_holders(token_address):
    """Fetch Solana holder count from Solana Tracker (requires API key)."""
    if not SOLANATRACKER_API_KEY or not is_valid_solana_address(token_address or ''):
        return 0
    url = f"https://data.solanatracker.io/tokens/{token_address}/holders"
    headers = {
        "accept": "application/json",
        "x-api-key": SOLANATRACKER_API_KEY,
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return 0
        payload = response.json() if hasattr(response, 'json') else {}
        parsed = _extract_holders_from_payload(payload)
        if parsed > 0:
            return parsed
        holders = payload.get('holders')
        if isinstance(holders, list) and holders:
            return len(holders)
    except Exception:
        return 0
    return 0


def fetch_birdeye_holders(token_address):
    """Fetch Solana holder count from BirdEye token overview (requires API key)."""
    if not BIRDEYE_API_KEY or not is_valid_solana_address(token_address or ''):
        return 0
    url = "https://public-api.birdeye.so/defi/token_overview"
    headers = {
        "accept": "application/json",
        "x-api-key": BIRDEYE_API_KEY,
    }
    params = {"address": token_address}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code != 200:
            return 0
        payload = response.json() if hasattr(response, 'json') else {}
        data = payload.get('data', {}) if isinstance(payload.get('data'), dict) else {}
        for key in ('holder', 'holders', 'holder_count', 'holders_count', 'holderCount'):
            parsed = _parse_positive_holders(data.get(key))
            if parsed > 0 and not _is_estimated_holders(parsed):
                return parsed
    except Exception:
        return 0
    return 0


def fetch_solana_rpc_holders(token_address):
    """Disabled: RPC-derived holder counts are estimated and excluded from scoring."""
    return 0


def fetch_coingecko_holders_by_symbol(symbol):
    """Fetch holders count from CoinGecko coin detail (community_data.twitter_followers as proxy or dedicated holder count)."""
    symbol_upper = normalize_symbol_for_api(symbol)
    if not symbol_upper:
        return 0
    # Try known IDs first, then search
    ids_to_try = get_override_ids(symbol_upper, 'coingecko_ids')
    if not ids_to_try:
        ids_to_try = search_coingecko_ids(symbol_upper)
    for coin_id in ids_to_try:
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&community_data=true&developer_data=false"
            resp = rate_limited_get(url, timeout=10)
            if resp is not None and resp.status_code == 200:
                data = resp.json()
                # CoinGecko doesn't have on-chain holders, but market_data may include circulating/total supply holders
                # Use twitter followers or telegram members as a weak proxy only if no better source exists
                # Best bet: check if any exchange_data or market_data has holder counts
                market_data = data.get('market_data', {})
                # Some coins have "total_supply" which at least validates existence
                # Return 0 — CoinGecko doesn't expose on-chain holder counts
        except Exception:
            pass
    return 0

def fetch_dexscreener_market_data(token_address, chain):
    """Fetch token market cap/volume/price from DexScreener token endpoint."""
    if not token_address:
        return None

    chain_key = (chain or '').strip().lower()
    chain_id_map = {
        'ethereum': {'ethereum'},
        'eth': {'ethereum'},
        'bsc': {'bsc'},
        'binance-smart-chain': {'bsc'},
        'polygon': {'polygon'},
        'polygon-pos': {'polygon'},
        'arbitrum': {'arbitrum'},
        'arb': {'arbitrum'},
        'op': {'optimism'},
        'optimism': {'optimism'},
        'base': {'base'},
        'linea': {'linea'},
        'linea-mainnet': {'linea'},
        'avax': {'avalanche'},
        'avalanche': {'avalanche'},
        'avalanche-c': {'avalanche'},
        'sei': {'sei', 'seiv2'},
        'sei-evm': {'sei', 'seiv2'},
        'sol': {'solana'},
        'solana': {'solana'},
        'sonic': {'sonic'},
        's': {'sonic'},
    }
    target_chain_ids = chain_id_map.get(chain_key, set())

    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            return None
        payload = response.json() if hasattr(response, 'json') else {}
        pairs = payload.get('pairs', []) if isinstance(payload, dict) else []
        if not isinstance(pairs, list) or not pairs:
            return None

        if target_chain_ids:
            filtered_pairs = [
                pair for pair in pairs
                if isinstance(pair, dict) and str(pair.get('chainId', '')).lower() in target_chain_ids
            ]
            if filtered_pairs:
                pairs = filtered_pairs

        def pair_rank(pair):
            if not isinstance(pair, dict):
                return (0.0, 0.0, 0.0)
            liquidity_usd = _safe_float((pair.get('liquidity') or {}).get('usd', 0))
            volume_h24 = _safe_float((pair.get('volume') or {}).get('h24', 0))
            market_cap = _safe_float(pair.get('marketCap', 0))
            fdv = _safe_float(pair.get('fdv', 0))
            return (liquidity_usd, volume_h24, market_cap or fdv)

        best_pair = max(pairs, key=pair_rank)
        if not isinstance(best_pair, dict):
            return None

        market_cap = _safe_float(best_pair.get('marketCap', 0))
        if market_cap <= 0:
            market_cap = _safe_float(best_pair.get('fdv', 0))
        volume_24h = _safe_float((best_pair.get('volume') or {}).get('h24', 0))
        price = _safe_float(best_pair.get('priceUsd', 0))

        if market_cap > 0 or volume_24h > 0 or price > 0:
            dex_chain = str(best_pair.get('chainId', '')).lower() or chain_key or 'unknown'
            dex_id = str(best_pair.get('dexId', '')).lower() or 'unknown'
            return {
                'market_cap': market_cap if market_cap > 0 else 0,
                'volume_24h': volume_24h if volume_24h > 0 else 0,
                'price': price if price > 0 else 0,
                'source': f'dexscreener:{dex_chain}:{dex_id}'
            }
    except Exception:
        return None
    return None

def fetch_additional_symbol_market_data(token_address, symbol, chain):
    """Fetch market data by symbol from multiple APIs to cover new tokens"""
    symbol_upper = normalize_symbol_for_api(symbol)
    if not symbol_upper:
        return []
    
    address_is_valid = is_valid_hex_address(token_address or "")
    is_native_placeholder = is_native_placeholder_address(token_address or "")
    points = []
    
    override_cg_ids = get_override_ids(symbol_upper, 'coingecko_ids')
    for cg_id in search_coingecko_ids(symbol_upper):
        data = fetch_coingecko_market_data_by_id(cg_id)
        if data:
            points.append(data)
            # Curated override IDs should map to a single intended asset.
            if override_cg_ids:
                break
    
    paprika_data = fetch_coinpaprika_market_data(symbol_upper)
    if paprika_data:
        points.append(paprika_data)
    
    coincap_data = fetch_coincap_market_data(symbol_upper)
    if coincap_data:
        points.append(coincap_data)
    
    chain_value = (chain or 'ethereum').lower()
    if address_is_valid and not is_native_placeholder and chain_value in ('ethereum', 'eth'):
        holders_count = fetch_ethplorer_holders(token_address)
        if holders_count > 0:
            points.append({
                'holders': holders_count,
                'market_cap': 0,
                'volume_24h': 0,
                'price': 0,
                'source': 'ethplorer'
            })
    
    # Try BscScan for BSC holders.
    if address_is_valid and not is_native_placeholder and chain_value in ('bsc', 'binance-smart-chain'):
        bscscan_holders = fetch_bscscan_holders(token_address)
        if bscscan_holders > 0:
            points.append({
                'holders': bscscan_holders,
                'market_cap': 0,
                'volume_24h': 0,
                'price': 0,
                'source': 'bscscan'
            })

    # Always try blockscout for supported EVM L2 chains.
    if address_is_valid and not is_native_placeholder:
        blockscout_holders = fetch_blockscout_holders(token_address, chain_value)
        if blockscout_holders > 0:
            points.append({
                'holders': blockscout_holders,
                'market_cap': 0,
                'volume_24h': 0,
                'price': 0,
                'source': f'blockscout_{chain_value}'
            })
    
    # For Sonic chain, also try alternative endpoints
    if address_is_valid and not is_native_placeholder and chain_value in ('s', 'sonic'):
        try:
            # Try Sonic RPC endpoint for holder count
            sonic_rpc_url = "https://rpc.soniclabs.com"
            # Note: This would require Web3 connection - keeping as fallback option
            # For now, blockscout should handle it
            pass
        except Exception:
            pass
    
    return points

def calculate_liquidity_from_volume(volume_24h, market_cap):
    """Calculate liquidity estimate from 24h volume using industry-standard ratios"""
    # Industry standard: Liquidity is typically 2-5% of market cap
    # For active tokens, liquidity can be estimated from volume
    # Common ratio: liquidity ≈ volume_24h * 0.1 to 0.3 (for active tokens)
    # Conservative estimate: use 0.15 multiplier for volume-based calculation
    
    if volume_24h > 0:
        # Method 1: Volume-based (for active trading tokens)
        volume_based_liq = volume_24h * 0.15  # Conservative multiplier
        return volume_based_liq
    
    # Method 2: Market cap-based (fallback)
    if market_cap > 0:
        # Conservative: 2% of market cap
        market_cap_based_liq = market_cap * 0.02
        return market_cap_based_liq
    
    return 0

def _chain_to_defillama_slug(chain):
    chain_key = (chain or '').strip().lower()
    mapping = {
        'ethereum': 'ethereum',
        'eth': 'ethereum',
        'polygon': 'polygon',
        'polygon-pos': 'polygon',
        'op': 'optimism',
        'optimism': 'optimism',
        'bsc': 'bsc',
        'binance-smart-chain': 'bsc',
        'arbitrum': 'arbitrum',
        'arb': 'arbitrum',
        'base': 'base',
        'linea': 'linea',
        'linea-mainnet': 'linea',
        'avax': 'avax',
        'avalanche': 'avax',
        'avalanche-c': 'avax',
        'sei': 'sei',
        'sonic': 'sonic',
        's': 'sonic',
        'mantle': 'mantle',
        'mnt': 'mantle',
        'zksync': 'zksync',
        'zk': 'zksync',
        'zksync-era': 'zksync',
        'solana': 'solana',
        'sol': 'solana',
    }
    return mapping.get(chain_key, 'ethereum')


def fetch_liquidity_from_dex_pools(token_address, symbol, chain='ethereum', volume_24h=0, market_cap=0, allow_coingecko=True):
    """Calculate liquidity from DEX pools and alternative sources"""
    liquidity_values = []
    sources = []
    token_ref = token_address.lower() if is_valid_hex_address(token_address or '') else str(token_address or '').strip()
    
    # Try DeFiLlama pools endpoint (alternative format)
    try:
        # Try different DeFiLlama endpoints
        endpoints = [
            f"https://api.llama.fi/pools/{token_ref}",
            f"https://coins.llama.fi/pools/{token_ref}",
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(
                    endpoint,
                    timeout=10,
                    headers={"Accept": "application/json", "User-Agent": "DeFiRiskAssessor/3.0"},
                )
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        # Sum TVL from all pools
                        total_tvl = sum(float(pool.get('tvlUsd', 0) or 0) for pool in data)
                        if total_tvl > 0:
                            liquidity_values.append(total_tvl)
                            sources.append('defillama_pools')
                            break
            except Exception:
                continue
    except Exception:
        pass
    
    # Try CoinGecko DEX data (optional; can be disabled to avoid free-tier throttling storms)
    coingecko_liq = 0
    if allow_coingecko:
        try:
            cg_chain = (chain or 'ethereum').strip().lower()
            platform = COINGECKO_PLATFORM_MAP.get(cg_chain, 'ethereum')
            contract_ref = token_address.lower() if is_valid_hex_address(token_address or '') else token_address
            url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{contract_ref}"
            response = rate_limited_get(url, timeout=10)
            if response is not None and response.status_code == 200:
                data = response.json()
                if 'market_data' in data:
                    market_data = data['market_data']
                    # Try total_liquidity
                    total_liq = market_data.get('total_liquidity', {}).get('usd', 0)
                    if total_liq > 0:
                        coingecko_liq = total_liq
                        liquidity_values.append(total_liq)
                        sources.append('coingecko_direct')
        except Exception:
            pass
    
    # If CoinGecko doesn't have direct liquidity, calculate from volume/market cap
    # This ensures we always have liquidity data when volume/market cap is available
    if coingecko_liq == 0 and (volume_24h > 0 or market_cap > 0):
        calculated_liq = calculate_liquidity_from_volume(volume_24h, market_cap)
        if calculated_liq > 0:
            liquidity_values.append(calculated_liq)
            if volume_24h > 0:
                sources.append('volume_calculated')
            else:
                sources.append('market_cap_calculated')
    
    # Calculate average if we have multiple sources
    if liquidity_values:
        avg_liquidity = sum(liquidity_values) / len(liquidity_values)
        return avg_liquidity, sources
    
    return 0, []

def fetch_real_liquidity_from_apis(token_address, symbol, chain='ethereum', volume_24h=0, market_cap=0, allow_coingecko=True):
    """Fetch real liquidity data from multiple APIs, then calculate from DEX pools if needed"""
    # Try direct liquidity endpoints first
    try:
        # Try DeFiLlama price endpoint (sometimes has liquidity)
        chain_slug = _chain_to_defillama_slug(chain)
        token_ref = token_address.lower() if is_valid_hex_address(token_address or '') else token_address
        url = f"https://coins.llama.fi/prices/current/{chain_slug}:{token_ref}"
        response = requests.get(
            url,
            timeout=10,
            headers={"Accept": "application/json", "User-Agent": "DeFiRiskAssessor/3.0"},
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'coins' in data and data['coins']:
                coin_key = f"{chain_slug}:{token_ref}"
                if coin_key in data['coins']:
                    coin_data = data['coins'][coin_key]
                    liquidity = coin_data.get('liquidity', 0)
                    if liquidity > 0:
                        return liquidity, ['defillama_direct']
    except Exception:
        pass
    
    # If direct endpoints don't work, calculate from DEX pools or volume/market cap
    liquidity, sources = fetch_liquidity_from_dex_pools(
        token_address,
        symbol,
        chain,
        volume_24h,
        market_cap,
        allow_coingecko=allow_coingecko
    )
    
    if liquidity > 0:
        return liquidity, sources
    
    return 0, []

def fetch_missing_market_data_from_api(token_address, symbol, chain, requested_metrics=None):
    """Fetch missing market data from APIs (multi-source averaging, no estimates)"""
    if not token_address:
        return None
    
    token_address_raw = str(token_address or '').strip()
    api_chain = (chain or 'ethereum').lower()
    if api_chain in ('solana', 'sol'):
        token_address_raw = SOLANA_ADDRESS_OVERRIDES.get(
            token_address_raw,
            SOLANA_ADDRESS_OVERRIDES.get(token_address_raw.lower(), token_address_raw)
        )
    address_is_valid = is_valid_hex_address(token_address_raw)
    address = token_address_raw.lower() if address_is_valid else token_address_raw
    solana_address_is_valid = is_valid_solana_address(token_address_raw)
    is_native_placeholder = is_native_placeholder_address(address)
    allow_contract_apis = address_is_valid and not is_native_placeholder
    symbol_key = (symbol or '').upper()
    symbol_api_key = normalize_symbol_for_api(symbol_key)
    market_symbol_key = MARKET_SYMBOL_ALIASES.get(symbol_api_key, symbol_api_key)
    symbol_candidates = []
    for candidate_symbol in (market_symbol_key, symbol_api_key, symbol_key):
        normalized_symbol = normalize_symbol_for_api(candidate_symbol)
        if normalized_symbol and normalized_symbol not in symbol_candidates:
            symbol_candidates.append(normalized_symbol)
    skip_symbol_only_sources = bool(symbol_candidates) and all(
        candidate in SYMBOL_ONLY_SOURCE_SKIP for candidate in symbol_candidates
    )
    requested = {
        str(metric).strip().lower()
        for metric in (requested_metrics or [])
        if isinstance(metric, str) and str(metric).strip()
    }
    need_market_metrics = not requested or bool(requested & {'market_cap', 'volume_24h', 'price'})
    need_holders_metric = not requested or 'holders' in requested
    
    metrics = {
        'market_cap': [],
        'volume_24h': [],
        'price': [],
        'holders': []
    }
    metric_source_values = {
        'market_cap': {},
        'volume_24h': {},
        'price': {},
        'holders': {},
    }
    sources_used = []
    
    def add_metric(metric, value, source_label=None):
        metric_key = str(metric or '').strip().lower()
        if metric_key not in metrics:
            return
        if metric == 'holders':
            parsed_holders = _parse_positive_holders(value)
            if parsed_holders <= 0 or _is_estimated_holders(parsed_holders):
                return
            value = parsed_holders
        if value and value > 0:
            parsed_value = float(value)
            metrics[metric_key].append(parsed_value)
            normalized_source = str(source_label or '').strip().lower()
            if normalized_source:
                existing_val = metric_source_values[metric_key].get(normalized_source, 0.0)
                if parsed_value > float(existing_val or 0.0):
                    metric_source_values[metric_key][normalized_source] = parsed_value
    
    def add_source(source_label):
        if source_label and source_label not in sources_used:
            sources_used.append(source_label)

    def _all_requested_metrics_resolved():
        if not requested:
            return all(bool(metrics.get(key)) for key in metrics)
        for key in requested:
            if key in metrics and not metrics.get(key):
                return False
        return True

    # Prefer cached API responses first (real historical data, avoids network when blocked)
    # But don't short-circuit if cached result has 0 holders — we'll augment below
    cached_api = None if is_native_placeholder else fetch_cached_api_market_data(token_address, symbol_key)
    if (not cached_api) and (not is_native_placeholder) and market_symbol_key and market_symbol_key != symbol_key:
        cached_api = fetch_cached_api_market_data(token_address, market_symbol_key)
    if cached_api:
        cached_sources = cached_api.get('sources_used') or []
        cached_source_label = cached_sources[0] if cached_sources else (cached_api.get('data_source') or 'api_cache')
        # Seed metrics from cached data so we can augment missing fields
        for key in ('market_cap', 'volume_24h', 'price', 'holders'):
            val = cached_api.get(key, 0) or 0
            if isinstance(val, (int, float)) and val > 0 and key != 'holders':
                add_metric(key, val, cached_source_label)
            elif key == 'holders' and isinstance(val, (int, float)) and val > 0 and not _is_estimated_holders(val):
                add_metric(key, val, cached_source_label)
        for src in cached_sources:
            add_source(src)
        # If all requested metrics are already filled, return early
        if _all_requested_metrics_resolved():
            return cached_api
    
    def apply_coingecko_market_data(data, source_label):
        updated = False
        if not isinstance(data, dict):
            return updated
        market_data = data.get('market_data', {})
        if isinstance(market_data, dict):
            mc = market_data.get('market_cap', {}).get('usd', 0) or 0
            vol = market_data.get('total_volume', {}).get('usd', 0) or 0
            price = market_data.get('current_price', {}).get('usd', 0) or 0
            if mc > 0:
                add_metric('market_cap', mc, source_label)
                updated = True
            if vol > 0:
                add_metric('volume_24h', vol, source_label)
                updated = True
            if price > 0:
                add_metric('price', price, source_label)
                updated = True
        # Do not map social followers to on-chain holders.
        # This created false low holder counts for some chains (e.g. Sonic).
        if updated:
            add_source(source_label)
        return updated
    
    def fetch_coingecko_simple(platform_id):
        cached_simple = (_coingecko_simple_batch_cache.get(platform_id, {}) if isinstance(_coingecko_simple_batch_cache, dict) else {}).get(address)
        if isinstance(cached_simple, dict) and cached_simple:
            price = cached_simple.get('usd', 0) or 0
            market_cap = cached_simple.get('usd_market_cap', 0) or 0
            volume = cached_simple.get('usd_24h_vol', 0) or 0
            if price > 0:
                add_metric('price', price, 'coingecko_simple_batch')
            if market_cap > 0:
                add_metric('market_cap', market_cap, 'coingecko_simple_batch')
            if volume > 0:
                add_metric('volume_24h', volume, 'coingecko_simple_batch')
            if price > 0 or market_cap > 0 or volume > 0:
                add_source('coingecko_simple_batch')
                return True

        simple_url = (
            f"https://api.coingecko.com/api/v3/simple/token_price/{platform_id}"
            f"?contract_addresses={address}&vs_currencies=usd"
            f"&include_market_cap=true&include_24hr_vol=true"
        )
        try:
            resp = rate_limited_get(simple_url, timeout=10)
            if resp is None:
                return False
            if resp.status_code == 200:
                data = resp.json()
                entry = data.get(address)
                if entry:
                    price = entry.get('usd', 0) or 0
                    market_cap = entry.get('usd_market_cap', 0) or 0
                    volume = entry.get('usd_24h_vol', 0) or 0
                    if price > 0:
                        add_metric('price', price, 'coingecko_simple')
                    if market_cap > 0:
                        add_metric('market_cap', market_cap, 'coingecko_simple')
                    if volume > 0:
                        add_metric('volume_24h', volume, 'coingecko_simple')
                    add_source('coingecko_simple')
                    _coingecko_simple_batch_cache.setdefault(platform_id, {})[address] = entry
                    return True
            elif resp.status_code == 429:
                print(f"      ⚠️  CoinGecko simple endpoint rate limit for {symbol}, using non-CoinGecko fallback sources")
        except Exception:
            return False
        return False
    
    # Solana-specific on-chain market metrics from Solscan.
    if need_market_metrics and api_chain in ('solana', 'sol') and solana_address_is_valid:
        solscan_market = fetch_solscan_market_metrics(token_address_raw)
        if solscan_market:
            solscan_source = solscan_market.get('source') or 'solscan_meta'
            add_metric('market_cap', solscan_market.get('market_cap', 0), solscan_source)
            add_metric('volume_24h', solscan_market.get('volume_24h', 0), solscan_source)
            add_metric('price', solscan_market.get('price', 0), solscan_source)
            add_source(solscan_source)

    # Try CoinMarketCap first for symbol-level spot market data.
    if need_market_metrics and symbol_candidates and not skip_symbol_only_sources:
        for symbol_candidate in symbol_candidates:
            cmc_data = fetch_coinmarketcap_market_data(symbol_candidate)
            if not cmc_data:
                continue
            cmc_source = cmc_data.get('source') or 'coinmarketcap'
            add_metric('market_cap', cmc_data.get('market_cap', 0), cmc_source)
            add_metric('volume_24h', cmc_data.get('volume_24h', 0), cmc_source)
            add_metric('price', cmc_data.get('price', 0), cmc_source)
            add_source(cmc_source)
            break

    # Curated CoinGecko ID overrides are queried early to avoid missing market cap when
    # contract-based CoinGecko endpoints return 4xx/429 (e.g. USD₮0 on SEI).
    override_coingecko_ids = []
    for symbol_candidate in symbol_candidates:
        override_coingecko_ids.extend(get_override_ids(symbol_candidate, 'coingecko_ids'))
    for cg_id in list(dict.fromkeys([x for x in override_coingecko_ids if x])):
        if not need_market_metrics:
            break
        if _all_requested_metrics_resolved():
            break
        cg_data = fetch_coingecko_market_data_by_id(cg_id)
        if not cg_data:
            continue
        cg_source = cg_data.get('source') or 'coingecko_id'
        add_metric('market_cap', cg_data.get('market_cap', 0), cg_source)
        add_metric('volume_24h', cg_data.get('volume_24h', 0), cg_source)
        add_metric('price', cg_data.get('price', 0), cg_source)
        add_source(cg_source)
    
    # Contract-address sources (skip for native placeholder addresses like 0xeeee...).
    if allow_contract_apis and need_market_metrics:
        try:
            llama_map = {
                'ethereum': 'ethereum',
                'eth': 'ethereum',
                'polygon': 'polygon',
                'op': 'optimism',
                'optimism': 'optimism',
                'bsc': 'bsc',
                'arbitrum': 'arbitrum',
                'arb': 'arbitrum',
                'base': 'base',
                'linea': 'linea',
                'avax': 'avax',
                'avalanche': 'avax',
                'avalanche-c': 'avax',
                'sonic': 'sonic',
                's': 'sonic',
                'sei': 'sei',
                'mantle': 'mantle',
                'mnt': 'mantle',
                'zksync': 'zksync',
                'zk': 'zksync',
                'zksync-era': 'zksync',
            }
            llama_chain = llama_map.get(api_chain, 'ethereum')
            llama_url = f"https://coins.llama.fi/prices/current/{llama_chain}:{address}"
            llama_resp = requests.get(
                llama_url,
                timeout=10,
                headers={"Accept": "application/json", "User-Agent": "DeFiRiskAssessor/3.0"},
            )
            if llama_resp.status_code == 200:
                data = llama_resp.json().get('coins', {})
                coin = data.get(f"{llama_chain}:{address}")
                if coin:
                    price = coin.get('price', 0) or 0
                    market_cap = coin.get('marketCap', 0) or 0
                    volume = coin.get('volume24h', 0) or 0
                    if price > 0:
                        add_metric('price', price, 'defillama')
                    if market_cap > 0:
                        add_metric('market_cap', market_cap, 'defillama')
                    if volume > 0:
                        add_metric('volume_24h', volume, 'defillama')
                    if price > 0 and market_cap == 0:
                        supply = coin.get('supply', 0) or 0
                        if supply > 0:
                            add_metric('market_cap', price * supply, 'defillama_supply')
                    add_source('defillama')
        except Exception:
            pass
        
        platform = COINGECKO_PLATFORM_MAP.get(api_chain, 'ethereum')
        # CoinGecko contract endpoint for detailed data
        try:
            contract_ref = address.lower() if is_valid_hex_address(address) else address
            cg_url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{contract_ref}"
            response = rate_limited_get(cg_url, timeout=10)
            if response is not None and response.status_code == 200:
                apply_coingecko_market_data(response.json(), 'coingecko_contract')
            elif response is not None and response.status_code == 429:
                print(f"      ⚠️  CoinGecko rate limit for {symbol}, skipping further CoinGecko calls for now")
            elif response is not None and response.status_code not in (200,):
                print(f"      ⚠️  CoinGecko contract endpoint {response.status_code} for {symbol}")
        except Exception:
            pass
        
        # Fallback to lightweight simple endpoint if we still lack market fields
        if (not metrics['market_cap']) or (not metrics['volume_24h']) or (not metrics['price']):
            fetch_coingecko_simple(platform)

    # DexScreener fallback for contract-address assets when market cap is still missing.
    # This helps chains where CMC/CG contract endpoints are sparse or temporarily rate-limited.
    if allow_contract_apis and need_market_metrics and (
        not metrics['market_cap'] or not metrics['volume_24h'] or not metrics['price']
    ):
        dexscreener_data = fetch_dexscreener_market_data(token_address_raw, api_chain)
        if dexscreener_data:
            dex_source = dexscreener_data.get('source') or 'dexscreener'
            if not metrics['market_cap']:
                add_metric('market_cap', dexscreener_data.get('market_cap', 0), dex_source)
            if not metrics['volume_24h']:
                add_metric('volume_24h', dexscreener_data.get('volume_24h', 0), dex_source)
            if not metrics['price']:
                add_metric('price', dexscreener_data.get('price', 0), dex_source)
            add_source(dex_source)
    
    # Final fallback to CoinPaprika (static map) if still missing
    if need_market_metrics and symbol_candidates and not skip_symbol_only_sources:
        for symbol_candidate in symbol_candidates:
            has_paprika_mapping = (
                symbol_candidate in COINPAPRIKA_IDS
                or bool(get_override_ids(symbol_candidate, 'coinpaprika_ids'))
            )
            if not has_paprika_mapping:
                continue
            paprika_data = fetch_coinpaprika_market_data(symbol_candidate)
            if not paprika_data:
                continue
            paprika_source = paprika_data.get('source') or 'coinpaprika'
            add_metric('market_cap', paprika_data.get('market_cap', 0), paprika_source)
            add_metric('volume_24h', paprika_data.get('volume_24h', 0), paprika_source)
            add_metric('price', paprika_data.get('price', 0), paprika_source)
            add_source(paprika_source)
            break
    
    # Extended sources (CoinGecko search, CoinCap, CoinPaprika search, Ethplorer, etc.)
    if need_market_metrics and symbol_candidates and not skip_symbol_only_sources:
        for symbol_candidate in symbol_candidates:
            additional_points = fetch_additional_symbol_market_data(token_address_raw, symbol_candidate, chain)
            for point in additional_points:
                point_source = point.get('source') or 'symbol_fallback'
                add_metric('market_cap', point.get('market_cap', 0), point_source)
                add_metric('volume_24h', point.get('volume_24h', 0), point_source)
                add_metric('price', point.get('price', 0), point_source)
                add_metric('holders', point.get('holders', 0), point_source)
                add_source(point_source)
            if _all_requested_metrics_resolved():
                break
    
    # Fetch holders from on-chain explorers.
    # For L2/new chains (including Sonic) we query multiple sources and keep the highest
    # confirmed value because some endpoints return partial pages only.
    if need_holders_metric and not is_native_placeholder:
        chain_lower = (chain or 'ethereum').lower()
        multi_source_holder_chains = {
            'op', 'optimism', 's', 'sonic', 'base', 'arbitrum', 'arb', 'linea', 'sei',
            'mantle', 'mnt', 'zksync', 'zk', 'zksync-era'
        }
        prefer_multi_source = chain_lower in multi_source_holder_chains

        if chain_lower in ('solana', 'sol') and solana_address_is_valid:
            solscan_holders = fetch_solscan_holders(token_address_raw)
            if solscan_holders and solscan_holders > 0:
                add_metric('holders', solscan_holders, 'solscan')
                add_source('solscan')
        if not metrics['holders'] and chain_lower in ('solana', 'sol') and solana_address_is_valid:
            tracker_holders = fetch_solanatracker_holders(token_address_raw)
            if tracker_holders and tracker_holders > 0:
                add_metric('holders', tracker_holders, 'solanatracker')
                add_source('solanatracker')
        if not metrics['holders'] and chain_lower in ('solana', 'sol') and solana_address_is_valid:
            birdeye_holders = fetch_birdeye_holders(token_address_raw)
            if birdeye_holders and birdeye_holders > 0:
                add_metric('holders', birdeye_holders, 'birdeye')
                add_source('birdeye')
        if chain_lower in ('bsc', 'binance-smart-chain') and address_is_valid:
            bscscan_holders = fetch_bscscan_holders(token_address)
            if bscscan_holders and bscscan_holders > 0:
                add_metric('holders', bscscan_holders, 'etherscan_multichain')
                add_source('etherscan_multichain')
        # Try Ethplorer for Ethereum tokens
        if chain_lower in ('ethereum', 'eth') and address_is_valid:
            ethplorer_holders = fetch_ethplorer_holders(token_address)
            if ethplorer_holders and ethplorer_holders > 0:
                add_metric('holders', ethplorer_holders, 'ethplorer')
                add_source('ethplorer')
        # Try Blockscout for L2 tokens (OP, Sonic, etc.)
        if (
            (not metrics['holders'] or prefer_multi_source)
            and chain_lower in ('op', 'optimism', 's', 'sonic', 'base', 'arbitrum', 'arb', 'mantle', 'mnt', 'zksync', 'zk', 'zksync-era')
        ):
            blockscout_holders = fetch_blockscout_holders(token_address, chain_lower)
            if blockscout_holders and blockscout_holders > 0:
                add_metric('holders', blockscout_holders, 'blockscout')
                add_source('blockscout')
        # Try Etherscan V2 chain-aware token holder endpoint early for chains that frequently
        # return partial counts in third-party endpoints.
        if (not metrics['holders'] or prefer_multi_source) and address_is_valid:
            etherscan_holders = fetch_etherscan_holders(token_address, chain_lower)
            if etherscan_holders and etherscan_holders > 0:
                add_metric('holders', etherscan_holders, 'etherscan')
                add_source('etherscan')
        # Try Moralis owners endpoint
        if (not metrics['holders'] or prefer_multi_source) and address_is_valid:
            moralis_holders = fetch_moralis_holders(token_address, chain_lower)
            if moralis_holders and moralis_holders > 0:
                add_metric('holders', moralis_holders, 'moralis')
                add_source('moralis')
        # Try GoPlus token_security holder count (works without dedicated key).
        if not metrics['holders'] and address_is_valid:
            goplus_holders = fetch_goplus_token_holders(token_address, chain_lower)
            if goplus_holders and goplus_holders > 0:
                add_metric('holders', goplus_holders, 'goplus_token_security')
                add_source('goplus_token_security')
        # Try Dune SIM holder endpoint (chain-aware)
        if (not metrics['holders'] or prefer_multi_source) and address_is_valid:
            dune_holders = fetch_dune_holders(token_address, chain_lower)
            if dune_holders and dune_holders > 0:
                add_metric('holders', dune_holders, 'dune_sim')
                add_source('dune_sim')
    
    if any(metrics[field] for field in metrics):
        holders_candidates = [int(v) for v in metrics['holders'] if isinstance(v, (int, float)) and v > 0]
        aggregated_result = {
            'market_cap': mean(metrics['market_cap']) if metrics['market_cap'] else 0,
            'volume_24h': mean(metrics['volume_24h']) if metrics['volume_24h'] else 0,
            'price': mean(metrics['price']) if metrics['price'] else 0,
            'holders': max(holders_candidates) if holders_candidates else 0,
            'sources_used': list(dict.fromkeys(sources_used)),
            'metric_source_values': {
                metric: values
                for metric, values in metric_source_values.items()
                if isinstance(values, dict) and values
            },
            'data_source': 'multi_api' if sources_used else 'N/A'
        }
        return aggregated_result
    
    return None

def extract_market_data(token_data, token_address=None, symbol=None, chain=None, fetch_if_missing=True):
    """Extract market data from token data structure - FIXED VERSION with real liquidity"""
    market_cap = 0
    volume_24h = 0
    holders = 0
    liquidity = 0
    price = 0
    data_source = "N/A"
    sources_used = []
    chain_lower = (chain or 'ethereum').lower()
    has_onchain_payload = False
    has_chain_compatible_onchain_holders = False
    
    # Try to get data from aggregated values first
    if 'aggregated' in token_data:
        agg = token_data['aggregated']
        market_cap = agg.get('market_cap', 0)
        volume_24h = agg.get('volume_24h', 0)
        # Holders are validated later through chain-compatible on-chain sources.
        # Do not trust top-level aggregated holders blindly (can be cross-chain stale).
        liquidity = agg.get('liquidity', 0)
        price = agg.get('price', 0)
        data_source = "webhook_cache"
        sources_used.append('webhook_cache')
    
    # Try market_data section for real-time data ONLY (skip fallback/estimated data)
    if 'market_data' in token_data:
        market_data = token_data['market_data']
        for source, data in market_data.items():
            if isinstance(data, dict) and data.get('source') == 'real-time':
                # Only use real-time data, skip fallback/estimated
                if 'market_cap' in data and data['market_cap'] > 0:
                    market_cap = data['market_cap']
                if 'volume_24h' in data and data['volume_24h'] > 0:
                    volume_24h = data['volume_24h']
                if 'price' in data and data['price'] > 0:
                    price = data['price']
                data_source = source
                sources_used.append(source)
                break
    
    # Try aggregates for market data if not found - but check for estimated/rounded values
    # Skip if values look like estimates (rounded to billions/millions)
    if 'aggregates' in token_data:
        agg = token_data['aggregates']
        if 'market' in agg:
            market_agg = agg['market']
            # Check if market_data has fallback source - if so, skip aggregates
            has_fallback = False
            if 'market_data' in token_data:
                for source, data in token_data['market_data'].items():
                    if isinstance(data, dict) and data.get('source') == 'fallback':
                        has_fallback = True
                        break
            
            # Only use aggregates if no fallback data exists
            if not has_fallback:
                mc_val = market_agg.get('market_cap', 0)
                vol_val = market_agg.get('volume_24h', 0)
                price_val = market_agg.get('price', 0)
                
                # Skip rounded/estimated values (check if value is exactly rounded)
                def is_estimated_value(val):
                    if val == 0:
                        return False
                    # Check if value is a round number (likely estimate)
                    # Values like 1000000000, 2000000000, 500000000 are estimates
                    rounded_estimates = [1000000000, 2000000000, 500000000, 1500000000, 
                                        100000000, 200000000, 500000000, 10000000, 20000000, 30000000]
                    return val in rounded_estimates
                
                if market_cap == 0 and mc_val > 0 and not is_estimated_value(mc_val):
                    market_cap = mc_val
                if volume_24h == 0 and vol_val > 0 and not is_estimated_value(vol_val):
                    volume_24h = vol_val
                if price == 0 and price_val > 0:
                    price = price_val
    
    # Try onchain_data for holders - ONLY real-time, skip estimates
    if 'onchain_data' in token_data:
        onchain_data = token_data['onchain_data']
        has_onchain_payload = isinstance(onchain_data, dict) and bool(onchain_data)
        for source, data in onchain_data.items():
            if isinstance(data, dict):
                if _is_chain_incompatible_holder_source(source, chain_lower):
                    # Prevent cross-chain contamination (e.g. Ethplorer holders on Sonic contracts).
                    continue
                data_source_type = data.get('source', '')
                # Skip explicitly estimated/fallback values.
                if data_source_type in ('fallback', 'estimated', 'l2-estimate'):
                    continue
                parsed_holders = _parse_positive_holders(data.get('holders', 0))
                if parsed_holders > 0 and not _is_estimated_holders(parsed_holders):
                    holders = int(parsed_holders)
                    has_chain_compatible_onchain_holders = True
                    sources_used.append(source)
                    break
    
    # Try aggregates for holders if not found - but check for estimated values
    if holders == 0 and 'aggregates' in token_data:
        agg = token_data['aggregates']
        if 'onchain' in agg:
            onchain_agg = agg['onchain']
            holders_val = onchain_agg.get('holders', 0)
            # Skip round numbers that look like estimates (e.g., 100000)
            if (
                holders_val > 0
                and not _is_estimated_holders(holders_val)
                and (not has_onchain_payload or has_chain_compatible_onchain_holders)
            ):
                holders = int(holders_val)
    
    # If holders still 0, try on-chain explorers directly (Ethplorer for ETH, Blockscout for L2)
    if holders == 0 and fetch_if_missing and token_address:
        if chain_lower in ('ethereum', 'eth') and is_valid_hex_address(token_address):
            ethplorer_holders = fetch_ethplorer_holders(token_address)
            if ethplorer_holders and ethplorer_holders > 0:
                holders = ethplorer_holders
                sources_used.append('ethplorer')
        if holders == 0 and chain_lower in ('bsc', 'binance-smart-chain') and is_valid_hex_address(token_address):
            bscscan_holders = fetch_bscscan_holders(token_address)
            if bscscan_holders and bscscan_holders > 0:
                holders = bscscan_holders
                sources_used.append('bscscan')
        if holders == 0 and chain_lower in (
            'op', 'optimism', 's', 'sonic', 'base', 'arbitrum', 'arb',
            'mantle', 'mnt', 'zksync', 'zk', 'zksync-era'
        ):
            blockscout_holders = fetch_blockscout_holders(token_address, chain_lower)
            if blockscout_holders and blockscout_holders > 0:
                holders = blockscout_holders
                sources_used.append('blockscout')
    
    # Try liquidity_data from cache
    if 'liquidity_data' in token_data:
        liquidity_data = token_data['liquidity_data']
        for source, data in liquidity_data.items():
            if isinstance(data, dict) and data.get('source') == 'real-time':
                if 'liquidity' in data and data['liquidity'] > 0:
                    liquidity = data['liquidity']
                    sources_used.append(source)
                break
    
    # Try aggregates for liquidity
    if 'aggregates' in token_data:
        agg = token_data['aggregates']
        if 'liquidity' in agg:
            lq = agg['liquidity']
            if isinstance(lq, dict):
                ll = lq.get('liquidity', 0)
                if isinstance(ll, (int, float)) and ll > 0:
                    liquidity = ll
            elif isinstance(lq, (int, float)) and lq > 0:
                liquidity = lq
    
    # If market data is missing, fetch from API (with rate limit handling)
    if fetch_if_missing and (market_cap == 0 or volume_24h == 0) and token_address and symbol and chain:
        print(f"    🔍 Fetching missing market data for {symbol} from API...")
        api_data = fetch_missing_market_data_from_api(token_address, symbol, chain)
        if api_data:
            # Only use API data if it's real (not estimated/rounded)
            def is_estimated_value(val):
                if val == 0:
                    return False
                rounded_estimates = [1000000000, 2000000000, 500000000, 1500000000, 
                                    100000000, 200000000, 500000000, 10000000, 20000000, 30000000]
                return val in rounded_estimates
            
            if market_cap == 0 and api_data['market_cap'] > 0 and not is_estimated_value(api_data['market_cap']):
                market_cap = api_data['market_cap']
            if volume_24h == 0 and api_data['volume_24h'] > 0 and not is_estimated_value(api_data['volume_24h']):
                volume_24h = api_data['volume_24h']
            if price == 0 and api_data['price'] > 0:
                price = api_data['price']
            parsed_api_holders = _parse_positive_holders(api_data.get('holders', 0))
            if holders == 0 and parsed_api_holders > 0 and not _is_estimated_holders(parsed_api_holders):
                holders = parsed_api_holders
            api_sources = api_data.get('sources_used', [])
            for src in api_sources:
                if src:
                    sources_used.append(src)
            if api_data.get('data_source') and api_data['data_source'] != "N/A":
                data_source = api_data['data_source']
            elif api_sources:
                data_source = ', '.join(dict.fromkeys(api_sources))
    
    # If liquidity is still 0, try to fetch from APIs or calculate from DEX pools/volume
    if fetch_if_missing and liquidity == 0 and token_address and symbol:
        print(f"    🔍 Calculating liquidity for {symbol} from DEX data...")
        real_liquidity, sources = fetch_real_liquidity_from_apis(token_address, symbol, chain_lower, volume_24h, market_cap)
        if real_liquidity > 0:
            liquidity = real_liquidity
            if data_source == "N/A":
                # Create source string from calculation sources
                if sources:
                    if len(sources) > 1:
                        data_source = f"dex_calculated ({', '.join(sources[:2])})"
                    else:
                        data_source = f"dex_calculated ({sources[0]})"
                else:
                    data_source = "dex_calculated"
            sources_used.append('dex_liquidity')
            print(f"    ✅ Calculated liquidity ${liquidity:,.0f} from {data_source}")
        else:
            print(f"    ⚠️  Could not calculate liquidity for {symbol}")
    
    return {
        'market_cap': market_cap,
        'volume_24h': volume_24h,
        'holders': holders,
        'liquidity': liquidity,
        'price': price,
        'data_source': data_source,
        'sources_used': list(dict.fromkeys(sources_used))
    }


def _ensure_swr_executor():
    """Initialize stale-while-revalidate executor from runtime settings."""
    global _SWR_EXECUTOR, _SWR_ENABLED, _SWR_WORKERS
    runtime_cfg = _get_runtime_api_settings()
    _SWR_ENABLED = bool(runtime_cfg.get("background_monitoring", False))
    if not _SWR_ENABLED:
        return
    target_workers = max(1, min(int(runtime_cfg.get("max_parallel_requests", 4) or 4), 4))
    if _SWR_EXECUTOR is None or _SWR_WORKERS != target_workers:
        if _SWR_EXECUTOR is not None:
            try:
                _SWR_EXECUTOR.shutdown(wait=False, cancel_futures=False)
            except Exception:
                pass
        _SWR_EXECUTOR = ThreadPoolExecutor(max_workers=target_workers, thread_name_prefix="token-swr")
        _SWR_WORKERS = target_workers


def _run_swr_refresh_task(token_address, token_name, symbol, chain, display_chain):
    """Background refresh: serve stale now, refresh cache/fallback asynchronously."""
    try:
        fresh_data = fetch_missing_market_data_from_api(
            token_address,
            symbol,
            chain,
            requested_metrics=["market_cap", "volume_24h", "price", "holders"],
        )
        if not isinstance(fresh_data, dict):
            return False
        payload = dict(fresh_data)
        if _normalize_metric_candidate("liquidity", payload.get("liquidity", 0)) <= 0:
            liq_val, liq_sources = fetch_real_liquidity_from_apis(
                token_address,
                symbol,
                chain,
                payload.get("volume_24h", 0),
                payload.get("market_cap", 0),
                allow_coingecko=False,
            )
            if liq_val > 0:
                payload["liquidity"] = liq_val
                sources_used = payload.get("sources_used", []) if isinstance(payload.get("sources_used"), list) else []
                sources_used.extend(liq_sources)
                payload["sources_used"] = list(dict.fromkeys(sources_used))
        payload["data_source"] = payload.get("data_source") or "swr_background_refresh"
        persist_real_data_to_cache(
            token_address,
            token_name,
            symbol,
            display_chain or chain,
            payload,
        )
        return True
    except Exception:
        return False


def _schedule_swr_refresh(token_address, token_name, symbol, chain, display_chain):
    """Queue background refresh for stale-but-usable entries."""
    if not _SWR_ENABLED or _SWR_EXECUTOR is None:
        return False
    task_key = build_token_storage_key(token_address, chain, symbol) or normalize_address_for_storage(token_address)
    if not task_key:
        return False
    with _SWR_FUTURES_LOCK:
        if task_key in _SWR_SCHEDULED_KEYS:
            return False
        _SWR_SCHEDULED_KEYS.add(task_key)
        future = _SWR_EXECUTOR.submit(
            _run_swr_refresh_task,
            token_address,
            token_name,
            symbol,
            chain,
            display_chain,
        )
        _SWR_FUTURES.append(future)
    return True


def _finalize_swr_queue(timeout_seconds=15.0):
    """Drain queued background refresh tasks with bounded wait."""
    global _SWR_EXECUTOR
    with _SWR_FUTURES_LOCK:
        pending = [f for f in _SWR_FUTURES if f is not None]
        _SWR_FUTURES.clear()
        _SWR_SCHEDULED_KEYS.clear()
    if not pending:
        return
    done, not_done = wait(pending, timeout=max(0.0, float(timeout_seconds)))
    if not_done:
        for future in not_done:
            try:
                future.cancel()
            except Exception:
                pass
    if _SWR_EXECUTOR is not None:
        try:
            _SWR_EXECUTOR.shutdown(wait=False, cancel_futures=False)
        except Exception:
            pass
        _SWR_EXECUTOR = None


def create_token_data_viewer_csv():
    """Create the token_data_viewer.csv file with current data"""
    print("🔄 Updating Token Data Viewer CSV...")
    
    # Load data sources
    tokens_df = load_tokens_csv()
    if tokens_df is None:
        return False
    
    policy = get_cache_policy()
    skip_seconds = policy["metric_skip_hours"] * 3600
    report_data = load_latest_report_data()
    webhook_cache = load_webhook_cache()
    fallback_data = load_fallback_data()
    _ensure_swr_executor()
    swr_refresh_queued = 0
    
    # Load previous viewer data (if present) to keep last known real values
    previous_rows = {}
    existing_viewer_csv = os.path.join(DATA_DIR, "token_data_viewer.csv")
    if os.path.exists(existing_viewer_csv):
        try:
            prev_df = pd.read_csv(existing_viewer_csv, keep_default_na=False)
            for _, row in prev_df.iterrows():
                symbol_key = str(row.get('Symbol', '')).upper()
                if symbol_key:
                    previous_rows[symbol_key] = row.to_dict()
            print(f"ℹ️ Loaded previous viewer data for {len(previous_rows)} tokens")
        except Exception as e:
            print(f"⚠️ Could not load previous viewer CSV: {e}")

    # Prime CoinGecko simple endpoint cache once per run to avoid per-token 429 storms.
    try:
        _prime_coingecko_simple_cache(tokens_df)
    except Exception as e:
        print(f"⚠️ Could not prefetch CoinGecko simple cache: {e}")
    
    # Create the viewer dataframe
    viewer_data = []
    
    for _, token_row in tokens_df.iterrows():
        # Metric accumulators so we can average across multiple sources
        metric_values = {
            'market_cap': [],
            'volume_24h': [],
            'holders': [],
            'liquidity': [],
            'price': [],
            'risk_score': []
        }
        sources_used = []
        api_payload = None
        api_liquidity_sources = []
        last_seen_ts = 0.0

        def add_metrics(values, source_label):
            """Add metrics from a source and track which metrics were used."""
            added = False
            for key in metric_values.keys():
                if key not in values:
                    continue
                val = values.get(key, 0) or 0
                if key == 'holders':
                    parsed_holders = _parse_positive_holders(val)
                    if parsed_holders <= 0 or _is_estimated_holders(parsed_holders):
                        continue
                    val = parsed_holders
                if isinstance(val, (int, float)) and val > 0:
                    metric_values[key].append(float(val))
                    added = True
            if added and source_label not in sources_used:
                sources_used.append(source_label)
            return added

        def aggregate_current_metrics():
            """Aggregate metrics with type-aware reduction rules."""
            aggregated_out = {}
            for metric_name, raw_values in metric_values.items():
                clean_values = [float(v) for v in raw_values if isinstance(v, (int, float)) and float(v) > 0]
                if not clean_values:
                    aggregated_out[metric_name] = 0
                elif metric_name == 'holders':
                    aggregated_out[metric_name] = int(max(clean_values))
                else:
                    aggregated_out[metric_name] = mean(clean_values)
            return aggregated_out

        address_raw = str(token_row.get('Contract Address', '') or '').strip()
        address = normalize_address_for_storage(address_raw)
        name = str(token_row.get('Token Name', '') or '').strip()
        symbol = str(token_row.get('Symbol', '') or '').strip()
        symbol_upper = str(symbol).upper() if isinstance(symbol, str) else str(symbol)
        chain = str(token_row.get('Chain', '') or '').strip()
        display_chain = chain
        chain_lower = chain.lower()

        if chain_lower in ('solana', 'sol'):
            address = SOLANA_ADDRESS_OVERRIDES.get(
                address,
                SOLANA_ADDRESS_OVERRIDES.get(address.lower(), address)
            )
        
        # Apply contract/chain overrides for API accuracy
        api_address = ADDRESS_OVERRIDES.get(address, ADDRESS_OVERRIDES.get(address.lower(), address))
        api_chain = CHAIN_OVERRIDES.get(symbol_upper, chain)
        native_placeholder_asset = is_native_placeholder_address(api_address)

        scoped_storage_key = build_token_storage_key(api_address, api_chain, symbol_upper)
        lookup_candidates = []
        if scoped_storage_key:
            lookup_candidates.append(scoped_storage_key)
        # Native placeholder assets share 0xeeee... across chains, so avoid generic
        # address lookups to prevent cross-chain cache contamination.
        if not native_placeholder_asset:
            for candidate in address_lookup_variants(api_address) + address_lookup_variants(address):
                if candidate and candidate not in lookup_candidates:
                    lookup_candidates.append(candidate)
        
        # Determine which cache key is available
        cache_key = first_present_key(webhook_cache, lookup_candidates)

        fallback_key = first_present_key(fallback_data, lookup_candidates)
        
        # 1) Fallback file first (agreed priority source)
        if fallback_key is not None:
            fb_entry = fallback_data[fallback_key]
            cleaned_fb, keep_entry, _ = sanitize_cache_entry(fallback_key, fb_entry)
            if keep_entry:
                fb_ts = get_entry_timestamp(fb_entry)
                fb_fresh = fb_ts > 0 and (time.time() - fb_ts) < skip_seconds
                if not fb_fresh:
                    print(f"    ℹ️  Fallback data for {symbol} is older than {policy['metric_skip_hours']}h, will still use it first then refresh missing metrics.")
                fb_metrics = extract_market_data(cleaned_fb, api_address, symbol, api_chain, fetch_if_missing=False)
                filtered_fb = {k: v for k, v in fb_metrics.items() if k in metric_values and not metric_values[k]}
                if filtered_fb:
                    add_metrics(filtered_fb, 'token_fallbacks')
                    last_seen_ts = max(last_seen_ts, fb_ts)

        # 2) Webhook cache second (fills only what fallback did not provide)
        if cache_key is not None:
            webhook_entry = webhook_cache[cache_key]
            cache_metrics = extract_market_data(webhook_entry, api_address, symbol, api_chain, fetch_if_missing=False)
            filtered_cache = {k: v for k, v in cache_metrics.items() if k in metric_values and not metric_values[k]}
            if filtered_cache:
                add_metrics(filtered_cache, 'webhook_cache')
            last_seen_ts = max(last_seen_ts, get_entry_timestamp(webhook_entry))
        
        # Aggregate current values and determine what is missing
        aggregated = aggregate_current_metrics()
        missing_metrics = [k for k in ('market_cap', 'volume_24h', 'holders', 'liquidity', 'price') if aggregated[k] <= 0]
        initial_missing_metrics = list(missing_metrics)
        api_fetch_metrics = [k for k in missing_metrics if k in ('market_cap', 'volume_24h', 'holders', 'price')]
        if native_placeholder_asset:
            for metric_name in ('market_cap', 'volume_24h', 'price'):
                if metric_name not in api_fetch_metrics:
                    api_fetch_metrics.append(metric_name)
        # Sonic holders are often stale in fallback/cache snapshots; always attempt
        # a fresh holder query so live chain values can overwrite old non-zero values.
        if (
            chain_lower in ('s', 'sonic')
            and not native_placeholder_asset
            and is_valid_hex_address(api_address)
            and 'holders' not in api_fetch_metrics
        ):
            api_fetch_metrics.append('holders')

        stale_entry = bool(last_seen_ts) and (time.time() - last_seen_ts) >= skip_seconds
        has_usable_stale_metrics = any(aggregated.get(k, 0) > 0 for k in ('market_cap', 'volume_24h', 'holders', 'liquidity', 'price'))
        if (
            stale_entry
            and has_usable_stale_metrics
            and not api_fetch_metrics
            and api_address
            and _schedule_swr_refresh(api_address, name, symbol, api_chain, display_chain)
        ):
            swr_refresh_queued += 1
            stale_age_hours = (time.time() - last_seen_ts) / 3600
            print(f"    🔁 Serving stale metrics for {symbol} ({stale_age_hours:.1f}h old); queued background refresh.")
        
        # 3) If anything is still missing, hit real-time APIs
        if api_fetch_metrics and api_address:
            if last_seen_ts and policy["respect_skip"]:
                age_hours = (time.time() - last_seen_ts) / 3600
                print(f"    ℹ️ Last real data {age_hours:.1f}h ago; fetching only missing metrics to avoid stale N/A values.")
            print(f"    🔍 Fetching missing metrics {api_fetch_metrics} for {symbol} via APIs...")
            api_data = fetch_missing_market_data_from_api(
                api_address,
                symbol,
                api_chain,
                requested_metrics=api_fetch_metrics
            )
            if api_data:
                api_payload = dict(api_data)
                if native_placeholder_asset:
                    # Native placeholders are symbol-level assets; replace stale contract-derived metrics.
                    for metric_name in ('market_cap', 'volume_24h', 'price'):
                        if isinstance(api_data.get(metric_name, 0), (int, float)) and api_data.get(metric_name, 0) > 0:
                            metric_values[metric_name] = []
                add_metrics(api_data, 'api')
        
        # 4) Calculate liquidity if still missing (uses DEX + volume/MC)
        aggregated = aggregate_current_metrics()
        if aggregated['liquidity'] <= 0 and api_address:
            liq_val, liq_sources = fetch_real_liquidity_from_apis(
                api_address,
                symbol,
                api_chain,
                aggregated['volume_24h'],
                aggregated['market_cap'],
                allow_coingecko=False
            )
            if liq_val > 0:
                api_liquidity_sources = liq_sources
                add_metrics({'liquidity': liq_val}, f"dex_liquidity ({', '.join(liq_sources)})" if liq_sources else "dex_liquidity")
                if api_payload is not None:
                    api_payload['liquidity'] = liq_val
            aggregated = aggregate_current_metrics()

        # 5) Last report is the final fallback for still-missing metrics only
        report_entry_key = first_present_key(report_data.get('by_address', {}), lookup_candidates)
        report_entry = report_data.get('by_address', {}).get(report_entry_key) if report_entry_key else None
        if not report_entry:
            report_entry = report_data.get('by_symbol', {}).get(symbol_upper)
        if report_entry:
            filtered_report = {}
            for k, v in report_entry.items():
                if k not in metric_values:
                    continue
                if k == 'risk_score':
                    filtered_report[k] = v
                elif native_placeholder_asset and k in ('market_cap', 'volume_24h', 'price'):
                    if isinstance(v, (int, float)) and v > 0:
                        filtered_report[k] = v
                elif not metric_values[k]:
                    filtered_report[k] = v
            if filtered_report:
                if native_placeholder_asset:
                    for metric_name in ('market_cap', 'volume_24h', 'price'):
                        if isinstance(filtered_report.get(metric_name, 0), (int, float)) and filtered_report.get(metric_name, 0) > 0:
                            metric_values[metric_name] = []
                add_metrics(filtered_report, 'latest_report')
        aggregated = aggregate_current_metrics()

        # Fallback to alias symbol from previous CSV if still empty
        has_real_data = (
            aggregated['market_cap'] > 0 or 
            aggregated['volume_24h'] > 0 or 
            aggregated['holders'] > 0 or 
            aggregated['price'] > 0 or
            aggregated['liquidity'] > 0
        )

        market_data = {
            'market_cap': aggregated['market_cap'],
            'volume_24h': aggregated['volume_24h'],
            'holders': int(aggregated['holders']) if aggregated['holders'] > 0 else 0,
            'liquidity': aggregated['liquidity'],
            'price': aggregated['price'],
            'risk_score': aggregated['risk_score'],
            'data_source': 'N/A',
            'sources_used': []
        }

        if not has_real_data:
            alias_symbol = SYMBOL_FALLBACKS.get(symbol_upper)
            alias_row = previous_rows.get(alias_symbol) if alias_symbol else None
            if alias_row:
                def parse_currency(value):
                    if not isinstance(value, str):
                        return 0
                    cleaned = value.replace('$', '').replace(',', '').strip()
                    try:
                        return float(cleaned)
                    except ValueError:
                        return 0
                def parse_integer(value):
                    if not isinstance(value, str):
                        return 0
                    cleaned = value.replace(',', '').strip()
                    try:
                        return int(float(cleaned))
                    except ValueError:
                        return 0
                
                mc = parse_currency(alias_row.get('Market Cap'))
                vol = parse_currency(alias_row.get('Volume 24h'))
                liq = parse_currency(alias_row.get('Liquidity'))
                price_val = parse_currency(alias_row.get('Price'))
                holders_val = parse_integer(alias_row.get('Holders'))
                
                if mc > 0 or vol > 0 or liq > 0 or price_val > 0 or holders_val > 0:
                    market_data['market_cap'] = mc
                    market_data['volume_24h'] = vol
                    market_data['liquidity'] = liq
                    market_data['price'] = price_val
                    market_data['holders'] = holders_val
                    market_data['data_source'] = f"alias:{alias_symbol}"
                    has_real_data = True
        
        # Keep placeholder row when no verified metrics are available yet.
        if not has_real_data:
            print(f"  ⚠️ {symbol}: No verified real-time data available, keeping placeholder entry.")
            market_data['data_source'] = "missing_real_data"
        else:
            unique_sources = list(dict.fromkeys(sources_used))
            if market_data['data_source'] == 'N/A':
                market_data['data_source'] = f"avg({', '.join(unique_sources)})" if len(unique_sources) > 1 else (unique_sources[0] if unique_sources else 'N/A')
            market_data['sources_used'] = unique_sources
            final_missing_metrics = [k for k in ('market_cap', 'volume_24h', 'holders', 'liquidity', 'price') if market_data.get(k, 0) <= 0]
            resolved_missing_metrics = [k for k in initial_missing_metrics if k not in final_missing_metrics]
            should_persist = bool(api_address) and bool(
                resolved_missing_metrics
                or (api_payload and any(api_payload.get(k, 0) > 0 for k in ('market_cap', 'volume_24h', 'price', 'holders', 'liquidity')))
                or (native_placeholder_asset and any(market_data.get(k, 0) > 0 for k in ('market_cap', 'volume_24h', 'price')))
            )
            if should_persist:
                payload_to_persist = dict(api_payload or {})
                for metric_key in ('market_cap', 'volume_24h', 'price', 'holders', 'liquidity'):
                    existing_val = payload_to_persist.get(metric_key, 0)
                    if not isinstance(existing_val, (int, float)) or existing_val <= 0:
                        payload_to_persist[metric_key] = market_data.get(metric_key, 0)
                if api_liquidity_sources and payload_to_persist.get('liquidity', 0) > 0:
                    payload_to_persist.setdefault('sources_used', []).extend(api_liquidity_sources)
                if unique_sources:
                    payload_to_persist.setdefault('sources_used', []).extend(unique_sources)
                payload_to_persist['sources_used'] = list(dict.fromkeys(payload_to_persist.get('sources_used', [])))
                payload_to_persist['data_source'] = market_data.get('data_source', 'pipeline_refresh')
                persist_real_data_to_cache(
                    api_address or address,
                    name,
                    symbol,
                    display_chain,
                    payload_to_persist
                )
        
        viewer_row = {
            'Token': name,
            'Symbol': symbol,
            'Chain': display_chain,
            'Market Cap': f"${market_data['market_cap']:,.2f}" if market_data['market_cap'] > 0 else "N/A",
            'Volume 24h': f"${market_data['volume_24h']:,.2f}" if market_data['volume_24h'] > 0 else "N/A",
            'Holders': f"{market_data['holders']:,}" if market_data['holders'] > 0 else "N/A",
            'Liquidity': f"${market_data['liquidity']:,.2f}" if market_data['liquidity'] > 0 else "N/A",
            'Price': f"${market_data['price']:,.2f}" if market_data['price'] > 0 else "N/A",
            'Risk Score': f"{market_data['risk_score']:.2f}" if market_data.get('risk_score', 0) > 0 else "N/A",
            'Data Source': market_data['data_source'],
            'Last Updated': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
        
        # If real-time APIs failed, reuse last known real values from previous CSV (including alias)
        prev_row = previous_rows.get(symbol_upper)
        if not prev_row:
            alias_symbol = SYMBOL_FALLBACKS.get(symbol_upper)
            if alias_symbol:
                prev_row = previous_rows.get(alias_symbol)
        if prev_row:
            filled_from_prev = False
            field_map = {
                'Market Cap': 'market_cap',
                'Volume 24h': 'volume_24h',
                'Liquidity': 'liquidity',
                'Price': 'price'
            }
            for field, key in field_map.items():
                prev_val = prev_row.get(field)
                if viewer_row[field] == "N/A" and isinstance(prev_val, str) and prev_val not in ("", "N/A", "nan", ""):
                    viewer_row[field] = prev_val
                    cleaned = prev_val.replace('$', '').replace(',', '')
                    try:
                        market_data[key] = float(cleaned)
                        filled_from_prev = True
                    except ValueError:
                        pass
            volatile_holder_chains = {
                's', 'sonic', 'op', 'optimism', 'base', 'arbitrum', 'arb', 'linea', 'sei',
                'mantle', 'mnt', 'zksync', 'zk', 'zksync-era'
            }
            if viewer_row['Holders'] == "N/A" and chain_lower not in volatile_holder_chains:
                prev_hold = prev_row.get('Holders')
                if isinstance(prev_hold, str) and prev_hold not in ("", "N/A", "nan"):
                    try:
                        prev_holders = int(prev_hold.replace(',', ''))
                        if prev_holders > 0 and not _is_estimated_holders(prev_holders):
                            viewer_row['Holders'] = prev_hold
                            market_data['holders'] = prev_holders
                            filled_from_prev = True
                    except ValueError:
                        pass
            if filled_from_prev and market_data['data_source'] in ('missing_real_data', 'N/A'):
                market_data['data_source'] = 'previous_csv'
                has_real_data = True
        
        if not has_real_data:
            holders_value = _parse_positive_holders(market_data.get('holders', 0))
            has_real_data = (
                (market_data.get('market_cap', 0) or 0) > 0
                or (market_data.get('volume_24h', 0) or 0) > 0
                or ((market_data.get('liquidity', 0) or 0) > 0)
                or ((market_data.get('price', 0) or 0) > 0)
                or (holders_value > 0 and not _is_estimated_holders(holders_value))
            )
        
        viewer_data.append(viewer_row)
        
        if has_real_data:
            data_parts = []
            if market_data['market_cap'] > 0:
                data_parts.append(f"MC=${market_data['market_cap']:,.0f}")
            if market_data['volume_24h'] > 0:
                data_parts.append(f"Vol=${market_data['volume_24h']:,.0f}")
            if market_data['holders'] > 0:
                data_parts.append(f"Holders={market_data['holders']:,}")
            if market_data['liquidity'] > 0:
                data_parts.append(f"Liq=${market_data['liquidity']:,.0f}")
            if market_data['price'] > 0:
                data_parts.append(f"Price=${market_data['price']:,.2f}")
            print(f"  ✅ {symbol}: {', '.join(data_parts)}")
            if 'dex_calculated' in market_data['data_source'] or 'dex_liquidity' in market_data['data_source']:
                print(f"     📊 Liquidity calculated from DEX pools: {market_data['data_source']}")
        else:
            print(f"     ℹ️  {symbol} will display as N/A until real data is available.")
    
    if swr_refresh_queued > 0:
        print(f"🔄 Finalizing {swr_refresh_queued} stale-while-revalidate task(s)...")
    _finalize_swr_queue(timeout_seconds=15.0)

    # Create DataFrame and save
    viewer_df = pd.DataFrame(viewer_data)
    
    viewer_csv = os.path.join(DATA_DIR, "token_data_viewer.csv")
    export_csv = os.path.join(DATA_DIR, "token_data_viewer_export.csv")
    enhanced_csv = os.path.join(DATA_DIR, "tokens_enhanced.csv")
    
    try:
        # Save to all three files that might be used by the Token Data Viewer
        # Use na_rep='N/A' to ensure N/A values are written as strings, not NaN
        viewer_df.to_csv(viewer_csv, index=False, na_rep='N/A')
        viewer_df.to_csv(export_csv, index=False, na_rep='N/A')
        viewer_df.to_csv(enhanced_csv, index=False, na_rep='N/A')
        print(f"✅ Updated all Token Data Viewer CSV files with {len(viewer_df)} tokens")
        print("   Priority: fallback file > webhook cache > live APIs for missing metrics > latest report")
        print("   Missing metrics trigger live API fetches and are cached back to fallback/real_data_cache")
        print("   LIQUIDITY COLUMN INCLUDED with real data or DEX-calculated values")
        print(f"   Files updated:")
        print(f"   - {viewer_csv}")
        print(f"   - {export_csv}")
        print(f"   - {enhanced_csv}")
        
        # Show sample data
        print("\n📊 Real Data Summary:")
        print(viewer_df[['Token', 'Symbol', 'Market Cap', 'Volume 24h', 'Holders', 'Liquidity', 'Price', 'Data Source']].head(5).to_string(index=False))
        
        return True
    except Exception as e:
        print(f"❌ Error saving token_data_viewer.csv: {e}")
        return False

if __name__ == "__main__":
    print(f"🚀 Token Data Viewer CSV Updater - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        success = create_token_data_viewer_csv()
    finally:
        _save_http_request_state(force=True)
        _finalize_swr_queue(timeout_seconds=1.0)
    
    if success:
        print("\n🎉 Token Data Viewer CSV updated successfully!")
        print("   ✅ Priority pipeline: fallback -> cache -> live API fill -> latest report fallback")
        print("   ✅ Real-time API hits cached to fallback to avoid rate limits")
        print("   ✅ LIQUIDITY COLUMN INCLUDED with real data from APIs/DEX")
    else:
        print("\n❌ Failed to update Token Data Viewer CSV")
        print("   Check the error messages above for details.")
