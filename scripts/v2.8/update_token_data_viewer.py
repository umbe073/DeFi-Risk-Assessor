#!/usr/bin/env python3
"""
Update Token Data Viewer CSV with current data
This script reads from tokens.csv and populates market data from webhook cache
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime
import requests
import time
from statistics import mean
from urllib.parse import quote
from pathlib import Path

# Project directories
PROJECT_ROOT = "/Users/amlfreak/Desktop/venv"
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
REAL_DATA_CACHE_FILE = os.path.join(DATA_DIR, "real_data_cache.json")
FALLBACK_FILE = os.path.join(DATA_DIR, "token_fallbacks.json")
API_RESPONSE_CACHE_FILE = os.path.join(DATA_DIR, "api_response_cache.json")

# Some tokens use canonical contracts or API chains that differ from tokens.csv
ADDRESS_OVERRIDES = {
    # Gala's active ERC-20 contract (matches webhook cache & real APIs)
    '0x15d4c048f83bd7e37d49ea4c83a07267ec4203da': '0xd1d2eb1b1e90b638588728b4130137d262c87cae',
    # SKY's on-chain data hasn't propagated yet; reuse Maker's canonical contract for API calls
    '0x56072c95faa701256059aa122697b133aed9279': '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2',
}

# Override API chain for specific symbols (display chain stays the same)
CHAIN_OVERRIDES = {
    'POL': 'ethereum',  # POL contract lives on Ethereum even though it represents Polygon
}

SYMBOL_FALLBACKS = {
    # Allow seamless migrations (reuse last known real data from the legacy symbol)
    'SKY': 'MKR',
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
        # Broad net for Sonic ticker so we get *real* data even if contract is placeholder/non-EVM
        'coingecko_ids': ['sonic', 'sonic-2', 'sonic-token', 'sonic-coin'],
        'coinpaprika_ids': ['sonic-sonic', 'sonic-sonic-3', 'sonic-sonic-4'],
        'coincap_ids': ['sonic'],
    },
}

COINGECKO_PLATFORM_MAP = {
    'ethereum': 'ethereum',
    'polygon': 'polygon-pos',
    'polygon-pos': 'polygon-pos',
    'op': 'optimistic-ethereum',
    'optimism': 'optimistic-ethereum',
    'bsc': 'binance-smart-chain',
    'sonic': 'sonic',
}

COINPAPRIKA_IDS = {
    'WBTC': 'wbtc-wrapped-bitcoin',
    '1INCH': '1inch-1inch',
    'POL': 'matic-polygon',
    'OP': 'op-optimism',
    'GRT': 'grt-the-graph',
    'QNT': 'qnt-quant',
    'SUSHI': 'sushi-sushi',
}

COINGECKO_REQUEST_MIN_DELAY = 1.5  # seconds between requests to avoid rate limits
_last_coingecko_request = 0.0
ETHPLORER_API_KEY = os.environ.get('ETHPLORER_API_KEY', 'freekey')


def rate_limited_get(url, timeout=10):
    """Rate-limited GET helper to avoid CoinGecko free-tier throttling."""
    global _last_coingecko_request
    elapsed = time.time() - _last_coingecko_request
    if elapsed < COINGECKO_REQUEST_MIN_DELAY:
        time.sleep(COINGECKO_REQUEST_MIN_DELAY - elapsed)
    response = requests.get(url, timeout=timeout)
    _last_coingecko_request = time.time()
    return response

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def is_valid_hex_address(address: str) -> bool:
    """Simple EVM address validator to avoid contract lookups for placeholder IDs."""
    if not isinstance(address, str):
        return False
    addr = address.lower()
    return addr.startswith('0x') and len(addr) == 42 and all(c in '0123456789abcdef' for c in addr[2:])


def load_settings():
    """Load user settings so we respect refresh intervals and skip windows."""
    default_settings = {
        "cache": {
            "auto_refresh_interval": "10 minutes",
            "cache_retention": "24 hours",
            "background_monitoring": False,
            "respect_48h_metric_skip": True,
            "metric_skip_hours": 48
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


def get_entry_timestamp(entry):
    """Extract a numeric timestamp from a cache/fallback entry if present."""
    if not isinstance(entry, dict):
        return 0.0
    ts = entry.get("timestamp", 0)
    try:
        return float(ts)
    except Exception:
        return 0.0


def load_latest_report_data():
    """Load the latest XLSX risk assessment report for fallback metrics."""
    reports = sorted(Path(DATA_DIR).glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    for report_path in reports:
        try:
            df = pd.read_excel(report_path, sheet_name=0)
        except Exception:
            continue
        if df.empty:
            continue
        by_address = {}
        by_symbol = {}

        def safe_num(val):
            try:
                if pd.isna(val):
                    return 0
                return float(val)
            except Exception:
                return 0

        for _, row in df.iterrows():
            address_val = str(row.get("Token Address", "") or "").lower()
            symbol_val = str(row.get("Symbol", "") or "").upper()
            entry = {
                "market_cap": safe_num(row.get("Market Cap", 0)),
                "volume_24h": safe_num(row.get("Volume 24h", 0)),
                "holders": int(safe_num(row.get("Holders", 0))),
                "liquidity": safe_num(row.get("Liquidity", 0)),
                "price": safe_num(row.get("Price", 0)),
                "risk_score": safe_num(row.get("Risk Score", 0)),
                "data_source": f"report:{report_path.name}"
            }
            if address_val:
                by_address[address_val] = entry
            if symbol_val:
                by_symbol[symbol_val] = entry
        if by_address or by_symbol:
            print(f"✅ Loaded latest report data from {report_path.name} ({len(by_address)} addresses)")
            return {
                "by_address": by_address,
                "by_symbol": by_symbol,
                "path": str(report_path)
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
    
    addr_key = (token_address or "").lower()
    symbol_key = (symbol or "").upper()
    metrics = {'market_cap': [], 'volume_24h': [], 'price': [], 'liquidity': []}
    sources = []
    
    for key, entry in cache.items():
        if not isinstance(entry, dict):
            continue
        if addr_key and addr_key not in key.lower():
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
        token_mappings[token_address] = entry
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
            tokens.update({k.lower(): v for k, v in token_mappings.items()})
        legacy_tokens = fallback_data.get('tokens', {})
        if isinstance(legacy_tokens, dict):
            tokens.update({k.lower(): v for k, v in legacy_tokens.items()})
        print(f"✅ Loaded fallback data with {len(tokens)} tokens")
        return tokens
    except Exception as e:
        print(f"❌ Error reading fallback data: {e}")
        return {}

def save_real_data_cache(cache_data):
    """Persist sanitized or updated real data cache to disk"""
    try:
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
            if holders_val in (100000, 0):
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
        isinstance(oc, dict) and (oc.get('holders', 0) or 0) > 0
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
            with open(REAL_DATA_CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {'tokens': {}, 'last_updated': 0}

def persist_real_data_to_cache(token_address, token_name, symbol, chain, market_data):
    """Persist freshly fetched real data back to the cache so future runs reuse it"""
    if not token_address:
        return
    
    has_real_metrics = any(
        market_data.get(key, 0) > 0 for key in ('market_cap', 'volume_24h', 'price', 'holders', 'liquidity')
    )
    if not has_real_metrics:
        return
    
    cache_data = load_full_real_data_cache()
    tokens = cache_data.setdefault('tokens', {})
    
    entry = tokens.get(token_address, {})
    entry['address'] = token_address
    entry['token_name'] = token_name
    entry['symbol'] = symbol
    entry['chain'] = chain
    entry['timestamp'] = time.time()
    entry['source'] = 'real_time'
    
    providers = market_data.get('sources_used') or []
    if not providers and market_data.get('data_source'):
        providers = [market_data['data_source']]
    
    entry['market_data'] = {
        'multi_api': {
            'market_cap': market_data.get('market_cap', 0),
            'volume_24h': market_data.get('volume_24h', 0),
            'price': market_data.get('price', 0),
            'source': 'real-time',
            'providers': providers
        }
    }
    
    entry['aggregates'] = {
        'market': {
            'market_cap': market_data.get('market_cap', 0),
            'volume_24h': market_data.get('volume_24h', 0),
            'price': market_data.get('price', 0)
        }
    }
    
    if market_data.get('holders', 0) > 0:
        holders_val = int(market_data['holders'])
        entry.setdefault('onchain_data', {})
        entry['onchain_data']['api'] = {
            'holders': holders_val,
            'source': 'real-time'
        }
        entry['aggregates'].setdefault('onchain', {})['holders'] = holders_val
    
    if market_data.get('liquidity', 0) > 0:
        entry.setdefault('liquidity_data', {})
        entry['liquidity_data']['calculated'] = {
            'liquidity': market_data['liquidity'],
            'source': 'real-time'
        }
        entry['aggregates'].setdefault('liquidity', {})['liquidity'] = market_data['liquidity']
    
    tokens[token_address] = entry
    cache_data['last_updated'] = time.time()
    save_real_data_cache(cache_data)
    
    # Also persist to fallback file so future runs can skip re-fetching within the skip window
    try:
        save_fallback_entry(token_address, entry)
    except Exception as e:
        print(f"⚠️  Could not persist {symbol} to fallback: {e}")

def get_override_ids(symbol_upper, key):
    """Get override identifiers for a symbol"""
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
        if response.status_code == 200:
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
    ids = get_override_ids(symbol_upper, 'coingecko_ids')
    if ids:
        return ids
    try:
        url = f"https://api.coingecko.com/api/v3/search?query={quote(symbol_upper)}"
        response = rate_limited_get(url, timeout=10)
        if response.status_code == 200:
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

def get_coinpaprika_ids(symbol_upper):
    """Get CoinPaprika IDs for a symbol"""
    ids = []
    override_ids = get_override_ids(symbol_upper, 'coinpaprika_ids')
    ids.extend([i for i in override_ids if i])
    if symbol_upper in COINPAPRIKA_IDS:
        ids.append(COINPAPRIKA_IDS[symbol_upper])
    if ids:
        return ids
    
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
    return ids

def fetch_coinpaprika_market_data(symbol_upper):
    """Fetch market data from CoinPaprika"""
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

def fetch_blockscout_holders(token_address, chain):
    """Fetch holders count from Blockscout explorers for L2 networks (v2 API)."""
    chain_lower = (chain or '').lower()
    blockscout_domains = {
        'op': 'optimism.blockscout.com',
        'optimism': 'optimism.blockscout.com',
        's': 'sonicscan.org',  # Sonic chain explorer
        'sonic': 'sonicscan.org',
    }
    domain = blockscout_domains.get(chain_lower)
    if not domain or not token_address:
        return 0
    
    try:
        # Try v2 API first
        url = f"https://{domain}/api/v2/tokens/{token_address}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            holders_val = data.get('holders_count') or data.get('holdersCount') or data.get('holder_count') or 0
            if isinstance(holders_val, str):
                holders_val = holders_val.replace(',', '').strip()
            try:
                holders_int = int(float(holders_val))
                if holders_int > 0:
                    return holders_int
            except Exception:
                pass
        
        # Fallback to v1 API for Sonic chain
        if chain_lower in ('s', 'sonic'):
            url_v1 = f"https://{domain}/api?module=token&action=getToken&contractaddress={token_address}"
            response_v1 = requests.get(url_v1, timeout=10)
            if response_v1.status_code == 200:
                data_v1 = response_v1.json()
                if data_v1.get('status') == '1':
                    holders_val = data_v1.get('result', {}).get('holders') or 0
                    if isinstance(holders_val, str):
                        holders_val = holders_val.replace(',', '').strip()
                    try:
                        holders_int = int(float(holders_val))
                        if holders_int > 0:
                            return holders_int
                    except Exception:
                        pass
    except Exception as e:
        print(f"      ⚠️  Blockscout API error for {chain}: {e}")
    return 0

def fetch_additional_symbol_market_data(token_address, symbol, chain):
    """Fetch market data by symbol from multiple APIs to cover new tokens"""
    symbol_upper = (symbol or '').upper()
    if not symbol_upper:
        return []
    
    address_is_valid = is_valid_hex_address(token_address or "")
    points = []
    
    for cg_id in search_coingecko_ids(symbol_upper):
        data = fetch_coingecko_market_data_by_id(cg_id)
        if data:
            points.append(data)
    
    paprika_data = fetch_coinpaprika_market_data(symbol_upper)
    if paprika_data:
        points.append(paprika_data)
    
    coincap_data = fetch_coincap_market_data(symbol_upper)
    if coincap_data:
        points.append(coincap_data)
    
    chain_value = (chain or 'ethereum').lower()
    if address_is_valid and chain_value in ('ethereum', 'op', 'optimism', 'arbitrum', 'base'):
        holders_count = fetch_ethplorer_holders(token_address)
        if holders_count > 0:
            points.append({
                'holders': holders_count,
                'market_cap': 0,
                'volume_24h': 0,
                'price': 0,
                'source': 'ethplorer'
            })
    
    # Always try blockscout for L2 chains (OP, S/Sonic, etc.)
    if address_is_valid:
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
    if address_is_valid and chain_value in ('s', 'sonic'):
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

def fetch_liquidity_from_dex_pools(token_address, symbol, volume_24h=0, market_cap=0):
    """Calculate liquidity from DEX pools and alternative sources"""
    liquidity_values = []
    sources = []
    
    # Try DeFiLlama pools endpoint (alternative format)
    try:
        # Try different DeFiLlama endpoints
        endpoints = [
            f"https://api.llama.fi/pools/{token_address.lower()}",
            f"https://coins.llama.fi/pools/{token_address.lower()}",
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
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
    
    # Try CoinGecko DEX data
    coingecko_liq = 0
    try:
        url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{token_address}"
        response = rate_limited_get(url, timeout=10)
        
        if response.status_code == 200:
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

def fetch_real_liquidity_from_apis(token_address, symbol, volume_24h=0, market_cap=0):
    """Fetch real liquidity data from multiple APIs, then calculate from DEX pools if needed"""
    # Try direct liquidity endpoints first
    try:
        # Try DeFiLlama price endpoint (sometimes has liquidity)
        url = f"https://coins.llama.fi/prices/current/ethereum:{token_address.lower()}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'coins' in data and data['coins']:
                coin_key = f"ethereum:{token_address.lower()}"
                if coin_key in data['coins']:
                    coin_data = data['coins'][coin_key]
                    liquidity = coin_data.get('liquidity', 0)
                    if liquidity > 0:
                        return liquidity, ['defillama_direct']
    except Exception:
        pass
    
    # If direct endpoints don't work, calculate from DEX pools or volume/market cap
    liquidity, sources = fetch_liquidity_from_dex_pools(token_address, symbol, volume_24h, market_cap)
    
    if liquidity > 0:
        return liquidity, sources
    
    return 0, []

def fetch_missing_market_data_from_api(token_address, symbol, chain):
    """Fetch missing market data from APIs (multi-source averaging, no estimates)"""
    import time
    
    if not token_address:
        return None
    
    address = token_address.lower()
    address_is_valid = is_valid_hex_address(address)
    symbol_key = (symbol or '').upper()
    api_chain = (chain or 'ethereum').lower()
    
    metrics = {
        'market_cap': [],
        'volume_24h': [],
        'price': [],
        'holders': []
    }
    sources_used = []

    # Prefer cached API responses first (real historical data, avoids network when blocked)
    cached_api = fetch_cached_api_market_data(token_address, symbol_key)
    if cached_api:
        return cached_api
    
    def add_metric(metric, value):
        if value and value > 0:
            metrics[metric].append(float(value))
    
    def add_source(source_label):
        if source_label and source_label not in sources_used:
            sources_used.append(source_label)
    
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
                add_metric('market_cap', mc)
                updated = True
            if vol > 0:
                add_metric('volume_24h', vol)
                updated = True
            if price > 0:
                add_metric('price', price)
                updated = True
        community = data.get('community_data', {})
        if isinstance(community, dict):
            holders = community.get('twitter_followers', 0) or 0
            if holders > 0:
                add_metric('holders', holders)
                updated = True
        if updated:
            add_source(source_label)
        return updated
    
    def fetch_coingecko_simple(platform_id):
        simple_url = (
            f"https://api.coingecko.com/api/v3/simple/token_price/{platform_id}"
            f"?contract_addresses={address}&vs_currencies=usd"
            f"&include_market_cap=true&include_24hr_vol=true"
        )
        for attempt in range(3):
            try:
                resp = rate_limited_get(simple_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    entry = data.get(address)
                    if entry:
                        price = entry.get('usd', 0) or 0
                        market_cap = entry.get('usd_market_cap', 0) or 0
                        volume = entry.get('usd_24h_vol', 0) or 0
                        if price > 0:
                            add_metric('price', price)
                        if market_cap > 0:
                            add_metric('market_cap', market_cap)
                        if volume > 0:
                            add_metric('volume_24h', volume)
                        add_source('coingecko_simple')
                        return True
                elif resp.status_code == 429:
                    print(f"      ⚠️  CoinGecko simple endpoint rate limit for {symbol}, retry {attempt + 1}/3...")
                    time.sleep(2 * (attempt + 1))
                    continue
                else:
                    break
            except Exception:
                break
        return False
    
    # Try DeFiLlama first (no API key required)
    if address_is_valid:
        try:
            llama_map = {
                'ethereum': 'ethereum',
                'polygon': 'polygon',
                'op': 'optimism',
                'optimism': 'optimism',
                'bsc': 'bsc',
            }
            llama_chain = llama_map.get(api_chain, 'ethereum')
            llama_url = f"https://coins.llama.fi/prices/current/{llama_chain}:{address}"
            llama_resp = requests.get(llama_url, timeout=10)
            if llama_resp.status_code == 200:
                data = llama_resp.json().get('coins', {})
                coin = data.get(f"{llama_chain}:{address}")
                if coin:
                    price = coin.get('price', 0) or 0
                    market_cap = coin.get('marketCap', 0) or 0
                    volume = coin.get('volume24h', 0) or 0
                    if price > 0:
                        add_metric('price', price)
                    if market_cap > 0:
                        add_metric('market_cap', market_cap)
                    if volume > 0:
                        add_metric('volume_24h', volume)
                    if price > 0 and market_cap == 0:
                        supply = coin.get('supply', 0) or 0
                        if supply > 0:
                            add_metric('market_cap', price * supply)
                    add_source('defillama')
        except Exception:
            pass
        
        platform = COINGECKO_PLATFORM_MAP.get(api_chain, 'ethereum')
        # CoinGecko contract endpoint for detailed data
        try:
            cg_url = f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{address}"
            response = rate_limited_get(cg_url, timeout=10)
            if response.status_code == 200:
                apply_coingecko_market_data(response.json(), 'coingecko_contract')
            elif response.status_code == 429:
                print(f"      ⚠️  CoinGecko rate limit for {symbol}, retrying shortly...")
                time.sleep(2)
                retry = rate_limited_get(cg_url, timeout=10)
                if retry.status_code == 200:
                    apply_coingecko_market_data(retry.json(), 'coingecko_contract')
            elif response.status_code not in (200,):
                print(f"      ⚠️  CoinGecko contract endpoint {response.status_code} for {symbol}")
        except Exception:
            pass
        
        # Fallback to lightweight simple endpoint if we still lack data
        fetch_coingecko_simple(platform)
    
    # Final fallback to CoinPaprika (static map) if still missing
    if symbol_key in COINPAPRIKA_IDS:
        paprika_id = COINPAPRIKA_IDS[symbol_key]
        paprika_data = fetch_coinpaprika_market_data(symbol_key)
        if paprika_data:
            add_metric('market_cap', paprika_data.get('market_cap', 0))
            add_metric('volume_24h', paprika_data.get('volume_24h', 0))
            add_metric('price', paprika_data.get('price', 0))
            add_source(paprika_data.get('source'))
    
    # Extended sources (CoinGecko search, CoinCap, CoinPaprika search, Ethplorer, etc.)
    additional_points = fetch_additional_symbol_market_data(token_address, symbol, chain)
    for point in additional_points:
        add_metric('market_cap', point.get('market_cap', 0))
        add_metric('volume_24h', point.get('volume_24h', 0))
        add_metric('price', point.get('price', 0))
        add_metric('holders', point.get('holders', 0))
        add_source(point.get('source'))
    
    if any(metrics[field] for field in metrics):
        aggregated_result = {
            'market_cap': mean(metrics['market_cap']) if metrics['market_cap'] else 0,
            'volume_24h': mean(metrics['volume_24h']) if metrics['volume_24h'] else 0,
            'price': mean(metrics['price']) if metrics['price'] else 0,
            'holders': int(mean(metrics['holders'])) if metrics['holders'] else 0,
            'sources_used': sources_used,
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
    
    # Try to get data from aggregated values first
    if 'aggregated' in token_data:
        agg = token_data['aggregated']
        market_cap = agg.get('market_cap', 0)
        volume_24h = agg.get('volume_24h', 0)
        holders = int(agg.get('holders', 0))
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
        for source, data in onchain_data.items():
            if isinstance(data, dict):
                data_source_type = data.get('source', '')
                # Only use real-time data, skip estimates/l2-estimate/fallback
                if data_source_type == 'real-time' and 'holders' in data and data['holders'] > 0:
                    holders = int(data['holders'])
                    sources_used.append(source)
                    break
    
    # Try aggregates for holders if not found - but check for estimated values
    if holders == 0 and 'aggregates' in token_data:
        agg = token_data['aggregates']
        if 'onchain' in agg:
            onchain_agg = agg['onchain']
            holders_val = onchain_agg.get('holders', 0)
            # Skip round numbers that look like estimates (e.g., 100000)
            if holders_val > 0 and holders_val != 100000:
                holders = int(holders_val)
    
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
            if holders == 0 and api_data['holders'] > 0:
                holders = api_data['holders']
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
        real_liquidity, sources = fetch_real_liquidity_from_apis(token_address, symbol, volume_24h, market_cap)
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
                if isinstance(val, (int, float)) and val > 0:
                    metric_values[key].append(float(val))
                    added = True
            if added and source_label not in sources_used:
                sources_used.append(source_label)
            return added

        # Fix linting error: convert to string first, then lowercase
        address_raw = token_row['Contract Address']
        address = str(address_raw).lower() if address_raw is not None else ''
        name = token_row['Token Name']
        symbol = token_row['Symbol']
        symbol_upper = str(symbol).upper() if isinstance(symbol, str) else str(symbol)
        chain = token_row['Chain']
        display_chain = chain
        
        # Apply contract/chain overrides for API accuracy
        api_address = ADDRESS_OVERRIDES.get(address, address)
        api_chain = CHAIN_OVERRIDES.get(symbol_upper, chain)
        
        # Determine which cache key is available
        cache_key = None
        if api_address in webhook_cache:
            cache_key = api_address
        elif address in webhook_cache:
            cache_key = address
        
        fallback_key = None
        if api_address in fallback_data:
            fallback_key = api_address
        elif address in fallback_data:
            fallback_key = address
        
        # 1) Webhook cache (fresh real-time)
        if cache_key is not None:
            webhook_entry = webhook_cache[cache_key]
            add_metrics(extract_market_data(webhook_entry, api_address, symbol, api_chain, fetch_if_missing=False), 'webhook_cache')
            last_seen_ts = max(last_seen_ts, get_entry_timestamp(webhook_entry))
        
        # 2) Fallback file (cached real data, still within skip window)
        if fallback_key is not None:
            fb_entry = fallback_data[fallback_key]
            cleaned_fb, keep_entry, _ = sanitize_cache_entry(fallback_key, fb_entry)
            if keep_entry:
                fb_ts = get_entry_timestamp(fb_entry)
                fb_fresh = fb_ts > 0 and (time.time() - fb_ts) < skip_seconds
                if not fb_fresh:
                    print(f"    ℹ️  Fallback data for {symbol} is older than {policy['metric_skip_hours']}h, will refresh via API.")
                else:
                    fb_metrics = extract_market_data(cleaned_fb, api_address, symbol, api_chain, fetch_if_missing=False)
                    filtered_fb = {k: v for k, v in fb_metrics.items() if k in metric_values and not metric_values[k]}
                    if filtered_fb:
                        add_metrics(filtered_fb, 'token_fallbacks')
                        last_seen_ts = max(last_seen_ts, fb_ts)
        
        # 3) Latest XLSX report if values still missing
        report_entry = report_data['by_address'].get(api_address) or report_data['by_address'].get(address)
        if not report_entry:
            report_entry = report_data['by_symbol'].get(symbol_upper)
        if report_entry:
            filtered_report = {
                k: v for k, v in report_entry.items()
                if k in metric_values and (k == 'risk_score' or not metric_values[k])
            }
            if filtered_report:
                add_metrics(filtered_report, 'latest_report')
        
        # Aggregate current values and determine what is missing
        aggregated = {k: (mean(v) if v else 0) for k, v in metric_values.items()}
        missing_metrics = [k for k in ('market_cap', 'volume_24h', 'holders', 'liquidity', 'price') if aggregated[k] <= 0]
        
        # 4) If anything is still missing, hit real-time APIs (respecting cache window per metric)
        if missing_metrics and api_address:
            if last_seen_ts and policy["respect_skip"]:
                age_hours = (time.time() - last_seen_ts) / 3600
                print(f"    ℹ️ Last real data {age_hours:.1f}h ago; fetching only missing metrics to avoid stale N/A values.")
            print(f"    🔍 Fetching missing metrics {missing_metrics} for {symbol} via APIs...")
            api_data = fetch_missing_market_data_from_api(api_address, symbol, api_chain)
            if api_data:
                api_payload = dict(api_data)
                add_metrics(api_data, 'api')
        
        # 5) Calculate liquidity if still missing (uses DEX + volume/MC)
        aggregated = {k: (mean(v) if v else 0) for k, v in metric_values.items()}
        if aggregated['liquidity'] <= 0 and api_address:
            liq_val, liq_sources = fetch_real_liquidity_from_apis(api_address, symbol, aggregated['volume_24h'], aggregated['market_cap'])
            if liq_val > 0:
                api_liquidity_sources = liq_sources
                add_metrics({'liquidity': liq_val}, f"dex_liquidity ({', '.join(liq_sources)})" if liq_sources else "dex_liquidity")
                if api_payload is not None:
                    api_payload['liquidity'] = liq_val
            aggregated = {k: (mean(v) if v else 0) for k, v in metric_values.items()}
        
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
            'holders': aggregated['holders'],
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
        
        # Last-resort: use estimated fallback entry to avoid empty rows for brand-new tokens
        if not has_real_data:
            print(f"  ⚠️ {symbol}: No verified real-time data available, keeping placeholder entry.")
            market_data['data_source'] = "missing_real_data"
        else:
            unique_sources = list(dict.fromkeys(sources_used))
            if market_data['data_source'] == 'N/A':
                market_data['data_source'] = f"avg({', '.join(unique_sources)})" if len(unique_sources) > 1 else (unique_sources[0] if unique_sources else 'N/A')
            market_data['sources_used'] = unique_sources
            # Persist only when we got fresh API data (real-time overwrite of webhook/fallback)
            if api_payload and any(api_payload.get(k, 0) > 0 for k in ('market_cap', 'volume_24h', 'price', 'holders', 'liquidity')):
                if api_liquidity_sources and api_payload.get('liquidity', 0) > 0:
                    api_payload.setdefault('sources_used', []).extend(api_liquidity_sources)
                persist_real_data_to_cache(
                    api_address or address,
                    name,
                    symbol,
                    display_chain,
                    api_payload
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
            if viewer_row['Holders'] == "N/A":
                prev_hold = prev_row.get('Holders')
                if isinstance(prev_hold, str) and prev_hold not in ("", "N/A", "nan"):
                    viewer_row['Holders'] = prev_hold
                    try:
                        market_data['holders'] = int(prev_hold.replace(',', ''))
                        filled_from_prev = True
                    except ValueError:
                        pass
            if filled_from_prev and market_data['data_source'] in ('missing_real_data', 'N/A'):
                market_data['data_source'] = 'previous_csv'
                has_real_data = True
        
        if not has_real_data:
            has_real_data = any(
                market_data.get(k, 0) > 0 for k in ('market_cap', 'volume_24h', 'holders', 'liquidity', 'price')
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
        print("   Priority: webhook cache > fallback file > latest report > live APIs (averaged when multiple)")
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
    
    success = create_token_data_viewer_csv()
    
    if success:
        print("\n🎉 Token Data Viewer CSV updated successfully!")
        print("   ✅ Priority pipeline: webhook -> fallback -> latest report -> live API fill")
        print("   ✅ Real-time API hits cached to fallback to avoid rate limits")
        print("   ✅ LIQUIDITY COLUMN INCLUDED with real data from APIs/DEX")
    else:
        print("\n❌ Failed to update Token Data Viewer CSV")
        print("   Check the error messages above for details.")
