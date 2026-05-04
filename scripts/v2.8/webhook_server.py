#!/usr/bin/env python3
"""
Webhook Server for DeFi Risk Assessment
Handles cache updates and real-time data fetching with fallback mechanisms
"""

import os
import sys
import json
import time
import threading
import re
import hashlib
import hmac
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

# Align chain normalization / deep-health allow-list with `web_portal/app/hodler_chain_codes.py`
_WEB_PORTAL_ROOT = Path(__file__).resolve().parent / "web_portal"
if _WEB_PORTAL_ROOT.is_dir() and str(_WEB_PORTAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_WEB_PORTAL_ROOT))
# Must stay in sync with `web_portal/app/hodler_chain_codes.CANONICAL_TOKEN_CHAIN_CODES`.
# Union with imported tuple so a stale/partial deploy of `hodler_chain_codes` still accepts all deep routes.
_HARDCODED_DEEP_HEALTH_CHAINS: frozenset[str] = frozenset(
    {
        "eth",
        "bsc",
        "tron",
        "polygon",
        "op",
        "arbitrum",
        "base",
        "mantle",
        "linea",
        "sei",
        "avax",
        "zksync",
        "solana",
        "thorchain",
    }
)
try:
    from app.hodler_chain_codes import CANONICAL_TOKEN_CHAIN_CODES, normalize_token_chain_hint

    # Always include the hardcoded multichain set first so a stale CANONICAL tuple cannot shrink probes.
    _DEEP_HEALTH_SUPPORTED_CHAINS = _HARDCODED_DEEP_HEALTH_CHAINS | frozenset(CANONICAL_TOKEN_CHAIN_CODES)
except ImportError:
    normalize_token_chain_hint = None  # type: ignore[assignment, misc]

    _DEEP_HEALTH_SUPPORTED_CHAINS = _HARDCODED_DEEP_HEALTH_CHAINS

# CRITICAL: Set unified app icon environment variables BEFORE any other imports
if sys.platform == "darwin":
    # AGGRESSIVE unified app icon environment variables with CORRECT bundle identifier
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
    
    # AGGRESSIVE: Set activation policy to completely hide from dock
    os.environ['NSApplicationActivationPolicy'] = 'accessory'
    os.environ['LSUIElement'] = 'true'
    os.environ['NSWindowCollectionBehavior'] = 'NSWindowCollectionBehaviorParticipatesInCycle'
    os.environ['NSWindowLevel'] = 'Normal'
    
    # Additional macOS environment variables
    os.environ['NSDocumentRevisionsKeepEveryOne'] = '1'
    os.environ['NSAppTransportSecurity'] = 'true'
    
    # AGGRESSIVE: Force basic mode and skip ALL macOS checks
    os.environ['TK_FORCE_BASIC_MODE'] = '1'
    os.environ['TK_SKIP_ALL_MACOS_CHECKS'] = '1'
    os.environ['TK_DISABLE_ALL_MACOS_FEATURES'] = '1'
    os.environ['TK_DISABLE_MACOS_VERSION_CALLS'] = '1'
    os.environ['TK_SKIP_MACOS_VERSION_CHECK'] = '1'
    os.environ['TK_DISABLE_MACOS_VERSION_METHOD'] = '1'
    os.environ['TK_USE_LEGACY_MODE'] = '1'
    os.environ['TK_DISABLE_NATIVE_FEATURES'] = '1'
    os.environ['TK_FORCE_COMPATIBILITY_MODE'] = '1'
    
    # AGGRESSIVE: Force tkinter to use framework mode
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'
    
    # AGGRESSIVE: Force app to run as background process
    os.environ['NSApplicationActivationPolicy'] = 'accessory'
    os.environ['LSUIElement'] = 'true'
    
    # AGGRESSIVE: Prevent dock icon completely
    os.environ['NSWindowCollectionBehavior'] = 'NSWindowCollectionBehaviorParticipatesInCycle'
    os.environ['NSWindowLevel'] = 'Normal'
    
    # AGGRESSIVE: Additional variables to prevent Python icon
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    
    # AGGRESSIVE: Additional bundle inheritance
    os.environ['CFBundleExecutable'] = 'Token Risk Assessment Tool'
    os.environ['CFBundlePackageType'] = 'APPL'
    os.environ['CFBundleSignature'] = '????'
    os.environ['CFBundleVersion'] = '1.0'
    os.environ['CFBundleShortVersionString'] = '1.0'
    
    # AGGRESSIVE: Force parent bundle inheritance
    os.environ['PARENT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['INHERIT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['BUNDLE_IDENTIFIER'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['CFBundleIdentifier'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'

# Import required packages
from flask import Flask, request, jsonify
import requests

# Add project root to path
# Priority:
# 1) explicit PROJECT_ROOT env var
# 2) auto-detect from this file location (.../scripts/v2.8/webhook_server.py -> repo root)
PROJECT_ROOT = os.getenv('PROJECT_ROOT')
if not PROJECT_ROOT:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(PROJECT_ROOT)
V2_SCRIPT_DIR = os.path.join(PROJECT_ROOT, 'scripts', 'v2.8')
TOKEN_MAPPINGS_GENERATOR = os.path.join(V2_SCRIPT_DIR, 'generate_token_mappings.py')
if V2_SCRIPT_DIR not in sys.path:
    sys.path.append(V2_SCRIPT_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
except Exception:
    pass

# Import enhanced cache manager
try:
    from cache_manager import get_cache_manager
    cache_manager = get_cache_manager()
    print("✅ Enhanced cache manager initialized in webhook server")
except ImportError:
    print("⚠️ Enhanced cache manager not available, using basic cache")
    cache_manager = None

app = Flask(__name__)

# Configuration
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CACHE_FILE = os.path.join(DATA_DIR, 'real_data_cache.json')
FALLBACK_FILE = os.path.join(DATA_DIR, 'token_fallbacks.json')
SYMBOL_CACHE_FILE = os.path.join(DATA_DIR, 'symbol_cache.json')
API_RATE_POLICY_FILE = os.path.join(DATA_DIR, 'api_runtime', 'api_rate_limits_free_tier.json')


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default


WEBHOOK_SHARED_SECRET = str(os.getenv('WEBHOOK_SHARED_SECRET', '')).strip()
WEBHOOK_REQUIRE_AUTH = _env_bool('WEBHOOK_REQUIRE_AUTH', default=bool(WEBHOOK_SHARED_SECRET))
WEBHOOK_REQUIRE_SIGNATURE = _env_bool('WEBHOOK_REQUIRE_SIGNATURE', default=bool(WEBHOOK_SHARED_SECRET))
WEBHOOK_SIGNATURE_MAX_AGE_SECONDS = max(30, _env_int('WEBHOOK_SIGNATURE_MAX_AGE_SECONDS', 300))
WEBHOOK_TRUST_PROXY_HEADERS = _env_bool('WEBHOOK_TRUST_PROXY_HEADERS', default=False)
SCRIPT_API_DEEP_HEALTH_MAX_AGE_SECONDS = max(300, _env_int('SCRIPT_API_DEEP_HEALTH_MAX_AGE_SECONDS', 6 * 3600))
SCRIPT_API_DEEP_HEALTH_MIN_TOKENS = max(1, _env_int('SCRIPT_API_DEEP_HEALTH_MIN_TOKENS', 1))


def _extract_client_ip() -> str:
    if WEBHOOK_TRUST_PROXY_HEADERS:
        xff = str(request.headers.get('X-Forwarded-For', '')).strip()
        if xff:
            return xff.split(',')[0].strip()
    return str(request.remote_addr or '').strip()


def _extract_webhook_token() -> str:
    auth_header = str(request.headers.get('Authorization', '')).strip()
    if auth_header.lower().startswith('bearer '):
        token = auth_header[7:].strip()
        if token:
            return token

    for header_name in ('X-Webhook-Token', 'X-API-Key'):
        token = str(request.headers.get(header_name, '')).strip()
        if token:
            return token

    query_token = str(request.args.get('token', '')).strip()
    if query_token:
        return query_token
    return ''


def _verify_webhook_signature(payload: bytes) -> tuple[bool, str]:
    if not WEBHOOK_SHARED_SECRET:
        return False, 'missing_shared_secret'

    signature = str(request.headers.get('X-Webhook-Signature', '')).strip()
    timestamp_raw = str(request.headers.get('X-Webhook-Timestamp', '')).strip()
    if not signature:
        return False, 'missing_signature'
    if not timestamp_raw:
        return False, 'missing_timestamp'

    try:
        timestamp_int = int(timestamp_raw)
    except ValueError:
        return False, 'invalid_timestamp'

    now_ts = int(time.time())
    if abs(now_ts - timestamp_int) > WEBHOOK_SIGNATURE_MAX_AGE_SECONDS:
        return False, 'stale_signature'

    signed_payload = f'{timestamp_int}.'.encode('utf-8') + (payload or b'')
    expected = 'sha256=' + hmac.new(
        WEBHOOK_SHARED_SECRET.encode('utf-8'),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected.lower(), signature.lower()):
        return False, 'invalid_signature'

    return True, 'ok'


def _require_webhook_access(*, require_signature: bool = False):
    if not WEBHOOK_REQUIRE_AUTH and not (require_signature and WEBHOOK_REQUIRE_SIGNATURE):
        return None

    if not WEBHOOK_SHARED_SECRET:
        return jsonify({
            'status': 'error',
            'message': 'Webhook authentication is enabled but WEBHOOK_SHARED_SECRET is missing',
        }), 503

    if WEBHOOK_REQUIRE_AUTH:
        token = _extract_webhook_token()
        if not token or not hmac.compare_digest(token, WEBHOOK_SHARED_SECRET):
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized webhook request',
            }), 401

    if require_signature and WEBHOOK_REQUIRE_SIGNATURE:
        payload = request.get_data(cache=True) or b''
        valid, reason = _verify_webhook_signature(payload)
        if not valid:
            return jsonify({
                'status': 'error',
                'message': reason,
            }), 401

    return None

class WebhookServer:
    def __init__(self):
        self.cache_data = {}
        self.fallback_data = {}
        self.symbol_cache = {}
        self._address_chain_cache = {}
        # Persisted per-token metric timestamps
        self.token_metrics = {}
        # Persisted per-token per-source success timestamps
        self.endpoint_metrics = {}
        # Per-source cooldown timestamps when rate limits are hit
        self.source_cooldowns = {}
        self.source_rate_policies = self._load_source_rate_policy()
        # policy hours for skip heuristic (default 48h)
        self.metric_skip_hours = 48
        self.cache_retention_hours = 24
        self.fallback_sync_hours = 4
        self.assessor = None
        self._assessor_lock = threading.Lock()
        self._swr_refresh_lock = threading.Lock()
        self._swr_refresh_inflight = set()
        self.load_existing_data()
        # Load skip policy from settings/env
        self._load_cache_policy()
        # Initialize full assessment delegate so webhook uses the same integrated API surface.
        self._init_assessor_delegate()

    def _init_assessor_delegate(self):
        """Initialize DeFiRiskAssessor delegate for comprehensive webhook enrichment."""
        try:
            if V2_SCRIPT_DIR not in sys.path:
                sys.path.append(V2_SCRIPT_DIR)
            from defi_complete_risk_assessment_clean import DeFiRiskAssessor
            self.assessor = DeFiRiskAssessor()
            print("✅ DeFiRiskAssessor delegate initialized in webhook server")
        except Exception as e:
            self.assessor = None
            print(f"⚠️ Could not initialize DeFiRiskAssessor delegate: {e}")

    def _refresh_token_mappings(self) -> bool:
        """Regenerate token mappings with consistent interpreter/path settings."""
        try:
            import subprocess
            import importlib
            if not os.path.exists(TOKEN_MAPPINGS_GENERATOR):
                print(f"  ⚠️  Token mappings generator not found: {TOKEN_MAPPINGS_GENERATOR}")
                return False
            subprocess.run(
                [sys.executable, TOKEN_MAPPINGS_GENERATOR],
                cwd=V2_SCRIPT_DIR,
                check=True
            )
            importlib.invalidate_caches()
            return True
        except Exception as e:
            print(f"  ⚠️  Failed to regenerate token mappings: {e}")
            return False

    def _load_token_mapping_resolver(self, resolver_name: str) -> Optional[Callable[..., Any]]:
        """Load resolver function from token_mappings, regenerating file when needed."""
        if V2_SCRIPT_DIR not in sys.path:
            sys.path.append(V2_SCRIPT_DIR)
        try:
            import importlib
            token_mappings_module = importlib.import_module('token_mappings')
            resolver = getattr(token_mappings_module, resolver_name, None)
            if callable(resolver):
                return resolver
        except Exception:
            pass

        if not self._refresh_token_mappings():
            return None

        try:
            import importlib
            token_mappings_module = importlib.import_module('token_mappings')
            token_mappings_module = importlib.reload(token_mappings_module)
            resolver = getattr(token_mappings_module, resolver_name, None)
            return resolver if callable(resolver) else None
        except Exception as e:
            print(f"  ⚠️  Failed to load token mapping resolver '{resolver_name}': {e}")
            return None

    def _load_cache_policy(self):
        try:
            # env override
            env_val = os.getenv('RESPECT_48H_METRIC_SKIP', '1').strip().lower()
            self.respect_skip = False if env_val in ('0', 'false', 'no') else True
            # optional settings.json
            settings_path = os.path.join(DATA_DIR, 'settings.json')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                cache_cfg = settings.get('cache', {}) if isinstance(settings, dict) else {}
                self.respect_skip = bool(cache_cfg.get('respect_48h_metric_skip', self.respect_skip))
                self.metric_skip_hours = int(cache_cfg.get('metric_skip_hours', self.metric_skip_hours))
                retention_text = cache_cfg.get('cache_retention', f'{int(self.cache_retention_hours)} hours')
                self.cache_retention_hours = self._parse_duration_to_hours(retention_text, self.cache_retention_hours)
                fallback_sync_text = cache_cfg.get('fallback_sync_interval', f'{int(self.fallback_sync_hours)} hours')
                self.fallback_sync_hours = self._parse_duration_to_hours(fallback_sync_text, self.fallback_sync_hours)
                custom_sync_hours = cache_cfg.get('fallback_sync_custom_hours')
                if custom_sync_hours not in (None, ''):
                    try:
                        custom_sync_hours = float(custom_sync_hours)
                        if custom_sync_hours > 0:
                            if str(fallback_sync_text).strip().lower() == 'custom':
                                self.fallback_sync_hours = custom_sync_hours
                    except Exception:
                        pass
                custom_days = cache_cfg.get('cache_retention_custom_days')
                if custom_days not in (None, ''):
                    try:
                        self.cache_retention_hours = max(self.cache_retention_hours, float(custom_days) * 24.0)
                    except Exception:
                        pass
                self.cache_retention_hours = max(1.0, min(float(self.cache_retention_hours), 24.0 * 365.0))
                self.fallback_sync_hours = max(1.0 / 60.0, min(float(self.fallback_sync_hours), 24.0 * 365.0))
        except Exception:
            self.respect_skip = True
            self.cache_retention_hours = 24
            self.fallback_sync_hours = 4

    @staticmethod
    def _parse_duration_to_hours(value, default_hours=24.0):
        """Parse settings durations (minutes/hours/days/weeks/months/years) into hours."""
        try:
            if isinstance(value, (int, float)):
                parsed = float(value)
                return parsed if parsed > 0 else float(default_hours)
            text = str(value or '').strip().lower()
            if not text:
                return float(default_hours)
            amount_token = ''.join(ch for ch in text if ch.isdigit() or ch == '.')
            if not amount_token:
                return float(default_hours)
            amount = float(amount_token)
            if 'minute' in text:
                return max(1.0 / 60.0, amount / 60.0)
            if 'day' in text:
                return amount * 24.0
            if 'week' in text:
                return amount * 24.0 * 7.0
            if 'month' in text:
                return amount * 24.0 * 30.0
            if 'year' in text:
                return amount * 24.0 * 365.0
            return amount
        except Exception:
            return float(default_hours)

    def _effective_skip_window_hours(self):
        """Use the largest skip window so already-found values are kept for retention horizon."""
        try:
            metric_window = float(getattr(self, 'metric_skip_hours', 48) or 48)
        except Exception:
            metric_window = 48.0
        try:
            retention_window = float(getattr(self, 'cache_retention_hours', 24) or 24)
        except Exception:
            retention_window = 24.0
        return max(1.0, max(metric_window, retention_window))

    def _load_source_rate_policy(self):
        """Load per-source cooldown defaults from shared free-tier rate-limit policy file."""
        try:
            if not os.path.exists(API_RATE_POLICY_FILE):
                return {}
            with open(API_RATE_POLICY_FILE, 'r') as f:
                payload = json.load(f)
            apis = payload.get('apis', {}) if isinstance(payload, dict) else {}
            policies = {}
            if isinstance(apis, dict):
                for api_name, cfg in apis.items():
                    if not isinstance(cfg, dict):
                        continue
                    cooldown = cfg.get('cooldown_seconds', cfg.get('window_seconds', 60))
                    try:
                        cooldown = float(cooldown)
                    except Exception:
                        cooldown = 60.0
                    policies[str(api_name).lower()] = max(1.0, cooldown)
            return policies
        except Exception:
            return {}
        
    def cleanup_duplicate_tokens(self):
        """Clean up duplicate tokens in cache (with and without chain suffixes)"""
        if 'tokens' not in self.cache_data:
            return
        
        tokens = self.cache_data['tokens']
        cleaned_tokens = {}
        duplicates_removed = 0
        
        for token_key, token_data in tokens.items():
            # Extract clean address (remove chain suffix)
            clean_address = token_key.split('_')[0] if '_' in token_key else token_key
            
            # If we already have this clean address, skip the duplicate
            if clean_address in cleaned_tokens:
                print(f"🔄 Removing duplicate token: {token_key} (keeping {clean_address})")
                duplicates_removed += 1
                continue
            
            # Store with clean address as key
            cleaned_tokens[clean_address] = token_data
        
        self.cache_data['tokens'] = cleaned_tokens
        print(f"✅ Cleaned up {duplicates_removed} duplicate tokens. Cache now has {len(cleaned_tokens)} unique tokens.")
        
    def load_existing_data(self):
        """Load existing cache and fallback data"""
        
        # Load cache
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.cache_data = json.load(f)
                print(f"✅ Loaded cache with {len(self.cache_data.get('tokens', {}))} tokens")
                
                # Clean up duplicates
                self.cleanup_duplicate_tokens()
                # Load token metric timestamps if available
                if 'token_metrics' in self.cache_data and isinstance(self.cache_data['token_metrics'], dict):
                    self.token_metrics = self.cache_data['token_metrics']
                else:
                    self.token_metrics = {}
                if 'endpoint_metrics' in self.cache_data and isinstance(self.cache_data['endpoint_metrics'], dict):
                    self.endpoint_metrics = self.cache_data['endpoint_metrics']
                else:
                    self.endpoint_metrics = {}
                
            except Exception as e:
                print(f"⚠️  Error loading cache: {e}")
                self.cache_data = {'tokens': {}, 'last_updated': 0}
        else:
            self.cache_data = {'tokens': {}, 'last_updated': 0}
            
        # Load fallback data
        if os.path.exists(FALLBACK_FILE):
            try:
                with open(FALLBACK_FILE, 'r') as f:
                    self.fallback_data = json.load(f)
                print(f"✅ Loaded fallback data with {len(self.fallback_data.get('token_mappings', {}))} tokens")
            except Exception as e:
                print(f"⚠️  Error loading fallback data: {e}")
                self.fallback_data = {'token_mappings': {}, 'metadata': {}}
        else:
            self.fallback_data = {'token_mappings': {}, 'metadata': {}}
            
        # Load symbol cache
        if os.path.exists(SYMBOL_CACHE_FILE):
            try:
                with open(SYMBOL_CACHE_FILE, 'r') as f:
                    self.symbol_cache = json.load(f)
                print(f"✅ Loaded symbol cache with {len(self.symbol_cache.get('symbols', {}))} symbols")
            except Exception as e:
                print(f"⚠️  Error loading symbol cache: {e}")
                self.symbol_cache = {'symbols': {}, 'metadata': {}}
        else:
            self.symbol_cache = {'symbols': {}, 'metadata': {}}
    
    def save_cache_data(self):
        """Save cache data to file"""
        try:
            self.cache_data['last_updated'] = time.time()
            # persist token metric timestamps
            self.cache_data['token_metrics'] = self.token_metrics
            self.cache_data['endpoint_metrics'] = self.endpoint_metrics
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
            print(f"✅ Cache saved with {len(self.cache_data.get('tokens', {}))} tokens")
        except Exception as e:
            print(f"❌ Error saving cache: {e}")
    
    def save_fallback_data(self):
        """Save fallback data to file"""
        try:
            self.fallback_data['metadata']['last_updated'] = datetime.now().isoformat()
            with open(FALLBACK_FILE, 'w') as f:
                json.dump(self.fallback_data, f, indent=2)
            print(f"✅ Fallback data saved with {len(self.fallback_data.get('token_mappings', {}))} tokens")
        except Exception as e:
            print(f"❌ Error saving fallback data: {e}")
    
    def save_symbol_cache(self):
        """Save symbol cache to file"""
        try:
            self.symbol_cache['metadata']['last_updated'] = datetime.now().isoformat()
            with open(SYMBOL_CACHE_FILE, 'w') as f:
                json.dump(self.symbol_cache, f, indent=2)
            print(f"✅ Symbol cache saved with {len(self.symbol_cache.get('symbols', {}))} symbols")
        except Exception as e:
            print(f"❌ Error saving symbol cache: {e}")

    @staticmethod
    def _to_float(value):
        """Safely convert numeric-like values to float."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_chain_code(chain_value):
        """Normalize chain aliases into canonical internal codes."""
        raw = str(chain_value or "").strip().lower().strip("/")
        if normalize_token_chain_hint is not None:
            hinted = normalize_token_chain_hint(raw)
            return hinted if hinted else raw
        # Fallback if `web_portal` package is not importable (keep in sync with hodler_chain_codes).
        alias_map = {
            "eth": "eth",
            "ethereum": "eth",
            "mainnet": "eth",
            "erc20": "eth",
            "op": "op",
            "optimism": "op",
            "polygon": "polygon",
            "matic": "polygon",
            "arb": "arbitrum",
            "arbitrum": "arbitrum",
            "base": "base",
            "mantle": "mantle",
            "mnt": "mantle",
            "zksync": "zksync",
            "thorchain": "thorchain",
            "thor": "thorchain",
            "bsc": "bsc",
            "binance": "bsc",
            "binance-smart-chain": "bsc",
            "linea": "linea",
            "avax": "avax",
            "avalanche": "avax",
            "avalanche-c": "avax",
            "sonic": "sonic",
            "s": "sonic",
            "sei": "sei",
            "tron": "tron",
            "trx": "tron",
            "sol": "solana",
            "solana": "solana",
            "spl": "solana",
        }
        return alias_map.get(raw, raw if raw else "")

    @staticmethod
    def _is_placeholder_holders_metric(value):
        """Detect rounded holder placeholders that should never overwrite real values."""
        try:
            parsed = int(float(value or 0))
        except Exception:
            return True
        if parsed <= 0:
            return True
        return parsed in {2500, 5000, 10000, 25000, 50000, 100000, 200000, 250000, 500000, 1000000}

    def _extract_candidate_metrics(self, payload):
        """Extract best candidate metrics from runtime payload (aggregates + per-source blobs)."""
        candidate = {
            'market_cap': 0.0,
            'volume_24h': 0.0,
            'holders': 0.0,
            'liquidity': 0.0,
            'price': 0.0
        }
        if not isinstance(payload, dict):
            return candidate

        def _take_max(metric, raw_value, allow_placeholder_holders=False):
            parsed = self._to_float(raw_value)
            if parsed is None or parsed <= 0:
                return
            if metric == 'holders':
                parsed = int(parsed)
                if parsed <= 0:
                    return
                if (not allow_placeholder_holders) and self._is_placeholder_holders_metric(parsed):
                    return
            current = self._to_float(candidate.get(metric, 0)) or 0.0
            if parsed > current:
                candidate[metric] = float(parsed)

        aggregates = payload.get('aggregates', {}) if isinstance(payload.get('aggregates'), dict) else {}
        market_agg = aggregates.get('market', {}) if isinstance(aggregates.get('market'), dict) else {}
        onchain_agg = aggregates.get('onchain', {}) if isinstance(aggregates.get('onchain'), dict) else {}
        liq_agg = aggregates.get('liquidity', {}) if isinstance(aggregates.get('liquidity'), dict) else {}

        _take_max('market_cap', market_agg.get('market_cap'))
        _take_max('volume_24h', market_agg.get('volume_24h'))
        _take_max('price', market_agg.get('price'))
        _take_max('holders', onchain_agg.get('holders'))
        _take_max('liquidity', liq_agg.get('liquidity'))

        market_blob = payload.get('market_data', {}) if isinstance(payload.get('market_data'), dict) else {}
        for source_payload in market_blob.values():
            if not isinstance(source_payload, dict):
                continue
            _take_max('market_cap', source_payload.get('market_cap') or source_payload.get('marketCap') or source_payload.get('fdv'))
            _take_max(
                'volume_24h',
                source_payload.get('volume_24h')
                or source_payload.get('volume24h')
                or source_payload.get('volumeUsd24Hr')
                or source_payload.get('usd_24h_vol')
            )
            _take_max('price', source_payload.get('price') or source_payload.get('priceUsd') or source_payload.get('usd'))
            nested_market = source_payload.get('market_data', {}) if isinstance(source_payload.get('market_data'), dict) else {}
            if nested_market:
                _take_max('market_cap', ((nested_market.get('market_cap') or {}).get('usd')))
                _take_max('volume_24h', ((nested_market.get('total_volume') or {}).get('usd')))
                _take_max('price', ((nested_market.get('current_price') or {}).get('usd')))

        onchain_blob = payload.get('onchain_data', {}) if isinstance(payload.get('onchain_data'), dict) else {}
        for source_payload in onchain_blob.values():
            if not isinstance(source_payload, dict):
                continue
            _take_max(
                'holders',
                source_payload.get('holders')
                or source_payload.get('total_holders')
                or source_payload.get('holder_count')
                or source_payload.get('holders_count')
            )
            _take_max('liquidity', source_payload.get('liquidity') or source_payload.get('liquidity_score') or source_payload.get('total_liquidity'))

        liquidity_blob = payload.get('liquidity_data', {}) if isinstance(payload.get('liquidity_data'), dict) else {}
        for source_payload in liquidity_blob.values():
            if not isinstance(source_payload, dict):
                continue
            _take_max('liquidity', source_payload.get('liquidity') or source_payload.get('liquidity_score') or source_payload.get('total_liquidity'))
            _take_max('volume_24h', source_payload.get('volume_24h') or source_payload.get('volumeUSD') or source_payload.get('volume'))

        # Top-level fields remain last fallback only.
        _take_max('market_cap', payload.get('market_cap'))
        _take_max('volume_24h', payload.get('volume_24h'))
        _take_max('holders', payload.get('holders'))
        _take_max('liquidity', payload.get('liquidity'))
        _take_max('price', payload.get('price'))

        if candidate['holders'] > 0:
            candidate['holders'] = int(candidate['holders'])
        return candidate

    def _collect_source_labels_for_confidence(self, payload_blob):
        """Collect source labels that actually contributed signal."""
        labels = []
        if not isinstance(payload_blob, dict):
            return labels

        def _payload_has_signal(payload):
            if not isinstance(payload, dict):
                return False
            candidate_keys = (
                'market_cap', 'marketCap', 'fdv',
                'volume_24h', 'volume24h', 'volumeUsd24Hr', 'usd_24h_vol',
                'price', 'priceUsd', 'usd',
                'holders', 'holder_count', 'holders_count', 'total_holders',
                'liquidity', 'liquidity_score', 'total_liquidity'
            )
            for key in candidate_keys:
                parsed = self._to_float(payload.get(key))
                if parsed is not None and parsed > 0:
                    return True
            for nested_value in payload.values():
                if isinstance(nested_value, dict) and _payload_has_signal(nested_value):
                    return True
            return False

        for source_name, payload in payload_blob.items():
            source_label = str(source_name or '').strip()
            if not source_label:
                continue
            if _payload_has_signal(payload):
                labels.append(source_label)
        return labels

    def _build_metric_source_values(self, payload, chain):
        """Build metric->source->value map used for overwrite corroboration checks."""
        metric_sources = {'market_cap': {}, 'volume_24h': {}, 'holders': {}, 'liquidity': {}}
        source_probe = {
            'market_data': payload.get('market_data', {}) if isinstance(payload, dict) and isinstance(payload.get('market_data'), dict) else {},
            'onchain_data': payload.get('onchain_data', {}) if isinstance(payload, dict) and isinstance(payload.get('onchain_data'), dict) else {},
            'liquidity_data': payload.get('liquidity_data', {}) if isinstance(payload, dict) and isinstance(payload.get('liquidity_data'), dict) else {},
        }
        chain_key = self._normalize_chain_code(chain)

        assessor = self.assessor
        if assessor and hasattr(assessor, '_collect_metric_source_values_for_overwrite'):
            try:
                with self._assessor_lock:
                    collected = assessor._collect_metric_source_values_for_overwrite(source_probe, chain_key)
                if isinstance(collected, dict):
                    for metric_name in metric_sources.keys():
                        metric_blob = collected.get(metric_name, {})
                        if isinstance(metric_blob, dict):
                            metric_sources[metric_name] = metric_blob
                    return metric_sources
            except Exception:
                pass

        def _set_metric(metric_name, source_name, raw_value, holders_metric=False):
            source_key = str(source_name or '').strip().lower()
            if not source_key:
                return
            parsed = self._to_float(raw_value)
            if parsed is None or parsed <= 0:
                return
            if holders_metric:
                parsed = int(parsed)
                if parsed <= 0 or self._is_placeholder_holders_metric(parsed):
                    return
            existing = self._to_float(metric_sources[metric_name].get(source_key, 0)) or 0.0
            if parsed > existing:
                metric_sources[metric_name][source_key] = float(parsed)

        for source_name, source_payload in source_probe['market_data'].items():
            if not isinstance(source_payload, dict):
                continue
            _set_metric('market_cap', source_name, source_payload.get('market_cap') or source_payload.get('marketCap') or source_payload.get('fdv'))
            _set_metric(
                'volume_24h',
                source_name,
                source_payload.get('volume_24h')
                or source_payload.get('volume24h')
                or source_payload.get('volumeUsd24Hr')
                or source_payload.get('usd_24h_vol')
            )
            _set_metric(
                'holders',
                source_name,
                source_payload.get('holders') or source_payload.get('holder_count') or source_payload.get('holders_count'),
                holders_metric=True
            )
            _set_metric('liquidity', source_name, source_payload.get('liquidity') or source_payload.get('liquidity_score') or source_payload.get('total_liquidity'))

        for source_name, source_payload in source_probe['onchain_data'].items():
            if not isinstance(source_payload, dict):
                continue
            _set_metric(
                'holders',
                source_name,
                source_payload.get('holders')
                or source_payload.get('total_holders')
                or source_payload.get('holder_count')
                or source_payload.get('holders_count'),
                holders_metric=True
            )
            _set_metric('liquidity', source_name, source_payload.get('liquidity') or source_payload.get('liquidity_score') or source_payload.get('total_liquidity'))

        for source_name, source_payload in source_probe['liquidity_data'].items():
            if not isinstance(source_payload, dict):
                continue
            _set_metric('liquidity', source_name, source_payload.get('liquidity') or source_payload.get('liquidity_score') or source_payload.get('total_liquidity'))

        return metric_sources

    def _apply_assessment_overwrite_policy(
        self,
        entry,
        candidate_metrics,
        metric_source_values,
        existing_source_labels,
        new_source_labels,
        chain
    ):
        """Resolve metric overwrites using the same validator policy as the assessment pipeline."""
        if not isinstance(entry, dict):
            entry = {}
        if not isinstance(candidate_metrics, dict):
            candidate_metrics = {}
        if not isinstance(metric_source_values, dict):
            metric_source_values = {}

        resolved_values = {
            'market_cap': 0.0,
            'volume_24h': 0.0,
            'holders': 0.0,
            'liquidity': 0.0,
            'price': 0.0
        }
        chain_key = self._normalize_chain_code(chain)
        existing_source_labels = [str(s or '').strip() for s in (existing_source_labels or []) if str(s or '').strip()]
        new_source_labels = [str(s or '').strip() for s in (new_source_labels or []) if str(s or '').strip()]
        if not new_source_labels:
            new_source_labels = list(existing_source_labels)

        assessor = self.assessor
        required_methods = (
            '_normalize_metric_for_overwrite',
            '_source_confidence_score',
            '_resolve_metric_overwrite',
            '_read_metric_history_for_overwrite',
            '_append_metric_history_snapshot'
        )
        if not assessor or not all(hasattr(assessor, method_name) for method_name in required_methods):
            old_values = {
                'market_cap': self._to_float(entry.get('market_cap')) or 0.0,
                'volume_24h': self._to_float(entry.get('volume_24h')) or 0.0,
                'holders': float(int(self._to_float(entry.get('holders')) or 0)),
                'liquidity': self._to_float(entry.get('liquidity')) or 0.0,
                'price': self._to_float(entry.get('price')) or 0.0,
            }
            for metric_name in ('market_cap', 'volume_24h', 'liquidity', 'price'):
                candidate = self._to_float(candidate_metrics.get(metric_name)) or 0.0
                resolved_values[metric_name] = candidate if candidate > 0 else old_values[metric_name]
            candidate_holders = int(self._to_float(candidate_metrics.get('holders')) or 0)
            old_holders = int(old_values['holders'])
            if candidate_holders > 0 and not self._is_placeholder_holders_metric(candidate_holders):
                resolved_values['holders'] = float(candidate_holders)
            elif old_holders > 0 and not self._is_placeholder_holders_metric(old_holders):
                resolved_values['holders'] = float(old_holders)
            entry['overwrite_policy'] = {
                'applied_at': time.time(),
                'old_source_confidence': 0.0,
                'new_source_confidence': 0.0,
                'decisions': {
                    'market_cap': 'fallback_keep_or_replace',
                    'volume_24h': 'fallback_keep_or_replace',
                    'holders': 'fallback_keep_or_replace',
                    'liquidity': 'fallback_keep_or_replace',
                    'price': 'fallback_keep_or_replace'
                }
            }
            return resolved_values

        with self._assessor_lock:
            old_values = {
                'market_cap': assessor._normalize_metric_for_overwrite('market_cap', entry.get('market_cap', 0), chain_key),
                'volume_24h': assessor._normalize_metric_for_overwrite('volume_24h', entry.get('volume_24h', 0), chain_key),
                'holders': assessor._normalize_metric_for_overwrite('holders', entry.get('holders', 0), chain_key),
                'liquidity': assessor._normalize_metric_for_overwrite('liquidity', entry.get('liquidity', 0), chain_key),
                'price': assessor._normalize_metric_for_overwrite('price', entry.get('price', 0), chain_key),
            }
            aggregates = entry.get('aggregates', {}) if isinstance(entry.get('aggregates'), dict) else {}
            agg_market = aggregates.get('market', {}) if isinstance(aggregates.get('market'), dict) else {}
            agg_onchain = aggregates.get('onchain', {}) if isinstance(aggregates.get('onchain'), dict) else {}
            agg_liquidity = aggregates.get('liquidity', {}) if isinstance(aggregates.get('liquidity'), dict) else {}
            if old_values['market_cap'] <= 0:
                old_values['market_cap'] = assessor._normalize_metric_for_overwrite('market_cap', agg_market.get('market_cap', 0), chain_key)
            if old_values['volume_24h'] <= 0:
                old_values['volume_24h'] = assessor._normalize_metric_for_overwrite('volume_24h', agg_market.get('volume_24h', 0), chain_key)
            if old_values['holders'] <= 0:
                old_values['holders'] = assessor._normalize_metric_for_overwrite('holders', agg_onchain.get('holders', 0), chain_key)
            if old_values['liquidity'] <= 0:
                old_values['liquidity'] = assessor._normalize_metric_for_overwrite('liquidity', agg_liquidity.get('liquidity', 0), chain_key)
            if old_values['price'] <= 0:
                old_values['price'] = assessor._normalize_metric_for_overwrite('price', agg_market.get('price', 0), chain_key)

            candidate_values = {
                'market_cap': assessor._normalize_metric_for_overwrite('market_cap', candidate_metrics.get('market_cap', 0), chain_key),
                'volume_24h': assessor._normalize_metric_for_overwrite('volume_24h', candidate_metrics.get('volume_24h', 0), chain_key),
                'holders': assessor._normalize_metric_for_overwrite('holders', candidate_metrics.get('holders', 0), chain_key),
                'liquidity': assessor._normalize_metric_for_overwrite('liquidity', candidate_metrics.get('liquidity', 0), chain_key),
                'price': assessor._normalize_metric_for_overwrite('price', candidate_metrics.get('price', 0), chain_key),
            }

            old_confidence = assessor._source_confidence_score(existing_source_labels)
            new_confidence = assessor._source_confidence_score(new_source_labels)
            policy_log = {}
            for metric_name in ('market_cap', 'volume_24h', 'holders', 'liquidity'):
                resolved_value, was_updated, decision_reason = assessor._resolve_metric_overwrite(
                    metric_name,
                    candidate_values.get(metric_name, 0),
                    old_values.get(metric_name, 0),
                    chain_key,
                    metric_source_values,
                    old_confidence,
                    new_confidence,
                    assessor._read_metric_history_for_overwrite(entry, metric_name, chain_key)
                )
                if not was_updated and old_values.get(metric_name, 0) > 0:
                    resolved_value = old_values.get(metric_name, 0)
                resolved_values[metric_name] = resolved_value
                policy_log[metric_name] = decision_reason

            resolved_values['price'] = candidate_values['price'] if candidate_values['price'] > 0 else old_values['price']
            policy_log['price'] = 'accept_valid_price' if candidate_values['price'] > 0 else 'keep_existing_price'
            entry['overwrite_policy'] = {
                'applied_at': time.time(),
                'old_source_confidence': old_confidence,
                'new_source_confidence': new_confidence,
                'decisions': policy_log
            }
            assessor._append_metric_history_snapshot(entry, resolved_values, chain_key)
        return resolved_values

    def _apply_resolved_metrics_to_entry(self, entry, resolved_values):
        """Apply resolved metrics to top-level fields and aggregate sections."""
        if not isinstance(entry, dict):
            return
        if not isinstance(resolved_values, dict):
            resolved_values = {}

        market_cap = self._to_float(resolved_values.get('market_cap')) or 0.0
        volume_24h = self._to_float(resolved_values.get('volume_24h')) or 0.0
        holders = int(self._to_float(resolved_values.get('holders')) or 0)
        liquidity = self._to_float(resolved_values.get('liquidity')) or 0.0
        price = self._to_float(resolved_values.get('price')) or 0.0

        entry['market_cap'] = market_cap if market_cap > 0 else 0.0
        entry['volume_24h'] = volume_24h if volume_24h > 0 else 0.0
        entry['holders'] = holders if holders > 0 else 0
        entry['liquidity'] = liquidity if liquidity > 0 else 0.0
        entry['price'] = price if price > 0 else 0.0

        aggregates = entry.get('aggregates', {})
        if not isinstance(aggregates, dict):
            aggregates = {}
        market_agg = aggregates.get('market', {})
        if not isinstance(market_agg, dict):
            market_agg = {}
        onchain_agg = aggregates.get('onchain', {})
        if not isinstance(onchain_agg, dict):
            onchain_agg = {}
        liq_agg = aggregates.get('liquidity', {})
        if not isinstance(liq_agg, dict):
            liq_agg = {}

        if market_cap > 0:
            market_agg['market_cap'] = market_cap
        if volume_24h > 0:
            market_agg['volume_24h'] = volume_24h
        if price > 0:
            market_agg['price'] = price
        if holders > 0:
            onchain_agg['holders'] = holders
        if liquidity > 0:
            liq_agg['liquidity'] = liquidity

        if market_agg:
            aggregates['market'] = market_agg
        if onchain_agg:
            aggregates['onchain'] = onchain_agg
        if liq_agg:
            aggregates['liquidity'] = liq_agg
        entry['aggregates'] = aggregates

    def _enqueue_swr_refresh(self, token_address):
        """Serve stale data now and refresh the same token in background once."""
        token_key = str(token_address or '').strip()
        if not token_key:
            return False
        with self._swr_refresh_lock:
            if token_key in self._swr_refresh_inflight:
                return False
            self._swr_refresh_inflight.add(token_key)

        def _worker():
            try:
                refreshed_data = self.fetch_real_time_data(token_key)
                if refreshed_data:
                    self.update_token_data(token_key, real_time_data=refreshed_data)
                    self.update_fallback_data_with_real_data(token_key, refreshed_data)
                    self.save_cache_data()
            except Exception as e:
                print(f"⚠️  SWR refresh failed for {token_key}: {e}")
            finally:
                with self._swr_refresh_lock:
                    self._swr_refresh_inflight.discard(token_key)

        thread = threading.Thread(
            target=_worker,
            daemon=True,
            name=f"swr_refresh_{token_key[:10]}"
        )
        thread.start()
        return True

    def _load_address_chain_cache(self):
        """Build an address -> chain cache from data/tokens.csv."""
        csv_file = os.path.join(DATA_DIR, 'tokens.csv')
        cache = {}
        try:
            if not os.path.exists(csv_file):
                self._address_chain_cache = {}
                return
            import csv
            with open(csv_file, newline='') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    raw_address = (
                        row.get('address')
                        or row.get('Address')
                        or row.get('contract_address')
                        or row.get('Contract Address')
                        or ''
                    )
                    raw_chain = row.get('chain') or row.get('Chain') or ''
                    address = str(raw_address).strip().lower()
                    chain = self._normalize_chain_code(raw_chain)
                    if address and chain:
                        cache[address] = chain
            self._address_chain_cache = cache
        except Exception:
            self._address_chain_cache = {}

    def _resolve_chain_for_token(self, original_token_address, clean_address):
        """Resolve chain code for a token (eth/op/polygon/etc.)."""
        try:
            if isinstance(original_token_address, str) and '_' in original_token_address:
                suffix = original_token_address.split('_')[-1].strip().lower()
                normalized_suffix = self._normalize_chain_code(suffix)
                if normalized_suffix:
                    return normalized_suffix
        except Exception:
            pass

        # Heuristic: base58 mint-like address indicates Solana.
        try:
            addr = str(clean_address or '').strip()
            if addr and not addr.startswith('0x') and 32 <= len(addr) <= 44:
                if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]+", addr):
                    return 'solana'
        except Exception:
            pass

        # Prefer tokens.csv chain mapping when available.
        try:
            if not self._address_chain_cache:
                self._load_address_chain_cache()
            cached_chain = self._address_chain_cache.get(str(clean_address or '').strip().lower(), '')
            if cached_chain:
                return cached_chain
        except Exception:
            pass

        l2_chain = self._get_l2_chain(clean_address)
        if l2_chain == 'optimism':
            return 'op'
        return 'eth'

    def _fetch_assessor_onchain_snapshot(self, token_address, chain):
        """Flatten assessor on-chain payload into webhook format."""
        if self.assessor is None:
            return None
        try:
            payload = self.assessor.fetch_onchain_data(token_address, chain) or {}
            holders_blob = payload.get('holders', {}) if isinstance(payload.get('holders'), dict) else {}
            supply_blob = payload.get('supply', {}) if isinstance(payload.get('supply'), dict) else {}
            activity_blob = payload.get('activity', {}) if isinstance(payload.get('activity'), dict) else {}
            out = {
                'holders': int(self._to_float(holders_blob.get('total_holders')) or 0),
                'total_supply': float(self._to_float(supply_blob.get('total_supply')) or 0),
                'tx_count': int(self._to_float(activity_blob.get('tx_count')) or 0),
                'source': 'assessor_onchain'
            }
            return out if self._has_valid_onchain_data(out) else None
        except Exception:
            return None

    def _get_existing_token_entry(self, token_address, clean_address):
        """Get prior cache entry using exact key and normalized address fallback."""
        tokens_cache = self.cache_data.get('tokens', {})
        if token_address in tokens_cache and isinstance(tokens_cache[token_address], dict):
            return tokens_cache[token_address]
        if clean_address in tokens_cache and isinstance(tokens_cache[clean_address], dict):
            return tokens_cache[clean_address]
        return {}

    def _build_market_snapshot_for_flags(self, token_data):
        """Build a flattened market snapshot used by red-flag checks."""
        market_snapshot = {}
        try:
            agg_market = ((token_data.get('aggregates') or {}).get('market') or {})
            agg_onchain = ((token_data.get('aggregates') or {}).get('onchain') or {})
            agg_liq = ((token_data.get('aggregates') or {}).get('liquidity') or {})
            market_snapshot = {
                'market_cap': self._to_float(agg_market.get('market_cap')) or 0,
                'volume_24h': self._to_float(agg_market.get('volume_24h')) or 0,
                'price': self._to_float(agg_market.get('price')) or 0,
                'holders': self._to_float(agg_onchain.get('holders')) or 0,
                'liquidity': self._to_float(agg_liq.get('liquidity')) or 0
            }
        except Exception:
            market_snapshot = {}
        return market_snapshot

    def _compute_value_changes(self, previous_entry, current_token_data):
        """Compare aggregate values and red flags against previous cache snapshot."""
        if not isinstance(previous_entry, dict):
            return {}

        prev_aggregates = previous_entry.get('aggregates', {})
        curr_aggregates = current_token_data.get('aggregates', {})
        if not isinstance(prev_aggregates, dict):
            prev_aggregates = {}
        if not isinstance(curr_aggregates, dict):
            curr_aggregates = {}

        metrics = [
            ('market', 'market_cap'),
            ('market', 'volume_24h'),
            ('market', 'price'),
            ('market', 'change_24h'),
            ('onchain', 'holders'),
            ('onchain', 'total_supply'),
            ('onchain', 'tx_count'),
            ('liquidity', 'liquidity'),
            ('liquidity', 'volume_24h'),
            ('liquidity', 'trade_count')
        ]

        changes = {}
        for section, key in metrics:
            prev_val = self._to_float(((prev_aggregates.get(section) or {}).get(key)))
            curr_val = self._to_float(((curr_aggregates.get(section) or {}).get(key)))
            if prev_val is None or curr_val is None:
                continue
            if prev_val == curr_val:
                continue
            delta = curr_val - prev_val
            pct_change = None
            if abs(prev_val) > 1e-12:
                pct_change = (delta / prev_val) * 100
            changes[f"{section}.{key}"] = {
                'previous': prev_val,
                'current': curr_val,
                'delta': delta,
                'pct_change': pct_change
            }

        prev_flags = set(previous_entry.get('red_flags', []) or [])
        curr_flags = set(current_token_data.get('red_flags', []) or [])
        added = sorted(curr_flags - prev_flags)
        removed = sorted(prev_flags - curr_flags)
        if added or removed:
            changes['red_flags'] = {
                'added': added,
                'removed': removed
            }

        if changes:
            changes['updated_at'] = datetime.now().isoformat()
        return changes
    
    def fetch_real_time_data(self, token_address):
        """Fetch comprehensive real-time data for a token with smart rate limiting bypass"""
        print(f"🔄 Fetching comprehensive real-time data for {token_address}")
        
        # Clean the token address (remove chain suffix like _eth, _polygon, etc.)
        clean_address = token_address.split('_')[0] if '_' in token_address else token_address
        chain = self._resolve_chain_for_token(token_address, clean_address)
        
        existing_entry = self._get_existing_token_entry(token_address, clean_address)

        token_data = {
            'address': clean_address,
            'chain': chain,
            'timestamp': time.time(),
            'market_data': {},
            'onchain_data': {},
            'social_data': {},
            'liquidity_data': {},
            'sentiment_data': {},
            'enhanced_data': {},
            'security_data': {},
            'red_flags': [],
            'value_changes': {}
        }
        
        # Get token symbol from address
        symbol = self.get_symbol_from_address(token_address)
        token_name = (
            (existing_entry.get('name') if isinstance(existing_entry, dict) else None)
            or symbol
            or ''
        )
        if symbol:
            token_data['symbol'] = symbol
        if token_name:
            token_data['name'] = token_name
        
        # ===== MARKET DATA WITH RATE LIMIT BYPASS =====
        if symbol and not self._should_skip_metric(token_address, 'market'):
            print(f"  📊 Fetching market data for {symbol}...")
            
            # Try multiple market data sources until we get data (CoinMarketCap first to avoid CoinGecko rate limits)
            market_data_sources = [
                ('coinmarketcap', lambda: self.fetch_cmc_data(symbol)),
                ('coingecko', lambda: self.fetch_coingecko_data(symbol)),
                ('defillama', lambda: self.fetch_defillama_market_data(symbol))
            ]
            
            for source_name, fetch_func in market_data_sources:
                try:
                    source_key = f"market:{source_name}"
                    if self._is_source_rate_limited(source_key):
                        continue
                    if self._should_skip_source(token_address, source_key):
                        continue
                    print(f"    🔄 Trying {source_name}...")
                    data, was_rate_limited, last_error = self._fetch_source_with_retries(
                        source_key, fetch_func, max_attempts=3
                    )
                    if was_rate_limited:
                        continue
                    if data and self._has_valid_market_data(data):
                        token_data['market_data'][source_name] = data
                        self._mark_source_success(token_address, source_key, time.time())
                        print(f"    ✅ {source_name} data obtained")
                        # Do not break — aggregate across all sources
                    else:
                        if last_error is not None:
                            print(f"    ❌ {source_name} failed after retries: {last_error}")
                        else:
                            print(f"    ⚠️  {source_name} returned no valid data")
                except Exception as e:
                    print(f"    ❌ {source_name} failed: {e}")
                    msg = str(e).lower()
                    if '429' in msg or 'rate limit' in msg:
                        self._set_source_cooldown(source_key)
                
                # Rate limiting delay between sources
                time.sleep(1.0)
        
        # ===== ONCHAIN DATA WITH RATE LIMIT BYPASS =====
        if not self._should_skip_metric(token_address, 'onchain'):
            print(f"  ⛓️  Fetching onchain data...")
        
        chain_lower = str(chain or '').strip().lower()
        # Keep on-chain sources strictly chain-compatible to avoid cross-chain holder pollution.
        if chain_lower == 'solana':
            onchain_data_sources = [
                ('assessor_onchain', lambda: self._fetch_assessor_onchain_snapshot(clean_address, chain)),
                ('bitquery', lambda: self.assessor.fetch_bitquery_data(clean_address, chain) if self.assessor else None)
            ]
        elif chain_lower in ('op', 'optimism'):
            onchain_data_sources = [
                ('optimism', lambda: self.fetch_optimism_data(clean_address)),
                ('assessor_onchain', lambda: self._fetch_assessor_onchain_snapshot(clean_address, chain)),
            ]
        elif chain_lower in ('eth', 'ethereum'):
            onchain_data_sources = [
                ('ethplorer', lambda: self.fetch_ethplorer_data(clean_address, chain=chain_lower)),
                ('etherscan', lambda: self.fetch_etherscan_data(clean_address, chain=chain_lower)),
                ('bitquery', lambda: self.fetch_bitquery_data(clean_address)),
                ('thegraph', lambda: self.fetch_thegraph_data(clean_address, symbol) if symbol else None),
                ('assessor_onchain', lambda: self._fetch_assessor_onchain_snapshot(clean_address, chain)),
            ]
        else:
            onchain_data_sources = [
                ('assessor_onchain', lambda: self._fetch_assessor_onchain_snapshot(clean_address, chain)),
            ]
        
        for source_name, fetch_func in onchain_data_sources:
            try:
                source_key = f"onchain:{source_name}"
                if self._is_source_rate_limited(source_key):
                    continue
                if self._should_skip_source(token_address, source_key):
                    continue
                print(f"    🔄 Trying {source_name}...")
                data, was_rate_limited, last_error = self._fetch_source_with_retries(
                    source_key, fetch_func, max_attempts=3
                )
                if was_rate_limited:
                    continue
                if data and self._has_valid_onchain_data(data):
                    token_data['onchain_data'][source_name] = data
                    self._mark_source_success(token_address, source_key, time.time())
                    print(f"    ✅ {source_name} data obtained")
                    # Do not break — aggregate across all sources
                else:
                    if last_error is not None:
                        print(f"    ❌ {source_name} failed after retries: {last_error}")
                    else:
                        print(f"    ⚠️  {source_name} returned no valid data")
            except Exception as e:
                print(f"    ❌ {source_name} failed: {e}")
                msg = str(e).lower()
                if '429' in msg or 'rate limit' in msg:
                    self._set_source_cooldown(source_key)
            
            time.sleep(0.5)  # Shorter delay for onchain data
        
        # ===== LIQUIDITY DATA WITH RATE LIMIT BYPASS =====
        if not self._should_skip_metric(token_address, 'liquidity'):
            print(f"  💧 Fetching liquidity data...")
        
        liquidity_data_sources = [
            ('defillama', lambda: self.fetch_defillama_liquidity_data(clean_address)),
            ('uniswap', lambda: self.fetch_uniswap_liquidity_data(clean_address)),
            ('sushiswap', lambda: self.fetch_sushiswap_liquidity_data(clean_address)),
            ('coingecko', lambda: self.fetch_coingecko_liquidity_data(symbol) if symbol else None),
            ('coinmarketcap', lambda: self.fetch_coinmarketcap_liquidity_data(symbol) if symbol else None),
            ('alchemy', lambda: self.fetch_alchemy_comprehensive_data(clean_address)),
            ('1inch', lambda: self.fetch_1inch_comprehensive_data(clean_address)),
            ('bitquery', lambda: self.fetch_bitquery_liquidity_data(clean_address)),
            ('thegraph', lambda: self.fetch_thegraph_liquidity_data(clean_address, symbol) if symbol else None)
        ]
        
        # Try all liquidity data sources (aggregate)
        liquidity_found = False
        for source_name, fetch_func in liquidity_data_sources:
            try:
                source_key = f"liquidity:{source_name}"
                if self._is_source_rate_limited(source_key):
                    continue
                if self._should_skip_source(token_address, source_key):
                    continue
                print(f"    🔄 Trying {source_name}...")
                data, was_rate_limited, last_error = self._fetch_source_with_retries(
                    source_key, fetch_func, max_attempts=3
                )
                if was_rate_limited:
                    continue
                if data and self._has_valid_liquidity_data(data):
                    token_data['liquidity_data'][source_name] = data
                    self._mark_source_success(token_address, source_key, time.time())
                    print(f"    ✅ {source_name} data obtained")
                    liquidity_found = True
                    # Do not break — aggregate across sources
                else:
                    if last_error is not None:
                        print(f"    ❌ {source_name} failed after retries: {last_error}")
                    else:
                        print(f"    ⚠️  {source_name} returned no valid data")
            except Exception as e:
                print(f"    ❌ {source_name} failed: {e}")
                msg = str(e).lower()
                if '429' in msg or 'rate limit' in msg:
                    self._set_source_cooldown(source_key)
            
            time.sleep(0.5)
        
        # If no real liquidity data found, try fallback data
        if not liquidity_found:
            fallback_data = self.get_fallback_liquidity_data(clean_address)
            if fallback_data:
                token_data['liquidity_data']['fallback'] = fallback_data
                print(f"    📦 Using fallback liquidity data")
            else:
                print(f"    💧 No liquidity data available - will show 0")
        
        # ===== SOCIAL DATA =====
        if symbol:
            print(f"  📱 Fetching social data for {symbol}...")
            
            social_data_sources = [
                ('twitter', lambda: self.fetch_twitter_social_data(symbol, symbol)),
                ('telegram', lambda: self.fetch_telegram_social_data(symbol, symbol)),
                ('discord', lambda: self.fetch_discord_social_data(symbol, symbol)),
                ('reddit', lambda: self.fetch_reddit_social_data(symbol, symbol))
            ]
            
            for source_name, fetch_func in social_data_sources:
                try:
                    source_key = f"social:{source_name}"
                    if self._is_source_rate_limited(source_key):
                        continue
                    if self._should_skip_source(token_address, source_key):
                        continue
                    data, was_rate_limited, last_error = self._fetch_source_with_retries(
                        source_key, fetch_func, max_attempts=3
                    )
                    if was_rate_limited:
                        continue
                    if data:
                        token_data['social_data'][source_name] = data
                        self._mark_source_success(token_address, source_key, time.time())
                    elif last_error is not None:
                        print(f"    ❌ {source_name} failed after retries: {last_error}")
                except Exception as e:
                    print(f"    ❌ {source_name} failed: {e}")
                    msg = str(e).lower()
                    if '429' in msg or 'rate limit' in msg:
                        self._set_source_cooldown(source_key)
        
        # ===== SENTIMENT DATA =====
        if symbol:
            print(f"  🧠 Fetching sentiment data for {symbol}...")
            
            sentiment_data_sources = [
                ('santiment', lambda: self.fetch_santiment_data(clean_address, chain)),
                ('arkham', lambda: self.fetch_arkham_intelligence_data(clean_address, symbol))
            ]
            
            for source_name, fetch_func in sentiment_data_sources:
                try:
                    source_key = f"sentiment:{source_name}"
                    if self._is_source_rate_limited(source_key):
                        continue
                    if self._should_skip_source(token_address, source_key):
                        continue
                    data, was_rate_limited, last_error = self._fetch_source_with_retries(
                        source_key, fetch_func, max_attempts=3
                    )
                    if was_rate_limited:
                        continue
                    if data:
                        token_data['sentiment_data'][source_name] = data
                        self._mark_source_success(token_address, source_key, time.time())
                    elif last_error is not None:
                        print(f"    ❌ {source_name} failed after retries: {last_error}")
                except Exception as e:
                    print(f"    ❌ {source_name} failed: {e}")
                    msg = str(e).lower()
                    if '429' in msg or 'rate limit' in msg:
                        self._set_source_cooldown(source_key)

        # ===== INTEGRATED INTELLIGENCE + RED FLAGS =====
        if self.assessor:
            print(f"  🛡️ Fetching integrated intelligence/compliance data...")
            enhanced_data = {}
            security_data = {}
            api_signal_flags = []
            try:
                with self._assessor_lock:
                    self.assessor.current_symbol = symbol or ''
                    self.assessor.current_token_name = token_name or symbol or ''
                    self.assessor.current_chain = chain
                    self.assessor.current_token_address = clean_address

                    enhanced_data = self.assessor.fetch_enhanced_data(clean_address, chain) or {}
                    security_data = self.assessor.fetch_security_reports(clean_address, chain) or {}
                    api_signal_flags = self.assessor._derive_api_signal_red_flags(enhanced_data) or []

                token_data['enhanced_data'] = enhanced_data if isinstance(enhanced_data, dict) else {}
                token_data['security_data'] = security_data if isinstance(security_data, dict) else {}
                for src_name, src_payload in token_data['enhanced_data'].items():
                    if src_payload:
                        self._mark_source_success(token_address, f"enhanced:{src_name}", time.time())
                if token_data['security_data']:
                    self._mark_source_success(token_address, "enhanced:security_reports", time.time())

                # Merge additional social sources fetched by the assessor.
                enhanced_social = (token_data['enhanced_data'].get('social_data') or {})
                if isinstance(enhanced_social, dict):
                    for source_name, payload in enhanced_social.items():
                        if payload and source_name not in token_data['social_data']:
                            token_data['social_data'][source_name] = payload
                            self._mark_source_success(token_address, f"social:{source_name}", time.time())

                token_data['red_flags'] = list(dict.fromkeys(api_signal_flags or []))
            except Exception as e:
                print(f"    ❌ integrated intelligence fetch failed: {e}")
        
        # ===== AGGREGATIONS =====
        try:
            token_data.setdefault('aggregates', {})

            # Market aggregates: average non-zero across sources
            if token_data['market_data']:
                mc_vals = []
                vol_vals = []
                price_vals = []
                change_vals = []
                for src, md in token_data['market_data'].items():
                    mc = md.get('market_cap')
                    vol = md.get('volume_24h')
                    prc = md.get('price')
                    change = md.get('change_24h')
                    if isinstance(mc, (int, float)) and mc > 0: mc_vals.append(mc)
                    if isinstance(vol, (int, float)) and vol > 0: vol_vals.append(vol)
                    if isinstance(prc, (int, float)) and prc > 0: price_vals.append(prc)
                    if isinstance(change, (int, float)): change_vals.append(change)
                def _avg(arr):
                    return (sum(arr) / len(arr)) if arr else 0
                agg_market = {
                    'market_cap': _avg(mc_vals),
                    'volume_24h': _avg(vol_vals),
                    'price': _avg(price_vals),
                    'change_24h': _avg(change_vals)
                }
                token_data['aggregates']['market'] = agg_market
                if any(v > 0 for v in [agg_market['market_cap'], agg_market['volume_24h'], agg_market['price']]):
                    print(f"  📊 Aggregated Market → MC=${agg_market['market_cap']:,.0f}, Vol=${agg_market['volume_24h']:,.0f}, Price=${agg_market['price']:.6f}, Change={agg_market['change_24h']:.2f}%")

            # Onchain aggregates: average non-zero across sources
            if token_data['onchain_data']:
                holders_vals, supply_vals, tx_vals = [], [], []
                for src, od in token_data['onchain_data'].items():
                    h = od.get('holders') or od.get('total_holders')
                    s = od.get('total_supply')
                    tx = od.get('tx_count')
                    if isinstance(h, (int, float)) and h > 0: holders_vals.append(h)
                    if isinstance(s, (int, float)) and s > 0: supply_vals.append(s)
                    if isinstance(tx, (int, float)) and tx > 0: tx_vals.append(tx)
                def _avg(arr):
                    return (sum(arr) / len(arr)) if arr else 0
                agg_onchain = {
                    'holders': _avg(holders_vals),
                    'total_supply': _avg(supply_vals),
                    'tx_count': _avg(tx_vals)
                }
                token_data['aggregates']['onchain'] = agg_onchain
                if any(v > 0 for v in agg_onchain.values()):
                    print(f"  ⛓️  Aggregated Onchain → Holders={agg_onchain['holders']:.0f}, Supply={agg_onchain['total_supply']:.0f}, TXs={agg_onchain['tx_count']:.0f}")

            # Liquidity aggregates: average non-zero across sources
            if token_data['liquidity_data']:
                liq_vals, lvol_vals, trade_vals = [], [], []
                for src, ld in token_data['liquidity_data'].items():
                    lq = ld.get('liquidity_score') or ld.get('total_liquidity') or ld.get('liquidity')
                    lv = ld.get('volume_24h') or ld.get('volumeUSD') or ld.get('volume')
                    trade_count = ld.get('trade_count') or ld.get('tx_count')
                    if isinstance(lq, (int, float)) and lq > 0: liq_vals.append(lq)
                    if isinstance(lv, (int, float)) and lv > 0: lvol_vals.append(lv)
                    if isinstance(trade_count, (int, float)) and trade_count > 0: trade_vals.append(trade_count)
                def _avg(arr):
                    return (sum(arr) / len(arr)) if arr else 0
                agg_liq = {
                    'liquidity': _avg(liq_vals),
                    'volume_24h': _avg(lvol_vals),
                    'trade_count': _avg(trade_vals)
                }
                token_data['aggregates']['liquidity'] = agg_liq
                if any(v > 0 for v in agg_liq.values()):
                    print(f"  💧 Aggregated Liquidity → Liquidity=${agg_liq['liquidity']:,.0f}, Vol=${agg_liq['volume_24h']:,.0f}, Trades={agg_liq['trade_count']:.0f}")
        except Exception as e:
            print(f"⚠️ Aggregation error: {e}")

        # Re-evaluate red flags with aggregate-backed market snapshot for stronger signal quality.
        if self.assessor:
            try:
                market_snapshot = self._build_market_snapshot_for_flags(token_data)
                with self._assessor_lock:
                    refreshed_flags = self.assessor.detect_red_flags(
                        clean_address,
                        chain,
                        symbol=symbol,
                        token_name=token_name,
                        market_data=market_snapshot
                    ) or []
                token_data['red_flags'] = list(dict.fromkeys((token_data.get('red_flags') or []) + refreshed_flags))
            except Exception as e:
                print(f"    ⚠️ red flag refresh failed: {e}")

        # Compute value deltas against previous cache snapshot.
        try:
            token_data['value_changes'] = self._compute_value_changes(existing_entry, token_data)
        except Exception as e:
            print(f"⚠️ Value change computation failed: {e}")
            token_data['value_changes'] = {}

        # Mark last-success per metric when we have valid data
        try:
            now_ts = time.time()
            if token_data.get('market_data') and any(self._has_valid_market_data(v) for v in token_data['market_data'].values()):
                self._mark_metric_success(token_address, 'market', now_ts)
            if token_data.get('onchain_data') and any(self._has_valid_onchain_data(v) for v in token_data['onchain_data'].values()):
                self._mark_metric_success(token_address, 'onchain', now_ts)
            if token_data.get('liquidity_data') and any(self._has_valid_liquidity_data(v) for v in token_data['liquidity_data'].values()):
                self._mark_metric_success(token_address, 'liquidity', now_ts)
            if token_data.get('social_data'):
                self._mark_metric_success(token_address, 'social', now_ts)
            if token_data.get('sentiment_data'):
                self._mark_metric_success(token_address, 'sentiment', now_ts)
        except Exception:
            pass

        return token_data

    def _should_skip_metric(self, token_address: str, metric: str) -> bool:
        """Return True if metric fetch should be skipped based on last success within policy window."""
        if not getattr(self, 'respect_skip', True):
            return False
        window_h = self._effective_skip_window_hours()
        last_ts = self._get_last_success_ts(token_address, metric)
        if last_ts <= 0:
            # Also check fallback history timestamps for aggregates
            fb_ts = self._get_fallback_metric_ts(token_address, metric)
            last_ts = max(last_ts, fb_ts)
        if last_ts <= 0:
            return False
        age_h = (time.time() - last_ts) / 3600
        if age_h < window_h:
            print(
                f"    ⏭️  Skipping {metric} fetch for {token_address} "
                f"(age {age_h:.1f}h < {window_h:.1f}h)"
            )
            return True
        return False

    def _source_key(self, source_name: str) -> str:
        """Normalize source key for per-endpoint skip tracking."""
        return str(source_name or '').strip().lower()

    def _source_base_key(self, source_name: str) -> str:
        source_key = self._source_key(source_name)
        if ':' in source_key:
            return source_key.split(':', 1)[1]
        return source_key

    def _default_source_cooldown(self, source_name: str) -> float:
        base = self._source_base_key(source_name)
        return float(self.source_rate_policies.get(base, 60.0))

    def _is_source_rate_limited(self, source_name: str) -> bool:
        base = self._source_base_key(source_name)
        until = float(self.source_cooldowns.get(base, 0) or 0)
        remaining = until - time.time()
        if remaining > 0:
            print(f"    ⏭️  {base} cooldown active ({remaining:.1f}s), skipping source call")
            return True
        if until:
            self.source_cooldowns.pop(base, None)
        return False

    def _set_source_cooldown(self, source_name: str, seconds: Optional[float] = None):
        base = self._source_base_key(source_name)
        if not base:
            return
        duration = self._default_source_cooldown(base) if seconds is None else max(1.0, float(seconds))
        self.source_cooldowns[base] = time.time() + duration

    def _is_rate_limited_payload(self, payload) -> bool:
        if not isinstance(payload, dict):
            return False
        err = str(payload.get('error', '') or payload.get('message', '')).lower()
        return ('rate_limit' in err) or ('rate limit' in err) or ('429' in err)

    def _fetch_source_with_retries(self, source_key: str, fetch_func, max_attempts: int = 3):
        """
        Execute one source fetch with bounded retries.
        Returns tuple: (payload, was_rate_limited, last_error)
        """
        source_key = self._source_key(source_key)
        last_error = None
        attempts = max(1, min(int(max_attempts or 3), 3))

        for attempt in range(attempts):
            try:
                payload = fetch_func()
                if self._is_rate_limited_payload(payload):
                    cooldown_seconds = None
                    if isinstance(payload, dict):
                        cooldown_raw = payload.get('cooldown_seconds')
                        if isinstance(cooldown_raw, (int, float)):
                            cooldown_seconds = float(cooldown_raw)
                        elif isinstance(cooldown_raw, str):
                            try:
                                cooldown_seconds = float(cooldown_raw.strip())
                            except Exception:
                                cooldown_seconds = None
                    self._set_source_cooldown(source_key, cooldown_seconds)
                    return None, True, last_error
                if payload:
                    return payload, False, None
            except Exception as e:
                last_error = e

            if attempt < attempts - 1:
                sleep_seconds = min(2.0, 0.4 * (attempt + 1))
                print(
                    f"    🔁 Retry {attempt + 2}/{attempts} for {source_key} "
                    f"in {sleep_seconds:.1f}s..."
                )
                time.sleep(sleep_seconds)

        return None, False, last_error

    def _should_skip_source(self, token_address: str, source_name: str) -> bool:
        """
        Skip one source if this token already has a successful value from that source
        within cache retention window.
        """
        if not getattr(self, 'respect_skip', True):
            return False
        source_key = self._source_key(source_name)
        if not source_key:
            return False
        window_h = self._effective_skip_window_hours()
        last_ts = self._get_last_source_success_ts(token_address, source_key)
        if last_ts <= 0:
            return False
        age_h = (time.time() - last_ts) / 3600
        if age_h < window_h:
            print(
                f"    ⏭️  Skipping {source_key} for {token_address} "
                f"(age {age_h:.1f}h < {window_h:.1f}h)"
            )
            return True
        return False

    def _mark_source_success(self, token_address: str, source_name: str, ts: float):
        source_key = self._source_key(source_name)
        if not source_key:
            return
        if 'endpoint_metrics' not in self.cache_data:
            self.cache_data['endpoint_metrics'] = {}
        if token_address not in self.cache_data['endpoint_metrics']:
            self.cache_data['endpoint_metrics'][token_address] = {}
        self.cache_data['endpoint_metrics'][token_address][source_key] = ts
        self.endpoint_metrics = self.cache_data['endpoint_metrics']

    def _get_last_source_success_ts(self, token_address: str, source_name: str) -> float:
        source_key = self._source_key(source_name)
        try:
            return float(self.endpoint_metrics.get(token_address, {}).get(source_key, 0))
        except Exception:
            return 0.0

    def _mark_metric_success(self, token_address: str, metric: str, ts: float):
        if 'token_metrics' not in self.cache_data:
            self.cache_data['token_metrics'] = {}
        if token_address not in self.cache_data['token_metrics']:
            self.cache_data['token_metrics'][token_address] = {}
        self.cache_data['token_metrics'][token_address][metric] = ts
        self.token_metrics = self.cache_data['token_metrics']

    def _get_last_success_ts(self, token_address: str, metric: str) -> float:
        try:
            return float(self.token_metrics.get(token_address, {}).get(metric, 0))
        except Exception:
            return 0.0

    def _get_fallback_metric_ts(self, token_address: str, metric: str) -> float:
        """Fallback to the last history timestamp for a related aggregate metric."""
        try:
            if not os.path.exists(FALLBACK_FILE):
                return 0.0
            with open(FALLBACK_FILE, 'r') as f:
                fb = json.load(f)
            entry = fb.get('token_mappings', {}).get(token_address, {})
            hist = entry.get('history', {}) if isinstance(entry, dict) else {}
            key_map = {
                'market': ['market_cap', 'volume_24h'],
                'onchain': ['holders'],
                'liquidity': ['liquidity']
            }
            keys = key_map.get(metric, [])
            best_ts = 0.0
            for k in keys:
                arr = hist.get(k, [])
                if isinstance(arr, list) and arr:
                    for it in arr:
                        ts = it.get('ts', 0)
                        try:
                            ts = float(ts)
                        except (ValueError, TypeError):
                            ts = 0
                        if ts > best_ts:
                            best_ts = ts
            return best_ts
        except Exception:
            return 0.0
    
    def _has_valid_market_data(self, data):
        """Check if market data contains valid non-zero values"""
        if not data:
            return False
        
        # Check for any non-zero market cap, volume, or price
        market_cap = data.get('market_cap', 0)
        volume = data.get('volume_24h', 0)
        price = data.get('price', 0)
        tvl = data.get('tvl', 0)
        
        return any([
            market_cap and market_cap > 0,
            volume and volume > 0,
            price and price > 0,
            tvl and tvl > 0
        ])
    
    def _has_valid_onchain_data(self, data):
        """Check if onchain data contains valid non-zero values"""
        if not data:
            return False
        
        # Check for any non-zero holders, supply, or transaction data
        holders = data.get('holders', 0)
        total_supply = data.get('total_supply', 0)
        volume = data.get('volume', 0)
        tx_count = data.get('tx_count', 0)
        
        return any([
            holders and holders > 0,
            total_supply and total_supply > 0,
            volume and volume > 0,
            tx_count and tx_count > 0
        ])
    
    def _has_valid_liquidity_data(self, data):
        """Check if liquidity data contains valid data (including metadata)"""
        if not data:
            return False
        
        # Check for any non-zero liquidity metrics or valid metadata
        liquidity_score = data.get('liquidity_score', 0)
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        decimals = data.get('decimals', 0)
        
        # Accept metadata-only data (name, symbol, decimals) even without liquidity_score
        return any([
            liquidity_score and liquidity_score > 0,
            name and name.strip(),
            symbol and symbol.strip(),
            decimals and decimals > 0
        ])

    def _entry_age_hours(self, token_data):
        """Return best-known entry age in hours from timestamp fields."""
        if not isinstance(token_data, dict):
            return float('inf')
        ts_candidates = []
        for key in ('timestamp', 'last_real_time_update', 'last_fallback_update'):
            raw_val = token_data.get(key)
            if isinstance(raw_val, (int, float)) and raw_val > 0:
                ts_candidates.append(float(raw_val))
        if not ts_candidates:
            return float('inf')
        latest_ts = max(ts_candidates)
        return max(0.0, (time.time() - latest_ts) / 3600.0)
    
    # ===== SMART REFRESH HELPER METHODS =====
    
    def get_existing_token_data(self, token_address):
        """Get existing token data from cache"""
        return self.cache_data.get('tokens', {}).get(token_address, {})
    
    def _has_comprehensive_data(self, token_data):
        """Check if token has comprehensive data (all major data types)"""
        if not token_data:
            return False

        # Respect retention horizon: stale data should be refreshed.
        if self._entry_age_hours(token_data) > self._effective_skip_window_hours():
            return False
        
        # Check if we have at least one market data source
        market_data = token_data.get('market_data', {})
        has_market_data = len(market_data) > 0 and any(
            self._has_valid_market_data(data) for data in market_data.values()
        )
        
        # Check if we have at least one onchain data source
        onchain_data = token_data.get('onchain_data', {})
        has_onchain_data = len(onchain_data) > 0 and any(
            self._has_valid_onchain_data(data) for data in onchain_data.values()
        )
        
        # Check if we have at least one liquidity data source (including metadata)
        liquidity_data = token_data.get('liquidity_data', {})
        has_liquidity_data = len(liquidity_data) > 0 and any(
            self._has_valid_liquidity_data(data) for data in liquidity_data.values()
        )
        
        # Consider comprehensive if we have market data, onchain data, AND any liquidity data
        return has_market_data and has_onchain_data and has_liquidity_data
    
    def _get_missing_data_types(self, token_data):
        """Get list of missing data types for a token"""
        missing_types = []
        
        if not token_data:
            return ['market_data', 'onchain_data', 'liquidity_data', 'social_data', 'sentiment_data']

        # If data is stale by retention policy, refresh all major categories.
        if self._entry_age_hours(token_data) > self._effective_skip_window_hours():
            return ['market_data', 'onchain_data', 'liquidity_data', 'social_data', 'sentiment_data']
        
        # Check market data
        market_data = token_data.get('market_data', {})
        if not market_data or not any(self._has_valid_market_data(data) for data in market_data.values()):
            missing_types.append('market_data')
        
        # Check onchain data
        onchain_data = token_data.get('onchain_data', {})
        if not onchain_data or not any(self._has_valid_onchain_data(data) for data in onchain_data.values()):
            missing_types.append('onchain_data')
        
        # Check liquidity data
        liquidity_data = token_data.get('liquidity_data', {})
        if not liquidity_data or not any(self._has_valid_liquidity_data(data) for data in liquidity_data.values()):
            missing_types.append('liquidity_data')
        
        # Check social data
        social_data = token_data.get('social_data', {})
        if not social_data:
            missing_types.append('social_data')
        
        # Check sentiment data
        sentiment_data = token_data.get('sentiment_data', {})
        if not sentiment_data:
            missing_types.append('sentiment_data')
        
        return missing_types
    
    # ===== COMPREHENSIVE DATA FETCHING METHODS =====
    
    def fetch_defillama_market_data(self, symbol):
        """Fetch market data from DeFiLlama"""
        try:
            # DeFiLlama uses different endpoint structure
            url = f"https://api.llama.fi/protocol/{symbol.lower()}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response structures
                if isinstance(data, dict):
                    # Single protocol data
                    tvl = data.get('tvl', 0)
                    if isinstance(tvl, list) and len(tvl) > 0:
                        # TVL is a list, get the latest value
                        tvl = tvl[-1].get('totalLiquidityUSD', 0) if isinstance(tvl[-1], dict) else 0
                    elif isinstance(tvl, (int, float)):
                        tvl = float(tvl)
                    else:
                        tvl = 0
                    
                    return {
                        'tvl': tvl,
                        'source': 'real-time'
                    }
                else:
                    print(f"    ⚠️  DeFiLlama returned unexpected data format")
                    return None
            else:
                print(f"    ⚠️  DeFiLlama API returned status {response.status_code}")
                return None
        except Exception as e:
            print(f"  ❌ DeFiLlama error: {e}")
        return None
    
    def fetch_bitquery_data(self, token_address):
        """Fetch onchain data from BitQuery"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('BITQUERY_API_KEY')
            
            if not api_key:
                print(f"    ⚠️  BitQuery API key not found")
                return None
            
            # Check if this is an L2 token
            if self._is_l2_token(token_address):
                print(f"    ⚠️  Skipping BitQuery for L2 token {token_address}")
                return None
            
            # GraphQL query for token holders
            query = """
            {
              ethereum {
                address(address: {is: "%s"}) {
                  smartContract {
                    contractType
                    currency {
                      name
                      symbol
                      decimals
                      totalSupply
                      holders
                    }
                  }
                }
              }
            }
            """ % token_address
            
            url = "https://graphql.bitquery.io"
            headers = {'X-API-KEY': api_key}
            
            response = requests.post(url, json={'query': query}, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']['ethereum']['address']:
                    currency = data['data']['ethereum']['address']['smartContract']['currency']
                    holders = currency.get('holders', 0)
                    total_supply = currency.get('totalSupply', 0)
                    
                    if holders > 0 or total_supply > 0:
                        return {
                            'holders': int(holders),
                            'total_supply': float(total_supply),
                            'source': 'real-time'
                        }
                    else:
                        print(f"    ⚠️  BitQuery returned no valid data for {token_address}")
                else:
                    print(f"    ⚠️  BitQuery returned no data for {token_address}")
            else:
                print(f"    ⚠️  BitQuery API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ BitQuery error: {e}")
        return None

    def fetch_bitquery_liquidity_data(self, token_address):
        """Fetch liquidity data from Bitquery API"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('BITQUERY_API_KEY')
            
            if not api_key:
                print(f"    ⚠️  Bitquery API key not found")
                return None
            
            # Bitquery GraphQL query for liquidity data
            query = """
            query GetLiquidityData($tokenAddress: String!) {
                ethereum(network: ethereum) {
                    dexTrades(
                        options: {limit: 100}
                        date: {since: "2024-01-01"}
                        baseCurrency: {is: $tokenAddress}
                    ) {
                        count
                        totalAmount: amount
                        totalValue: value
                    }
                }
            }
            """
            
            url = "https://graphql.bitquery.io"
            headers = {
                'Content-Type': 'application/json',
                'X-API-KEY': api_key
            }
            
            payload = {
                'query': query,
                'variables': {'tokenAddress': token_address}
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data'] and data['data'].get('ethereum'):
                    ethereum_data = data['data']['ethereum']
                    if ethereum_data and len(ethereum_data) > 0:
                        trade_data = ethereum_data[0]
                        return {
                            'source': 'bitquery',
                            'trade_count': trade_data.get('count', 0),
                            'total_amount': trade_data.get('totalAmount', 0),
                            'total_value': trade_data.get('totalValue', 0)
                        }
            else:
                print(f"    ❌ Bitquery liquidity API error: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ Bitquery liquidity fetch failed: {e}")
        
        return None

    def fetch_thegraph_liquidity_data(self, token_address, symbol):
        """Fetch liquidity data from TheGraph API"""
        try:
            # Query Uniswap V2 liquidity data
            query = """
            {
              token(id: "%s") {
                totalSupply
                volume
                txCount
                liquidity
                priceUSD
              }
            }
            """ % token_address
            
            url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
            response = requests.post(url, json={'query': query}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']['token']:
                    token_data = data['data']['token']
                    liquidity = float(token_data.get('liquidity', 0))
                    volume = float(token_data.get('volume', 0))
                    
                    if liquidity > 0 or volume > 0:
                        return {
                            'source': 'thegraph',
                            'liquidity': liquidity,
                            'volume': volume,
                            'tx_count': token_data.get('txCount', 0),
                            'price_usd': float(token_data.get('priceUSD', 0))
                        }
            else:
                print(f"    ❌ TheGraph liquidity API error: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ TheGraph liquidity fetch failed: {e}")
        
        return None
    
    def fetch_thegraph_data(self, token_address, symbol):
        """Fetch onchain data from TheGraph"""
        try:
            # Query Uniswap V2 data
            query = """
            {
              token(id: "%s") {
                totalSupply
                volume
                txCount
              }
            }
            """ % token_address.lower()
            
            url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
            response = requests.post(url, json={'query': query}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']['token']:
                    token = data['data']['token']
                    return {
                        'total_supply': float(token.get('totalSupply', 0)),
                        'volume': float(token.get('volume', 0)),
                        'tx_count': int(token.get('txCount', 0)),
                        'source': 'real-time'
                    }
        except Exception as e:
            print(f"  ❌ TheGraph error: {e}")
        return None
    
    def fetch_optimism_data(self, token_address):
        """Fetch data for Optimism L2 tokens"""
        try:
            if not token_address:
                return None

            def _parse_holders(value):
                try:
                    if isinstance(value, str):
                        value = value.replace(',', '').strip()
                    parsed = int(float(value))
                    return parsed if parsed > 0 else 0
                except Exception:
                    return 0

            holders = 0
            blockscout_urls = [
                f"https://optimism.blockscout.com/api/v2/tokens/{token_address}",
                f"https://blockscout.com/optimism/mainnet/api/v2/tokens/{token_address}",
            ]
            for url in blockscout_urls:
                try:
                    response = requests.get(url, timeout=15, headers={"User-Agent": "DeFiRiskAssessor/3.0"})
                    if response.status_code != 200:
                        continue
                    payload = response.json()
                    holders = _parse_holders(
                        payload.get('holders_count')
                        or payload.get('holdersCount')
                        or payload.get('holder_count')
                    )
                    if holders > 0:
                        break
                except Exception:
                    continue

            # Fallback to Etherscan V2 chain-aware token holder endpoint
            if holders <= 0:
                api_key = os.getenv('ETHERSCAN_API_KEY')
                if api_key:
                    try:
                        url = "https://api.etherscan.io/v2/api"
                        params = {
                            'chainid': 10,
                            'module': 'token',
                            'action': 'tokenholderlist',
                            'contractaddress': token_address,
                            'page': 1,
                            'offset': 1,
                            'apikey': api_key
                        }
                        response = requests.get(url, params=params, timeout=15)
                        if response.status_code == 200:
                            payload = response.json()
                            if payload.get('status') == '1':
                                result = payload.get('result')
                                if isinstance(result, list) and result:
                                    holders = _parse_holders((result[0] or {}).get('TokenHolderCount'))
                                elif isinstance(result, dict):
                                    holders = _parse_holders(result.get('TokenHolderCount'))
                    except Exception:
                        pass

            if holders > 0:
                return {
                    'name': 'Optimism',
                    'symbol': 'OP',
                    'decimals': 18,
                    'holders': holders,
                    'source': 'real-time'
                }
        except Exception as e:
            print(f"  ❌ Optimism data error: {e}")
        return None
    
    def fetch_1inch_comprehensive_data(self, token_address):
        """Fetch liquidity data from 1inch"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('INCH_API_KEY')
            
            if not api_key:
                print(f"    ⚠️  1inch API key not found")
                return None
            
            # Check if this is an L2 token
            if self._is_l2_token(token_address):
                print(f"    ⚠️  Skipping 1inch for L2 token {token_address}")
                return None
            
            from token_list_registry import oneinch_dst_stable_for_chain

            usdc_address = oneinch_dst_stable_for_chain('eth')
            if not usdc_address:
                print(f"    ⚠️  No USDC/USDT/DAI row for eth in tokens.csv; skipping 1inch")
                return None

            url = f"https://api.1inch.com/swap/v6.0/1/quote"
            params = {
                'src': token_address,
                'dst': usdc_address,
                'amount': '1000000000000000000'  # 1 token
            }
            
            headers = {'Authorization': f'Bearer {api_key}'}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                to_token_amount = data.get('toTokenAmount', 0)
                
                if to_token_amount and float(to_token_amount) > 0:
                    return {
                        'liquidity_score': float(to_token_amount),
                        'source': 'real-time'
                    }
                else:
                    print(f"    ⚠️  1inch returned no liquidity data for {token_address}")
            else:
                print(f"    ⚠️  1inch API returned status {response.status_code}")
                if response.status_code == 400:
                    print(f"    ⚠️  This might be due to unsupported token or insufficient liquidity")
        except Exception as e:
            print(f"  ❌ 1inch error: {e}")
        return None
    
    def fetch_defillama_liquidity_data(self, token_address):
        """Fetch liquidity data from DeFiLlama API"""
        try:
            # DeFiLlama API endpoint for token-specific data
            url = f"https://api.llama.fi/v2/chains/ethereum/tokens/{token_address}"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if 'tokens' in data and token_address.lower() in data['tokens']:
                    token_data = data['tokens'][token_address.lower()]
                    tvl = float(token_data.get('tvl', 0))
                    
                    if tvl > 0:
                        return {
                            'liquidity_score': tvl,
                            'source': 'real-time'
                        }
                    else:
                        print(f"    ⚠️  DeFiLlama returned no liquidity for {token_address}")
                else:
                    print(f"    ⚠️  DeFiLlama returned no data for {token_address}")
            elif response.status_code == 404:
                print(f"    ⚠️  DeFiLlama: Token {token_address} not found (404)")
            else:
                print(f"    ⚠️  DeFiLlama API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ DeFiLlama error: {e}")
        return None
    
    def fetch_uniswap_liquidity_data(self, token_address):
        """Fetch liquidity data from Uniswap V3 API"""
        try:
            # Uniswap V3 Graph API endpoint (free, no API key required)
            url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
            
            # Query for token liquidity data
            query = """
            {
              token(id: "%s") {
                id
                totalValueLockedUSD
                volumeUSD
                poolCount
                pools(first: 5, orderBy: totalValueLockedUSD, orderDirection: desc) {
                  id
                  totalValueLockedUSD
                  volumeUSD
                  feeTier
                }
              }
            }
            """ % token_address.lower()
            
            response = requests.post(url, json={'query': query}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']['token']:
                    token_data = data['data']['token']
                    tvl_usd = float(token_data.get('totalValueLockedUSD', 0))
                    volume_usd = float(token_data.get('volumeUSD', 0))
                    
                    if tvl_usd > 0:
                        return {
                            'liquidity_score': tvl_usd,
                            'volume_24h': volume_usd,
                            'source': 'real-time'
                        }
                    else:
                        print(f"    ⚠️  Uniswap returned no liquidity for {token_address}")
                else:
                    print(f"    ⚠️  Uniswap: Token {token_address} not found in V3 pools")
            else:
                print(f"    ⚠️  Uniswap API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ Uniswap error: {e}")
        return None
    
    def fetch_sushiswap_liquidity_data(self, token_address):
        """Fetch liquidity data from SushiSwap API"""
        try:
            # SushiSwap Graph API endpoint (free, no API key required)
            url = "https://api.thegraph.com/subgraphs/name/sushiswap/exchange"
            
            # Query for token liquidity data
            query = """
            {
              token(id: "%s") {
                id
                totalSupply
                volumeUSD
                liquidity
                liquidityUSD
                pairBase {
                  id
                  liquidityUSD
                  volumeUSD
                }
              }
            }
            """ % token_address.lower()
            
            response = requests.post(url, json={'query': query}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']['token']:
                    token_data = data['data']['token']
                    liquidity_usd = float(token_data.get('liquidityUSD', 0))
                    volume_usd = float(token_data.get('volumeUSD', 0))
                    
                    # Also check pair data for additional liquidity
                    pair_base = token_data.get('pairBase', {})
                    if pair_base:
                        pair_liquidity = float(pair_base.get('liquidityUSD', 0))
                        if pair_liquidity > liquidity_usd:
                            liquidity_usd = pair_liquidity
                    
                    if liquidity_usd > 0:
                        return {
                            'liquidity_score': liquidity_usd,
                            'volume_24h': volume_usd,
                            'source': 'real-time'
                        }
                    else:
                        print(f"    ⚠️  SushiSwap returned no liquidity for {token_address}")
                else:
                    print(f"    ⚠️  SushiSwap: Token {token_address} not found in V2 pools")
            else:
                print(f"    ⚠️  SushiSwap API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ SushiSwap error: {e}")
        return None
    
    def _get_coin_id(self, symbol):
        """Get CoinGecko coin ID from symbol"""
        # Simple mapping for common tokens
        coin_mapping = {
            'UNI': 'uniswap',
            'DAI': 'dai',
            '1INCH': '1inch',
            'GRT': 'the-graph',
            'SUSHI': 'sushi',
            'MKR': 'maker',
            'QNT': 'quant-network',
            'POL': 'matic-network',
            'OP': 'optimism',
            'LINK': 'chainlink',
            'WBTC': 'wrapped-bitcoin',
            'USDT': 'tether',
            'USDC': 'usd-coin',
            'AAVE': 'aave',
            'COMP': 'compound-governance-token',
            'BAT': 'basic-attention-token',
            'TRON': 'tron',
            'SONIC': 'sonic'  # This might not exist in CoinGecko
        }
        return coin_mapping.get(symbol.upper())
    
    def fetch_coingecko_liquidity_data(self, symbol):
        """Fetch liquidity data from CoinGecko API"""
        try:
            # Get coin ID from symbol
            coin_id = self._get_coin_id(symbol)
            if not coin_id:
                return None
            
            # CoinGecko API endpoint for token data
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Extract liquidity data from CoinGecko response
                market_data = data.get('market_data', {})
                liquidity_score = market_data.get('total_liquidity', 0)
                
                if liquidity_score and liquidity_score > 0:
                    return {
                        'liquidity_score': liquidity_score,
                        'source': 'real-time'
                    }
                else:
                    print(f"    ⚠️  CoinGecko returned no liquidity for {symbol}")
            elif response.status_code == 429:
                print(f"    ⏰ CoinGecko rate limited for {symbol}")
                return {
                    'error': 'rate_limited',
                    'cooldown_seconds': self._default_source_cooldown('coingecko'),
                    'source': 'coingecko'
                }
            else:
                print(f"    ⚠️  CoinGecko API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ CoinGecko error: {e}")
        return None
    
    def fetch_coinmarketcap_liquidity_data(self, symbol):
        """Fetch liquidity data from CoinMarketCap API"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('COINMARKETCAP_API_KEY')
            
            if not api_key:
                print(f"    ⚠️  CoinMarketCap API key not found")
                return None
            
            # CoinMarketCap API endpoint for market data
            url = f"https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            params = {
                'symbol': symbol,
                'convert': 'USD'
            }
            headers = {
                'X-CMC-Pro-API-Key': api_key
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and symbol in data['data']:
                    token_data = data['data'][symbol]
                    quote = token_data.get('quote', {}).get('USD', {})
                    
                    # CoinMarketCap doesn't provide direct liquidity; do not estimate from market cap
                    print(f"    ⚠️  CoinMarketCap provides no direct liquidity for {symbol}")
                    return None
                else:
                    print(f"    ⚠️  CoinMarketCap returned no data for {symbol}")
            elif response.status_code == 429:
                print(f"    ⏰ CoinMarketCap rate limited for {symbol}")
                return {
                    'error': 'rate_limited',
                    'cooldown_seconds': self._default_source_cooldown('coinmarketcap'),
                    'source': 'coinmarketcap'
                }
            else:
                print(f"    ⚠️  CoinMarketCap API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ CoinMarketCap error: {e}")
        return None
    
    def update_fallback_data_with_real_data(self, token_address, real_data):
        """Update fallback data with real data from webhook cache"""
        try:
            if not real_data:
                return
            storage_key = str(token_address or '').strip()
            if storage_key.startswith('0x') and len(storage_key) == 42:
                storage_key = storage_key.lower()
            if not storage_key:
                return
            
            # Load existing fallback data (unified storage)
            if os.path.exists(FALLBACK_FILE):
                with open(FALLBACK_FILE, 'r') as f:
                    fallback_data = json.load(f)
            else:
                fallback_data = {'token_mappings': {}, 'metadata': {}}
            if not isinstance(fallback_data, dict):
                fallback_data = {'token_mappings': {}, 'metadata': {}}
            token_mappings = fallback_data.get('token_mappings', {})
            if not isinstance(token_mappings, dict):
                token_mappings = {}
            fallback_data['token_mappings'] = token_mappings
            
            candidate_metrics = self._extract_candidate_metrics(real_data)
            market_cap = self._to_float(candidate_metrics.get('market_cap')) or 0.0
            volume_24h = self._to_float(candidate_metrics.get('volume_24h')) or 0.0
            holders = int(self._to_float(candidate_metrics.get('holders')) or 0)
            liquidity = self._to_float(candidate_metrics.get('liquidity')) or 0.0
            
            # Update fallback data if we have real values
            if market_cap > 0 or volume_24h > 0 or holders > 0 or liquidity > 0:
                entry = token_mappings.get(storage_key, {})
                if not isinstance(entry, dict):
                    entry = {}
                now_ts = time.time()
                sync_window_h = max(1.0 / 60.0, float(getattr(self, 'fallback_sync_hours', 4) or 4))
                try:
                    last_update_ts = float(entry.get('last_updated', 0) or 0)
                except Exception:
                    last_update_ts = 0.0

                # Only sync each token to fallback on configured cadence, unless this write would fill
                # currently missing fallback metrics with new non-zero values.
                fill_missing_now = False
                if isinstance(entry, dict) and entry:
                    try:
                        fill_missing_now = (
                            (float(entry.get('market_cap', 0) or 0) <= 0 and market_cap > 0)
                            or (float(entry.get('volume_24h', 0) or 0) <= 0 and volume_24h > 0)
                            or (float(entry.get('holders', 0) or 0) <= 0 and holders > 0)
                            or (float(entry.get('liquidity', 0) or 0) <= 0 and liquidity > 0)
                        )
                    except Exception:
                        fill_missing_now = False
                if last_update_ts > 0 and not fill_missing_now:
                    age_hours = max(0.0, (now_ts - last_update_ts) / 3600.0)
                    if age_hours < sync_window_h:
                        print(
                            f"    ⏭️  Skipping fallback sync for {storage_key[:10]} "
                            f"(updated {age_hours:.1f}h ago; sync interval {sync_window_h:.1f}h)"
                        )
                        return

                # preserve existing identity fields
                name = entry.get('name') or real_data.get('name') or ''
                symbol = entry.get('symbol') or real_data.get('symbol') or ''
                chain_hint = entry.get('chain') or real_data.get('chain') or ''
                history = entry.get('history', {}) if isinstance(entry.get('history', {}), dict) else {}
                existing_market_data = entry.get('market_data', {}) if isinstance(entry.get('market_data'), dict) else {}
                existing_onchain_data = entry.get('onchain_data', {}) if isinstance(entry.get('onchain_data'), dict) else {}
                existing_liquidity_data = entry.get('liquidity_data', {}) if isinstance(entry.get('liquidity_data'), dict) else {}
                incoming_market_data = real_data.get('market_data', {}) if isinstance(real_data.get('market_data'), dict) else {}
                incoming_onchain_data = real_data.get('onchain_data', {}) if isinstance(real_data.get('onchain_data'), dict) else {}
                incoming_liquidity_data = real_data.get('liquidity_data', {}) if isinstance(real_data.get('liquidity_data'), dict) else {}

                existing_source_labels = []
                existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_market_data))
                existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_onchain_data))
                existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_liquidity_data))
                new_source_labels = []
                new_source_labels.extend(self._collect_source_labels_for_confidence(incoming_market_data))
                new_source_labels.extend(self._collect_source_labels_for_confidence(incoming_onchain_data))
                new_source_labels.extend(self._collect_source_labels_for_confidence(incoming_liquidity_data))
                metric_source_values = self._build_metric_source_values(real_data, chain_hint or real_data.get('chain') or '')
                resolved_values = self._apply_assessment_overwrite_policy(
                    entry,
                    candidate_metrics,
                    metric_source_values,
                    existing_source_labels,
                    new_source_labels,
                    chain_hint or real_data.get('chain') or ''
                )

                def _append_hist(key, value):
                    if not isinstance(history, dict):
                        return
                    arr = history.get(key, [])
                    if not isinstance(arr, list):
                        arr = []
                    if key == 'holders':
                        if isinstance(value, (int, float)) and value > 0 and not self._is_placeholder_holders_metric(value):
                            arr.append({'value': int(value), 'ts': now_ts})
                    elif isinstance(value, (int, float)) and value > 0:
                        arr.append({'value': value, 'ts': now_ts})
                    cutoff = now_ts - 48 * 3600
                    arr = [x for x in arr[-50:] if isinstance(x, dict) and x.get('ts', 0) >= cutoff]
                    history[key] = arr
                _append_hist('market_cap', resolved_values.get('market_cap', 0))
                _append_hist('volume_24h', resolved_values.get('volume_24h', 0))
                _append_hist('holders', resolved_values.get('holders', 0))
                _append_hist('liquidity', resolved_values.get('liquidity', 0))

                try:
                    existing_market_cap = float(entry.get('market_cap', 0) or 0)
                except Exception:
                    existing_market_cap = 0.0
                try:
                    existing_volume = float(entry.get('volume_24h', 0) or 0)
                except Exception:
                    existing_volume = 0.0
                try:
                    existing_holders = int(float(entry.get('holders', 0) or 0))
                except Exception:
                    existing_holders = 0
                try:
                    existing_liquidity = float(entry.get('liquidity', 0) or 0)
                except Exception:
                    existing_liquidity = 0.0

                resolved_market_cap = self._to_float(resolved_values.get('market_cap')) or 0.0
                resolved_volume = self._to_float(resolved_values.get('volume_24h')) or 0.0
                resolved_holders = int(self._to_float(resolved_values.get('holders')) or 0)
                resolved_liquidity = self._to_float(resolved_values.get('liquidity')) or 0.0
                resolved_price = self._to_float(resolved_values.get('price')) or 0.0

                merged_market_cap = resolved_market_cap if resolved_market_cap > 0 else existing_market_cap
                merged_volume = resolved_volume if resolved_volume > 0 else existing_volume
                merged_holders = resolved_holders if resolved_holders > 0 and not self._is_placeholder_holders_metric(resolved_holders) else (
                    existing_holders if existing_holders > 0 and not self._is_placeholder_holders_metric(existing_holders) else 0
                )
                merged_liquidity = resolved_liquidity if resolved_liquidity > 0 else existing_liquidity

                fallback_entry = {
                    'name': name,
                    'symbol': symbol,
                    'chain': chain_hint,
                    'market_cap': merged_market_cap,
                    'volume_24h': merged_volume,
                    'holders': merged_holders,
                    'liquidity': merged_liquidity,
                    'price': resolved_price if resolved_price > 0 else (self._to_float(entry.get('price')) or 0.0),
                    'history': history,
                    'last_updated': now_ts,
                    'source': 'webhook_cache'
                }
                if incoming_market_data:
                    fallback_entry['market_data'] = incoming_market_data
                elif existing_market_data:
                    fallback_entry['market_data'] = existing_market_data
                if incoming_onchain_data:
                    fallback_entry['onchain_data'] = incoming_onchain_data
                elif existing_onchain_data:
                    fallback_entry['onchain_data'] = existing_onchain_data
                if incoming_liquidity_data:
                    fallback_entry['liquidity_data'] = incoming_liquidity_data
                elif existing_liquidity_data:
                    fallback_entry['liquidity_data'] = existing_liquidity_data
                if isinstance(entry.get('metric_history'), list):
                    fallback_entry['metric_history'] = entry.get('metric_history')
                if isinstance(entry.get('overwrite_policy'), dict):
                    fallback_entry['overwrite_policy'] = entry.get('overwrite_policy')

                token_mappings[storage_key] = fallback_entry
                raw_token_key = str(token_address or '').strip()
                if storage_key != raw_token_key:
                    token_mappings.pop(raw_token_key, None)
                storage_key_lower = storage_key.lower()
                for existing_key in list(token_mappings.keys()):
                    if existing_key == storage_key:
                        continue
                    if str(existing_key).lower() == storage_key_lower:
                        token_mappings.pop(existing_key, None)
                
                # Save updated fallback data
                with open(FALLBACK_FILE, 'w') as f:
                    json.dump(fallback_data, f, indent=2)
                
                print(f"    📦 Updated fallback data for {storage_key} with real values")
            
        except Exception as e:
            print(f"    ❌ Error updating fallback data: {e}")
    
    def get_fallback_liquidity_data(self, token_address):
        """Get liquidity data from fallback cache"""
        try:
            if os.path.exists(FALLBACK_FILE):
                with open(FALLBACK_FILE, 'r') as f:
                    fallback_data = json.load(f)
                
                token_data = fallback_data.get('token_mappings', {}).get(token_address, {})
                liquidity = token_data.get('liquidity', 0)
                
                if liquidity > 0:
                    return {
                        'liquidity_score': liquidity,
                        'source': 'fallback_cache'
                    }
        except Exception as e:
            print(f"    ❌ Error reading fallback data: {e}")
        return None
    
    def fetch_alchemy_comprehensive_data(self, token_address):
        """Fetch onchain data from Alchemy"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('ALCHEMY_API_KEY')
            
            if not api_key:
                print(f"    ⚠️  Alchemy API key not found")
                return None
            
            # Check if this is an L2 token
            if self._is_l2_token(token_address):
                print(f"    ⚠️  Skipping Alchemy for L2 token {token_address}")
                return None
            
            url = f"https://eth-mainnet.g.alchemy.com/v2/{api_key}"
            payload = {
                "jsonrpc": "2.0",
                "method": "alchemy_getTokenMetadata",
                "params": [token_address],
                "id": 1
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    result = data['result']
                    
                    # Handle None values safely
                    decimals = result.get('decimals')
                    if decimals is not None:
                        try:
                            decimals = int(decimals)
                        except (ValueError, TypeError):
                            decimals = 0
                    else:
                        decimals = 0
                    
                    name = result.get('name', '')
                    symbol = result.get('symbol', '')
                    
                    # Only return data if we have meaningful information
                    if name or symbol or decimals > 0:
                        return {
                            'name': name,
                            'symbol': symbol,
                            'decimals': decimals,
                            'source': 'real-time'
                        }
                    else:
                        print(f"    ⚠️  Alchemy returned no valid data for {token_address}")
                else:
                    print(f"    ⚠️  Alchemy returned no result for {token_address}")
            else:
                print(f"    ⚠️  Alchemy API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ Alchemy error: {e}")
        return None
    
    def fetch_twitter_social_data(self, token_symbol, token_name):
        """Fetch Twitter social data"""
        try:
            if self.assessor:
                with self._assessor_lock:
                    data = self.assessor.fetch_twitter_social_data(token_symbol, token_name)
                return data or {}
            return {
                'followers': 0,
                'mentions_24h': 0,
                'sentiment_score': 0.0,
                'source': 'simulated'
            }
        except Exception as e:
            print(f"  ❌ Twitter error: {e}")
        return None
    
    def fetch_telegram_social_data(self, token_symbol, token_name):
        """Fetch Telegram social data"""
        try:
            if self.assessor:
                with self._assessor_lock:
                    data = self.assessor.fetch_telegram_social_data(token_symbol, token_name)
                return data or {}
            return {
                'members': 0,
                'messages_24h': 0,
                'sentiment_score': 0.0,
                'source': 'simulated'
            }
        except Exception as e:
            print(f"  ❌ Telegram error: {e}")
        return None
    
    def fetch_discord_social_data(self, token_symbol, token_name):
        """Fetch Discord social data"""
        try:
            if self.assessor:
                with self._assessor_lock:
                    data = self.assessor.fetch_discord_social_data(token_symbol, token_name)
                return data or {}
            return {
                'members': 0,
                'messages_24h': 0,
                'sentiment_score': 0.0,
                'source': 'simulated'
            }
        except Exception as e:
            print(f"  ❌ Discord error: {e}")
        return None
    
    def fetch_reddit_social_data(self, token_symbol, token_name):
        """Fetch Reddit social data"""
        try:
            if self.assessor:
                with self._assessor_lock:
                    data = self.assessor.fetch_reddit_social_data(token_symbol, token_name)
                return data or {}
            return {
                'subscribers': 0,
                'posts_24h': 0,
                'sentiment_score': 0.0,
                'source': 'simulated'
            }
        except Exception as e:
            print(f"  ❌ Reddit error: {e}")
        return None
    
    def fetch_santiment_data(self, token_address, chain):
        """Fetch sentiment data from Santiment"""
        try:
            if self.assessor:
                with self._assessor_lock:
                    data = self.assessor.fetch_santiment_data(token_address, chain)
                return data or {}
            return {
                'sentiment_score': 0.0,
                'social_volume': 0,
                'dev_activity': 0,
                'source': 'simulated'
            }
        except Exception as e:
            print(f"  ❌ Santiment error: {e}")
        return None
    
    def fetch_arkham_intelligence_data(self, token_address, token_symbol):
        """Fetch intelligence data from Arkham"""
        try:
            if self.assessor:
                with self._assessor_lock:
                    data = self.assessor.fetch_arkham_intelligence_data(token_address, token_symbol)
                return data or {}
            return {
                'risk_score': 0.0,
                'intelligence_score': 0.0,
                'source': 'simulated'
            }
        except Exception as e:
            print(f"  ❌ Arkham error: {e}")
        return None
    
    def get_symbol_from_address(self, token_address):
        """Get symbol from token address with enhanced fallback logic"""
        try:
            # Clean the token address (remove chain suffix like _eth, _polygon, etc.)
            clean_address = token_address.split('_')[0] if '_' in token_address else token_address
            map_key = str(clean_address).strip()
            if map_key.startswith('0x'):
                map_key = map_key.lower()

            # Try token_mappings (generated from tokens.csv)
            try:
                get_token_symbol = self._load_token_mapping_resolver('get_token_symbol')
                if callable(get_token_symbol):
                    symbol = get_token_symbol(map_key)
                    if symbol and symbol != 'Unknown':
                        print(f"  ✅ Found symbol for {clean_address}: {symbol}")
                        return symbol
            except Exception as e:
                print(f"  ⚠️  Token mappings import failed: {e}")
            
            # Last resort: tokens.csv via TokenManager (handles column renames)
            try:
                from centralized_token_manager import TokenManager

                tm = TokenManager()
                token_row = tm.get_token_by_address(clean_address)
                if token_row and token_row.get('symbol'):
                    symbol = token_row['symbol']
                    print(f"  ✅ Found symbol from tokens.csv for {clean_address}: {symbol}")
                    return symbol
            except Exception as e:
                print(f"  ⚠️  CSV lookup failed: {e}")
            
            print(f"  ⚠️  No symbol mapping found for {clean_address}")
            return None
            
        except Exception as e:
            print(f"  ❌ Error getting symbol for {token_address}: {e}")
            return None
    
    def fetch_coingecko_data(self, symbol):
        """Fetch real data from CoinGecko API"""
        try:
            # Get CoinGecko ID
            resolver = self._load_token_mapping_resolver('get_coingecko_id')
            coin_id = None
            if callable(resolver):
                resolved_id = resolver(symbol)
                if resolved_id is not None:
                    coin_id = str(resolved_id)
            
            if not coin_id:
                print(f"    ❌ No CoinGecko ID found for {symbol}")
                return None
            
            print(f"    🔍 CoinGecko ID: {coin_id}")
            
            # Fetch comprehensive data from CoinGecko
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd',
                'include_market_cap': 'true',
                'include_24hr_vol': 'true',
                'include_24hr_change': 'true',
                'include_last_updated_at': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            print(f"    📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"    📊 Response data: {data}")
                
                if coin_id in data:
                    coin_data = data[coin_id]
                    market_cap = coin_data.get('usd_market_cap', 0)
                    volume_24h = coin_data.get('usd_24h_vol', 0)
                    price = coin_data.get('usd', 0)
                    change_24h = coin_data.get('usd_24h_change', 0)
                    last_updated = coin_data.get('last_updated_at', 0)
                    
                    # If CoinGecko returns 0 market cap, try fallback data
                    if market_cap == 0:
                        print(f"    ⚠️  CoinGecko returned 0 market cap for {symbol}, trying fallback data")
                        fallback_data = self._get_fallback_market_data(symbol)
                        if fallback_data:
                            print(f"    📦 Using fallback data for {symbol}")
                            return fallback_data
                    
                    result = {
                        'market_cap': market_cap,
                        'volume_24h': volume_24h,
                        'price': price,
                        'change_24h': change_24h,
                        'last_updated': last_updated,
                        'source': 'real-time'
                    }
                    print(f"    ✅ CoinGecko data: MC=${result['market_cap']:,.0f}, Vol=${result['volume_24h']:,.0f}")
                    return result
                else:
                    print(f"    ❌ Coin ID {coin_id} not found in response")
            elif response.status_code == 429:
                print(f"    ⏰ Rate limited by CoinGecko - will retry later")
                # Try to get fallback data for rate-limited tokens
                fallback_data = self._get_fallback_market_data(symbol)
                if fallback_data:
                    print(f"    📦 Using fallback data for {symbol}")
                    return fallback_data
                return {
                    'error': 'rate_limited',
                    'cooldown_seconds': self._default_source_cooldown('coingecko'),
                    'source': 'coingecko'
                }
            else:
                print(f"    ❌ API Error: {response.text}")
        except Exception as e:
            print(f"  ❌ CoinGecko API error: {e}")
        
        # Special handling for SONIC - if CoinGecko returns 0 market cap, use fallback
        if symbol == 'SONIC':
            print(f"    ⚠️  CoinGecko returned 0 market cap for SONIC, using CoinMarketCap data")
            fallback_data = self._get_fallback_market_data(symbol)
            if fallback_data:
                print(f"    📦 Using CoinMarketCap fallback data for SONIC")
                return fallback_data
        
        return None
    
    def _get_fallback_market_data(self, symbol):
        """Get fallback market data from cached real fallback entries (no hardcoded estimates)."""
        try:
            mappings = self.fallback_data.get('token_mappings', {}) if isinstance(self.fallback_data, dict) else {}
            symbol_upper = str(symbol or '').upper()
            for entry in mappings.values():
                if not isinstance(entry, dict):
                    continue
                if str(entry.get('symbol', '')).upper() != symbol_upper:
                    continue

                market_cap = 0.0
                volume_24h = 0.0
                price = 0.0

                aggregates = entry.get('aggregates', {}) if isinstance(entry.get('aggregates'), dict) else {}
                market = aggregates.get('market', {}) if isinstance(aggregates.get('market'), dict) else {}
                market_cap = float(market.get('market_cap', 0) or 0)
                volume_24h = float(market.get('volume_24h', 0) or 0)
                price = float(market.get('price', 0) or 0)

                market_data = entry.get('market_data', {}) if isinstance(entry.get('market_data'), dict) else {}
                for payload in market_data.values():
                    if not isinstance(payload, dict):
                        continue
                    market_cap = max(market_cap, float(payload.get('market_cap', 0) or 0))
                    volume_24h = max(volume_24h, float(payload.get('volume_24h', 0) or 0))
                    price = max(price, float(payload.get('price', 0) or 0))

                if market_cap > 0 or volume_24h > 0 or price > 0:
                    return {
                        'market_cap': market_cap,
                        'volume_24h': volume_24h,
                        'price': price,
                        'source': 'fallback_cache'
                    }
        except Exception:
            return None
        return None
    
    def fetch_cmc_data(self, symbol):
        """Fetch real data from CoinMarketCap API"""
        try:
            # Get CMC ID
            resolver = self._load_token_mapping_resolver('get_cmc_id')
            cmc_id = None
            if callable(resolver):
                resolved_id = resolver(symbol)
                if resolved_id is not None:
                    cmc_id = str(resolved_id)
            
            if not cmc_id:
                return None
            
            # Load API key
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('COINMARKETCAP_API_KEY')
            
            if not api_key:
                return None
            
            # Fetch from CoinMarketCap
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {'X-CMC_PRO_API_KEY': api_key}
            params = {'id': cmc_id}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and str(cmc_id) in data['data']:
                    quote = data['data'][str(cmc_id)]['quote']['USD']
                    return {
                        'market_cap': quote.get('market_cap', 0),
                        'volume_24h': quote.get('volume_24h', 0),
                        'price': quote.get('price', 0),
                        'source': 'real-time'
                    }
            elif response.status_code == 429:
                return {
                    'error': 'rate_limited',
                    'cooldown_seconds': self._default_source_cooldown('coinmarketcap'),
                    'source': 'coinmarketcap'
                }
        except Exception as e:
            print(f"  ❌ CoinMarketCap API error: {e}")
        return None
    
    def _is_l2_token(self, token_address):
        """True when tokens.csv declares this contract on a non-eth chain (skip Ethereum L1-only probes)."""
        try:
            from token_list_registry import registry_declared_chains_for_address

            declared = registry_declared_chains_for_address(str(token_address or '').strip())
            if not declared:
                return False
            return any(c != 'eth' for c in declared)
        except Exception:
            return False

    def _get_l2_chain(self, token_address):
        """Return a coarse L2 hint from tokens.csv (Optimism first for legacy callers)."""
        try:
            from token_list_registry import registry_declared_chains_for_address

            declared = registry_declared_chains_for_address(str(token_address or '').strip())
            if 'op' in declared:
                return 'optimism'
            if 'arbitrum' in declared:
                return 'arbitrum'
            if 'polygon' in declared:
                return 'polygon'
            if 'base' in declared:
                return 'base'
        except Exception:
            pass
        return None
    
    def fetch_etherscan_data(self, token_address, chain='eth'):
        """Fetch real data from Etherscan API"""
        try:
            chain_key = self._normalize_chain_code(chain)
            if chain_key not in ('eth', 'ethereum'):
                return None

            # Load API key
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('ETHERSCAN_API_KEY')
            
            if not api_key:
                print(f"    ⚠️  Etherscan API key not found")
                return None
            
            # Check if this is an L2 token
            if self._is_l2_token(token_address):
                print(f"    ⚠️  Skipping Etherscan for L2 token {token_address}")
                return None
            
            # Get token holders
            url = "https://api.etherscan.io/v2/api"
            params = {
                'chainid': 1,
                'module': 'token',
                'action': 'tokenholderlist',
                'contractaddress': token_address,
                'page': 1,
                'offset': 1,
                'apikey': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('result'):
                    holders_data = data['result'][0]
                    return {
                        'holders': int(holders_data.get('TokenHolderCount', 0)),
                        'total_supply': float(holders_data.get('TokenSupply', 0)),
                        'source': 'real-time'
                    }
                else:
                    print(f"    ⚠️  Etherscan returned status: {data.get('status')}, message: {data.get('message', 'Unknown')}")
            else:
                print(f"    ⚠️  Etherscan API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ Etherscan API error: {e}")
        return None
    
    def fetch_ethplorer_data(self, token_address, chain='eth'):
        """Fetch real data from Ethplorer API"""
        try:
            chain_key = self._normalize_chain_code(chain)
            if chain_key not in ('eth', 'ethereum'):
                return None

            # Check if this is an L2 token
            if self._is_l2_token(token_address):
                print(f"    ⚠️  Skipping Ethplorer for L2 token {token_address}")
                return None
            
            url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey=freekey"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('error'):
                    print(f"    ⚠️  Ethplorer error: {data.get('error')}")
                    return None
                
                holders = data.get('holdersCount', 0)
                total_supply = data.get('totalSupply', 0)
                
                if holders > 0 or total_supply > 0:
                    return {
                        'holders': int(holders),
                        'total_supply': float(total_supply),
                        'source': 'real-time'
                    }
                else:
                    print(f"    ⚠️  Ethplorer returned no valid data for {token_address}")
            else:
                print(f"    ⚠️  Ethplorer API returned status {response.status_code}")
        except Exception as e:
            print(f"  ❌ Ethplorer API error: {e}")
        return None
    
    def get_fallback_data(self, token_address):
        """Get fallback data for a token"""
        
        address_lower = token_address.lower()
        
        if address_lower in self.fallback_data.get('token_mappings', {}):
            fallback = self.fallback_data['token_mappings'][address_lower]
            print(f"✅ Fallback data found for {token_address}: {fallback.get('symbol', 'Unknown')}")
            return fallback
        
        print(f"⚠️  No fallback data for {token_address}")
        return None
    
    def update_token_data(self, token_address, real_time_data=None, fallback_data=None):
        """Update token data in cache with real-time or fallback data"""
        
        if 'tokens' not in self.cache_data:
            self.cache_data['tokens'] = {}
        
        current_data = self.cache_data['tokens'].get(token_address, {})
        if not isinstance(current_data, dict):
            current_data = {}
        now_ts = time.time()

        existing_market_data = current_data.get('market_data', {}) if isinstance(current_data.get('market_data'), dict) else {}
        existing_onchain_data = current_data.get('onchain_data', {}) if isinstance(current_data.get('onchain_data'), dict) else {}
        existing_liquidity_data = current_data.get('liquidity_data', {}) if isinstance(current_data.get('liquidity_data'), dict) else {}
        
        # Merge real-time data if available
        if isinstance(real_time_data, dict) and real_time_data:
            incoming_market_data = real_time_data.get('market_data', {}) if isinstance(real_time_data.get('market_data'), dict) else {}
            incoming_onchain_data = real_time_data.get('onchain_data', {}) if isinstance(real_time_data.get('onchain_data'), dict) else {}
            incoming_liquidity_data = real_time_data.get('liquidity_data', {}) if isinstance(real_time_data.get('liquidity_data'), dict) else {}
            incoming_social_data = real_time_data.get('social_data', {}) if isinstance(real_time_data.get('social_data'), dict) else {}
            incoming_sentiment_data = real_time_data.get('sentiment_data', {}) if isinstance(real_time_data.get('sentiment_data'), dict) else {}
            incoming_enhanced_data = real_time_data.get('enhanced_data', {}) if isinstance(real_time_data.get('enhanced_data'), dict) else {}
            incoming_security_data = real_time_data.get('security_data', {}) if isinstance(real_time_data.get('security_data'), dict) else {}
            incoming_aggregates = real_time_data.get('aggregates', {}) if isinstance(real_time_data.get('aggregates'), dict) else {}

            merged_market_data = dict(existing_market_data)
            merged_market_data.update(incoming_market_data)
            merged_onchain_data = dict(existing_onchain_data)
            merged_onchain_data.update(incoming_onchain_data)
            merged_liquidity_data = dict(existing_liquidity_data)
            merged_liquidity_data.update(incoming_liquidity_data)

            current_data.update({
                'last_real_time_update': now_ts,
                'timestamp': now_ts,
                'market_data': merged_market_data,
                'onchain_data': merged_onchain_data,
                'social_data': incoming_social_data,
                'liquidity_data': merged_liquidity_data,
                'sentiment_data': incoming_sentiment_data,
                'aggregates': incoming_aggregates,
                'enhanced_data': incoming_enhanced_data,
                'security_data': incoming_security_data,
                'red_flags': real_time_data.get('red_flags', []),
                'value_changes': real_time_data.get('value_changes', {}),
                'symbol': real_time_data.get('symbol') or current_data.get('symbol'),
                'name': real_time_data.get('name') or current_data.get('name'),
                'chain': real_time_data.get('chain') or current_data.get('chain'),
                'data_source': 'real-time'
            })

            existing_source_labels = []
            existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_market_data))
            existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_onchain_data))
            existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_liquidity_data))
            new_source_labels = []
            new_source_labels.extend(self._collect_source_labels_for_confidence(incoming_market_data))
            new_source_labels.extend(self._collect_source_labels_for_confidence(incoming_onchain_data))
            new_source_labels.extend(self._collect_source_labels_for_confidence(incoming_liquidity_data))
            candidate_metrics = self._extract_candidate_metrics(real_time_data)
            metric_source_values = self._build_metric_source_values(real_time_data, current_data.get('chain') or '')
            resolved_values = self._apply_assessment_overwrite_policy(
                current_data,
                candidate_metrics,
                metric_source_values,
                existing_source_labels,
                new_source_labels,
                current_data.get('chain') or ''
            )
            self._apply_resolved_metrics_to_entry(current_data, resolved_values)
            current_data.pop('swr_stale_served', None)
            current_data.pop('swr_refresh_queued_at', None)
            print(f"✅ Updated {token_address} with real-time data")
        
        # Use fallback data if real-time failed
        elif isinstance(fallback_data, dict) and fallback_data:
            current_data.update({
                'last_fallback_update': now_ts,
                'timestamp': now_ts,
                'symbol': fallback_data.get('symbol') or current_data.get('symbol'),
                'name': fallback_data.get('name') or current_data.get('name'),
                'type': fallback_data.get('type'),
                'verified': fallback_data.get('verified', False),
                'chain': fallback_data.get('chain') or current_data.get('chain'),
                'data_source': 'fallback'
            })
            candidate_metrics = {
                'market_cap': self._to_float(fallback_data.get('market_cap')) or 0.0,
                'volume_24h': self._to_float(fallback_data.get('volume_24h')) or 0.0,
                'holders': int(self._to_float(fallback_data.get('holders')) or 0),
                'liquidity': self._to_float(fallback_data.get('liquidity')) or 0.0,
                'price': self._to_float(fallback_data.get('price')) or 0.0,
            }
            metric_source_values = {'market_cap': {}, 'volume_24h': {}, 'holders': {}, 'liquidity': {}}
            if candidate_metrics['market_cap'] > 0:
                metric_source_values['market_cap']['fallback'] = candidate_metrics['market_cap']
            if candidate_metrics['volume_24h'] > 0:
                metric_source_values['volume_24h']['fallback'] = candidate_metrics['volume_24h']
            if candidate_metrics['holders'] > 0 and not self._is_placeholder_holders_metric(candidate_metrics['holders']):
                metric_source_values['holders']['fallback'] = float(candidate_metrics['holders'])
            if candidate_metrics['liquidity'] > 0:
                metric_source_values['liquidity']['fallback'] = candidate_metrics['liquidity']
            existing_source_labels = []
            existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_market_data))
            existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_onchain_data))
            existing_source_labels.extend(self._collect_source_labels_for_confidence(existing_liquidity_data))
            resolved_values = self._apply_assessment_overwrite_policy(
                current_data,
                candidate_metrics,
                metric_source_values,
                existing_source_labels,
                ['fallback'],
                current_data.get('chain') or ''
            )
            self._apply_resolved_metrics_to_entry(current_data, resolved_values)
            queued_refresh = self._enqueue_swr_refresh(token_address)
            current_data['swr_stale_served'] = True
            if queued_refresh:
                current_data['swr_refresh_queued_at'] = now_ts
            print(f"✅ Updated {token_address} with fallback data")
        
        self.cache_data['tokens'][token_address] = current_data
        return current_data

    def load_tokens_from_csv(self):
        """Load token list from tokens.csv file"""
        try:
            import pandas as pd
            csv_file = os.path.join(DATA_DIR, 'tokens.csv')
            
            if not os.path.exists(csv_file):
                print(f"⚠️  tokens.csv not found at {csv_file}")
                return []
            
            df = pd.read_csv(csv_file)
            tokens = []
            address_chain_cache = {}
            
            for _, row in df.iterrows():
                address = str(row.get('address') or row.get('Address') or '').strip()
                chain = self._normalize_chain_code(row.get('chain') or row.get('Chain') or '')
                # Use clean address without chain suffix for consistency
                if address:
                    tokens.append(address)
                    if chain:
                        address_chain_cache[address.lower()] = chain

            if address_chain_cache:
                self._address_chain_cache = address_chain_cache
            
            print(f"✅ Loaded {len(tokens)} tokens from tokens.csv")
            return tokens
            
        except Exception as e:
            print(f"❌ Error loading tokens from CSV: {e}")
            return []

    def update_all_cache(self):
        """Update all cached data using enhanced cache manager if available"""
        
        print("🔄 Triggered cache update for all tokens")
        
        # Use enhanced cache manager if available
        if cache_manager:
            return self._update_all_cache_enhanced()
        else:
            return self._update_all_cache_basic()
    
    def _update_all_cache_enhanced(self):
        """Update all cached data using priority-based strategy"""
        try:
            # Load tokens from CSV file (source of truth)
            tokens_to_update = self.load_tokens_from_csv()
            
            # If CSV loading fails, fall back to existing cache
            if not tokens_to_update:
                print("⚠️  Falling back to existing cache tokens")
                tokens_to_update = list(self.cache_data.get('tokens', {}).keys())
            
            updated_count = 0
            skipped_count = 0
            rate_limited_count = 0
            fallback_count = 0
            
            print(f"🔄 Starting priority-based cache update for {len(tokens_to_update)} tokens...")
            
            for i, token_address in enumerate(tokens_to_update, 1):
                try:
                    print(f"\n📋 [{i}/{len(tokens_to_update)}] Processing {token_address}")
                    
                    # Check if token already has comprehensive data
                    existing_data = self.get_existing_token_data(token_address)
                    if self._has_comprehensive_data(existing_data):
                        print(f"    ⏭️  Skipping {token_address} - already has comprehensive data")
                        skipped_count += 1
                        continue
                    
                    # Check what data is missing and fetch only what's needed
                    missing_data_types = self._get_missing_data_types(existing_data)
                    if not missing_data_types:
                        print(f"    ⏭️  Skipping {token_address} - no missing data types")
                        skipped_count += 1
                        continue
                    
                    print(f"    🔄 Fetching missing data types: {', '.join(missing_data_types)}")
                    real_time_data = self.fetch_real_time_data(token_address)
                    
                    if real_time_data:
                        # Update cache directly with fresh data
                        if cache_manager and hasattr(cache_manager, 'update_cache_with_real_time_data'):
                            cache_manager.update_cache_with_real_time_data(token_address, real_time_data)
                        
                        # Update fallback data with real data
                        self.update_fallback_data_with_real_data(token_address, real_time_data)
                        
                        updated_count += 1
                        print(f"    ✅ Updated {token_address} with fresh data")
                    else:
                        print(f"    ⚠️  No data available for {token_address}")
                        
                except Exception as e:
                    if "rate limit" in str(e).lower() or "429" in str(e):
                        rate_limited_count += 1
                        print(f"    ⏰ Rate limited for {token_address}, using fallback")
                    else:
                        print(f"    ❌ Error updating {token_address}: {e}")
            
            # Sync webhook server's cache with cache manager
            if cache_manager and hasattr(cache_manager, 'cache_data'):
                # Update timestamp
                if 'last_updated' in cache_manager.cache_data:
                    self.cache_data['last_updated'] = cache_manager.cache_data['last_updated']
                    print(f"🔄 Updated webhook server timestamp to: {self.cache_data['last_updated']}")
                
                # Sync token data
                cache_manager_tokens = cache_manager.cache_data.get('tokens', {})
                self.cache_data['tokens'] = cache_manager_tokens
                print(f"🔄 Synced {len(cache_manager_tokens)} tokens from cache manager")
                
                # Save the synced data
                self.save_cache_data()
            
            # Get cache statistics
            stats = cache_manager.get_cache_stats() if cache_manager and hasattr(cache_manager, 'get_cache_stats') else {}
            
            print(f"\n📊 Cache Update Summary:")
            print(f"   ✅ Fresh data updated: {updated_count}")
            print(f"   ⏭️  Skipped (already complete): {skipped_count}")
            print(f"   📦 Fallback data used: {fallback_count}")
            print(f"   ⏰ Rate limited: {rate_limited_count}")
            print(f"   📋 Total processed: {len(tokens_to_update)}")
            
            return {
                'status': 'success',
                'message': f'Updated {updated_count} tokens with fresh data, {skipped_count} skipped (already complete), {fallback_count} with fallback data',
                'total_tokens': len(tokens_to_update),
                'updated_count': updated_count,
                'skipped_count': skipped_count,
                'fallback_count': fallback_count,
                'rate_limited_count': rate_limited_count,
                'cache_stats': stats
            }
            
        except Exception as e:
            print(f"❌ Error in enhanced update_all_cache: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _update_all_cache_basic(self):
        """Update all cached data with basic cache management"""
        try:
            # Load tokens from CSV file (source of truth)
            tokens_to_update = self.load_tokens_from_csv()
            
            # If CSV loading fails, fall back to existing cache
            if not tokens_to_update:
                print("⚠️  Falling back to existing cache tokens")
                tokens_to_update = list(self.cache_data.get('tokens', {}).keys())
            
            updated_count = 0
            fallback_count = 0
            
            for token_address in tokens_to_update:
                try:
                    # Try real-time data first
                    real_time_data = self.fetch_real_time_data(token_address)
                    self.update_token_data(token_address, real_time_data=real_time_data)
                    updated_count += 1
                    
                except Exception as e:
                    print(f"⚠️  Real-time failed for {token_address}: {e}")
                    
                    # Fall back to cached fallback data
                    fallback_data = self.get_fallback_data(token_address)
                    if fallback_data:
                        self.update_token_data(token_address, fallback_data=fallback_data)
                        fallback_count += 1
            
            # Update last_updated timestamp
            self.cache_data['last_updated'] = time.time()
            
            # Save updated cache
            self.save_cache_data()
            
            return {
                'status': 'success',
                'message': f'Updated {updated_count} tokens with real-time data, {fallback_count} with fallback data',
                'total_tokens': len(tokens_to_update)
            }
            
        except Exception as e:
            print(f"❌ Error in basic update_all_cache: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

# Initialize webhook server
webhook_server = WebhookServer()
update_all_lock = threading.Lock()
update_all_inflight = False
update_all_last_started = None
update_all_last_finished = None
update_all_last_result = None


def _run_update_all_background_job():
    """Background worker for full cache refresh."""
    global update_all_inflight, update_all_last_finished, update_all_last_result
    try:
        result = webhook_server.update_all_cache()
    except Exception as e:
        result = {
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }
        print(f"❌ Async update_all job failed: {e}")
    with update_all_lock:
        update_all_inflight = False
        update_all_last_finished = datetime.now().isoformat()
        update_all_last_result = result


def _extract_token_update_ts(entry: Any) -> float:
    if not isinstance(entry, dict):
        return 0.0
    for field_name in ('last_real_time_update', 'timestamp', 'last_fallback_update'):
        raw = entry.get(field_name, 0)
        try:
            ts = float(raw)
        except (TypeError, ValueError):
            ts = 0.0
        if ts > 0:
            return ts
    return 0.0


def _build_chain_deep_health_snapshot(chain_hint: str) -> tuple[dict[str, Any], int]:
    chain_code = webhook_server._normalize_chain_code(chain_hint)
    supported_chains = _DEEP_HEALTH_SUPPORTED_CHAINS
    if chain_code not in supported_chains:
        return ({
            'status': 'error',
            'message': f'unsupported_chain:{chain_hint}',
            'supported_chains': sorted(supported_chains),
            'timestamp': datetime.now().isoformat(),
        }, 404)

    tokens_blob = webhook_server.cache_data.get('tokens', {})
    if not isinstance(tokens_blob, dict):
        tokens_blob = {}

    now_ts = time.time()
    total_tokens = 0
    fresh_tokens = 0
    stale_tokens = 0
    latest_update_ts = 0.0
    oldest_update_ts = 0.0
    stale_examples: list[str] = []

    for token_key, token_entry in tokens_blob.items():
        if not isinstance(token_entry, dict):
            continue
        entry_chain = webhook_server._normalize_chain_code(token_entry.get('chain', ''))
        if entry_chain != chain_code:
            continue
        total_tokens += 1
        update_ts = _extract_token_update_ts(token_entry)
        if update_ts > 0:
            if latest_update_ts <= 0 or update_ts > latest_update_ts:
                latest_update_ts = update_ts
            if oldest_update_ts <= 0 or update_ts < oldest_update_ts:
                oldest_update_ts = update_ts
        age_seconds = (now_ts - update_ts) if update_ts > 0 else float('inf')
        if age_seconds <= float(SCRIPT_API_DEEP_HEALTH_MAX_AGE_SECONDS):
            fresh_tokens += 1
            continue
        stale_tokens += 1
        if len(stale_examples) < 5:
            stale_examples.append(str(token_key))

    status = 'healthy'
    http_status = 200
    message = f'chain cache healthy for {chain_code}'
    if total_tokens < SCRIPT_API_DEEP_HEALTH_MIN_TOKENS:
        status = 'warming_up'
        http_status = 200
        message = f'insufficient_token_coverage_for_chain:{chain_code}'
    elif fresh_tokens <= 0:
        status = 'degraded'
        http_status = 503
        message = f'no_fresh_tokens_for_chain:{chain_code}'

    latest_age = round(max(0.0, now_ts - latest_update_ts), 1) if latest_update_ts > 0 else None
    oldest_age = round(max(0.0, now_ts - oldest_update_ts), 1) if oldest_update_ts > 0 else None

    return ({
        'status': status,
        'message': message,
        'chain': chain_code,
        'max_age_seconds': int(SCRIPT_API_DEEP_HEALTH_MAX_AGE_SECONDS),
        'min_tokens': int(SCRIPT_API_DEEP_HEALTH_MIN_TOKENS),
        'cached_tokens': int(total_tokens),
        'fresh_tokens': int(fresh_tokens),
        'stale_tokens': int(stale_tokens),
        'latest_update_age_seconds': latest_age,
        'oldest_update_age_seconds': oldest_age,
        'stale_examples': stale_examples,
        'timestamp': datetime.now().isoformat(),
    }, http_status)

@app.route('/webhook/update_all', methods=['POST'])
def update_all_cache():
    """Update all cached data"""
    access_error = _require_webhook_access(require_signature=True)
    if access_error:
        return access_error

    global update_all_inflight, update_all_last_started
    async_mode_raw = request.args.get('async', '0')
    async_mode = str(async_mode_raw).strip().lower() in {'1', 'true', 'yes', 'on'}

    if async_mode:
        with update_all_lock:
            if update_all_inflight:
                return jsonify({
                    'status': 'accepted',
                    'message': 'Update already running',
                    'mode': 'async',
                    'in_progress': True,
                    'started_at': update_all_last_started,
                    'timestamp': datetime.now().isoformat()
                }), 202
            update_all_inflight = True
            update_all_last_started = datetime.now().isoformat()

        worker = threading.Thread(target=_run_update_all_background_job, daemon=True, name='update_all_worker')
        worker.start()
        return jsonify({
            'status': 'accepted',
            'message': 'Background refresh started',
            'mode': 'async',
            'in_progress': True,
            'started_at': update_all_last_started,
            'timestamp': datetime.now().isoformat()
        }), 202
    
    try:
        result = webhook_server.update_all_cache()
        
        return jsonify({
            'status': result['status'],
            'message': result['message'],
            'timestamp': datetime.now().isoformat(),
            'total_tokens': result.get('total_tokens', 0)
        }), 200 if result['status'] == 'success' else 500
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/webhook/update_all_status', methods=['GET'])
def get_update_all_status():
    """Get async update-all execution status."""
    access_error = _require_webhook_access(require_signature=False)
    if access_error:
        return access_error

    with update_all_lock:
        return jsonify({
            'status': 'running' if update_all_inflight else 'idle',
            'in_progress': bool(update_all_inflight),
            'started_at': update_all_last_started,
            'finished_at': update_all_last_finished,
            'last_result': update_all_last_result,
            'timestamp': datetime.now().isoformat()
        })

@app.route('/webhook/update_token', methods=['POST'])
def update_single_token():
    """Update a single token's data"""
    access_error = _require_webhook_access(require_signature=True)
    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}
    token_address = str(
        data.get('address')
        or data.get('token_address')
        or ''
    ).strip()
    
    if not token_address:
        return jsonify({
            'status': 'error',
            'message': 'Token address required in payload field `address` (or legacy `token_address`)',
        }), 400
    
    print(f"🔄 Triggered cache update for {token_address}")
    
    try:
        # Try real-time data first
        try:
            real_time_data = webhook_server.fetch_real_time_data(token_address)
            webhook_server.update_token_data(token_address, real_time_data=real_time_data)
            webhook_server.save_cache_data()
            
            return jsonify({
                'status': 'success',
                'message': f'Updated {token_address} with real-time data',
                'timestamp': datetime.now().isoformat(),
                'data_source': 'real-time'
            }), 200
            
        except Exception as e:
            print(f"⚠️  Real-time failed: {e}")
            
            # Fall back to cached fallback data
            fallback_data = webhook_server.get_fallback_data(token_address)
            if fallback_data:
                webhook_server.update_token_data(token_address, fallback_data=fallback_data)
                webhook_server.save_cache_data()
                
                return jsonify({
                    'status': 'success',
                    'message': f'Updated {token_address} with fallback data',
                    'timestamp': datetime.now().isoformat(),
                    'data_source': 'fallback'
                }), 200
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'No data available for {token_address}',
                    'timestamp': datetime.now().isoformat()
                }), 404
                
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/webhook/status', methods=['GET'])
def get_status():
    """Get webhook server status"""
    access_error = _require_webhook_access(require_signature=False)
    if access_error:
        return access_error
    
    # Get last_updated timestamp and handle invalid values
    last_updated = webhook_server.cache_data.get('last_updated', 0)
    
    # Check if timestamp is valid (not 0 or epoch 0)
    if last_updated <= 0:
        cache_age = 0  # No valid cache data
    else:
        cache_age = (time.time() - last_updated) / 3600
    
    return jsonify({
        'status': 'running',
        'cache_tokens': len(webhook_server.cache_data.get('tokens', {})),
        'fallback_tokens': len(webhook_server.fallback_data.get('token_mappings', {})),
        'symbol_cache_size': len(webhook_server.symbol_cache.get('symbols', {})),
        'cache_age_hours': round(cache_age, 2),
        'last_updated': last_updated,
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/webhook/cache', methods=['GET'])
def get_cache():
    """Get webhook cache data for dashboard display"""
    access_error = _require_webhook_access(require_signature=False)
    if access_error:
        return access_error

    try:
        # Return the cache data in a format suitable for the dashboard
        cache_data = {
            'tokens': webhook_server.cache_data.get('tokens', {}),
            'fallback_data': webhook_server.fallback_data.get('token_mappings', {}),
            'symbol_cache': webhook_server.symbol_cache.get('symbols', {}),
            'last_updated': webhook_server.cache_data.get('last_updated', 0)
        }
        return jsonify(cache_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/webhook/health/deep/<chain>', methods=['GET'])
def deep_health_check(chain):
    """Chain-specific deep health endpoint based on cache freshness."""
    payload, http_status = _build_chain_deep_health_snapshot(chain)
    return jsonify(payload), http_status

def run_webhook_server():
    """Run the webhook server"""
    print("🚀 Starting webhook server on port 5001...")
    print("📡 Available endpoints:")
    print("  • POST /webhook/update_all - Update all token cache")
    print("  • POST /webhook/update_token - Update single token")
    print("  • GET /webhook/status - Get server status")
    print("  • GET /webhook/health - Health check")
    print("  • GET /webhook/health/deep/<chain> - Chain deep health (eth|bsc|tron|polygon|op|… see hodler_chain_codes)")
    print("🔐 Webhook security:")
    print(f"  • shared secret configured: {'yes' if bool(WEBHOOK_SHARED_SECRET) else 'no'}")
    print(f"  • auth required: {'yes' if WEBHOOK_REQUIRE_AUTH else 'no'}")
    print(f"  • signature required on mutating requests: {'yes' if WEBHOOK_REQUIRE_SIGNATURE else 'no'}")
    print(f"  • signature max age seconds: {WEBHOOK_SIGNATURE_MAX_AGE_SECONDS}")
    
    app.run(host='127.0.0.1', port=5001, debug=False, threaded=True)

if __name__ == "__main__":
    run_webhook_server()
