#!/usr/bin/env python3
"""
Enhanced Cache Manager for DeFi Risk Assessment
Implements intelligent caching with fallback data preservation and automatic cache refresh
"""

import os
import json
import time
import threading
import copy
import tempfile
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import requests

try:
    from dotenv import load_dotenv
    _DEFAULT_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    if os.path.exists(_DEFAULT_ENV_PATH):
        load_dotenv(_DEFAULT_ENV_PATH)
except Exception:
    pass

WEBHOOK_BASE_URL = str(os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5001')).strip().rstrip('/')
WEBHOOK_SHARED_SECRET = str(os.getenv('WEBHOOK_SHARED_SECRET', '')).strip()


def _webhook_headers(payload_bytes: bytes = b'', *, include_signature: bool = False) -> dict[str, str]:
    headers = {'Content-Type': 'application/json'}
    if not WEBHOOK_SHARED_SECRET:
        return headers

    headers['Authorization'] = f'Bearer {WEBHOOK_SHARED_SECRET}'
    if include_signature:
        timestamp = str(int(time.time()))
        signed_payload = f'{timestamp}.'.encode('utf-8') + (payload_bytes or b'')
        signature = hmac.new(
            WEBHOOK_SHARED_SECRET.encode('utf-8'),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        headers['X-Webhook-Timestamp'] = timestamp
        headers['X-Webhook-Signature'] = f'sha256={signature}'
    return headers

class EnhancedCacheManager:
    """
    Enhanced cache manager that:
    1. Saves real-time data to fallback files
    2. Uses cached data when available and fresh
    3. Preserves old but relevant data
    4. Implements intelligent cache refresh
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._lock = threading.RLock()
        self.cache_file = os.path.join(data_dir, 'real_data_cache.json')
        self.fallback_file = os.path.join(data_dir, 'token_fallbacks.json')
        self.cache_metadata_file = os.path.join(data_dir, 'cache_metadata.json')
        self.settings_file = os.path.join(data_dir, 'settings.json')
        
        # Cache configuration
        self.cache_duration_hours = 2  # How long to consider cache fresh
        self.preserve_duration_hours = 48  # How long to preserve old data (48 hours)
        self.max_cache_size_mb = 50  # Maximum cache size in MB
        self._load_cache_policy_from_settings()
        
        # Load existing data
        self.cache_data = self._load_cache()
        self.fallback_data = self._load_fallbacks()
        self.metadata = self._load_metadata()
        
        # Start background refresh thread
        self._start_background_refresh()

    @staticmethod
    def _parse_duration_to_hours(value, default_hours=48.0) -> float:
        """Parse strings like '72 hours' or '30 days' into hours."""
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return float(default_hours)
        text = value.strip().lower()
        if not text:
            return float(default_hours)
        parts = text.split()
        try:
            amount = float(parts[0])
        except Exception:
            return float(default_hours)
        unit = parts[1] if len(parts) > 1 else 'hours'
        if unit.startswith('minute'):
            return amount / 60.0
        if unit.startswith('day'):
            return amount * 24.0
        if unit.startswith('week'):
            return amount * 24.0 * 7.0
        if unit.startswith('month'):
            return amount * 24.0 * 30.0
        if unit.startswith('year'):
            return amount * 24.0 * 365.0
        return amount

    def _load_cache_policy_from_settings(self):
        """Load cache retention policy from settings.json."""
        try:
            if not os.path.exists(self.settings_file):
                return
            with open(self.settings_file, 'r') as f:
                settings = json.load(f) or {}
            cache_cfg = settings.get('cache', {}) if isinstance(settings, dict) else {}
            retention_text = cache_cfg.get('cache_retention', f"{int(self.preserve_duration_hours)} hours")
            retention_hours = self._parse_duration_to_hours(retention_text, self.preserve_duration_hours)

            # Support explicit custom days key when the UI uses "Custom".
            custom_days = cache_cfg.get('cache_retention_custom_days')
            try:
                custom_days = int(custom_days)
            except (TypeError, ValueError):
                custom_days = None
            if custom_days is not None and custom_days > 0:
                retention_hours = max(retention_hours, float(custom_days) * 24.0)

            # Keep within practical and user-requested bounds (12h .. 365d).
            retention_hours = max(12.0, min(retention_hours, 24.0 * 365.0))
            self.preserve_duration_hours = retention_hours
            print(f"🗂️ Cache retention policy loaded: {self.preserve_duration_hours:.1f}h")
        except Exception as e:
            print(f"⚠️ Could not load cache retention settings: {e}")
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache data with error handling"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                print(f"✅ Loaded cache with {len(data.get('tokens', {}))} tokens")
                return data
        except Exception as e:
            print(f"⚠️ Error loading cache: {e}")
        
        return {'tokens': {}, 'last_updated': 0, 'metadata': {}}
    
    def _load_fallbacks(self) -> Dict[str, Any]:
        """Load fallback data with error handling"""
        try:
            if os.path.exists(self.fallback_file):
                with open(self.fallback_file, 'r') as f:
                    data = json.load(f)
                print(f"✅ Loaded fallback data with {len(data.get('token_mappings', {}))} tokens")
                return data
        except Exception as e:
            print(f"⚠️ Error loading fallback data: {e}")
        
        return {'token_mappings': {}, 'metadata': {}, 'last_updated': 0}
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata"""
        try:
            if os.path.exists(self.cache_metadata_file):
                with open(self.cache_metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading metadata: {e}")
        
        return {
            'last_refresh': 0,
            'refresh_count': 0,
            'total_data_points': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def _save_cache(self):
        """Save cache data with error handling"""
        try:
            # Ensure directory exists
            os.makedirs(self.data_dir, exist_ok=True)
            with self._lock:
                payload = copy.deepcopy(self.cache_data)
            self._atomic_write_json(self.cache_file, payload)
            print(f"✅ Cache saved with {len(payload.get('tokens', {}))} tokens")
        except Exception as e:
            print(f"❌ Error saving cache: {e}")
    
    def _save_fallbacks(self):
        """Save fallback data with error handling"""
        try:
            # Ensure directory exists
            os.makedirs(self.data_dir, exist_ok=True)
            with self._lock:
                payload = copy.deepcopy(self.fallback_data)
            self._atomic_write_json(self.fallback_file, payload)
            print(f"✅ Fallback data saved with {len(payload.get('token_mappings', {}))} tokens")
        except Exception as e:
            print(f"❌ Error saving fallback data: {e}")
    
    def _save_metadata(self):
        """Save cache metadata"""
        try:
            with self._lock:
                payload = copy.deepcopy(self.metadata)
            self._atomic_write_json(self.cache_metadata_file, payload)
        except Exception as e:
            print(f"❌ Error saving metadata: {e}")

    def _atomic_write_json(self, path: str, payload: Dict[str, Any]):
        """Write JSON atomically to avoid partial writes/corruption under concurrency."""
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
    
    def get_cached_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get cached data for a token with intelligent fallback logic
        Returns None if no fresh data is available
        """
        with self._lock:
            tokens = self.cache_data.get('tokens', {})
        
        if token_address in tokens:
            cached_data = tokens[token_address]
            timestamp = cached_data.get('timestamp', 0)
            # Ensure timestamp is numeric
            if isinstance(timestamp, str):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    timestamp = 0
            cache_age = time.time() - timestamp
            cache_age_hours = cache_age / 3600
            
            # Use cache if fresh enough and timestamp is valid (not 0)
            if timestamp > 0 and cache_age_hours < self.cache_duration_hours:
                self.metadata['cache_hits'] += 1
                print(f"    ✅ Using fresh cached data (age: {cache_age_hours:.1f}h)")
                return cached_data
            elif timestamp <= 0:
                print(f"    ⚠️ Cache has invalid timestamp (0), will fetch fresh data")
            else:
                print(f"    ⚠️ Cache too old ({cache_age_hours:.1f}h), will fetch fresh data")
        
        # Check fallback data
        with self._lock:
            fallback_tokens = self.fallback_data.get('token_mappings', {})
        if token_address in fallback_tokens:
            fallback_data = fallback_tokens[token_address]
            timestamp = fallback_data.get('timestamp', 0)
            # Ensure timestamp is numeric
            if isinstance(timestamp, str):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    timestamp = 0
            fallback_age = time.time() - timestamp
            fallback_age_hours = fallback_age / 3600
            
            # Use fallback if not too old and timestamp is valid (not 0)
            if timestamp > 0 and fallback_age_hours < self.preserve_duration_hours:
                print(f"    🔄 Using fallback data (age: {fallback_age_hours:.1f}h)")
                return fallback_data
            elif timestamp <= 0:
                print(f"    ⚠️ Fallback data has invalid timestamp (0)")
            else:
                print(f"    ⚠️ Fallback data too old ({fallback_age_hours:.1f}h)")
        
        with self._lock:
            self.metadata['cache_misses'] += 1
        return None
    
    def update_cache_with_real_time_data(self, token_address: str, real_time_data: Dict[str, Any]):
        """
        Update both cache and fallback with real-time data
        Preserves old data in fallback if it's still relevant
        """
        current_time = time.time()
        
        with self._lock:
            # Add timestamp to data
            real_time_data['timestamp'] = current_time
            real_time_data['source'] = 'real_time'
            
            # Update cache (primary storage)
            if 'tokens' not in self.cache_data:
                self.cache_data['tokens'] = {}
            
            # Preserve old cache data in fallback if it's still relevant
            if token_address in self.cache_data['tokens']:
                old_cache_data = self.cache_data['tokens'][token_address]
                timestamp = old_cache_data.get('timestamp', 0)
                # Ensure timestamp is numeric
                if isinstance(timestamp, str):
                    try:
                        timestamp = float(timestamp)
                    except (ValueError, TypeError):
                        timestamp = 0
                old_age = current_time - timestamp
                
                # If old data is still within preserve duration, move to fallback
                if old_age < self.preserve_duration_hours * 3600:
                    if 'token_mappings' not in self.fallback_data:
                        self.fallback_data['token_mappings'] = {}
                    
                    # Only preserve if we don't have newer fallback data
                    old_timestamp = old_cache_data.get('timestamp', 0)
                    if isinstance(old_timestamp, str):
                        try:
                            old_timestamp = float(old_timestamp)
                        except (ValueError, TypeError):
                            old_timestamp = 0
                    
                    fallback_timestamp = self.fallback_data['token_mappings'][token_address].get('timestamp', 0) if token_address in self.fallback_data['token_mappings'] else 0
                    if isinstance(fallback_timestamp, str):
                        try:
                            fallback_timestamp = float(fallback_timestamp)
                        except (ValueError, TypeError):
                            fallback_timestamp = 0
                    
                    if (token_address not in self.fallback_data['token_mappings'] or 
                        old_timestamp > fallback_timestamp):
                        
                        old_cache_data['source'] = 'preserved_cache'
                        self.fallback_data['token_mappings'][token_address] = old_cache_data
                        print(f"    💾 Preserved old cache data in fallback")
            
            # Update cache with new data
            self.cache_data['tokens'][token_address] = real_time_data
            self.cache_data['last_updated'] = current_time
            
            # Also update fallback with new data
            if 'token_mappings' not in self.fallback_data:
                self.fallback_data['token_mappings'] = {}
            
            self.fallback_data['token_mappings'][token_address] = real_time_data
            self.fallback_data['last_updated'] = current_time
            
            # Update metadata
            self.metadata['total_data_points'] += 1
            self.metadata['last_refresh'] = current_time
        
        # Save both files
        self._save_cache()
        self._save_fallbacks()
        self._save_metadata()
        
        print(f"    ✅ Updated cache and fallback with real-time data")
        
        # Don't trigger webhook update if we're already in a webhook context
        # This prevents circular dependencies
        # self._trigger_webhook_update(token_address)
    
    def _trigger_webhook_update(self, token_address: str):
        """Trigger webhook update for cache refresh"""
        try:
            payload = {'address': token_address, 'token_address': token_address}
            payload_bytes = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
            requests.post(
                f'{WEBHOOK_BASE_URL}/webhook/update_token',
                data=payload_bytes,
                headers=_webhook_headers(payload_bytes, include_signature=True),
                timeout=5,
            )
        except Exception as e:
            # Webhook update is optional, don't fail if it doesn't work
            pass
    
    def fetch_data_with_intelligent_cache(self, token_address: str, fetch_function) -> Optional[Dict[str, Any]]:
        """
        Fetch data with priority-based strategy:
        1. Run assessment -> API works, no rate limitation -> Obtain real-time data and use it
        2. Run assessment -> API works, rate limitation -> Get data until rate limited, then use fallback
        3. Run assessment -> API does not work -> fetch fallback data directly
        4. Background refresh -> Constantly fetch data respecting rate limits
        """
        current_time = time.time()
        
        # First, check if we have fresh cached data
        cached_data = self.get_cached_data(token_address)
        if cached_data:
            print(f"    ✅ Using fresh cached data")
            return cached_data
        
        # Check fallback data
        fallback_data = self.get_fallback_data(token_address)
        if fallback_data:
            print(f"    📦 Using fallback data")
            # Optional heuristic: if fallback data is within 48h, skip real-time API calls entirely
            if self._respect_48h_skip():
                ts = fallback_data.get('timestamp', 0)
                try:
                    ts = float(ts)
                except (ValueError, TypeError):
                    ts = 0
                if ts > 0:
                    age_h = (current_time - ts) / 3600
                    if age_h < self.preserve_duration_hours:
                        print(f"    ⏭️  Skipping real-time fetch (fallback age {age_h:.1f}h < {self.preserve_duration_hours}h)")
                        return fallback_data
        
        # Try to fetch fresh real-time data
        print(f"    🔄 Attempting to fetch fresh real-time data...")
        try:
            real_time_data = fetch_function(token_address)
            
            if real_time_data and self._has_valid_data(real_time_data):
                # Priority 1: API works, no rate limitation
                print(f"    ✅ Successfully obtained real-time data")
                self.update_cache_with_real_time_data(token_address, real_time_data)
                return real_time_data
            else:
                # Priority 3: API does not work, use fallback
                if fallback_data:
                    print(f"    ⚠️ API failed, using fallback data")
                    return fallback_data
                else:
                    print(f"    ❌ No data available from API or fallback")
                    return None
                    
        except Exception as e:
            print(f"    ❌ API error: {e}")
            # Priority 3: API does not work, use fallback
            if fallback_data:
                print(f"    📦 Using fallback data due to API error")
                return fallback_data
            else:
                print(f"    ❌ No fallback data available")
                return None

    def _respect_48h_skip(self) -> bool:
        """Determine whether to skip real-time API calls when recent data (<48h) exists."""
        # Prefer environment variable; default to true
        env_val = os.getenv('RESPECT_48H_METRIC_SKIP', '1').strip().lower()
        if env_val in ('0', 'false', 'no'):  # explicitly disabled
            return False
        if env_val in ('1', 'true', 'yes'):  # explicitly enabled
            return True
        # Try reading settings.json if present
        try:
            settings_path = os.path.join(self.data_dir, 'settings.json')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                return bool(settings.get('cache', {}).get('respect_48h_metric_skip', True))
        except Exception:
            pass
        return True
    
    def _has_valid_data(self, data: Dict[str, Any]) -> bool:
        """Check if data contains valid (non-zero) values"""
        if not data:
            return False
        
        # Check market data
        market_data = data.get('market_data', {})
        for source, source_data in market_data.items():
            if isinstance(source_data, dict):
                if (source_data.get('market_cap', 0) > 0 or 
                    source_data.get('volume_24h', 0) > 0 or 
                    source_data.get('price', 0) > 0):
                    return True
        
        # Check onchain data
        onchain_data = data.get('onchain_data', {})
        for source, source_data in onchain_data.items():
            if isinstance(source_data, dict):
                if source_data.get('holders', 0) > 0:
                    return True
        
        return False
    
    def get_fallback_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get fallback data for a token"""
        try:
            fallback_tokens = self.fallback_data.get('token_mappings', {})
            if token_address in fallback_tokens:
                fallback_data = fallback_tokens[token_address]
                
                # Check if fallback data is still within preserve duration
                timestamp = fallback_data.get('timestamp', 0)
                if isinstance(timestamp, str):
                    try:
                        timestamp = float(timestamp)
                    except (ValueError, TypeError):
                        timestamp = 0
                
                # Only use fallback if timestamp is valid (not 0)
                if timestamp > 0:
                    data_age = time.time() - timestamp
                    if data_age < self.preserve_duration_hours * 3600:
                        return fallback_data
                    else:
                        print(f"    ⏰ Fallback data expired ({data_age/3600:.1f}h old)")
                        return None
                else:
                    print(f"    ⚠️ Fallback data has invalid timestamp (0)")
                    return None
        except Exception as e:
            print(f"    ❌ Error getting fallback data: {e}")
        
        return None
    
    def _start_background_refresh(self):
        """Start background thread for periodic cache refresh"""
        def background_refresh():
            while True:
                try:
                    time.sleep(3600)  # Check every hour
                    self._perform_background_refresh()
                except Exception as e:
                    print(f"⚠️ Background refresh error: {e}")
        
        refresh_thread = threading.Thread(target=background_refresh, daemon=True)
        refresh_thread.start()
        print("🔄 Background cache refresh started")
    
    def _perform_background_refresh(self):
        """Perform background cache refresh with configured data preservation window."""
        current_time = time.time()
        with self._lock:
            tokens = copy.deepcopy(self.cache_data.get('tokens', {}))
        stale_tokens = []
        
        print(f"🔄 Background refresh: Checking {len(tokens)} tokens...")
        
        for token_address, token_data in tokens.items():
            timestamp = token_data.get('timestamp', 0)
            if isinstance(timestamp, str):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    timestamp = 0
            
            cache_age = current_time - timestamp
            
            if cache_age > self.cache_duration_hours * 3600:
                # Token is stale, but check if we should preserve it
                if cache_age < self.preserve_duration_hours * 3600:
                    # Move to fallback before clearing
                    self._preserve_to_fallback(token_address, token_data)
                    stale_tokens.append(token_address)
                else:
                    # Data is older than configured retention window, safe to clear
                    print(f"    🗑️ Token {token_address} data older than {self.preserve_duration_hours:.1f}h, clearing")
        
        if stale_tokens:
            print(f"🔄 Background refresh: {len(stale_tokens)} tokens moved to fallback")
            # Here you could implement background refresh logic
            # For now, just log the stale tokens
            for token in stale_tokens[:5]:  # Limit to 5 to avoid overwhelming
                print(f"    ⏰ Token {token} preserved in fallback, ready for refresh")
    
    def _preserve_to_fallback(self, token_address: str, token_data: Dict[str, Any]):
        """Preserve token data to fallback before clearing from cache"""
        try:
            with self._lock:
                if 'token_mappings' not in self.fallback_data:
                    self.fallback_data['token_mappings'] = {}
            
                # Only preserve if we don't have newer fallback data
                old_timestamp = token_data.get('timestamp', 0)
                if isinstance(old_timestamp, str):
                    try:
                        old_timestamp = float(old_timestamp)
                    except (ValueError, TypeError):
                        old_timestamp = 0
            
                fallback_timestamp = self.fallback_data['token_mappings'].get(token_address, {}).get('timestamp', 0)
                if isinstance(fallback_timestamp, str):
                    try:
                        fallback_timestamp = float(fallback_timestamp)
                    except (ValueError, TypeError):
                        fallback_timestamp = 0
            
                if (token_address not in self.fallback_data['token_mappings'] or 
                    old_timestamp > fallback_timestamp):
                    
                    token_data['source'] = 'preserved_cache'
                    self.fallback_data['token_mappings'][token_address] = token_data
                    print(f"    💾 Preserved {token_address} data to fallback")
                
        except Exception as e:
            print(f"    ❌ Error preserving {token_address} to fallback: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            tokens = self.cache_data.get('tokens', {})
            fallback_tokens = self.fallback_data.get('token_mappings', {})
            metadata = copy.deepcopy(self.metadata)
        
        return {
            'cache_tokens': len(tokens),
            'fallback_tokens': len(fallback_tokens),
            'cache_hits': metadata.get('cache_hits', 0),
            'cache_misses': metadata.get('cache_misses', 0),
            'total_data_points': metadata.get('total_data_points', 0),
            'last_refresh': metadata.get('last_refresh', 0),
            'cache_size_mb': self._get_cache_size_mb()
        }
    
    def _get_cache_size_mb(self) -> float:
        """Get cache file size in MB"""
        try:
            if os.path.exists(self.cache_file):
                return os.path.getsize(self.cache_file) / (1024 * 1024)
        except:
            pass
        return 0.0
    
    def cleanup_old_data(self):
        """Clean up old data that's beyond configured preserve duration."""
        current_time = time.time()
        preserve_seconds = self.preserve_duration_hours * 3600
        
        print(f"🧹 Cleaning up data older than {self.preserve_duration_hours} hours...")
        
        # Clean up fallback data - only remove data older than configured retention
        with self._lock:
            fallback_tokens = copy.deepcopy(self.fallback_data.get('token_mappings', {}))
        cleaned_fallback = {}
        removed_count = 0
        
        for token_address, token_data in fallback_tokens.items():
            timestamp = token_data.get('timestamp', 0)
            if isinstance(timestamp, str):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    timestamp = 0
            
            data_age = current_time - timestamp
            if data_age < preserve_seconds:
                cleaned_fallback[token_address] = token_data
            else:
                removed_count += 1
                print(f"    🗑️ Removed {token_address} (age: {data_age/3600:.1f}h)")
        
        if removed_count > 0:
            with self._lock:
                self.fallback_data['token_mappings'] = cleaned_fallback
            self._save_fallbacks()
            print(f"🧹 Cleaned up {removed_count} entries older than {self.preserve_duration_hours}h")
        else:
            print(f"🧹 No data older than {self.preserve_duration_hours}h found")
        
        # Also clean up cache data older than configured retention
        with self._lock:
            cache_tokens = copy.deepcopy(self.cache_data.get('tokens', {}))
        cleaned_cache = {}
        cache_removed = 0
        
        for token_address, token_data in cache_tokens.items():
            timestamp = token_data.get('timestamp', 0)
            if isinstance(timestamp, str):
                try:
                    timestamp = float(timestamp)
                except (ValueError, TypeError):
                    timestamp = 0
            
            data_age = current_time - timestamp
            if data_age < preserve_seconds:
                cleaned_cache[token_address] = token_data
            else:
                cache_removed += 1
                print(f"    🗑️ Removed {token_address} from cache (age: {data_age/3600:.1f}h)")
        
        if cache_removed > 0:
            with self._lock:
                self.cache_data['tokens'] = cleaned_cache
            self._save_cache()
            print(f"🧹 Cleaned up {cache_removed} cache entries older than {self.preserve_duration_hours}h")
    
    def force_refresh_all(self):
        """Force refresh all cached data (for manual trigger)"""
        print("🔄 Force refreshing all cached data...")
        with self._lock:
            self.metadata['refresh_count'] += 1
        self._save_metadata()
        # This would trigger a full refresh of all cached data
        # Implementation depends on your specific needs

# Global cache manager instance
_cache_manager = None

def get_cache_manager(data_dir: Optional[str] = None) -> EnhancedCacheManager:
    """Get or create global cache manager instance"""
    global _cache_manager
    
    if _cache_manager is None:
        if data_dir is None:
            # Default data directory
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            data_dir = os.path.join(project_root, 'data')
        
        _cache_manager = EnhancedCacheManager(data_dir)
    
    return _cache_manager
