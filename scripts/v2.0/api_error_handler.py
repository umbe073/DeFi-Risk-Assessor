#!/usr/bin/env python3
"""
Enhanced API Error Handler for DeFi Risk Assessment
Provides intelligent fallback mechanisms and better error handling
"""

import os
import time
import json
import logging
import copy
import threading
import tempfile
import random
import atexit
import hashlib
from typing import Dict, Any, Optional, List, Callable, cast
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, parse_qsl, urlencode
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class APIErrorHandler:
    """
    Enhanced API error handler that provides:
    1. Intelligent retry logic with exponential backoff
    2. API-specific error handling
    3. Fallback data mechanisms
    4. Rate limiting management
    5. Error categorization and logging
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._state_lock = threading.RLock()
        self._thread_local = threading.local()
        self.runtime_dir = os.path.join(data_dir, 'api_runtime')
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.error_log_file = os.path.join(self.runtime_dir, 'api_errors.json')
        self.rate_limit_file = os.path.join(self.runtime_dir, 'rate_limits.json')
        self.fallback_data_file = os.path.join(self.runtime_dir, 'api_fallbacks.json')
        self._legacy_files = {
            'errors': os.path.join(data_dir, 'api_errors.json'),
            'rate_limits': os.path.join(data_dir, 'rate_limits.json'),
            'fallbacks': os.path.join(data_dir, 'api_fallbacks.json'),
        }
        self._last_persist_ts = {
            'errors': 0.0,
            'rate_limits': 0.0,
            'fallbacks': 0.0,
        }
        self._persist_interval_sec = {
            'errors': 5.0,
            'rate_limits': 5.0,
            'fallbacks': 20.0,
        }
        # Avoid expensive fallback serialization for very large payloads.
        self._max_fallback_payload_chars = int(os.getenv('API_FALLBACK_MAX_CHARS', '120000'))
        self._max_fallback_file_bytes = int(float(os.getenv('API_FALLBACK_MAX_FILE_MB', '40')) * 1024 * 1024)
        self._max_fallback_entries_per_api = int(os.getenv('API_FALLBACK_MAX_ENTRIES_PER_API', '400'))
        self._fallback_retention_hours = float(os.getenv('API_FALLBACK_RETENTION_HOURS', str(24 * 14)))
        self.rate_limit_policy_file = os.path.join(self.runtime_dir, 'api_rate_limits_free_tier.json')
        self._cache_retention_hours = self._load_cache_retention_hours()
        try:
            self._max_retry_after_seconds = max(
                5.0,
                float(os.getenv('API_MAX_RETRY_AFTER_SECONDS', '300') or 300)
            )
        except Exception:
            self._max_retry_after_seconds = 300.0
        try:
            self._max_cooldown_seconds = max(
                30.0,
                float(os.getenv('API_MAX_COOLDOWN_SECONDS', '900') or 900)
            )
        except Exception:
            self._max_cooldown_seconds = 900.0
        try:
            self._chainabuse_max_cooldown_seconds = max(
                60.0,
                float(os.getenv('CHAINABUSE_MAX_COOLDOWN_SECONDS', '600') or 600)
            )
        except Exception:
            self._chainabuse_max_cooldown_seconds = 600.0
        try:
            self._max_window_seconds = max(
                10.0,
                float(os.getenv('API_MAX_WINDOW_SECONDS', '3600') or 3600)
            )
        except Exception:
            self._max_window_seconds = 3600.0
        try:
            self._chainabuse_window_cap_seconds = max(
                30.0,
                float(os.getenv('CHAINABUSE_WINDOW_CAP_SECONDS', '600') or 600)
            )
        except Exception:
            self._chainabuse_window_cap_seconds = 600.0
        self._migrate_legacy_state_files()
        
        # Load existing error data
        self.error_history = self._load_error_history()
        self.rate_limits = self._load_rate_limits()
        self.fallback_data = self._load_fallback_data()
        
        # API-specific configurations
        self.api_configs = {
            'coingecko': {
                'base_url': 'https://api.coingecko.com',
                'rate_limit': 50,  # calls per minute
                'retry_delay': 1,
                'max_retries': 3,
                'timeout': 10
            },
            'coinmarketcap': {
                'base_url': 'https://pro-api.coinmarketcap.com',
                'rate_limit': 30,
                'retry_delay': 2,
                'max_retries': 2,
                'timeout': 15
            },
            'etherscan': {
                'base_url': 'https://api.etherscan.io',
                # Etherscan free tier is typically 5 req/s (not per-minute).
                # Keep an internal per-minute cap that is permissive but bounded.
                'rate_limit': 240,
                'retry_delay': 0.2,
                'max_retries': 3,
                'timeout': 10
            },
            'moralis': {
                'base_url': 'https://deep-index.moralis.io',
                'rate_limit': 25,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'twitter': {
                'base_url': 'https://api.twitter.com',
                'rate_limit': 15,
                'retry_delay': 5,
                'max_retries': 1,
                'timeout': 10,
                'non_blocking_rate_limit': True,
                'max_blocking_wait': 2
            },
            'defillama': {
                'base_url': 'llama.fi',
                'rate_limit': 100,
                'retry_delay': 0.5,
                'max_retries': 2,
                'timeout': 15
            },
            '1inch': {
                'base_url': 'https://api.1inch.dev',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'debank': {
                'base_url': 'https://pro-openapi.debank.com',
                'rate_limit': 10,
                'retry_delay': 2,
                'max_retries': 2,
                'timeout': 15
            },
            'santiment': {
                'base_url': 'https://api.santiment.net',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 10
            },
            'cointelegraph': {
                'base_url': 'https://cointelegraph.com',
                'rate_limit': 50,
                'retry_delay': 0.5,
                'max_retries': 3,
                'timeout': 10
            },
            'ethplorer': {
                'base_url': 'api.ethplorer.io',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'breadcrumbs': {
                'base_url': 'api.breadcrumbs',
                'rate_limit': 100,
                'retry_delay': 2,
                'max_retries': 2,
                'timeout': 20
            },
            'chainabuse': {
                'base_url': 'api.chainabuse.com',
                'rate_limit': 30,
                'retry_delay': 2,
                'max_retries': 3,
                'timeout': 20,
                'max_backoff': 120,
                'jitter_ratio': 0.35,
                'cooldown': 180,
                'non_blocking_rate_limit': True,
                'max_blocking_wait': 3
            },
            'arkham': {
                'base_url': 'api.arkm.com',
                'rate_limit': 100,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'zapper': {
                'base_url': 'https://public.zapper.xyz',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'blockscout': {
                'base_url': 'blockscout.com',
                'rate_limit': 30,
                'retry_delay': 0.5,
                'max_retries': 2,
                'timeout': 15
            },
            'thegraph': {
                'base_url': 'gateway.thegraph.com',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'coinpaprika': {
                'base_url': 'api.coinpaprika.com',
                'rate_limit': 50,
                'retry_delay': 0.5,
                'max_retries': 2,
                'timeout': 10
            },
            'coincap': {
                'base_url': 'api.coincap.io',
                'rate_limit': 50,
                'retry_delay': 0.5,
                'max_retries': 2,
                'timeout': 10
            },
            'dune': {
                'base_url': 'api.sim.dune.com',
                'rate_limit': 5,
                'retry_delay': 2,
                'max_retries': 2,
                'timeout': 20,
                'non_blocking_rate_limit': True,
                'max_blocking_wait': 2
            },
            'alchemy': {
                'base_url': 'alchemy.com',
                'rate_limit': 50,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'bitquery': {
                'base_url': 'graphql.bitquery.io',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'coindesk': {
                'base_url': 'coindesk.com',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'theblock': {
                'base_url': 'theblock.co',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'decrypt': {
                'base_url': 'decrypt.co',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'reddit': {
                'base_url': 'reddit.com',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'discord': {
                'base_url': 'discord.com',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'telegram': {
                'base_url': 'api.telegram.org',
                'rate_limit': 30,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'scorechain': {
                'base_url': 'api.scorechain.com',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'trm_labs': {
                'base_url': 'trmlabs.com',
                # Public TRM sanctions endpoint defaults to 1 request/sec.
                'rate_limit': 1,
                'window_seconds': 1,
                'retry_delay': 1,
                'max_retries': 0,
                'timeout': 15,
                'non_blocking_rate_limit': True,
                'max_blocking_wait': 0.5
            },
            'opensanctions': {
                'base_url': 'api.opensanctions.org',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'lukka': {
                'base_url': 'api.lukka.tech',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'defisafety': {
                'base_url': 'api.defisafety.com',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'certik': {
                'base_url': 'api.certik.com',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'bitcointalk': {
                'base_url': 'bitcointalk.org',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 15
            },
            'vespia': {
                'base_url': 'dev-api.vespia.io',
                'rate_limit': 20,
                'retry_delay': 1,
                'max_retries': 2,
                'timeout': 20
            }
        }
        self._apply_external_rate_limit_policy()
        with self._state_lock:
            self.rate_limits = self._sanitize_loaded_rate_limits(self.rate_limits)
        
        # Error categories
        self.error_categories = {
            'rate_limit': ['429', 'rate limit', 'too many requests'],
            'auth_error': ['401', '403', 'unauthorized', 'forbidden', 'invalid token'],
            'not_found': ['404', 'not found', 'protocol not found'],
            'server_error': ['500', '502', '503', '504', 'internal server error'],
            'timeout': ['timeout', 'connection error', 'network error'],
            'invalid_request': ['400', 'bad request', 'invalid parameter']
        }

        # Global API concurrency caps to avoid oversubscription across token workers.
        self.api_concurrency_caps = {
            # Keep strict caps where providers are known to throttle aggressively.
            'chainabuse': 1,
            'twitter': 1,
            'dune': 1,
            'thegraph': 2,
            # Allow higher parallelism for high-volume market/on-chain APIs.
            'coingecko': 6,
            'etherscan': 3,
        }
        self.api_concurrency_semaphores = {
            api: threading.BoundedSemaphore(max(1, int(limit)))
            for api, limit in self.api_concurrency_caps.items()
        }
        atexit.register(self._flush_state)

    def _parse_duration_to_hours(self, value: Any, default_hours: float) -> float:
        """Parse settings duration text like '72 hours' / '10 minutes' into hours."""
        try:
            if isinstance(value, (int, float)):
                parsed = float(value)
                return parsed if parsed > 0 else float(default_hours)
            text = str(value or '').strip().lower()
            if not text:
                return float(default_hours)
            num = ''.join(ch for ch in text if ch.isdigit() or ch == '.')
            if not num:
                return float(default_hours)
            amount = float(num)
            if 'minute' in text:
                return amount / 60.0
            if 'day' in text:
                return amount * 24.0
            return amount
        except Exception:
            return float(default_hours)

    def _load_cache_retention_hours(self) -> float:
        """Load cache retention policy so endpoint no-repeat follows user retention settings."""
        default_hours = 48.0
        try:
            settings_path = os.path.join(self.data_dir, 'settings.json')
            if not os.path.exists(settings_path):
                return default_hours
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            cache_cfg = settings.get('cache', {}) if isinstance(settings, dict) else {}
            retention_text = cache_cfg.get('cache_retention', f'{int(default_hours)} hours')
            retention_hours = self._parse_duration_to_hours(retention_text, default_hours)
            custom_days = cache_cfg.get('cache_retention_custom_days')
            if custom_days not in (None, ''):
                try:
                    retention_hours = max(retention_hours, float(custom_days) * 24.0)
                except Exception:
                    pass
            retention_hours = max(12.0, min(retention_hours, 24.0 * 365.0))
            return retention_hours
        except Exception:
            return default_hours

    def _apply_external_rate_limit_policy(self):
        """
        Merge optional per-API free-tier policy file into api_configs.
        Supports:
        - max_calls/window_seconds (windowed limiter)
        - cooldown_seconds
        - max_retries, retry_delay, timeout
        - non_blocking_rate_limit, max_blocking_wait
        """
        if not os.path.exists(self.rate_limit_policy_file):
            return
        try:
            with open(self.rate_limit_policy_file, 'r') as f:
                payload = json.load(f)
            policies = payload.get('apis', {}) if isinstance(payload, dict) else {}
            if not isinstance(policies, dict):
                return
            for api_name, cfg in policies.items():
                if not isinstance(cfg, dict):
                    continue
                target = self.api_configs.setdefault(str(api_name), {})
                max_calls = cfg.get('max_calls')
                window_seconds = cfg.get('window_seconds')
                cooldown_seconds = cfg.get('cooldown_seconds')
                if isinstance(max_calls, (int, float)) and max_calls > 0:
                    target['rate_limit'] = float(max_calls)
                if isinstance(window_seconds, (int, float)) and window_seconds > 0:
                    target['window_seconds'] = float(window_seconds)
                if isinstance(cooldown_seconds, (int, float)) and cooldown_seconds >= 0:
                    target['cooldown'] = float(cooldown_seconds)
                for key in ('retry_delay', 'max_retries', 'timeout', 'max_backoff', 'jitter_ratio', 'max_blocking_wait'):
                    value = cfg.get(key)
                    if isinstance(value, (int, float)) and value >= 0:
                        target[key] = value
                for bool_key in ('non_blocking_rate_limit',):
                    if bool_key in cfg:
                        target[bool_key] = bool(cfg.get(bool_key))
        except Exception as e:
            print(f"⚠️ Error loading external API rate-limit policy: {e}")

    def _migrate_legacy_state_files(self):
        """Move legacy state files from data/ into data/api_runtime/ once."""
        try:
            mapping = [
                (self._legacy_files.get('errors'), self.error_log_file),
                (self._legacy_files.get('rate_limits'), self.rate_limit_file),
                (self._legacy_files.get('fallbacks'), self.fallback_data_file),
            ]
            for src, dst in mapping:
                if not src or not dst:
                    continue
                if os.path.exists(dst):
                    continue
                if os.path.exists(src):
                    os.replace(src, dst)
        except Exception:
            # Non-fatal; handler can still operate with empty state files.
            pass

    def _get_thread_session(self) -> requests.Session:
        """Reuse one HTTP session per thread to reduce connection setup overhead."""
        session = getattr(self._thread_local, 'session', None)
        if session is not None:
            return session
        session = requests.Session()
        retry_strategy = Retry(total=0, connect=0, read=0, redirect=0, status=0)
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=32, pool_maxsize=64)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        self._thread_local.session = session
        return session

    def _should_persist(self, key: str, force: bool = False) -> bool:
        """Throttle state file writes to reduce synchronous I/O overhead."""
        if force:
            return True
        now_ts = time.time()
        last_ts = float(self._last_persist_ts.get(key, 0.0) or 0.0)
        interval = float(self._persist_interval_sec.get(key, 5.0) or 5.0)
        if (now_ts - last_ts) < interval:
            return False
        self._last_persist_ts[key] = now_ts
        return True
    
    def _load_error_history(self) -> Dict[str, Any]:
        """Load error history from file"""
        try:
            if os.path.exists(self.error_log_file):
                with open(self.error_log_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading error history: {e}")
        return {'errors': [], 'stats': {}}
    
    def _load_rate_limits(self) -> Dict[str, Any]:
        """Load rate limit data from file"""
        try:
            if os.path.exists(self.rate_limit_file):
                with open(self.rate_limit_file, 'r') as f:
                    payload = json.load(f)
                return self._sanitize_loaded_rate_limits(payload)
        except Exception as e:
            print(f"⚠️ Error loading rate limits: {e}")
        return {}

    def _effective_window_seconds(self, api_name: str, api_config: Dict[str, Any]) -> float:
        """Return bounded rate-limit window to avoid pathological waits from stale policy values."""
        try:
            configured = float(api_config.get('window_seconds', 60) or 60)
        except Exception:
            configured = 60.0
        configured = max(1.0, configured)
        cap = self._chainabuse_window_cap_seconds if api_name == 'chainabuse' else self._max_window_seconds
        return max(1.0, min(configured, cap))

    def _sanitize_cooldown_seconds(self, api_name: str, seconds: float) -> float:
        """Clamp cooldown values to sane per-API limits."""
        try:
            raw_seconds = float(seconds or 0.0)
        except Exception:
            raw_seconds = 0.0
        if raw_seconds <= 0:
            return 0.0
        cap = self._chainabuse_max_cooldown_seconds if api_name == 'chainabuse' else self._max_cooldown_seconds
        return max(0.0, min(raw_seconds, cap))

    def _sanitize_loaded_rate_limits(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize persisted rate-limit state and clamp stale cooldowns."""
        if not isinstance(payload, dict):
            return {}
        now_ts = time.time()
        sanitized: Dict[str, Any] = {}
        for api_name, rate_blob in payload.items():
            api_key = str(api_name or '').strip().lower()
            if not api_key or not isinstance(rate_blob, dict):
                continue
            api_cfg = (getattr(self, 'api_configs', {}) or {}).get(api_key, {})
            window_seconds = self._effective_window_seconds(api_key, api_cfg)
            try:
                max_calls = int(float(api_cfg.get('rate_limit', 30) or 30))
            except Exception:
                max_calls = 30
            max_calls = max(1, min(max_calls, 1000))

            cleaned_calls: List[float] = []
            for raw_ts in rate_blob.get('calls', []):
                try:
                    ts_val = float(raw_ts)
                except Exception:
                    continue
                if ts_val <= 0 or ts_val > (now_ts + 5):
                    continue
                if (now_ts - ts_val) <= window_seconds:
                    cleaned_calls.append(ts_val)
            if len(cleaned_calls) > max_calls:
                cleaned_calls = cleaned_calls[-max_calls:]

            cooldown_until = 0.0
            try:
                cooldown_until = float(rate_blob.get('cooldown_until', 0) or 0)
            except Exception:
                cooldown_until = 0.0
            if cooldown_until > now_ts:
                remaining = cooldown_until - now_ts
                remaining = self._sanitize_cooldown_seconds(api_key, remaining)
                cooldown_until = now_ts + remaining if remaining > 0 else 0.0
            else:
                cooldown_until = 0.0

            entry: Dict[str, Any] = {'calls': cleaned_calls}
            if cooldown_until > now_ts:
                entry['cooldown_until'] = cooldown_until
            sanitized[api_key] = entry
        return sanitized
    
    def _load_fallback_data(self) -> Dict[str, Any]:
        """Load fallback data from file"""
        try:
            if os.path.exists(self.fallback_data_file):
                file_size = os.path.getsize(self.fallback_data_file)
                if file_size > self._max_fallback_file_bytes:
                    oversize_backup = f"{self.fallback_data_file}.oversize.{int(time.time())}"
                    os.replace(self.fallback_data_file, oversize_backup)
                    print(
                        f"⚠️ API fallback cache oversized ({file_size / (1024 * 1024):.1f} MB), "
                        "rotating to keep runtime responsive"
                    )
                    return {}
                with open(self.fallback_data_file, 'r') as f:
                    payload = json.load(f)
                payload = self._prune_loaded_fallback_data(payload)
                return payload
        except Exception as e:
            print(f"⚠️ Error loading fallback data: {e}")
            # Recover from a corrupted fallback cache file to prevent repeated startup noise.
            try:
                if os.path.exists(self.fallback_data_file):
                    corrupt_backup = f"{self.fallback_data_file}.corrupt.{int(time.time())}"
                    os.replace(self.fallback_data_file, corrupt_backup)
                with open(self.fallback_data_file, 'w') as f:
                    json.dump({}, f)
            except Exception:
                pass
        return {}

    def _prune_loaded_fallback_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Prune stale/oversized API fallback payloads loaded from disk."""
        if not isinstance(payload, dict):
            return {}
        cutoff_ts = time.time() - (self._fallback_retention_hours * 3600.0)

        def _ts(entry: Dict[str, Any]) -> float:
            try:
                raw_ts = entry.get('timestamp')
                if isinstance(raw_ts, (int, float)):
                    return float(raw_ts)
                if isinstance(raw_ts, str) and raw_ts:
                    return datetime.fromisoformat(raw_ts).timestamp()
            except Exception:
                pass
            return 0.0

        pruned: Dict[str, Any] = {}
        changed = False
        for api_name, endpoint_map in payload.items():
            if not isinstance(endpoint_map, dict):
                continue
            entries = []
            for endpoint, blob in endpoint_map.items():
                if not isinstance(blob, dict):
                    changed = True
                    continue
                ts_val = _ts(blob)
                if ts_val > 0 and ts_val < cutoff_ts:
                    changed = True
                    continue
                entries.append((ts_val, endpoint, blob))

            entries.sort(key=lambda item: item[0], reverse=True)
            if len(entries) > self._max_fallback_entries_per_api:
                changed = True
            kept = entries[:self._max_fallback_entries_per_api]
            if kept:
                pruned[api_name] = {endpoint: blob for _, endpoint, blob in kept}

        if changed:
            self.fallback_data = pruned
            self._persist_fallback_data(force=True)
        return pruned
    
    def _save_error_history(self, force: bool = False):
        """Save error history to file"""
        if not self._should_persist('errors', force=force):
            return
        try:
            with self._state_lock:
                payload = copy.deepcopy(self.error_history)
            self._atomic_write_json(self.error_log_file, payload)
        except Exception as e:
            print(f"⚠️ Error saving error history: {e}")
    
    def _save_rate_limits(self, force: bool = False):
        """Save rate limit data to file"""
        if not self._should_persist('rate_limits', force=force):
            return
        try:
            with self._state_lock:
                payload = copy.deepcopy(self.rate_limits)
            self._atomic_write_json(self.rate_limit_file, payload)
        except Exception as e:
            print(f"⚠️ Error saving rate limits: {e}")
    
    def _persist_fallback_data(self, force: bool = False):
        """Persist fallback data dictionary to file"""
        if not self._should_persist('fallbacks', force=force):
            return
        try:
            with self._state_lock:
                payload = copy.deepcopy(self.fallback_data)
            self._atomic_write_json(self.fallback_data_file, payload)
        except Exception as e:
            print(f"⚠️ Error saving fallback data: {e}")

    def _flush_state(self):
        """Best-effort flush of in-memory state to disk."""
        try:
            self._save_rate_limits(force=True)
            self._save_error_history(force=True)
            self._persist_fallback_data(force=True)
        except Exception:
            pass

    def _atomic_write_json(self, path: str, payload: Dict[str, Any]):
        """Atomically write JSON to disk to avoid partial/corrupted files."""
        directory = os.path.dirname(path) or '.'
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=f"{os.path.basename(path)}.tmp.", dir=directory)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise
    
    def _identify_api(self, url: str) -> str:
        """Identify which API the URL belongs to"""
        try:
            host = urlparse(url).netloc.lower()
            # Fast host-based mappings first to avoid "unknown" retry labels.
            host_map = {
                'api.arkm.com': 'arkham',
                'api.intel.arkm.com': 'arkham',
                'api.breadcrumbs.app': 'breadcrumbs',
                'api.breadcrumbs.one': 'breadcrumbs',
                'api.chainabuse.com': 'chainabuse',
                'api.santiment.net': 'santiment',
                'api.ethplorer.io': 'ethplorer',
                'deep-index.moralis.io': 'moralis',
                'public.zapper.xyz': 'zapper',
                'pro-openapi.debank.com': 'debank',
                'api.etherscan.io': 'etherscan',
                'api.bscscan.com': 'etherscan',
                'api.1inch.com': '1inch',
                'api.1inch.dev': '1inch',
                'api.llama.fi': 'defillama',
                'coins.llama.fi': 'defillama',
                'yields.llama.fi': 'defillama',
                'graphql.bitquery.io': 'bitquery',
                'www.coindesk.com': 'coindesk',
                'www.theblock.co': 'theblock',
                'decrypt.co': 'decrypt',
                'cointelegraph.com': 'cointelegraph',
                'www.reddit.com': 'reddit',
                'oauth.reddit.com': 'reddit',
                'discord.com': 'discord',
                'api.telegram.org': 'telegram',
                'bitcointalk.org': 'bitcointalk',
                'dev-api.vespia.io': 'vespia',
                'api.scorechain.com': 'scorechain',
                'api.trmlabs.com': 'trm_labs',
                'api.sanctions.trmlabs.com': 'trm_labs',
                'api.opensanctions.org': 'opensanctions',
                'api.lukka.tech': 'lukka',
                'api.defisafety.com': 'defisafety',
                'api.certik.com': 'certik',
                'api.dune.com': 'dune',
                'api.sim.dune.com': 'dune',
            }
            if host in host_map:
                return host_map[host]
            for known_host, name in host_map.items():
                if known_host in host:
                    return name
        except Exception:
            pass

        for api_name, config in self.api_configs.items():
            if config['base_url'] in url:
                return api_name
        return 'unknown'

    def _acquire_api_concurrency_slot(self, api_name: str, blocking: bool = True, timeout_seconds: Optional[float] = None):
        """Acquire a shared concurrency slot for APIs with global caps."""
        key = str(api_name or '').strip().lower()
        semaphore = self.api_concurrency_semaphores.get(key)
        if semaphore is None:
            return None
        start_ts = time.time()
        acquired = False
        if not blocking:
            acquired = semaphore.acquire(blocking=False)
        elif timeout_seconds is not None:
            try:
                acquired = semaphore.acquire(timeout=max(0.0, float(timeout_seconds)))
            except Exception:
                acquired = semaphore.acquire()
        else:
            acquired = semaphore.acquire()
        if not acquired:
            return False
        waited = time.time() - start_ts
        if waited > 1.0:
            print(f"    ⏳ Waiting {waited:.2f}s for {key} concurrency slot...")
        return semaphore

    def _release_api_concurrency_slot(self, semaphore):
        """Release API concurrency slot."""
        if semaphore is None:
            return
        try:
            semaphore.release()
        except Exception:
            pass
    
    def _categorize_error(self, error_msg: str, status_code: Optional[int] = None) -> str:
        """Categorize error based on message and status code"""
        error_lower = error_msg.lower()
        
        if status_code:
            status_str = str(status_code)
            for category, patterns in self.error_categories.items():
                if status_str in patterns:
                    return category
        
        for category, patterns in self.error_categories.items():
            for pattern in patterns:
                if pattern in error_lower:
                    return category
        
        return 'unknown'
    
    def _check_rate_limit(self, api_name: str) -> bool:
        """Check if we're within rate limits for an API"""
        if api_name not in self.api_configs:
            return True

        current_time = time.time()
        api_config = self.api_configs[api_name]
        window_seconds = self._effective_window_seconds(api_name, api_config)
        try:
            max_calls = float(api_config.get('rate_limit', 30) or 30)
        except Exception:
            max_calls = 30.0
        with self._state_lock:
            if api_name not in self.rate_limits:
                self.rate_limits[api_name] = {'calls': [], 'last_reset': current_time}

            rate_data = self.rate_limits[api_name]
            cooldown_until = float(rate_data.get('cooldown_until', 0) or 0)
            if cooldown_until > current_time:
                return False
            if cooldown_until:
                rate_data.pop('cooldown_until', None)

            # Clean old calls (windowed, API-specific).
            rate_data['calls'] = [call_time for call_time in rate_data['calls']
                                  if current_time - call_time < window_seconds]

            # Check if we're within limits
            if len(rate_data['calls']) >= max_calls:
                return False

            # Add current call
            rate_data['calls'].append(current_time)
        self._save_rate_limits(force=False)
        return True
    
    def _wait_for_rate_limit(self, api_name: str):
        """Wait if we've hit rate limits"""
        if api_name not in self.api_configs:
            return

        api_config = self.api_configs[api_name]
        current_time = time.time()
        window_seconds = self._effective_window_seconds(api_name, api_config)
        try:
            max_calls = float(api_config.get('rate_limit', 30) or 30)
        except Exception:
            max_calls = 30.0

        wait_time = 0
        with self._state_lock:
            if api_name in self.rate_limits:
                rate_data = self.rate_limits[api_name]
                cooldown_until = float(rate_data.get('cooldown_until', 0) or 0)
                if cooldown_until > current_time:
                    wait_time = max(wait_time, cooldown_until - current_time)
                rate_data['calls'] = [call_time for call_time in rate_data['calls']
                                      if current_time - call_time < window_seconds]

                if len(rate_data['calls']) >= max_calls:
                    wait_time = window_seconds - (current_time - rate_data['calls'][0])
        # Avoid noisy sub-100ms waits being rendered as "0.0s".
        if wait_time > 0.05:
            print(f"    ⏰ Rate limit hit for {api_name}, waiting {wait_time:.2f}s...")
            time.sleep(wait_time)

    def _peek_rate_limit_wait(self, api_name: str) -> float:
        """Return estimated seconds to wait for current API rate-limit window/cooldown."""
        if api_name not in self.api_configs:
            return 0.0

        api_config = self.api_configs[api_name]
        current_time = time.time()
        window_seconds = self._effective_window_seconds(api_name, api_config)
        try:
            max_calls = float(api_config.get('rate_limit', 30) or 30)
        except Exception:
            max_calls = 30.0
        wait_time = 0.0
        with self._state_lock:
            if api_name in self.rate_limits:
                rate_data = self.rate_limits[api_name]
                cooldown_until = float(rate_data.get('cooldown_until', 0) or 0)
                if cooldown_until > current_time:
                    wait_time = max(wait_time, cooldown_until - current_time)

                recent_calls = [
                    call_time for call_time in rate_data.get('calls', [])
                    if current_time - call_time < window_seconds
                ]
                if len(recent_calls) >= max_calls:
                    wait_time = max(wait_time, window_seconds - (current_time - recent_calls[0]))
        if wait_time <= 0.05:
            return 0.0
        return max(0.0, wait_time)

    def _make_rate_limited_response(self, url: str, retry_after_seconds: float = 0.0) -> requests.Response:
        """Build a synthetic HTTP 429 response for non-blocking rate-limit paths."""
        response = requests.Response()
        response.status_code = 429
        response.reason = 'Too Many Requests'
        response.url = str(url)
        if retry_after_seconds and retry_after_seconds > 0:
            response.headers['Retry-After'] = str(int(max(1, round(retry_after_seconds))))
        response._content = b''
        return response

    def _parse_retry_after_seconds(self, response: Optional[requests.Response]) -> float:
        """Parse Retry-After header seconds (supports integer seconds and HTTP-date)."""
        try:
            if response is None:
                return 0.0
            retry_after = response.headers.get('Retry-After')
            if retry_after is None:
                return 0.0
            retry_after = str(retry_after).strip()
            if not retry_after:
                return 0.0
            try:
                seconds = float(retry_after)
                return max(0.0, min(seconds, self._max_retry_after_seconds))
            except ValueError:
                dt = parsedate_to_datetime(retry_after)
                if dt is None:
                    return 0.0
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                seconds = max(0.0, (dt - now).total_seconds())
                return min(seconds, self._max_retry_after_seconds)
        except Exception:
            return 0.0

    def _set_cooldown(self, api_name: str, seconds: float):
        """Set/extend a temporary cooldown for an API."""
        seconds = self._sanitize_cooldown_seconds(api_name, seconds)
        if seconds <= 0:
            return
        now_ts = time.time()
        with self._state_lock:
            if api_name not in self.rate_limits:
                self.rate_limits[api_name] = {'calls': [], 'last_reset': now_ts}
            rate_data = self.rate_limits[api_name]
            current_until = float(rate_data.get('cooldown_until', 0) or 0)
            new_until = now_ts + float(seconds)
            if new_until > current_until:
                rate_data['cooldown_until'] = new_until
        self._save_rate_limits(force=True)

    def _chainabuse_backoff_delay(self, attempt: int, api_config: Dict[str, Any], retry_after: float = 0.0) -> float:
        """Compute exponential backoff + jitter delay for Chainabuse retries."""
        base = float(api_config.get('retry_delay', 2) or 2)
        max_backoff = float(api_config.get('max_backoff', 120) or 120)
        max_backoff = min(max_backoff, self._chainabuse_max_cooldown_seconds)
        jitter_ratio = float(api_config.get('jitter_ratio', 0.35) or 0.35)
        expo = min(max_backoff, base * (2 ** max(0, int(attempt))))
        jitter = random.uniform(0.0, max(0.0, expo * jitter_ratio))
        delay = expo + jitter
        if retry_after > 0:
            delay = max(delay, retry_after)
        return min(max_backoff, delay)
    
    def _log_error(self, api_name: str, url: str, error_msg: str, status_code: Optional[int] = None):
        """Log error for analysis"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'api_name': api_name,
            'url': url,
            'error': error_msg,
            'status_code': status_code,
            'category': self._categorize_error(error_msg, status_code)
        }
        
        with self._state_lock:
            self.error_history['errors'].append(error_entry)

            # Update stats
            if api_name not in self.error_history['stats']:
                self.error_history['stats'][api_name] = {'total_errors': 0, 'categories': {}}

            stats = self.error_history['stats'][api_name]
            stats['total_errors'] += 1

            category = error_entry['category']
            if category not in stats['categories']:
                stats['categories'][category] = 0
            stats['categories'][category] += 1
        
        self._save_error_history(force=False)
    
    def _get_fallback_data(self, api_name: str, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get fallback data for an API endpoint"""
        try:
            with self._state_lock:
                if api_name in self.fallback_data:
                    return self.fallback_data[api_name].get(endpoint)
        except Exception as e:
            print(f"⚠️ Error getting fallback data: {e}")
        return None

    def _build_fallback_endpoint_key(self, url: str, **kwargs) -> str:
        """Build a stable fallback key that preserves token/address-specific query context."""
        try:
            parsed = urlparse(url)
            path = parsed.path or '/'
            query_pairs = []

            # Include URL query params.
            query_pairs.extend(parse_qsl(parsed.query or '', keep_blank_values=True))

            # Include request params passed separately.
            params = kwargs.get('params')
            if isinstance(params, dict):
                for key in sorted(params.keys()):
                    value = params.get(key)
                    if isinstance(value, (list, tuple)):
                        for item in value:
                            query_pairs.append((str(key), str(item)))
                    elif value is not None:
                        query_pairs.append((str(key), str(value)))
            elif isinstance(params, (list, tuple)):
                for item in params:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        query_pairs.append((str(item[0]), str(item[1])))

            # For POST/JSON endpoints, include payload identity keys that commonly carry token scope.
            body = kwargs.get('json')
            if isinstance(body, dict):
                for key in ('address', 'token_address', 'contract', 'contract_address', 'chain', 'chain_id'):
                    if key in body and body.get(key) is not None:
                        query_pairs.append((key, str(body.get(key))))

            if query_pairs:
                query_pairs_sorted = sorted((str(k), str(v)) for k, v in query_pairs)
                return f"{path}?{urlencode(query_pairs_sorted, doseq=True)}"
            return path
        except Exception:
            return url.split('/')[-1] if '/' in url else 'default'
    
    def _save_fallback_data(self, api_name: str, endpoint: str, data: Dict[str, Any]):
        """Save data as fallback for future use"""
        try:
            serialized = json.dumps(data, sort_keys=True, default=str)
            if len(serialized) > self._max_fallback_payload_chars:
                return
            payload_hash = hashlib.sha1(serialized.encode('utf-8')).hexdigest()
            with self._state_lock:
                if api_name not in self.fallback_data:
                    self.fallback_data[api_name] = {}

                existing = self.fallback_data[api_name].get(endpoint, {})
                if isinstance(existing, dict) and existing.get('hash') == payload_hash:
                    return

                self.fallback_data[api_name][endpoint] = {
                    'data': data,
                    'timestamp': datetime.now().isoformat(),
                    'hash': payload_hash
                }
                if len(self.fallback_data[api_name]) > self._max_fallback_entries_per_api:
                    sortable = []
                    for ep_key, ep_blob in self.fallback_data[api_name].items():
                        ts_val = 0.0
                        try:
                            raw_ts = ep_blob.get('timestamp') if isinstance(ep_blob, dict) else None
                            if isinstance(raw_ts, (int, float)):
                                ts_val = float(raw_ts)
                            elif isinstance(raw_ts, str) and raw_ts:
                                ts_val = datetime.fromisoformat(raw_ts).timestamp()
                        except Exception:
                            ts_val = 0.0
                        sortable.append((ts_val, ep_key, ep_blob))
                    sortable.sort(key=lambda item: item[0], reverse=True)
                    self.fallback_data[api_name] = {
                        ep_key: ep_blob
                        for _, ep_key, ep_blob in sortable[:self._max_fallback_entries_per_api]
                    }
            self._persist_fallback_data(force=False)
        except Exception as e:
            print(f"⚠️ Error saving fallback data: {e}")

    def _fallback_entry_age_hours(self, entry: Dict[str, Any]) -> Optional[float]:
        """Return fallback entry age in hours."""
        if not isinstance(entry, dict):
            return None
        try:
            ts_raw = entry.get('timestamp')
            ts_val = None
            if isinstance(ts_raw, (int, float)):
                ts_val = float(ts_raw)
            elif isinstance(ts_raw, str) and ts_raw:
                ts_val = datetime.fromisoformat(ts_raw).timestamp()
            if not ts_val or ts_val <= 0:
                return None
            return max(0.0, (time.time() - ts_val) / 3600.0)
        except Exception:
            return None

    def _fallback_has_signal(self, data: Any) -> bool:
        """Return True when cached payload contains meaningful token-specific signal."""
        if data is None:
            return False
        if isinstance(data, dict):
            if not data:
                return False
            if data.get('error') or data.get('skipped') or data.get('placeholder'):
                return False
            for value in data.values():
                if isinstance(value, bool) and value:
                    return True
                if isinstance(value, (int, float)) and value > 0:
                    return True
                if isinstance(value, str) and value.strip() and value.strip().lower() not in {'neutral', 'unknown', 'n/a'}:
                    return True
                if isinstance(value, list) and value:
                    return True
                if isinstance(value, dict) and value:
                    return True
            return False
        if isinstance(data, list):
            return len(data) > 0
        if isinstance(data, (int, float)):
            return float(data) > 0
        if isinstance(data, str):
            return bool(data.strip())
        return bool(data)

    def _make_cached_response(self, data: Any) -> requests.Response:
        """Create response-like object carrying cached JSON payload."""
        class MockResponse:
            def __init__(self, payload):
                self.status_code = 200
                self.reason = 'OK'
                self._data = payload
                self.headers = {'X-Fallback-Cache': 'hit'}

            def json(self):
                return self._data

        return cast(requests.Response, MockResponse(data))
    
    def make_request(self, method: str, url: str, api_name: Optional[str] = None, 
                    fallback_func: Optional[Callable[[], requests.Response]] = None, **kwargs) -> Optional[requests.Response]:
        """
        Make an API request with intelligent error handling and fallbacks
        
        Args:
            method: HTTP method
            url: Request URL
            api_name: API name for rate limiting (auto-detected if None)
            fallback_func: Function to call if request fails
            **kwargs: Additional request parameters
        """
        if api_name is None:
            api_name = self._identify_api(url)
        force_live = bool(kwargs.pop('force_live', False))
        method_upper = str(method or 'GET').upper().strip()

        # Get API configuration
        api_config = self.api_configs.get(api_name, {
            'retry_delay': 1,
            'max_retries': 3,
            'timeout': 10
        })
        non_blocking_rate_limit = bool(api_config.get('non_blocking_rate_limit', False))
        try:
            max_blocking_wait = float(
                api_config.get('max_blocking_wait', os.getenv('API_RATE_LIMIT_MAX_BLOCKING_SECONDS', '3')) or 3
            )
        except Exception:
            max_blocking_wait = 3.0

        # Per-endpoint no-repeat: if this token-specific endpoint already has a fresh,
        # meaningful fallback payload inside retention, reuse it and skip live call.
        endpoint_key = self._build_fallback_endpoint_key(url, **kwargs)
        if method_upper == 'GET' and not force_live and api_name:
            try:
                cached_entry = self._get_fallback_data(api_name, endpoint_key)
                if cached_entry:
                    age_h = self._fallback_entry_age_hours(cached_entry)
                    cached_data = cached_entry.get('data') if isinstance(cached_entry, dict) else None
                    if (
                        age_h is not None
                        and age_h <= self._cache_retention_hours
                        and self._fallback_has_signal(cached_data)
                    ):
                        return self._make_cached_response(cached_data)
            except Exception:
                pass

        # Check rate limits
        if not self._check_rate_limit(api_name):
            estimated_wait = self._peek_rate_limit_wait(api_name)
            if non_blocking_rate_limit or estimated_wait > max_blocking_wait:
                self._log_error(api_name, url, "Rate limit cooldown active", 429)
                print(
                    f"    ⏭️  {api_name} rate-limited ({estimated_wait:.1f}s remaining), "
                    "skipping blocking wait"
                )
                return self._make_rate_limited_response(url, estimated_wait)
            self._wait_for_rate_limit(api_name)

        
        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = api_config['timeout']
        try:
            configured_retries = int(api_config.get('max_retries', 2) or 2)
        except Exception:
            configured_retries = 2
        configured_retries = max(0, configured_retries)
        # Hard cap: maximum 3 attempts total (initial attempt + retries).
        max_attempts = min(3, configured_retries + 1)
        
        # Reuse one per-thread session instead of creating a new one per request.
        session = self._get_thread_session()
        last_response: Optional[requests.Response] = None
        
        # Make request
        for attempt in range(max_attempts):
            try:
                slot = self._acquire_api_concurrency_slot(
                    api_name,
                    blocking=not non_blocking_rate_limit,
                    timeout_seconds=max_blocking_wait if not non_blocking_rate_limit else 0
                )
                if slot is False:
                    print(f"    ⏭️  {api_name} concurrency slot busy, skipping blocking wait")
                    return self._make_rate_limited_response(url, retry_after_seconds=1.0)
                try:
                    response = session.request(method, url, **kwargs)
                finally:
                    self._release_api_concurrency_slot(slot)
                last_response = response
                
                # Check for success
                if response.status_code == 200:
                    # Save successful response as fallback data
                    if method_upper == 'GET':
                        try:
                            self._save_fallback_data(api_name, endpoint_key, response.json())
                        except:
                            pass
                    return response
                
                # Handle specific error codes
                if response.status_code == 429:
                    self._log_error(api_name, url, f"Rate limit exceeded", response.status_code)
                    retry_after = self._parse_retry_after_seconds(response)
                    if api_name == 'chainabuse':
                        wait_time = self._chainabuse_backoff_delay(attempt, api_config, retry_after)
                        cooldown_floor = float(api_config.get('cooldown', 0) or 0)
                        self._set_cooldown(api_name, max(wait_time, cooldown_floor))
                        if non_blocking_rate_limit or wait_time > max_blocking_wait:
                            print(
                                f"    ⏭️  Chainabuse rate-limited, cooldown {wait_time:.2f}s "
                                f"(attempt {attempt + 1}/{max_attempts})"
                            )
                            return response
                        print(
                            f"    ⏰ Chainabuse rate limit hit, waiting {wait_time:.2f}s "
                            f"(attempt {attempt + 1}/{max_attempts})"
                        )
                    else:
                        wait_time = api_config['retry_delay'] * (2 ** attempt)
                        wait_time = max(wait_time, retry_after) if retry_after > 0 else wait_time
                        cooldown_floor = float(api_config.get('cooldown', 0) or 0)
                        self._set_cooldown(api_name, max(wait_time, cooldown_floor))
                        wait_time = max(wait_time, cooldown_floor)
                        if non_blocking_rate_limit or wait_time > max_blocking_wait:
                            print(
                                f"    ⏭️  {api_name} rate-limited, cooldown {wait_time:.2f}s "
                                f"(attempt {attempt + 1}/{max_attempts})"
                            )
                            return response
                        print(f"    ⏰ Rate limit hit for {api_name}, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                elif response.status_code in [401, 403]:
                    # Some free/public APIs (e.g. DeFiLlama) may emit 403 for anti-bot
                    # filtering and not because credentials are invalid.
                    if response.status_code == 403 and str(api_name or '').strip().lower() in {'defillama'}:
                        self._log_error(api_name, url, f"Access temporarily unavailable: {response.status_code}", response.status_code)
                        print(f"    ⚠️ {api_name} temporarily unavailable ({response.status_code})")
                        break
                    self._log_error(api_name, url, f"Authentication error: {response.status_code}", response.status_code)
                    print(f"    ❌ Authentication error for {api_name}: {response.status_code}")
                    break
                
                elif response.status_code == 404:
                    self._log_error(api_name, url, f"Not found: {response.status_code}", response.status_code)
                    print(f"    ⚠️ Not found for {api_name}: {response.status_code}")
                    break
                
                elif 400 <= response.status_code < 500:
                    # Client-side request errors are deterministic; don't retry.
                    self._log_error(api_name, url, f"HTTP {response.status_code}: {response.reason}", response.status_code)
                    break
                
                else:
                    self._log_error(api_name, url, f"HTTP {response.status_code}: {response.reason}", response.status_code)
                    if attempt < max_attempts - 1:
                        wait_time = api_config['retry_delay'] * (2 ** attempt)
                        print(f"    ⚠️ Retrying {api_name} in {wait_time}s... (attempt {attempt + 1}/{max_attempts})")
                        time.sleep(wait_time)
                        continue
                    break
                
            except requests.exceptions.RequestException as e:
                self._log_error(api_name, url, str(e))
                if attempt < max_attempts - 1:
                    wait_time = api_config['retry_delay'] * (2 ** attempt)
                    print(f"    ⚠️ Network error for {api_name}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                break
        
        # Try fallback function if provided
        if fallback_func:
            try:
                print(f"    🔄 Trying fallback for {api_name}...")
                return fallback_func()
            except Exception as e:
                print(f"    ❌ Fallback failed for {api_name}: {e}")
        
        # Try cached fallback data
        if method_upper == 'GET':
            try:
                fallback_data = self._get_fallback_data(api_name, endpoint_key)
                # Legacy endpoint-only fallback keys were not token-specific and can
                # leak market/on-chain values across tokens. Keep them only for
                # static content feeds where URL path identity is sufficient.
                legacy_safe_apis = {'coindesk', 'theblock', 'decrypt', 'cointelegraph', 'bitcointalk'}
                if not fallback_data and api_name in legacy_safe_apis:
                    legacy_endpoint = url.split('/')[-1] if '/' in url else 'default'
                    fallback_data = self._get_fallback_data(api_name, legacy_endpoint)
                if fallback_data:
                    print(f"    🔄 Using cached fallback data for {api_name}")
                    return self._make_cached_response(fallback_data['data'])
            except Exception as e:
                print(f"    ⚠️ Error using fallback data: {e}")
        
        # Opportunistically flush throttled state at request boundary.
        self._save_rate_limits(force=False)
        self._save_error_history(force=False)
        self._persist_fallback_data(force=False)

        # Return the last HTTP response when available so callers can surface real status codes.
        if last_response is not None:
            return last_response

        return None
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            'total_errors': len(self.error_history['errors']),
            'api_stats': self.error_history['stats'],
            'recent_errors': self.error_history['errors'][-10:] if self.error_history['errors'] else []
        }
    
    def clear_error_history(self):
        """Clear error history"""
        self.error_history = {'errors': [], 'stats': {}}
        self._save_error_history()
        print("✅ Error history cleared")

# Global error handler instance
_error_handler = None

def get_error_handler(data_dir: Optional[str] = None) -> APIErrorHandler:
    """Get or create global error handler instance"""
    global _error_handler
    
    if _error_handler is None:
        if data_dir is None:
            # Default data directory
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            data_dir = os.path.join(project_root, 'data')
        
        _error_handler = APIErrorHandler(data_dir)
    
    return _error_handler
