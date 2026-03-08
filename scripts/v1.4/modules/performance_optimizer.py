#!/usr/bin/env python3
"""
Performance Optimization Module
Implements caching and parallel processing for improved performance
"""

import asyncio
import aiohttp
import concurrent.futures
import threading
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from .utils import Logger, CacheManager

@dataclass
class CacheConfig:
    """Cache configuration"""
    enabled: bool = True
    ttl: int = 3600  # 1 hour
    max_size: int = 1000
    cleanup_interval: int = 300  # 5 minutes

@dataclass
class ParallelConfig:
    """Parallel processing configuration"""
    max_workers: int = 10
    chunk_size: int = 5
    timeout: int = 30
    retry_attempts: int = 3

class PerformanceOptimizer:
    """Performance optimization with caching and parallel processing"""
    
    def __init__(self, cache_config: CacheConfig = None, parallel_config: ParallelConfig = None):
        self.cache_config = cache_config or CacheConfig()
        self.parallel_config = parallel_config or ParallelConfig()
        self.logger = Logger("PerformanceOptimizer")
        self.cache = CacheManager(self.cache_config.ttl)
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'parallel_executions': 0,
            'total_time_saved': 0
        }
        self.lock = threading.Lock()
    
    def get_cache_key(self, func_name: str, *args, **kwargs) -> str:
        """Generate cache key for function call"""
        # Create a hash of the function name and arguments
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def cached_call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with caching"""
        if not self.cache_config.enabled:
            return func(*args, **kwargs)
        
        cache_key = self.get_cache_key(func.__name__, *args, **kwargs)
        
        # Try to get from cache
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            with self.lock:
                self.stats['cache_hits'] += 1
            self.logger.info(f"Cache hit for {func.__name__}")
            return cached_result
        
        # Cache miss, execute function
        with self.lock:
            self.stats['cache_misses'] += 1
        
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Cache the result
        self.cache.set(cache_key, result)
        
        with self.lock:
            self.stats['total_time_saved'] += execution_time
        
        self.logger.info(f"Cache miss for {func.__name__}, executed in {execution_time:.2f}s")
        return result
    
    async def parallel_api_calls(self, api_calls: List[Dict]) -> List[Dict]:
        """Execute API calls in parallel"""
        if not api_calls:
            return []
        
        async def make_api_call(session: aiohttp.ClientSession, call: Dict) -> Dict:
            """Make a single API call"""
            url = call['url']
            headers = call.get('headers', {})
            params = call.get('params', {})
            timeout = aiohttp.ClientTimeout(total=self.parallel_config.timeout)
            
            for attempt in range(self.parallel_config.retry_attempts):
                try:
                    async with session.get(url, headers=headers, params=params, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                'success': True,
                                'data': data,
                                'url': url,
                                'attempt': attempt + 1
                            }
                        else:
                            return {
                                'success': False,
                                'error': f"HTTP {response.status}",
                                'url': url,
                                'attempt': attempt + 1
                            }
                except Exception as e:
                    if attempt == self.parallel_config.retry_attempts - 1:
                        return {
                            'success': False,
                            'error': str(e),
                            'url': url,
                            'attempt': attempt + 1
                        }
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            
            return {
                'success': False,
                'error': 'Max retries exceeded',
                'url': url,
                'attempt': self.parallel_config.retry_attempts
            }
        
        # Execute API calls in parallel
        connector = aiohttp.TCPConnector(limit=self.parallel_config.max_workers)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [make_api_call(session, call) for call in api_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        with self.lock:
            self.stats['parallel_executions'] += len(api_calls)
        
        return results
    
    def parallel_process_tokens(self, tokens: List[Dict], process_func: Callable) -> List[Dict]:
        """Process tokens in parallel using ThreadPoolExecutor"""
        if not tokens:
            return []
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallel_config.max_workers) as executor:
            # Submit all tasks
            future_to_token = {
                executor.submit(process_func, token): token 
                for token in tokens
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_token):
                token = future_to_token[future]
                try:
                    result = future.result(timeout=self.parallel_config.timeout)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Error processing token {token}: {e}")
                    results.append({
                        'token': token,
                        'error': str(e),
                        'success': False
                    })
        
        return results
    
    def chunk_processing(self, items: List[Any], chunk_size: int = None) -> List[List[Any]]:
        """Split items into chunks for processing"""
        chunk_size = chunk_size or self.parallel_config.chunk_size
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    def batch_api_calls(self, api_calls: List[Dict]) -> List[Dict]:
        """Execute API calls in batches"""
        if not api_calls:
            return []
        
        results = []
        chunks = self.chunk_processing(api_calls)
        
        for i, chunk in enumerate(chunks):
            self.logger.info(f"Processing batch {i+1}/{len(chunks)} ({len(chunk)} calls)")
            
            # Execute chunk in parallel
            chunk_results = asyncio.run(self.parallel_api_calls(chunk))
            results.extend(chunk_results)
            
            # Rate limiting between batches
            if i < len(chunks) - 1:
                time.sleep(1)  # 1 second delay between batches
        
        return results
    
    def optimize_data_collection(self, data_collectors: List[Callable], token_data: Dict) -> Dict:
        """Optimize data collection with caching and parallel processing"""
        results = {}
        
        # Prepare API calls for parallel execution
        api_calls = []
        for collector in data_collectors:
            # This would be customized based on the actual collector implementation
            api_calls.append({
                'url': f"https://api.example.com/{collector.__name__}",
                'headers': {},
                'params': {'token': token_data.get('address')}
            })
        
        # Execute API calls in parallel
        api_results = self.batch_api_calls(api_calls)
        
        # Process results
        for i, result in enumerate(api_results):
            collector_name = data_collectors[i].__name__
            if result['success']:
                results[collector_name] = result['data']
            else:
                self.logger.warning(f"Failed to collect {collector_name}: {result['error']}")
                results[collector_name] = {}
        
        return results
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        with self.lock:
            cache_hit_rate = (
                self.stats['cache_hits'] / 
                max(self.stats['cache_hits'] + self.stats['cache_misses'], 1) * 100
            )
            
            return {
                **self.stats,
                'cache_hit_rate': cache_hit_rate,
                'cache_size': self.cache.size(),
                'total_operations': self.stats['cache_hits'] + self.stats['cache_misses'],
                'time_saved_hours': self.stats['total_time_saved'] / 3600
            }
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.logger.info("Cache cleared")
    
    def optimize_memory_usage(self):
        """Optimize memory usage by cleaning up expired cache entries"""
        self.cache.cleanup_expired()
        self.logger.info("Memory optimization completed")
    
    def get_cache_info(self) -> Dict:
        """Get detailed cache information"""
        return {
            'enabled': self.cache_config.enabled,
            'ttl': self.cache_config.ttl,
            'max_size': self.cache_config.max_size,
            'current_size': self.cache.size(),
            'hit_rate': self.get_performance_stats()['cache_hit_rate']
        }

class AsyncDataCollector:
    """Asynchronous data collector for improved performance"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.logger = Logger("AsyncDataCollector")
    
    async def collect_market_data(self, symbol: str) -> Dict:
        """Collect market data asynchronously"""
        try:
            # CoinGecko API call
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': symbol.lower(),
                'vs_currencies': 'usd',
                'include_market_cap': 'true',
                'include_24hr_vol': 'true',
                'include_24hr_change': 'true'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'source': 'coingecko',
                        'data': data,
                        'success': True
                    }
                else:
                    return {
                        'source': 'coingecko',
                        'error': f"HTTP {response.status}",
                        'success': False
                    }
        except Exception as e:
            return {
                'source': 'coingecko',
                'error': str(e),
                'success': False
            }
    
    async def collect_social_data(self, symbol: str, token_name: str) -> Dict:
        """Collect social data asynchronously"""
        # This would implement actual social data collection
        # For now, return mock data
        return {
            'source': 'social',
            'data': {
                'twitter_tweets': 1000,
                'telegram_members': 5000,
                'discord_members': 3000
            },
            'success': True
        }
    
    async def collect_security_data(self, token_address: str) -> Dict:
        """Collect security data asynchronously"""
        # This would implement actual security data collection
        return {
            'source': 'security',
            'data': {
                'certik_score': 85,
                'defisafety_score': 75,
                'alchemy_verified': True
            },
            'success': True
        }

class PerformanceMonitor:
    """Monitor and track performance metrics"""
    
    def __init__(self):
        self.logger = Logger("PerformanceMonitor")
        self.metrics = defaultdict(list)
        self.start_time = time.time()
    
    def record_metric(self, metric_name: str, value: float):
        """Record a performance metric"""
        self.metrics[metric_name].append({
            'value': value,
            'timestamp': time.time()
        })
    
    def get_average_metric(self, metric_name: str) -> float:
        """Get average value for a metric"""
        if metric_name not in self.metrics:
            return 0.0
        
        values = [m['value'] for m in self.metrics[metric_name]]
        return sum(values) / len(values) if values else 0.0
    
    def get_performance_report(self) -> Dict:
        """Generate performance report"""
        uptime = time.time() - self.start_time
        
        return {
            'uptime_seconds': uptime,
            'uptime_hours': uptime / 3600,
            'average_response_time': self.get_average_metric('response_time'),
            'average_cache_hit_rate': self.get_average_metric('cache_hit_rate'),
            'total_requests': len(self.metrics.get('requests', [])),
            'total_errors': len(self.metrics.get('errors', [])),
            'error_rate': (
                len(self.metrics.get('errors', [])) / 
                max(len(self.metrics.get('requests', [])), 1) * 100
            )
        }
    
    def log_performance_summary(self):
        """Log performance summary"""
        report = self.get_performance_report()
        
        self.logger.info("Performance Summary:")
        self.logger.info(f"  Uptime: {report['uptime_hours']:.2f} hours")
        self.logger.info(f"  Average Response Time: {report['average_response_time']:.2f}s")
        self.logger.info(f"  Average Cache Hit Rate: {report['average_cache_hit_rate']:.1f}%")
        self.logger.info(f"  Total Requests: {report['total_requests']}")
        self.logger.info(f"  Error Rate: {report['error_rate']:.1f}%") 