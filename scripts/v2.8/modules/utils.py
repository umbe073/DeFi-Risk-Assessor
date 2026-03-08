#!/usr/bin/env python3
"""
Utils Module
Contains utility classes for logging, caching, and rate limiting
"""

import os
import json
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
import re # Added for sanitization

class Logger:
    """Enhanced logging utility"""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create file handler
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler(f'logs/{name.lower()}.log')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)

class CacheManager:
    """Enhanced in-memory cache with TTL and edge case handling"""
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 10000):
        self.cache = {}
        self.timestamps = {}
        self.ttl_values = {}  # Store custom TTL values
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.lock = threading.Lock()
        self.access_count = defaultdict(int)  # Track access frequency
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # Cleanup every 5 minutes
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache with enhanced error handling"""
        try:
            with self.lock:
                # Check if cleanup is needed
                self._maybe_cleanup()
                
                if key in self.cache:
                    # Get custom TTL or use default
                    ttl = self.ttl_values.get(key, self.default_ttl)
                    timestamp = self.timestamps.get(key, 0)
                    
                    if time.time() - timestamp < ttl:
                        # Update access count for LRU
                        self.access_count[key] += 1
                        return self.cache[key]
                    else:
                        # Expired, remove it
                        self._remove_key(key)
                return None
        except Exception as e:
            # Log error but don't crash
            logging.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with memory management"""
        try:
            with self.lock:
                # Check if cleanup is needed
                self._maybe_cleanup()
                
                # Check if we need to evict items
                if len(self.cache) >= self.max_size:
                    self._evict_least_used()
                
                # Sanitize key
                safe_key = self._sanitize_key(key)
                
                self.cache[safe_key] = value
                self.timestamps[safe_key] = time.time()
                
                # Store custom TTL if provided
                if ttl is not None:
                    self.ttl_values[safe_key] = ttl
                else:
                    # Use default TTL
                    self.ttl_values[safe_key] = self.default_ttl
                
                # Initialize access count
                if safe_key not in self.access_count:
                    self.access_count[safe_key] = 0
                    
        except Exception as e:
            logging.error(f"Cache set error for key {key}: {e}")
    
    def delete(self, key: str):
        """Delete value from cache"""
        try:
            with self.lock:
                safe_key = self._sanitize_key(key)
                self._remove_key(safe_key)
        except Exception as e:
            logging.error(f"Cache delete error for key {key}: {e}")
    
    def _remove_key(self, key: str):
        """Remove key from all cache structures"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]
        if key in self.ttl_values:
            del self.ttl_values[key]
        if key in self.access_count:
            del self.access_count[key]
    
    def _sanitize_key(self, key: str) -> str:
        """Sanitize cache key to prevent issues"""
        if not key or not isinstance(key, str):
            return "default_key"
        
        # Remove problematic characters
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
        
        # Limit length
        if len(safe_key) > 100:
            safe_key = safe_key[:100]
        
        return safe_key
    
    def _maybe_cleanup(self):
        """Cleanup expired entries if needed"""
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self.cleanup_expired()
            self.last_cleanup = current_time
    
    def _evict_least_used(self):
        """Evict least recently used items"""
        if not self.cache:
            return
        
        # Find least used items
        sorted_items = sorted(
            self.access_count.items(),
            key=lambda x: x[1]
        )
        
        # Remove 10% of least used items
        items_to_remove = max(1, len(sorted_items) // 10)
        
        for key, _ in sorted_items[:items_to_remove]:
            self._remove_key(key)
    
    def cleanup_expired(self):
        """Clean up expired cache entries"""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, timestamp in self.timestamps.items():
                ttl = self.ttl_values.get(key, self.default_ttl)
                if current_time - timestamp > ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_key(key)
                
        except Exception as e:
            logging.error(f"Cache cleanup error: {e}")
    
    def clear(self):
        """Clear all cache"""
        try:
            with self.lock:
                self.cache.clear()
                self.timestamps.clear()
                self.ttl_values.clear()
                self.access_count.clear()
        except Exception as e:
            logging.error(f"Cache clear error: {e}")
    
    def size(self) -> int:
        """Get current cache size"""
        try:
            with self.lock:
                return len(self.cache)
        except Exception:
            return 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            with self.lock:
                return {
                    'size': len(self.cache),
                    'max_size': self.max_size,
                    'utilization': len(self.cache) / self.max_size * 100,
                    'total_access': sum(self.access_count.values()),
                    'avg_access': sum(self.access_count.values()) / max(len(self.access_count), 1)
                }
        except Exception as e:
            logging.error(f"Cache stats error: {e}")
            return {}
    
    def get_keys(self) -> List[str]:
        """Get all cache keys"""
        try:
            with self.lock:
                return list(self.cache.keys())
        except Exception:
            return []

class RateLimiter:
    """Simple rate limiter with exponential backoff"""
    
    def __init__(self):
        self.request_history = defaultdict(lambda: deque())
        self.error_counts = defaultdict(int)
        self.lock = threading.Lock()
    
    def can_make_request(self, endpoint: str, max_requests: int = 100, time_window: int = 3600) -> bool:
        """Check if request can be made"""
        with self.lock:
            now = time.time()
            history = self.request_history[endpoint]
            
            # Remove old requests
            while history and now - history[0] > time_window:
                history.popleft()
            
            return len(history) < max_requests
    
    def record_request(self, endpoint: str, success: bool = True):
        """Record a request"""
        with self.lock:
            now = time.time()
            self.request_history[endpoint].append(now)
            
            if not success:
                self.error_counts[endpoint] += 1
    
    def get_delay(self, endpoint: str, attempt: int = 0) -> float:
        """Calculate delay for retry"""
        base_delay = 1.0
        max_delay = 60.0
        
        # Exponential backoff
        delay = min(base_delay * (2 ** attempt), max_delay)
        
        # Add jitter
        import random
        jitter = random.uniform(0, delay * 0.1)
        delay += jitter
        
        return delay
    
    def wait_if_needed(self, endpoint: str, max_requests: int = 100, time_window: int = 3600):
        """Wait if rate limit is exceeded"""
        if not self.can_make_request(endpoint, max_requests, time_window):
            with self.lock:
                now = time.time()
                history = self.request_history[endpoint]
                
                if history:
                    oldest_request = history[0]
                    time_until_reset = time_window - (now - oldest_request)
                    
                    if time_until_reset > 0:
                        time.sleep(time_until_reset)
    
    def get_status(self, endpoint: str) -> Dict:
        """Get rate limit status for endpoint"""
        with self.lock:
            now = time.time()
            history = self.request_history[endpoint]
            
            # Remove old requests
            while history and now - history[0] > 3600:  # 1 hour window
                history.popleft()
            
            return {
                'current_requests': len(history),
                'error_count': self.error_counts[endpoint],
                'can_make_request': len(history) < 100
            }

class ProgressTracker:
    """Track progress of batch operations"""
    
    def __init__(self, total: int, description: str = "Processing"):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
        self.lock = threading.Lock()
    
    def update(self, increment: int = 1):
        """Update progress"""
        with self.lock:
            self.current += increment
            self._print_progress()
    
    def _print_progress(self):
        """Print progress bar"""
        percentage = (self.current / self.total) * 100
        elapsed = time.time() - self.start_time
        
        if self.current > 0:
            estimated_total = elapsed * self.total / self.current
            remaining = estimated_total - elapsed
            eta = f"ETA: {remaining:.1f}s"
        else:
            eta = "ETA: --"
        
        bar_length = 50
        filled_length = int(bar_length * self.current // self.total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        print(f"\r{self.description}: |{bar}| {percentage:.1f}% ({self.current}/{self.total}) {eta}", end='', flush=True)
        
        if self.current >= self.total:
            print()  # New line when complete
    
    def get_stats(self) -> Dict:
        """Get progress statistics"""
        elapsed = time.time() - self.start_time
        if self.current > 0:
            rate = self.current / elapsed
            estimated_total = elapsed * self.total / self.current
            remaining = estimated_total - elapsed
        else:
            rate = 0
            remaining = 0
        
        return {
            'current': self.current,
            'total': self.total,
            'percentage': (self.current / self.total) * 100,
            'elapsed': elapsed,
            'rate': rate,
            'remaining': remaining
        }

class DataExporter:
    """Export data to various formats"""
    
    @staticmethod
    def export_to_json(data: List[Dict], filename: str):
        """Export data to JSON format"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"Failed to export to JSON: {e}")
            return False
    
    @staticmethod
    def export_to_csv(data: List[Dict], filename: str):
        """Export data to CSV format"""
        try:
            import csv
            
            if not data:
                return False
            
            fieldnames = data[0].keys()
            
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            return True
        except Exception as e:
            print(f"Failed to export to CSV: {e}")
            return False
    
    @staticmethod
    def export_to_excel(data: List[Dict], filename: str):
        """Export data to Excel format"""
        try:
            import pandas as pd
            
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False)
            return True
        except ImportError:
            print("pandas not available, skipping Excel export")
            return False
        except Exception as e:
            print(f"Failed to export to Excel: {e}")
            return False

class ConfigManager:
    """Manage configuration files"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._get_default_config()
        except Exception as e:
            print(f"Failed to load config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            'api_keys': {},
            'rate_limits': {
                'twitter': {'max_requests': 450, 'time_window': 900},
                'etherscan': {'max_requests': 5, 'time_window': 1},
                'coingecko': {'max_requests': 50, 'time_window': 60}
            },
            'cache_settings': {
                'enabled': True,
                'ttl': 3600
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/risk_assessment.log'
            },
            'output': {
                'json': True,
                'excel': True,
                'csv': False
            }
        }
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save_config()
    
    def update(self, updates: Dict):
        """Update multiple configuration values"""
        for key, value in updates.items():
            self.set(key, value) 
