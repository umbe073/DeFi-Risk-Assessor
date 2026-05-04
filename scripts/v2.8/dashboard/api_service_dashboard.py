#!/usr/bin/env python3
"""
API Service Dashboard
Comprehensive dashboard for monitoring and controlling API services with categorization
"""

import sys
import os

# CRITICAL: Set unified app icon environment variables BEFORE any other imports
if sys.platform == "darwin":
    # CRITICAL: Force Python to hide from dock (MUST BE FIRST)
    os.environ['LSUIElement'] = 'true'
    os.environ['NSApplicationActivationPolicy'] = 'accessory'
    
    # Unified app icon environment variables with CORRECT bundle identifier
    os.environ['BUNDLE_IDENTIFIER'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['APP_BUNDLE'] = 'true'
    os.environ['CFBundleIdentifier'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['CFBundleName'] = 'Token Risk Assessment Tool'
    os.environ['CFBundleDisplayName'] = 'Token Risk Assessment Tool'
    os.environ['PARENT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['INHERIT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    
    # Performance optimizations
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    
    # Basic tkinter compatibility
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

# macOS compatibility - must be imported before tkinter
import sys
import os
if sys.platform == "darwin":
    # Import and apply macOS compatibility fix
    try:
        # Add the current directory to the path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Use tkinter compatibility module for macOS compatibility
        from tkinter_compatibility import tkinter_compat
        if tkinter_compat.is_compatible():
            print("✅ Tkinter compatibility verified")
        else:
            print("⚠️ Tkinter compatibility not available")
    except ImportError:
        # Fallback - just set basic environment variables
        os.environ['TK_SILENCE_DEPRECATION'] = '1'
        os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
        os.environ['TK_FRAMEWORK'] = '1'
        os.environ['DISPLAY'] = ':0'
        print("✅ Basic macOS compatibility applied")
    
    print("Running API dashboard with macOS compatibility")

import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
import time
import hmac
import hashlib
import base64
import requests
import tempfile
import signal
import subprocess
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

# App bundle mode is now handled by the macOS compatibility fix
# No need for separate dock utilities

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

CHAINABUSE_STANDARD_MONTH_SECONDS = 30 * 24 * 60 * 60
PROBE_COOLDOWN_MIN_SECONDS = 30
PROBE_COOLDOWN_MAX_SECONDS = CHAINABUSE_STANDARD_MONTH_SECONDS
CHAINABUSE_STANDARD_MONTHLY_CALLS = 10
CHAINABUSE_STANDARD_PROBE_SPACING_SECONDS = (
    CHAINABUSE_STANDARD_MONTH_SECONDS // CHAINABUSE_STANDARD_MONTHLY_CALLS
)
CHAINABUSE_PARTNER_PROBE_SPACING_SECONDS = 300


def _chainabuse_partner_tier_enabled() -> bool:
    tier = (
        str(os.environ.get("CHAINABUSE_RATE_LIMIT_TIER", "standard") or "")
        .strip()
        .lower()
    )
    return tier in {"partner", "premium", "law_enforcement", "law-enforcement", "le"}


def _chainabuse_live_probe_enabled() -> bool:
    """Return true when API Center may spend a ChainAbuse request on a live probe."""
    if _chainabuse_partner_tier_enabled():
        return True
    flag = (
        str(os.environ.get("CHAINABUSE_LIVE_PROBE_ENABLED", "") or "")
        .strip()
        .lower()
    )
    return flag in {"1", "true", "yes", "on"}


def _chainabuse_probe_spacing_seconds() -> int:
    if _chainabuse_partner_tier_enabled():
        return CHAINABUSE_PARTNER_PROBE_SPACING_SECONDS
    return CHAINABUSE_STANDARD_PROBE_SPACING_SECONDS


def _chainabuse_local_probe_message(service_name: str) -> str:
    """Message for the default non-consuming ChainAbuse API Center probe."""
    return (
        f"✅ {service_name}: CHAINABUSE_API_KEY is configured. Live API Center probes are disabled "
        "for standard ChainAbuse keys so the 10/month quota is reserved for the shared cache queue; "
        "cached assessment results remain available to paid plans."
    )


CUSTOMER_FACING_SERVICE_DESCRIPTIONS = {
    "etherscan": "Ethereum explorer and contract data",
    "infura": "Blockchain RPC infrastructure",
    "moralis": "On-chain token and wallet data",
    "alchemy": "Blockchain RPC and token data",
    "coingecko": "Crypto prices and market data",
    "coinmarketcap": "Crypto rankings and market data",
    "coinapi": "Crypto market and exchange data",
    "coinpaprika": "Crypto prices and market data",
    "birdeye": "Token pricing and liquidity data",
    "coincap": "Crypto prices and market data",
    "dexscreener": "DEX liquidity and pair data",
    "ethplorer": "Ethereum token and holder data",
    "santiment": "On-chain and sentiment analytics",
    "solscan": "Solana explorer and token data",
    "solanatracker": "Solana token and holder data",
    "zapper": "DeFi portfolio and protocol data",
    "debank": "DeFi portfolio and protocol data",
    "oneinch": "DEX aggregation and token data",
    "lifi": "Cross-chain route and bridge data",
    "breadcrumbs": "Address risk and sanctions screening",
    "certik": "Smart contract security intelligence",
    "chainalysis_oracle": "Sanctions screening reference",
    "honeypot": "Honeypot and token-tax screening",
    "ofac_sls": "Sanctions list screening",
    "scamsniffer": "Scam address intelligence",
    "twitter": "Social sentiment and trend data",
    "discord": "Community activity signals",
    "telegram": "Community activity signals",
    "reddit": "Community sentiment signals",
    "arkham": "On-chain entity intelligence",
    "oklink": "Address labels and risk intelligence",
    "goplus": "Token and address security checks",
    "trmlabs": "Sanctions and risk screening",
    "chainabuse": "Shared abuse-report cache",
    "thegraph": "Indexed blockchain protocol data",
    "dune": "On-chain analytics and query data",
    "bitcointalk": "Forum discussion signals",
    "cointelegraph": "Crypto news signals",
    "coindesk": "Crypto news signals",
    "theblock": "Crypto news signals",
    "decrypt": "Crypto news signals",
    "defillama": "DeFi protocol and TVL data",
    "defi_api": "Token security and scanner data",
}


def _chainabuse_probe_cooldown_after_429_seconds() -> float:
    default = (
        CHAINABUSE_PARTNER_PROBE_SPACING_SECONDS
        if _chainabuse_partner_tier_enabled()
        else CHAINABUSE_STANDARD_MONTH_SECONDS
    )
    raw = os.environ.get("CHAINABUSE_PROBE_COOLDOWN_AFTER_429")
    try:
        wait = float(raw) if raw is not None else float(default)
    except (TypeError, ValueError):
        wait = float(default)
    if _chainabuse_partner_tier_enabled():
        return max(30.0, wait)
    # Standard ChainAbuse keys are quota-limited monthly; a 429 usually means
    # the monthly bucket is exhausted, not a short rolling window.
    return max(float(CHAINABUSE_STANDARD_MONTH_SECONDS), wait)


def _load_env_for_probes() -> None:
    """Load suite and web portal dotenv files for API probes."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = os.path.dirname(os.path.abspath(__file__))
    scripts_v20 = os.path.dirname(here)
    scripts_dir = os.path.dirname(scripts_v20)
    suite_root = os.path.dirname(scripts_dir)
    web_portal = os.path.join(suite_root, 'scripts', 'v2.0', 'web_portal')
    forced = str(os.environ.get('HODLER_SUITE_ENV_FILE', '') or '').strip()
    candidates = [
        forced,
        os.path.join(suite_root, '.env'),
        os.path.join(web_portal, '.env'),
        os.path.join(web_portal, 'web_portal.env'),
        os.path.join(suite_root, 'web_portal', 'web_portal.env'),
        os.path.join(suite_root, 'web_portal', '.env'),
        '/etc/hodler-suite/web_portal.env',
        '/etc/hodler-suite/hodler-suite.env',
    ]
    seen: set[str] = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path):
            load_dotenv(path, override=False)
    try:
        import sys

        if web_portal not in sys.path:
            sys.path.insert(0, web_portal)
        from app.credentials_vault import apply_credentials_vault_if_configured

        apply_credentials_vault_if_configured()
    except Exception:
        pass


def _normalize_chainabuse_key_for_basic_auth(raw: str) -> str:
    """Strip BOM, quotes, and mistaken auth prefixes from env values before Basic auth."""
    key = str(raw or "").replace("\ufeff", "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {'"', "'"}:
        key = key[1:-1].strip()
    lowered = key.lower()
    if lowered.startswith("bearer "):
        key = key[7:].strip()
    elif lowered.startswith("basic "):
        key = key[6:].strip()
    return key


def _chainabuse_basic_authorization_header(raw_api_key: str) -> str:
    """Basic with empty password (OpenAPI / ``curl --user KEY:``)."""
    user = _normalize_chainabuse_key_for_basic_auth(raw_api_key)
    return "Basic " + base64.b64encode(f"{user}:".encode("utf-8")).decode("ascii")


def _chainabuse_basic_authorization_header_dual(raw_api_key: str) -> str:
    """Basic with API key as both username and password (Chainabuse getting-started docs)."""
    user = _normalize_chainabuse_key_for_basic_auth(raw_api_key)
    return "Basic " + base64.b64encode(f"{user}:{user}".encode("utf-8")).decode("ascii")


def _chainabuse_reports_url() -> str:
    """Resolve GET reports URL; tolerate ``CHAINABUSE_BASE_URL`` already ending in ``/v0``."""
    raw = (os.getenv("CHAINABUSE_BASE_URL") or "https://api.chainabuse.com").strip().rstrip("/")
    if raw.lower().endswith("/v0"):
        return f"{raw}/reports"
    return f"{raw}/v0/reports"


def _chainabuse_json_error_hint(response) -> str:
    """Return a short JSON ``message``/``reason`` from Chainabuse error bodies (e.g. 401)."""
    if response is None:
        return ""
    try:
        data = response.json()
        if isinstance(data, dict):
            msg = str(
                data.get("message") or data.get("reason") or data.get("error") or ""
            ).strip()
            if msg:
                return msg[:200]
    except Exception:
        pass
    return ""


def _probe_http_timeout_seconds(service_id: str) -> int:
    """HTTP read timeout for dashboard probes (some public hosts are slow under audit load)."""
    sid = (service_id or "").strip().lower()
    if sid == "defillama":
        raw = (os.getenv("DEFILLAMA_PROBE_TIMEOUT_SECONDS") or "35").strip()
        try:
            return max(10, int(float(raw)))
        except (TypeError, ValueError):
            return 35
    return 10


def _parse_retry_after_seconds(response) -> float | None:
    """Parse ``Retry-After`` as delta-seconds or HTTP-date; return seconds to wait or None."""
    if response is None:
        return None
    raw = response.headers.get("Retry-After") if hasattr(response, "headers") else None
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        secs = float(text)
        if secs > 0:
            return min(
                float(PROBE_COOLDOWN_MAX_SECONDS),
                max(float(PROBE_COOLDOWN_MIN_SECONDS), secs),
            )
    except (TypeError, ValueError):
        pass
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            return min(
                float(PROBE_COOLDOWN_MAX_SECONDS),
                max(float(PROBE_COOLDOWN_MIN_SECONDS), delta),
            )
    except Exception:
        pass
    return None


def _record_probe_cooldown_after_429(service_id: str, response) -> None:
    """Mirror provider rate limits into ``rate_limits.json`` for API Center cooldown display."""
    sid = str(service_id or "").strip().lower()
    if not sid:
        return
    wait = _parse_retry_after_seconds(response)
    if wait is None:
        if sid == "chainabuse":
            wait = _chainabuse_probe_cooldown_after_429_seconds()
        else:
            try:
                wait = float(os.environ.get("API_PROBE_COOLDOWN_AFTER_429", "120") or 120)
            except (TypeError, ValueError):
                wait = 120.0
    try:
        from app.api_service_manager import record_probe_cooldown_until
    except Exception:
        return
    try:
        record_probe_cooldown_until(sid, seconds=float(wait))
    except Exception:
        return


class APIServiceDashboard:
    def __init__(self):
        try:
            self.root = tk.Tk()
        except Exception as e:
            # Fallback error window if tkinter fails
            print(f"Error initializing tkinter: {e}")
            return
            
        self.setup_window()
        self.services = self.initialize_services()
        self.auto_refresh_enabled = False
        self.auto_refresh_interval = 300  # 5 minutes default
        self.auto_refresh_job = None
        self.auto_trigger_enabled = False
        self.create_widgets()
        # Don't start update_service_status immediately - start it after mainloop begins
        
        # Set up window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_window(self):
        """Setup the dashboard window"""
        self.root.title("DeFi API Service Dashboard")
        self.root.geometry("900x800")
        
        # Configure window attributes for better behavior
        if sys.platform == "darwin":
            # On macOS, avoid problematic window attributes that cause hanging
            try:
                # Don't set window type to dialog as it causes mainloop to hang
                # Just set basic attributes
                self.root.wm_attributes('-topmost', False)
            except:
                # Fallback: just keep window behavior normal
                pass
        self.root.resizable(True, True)
        
        # Bring window to front (simplified)
        self.root.lift()
        
        # Modern styling - use try-except to avoid crashes
        try:
            style = ttk.Style()
            style.theme_use('clam')
            
            # Configure custom styles
            style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#2c3e50')
            style.configure('Category.TLabel', font=('Arial', 12, 'bold'), foreground='#34495e')
            style.configure('Service.TLabel', font=('Arial', 10, 'bold'))
            style.configure('Status.TLabel', font=('Arial', 10))
            style.configure('Available.TLabel', foreground='#27ae60', font=('Arial', 10, 'bold'))
            style.configure('Limited.TLabel', foreground='#f39c12', font=('Arial', 10, 'bold'))
            style.configure('Unavailable.TLabel', foreground='#e74c3c', font=('Arial', 10, 'bold'))
        except Exception as e:
            print(f"Warning: Could not configure styles: {e}")
            # Continue without custom styling
        
    def initialize_services(self):
        """Initialize API service configurations organized by category"""
        services = {
            # === BLOCKCHAIN INFRASTRUCTURE ===
            'etherscan': {
                'name': 'Etherscan API',
                'env_key': 'ETHERSCAN_API_KEY',
                'category': '🔗 Blockchain Infrastructure',
                'rate_limit': 5,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.etherscan.io/v2/api?chainid=1&module=stats&action=ethsupply&apikey=',
                'description': 'Ethereum blockchain explorer & contract data'
            },
            'infura': {
                'name': 'Infura API',
                'env_key': 'INFURA_API_KEY',
                'category': '🔗 Blockchain Infrastructure',
                'rate_limit': 100000,
                'rate_period': 86400,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://mainnet.infura.io/v3/{}',
                'description': 'Ethereum node infrastructure & RPC access'
            },
            'moralis': {
                'name': 'Moralis API',
                'env_key': 'MORALIS_API_KEY',
                'category': '🔗 Blockchain Infrastructure',
                'rate_limit': 25,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://deep-index.moralis.io/api/v2/erc20/metadata?chain=eth&addresses=0xdAC17F958D2ee523a2206206994597C13D831ec7',
                'description': 'Web3 blockchain data & NFT metadata'
            },
            'alchemy': {
                'name': 'Alchemy API',
                'env_key': 'ALCHEMY_API_KEY',
                'category': '🔗 Blockchain Infrastructure',
                'rate_limit': 100,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://eth-mainnet.g.alchemy.com/v2/{}',
                'description': 'Enhanced blockchain infrastructure & analytics'
            },

            # === MARKET DATA ===
            'coingecko': {
                'name': 'CoinGecko API',
                'env_key': 'COINGECKO_API_KEY',
                'category': '📊 Market Data',
                'rate_limit': 30,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
                'description': 'Cryptocurrency prices, market cap, volume (2025 v3 API)'
            },
            'coinmarketcap': {
                'name': 'CoinMarketCap API',
                'env_key': 'COINMARKETCAP_API_KEY',
                'category': '📊 Market Data',
                'rate_limit': 333,
                'rate_period': 86400,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol=BTC',
                'description': 'Comprehensive crypto market data & rankings (2025 v2 API)'
            },
            'coinapi': {
                'name': 'CoinAPI',
                'env_key': 'COINAPI_API_KEY',
                'category': '📊 Market Data',
                'rate_limit': 1000,
                'rate_period': 86400,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://rest.coinapi.io/v1/exchangerate/BTC/USD',
                'description': 'Institutional-grade crypto market data & exchange rates (REST API)'
            },
            'coinpaprika': {
                'name': 'Coinpaprika API',
                'env_key': None,
                'category': '📊 Market Data',
                'rate_limit': 20000,
                'rate_period': 86400,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.coinpaprika.com/v1/tickers/btc-bitcoin',
                'description': 'Alternative crypto market data & historical prices (Free - No API key required)'
            },
            'birdeye': {
                'name': 'BirdEye API',
                'env_key': 'BIRDEYE_API_KEY',
                'category': '📊 Market Data',
                'rate_limit': 60,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://public-api.birdeye.so/defi/networks',
                'description': 'Solana token liquidity, pricing & holder analytics'
            },
            'coincap': {
                'name': 'CoinCap API',
                'env_key': 'COINCAP_API_KEY',
                'category': '📊 Market Data',
                'rate_limit': 200,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.coincap.io/v2/assets?limit=1',
                'description': 'Market data; optional COINCAP_API_KEY for v3 (Bearer), else public v2 tier',
            },
            'dexscreener': {
                'name': 'DexScreener API',
                'env_key': None,
                'category': '📊 Market Data',
                'rate_limit': 300,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.dexscreener.com/latest/dex/tokens/0x0000000000000000000000000000000000000000',
                'description': 'DEX pairs, liquidity & price discovery (no API key required)'
            },

            # === BLOCKCHAIN ANALYTICS ===
            'ethplorer': {
                'name': 'Ethplorer API',
                'env_key': 'ETHPLORER_API_KEY',
                'category': '📈 Blockchain Analytics',
                'rate_limit': 5,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.ethplorer.io/getTokenInfo/0xdAC17F958D2ee523a2206206994597C13D831ec7?apiKey=',
                'description': 'Ethereum token analytics & holder insights'
            },
            'santiment': {
                'name': 'Santiment API',
                'env_key': 'SANTIMENT_API_KEY',
                'category': '📈 Blockchain Analytics',
                'rate_limit': 60,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.santiment.net/graphql',
                'description': 'Social sentiment, dev activity & on-chain metrics'
            },
            'solscan': {
                'name': 'Solscan API',
                'env_key': 'SOLSCAN_API_KEY',
                'category': '📈 Blockchain Analytics',
                'rate_limit': 60,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://public-api.solscan.io/chaininfo',
                'description': 'Solana explorer; public chaininfo or Pro probe via SOLSCAN_PROBE_USE_PRO_API.',
            },
            'solanatracker': {
                'name': 'SolanaTracker API',
                'env_key': 'SOLANATRACKER_API_KEY',
                'category': '📈 Blockchain Analytics',
                'rate_limit': 60,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': (
                    'https://data.solanatracker.io/tokens/'
                    'So11111111111111111111111111111111111111112/holders'
                ),
                'description': 'Solana token holder & liquidity metrics'
            },

            # === DEFI PROTOCOLS ===
            'zapper': {
                'name': 'Zapper API',
                'env_key': 'ZAPPER_API_KEY',
                'category': '🔄 DeFi Protocols',
                'rate_limit': 10,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://public.zapper.xyz/graphql',
                'description': 'DeFi portfolio tracking & yield analytics (GraphQL API)'
            },
            'debank': {
                'name': 'DeBank API',
                'env_key': 'DEBANK_API_KEY',
                'category': '🔄 DeFi Protocols',
                'rate_limit': 5,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://pro-openapi.debank.com/v1/user/token_list?id=0x5853ed4f26a3fcea565b3fbc698bb19cdf6deb85',
                'description': (
                    'DeFi portfolio & protocol data; key from cloud.debank.com (probe uses AccessKey header)'
                )
            },
            'oneinch': {
                'name': '1inch API',
                'env_key': 'INCH_API_KEY',
                'category': '🔄 DeFi Protocols',
                'rate_limit': 10,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.1inch.com/swap/v6.0/1/tokens',
                'description': 'DEX aggregation & best swap route optimization (2025 v6.0 API)'
            },
            'lifi': {
                'name': 'LI.FI API',
                'env_key': 'LI_FI_API_KEY',
                'category': '🔄 DeFi Protocols',
                'rate_limit': 60,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://li.quest/v1/chains',
                'description': 'Cross-chain swap & bridge routing (LI.FI)'
            },

            # === SECURITY & COMPLIANCE ===
            'breadcrumbs': {
                'name': 'Breadcrumbs API',
                'env_key': 'BREADCRUMBS_API_KEY',
                'category': '🛡️ Security & Compliance',
                'rate_limit': 100,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.breadcrumbs.one/risk/address',
                'description': 'Sanctions & illicit-activity screening (risk endpoint)'
            },
            'certik': {
                'name': 'CertiK API',
                'env_key': 'CERTIK_API_KEY',
                'category': '🛡️ Security & Compliance',
                'rate_limit': 100,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': None,
                'description': 'Smart contract security audits & vulnerability data'
            },
            'chainalysis_oracle': {
                'name': 'Chainalysis Sanctions Oracle',
                'env_key': None,
                'category': '🛡️ Security & Compliance',
                'rate_limit': 30,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://www.chainalysis.com/',
                'description': 'Sanctions oracle reference & contract catalog (website reachability)'
            },
            'honeypot': {
                'name': 'Honeypot.is API',
                'env_key': None,
                'category': '🛡️ Security & Compliance',
                'rate_limit': 30,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': (
                    'https://api.honeypot.is/v2/IsHoneypot?address='
                    '0xdAC17F958D2ee523a2206206994597C13D831ec7&chainId=1'
                ),
                'description': 'Token honeypot / sell-tax simulation (public endpoint)'
            },
            'ofac_sls': {
                'name': 'OFAC Sanctions List Service',
                'env_key': None,
                'category': '🛡️ Security & Compliance',
                'rate_limit': 10,
                'rate_period': 3600,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': (
                    'https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/sdn.csv'
                ),
                'description': 'US Treasury OFAC SDN export (public CSV endpoint)'
            },
            'scamsniffer': {
                'name': 'ScamSniffer Dataset',
                'env_key': None,
                'category': '🛡️ Security & Compliance',
                'rate_limit': 20,
                'rate_period': 3600,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': (
                    'https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/address.json'
                ),
                'description': 'Community scam address blacklist (GitHub raw JSON)'
            },

            # === SOCIAL & SENTIMENT ===
            'twitter': {
                'name': 'Twitter API',
                'env_key': 'TWITTER_BEARER_TOKEN',
                'category': '📱 Social & Sentiment',
                'rate_limit': 300,
                'rate_period': 900,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.twitter.com/2/users/by/username/elonmusk',
                'description': 'Social media sentiment analysis & trending topics'
            },
            'discord': {
                'name': 'Discord API',
                'env_key': 'DISCORD_BOT_TOKEN',
                'category': '📱 Social & Sentiment',
                'rate_limit': 50,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://discord.com/api/v10/users/@me',
                'description': 'Discord server data & community engagement metrics'
            },
            'telegram': {
                'name': 'Telegram API',
                'env_key': 'TELEGRAM_BOT_TOKEN',
                'category': '📱 Social & Sentiment',
                'rate_limit': 30,
                'rate_period': 1,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.telegram.org/bot{}/getMe',
                'description': 'Telegram channel data & crypto discussions'
            },
            'reddit': {
                'name': 'Reddit API',
                'env_key': 'REDDIT_CLIENT_ID',
                'secondary_key': 'REDDIT_CLIENT_SECRET',
                'category': '📱 Social & Sentiment',
                'rate_limit': 100,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://oauth.reddit.com/api/v1/me',
                'description': 'Reddit posts, comments & community sentiment'
            },
            'arkham': {
                'name': 'Arkham API',
                'env_key': 'ARKHAM_API_KEY',
                'category': '🔍 Intelligence & Research',
                'rate_limit': 100,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.arkm.com/intelligence/address/0xdAC17F958D2ee523a2206206994597C13D831ec7',
                'description': 'On-chain intelligence & entity identification'
            },
            'oklink': {
                'name': 'OKLink API',
                'env_key': 'OKLINK_API_KEY',
                'category': '🔍 Intelligence & Research',
                'rate_limit': 100,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://www.oklink.com/api/v5/tracker/kya/chain-list',
                'description': 'Address risk intelligence, labels, and compliance analytics'
            },
            'goplus': {
                'name': 'GoPlus Security API',
                'env_key': None,
                'category': '🔍 Intelligence & Research',
                'rate_limit': 60,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': (
                    'https://api.gopluslabs.io/api/v1/address_security/'
                    '0xdAC17F958D2ee523a2206206994597C13D831ec7'
                ),
                'description': 'Malicious address & contract risk intelligence (free public tier)'
            },
            'trmlabs': {
                'name': 'TRM Labs Sanctions API',
                'env_key': 'TRMLABS_API_KEY',
                'category': '🔍 Intelligence & Research',
                'rate_limit': 100,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.trmlabs.com/public/v1/sanctions/screening',
                'description': 'Sanctions screening (optional API key for higher throughput)'
            },
            'chainabuse': {
                'name': 'Chainabuse API',
                'env_key': 'CHAINABUSE_API_KEY',
                'category': '🔍 Intelligence & Research',
                'rate_limit': (
                    5000
                    if _chainabuse_partner_tier_enabled()
                    else CHAINABUSE_STANDARD_MONTHLY_CALLS
                ),
                'rate_period': (
                    3600
                    if _chainabuse_partner_tier_enabled()
                    else CHAINABUSE_STANDARD_MONTH_SECONDS
                ),
                'probe_request_budget': 1,
                'probe_cooldown_seconds': _chainabuse_probe_spacing_seconds(),
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.chainabuse.com/v0/reports',
                'description': (
                    'Shared abuse-report cache; standard API Center probe is local to preserve the 10/month quota.'
                ),
            },
            'thegraph': {
                'name': 'The Graph API',
                'env_key': 'THE_GRAPH_API_KEY',
                'category': '📈 Blockchain Analytics',
                'rate_limit': 1000,
                'rate_period': 3600,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://gateway.thegraph.com/api/{}/subgraphs/id/DZz4kDTdmzWLWsV373w2bSmoar3umKKH9y82SUKr5qmp',
                'description': 'Decentralized protocol for indexing blockchain data'
            },
            'dune': {
                'name': 'Dune Analytics API',
                'env_key': 'DUNE_API_KEY',
                'category': '📈 Blockchain Analytics',
                'rate_limit': 100,
                'rate_period': 3600,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://api.dune.com/api/v1/query/{}/results?limit=1',
                'description': 'Dune Cloud SQL plus SIM EVM; use DUNE_USE_SIM_API or env defaults.',
            },
            'bitcointalk': {
                'name': 'Bitcointalk Scraper',
                'env_key': None,
                'category': '📰 News & Research',
                'rate_limit': 10,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://bitcointalk.org/index.php?action=recent',
                'description': 'Bitcoin forum discussions & project announcements'
            },
            'cointelegraph': {
                'name': 'Cointelegraph Scraper',
                'env_key': 'COINTELEGRAPH_USER_AGENT',
                'category': '📰 News & Research',
                'rate_limit': 30,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://cointelegraph.com/rss',
                'description': 'Crypto news & market analysis articles'
            },
            'coindesk': {
                'name': 'CoinDesk RSS',
                'env_key': None,
                'category': '📰 News & Research',
                'rate_limit': 10,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
                'description': 'Crypto news RSS feed & market insights'
            },
            'theblock': {
                'name': 'The Block API',
                'env_key': None,
                'category': '📰 News & Research',
                'rate_limit': 20,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://www.theblock.co/api/content',
                'description': 'Crypto news articles & market analysis'
            },
            'decrypt': {
                'name': 'Decrypt RSS',
                'env_key': None,
                'category': '📰 News & Research',
                'rate_limit': 15,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://decrypt.co/feed',
                'description': 'Crypto news RSS feed & educational content'
            },
            'defillama': {
                'name': 'DeFiLlama API',
                'env_key': None,
                'category': '📊 Market Data',
                'rate_limit': 100,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                # Small JSON probe (``/protocols`` often exceeds read timeouts on busy hosts).
                'test_endpoint': (
                    'https://coins.llama.fi/prices/current/'
                    'ethereum:0xdAC17F958D2ee523a2206206994597C13D831ec7'
                ),
                'description': 'DeFi TVL, protocol data & yield farming info (Free)'
            },
            'defi_api': {
                'name': 'De.Fi API',
                'env_key': 'DEFI_API_KEY',
                'category': '📊 Market Data',
                'rate_limit': 60,
                'rate_period': 60,
                'last_call': 0,
                'calls_count': 0,
                'test_endpoint': 'https://public-api.de.fi/graphql',
                'description': 'De.Fi GraphQL (Shield, Scanner, chain metadata); authenticate with X-Api-Key'
            }
        }
        for sid, description in CUSTOMER_FACING_SERVICE_DESCRIPTIONS.items():
            if sid in services:
                services[sid]['description'] = description
        return services

    def _api_runtime_dir(self) -> str:
        """Writable API runtime dir (matches web portal ``resolve_api_runtime_dir`` when env is set)."""
        env_dir = str(os.environ.get("API_SERVICE_RUNTIME_DIR", "") or "").strip()
        if env_dir:
            return env_dir
        return os.path.join(DATA_DIR, "api_runtime")

    def load_service_toggles(self) -> None:
        """Merge persisted enable/disable flags from ``service_toggles.json`` into ``self.services``."""
        path = os.path.join(self._api_runtime_dir(), "service_toggles.json")
        if not os.path.isfile(path):
            return
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return
        raw = data.get("services", data) if isinstance(data, dict) else {}
        if not isinstance(raw, dict):
            return
        for service_id, enabled in raw.items():
            sid = str(service_id or "").strip().lower()
            if sid in self.services:
                self.services[sid]["enabled"] = bool(enabled)

    def export_service_registry(self) -> None:
        """Write ``api_services_registry.json`` for the web portal API Center (``load_service_registry``)."""
        runtime = self._api_runtime_dir()
        os.makedirs(runtime, exist_ok=True)
        path = os.path.join(runtime, "api_services_registry.json")
        services_out = []
        for service_id, svc in self.services.items():
            sid = str(service_id or "").strip().lower()
            if not sid:
                continue
            row: dict = {
                "id": sid,
                "name": str(svc.get("name", sid)).strip() or sid,
                "category": str(svc.get("category", "Other")).strip() or "Other",
                "description": str(svc.get("description", "")).strip(),
                "enabled": bool(svc.get("enabled", True)),
                "env_key": svc.get("env_key"),
                "reference_url": str(svc.get("reference_url", "") or "").strip(),
            }
            for probe_key in ("rate_limit", "rate_period", "probe_request_budget", "probe_cooldown_seconds"):
                if probe_key not in svc:
                    continue
                val = svc.get(probe_key)
                if val is None:
                    continue
                try:
                    num = int(val)
                except (TypeError, ValueError):
                    continue
                if num > 0:
                    row[probe_key] = num
            services_out.append(row)
        payload = {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "service_count": len(services_out),
            "services": services_out,
        }
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError as exc:
            print(f"Warning: could not export API service registry: {exc}")
        
    def create_widgets(self):
        """Create all dashboard widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="API Service Control Dashboard", style='Title.TLabel')
        title_label.grid(row=0, column=0, pady=(0, 20), sticky=tk.W)
        
        # Services frame with scrollbar
        services_container = ttk.Frame(main_frame)
        services_container.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        services_container.columnconfigure(0, weight=1)
        services_container.rowconfigure(0, weight=1)
        
        # Canvas and scrollbar for services
        canvas = tk.Canvas(services_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(services_container, orient="vertical", command=canvas.yview)
        self.services_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        canvas_frame = canvas.create_window((0, 0), window=self.services_frame, anchor="nw")
        
        # Configure scrolling
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def configure_canvas_width(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_frame, width=canvas_width)
            
        self.services_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_canvas_width)
        
        # Create service widgets
        self.service_widgets = {}
        self.create_service_widgets()
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, sticky="ew")
        control_frame.columnconfigure(4, weight=1)
        
        # Refresh all button
        refresh_btn = ttk.Button(control_frame, text="🔄 Refresh All Services", command=self.refresh_all_services)
        refresh_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Test all button
        test_btn = ttk.Button(control_frame, text="🧪 Test All Available", command=self.test_all_services)
        test_btn.grid(row=0, column=1, padx=(0, 10))
        
        # Auto-refresh settings button
        auto_btn = ttk.Button(control_frame, text="⚙️ Auto-Refresh Settings", command=self.open_auto_refresh_settings)
        auto_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Close button
        close_btn = ttk.Button(control_frame, text="❌ Close", command=self.close_dashboard)
        close_btn.grid(row=0, column=4)
        
    def create_service_widgets(self):
        """Create widgets for each API service grouped by category"""
        self.services_frame.columnconfigure(0, weight=1)
        
        # Group services by category
        categories = {}
        for service_id, service in self.services.items():
            category = service.get('category', 'Other')
            if category not in categories:
                categories[category] = []
            categories[category].append((service_id, service))
        
        row = 0
        
        # Create widgets for each category
        for category, services in categories.items():
            # Category header
            category_frame = ttk.LabelFrame(self.services_frame, text=category, padding="15")
            category_frame.grid(row=row, column=0, sticky="ew", pady=(0, 15))
            category_frame.columnconfigure(0, weight=1)
            
            sub_row = 0
            for service_id, service in services:
                # Service container frame within category
                service_frame = ttk.Frame(category_frame, padding="10")
                service_frame.grid(row=sub_row, column=0, sticky="ew", pady=(0, 8))
                service_frame.columnconfigure(1, weight=1)
                
                # Status indicator (colored dot)
                status_canvas = tk.Canvas(service_frame, width=20, height=20, highlightthickness=0)
                status_canvas.grid(row=0, column=0, padx=(0, 10))
                
                # Service name and description
                name_frame = ttk.Frame(service_frame)
                name_frame.grid(row=0, column=1, sticky="ew")
                name_frame.columnconfigure(0, weight=1)
                
                name_label = ttk.Label(name_frame, text=service['name'], style='Service.TLabel')
                name_label.grid(row=0, column=0, sticky=tk.W)
                
                desc_label = ttk.Label(name_frame, text=service['description'], style='Status.TLabel')
                desc_label.grid(row=1, column=0, sticky=tk.W)
                
                # Rate limit countdown
                countdown_label = ttk.Label(service_frame, text="Ready", style='Available.TLabel')
                countdown_label.grid(row=0, column=2, padx=(10, 10))
                
                # Manual trigger button
                trigger_btn = ttk.Button(service_frame, text="🔄 Fetch Data", 
                                       command=lambda sid=service_id: self.trigger_service(sid))
                trigger_btn.grid(row=0, column=3)
                
                # Store widget references
                self.service_widgets[service_id] = {
                    'frame': service_frame,
                    'status_canvas': status_canvas,
                    'countdown_label': countdown_label,
                    'trigger_btn': trigger_btn,
                    'name_label': name_label
                }
                
                sub_row += 1
            
            row += 1
    
    def get_service_status(self, service_id):
        """Get the current status of a service with detailed countdown"""
        service = self.services[service_id]
        
        # Check if API key is available (special handling for optional keys)
        if service['env_key']:
            api_key = os.getenv(service['env_key'])
            # Special case for CoinGecko - free tier doesn't require key
            if not api_key and service_id not in ('coingecko', 'coincap'):
                return 'unavailable', 'No API key configured'
            
            # Special case for Reddit - also check secondary key
            if service_id == 'reddit' and api_key:
                secondary_key = service.get('secondary_key')
                if secondary_key and not os.getenv(secondary_key):
                    return 'unavailable', 'Reddit client secret not configured'
        
        # Check rate limiting with detailed time formatting
        current_time = time.time()
        time_since_last = current_time - service['last_call']
        
        if service['last_call'] > 0 and time_since_last < service['rate_period']:
            if service['calls_count'] >= service['rate_limit']:
                remaining = service['rate_period'] - time_since_last
                
                # Format time display based on duration
                if remaining > 3600:  # More than 1 hour
                    hours = int(remaining // 3600)
                    minutes = int((remaining % 3600) // 60)
                    time_str = f"{hours}h {minutes}m"
                elif remaining > 60:  # More than 1 minute
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    time_str = f"{minutes}m {seconds}s"
                else:  # Less than 1 minute
                    time_str = f"{remaining:.0f}s"
                
                return 'limited', time_str
            else:
                # Still within rate period but calls available
                remaining = service['rate_period'] - time_since_last
                if remaining > 60:
                    minutes = int(remaining // 60)
                    time_str = f"Next: {minutes}m"
                else:
                    time_str = f"Next: {remaining:.0f}s"
                return 'available', time_str
        else:
            # Reset counter if period has passed
            service['calls_count'] = 0
            if time_since_last >= service['rate_period']:
                service['last_call'] = 0  # Reset for fresh start
        
        return 'available', 'Ready'
    
    def update_service_status(self):
        """Update the status display for all services"""
        for service_id, widgets in self.service_widgets.items():
            status, message = self.get_service_status(service_id)
            
            # Update status dot color
            canvas = widgets['status_canvas']
            canvas.delete("all")
            
            if status == 'available':
                color = '#27ae60'  # Green
                widgets['countdown_label'].config(text=message, style='Available.TLabel')
                widgets['trigger_btn'].config(state='normal')
            elif status == 'limited':
                color = '#f39c12'  # Orange
                widgets['countdown_label'].config(text=message, style='Limited.TLabel')
                widgets['trigger_btn'].config(state='disabled')
            else:  # unavailable
                color = '#e74c3c'  # Red
                widgets['countdown_label'].config(text=message, style='Unavailable.TLabel')
                widgets['trigger_btn'].config(state='disabled')
            
            # Draw status dot
            canvas.create_oval(5, 5, 15, 15, fill=color, outline=color)
        
        # Schedule next update
        self.root.after(1000, self.update_service_status)  # Update every second
    
    def trigger_service(self, service_id):
        """Manually trigger data fetch for a specific service"""
        service = self.services[service_id]
        
        # Check if service is available
        status, message = self.get_service_status(service_id)
        if status != 'available':
            messagebox.showwarning("Service Unavailable", f"{service['name']} is not available: {message}")
            return
        
        # Update rate limiting
        current_time = time.time()
        service['last_call'] = current_time
        service['calls_count'] += 1
        
        # Show loading state
        widgets = self.service_widgets[service_id]
        widgets['trigger_btn'].config(text="⏳ Fetching...", state='disabled')
        
        # Run fetch in background thread
        thread = threading.Thread(target=self._fetch_service_data, args=(service_id,), daemon=True)
        thread.start()
    
    def _probe_format_response(self, service_id, service, response, last_request_exception):
        """Map HTTP probe outcome to user-facing success flag and summary (API Center / dashboard)."""
        success = False
        message = ""
        # Check response
        if response is not None:
            if response.status_code in (200, 201):
                if service_id == 'oklink':
                    try:
                        payload = response.json()
                        ok_code = str(payload.get('code', '')).strip()
                        ok_msg = str(payload.get('msg', '')).strip()
                    except Exception:
                        ok_code = ''
                        ok_msg = ''

                    if ok_code and ok_code != '0':
                        success = True
                        message = f"⚠️ {service['name']}: API reachable but returned code {ok_code} ({ok_msg or 'see OKLink docs'})"
                    else:
                        success = True
                        message = f"✅ Success: {service['name']} responded correctly"
                elif service_id == 'defi_api':
                    try:
                        payload_json = response.json()
                    except Exception:
                        payload_json = {}
                    errs = payload_json.get('errors') if isinstance(payload_json, dict) else None
                    if errs:
                        success = False
                        message = f"❌ {service['name']}: GraphQL returned errors"
                    else:
                        success = True
                        message = f"✅ Success: {service['name']} responded correctly"
                elif service_id == 'dune':
                    success = True
                    rurl = str(getattr(response, "url", "") or "")
                    resp_host = (urlparse(rurl).hostname or "").lower()
                    if resp_host == "api.sim.dune.com":
                        message = (
                            f"✅ Success: {service['name']} (SIM on api.sim.dune.com; matches DUNE_SIM_* usage)"
                        )
                    else:
                        message = f"✅ Success: {service['name']} responded correctly"
                else:
                    success = True
                    message = f"✅ Success: {service['name']} responded correctly"
            elif (
                response.status_code in [401, 402, 403, 404, 422, 429, 500, 550]
                and service_id in [
                    'moralis',
                    'twitter',
                    'zapper',
                    'breadcrumbs',
                    'reddit',
                    'dune',
                    'coinapi',
                    'oklink',
                    'chainabuse',
                    'trmlabs',
                    'birdeye',
                    'lifi',
                    'solanatracker',
                    'solscan',
                    'debank',
                ]
            ):
                # For selected APIs, these statuses still confirm connectivity/auth endpoint health.
                success = True
                if service_id == 'moralis':
                    message = f"✅ {service['name']}: Connection successful (free plan limit reached)"
                elif service_id == 'zapper':
                    if response.status_code == 500:
                        message = f"⚠️ {service['name']}: GraphQL endpoint reachable (request shape rejected)"
                    elif response.status_code == 404:
                        message = f"⚠️ {service['name']}: Endpoint changed but service is reachable"
                    else:
                        message = f"✅ {service['name']}: Connection successful (API reachable)"
                elif service_id == 'breadcrumbs':
                    if response.status_code == 404:
                        message = f"⚠️ {service['name']}: Endpoint not found on this host, service reachable"
                    elif response.status_code == 403:
                        message = f"⚠️ {service['name']}: Authentication rejected (check key/plan; Compliance API also needs BREADCRUMBS_API_SECRET)"
                    elif response.status_code == 401:
                        message = f"⚠️ {service['name']}: Unauthorized (verify key format and API host)"
                    else:
                        message = f"✅ {service['name']}: Connection successful (API reachable)"
                elif service_id == 'reddit':
                    message = f"✅ {service['name']}: Connection successful (OAuth2 endpoint reachable)"
                elif service_id == 'dune':
                    if response.status_code == 404:
                        message = f"⚠️ {service['name']}: Query not found, but API is reachable"
                    elif response.status_code == 429:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 429 — provider rate limit; "
                            "wait and retry or reduce parallel probes)"
                        )
                    elif response.status_code == 401:
                        message = (
                            f"⚠️ {service['name']}: Unauthorized (HTTP 401) on api.dune.com after SIM "
                            "fallback — key not accepted for Cloud or SIM; verify DUNE_API_KEY, "
                            "DUNE_SIM_BASE_URL, DUNE_SIM_CHAIN_ID, or set DUNE_USE_SIM_API=1 for SIM-only"
                        )
                    elif response.status_code == 403:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 403 — plan, IP allowlist, or "
                            "feature scope; key is accepted at the edge)"
                        )
                    elif response.status_code == 402:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 402 — billing/plan restriction)"
                        )
                    elif response.status_code == 422:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 422 — probe rejected; "
                            "try DUNE_QUERY_ID or check Dune API changes)"
                        )
                    elif response.status_code in (500, 502, 503, 504):
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP {response.status_code} — "
                            "Dune server error; retry later)"
                        )
                    elif response.status_code == 550:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 550 — provider-specific status; "
                            "see Dune status/docs)"
                        )
                    else:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP {response.status_code}); "
                            "if queries fail, verify DUNE_API_KEY in Dune settings"
                        )
                elif service_id == 'coinapi':
                    if response.status_code == 550:
                        message = f"⚠️ {service['name']}: API key accepted but plan/credits limit reached"
                    elif response.status_code == 429:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 429 — provider rate limit or quota; "
                            "key is accepted at the edge)"
                        )
                    elif response.status_code == 401:
                        message = (
                            f"⚠️ {service['name']}: Unauthorized (HTTP 401 — invalid COINAPI_API_KEY)"
                        )
                    elif response.status_code == 403:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 403 — subscription/plan or "
                            "endpoint not enabled; key is accepted at the edge)"
                        )
                    elif response.status_code == 402:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 402 — payment/plan restriction)"
                        )
                    elif response.status_code == 404:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 404 — probe path returned "
                            "not found; check CoinAPI product URL)"
                        )
                    elif response.status_code == 422:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 422 — request not applicable "
                            "to this key/plan)"
                        )
                    elif response.status_code in (500, 502, 503, 504):
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP {response.status_code} — "
                            "CoinAPI server error; retry later)"
                        )
                    else:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP {response.status_code}); "
                            "if market data fails, verify COINAPI_API_KEY and plan"
                        )
                elif service_id == 'oklink':
                    if response.status_code == 429:
                        message = f"⚠️ {service['name']}: Rate limited (check request frequency)"
                    else:
                        message = f"⚠️ {service['name']}: Authentication/authorization issue (check OKLINK_API_KEY)"
                elif service_id == 'twitter' and response.status_code == 429:
                    message = f"✅ {service['name']}: Connection successful (rate limited)"
                elif service_id == 'twitter':
                    message = f"✅ {service['name']}: Connection successful (API reachable)"
                elif service_id == 'chainabuse':
                    if response.status_code in [400, 404, 422]:
                        message = f"⚠️ {service['name']}: Endpoint reachable (request parameters rejected)"
                    elif response.status_code == 429:
                        message = (
                            f"⚠️ {service['name']}: HTTP 429 — ChainAbuse monthly quota/rate window is exhausted. "
                            "The risk engine now uses the shared 365-day cache and 50-token queue, so avoid "
                            "manual live probes on standard keys; wait for the provider reset or use a partner key."
                        )
                    elif response.status_code == 401:
                        hint = _chainabuse_json_error_hint(response)
                        hint_txt = f" {hint}" if hint else ""
                        message = (
                            f"⚠️ {service['name']}: HTTP 401{hint_txt}. Chainabuse documents this as "
                            "wrong or missing API credentials — regenerate the key (Profile → Settings → API), "
                            "paste the raw value into CHAINABUSE_API_KEY (no quotes/BOM), and set "
                            "CHAINABUSE_BASE_URL to https://api.chainabuse.com or …/v0 only."
                        )
                    elif response.status_code == 403:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 403 — plan, scope, or "
                            "provider policy; key may still be valid)"
                        )
                    elif response.status_code == 402:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP 402 — billing/plan restriction)"
                        )
                    elif response.status_code in (500, 502, 503, 504):
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP {response.status_code} — "
                            "ChainAbuse server error; retry later)"
                        )
                    else:
                        message = (
                            f"✅ {service['name']}: API reachable (HTTP {response.status_code}); "
                            "if reports fail, verify CHAINABUSE_API_KEY in ChainAbuse console"
                        )
                elif service_id == 'trmlabs':
                    if response.status_code in [400, 404, 422]:
                        message = f"⚠️ {service['name']}: Endpoint reachable (request parameters rejected)"
                    elif response.status_code == 429:
                        message = f"⚠️ {service['name']}: Rate limited"
                    else:
                        message = f"⚠️ {service['name']}: Authentication issue (check TRMLABS_API_KEY)"
                elif service_id == 'birdeye':
                    message = f"⚠️ {service['name']}: Authentication or plan issue (check BIRDEYE_API_KEY)"
                elif service_id == 'lifi':
                    message = f"⚠️ {service['name']}: Authentication issue (check LI_FI_API_KEY)"
                elif service_id == 'solanatracker':
                    message = f"⚠️ {service['name']}: Authentication issue (check SOLANATRACKER_API_KEY)"
                elif service_id == 'solscan':
                    message = (
                        f"⚠️ {service['name']}: Authentication failed on public-api "
                        '(check SOLSCAN_API_KEY; use SOLSCAN_PROBE_USE_PRO_API=1 only for Solscan Pro keys)'
                    )
                elif service_id == 'debank':
                    message = (
                        f"⚠️ {service['name']}: Not authorized — use an access key from "
                        'https://cloud.debank.com and set DEBANK_API_KEY (header AccessKey).'
                    )
            elif service_id == 'defi_api' and response.status_code in (502, 503, 504):
                # De.Fi / CDN often returns HTML 502; not indicative of an invalid DEFI_API_KEY.
                success = True
                message = (
                    f"⚠️ {service['name']}: HTTP {response.status_code} from De.Fi or edge "
                    "(Bad Gateway / temporarily unavailable — does not prove DEFI_API_KEY is wrong); "
                    "retry later or set DEFI_GRAPHQL_URL if your plan uses a custom host"
                )
            else:
                success = False
                message = f"❌ Error: {service['name']} returned {response.status_code}"
                if hasattr(response, 'text') and response.text:
                    error_text = response.text[:200]  # First 200 chars of error message
                    # Special handling for common API issues
                    if service_id == 'moralis' and 'usage has been consumed' in error_text:
                        message = f"⚠️ {service['name']}: Free plan daily usage exceeded"
                    elif service_id == 'zapper' and ('Missing API key' in error_text or 'Forbidden' in error_text or 'Unauthorized' in error_text):
                        message = f"✅ {service['name']}: Connection successful (verify authentication)"
                    elif service_id == 'arkham' and ('Invalid API key' in error_text or 'Unauthorized' in error_text or 'forbidden' in error_text.lower()):
                        message = f"✅ {service['name']}: Connection successful (verify API key)"
                    elif service_id == 'arkham' and ('not found' in error_text.lower() or '404' in error_text):
                        message = f"✅ {service['name']}: Connection successful (endpoint may have changed)"
                    elif service_id == 'arkham' and ('rate limit' in error_text.lower() or '429' in error_text):
                        message = f"✅ {service['name']}: Connection successful (rate limited)"
                    elif service_id == 'arkham' and ('not configured' in error_text.lower()):
                        message = f"⚠️ {service['name']}: API key not configured - add ARKHAM_API_KEY to .env file"
                    elif service_id == 'arkham' and ('invalid api key' in error_text.lower()):
                        message = f"⚠️ {service['name']}: Invalid API key - check your ARKHAM_API_KEY"
                    elif service_id == 'breadcrumbs' and ('Unauthorized' in error_text or 'Forbidden' in error_text):
                        message = f"✅ {service['name']}: Connection successful (verify API key)"
                    elif service_id == 'oklink' and ('50011' in error_text or 'too many requests' in error_text.lower()):
                        message = f"⚠️ {service['name']}: Rate limit exceeded"
                    elif service_id == 'oklink' and ('50014' in error_text or 'invalid authorization' in error_text.lower()):
                        message = f"⚠️ {service['name']}: Invalid authorization (check OKLINK_API_KEY)"
                    elif service_id == 'twitter' and ('Unsupported Authentication' in error_text or 'forbidden' in error_text.lower() or 'Too Many Requests' in error_text):
                        message = f"✅ {service['name']}: Connection successful (API reachable)"
                    elif service_id == 'reddit' and ('Unauthorized' in error_text or 'invalid_grant' in error_text):
                        message = f"✅ {service['name']}: Connection successful (OAuth2 endpoint reachable)"
                    elif 'unauthorized' in error_text.lower() or 'invalid api key' in error_text.lower():
                        message = f"❌ {service['name']}: Invalid API key"
                    elif service_id == 'defi_api' and '<html' in error_text.lower():
                        message = (
                            f"⚠️ {service['name']}: HTTP {response.status_code} returned an HTML error page "
                            "(proxy or upstream); check DEFI_GRAPHQL_URL or retry — body omitted"
                        )
                        success = True
                    else:
                        message += f" - {error_text}"
        else:
            success = False
            if service_id == 'trmlabs' and last_request_exception:
                err = str(last_request_exception).lower()
                if (
                    'failed to resolve' in err
                    or 'name or service not known' in err
                    or 'nodename nor servname provided' in err
                    or 'temporary failure in name resolution' in err
                ):
                    message = (
                        f"⚠️ {service['name']}: Endpoint hostname is not resolvable "
                        "(set TRMLABS_SANCTIONS_ENDPOINT if TRM provided a custom host)."
                    )
                    success = True
                else:
                    message = f"❌ Error: {service['name']} failed to get a response ({last_request_exception})"
            else:
                message = f"❌ Error: {service['name']} failed to get a response"
        return success, message

    def _fetch_service_data(self, service_id):  # pyright: ignore[reportGeneralTypeIssues]
        """Fetch data from a specific service in background"""
        service = self.services[service_id]
        widgets = self.service_widgets[service_id]
        
        try:
            success = False
            
            if service['test_endpoint']:
                _load_env_for_probes()

                # Make test API call
                headers = {}
                url = service['test_endpoint']
                
                # Handle API key and make request based on service type
                response = None
                api_key = None
                success = False
                message = ""
                last_request_exception = None

                if service['env_key']:
                    api_key = os.getenv(service['env_key'])
                    if service_id == 'debank' and not (api_key or '').strip():
                        api_key = os.getenv('DEBANK_ACCESS_KEY')
                
                if service_id == 'infura' and api_key:
                    # Replace {api_key} placeholder in URL
                    url = url.format(api_key)
                    # Infura requires JSON-RPC POST request
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "eth_blockNumber", 
                        "params": [],
                        "id": 1
                    }
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                    
                elif service_id == 'alchemy' and api_key:
                    # Replace {api_key} placeholder in URL
                    url = url.format(api_key)
                    # Alchemy requires JSON-RPC POST request
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "eth_blockNumber",
                        "params": [],
                        "id": 1
                    }
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, json=payload, headers=headers, timeout=10)

                elif service_id == 'defi_api':
                    api_key = os.getenv('DEFI_API_KEY', '').strip()
                    graphql_url = (
                        os.getenv('DEFI_GRAPHQL_URL', '').strip()
                        or url
                        or 'https://public-api.de.fi/graphql'
                    ).rstrip('/')
                    if not api_key:
                        message = (
                            f"⚠️ {service['name']}: DEFI_API_KEY is not set. "
                            "Add it under Settings → Credentials, or in web_portal.env / "
                            "/etc/hodler-suite/web_portal.env (audit loads the vault when "
                            "CREDENTIALS_VAULT_PATH and VAULT_MASTER_PASSWORD are set)."
                        )
                        success = True
                        self.root.after(0, self._update_fetch_result, service_id, success, message)
                        return
                    headers = {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-Api-Key': api_key,
                    }
                    payload = {'query': 'query { chains { id name } }'}
                    response = requests.post(graphql_url, json=payload, headers=headers, timeout=12)

                elif service_id == 'solscan':
                    token = (
                        os.getenv('SOLSCAN_API_KEY')
                        or os.getenv('SOLSCAN_PRO_API_KEY')
                        or ''
                    ).strip()
                    probe_pro = str(
                        os.getenv('SOLSCAN_PROBE_USE_PRO_API') or os.getenv('SOLSCAN_USE_PRO_API') or ''
                    ).strip().lower() in {'1', 'true', 'yes', 'on'}
                    if token and probe_pro:
                        # Paid Pro API (v2); not used for free-tier keys from API Management.
                        response = requests.get(
                            'https://pro-api.solscan.io/v2.0/token/meta',
                            headers={'token': token, 'Accept': 'application/json'},
                            params={'address': 'So11111111111111111111111111111111111111112'},
                            timeout=12,
                        )
                    elif token:
                        # Free / standard keys: same ``token`` header on the public host (not pro-api).
                        response = requests.get(
                            'https://public-api.solscan.io/chaininfo',
                            headers={'token': token, 'Accept': 'application/json'},
                            timeout=12,
                        )
                    else:
                        response = requests.get(
                            'https://public-api.solscan.io/chaininfo',
                            headers={'Accept': 'application/json'},
                            timeout=10,
                        )

                elif service_id == 'trmlabs':
                    trm_key = (os.getenv('TRMLABS_API_KEY') or os.getenv('TRM_LABS_API_KEY') or '').strip()
                    headers = {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                    }
                    if trm_key:
                        headers['x-api-key'] = trm_key
                    test_address = '0xdAC17F958D2ee523a2206206994597C13D831ec7'
                    payload = [{'address': test_address}]
                    base_url = service.get('test_endpoint') or 'https://api.trmlabs.com/public/v1/sanctions/screening'
                    override_endpoint = (os.getenv('TRMLABS_SANCTIONS_ENDPOINT') or '').strip()
                    if override_endpoint:
                        if override_endpoint.startswith('http'):
                            normalized_override = override_endpoint.rstrip('/')
                        else:
                            normalized_override = f"https://{override_endpoint.strip('/')}"
                        if not normalized_override.endswith('/public/v1/sanctions/screening'):
                            normalized_override = f"{normalized_override}/public/v1/sanctions/screening"
                    else:
                        normalized_override = ''
                    candidate_urls = [
                        normalized_override or base_url,
                        'https://api.trmlabs.com/public/v1/sanctions/screening',
                        'https://sanctions.trmlabs.com/public/v1/sanctions/screening',
                        'https://api.sanctions.trmlabs.com/public/v1/sanctions/screening',
                    ]
                    candidate_urls = list(dict.fromkeys(candidate_urls))
                    response = None
                    best_response = None
                    for candidate_url in candidate_urls:
                        try:
                            candidate_response = requests.post(
                                candidate_url,
                                headers=headers,
                                json=payload,
                                timeout=12,
                            )
                        except requests.RequestException as req_exc:
                            last_request_exception = req_exc
                            continue
                        if candidate_response.status_code in [200, 201]:
                            response = candidate_response
                            break
                        if (
                            best_response is None
                            or candidate_response.status_code in [400, 401, 403, 404, 422, 429]
                        ):
                            best_response = candidate_response
                        if candidate_response.status_code in [400, 401, 403, 404, 405, 422, 429]:
                            continue
                        response = candidate_response
                        break
                    if response is None:
                        response = best_response

                elif service_id == 'coincap':
                    cap_key = str(os.getenv('COINCAP_API_KEY') or '').strip()
                    response = None
                    last_coincap_exc = None
                    if cap_key:
                        try:
                            response = requests.get(
                                'https://rest.coincap.io/v3/assets',
                                headers={
                                    'Accept': 'application/json',
                                    'Authorization': f'Bearer {cap_key}',
                                },
                                params={'limit': '1'},
                                timeout=12,
                            )
                        except requests.RequestException as exc:
                            last_coincap_exc = exc
                            response = None
                    if response is None or (
                        response is not None and response.status_code in (401, 403)
                    ):
                        urls = [
                            'https://api.coincap.io/v2/assets?limit=1',
                            'https://rest.coincap.io/v3/assets?limit=1',
                        ]
                        for cand in urls:
                            try:
                                response = requests.get(
                                    cand,
                                    headers={'Accept': 'application/json'},
                                    timeout=12,
                                )
                                if response.status_code == 200:
                                    break
                            except requests.RequestException as exc:
                                last_coincap_exc = exc
                                response = None
                                continue
                    if response is None and last_coincap_exc is not None:
                        err_l = str(last_coincap_exc).lower()
                        if any(
                            x in err_l
                            for x in (
                                'resolve',
                                'name or service not known',
                                'nodename nor servname',
                                'gaierror',
                                'temporary failure in name resolution',
                            )
                        ):
                            message = (
                                f"⚠️ {service['name']}: Cannot reach API ({last_coincap_exc!s}). "
                                'This is often DNS or outbound HTTPS blocking on the audit host.'
                            )
                            success = True
                            self.root.after(0, self._update_fetch_result, service_id, success, message)
                            return
                        message = f"❌ Error: {service['name']} - {last_coincap_exc!s}"
                        success = False
                        self.root.after(0, self._update_fetch_result, service_id, success, message)
                        return

                elif api_key:
                    # Handle other services with API keys
                    if service_id == 'moralis':
                        headers['X-API-Key'] = api_key
                    elif service_id == 'birdeye':
                        headers['x-api-key'] = api_key.strip()
                        headers['Accept'] = 'application/json'
                        response = requests.get(url, headers=headers, timeout=12)
                    elif service_id == 'lifi':
                        headers['accept'] = 'application/json'
                        headers['x-lifi-api-key'] = api_key.strip()
                        response = requests.get('https://li.quest/v1/chains', headers=headers, timeout=12)
                    elif service_id == 'solanatracker':
                        headers['x-api-key'] = api_key.strip()
                        headers['Accept'] = 'application/json'
                        response = requests.get(url, headers=headers, timeout=12)
                    elif service_id == 'debank':
                        access_key = api_key.strip()
                        headers['AccessKey'] = access_key
                        headers['Accept'] = 'application/json'
                        response = requests.get(url, headers=headers, timeout=12)
                    elif service_id == 'coinmarketcap':
                        headers['X-CMC_PRO_API_KEY'] = api_key
                        headers['Accept'] = 'application/json'
                    elif service_id == 'coinapi':
                        normalized_key = api_key.strip()
                        coin_headers = {
                            'X-CoinAPI-Key': normalized_key,
                            'Accept': 'application/json',
                        }
                        try:
                            response = requests.get(url, headers=coin_headers, timeout=12)
                        except requests.RequestException:
                            response = None
                        if response is not None and response.status_code not in (200, 201):
                            try:
                                alt = requests.get(
                                    'https://rest.coinapi.io/v1/assets',
                                    headers=coin_headers,
                                    params={'limit': '1'},
                                    timeout=12,
                                )
                            except requests.RequestException:
                                alt = None
                            if alt is not None and alt.status_code in (200, 201):
                                response = alt
                    elif service_id == 'covalent':
                        # Covalent uses API key in URL, not headers
                        url = f"{url}?key={api_key}"
                    elif service_id == 'zapper':
                        normalized_key = api_key.strip()
                        headers['x-zapper-api-key'] = normalized_key
                        headers['Content-Type'] = 'application/json'
                        payload = {
                            "query": (
                                "query PortfolioV2($addresses: [Address!]!, $networks: [Network!]) { "
                                "portfolioV2(addresses: $addresses, networks: $networks) { "
                                "tokenBalances { byToken { edges { node { symbol } } } } } }"
                            ),
                            "variables": {
                                "addresses": ["0xdAC17F958D2ee523a2206206994597C13D831ec7"],
                                "networks": ["ETHEREUM_MAINNET"]
                            }
                        }
                        try:
                            response = requests.post(url, json=payload, headers=headers, timeout=15)
                        except requests.RequestException:
                            fallback_headers = {'X-Zapper-API-Key': normalized_key}
                            response = requests.get('https://api.zapper.xyz/v2/prices', headers=fallback_headers, timeout=10)
                    elif service_id == 'oneinch':
                        headers['Authorization'] = f'Bearer {api_key}'
                    elif service_id == 'twitter':
                        headers['Authorization'] = f'Bearer {api_key}'
                    elif service_id == 'reddit':
                        # Reddit requires OAuth2 application-only authentication
                        reddit_secret = os.getenv(service.get('secondary_key', ''))
                        if reddit_secret:
                            # Get application-only access token
                            access_token = self._get_reddit_access_token(api_key, reddit_secret)
                            if access_token:
                                headers['Authorization'] = f'Bearer {access_token}'
                                headers['User-Agent'] = 'DeFiRiskAssessment/1.0'
                            else:
                                message = f"⚠️ {service['name']}: Failed to get OAuth2 access token"
                                success = False
                                self.root.after(0, self._update_fetch_result, service_id, success, message)
                                return
                        else:
                            message = f"⚠️ {service['name']}: Missing REDDIT_CLIENT_SECRET"
                            success = False
                            self.root.after(0, self._update_fetch_result, service_id, success, message)
                            return
                    elif service_id == 'santiment':
                        headers['Apikey'] = api_key
                        headers['Content-Type'] = 'application/json'
                        # Simple GraphQL query for testing
                        payload = {
                            "query": "{ getMetric(metric: \"price_usd\") { metadata { metric } } }"
                        }
                        response = requests.post(url, json=payload, headers=headers, timeout=10)
                    elif service_id == 'breadcrumbs':
                        normalized_key = api_key.strip()
                        breadcrumbs_secret = (os.getenv('BREADCRUMBS_API_SECRET') or '').strip()
                        test_address = '0xdAC17F958D2ee523a2206206994597C13D831ec7'
                        response = None
                        best_response = None
                        try:
                            primary = requests.post(
                                'https://api.breadcrumbs.one/sanctioned_address',
                                headers={'X-API-KEY': normalized_key, 'Accept': 'application/json'},
                                json=[{'chain': 'ETH', 'address': test_address}],
                                timeout=10,
                            )
                        except requests.RequestException:
                            primary = None
                        if primary is not None and primary.status_code == 200:
                            response = primary
                        else:
                            if primary is not None:
                                best_response = primary
                            candidate_requests = [
                                (
                                    'https://api.breadcrumbs.one/risk/address',
                                    {'X-API-KEY': normalized_key, 'Accept': 'application/json'},
                                    {'chain': 'ETH', 'address': test_address},
                                ),
                                (
                                    'https://api.breadcrumbs.one/sanctions/address',
                                    {'X-API-KEY': normalized_key, 'Accept': 'application/json'},
                                    {'chain': 'ETH', 'address': test_address},
                                ),
                                (
                                    f'https://api.breadcrumbs.app/v2/address/{test_address}/risk-score',
                                    {'Authorization': f'Bearer {normalized_key}', 'Accept': 'application/json'},
                                    {'chain': 'ETH'},
                                ),
                                (
                                    f'https://api.breadcrumbs.app/v2/address/{test_address}/risk-score',
                                    {'X-API-KEY': normalized_key, 'Accept': 'application/json'},
                                    {'chain': 'ETH'},
                                ),
                            ]
                            if breadcrumbs_secret:
                                nonce = str(int(time.time() * 1000))
                                compliance_path = f'/api/risk/address?chain=ETH&address={test_address}'
                                compliance_url = f'https://apicompliance.breadcrumbs.app{compliance_path}'
                                signature_payloads = [
                                    f'{nonce}{compliance_url}',
                                    f'{nonce}{compliance_path}',
                                    f'{nonce}GET{compliance_url}',
                                    f'{nonce}GET{compliance_path}',
                                ]
                                for signature_payload in dict.fromkeys(signature_payloads):
                                    signature = hmac.new(
                                        breadcrumbs_secret.encode('utf-8'),
                                        signature_payload.encode('utf-8'),
                                        hashlib.sha256
                                    ).hexdigest()
                                    candidate_requests.append(
                                        (
                                            compliance_url,
                                            {
                                                'X-API-Key': normalized_key,
                                                'X-API-Nonce': nonce,
                                                'X-API-Signature': signature,
                                                'Accept': 'application/json',
                                            },
                                            {},
                                        )
                                    )
                            for candidate_url, candidate_headers, candidate_params in candidate_requests:
                                try:
                                    candidate_response = requests.get(
                                        candidate_url,
                                        headers=candidate_headers,
                                        params=candidate_params,
                                        timeout=10,
                                    )
                                except requests.RequestException:
                                    continue

                                if candidate_response.status_code == 200:
                                    response = candidate_response
                                    break

                                if (
                                    best_response is None
                                    or candidate_response.status_code in [401, 403, 429]
                                ):
                                    best_response = candidate_response

                                if candidate_response.status_code in [401, 403, 404, 405, 429]:
                                    continue

                                response = candidate_response
                                break

                            if response is None:
                                response = best_response
                    elif service_id == 'oklink':
                        normalized_key = api_key.strip()
                        headers['Ok-Access-Key'] = normalized_key
                        headers['Accept'] = 'application/json'
                        headers['Content-Type'] = 'application/json'
                        response = requests.get(
                            url, headers=headers, timeout=_probe_http_timeout_seconds(service_id)
                        )
                    elif service_id == 'discord':
                        headers['Authorization'] = f'Bot {api_key}'
                    elif service_id == 'telegram':
                        url = url.format(api_key)
                    elif service_id == 'arkham':
                        # Arkham API uses API key authentication with specific headers
                        try:
                            # Test Arkham API directly with proper headers
                            api_key = os.getenv('ARKHAM_API_KEY')
                            if api_key:
                                normalized_key = api_key.strip()
                                if normalized_key.lower().startswith('bearer '):
                                    normalized_key = normalized_key.split(' ', 1)[1].strip()
                                headers = {
                                    'API-Key': normalized_key,
                                    'X-Timestamp': str(int(time.time() * 1_000_000))
                                }
                                test_address = '0xdAC17F958D2ee523a2206206994597C13D831ec7'
                                url = f"https://api.arkm.com/intelligence/address/{test_address}"
                                response = requests.get(
                                    url,
                                    headers=headers,
                                    timeout=_probe_http_timeout_seconds(service_id),
                                )
                            else:
                                response = None
                                
                        except Exception as e:
                            response = None
                    elif service_id == 'thegraph':
                        # The Graph uses API key in URL path and requires GraphQL POST
                        url = url.format(api_key)
                        headers['Content-Type'] = 'application/json'
                        # Simple GraphQL query for testing
                        payload = {
                            "query": "{ indexingStatuses { subgraph chains { network } } }"
                        }
                        response = requests.post(url, json=payload, headers=headers, timeout=10)
                    elif service_id == 'dune':
                        normalized_key = api_key.strip()

                        def _dune_env_truthy(var_name: str) -> bool:
                            val = (os.getenv(var_name) or "").strip().lower()
                            return val in ("1", "true", "yes", "on")

                        sim_base = (os.getenv("DUNE_SIM_BASE_URL") or "https://api.sim.dune.com/v1").strip().rstrip(
                            "/"
                        )
                        sim_chain = (os.getenv("DUNE_SIM_CHAIN_ID") or "1").strip()
                        if not sim_chain.isdigit():
                            sim_chain = "1"
                        test_tok = (
                            os.getenv("DUNE_TEST_TOKEN_ADDRESS") or "0xdAC17F958D2ee523a2206206994597C13D831ec7"
                        ).strip()
                        if not (test_tok.startswith("0x") and len(test_tok) == 42):
                            test_tok = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

                        def _dune_sim_probe():
                            """Try several SIM EVM routes (matches Dune console: token info, activity, etc.)."""
                            sim_headers = {
                                "Accept": "application/json",
                                "X-Sim-Api-Key": normalized_key,
                            }
                            probe_wallet = (
                                (os.getenv("DUNE_SIM_PROBE_WALLET") or "").strip()
                                or "0xd8dA6BF26964af9D7eed9e03e53415D37aa96045"
                            )
                            last_resp = None
                            sim_candidates = [
                                (
                                    f"{sim_base}/evm/token-info/{test_tok}",
                                    {"chain_ids": sim_chain, "limit": 1},
                                ),
                                (
                                    f"{sim_base}/evm/activity/{test_tok}",
                                    {"chain_ids": sim_chain, "limit": 1},
                                ),
                                (
                                    f"{sim_base}/evm/token-holders/{sim_chain}/{test_tok}",
                                    {"limit": 1},
                                ),
                                (
                                    f"{sim_base}/evm/balances/{probe_wallet}",
                                    {"chain_ids": sim_chain, "limit": 1},
                                ),
                                (
                                    f"{sim_base}/evm/transactions/{probe_wallet}",
                                    {"chain_ids": sim_chain, "limit": 1},
                                ),
                            ]
                            for sim_url, params in sim_candidates:
                                try:
                                    last_resp = requests.get(
                                        sim_url,
                                        headers=sim_headers,
                                        params=params,
                                        timeout=12,
                                    )
                                except requests.RequestException:
                                    last_resp = None
                                    continue
                                if last_resp is not None and last_resp.status_code in (200, 201):
                                    return last_resp
                            return last_resp

                        use_sim_only = _dune_env_truthy("DUNE_USE_SIM_API")
                        dune_headers_prod = {
                            "Accept": "application/json",
                            "Content-Type": "application/json",
                            "X-Dune-API-Key": normalized_key,
                        }
                        response = None
                        best_response = None

                        if use_sim_only:
                            response = _dune_sim_probe()
                        else:
                            # Prefer production Dune Cloud usage (SQL / analytics keys).
                            try:
                                usage_resp = requests.post(
                                    "https://api.dune.com/api/v1/usage",
                                    headers=dune_headers_prod,
                                    json={},
                                    timeout=12,
                                )
                            except requests.RequestException:
                                usage_resp = None
                            if usage_resp is not None and usage_resp.status_code in (200, 201):
                                response = usage_resp
                            elif usage_resp is not None and usage_resp.status_code == 429:
                                # Do not hammer query endpoints after a global rate limit on usage.
                                response = usage_resp
                            else:
                                if usage_resp is not None:
                                    if best_response is None or usage_resp.status_code in [401, 403, 429]:
                                        best_response = usage_resp
                            if response is None:
                                probe_headers = {
                                    "X-Dune-API-Key": normalized_key,
                                    "Accept": "application/json",
                                }
                                dune_query_id = (os.getenv("DUNE_QUERY_ID") or "").strip()
                                query_candidates = []
                                if dune_query_id.isdigit():
                                    query_candidates.append(dune_query_id)
                                # Stable defaults when DUNE_QUERY_ID is unset or invalid.
                                query_candidates.extend(["3373921", "1"])
                                query_candidates = list(dict.fromkeys(query_candidates))

                                dune_urls = []
                                for qid in query_candidates:
                                    dune_urls.append(f"https://api.dune.com/api/v1/query/{qid}/results?limit=1")
                                    dune_urls.append(f"https://api.dune.com/api/v1/queries/{qid}/results?limit=1")

                                # Cap attempts: a full audit already touches many providers; bursty GETs
                                # here often return 429 even when the key is valid.
                                for dune_url in dune_urls[:3]:
                                    try:
                                        candidate_response = requests.get(
                                            dune_url, headers=probe_headers, timeout=15
                                        )
                                    except requests.RequestException:
                                        continue

                                    if candidate_response.status_code == 200:
                                        response = candidate_response
                                        break

                                    if (
                                        best_response is None
                                        or candidate_response.status_code in [401, 403, 429]
                                    ):
                                        best_response = candidate_response

                                    # Query IDs frequently 404; continue until we hit a known good endpoint.
                                    if candidate_response.status_code in [401, 403, 404, 429]:
                                        continue

                                    response = candidate_response
                                    break

                                if response is None:
                                    response = best_response

                            # SIM-only keys are rejected on api.dune.com (HTTP 401). Align with
                            # ``defi_complete_risk_assessment_clean`` (X-Sim-Api-Key + api.sim.dune.com).
                            if response is not None and response.status_code == 401:
                                sim_r = _dune_sim_probe()
                                if sim_r is not None and sim_r.status_code in (200, 201):
                                    response = sim_r
                    elif service_id == 'chainabuse':
                        if not _chainabuse_live_probe_enabled():
                            success = True
                            message = _chainabuse_local_probe_message(service['name'])
                            self.root.after(0, self._update_fetch_result, service_id, success, message)
                            return

                        # Standard ChainAbuse keys only get 10 calls/month, so keep the probe to
                        # the canonical reports endpoint and avoid cycling through auth schemes.
                        minimal_params = {"page": 1, "perPage": 1}
                        chainabuse_url = _chainabuse_reports_url()
                        basic_dual = _chainabuse_basic_authorization_header_dual(api_key)
                        basic_empty = _chainabuse_basic_authorization_header(api_key)
                        base_headers = {
                            "Accept": "application/json",
                            "User-Agent": "HodlerSuite-APIAudit/1.0 (+https://hodler-suite.com)",
                        }

                        def _ch(extra_headers: dict) -> dict:
                            merged = dict(base_headers)
                            merged.update(extra_headers)
                            return merged

                        # Current docs require the API key in both Basic username and password.
                        # ``KEY:`` remains as a single fallback for older deployments.
                        attempts = [
                            {
                                "headers": _ch({"Authorization": basic_dual}),
                                "params": dict(minimal_params),
                                "auth": None,
                            },
                            {
                                "headers": _ch({"Authorization": basic_empty}),
                                "params": dict(minimal_params),
                                "auth": None,
                            },
                        ]
                        headless = (
                            str(os.environ.get("API_SERVICE_AUDIT_HEADLESS", ""))
                            .strip()
                            .lower()
                            in {"1", "true", "yes", "on"}
                        )
                        if headless:
                            # Chainabuse Public API: GET ``/v0/reports`` with Basic auth and optional query
                            # params (``page``, ``perPage`` 1–50). Use the documented key:key scheme first.
                            # Ref: https://docs.chainabuse.com/reference/reports-1
                            attempts = [
                                {
                                    "headers": _ch({"Authorization": basic_dual}),
                                    "params": dict(minimal_params),
                                    "auth": None,
                                },
                                {
                                    "headers": _ch({"Authorization": basic_empty}),
                                    "params": dict(minimal_params),
                                    "auth": None,
                                },
                            ]
                        response = None
                        best_response = None
                        for attempt in attempts:
                            try:
                                candidate_response = requests.get(
                                    chainabuse_url,
                                    headers=attempt["headers"],
                                    params=attempt["params"],
                                    auth=attempt["auth"],
                                    timeout=12,
                                )
                            except requests.RequestException:
                                continue
                            if candidate_response.status_code == 200:
                                response = candidate_response
                                break
                            # 429 means credentials were accepted at the edge; stop — later fallbacks
                            # (Bearer, apiKey, …) often return 401 and would overwrite ``best_response``.
                            if candidate_response.status_code == 429:
                                response = candidate_response
                                break
                            if (
                                best_response is None
                                or candidate_response.status_code in [401, 403, 404, 422, 429]
                            ):
                                if best_response is None:
                                    best_response = candidate_response
                                else:
                                    bc = int(best_response.status_code)
                                    cc = int(candidate_response.status_code)
                                    # Prefer rate-limit (auth accepted) over spurious 401 from alt schemes.
                                    if bc == 401 and cc == 429:
                                        best_response = candidate_response
                                    elif bc == 429 and cc == 401:
                                        pass
                                    else:
                                        best_response = candidate_response
                            if candidate_response.status_code in [401, 403, 404, 405, 422, 429]:
                                continue
                            response = candidate_response
                            break
                        if response is None:
                            response = best_response
                    elif service_id == 'cointelegraph':
                        # Cointelegraph uses custom User-Agent for RSS scraping
                        headers['User-Agent'] = api_key
                    elif service_id in ['etherscan', 'ethplorer']:
                        url += api_key
                    else:
                        if '?' in url:
                            url += f'&apikey={api_key}'
                        else:
                            url += f'?apikey={api_key}'
                    
                    # Make GET request for non-RPC services (except those that already made requests)
                    if service_id not in [
                        'santiment',
                        'thegraph',
                        'zapper',
                        'dune',
                        'breadcrumbs',
                        'oklink',
                        'defi_api',
                        'birdeye',
                        'lifi',
                        'solanatracker',
                        'chainabuse',
                        'debank',
                        'coinapi',
                    ]:  # These services handle their own requests
                        response = requests.get(
                            url, headers=headers, timeout=_probe_http_timeout_seconds(service_id)
                        )
                
                else:
                    # No API key or service doesn't need one
                    if service_id not in [
                        'infura',
                        'alchemy',
                        'zapper',
                        'oneinch',
                        'twitter',
                        'reddit',
                        'breadcrumbs',
                        'thegraph',
                        'coinapi',
                        'dune',
                        'oklink',
                        'defi_api',
                        'solscan',
                        'trmlabs',
                        'coincap',
                        'birdeye',
                        'lifi',
                        'solanatracker',
                        'chainabuse',
                    ]:
                        response = requests.get(
                            url, headers=headers, timeout=_probe_http_timeout_seconds(service_id)
                        )
                    else:
                        # These services require API keys, can't test without them
                        if service_id in ['bitcointalk', 'cointelegraph']:
                            # These don't need API keys, just do a simple GET
                            response = requests.get(
                                url,
                                headers=headers,
                                timeout=_probe_http_timeout_seconds(service_id),
                            )
                        else:
                            message = f"⚠️ {service['name']} requires API key for testing"
                            success = False
                            self.root.after(0, self._update_fetch_result, service_id, success, message)
                            return
                
                try:
                    if response is not None and int(response.status_code) == 429:
                        _record_probe_cooldown_after_429(service_id, response)
                except Exception:
                    pass

                success, message = self._probe_format_response(
                    service_id,
                    service,
                    response,
                    last_request_exception,
                )
            
            # Update UI in main thread
            self.root.after(0, self._update_fetch_result, service_id, success, message)
            
        except Exception as e:
            error_msg = f"❌ Error: {service['name']} - {str(e)}"
            self.root.after(0, self._update_fetch_result, service_id, False, error_msg)
    
    def _get_reddit_access_token(self, client_id, client_secret):
        """Get Reddit OAuth2 application-only access token"""
        try:
            import base64
            
            # Create HTTP Basic Auth header
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'User-Agent': 'DeFiRiskAssessment/1.0',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Request application-only access token
            data = 'grant_type=client_credentials'
            
            response = requests.post(
                'https://www.reddit.com/api/v1/access_token',
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data.get('access_token')
            else:
                print(f"Reddit OAuth2 error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Reddit OAuth2 exception: {e}")
            return None
    
    def _update_fetch_result(self, service_id, success, message):
        """Update UI with fetch result"""
        widgets = self.service_widgets[service_id]
        
        # Reset button
        widgets['trigger_btn'].config(text="🔄 Fetch Data", state='normal')
        
        # Show result message
        messagebox.showinfo("Fetch Result", message)
    
    def open_auto_refresh_settings(self):
        """Open auto-refresh settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Auto-Refresh Settings")
        settings_window.geometry("500x420")
        settings_window.transient(self.root)
        settings_window.grab_set()
        settings_window.resizable(False, False)
        
        # Center the window
        settings_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid expansion
        settings_window.columnconfigure(0, weight=1)
        settings_window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="⚙️ Auto-Refresh Settings", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Enable auto-refresh checkbox
        self.auto_refresh_var = tk.BooleanVar(value=self.auto_refresh_enabled)
        enable_cb = ttk.Checkbutton(main_frame, text="Enable automatic cache refresh", 
                                   variable=self.auto_refresh_var)
        enable_cb.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))
        
        # Refresh interval setting
        ttk.Label(main_frame, text="Refresh interval:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
        
        interval_frame = ttk.Frame(main_frame)
        interval_frame.grid(row=2, column=1, sticky="ew", pady=5)
        
        self.interval_var = tk.StringVar(value=str(self.auto_refresh_interval // 60))
        interval_entry = ttk.Entry(interval_frame, textvariable=self.interval_var, width=10)
        interval_entry.grid(row=0, column=0, padx=(0, 5))
        
        ttk.Label(interval_frame, text="minutes").grid(row=0, column=1)
        
        # System integration options
        ttk.Label(main_frame, text="System Integration:", font=('Arial', 11, 'bold')).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(20, 10))
        
        self.auto_trigger_var = tk.BooleanVar(value=self.auto_trigger_enabled)
        trigger_cb = ttk.Checkbutton(main_frame, text="Auto-trigger API calls when rate limits reset", 
                                    variable=self.auto_trigger_var)
        trigger_cb.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Information label
        info_text = """When enabled, the system will automatically refresh the cache
and trigger API calls when rate limit periods expire.

This ensures your data cache stays fresh and takes advantage
of available API calls as soon as rate limits reset."""
        
        info_label = ttk.Label(main_frame, text=info_text, font=('Arial', 9), 
                              foreground='#5d6d7e', justify=tk.LEFT)
        info_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(20, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(20, 0))
        
        save_btn = ttk.Button(button_frame, text="💾 Save Settings", 
                             command=lambda: self.save_auto_refresh_settings(settings_window))
        save_btn.grid(row=0, column=0, padx=(0, 10))
        
        cancel_btn = ttk.Button(button_frame, text="❌ Cancel", command=settings_window.destroy)
        cancel_btn.grid(row=0, column=1)
    
    def save_auto_refresh_settings(self, settings_window):
        """Save auto-refresh settings"""
        try:
            # Update interval
            minutes = int(self.interval_var.get())
            if minutes < 1:
                messagebox.showerror("Invalid Input", "Refresh interval must be at least 1 minute.")
                return
            
            self.auto_refresh_interval = minutes * 60
            self.auto_refresh_enabled = self.auto_refresh_var.get()
            self.auto_trigger_enabled = self.auto_trigger_var.get()
            
            # Apply settings
            if self.auto_refresh_enabled:
                self.start_auto_refresh()
            else:
                self.stop_auto_refresh()
            
            messagebox.showinfo("Settings Saved", 
                              f"Auto-refresh settings updated:\n"
                              f"• Refresh: {'Enabled' if self.auto_refresh_enabled else 'Disabled'}\n"
                              f"• Interval: {minutes} minutes\n"
                              f"• Auto-trigger: {'Enabled' if self.auto_trigger_enabled else 'Disabled'}")
            settings_window.destroy()
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for refresh interval.")
    
    def start_auto_refresh(self):
        """Start automatic refresh"""
        if self.auto_refresh_job:
            self.root.after_cancel(self.auto_refresh_job)
        
        def auto_refresh_task():
            if self.auto_refresh_enabled:
                self.refresh_all_services()
                # Check for services ready to trigger
                if self.auto_trigger_enabled:
                    self.auto_trigger_ready_services()
                # Schedule next refresh
                self.auto_refresh_job = self.root.after(self.auto_refresh_interval * 1000, auto_refresh_task)
        
        self.auto_refresh_job = self.root.after(self.auto_refresh_interval * 1000, auto_refresh_task)
    
    def stop_auto_refresh(self):
        """Stop automatic refresh"""
        if self.auto_refresh_job:
            self.root.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None
    
    def auto_trigger_ready_services(self):
        """Automatically trigger services that are ready"""
        triggered_count = 0
        for service_id in self.services:
            status, _ = self.get_service_status(service_id)
            if status == 'available':
                service = self.services[service_id]
                # Only trigger if it's been idle for sufficient time
                if service['last_call'] == 0 or (time.time() - service['last_call']) > service['rate_period']:
                    self.trigger_service(service_id)
                    triggered_count += 1
                    time.sleep(0.5)  # Small delay between triggers
        
        if triggered_count > 0:
            print(f"Auto-triggered {triggered_count} API services")
    
    def refresh_all_services(self):
        """Refresh status for all services"""
        self.update_service_status()
        # No need to show message for auto-refresh
        
    def test_all_services(self):
        """Test all available services"""
        available_services = []
        
        for service_id in self.services:
            status, _ = self.get_service_status(service_id)
            if status == 'available':
                available_services.append(service_id)
        
        if not available_services:
            messagebox.showwarning("No Services", "No services are currently available for testing")
            return
        
        if not messagebox.askyesno("Test All Services", 
                                  f"Test {len(available_services)} available services?\n\n"
                                  "This will make API calls to each service."):
            return
        
        # Test each available service
        for service_id in available_services:
            self.trigger_service(service_id)
            time.sleep(1)  # Prevent overwhelming
    
    def close_dashboard(self):
        """Close the dashboard"""
        self.stop_auto_refresh()
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Start the dashboard"""
        # Start the status update loop after a brief delay
        self.root.after(1000, self.update_service_status)
        self.root.mainloop()
        
    def on_closing(self):
        """Handle window close event"""
        try:
            self.cleanup_lock_file()
            self.root.destroy()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            self.root.destroy()
            
    def cleanup_lock_file(self):
        """Clean up the API dashboard lock file"""
        try:
            lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
            lock_file = os.path.join(lock_dir, 'api_dashboard.lock')
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print("API Dashboard lock file cleaned up")
        except Exception as e:
            print(f"Error cleaning up lock file: {e}")

def main():
    """Main entry point"""
    try:
        _load_env_for_probes()
        
        dashboard = APIServiceDashboard()
        dashboard.run()
    except Exception as e:
        print(f"Dashboard error: {e}")
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error", f"Could not start API dashboard: {e}")
        except:
            pass

def create_lock_file():
    """Create lock file for this instance"""
    lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
    os.makedirs(lock_dir, exist_ok=True)
    lock_file = os.path.join(lock_dir, 'api_dashboard.lock')
    
    lock_data = {
        'pid': os.getpid(),
        'started_at': time.time(),
        'service_name': 'api_dashboard'
    }
    
    try:
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f)
        
        # Register cleanup on exit
        import atexit
        atexit.register(lambda: cleanup_lock_file(lock_file))
        
        # Also register signal handlers for proper cleanup
        import signal
        signal.signal(signal.SIGTERM, lambda sig, frame: cleanup_lock_file(lock_file))
        signal.signal(signal.SIGINT, lambda sig, frame: cleanup_lock_file(lock_file))
        signal.signal(signal.SIGQUIT, lambda sig, frame: cleanup_lock_file(lock_file))
        
        # Register a more robust cleanup function
        def robust_cleanup():
            try:
                cleanup_lock_file(lock_file)
            except:
                pass
        
        # Register with atexit
        import atexit
        atexit.register(robust_cleanup)
        
    except Exception as e:
        print(f"Warning: Could not create lock file: {e}")

def cleanup_lock_file(lock_file):
    """Clean up lock file on exit"""
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
            print(f"✅ Lock file cleaned up: {os.path.basename(lock_file)}")
    except Exception as e:
        print(f"⚠️ Error cleaning up lock file: {e}")

def check_singleton():
    """Check if another instance is already running"""
    lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
    lock_file = os.path.join(lock_dir, 'api_dashboard.lock')
    
    # Check if another instance is running
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                data = json.load(f)
                pid = data.get('pid')
                
            # Check if process is actually running
            if pid:
                try:
                    os.kill(pid, 0)  # Check existence
                    print("API Service Dashboard is already running")
                    # Try to bring existing window to front (configurable)
                    from os import getenv
                    focus_mode = (getenv('FOCUS_BEHAVIOR', 'disabled') or '').lower()
                    if sys.platform == "darwin" and focus_mode not in ("disabled", "off", "false", "0"):
                        script = f'''
                        tell application "System Events"
                            set appList to every application process whose name contains "Python"
                            repeat with appProcess in appList
                                try
                                    tell appProcess
                                        set windowList to every window
                                        repeat with windowItem in windowList
                                            if name of windowItem contains "API Service Dashboard" then
                                                set frontmost of appProcess to true
                                                perform action "AXRaise" of windowItem
                                                return
                                            end if
                                        end repeat
                                    end tell
                                end try
                            end repeat
                        end tell
                        '''
                        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
                    return False  # Don't start new instance
                except OSError:
                    # Process doesn't exist, remove stale lock
                    os.remove(lock_file)
        except (json.JSONDecodeError, FileNotFoundError):
            try:
                os.remove(lock_file)
            except:
                pass
    
    return True  # OK to start new instance

if __name__ == "__main__":
    if check_singleton():
        create_lock_file()
        main()
