#!/usr/bin/env python3
"""
Webhook Server for DeFi Risk Assessment Cache Monitoring
Handles cache updates and monitoring through HTTP endpoints
"""

import os
import json
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
import hashlib
from functools import lru_cache
import requests
from pathlib import Path
import pandas as pd

# Set up Flask app
app = Flask(__name__)

class SmartCache:
    """Enhanced caching system with field-level age tracking and intelligent refresh"""
    
    def __init__(self, cache_file='data/fallbacks/real_data_cache.json', max_age_hours=48):
        self.cache_file = cache_file
        self.max_age_hours = max_age_hours
        self.cache_lock = threading.Lock()
        self.request_cache = {}  # In-memory request cache to avoid duplicate API calls
        self.last_request_time = {}  # Track last request time per endpoint
        
        # 2025 API Rate Limits (calls per minute)
        self.rate_limits = {
            'coingecko': {'calls_per_minute': 10, 'burst_limit': 5},  # Free tier: 10 calls/min
            'coinmarketcap': {'calls_per_minute': 30, 'burst_limit': 10},  # Free tier: 30 calls/min
            'moralis': {'calls_per_minute': 100, 'burst_limit': 20},  # Free tier: 100 calls/min
            'alchemy': {'calls_per_minute': 100, 'burst_limit': 20},  # Free tier: 100 calls/min
            'etherscan': {'calls_per_minute': 5, 'burst_limit': 2},  # Free tier: 5 calls/sec
            'ethplorer': {'calls_per_minute': 20, 'burst_limit': 5},  # Free tier: 20 calls/min
            'defillama': {'calls_per_minute': 60, 'burst_limit': 10},  # Free tier: 60 calls/min
            'breadcrumbs': {'calls_per_minute': 10, 'burst_limit': 3},  # Free tier: 10 calls/min
            'dune': {'calls_per_minute': 5, 'burst_limit': 2},  # Free tier: 5 calls/min
        }
        
    def _get_cache_key(self, endpoint, params=None):
        """Generate a unique cache key for an API request"""
        key_data = f"{endpoint}_{params or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_request_too_recent(self, endpoint, min_interval_seconds=5):
        """Check if we made a request to this endpoint too recently"""
        now = time.time()
        last_time = self.last_request_time.get(endpoint, 0)
        return (now - last_time) < min_interval_seconds
    
    def _record_request(self, endpoint):
        """Record that we made a request to this endpoint"""
        self.last_request_time[endpoint] = time.time()
    
    def check_rate_limit(self, endpoint):
        """Check if we can make a request to an endpoint based on rate limits"""
        if endpoint not in self.rate_limits:
            return True, 0  # No rate limit defined, allow request
        
        current_time = time.time()
        rate_limit = self.rate_limits[endpoint]
        calls_per_minute = rate_limit['calls_per_minute']
        burst_limit = rate_limit['burst_limit']
        
        # Check if we have request history for this endpoint
        if endpoint not in self.last_request_time:
            return True, 0  # First request, allow it
        
        # Simple rate limiting: check if we can make a request
        # For more sophisticated rate limiting, we'd track request counts per minute
        min_interval = 60.0 / calls_per_minute  # Minimum seconds between requests
        
        if self._is_request_too_recent(endpoint, int(min_interval)):
            wait_time = min_interval - (current_time - self.last_request_time[endpoint])
            return False, wait_time
        
        return True, 0
    
    def wait_for_rate_limit(self, endpoint):
        """Wait for rate limit to reset if necessary"""
        can_request, wait_time = self.check_rate_limit(endpoint)
        
        if not can_request:
            print(f"  ⏳ Rate limit reached for {endpoint}, waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
        
        return True
    
    def should_fetch_field(self, token_address, field_name):
        """Check if a specific field should be fetched based on age"""
        try:
            with self.cache_lock:
                if not os.path.exists(self.cache_file):
                    return True
                
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                if token_address not in cache_data:
                    return True
                
                token_data = cache_data[token_address]
                if field_name not in token_data:
                    return True
                
                field_data = token_data[field_name]
                if not isinstance(field_data, dict) or 'timestamp' not in field_data:
                    return True
                
                # Check if field is older than max_age_hours
                field_timestamp = field_data['timestamp']
                field_age = time.time() - field_timestamp
                max_age_seconds = self.max_age_hours * 3600
                
                return field_age > max_age_seconds
                
        except Exception as e:
            print(f"  ⚠️  Cache check error for {field_name}: {e}")
            return True
    
    def update_field(self, token_address, field_name, value, source='unknown'):
        """Update a specific field in the cache with timestamp"""
        try:
            with self.cache_lock:
                # Load existing cache
                cache_data = {}
                if os.path.exists(self.cache_file):
                    with open(self.cache_file, 'r') as f:
                        cache_data = json.load(f)
                
                # Initialize token data if not exists
                if token_address not in cache_data:
                    cache_data[token_address] = {}
                
                # Update field with timestamp and source
                cache_data[token_address][field_name] = {
                    'value': value,
                    'timestamp': time.time(),
                    'source': source,
                    'updated_at': datetime.now().isoformat()
                }
                
                # Save updated cache
                os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
                with open(self.cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                
                print(f"  ✅ Updated {field_name} for {token_address[:8]}... (source: {source})")
                
        except Exception as e:
            print(f"  ❌ Cache update error for {field_name}: {e}")
    
    def get_field(self, token_address, field_name):
        """Get a specific field value from cache"""
        try:
            with self.cache_lock:
                if not os.path.exists(self.cache_file):
                    return None
                
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                if token_address not in cache_data:
                    return None
                
                token_data = cache_data[token_address]
                if field_name not in token_data:
                    return None
                
                field_data = token_data[field_name]
                if isinstance(field_data, dict) and 'value' in field_data:
                    return field_data['value']
                
                return field_data
                
        except Exception as e:
            print(f"  ⚠️  Cache read error for {field_name}: {e}")
            return None
    
    def get_all_token_data(self, token_address):
        """Get all cached data for a token"""
        try:
            with self.cache_lock:
                if not os.path.exists(self.cache_file):
                    return {}
                
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                return cache_data.get(token_address, {})
                
        except Exception as e:
            print(f"  ⚠️  Cache read error for token: {e}")
            return {}

# Initialize smart cache
smart_cache = SmartCache()

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CACHE_FILE = os.path.join(DATA_DIR, 'real_data_cache.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

# Global state
cache_data = {}
last_update = 0
monitoring_active = False
monitor_thread = None

def load_settings():
    """Load settings from settings.json"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading settings: {e}")
    return {
        "cache": {
            "background_monitoring": False,
            "auto_refresh_interval": "1 hour",
            "cache_retention": "24 hours"
        }
    }

def save_settings(settings):
    """Save settings to settings.json"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def load_cache():
    """Load cache data from file"""
    global cache_data, last_update
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                last_update = cache_data.get('last_updated', 0)
                print(f"✅ Cache loaded: {len(cache_data.get('tokens', {}))} tokens")
                return True
    except Exception as e:
        print(f"Error loading cache: {e}")
    return False

def save_cache():
    """Save cache data to file"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        cache_data['last_updated'] = int(time.time())
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        print(f"✅ Cache saved: {len(cache_data.get('tokens', {}))} tokens")
        return True
    except Exception as e:
        print(f"Error saving cache: {e}")
        return False

def fetch_market_data_by_symbol(symbol, chain):
    """Fetch market data by symbol for non-Ethereum tokens"""
    print(f"  🔄 Fetching market data by symbol for {symbol} on {chain}...")
    
    try:
        # Use CoinGecko's simple price API by symbol
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': symbol.lower(),  # CoinGecko uses lowercase symbols
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true',
            'include_last_updated_at': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if symbol.lower() in data:
                token_data = data[symbol.lower()]
                market_data = {
                    'price': token_data.get('usd', 0),
                    'market_cap': token_data.get('usd_market_cap', 0),
                    'volume_24h': token_data.get('usd_24h_vol', 0),
                    'last_updated': token_data.get('last_updated_at', int(time.time())),
                    'source': 'CoinGecko'
                }
                print(f"  ✅ {symbol} data by symbol: MC=${market_data['market_cap']:,.0f}, Vol=${market_data['volume_24h']:,.0f}")
                return market_data
            else:
                print(f"  ⚠️ {symbol} not found in CoinGecko by symbol")
        else:
            print(f"  ⚠️ CoinGecko API error: {response.status_code}")
    except Exception as e:
        print(f"  ⚠️ Error fetching {symbol} by symbol: {e}")
    
    return None

def fetch_market_data_from_multiple_sources(symbol, address):
    """Fetch market data from multiple sources and calculate averages"""
    market_data_sources = {}
    
    # Try CoinGecko
    coingecko_data = fetch_token_data_from_coingecko(symbol, address)
    if coingecko_data:
        market_data_sources['coingecko'] = coingecko_data
    
    # Try CoinMarketCap
    cmc_data = fetch_token_data_from_coinmarketcap(symbol, address)
    if cmc_data:
        market_data_sources['coinmarketcap'] = cmc_data
    
    # Try Moralis
    moralis_data = fetch_token_data_from_moralis(symbol, address)
    if moralis_data:
        market_data_sources['moralis'] = moralis_data
    
    # Try Alchemy
    alchemy_data = fetch_token_data_from_alchemy(symbol, address)
    if alchemy_data:
        market_data_sources['alchemy'] = alchemy_data
    
    # Try Etherscan
    etherscan_data = fetch_token_data_from_etherscan(symbol, address)
    if etherscan_data:
        market_data_sources['etherscan'] = etherscan_data
    
    
    # Calculate averages if we have multiple sources
    if len(market_data_sources) > 1:
        return calculate_market_data_averages(market_data_sources)
    elif len(market_data_sources) == 1:
        return list(market_data_sources.values())[0]
    else:
        return None

def fetch_token_data_from_coingecko(symbol, address):
    """Fetch real token data from CoinGecko API with smart caching"""
    try:
        # Check if we should skip this fetch based on age using smart cache
        if not smart_cache.should_fetch_field(address, 'coingecko_data'):
            print(f"  ⏭️  Skipping CoinGecko fetch for {symbol} (data is fresh)")
            cached_data = smart_cache.get_field(address, 'coingecko_data')
            if cached_data:
                return cached_data
        
        # Rate limiting - check if we made a request too recently
        endpoint = 'coingecko'
        smart_cache.wait_for_rate_limit(endpoint)
        smart_cache._record_request(endpoint)
        
        # CoinGecko API endpoint for token data
        url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum"
        params = {
            'contract_addresses': address,
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true',
            'include_24hr_change': 'true',
            'include_last_updated_at': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if address.lower() in data:
                token_data = data[address.lower()]
                result = {
                    'price': token_data.get('usd', 0),
                    'market_cap': token_data.get('usd_market_cap', 0),
                    'volume_24h': token_data.get('usd_24h_vol', 0),
                    'last_updated': token_data.get('last_updated_at', int(time.time())),
                    'source': 'coingecko'
                }
                
                # Update smart cache with the new data
                smart_cache.update_field(address, 'coingecko_data', result, 'CoinGecko')
                
                # Add delay after successful request
                time.sleep(2)
                
                return result
        elif response.status_code == 429:
            print(f"  ⚠️ CoinGecko rate limit hit for {symbol}, using cached data")
            # Return cached data if available
            cached_data = smart_cache.get_field(address, 'coingecko_data')
            if cached_data:
                return cached_data
    except Exception as e:
        print(f"  ❌ Error fetching {symbol} data from CoinGecko: {e}")
    
    return None

def fetch_token_data_from_coinmarketcap(symbol, address):
    """Fetch token data from CoinMarketCap API"""
    try:
        # CoinMarketCap API endpoint (requires API key)
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {
            'X-CMC_PRO_API_KEY': os.getenv('COINMARKETCAP_API_KEY', ''),
            'Accept': 'application/json'
        }
        params = {
            'address': address,
            'convert': 'USD'
        }
        
        if not headers['X-CMC_PRO_API_KEY']:
            return None
            
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']:
                token_data = list(data['data'].values())[0]
                quote = token_data.get('quote', {}).get('USD', {})
                return {
                    'price': quote.get('price', 0),
                    'market_cap': quote.get('market_cap', 0),
                    'volume_24h': quote.get('volume_24h', 0),
                    'last_updated': int(time.time()),
                    'source': 'coinmarketcap'
                }
    except Exception as e:
        print(f"  ❌ Error fetching {symbol} data from CoinMarketCap: {e}")
    
    return None

def fetch_token_data_from_moralis(symbol, address):
    """Fetch token data from Moralis API"""
    try:
        # Moralis API endpoint
        url = f"https://deep-index.moralis.io/api/v2/erc20/{address}/price"
        headers = {
            'X-API-Key': os.getenv('MORALIS_API_KEY', ''),
            'Accept': 'application/json'
        }
        params = {
            'chain': 'eth'
        }
        
        if not headers['X-API-Key']:
            return None
            
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'price': data.get('usdPrice', 0),
                'market_cap': data.get('usdPrice', 0) * data.get('tokenBalance', 0),  # Estimate
                'volume_24h': 0,  # Not available in this endpoint
                'last_updated': int(time.time()),
                'source': 'moralis'
            }
    except Exception as e:
        print(f"  ❌ Error fetching {symbol} data from Moralis: {e}")
    
    return None

def fetch_token_data_from_alchemy(symbol, address):
    """Fetch token data from Alchemy API"""
    try:
        # Alchemy API endpoint
        url = f"https://eth-mainnet.g.alchemy.com/v2/{os.getenv('ALCHEMY_API_KEY', '')}/getTokenMetadata"
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'alchemy_getTokenMetadata',
            'params': [address]
        }
        
        if not os.getenv('ALCHEMY_API_KEY'):
            return None
            
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if 'result' in result:
                token_data = result['result']
                # Alchemy doesn't provide price data directly, return None
                return None
    except Exception as e:
        print(f"  ❌ Error fetching {symbol} data from Alchemy: {e}")
    
    return None

def fetch_token_data_from_etherscan(symbol, address):
    """Fetch token data from Etherscan API"""
    try:
        # Etherscan API endpoint for token info
        url = "https://api.etherscan.io/api"
        params = {
            'module': 'token',
            'action': 'tokeninfo',
            'contractaddress': address,
            'apikey': os.getenv('ETHERSCAN_API_KEY', '')
        }
        
        if not params['apikey']:
            return None
            
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and 'result' in data:
                token_data = data['result'][0] if data['result'] else {}
                # Etherscan doesn't provide real-time price data
                return None
    except Exception as e:
        print(f"  ❌ Error fetching {symbol} data from Etherscan: {e}")
    
    return None


def calculate_market_data_averages(market_data_sources):
    """Calculate average market data from multiple sources"""
    try:
        prices = []
        market_caps = []
        volumes = []
        
        for source, data in market_data_sources.items():
            if data.get('price', 0) > 0:
                prices.append(data['price'])
            if data.get('market_cap', 0) > 0:
                market_caps.append(data['market_cap'])
            if data.get('volume_24h', 0) > 0:
                volumes.append(data['volume_24h'])
        
        avg_price = sum(prices) / len(prices) if prices else 0
        avg_market_cap = sum(market_caps) / len(market_caps) if market_caps else 0
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        
        sources_used = list(market_data_sources.keys())
        print(f"  📊 Calculated averages from {len(sources_used)} sources: {', '.join(sources_used)}")
        
        return {
            'price': avg_price,
            'market_cap': avg_market_cap,
            'volume_24h': avg_volume,
            'last_updated': int(time.time()),
            'source': f"average_of_{len(sources_used)}_sources",
            'sources': sources_used
        }
    except Exception as e:
        print(f"  ❌ Error calculating market data averages: {e}")
        return None

def fetch_liquidity_data(symbol, address):
    """Fetch liquidity data from multiple DEX APIs"""
    liquidity_sources = []
    
    # Try 1inch API for liquidity data
    try:
        # 1inch API for token liquidity
        inch_url = "https://api.1inch.dev/swap/v6.0/1/quote"
        headers = {'Authorization': 'Bearer YOUR_1INCH_API_KEY'}  # Replace with actual API key
        params = {
            'src': address,
            'dst': '0x6B175474E89094C44Da98b954EedeAC495271d0F',  # DAI
            'amount': '1000000000000000000'  # 1 token
        }
        
        response = requests.get(inch_url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'toAmount' in data:
                # Convert to USD value (rough estimate)
                liquidity_value = float(data['toAmount']) / 1e18  # Convert from wei
                liquidity_sources.append({
                    'liquidity': liquidity_value * 1000,  # Rough USD conversion
                    'liquidity_provider': '1inch',
                    'source': '1inch'
                })
    except Exception as e:
        print(f"Error fetching {symbol} liquidity from 1inch: {e}")
    
    # Try DeFiLlama for token price and liquidity data
    try:
        # Use the correct DeFiLlama endpoint for token prices
        defillama_url = f"https://coins.llama.fi/prices/current/ethereum:{address.lower()}"
        response = requests.get(defillama_url, timeout=10, headers={'User-Agent': 'DeFi Risk Assessment'})
        if response.status_code == 200:
            data = response.json()
            if 'coins' in data:
                coin_data = data['coins'].get(f'ethereum:{address.lower()}')
                if coin_data and 'price' in coin_data:
                    # Use price as liquidity indicator
                    liquidity_sources.append({
                        'liquidity': float(coin_data['price']) * 1000000,  # Rough liquidity estimate
                        'liquidity_provider': 'DeFiLlama',
                        'source': 'defillama'
                    })
    except Exception as e:
        print(f"Error fetching {symbol} liquidity from DeFiLlama: {e}")
    
    # Try CoinGecko for market data (can be used as liquidity proxy)
    try:
        coingecko_url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum"
        params = {
            'contract_addresses': address,
            'vs_currencies': 'usd',
            'include_24hr_vol': 'true',
            'include_24hr_change': 'true'
        }
        response = requests.get(coingecko_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if address.lower() in data:
                token_data = data[address.lower()]
                # Use 24h volume as liquidity proxy
                volume_24h = token_data.get('usd_24h_vol', 0)
                if volume_24h > 0:
                    liquidity_sources.append({
                        'liquidity': volume_24h * 0.1,  # 10% of volume as liquidity estimate
                        'liquidity_provider': 'CoinGecko Volume',
                        'source': 'coingecko'
                    })
    except Exception as e:
        print(f"Error fetching {symbol} liquidity from CoinGecko: {e}")
    
    # Return the best available liquidity data
    if liquidity_sources:
        # Sort by liquidity value and return the highest
        best_source = max(liquidity_sources, key=lambda x: x['liquidity'])
        print(f"  💧 {symbol} liquidity: ${best_source['liquidity']:,.0f} from {best_source['liquidity_provider']}")
        return best_source
    
    # Fallback: return 0 (will be estimated based on market cap)
    print(f"  ⚠️ No liquidity data found for {symbol}")
    return {
        'liquidity': 0,  # Will be calculated based on market cap
        'liquidity_provider': 'Estimated',
        'source': 'fallback'
    }

def get_fallback_market_data(address):
    """Get market data from fallback file for a specific token"""
    try:
        fallback_file = os.path.join(DATA_DIR, 'fallbacks', 'token_fallbacks.json')
        if not os.path.exists(fallback_file):
            return None
        
        with open(fallback_file, 'r') as f:
            fallback_data = json.load(f)
        
        token_data = fallback_data.get('token_mappings', {}).get(address.lower(), {})
        market_data = token_data.get('market_data', {})
        
        # Find the first source with good data
        for source, data in market_data.items():
            if isinstance(data, dict) and (data.get('market_cap', 0) > 0 or data.get('volume_24h', 0) > 0):
                return {
                    'price': data.get('price', 0),
                    'market_cap': data.get('market_cap', 0),
                    'volume_24h': data.get('volume_24h', 0),
                    'last_updated': data.get('last_updated', int(time.time())),
                    'source': source
                }
        
        return None
    except Exception as e:
        print(f"  ⚠️ Error getting fallback market data: {e}")
        return None

def get_fallback_liquidity_data(address):
    """Get liquidity data from fallback file for a specific token"""
    try:
        fallback_file = os.path.join(DATA_DIR, 'fallbacks', 'token_fallbacks.json')
        if not os.path.exists(fallback_file):
            return None
        
        with open(fallback_file, 'r') as f:
            fallback_data = json.load(f)
        
        token_data = fallback_data.get('token_mappings', {}).get(address.lower(), {})
        liquidity_data = token_data.get('liquidity_data', {})
        
        # Find the first source with good data
        for source, data in liquidity_data.items():
            if isinstance(data, dict) and data.get('liquidity_score', 0) > 0:
                return {
                    'liquidity_score': data.get('liquidity_score', 0),
                    'liquidity_provider': data.get('liquidity_provider', source),
                    'source': source
                }
        
        return None
    except Exception as e:
        print(f"  ⚠️ Error getting fallback liquidity data: {e}")
        return None

def get_fallback_holders_data(address):
    """Get holders data from fallback file for a specific token - REJECTS ALL ESTIMATED VALUES"""
    try:
        fallback_file = os.path.join(DATA_DIR, 'fallbacks', 'token_fallbacks.json')
        if not os.path.exists(fallback_file):
            return 0

        with open(fallback_file, 'r') as f:
            fallback_data = json.load(f)

        token_data = fallback_data.get('token_mappings', {}).get(address.lower(), {})
        onchain_data = token_data.get('onchain_data', {})

        # Find the first source with REAL data (reject estimated values)
        for source, data in onchain_data.items():
            if isinstance(data, dict):
                holders = data.get('holders', 0)
                source_type = data.get('source', '')

                # REJECT estimated values - only accept real data
                if holders > 0 and source_type != 'estimated' and source_type != 'placeholder':
                    print(f"  ✅ Found real holders data for {address[:10]}...: {holders:,} from {source}")
                    return holders

        print(f"  ⚠️ No real holders data found for {address[:10]}... (rejected estimated values)")
        return 0
    except Exception as e:
        print(f"  ⚠️ Error getting fallback holders data: {e}")
        return 0

def fetch_real_holders_data(symbol, address):
    """Try to fetch real holders data from APIs"""
    print(f"  👥 Attempting to fetch real holders data for {symbol}...")
    
    try:
        # Try Ethplorer API for Ethereum tokens
        if address.startswith('0x') and len(address) == 42:
            url = f"https://api.ethplorer.io/getTokenInfo/{address}"
            params = {'apiKey': 'freekey'}  # Free tier API key
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                holders = data.get('holdersCount', 0)
                if holders > 0:
                    print(f"  ✅ Found real holders data for {symbol}: {holders:,} from Ethplorer")
                    return holders
                else:
                    print(f"  ⚠️ Ethplorer returned 0 holders for {symbol}")
            else:
                print(f"  ⚠️ Ethplorer API error: {response.status_code}")
        
        # Try Etherscan API for Ethereum tokens
        if address.startswith('0x') and len(address) == 42:
            # Note: This would require an Etherscan API key for holders data
            print(f"  ⚠️ Etherscan holders API requires paid key for {symbol}")
        
        print(f"  ⚠️ No real holders data available for {symbol}")
        return 0
        
    except Exception as e:
        print(f"  ⚠️ Error fetching real holders data for {symbol}: {e}")
        return 0

def load_tokens_from_csv():
    """Load token addresses and symbols from tokens.csv file"""
    tokens_file = os.path.join(DATA_DIR, 'tokens.csv')
    tokens = {}
    
    try:
        if os.path.exists(tokens_file):
            import csv
            with open(tokens_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    symbol = row.get('symbol', '').strip()
                    address = row.get('address', '').strip()
                    name = row.get('name', '').strip()
                    chain = row.get('chain', '').strip()
                    
                    if symbol and address:
                        tokens[symbol] = {
                            'address': address,
                            'name': name,
                            'chain': chain
                        }
            print(f"✅ Loaded {len(tokens)} tokens from tokens.csv")
        else:
            print(f"⚠️ tokens.csv not found at {tokens_file}")
    except Exception as e:
        print(f"❌ Error loading tokens.csv: {e}")
    
    return tokens

def _safe_number(value):
    """Convert mixed string/number inputs into a float safely"""
    try:
        if isinstance(value, str):
            cleaned = value.replace('$', '').replace(',', '').strip()
            if cleaned == '':
                return 0
            return float(cleaned)
        if pd.isna(value):
            return 0
        return float(value)
    except Exception:
        return 0

def load_risk_report_data():
    """Load risk_report.json into address/symbol lookup tables"""
    report_path = os.path.join(DATA_DIR, 'risk_report.json')
    by_address, by_symbol = {}, {}
    try:
        if os.path.exists(report_path):
            with open(report_path, 'r') as f:
                entries = json.load(f)
            if isinstance(entries, list):
                for entry in entries:
                    addr = str(entry.get('token', '') or '').lower()
                    sym = str(entry.get('symbol', '') or '').upper()
                    if addr:
                        by_address[addr] = entry
                    if sym:
                        by_symbol[sym] = entry
            print(f"✅ Loaded risk_report.json entries: {len(by_address)} tokens")
    except Exception as e:
        print(f"⚠️ Error loading risk_report.json: {e}")
    return {'by_address': by_address, 'by_symbol': by_symbol}

def load_latest_xlsx_data():
    """Load latest XLSX report to use as a real-data fallback for cache refresh"""
    by_address, by_symbol = {}, {}
    try:
        reports = sorted(Path(DATA_DIR).glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
        for report in reports:
            try:
                df = pd.read_excel(report)
            except Exception:
                continue
            if df.empty:
                continue
            for _, row in df.iterrows():
                addr = str(row.get('Token Address', '') or '').lower()
                sym = str(row.get('Symbol', '') or '').upper()
                entry = {
                    'symbol': sym,
                    'name': str(row.get('Token Name', '') or sym),
                    'chain': str(row.get('Chain', '') or ''),
                    'market_cap': _safe_number(row.get('Market Cap', 0)),
                    'volume_24h': _safe_number(row.get('Volume 24h', 0)),
                    'holders': int(_safe_number(row.get('Holders', 0))),
                    'liquidity': _safe_number(row.get('Liquidity', 0)),
                    'price': _safe_number(row.get('Price', 0)),
                    'risk_score': _safe_number(row.get('Risk Score', 0)),
                    'risk_category': str(row.get('Risk Category', '') or ''),
                    'is_stablecoin': str(row.get('Is Stablecoin', '')).lower() in ('yes', 'true', '1'),
                    'eu_compliance_status': str(row.get('EU Compliance Status', '') or '')
                }
                if addr:
                    by_address[addr] = entry
                if sym:
                    by_symbol[sym] = entry
            print(f"✅ Loaded latest XLSX metrics from {report.name} ({len(by_address)} tokens)")
            break
    except Exception as e:
        print(f"⚠️ Error loading XLSX metrics: {e}")
    return {'by_address': by_address, 'by_symbol': by_symbol}

def update_cache_data():
    """Update cache with fresh data from APIs using smart caching and tokens.csv"""
    global cache_data, last_update
    
    print("🔄 Updating cache data with smart caching...")
    
    # Initialize cache structure
    if 'tokens' not in cache_data:
        cache_data['tokens'] = {}
    
    # Load tokens from CSV file instead of hardcoded values
    tokens_data = load_tokens_from_csv()
    risk_report_data = load_risk_report_data()
    xlsx_data = load_latest_xlsx_data()
    
    # Add some additional tokens that might not be in CSV
    additional_tokens = {}
    existing_symbols = set(tokens_data.keys())
    for addr, entry in risk_report_data['by_address'].items():
        sym = str(entry.get('symbol', '') or '').upper()
        if sym and sym not in existing_symbols and sym not in additional_tokens:
            additional_tokens[sym] = {
                'address': addr,
                'name': entry.get('token', sym),
                'chain': entry.get('chain', 'ethereum')
            }
    for addr, entry in xlsx_data['by_address'].items():
        sym = str(entry.get('symbol', '') or '').upper()
        if sym and sym not in existing_symbols and sym not in additional_tokens:
            additional_tokens[sym] = {
                'address': addr,
                'name': entry.get('name', sym),
                'chain': entry.get('chain', 'ethereum')
            }
    
    # Merge tokens
    all_tokens = {**tokens_data, **additional_tokens}
    
    updated_count = 0
    
    for symbol, token_info in all_tokens.items():
        try:
            address = token_info['address']
            name = token_info['name']
            chain = token_info['chain']
            report_entry = risk_report_data['by_address'].get(address.lower()) or risk_report_data['by_symbol'].get(symbol.upper(), {})
            xlsx_entry = xlsx_data['by_address'].get(address.lower()) or xlsx_data['by_symbol'].get(symbol.upper(), {})
            
            print(f"🔄 Fetching data for {symbol} ({name})...")
            
            # Check existing data age for this token
            existing_token_data = cache_data.get('tokens', {}).get(address.lower(), {})
            existing_timestamp = existing_token_data.get('timestamp', 0)
            current_time = int(time.time())
            data_age = current_time - existing_timestamp
            
            # Check existing data to determine what needs to be fetched
            existing_market_cap = existing_token_data.get('market_cap', 0)
            existing_volume_24h = existing_token_data.get('volume_24h', 0)
            existing_liquidity = existing_token_data.get('liquidity', 0)
            existing_holders = existing_token_data.get('holders', 0)
            
            # Only fetch data for fields that are 0 or missing
            need_market_data = (existing_market_cap == 0 or existing_volume_24h == 0)
            need_liquidity_data = (existing_liquidity == 0)
            need_holders_data = (existing_holders == 0)
            
            market_data = None
            liquidity_data = None
            holders = 0
            
            # Fetch market data only if needed
            if need_market_data:
                print(f"  📊 Fetching market data for {symbol} (MC={existing_market_cap}, Vol={existing_volume_24h})")
                
                # Check if this is a non-Ethereum token that might not be supported by our APIs
                if chain not in ['ethereum', 'polygon']:
                    print(f"  ⚠️ {symbol} is on {chain} chain - limited API support, trying CoinGecko by symbol")
                    # Try to fetch by symbol instead of contract address for non-Ethereum tokens
                    market_data = fetch_market_data_by_symbol(symbol, chain)
                else:
                    # First, check if we have good data in the fallback file
                    fallback_market_data = get_fallback_market_data(address)
                    if fallback_market_data and (fallback_market_data.get('market_cap', 0) > 0 or fallback_market_data.get('volume_24h', 0) > 0):
                        print(f"  📊 Using fallback market data for {symbol}")
                        market_data = fallback_market_data
                    else:
                        # Check smart cache
                        cached_market = smart_cache.get_field(address, 'market_data')
                        if cached_market:
                            cached_mc = cached_market.get('market_cap', 0)
                            cached_vol = cached_market.get('volume_24h', 0)
                            if cached_mc > 0 or cached_vol > 0:
                                print(f"  📊 Using smart cached market data for {symbol}")
                                market_data = cached_market
                            else:
                                print(f"  📊 Cached market data for {symbol} has 0 values - forcing fresh fetch")
                                market_data = fetch_market_data_from_multiple_sources(symbol, address)
                        else:
                            print(f"  📊 No cached market data for {symbol} - forcing fresh fetch")
                            market_data = fetch_market_data_from_multiple_sources(symbol, address)
                
                # Rate limiting delay
                time.sleep(6)  # 6 seconds = 10 calls per minute for CoinGecko
            else:
                print(f"  📊 Skipping market data fetch for {symbol} (MC={existing_market_cap}, Vol={existing_volume_24h})")
                # Use existing data
                if existing_market_cap > 0 or existing_volume_24h > 0:
                    market_data = {
                        'market_cap': existing_market_cap,
                        'volume_24h': existing_volume_24h,
                        'price': existing_token_data.get('price', 0),
                        'source': 'existing_cache'
                    }
            if not market_data and report_entry:
                metrics = report_entry.get('key_metrics', {})
                mc = metrics.get('market_cap', 0)
                vol = metrics.get('volume_24h', 0)
                price_val = metrics.get('price', 0)
                if mc or vol or price_val:
                    market_data = {
                        'market_cap': mc,
                        'volume_24h': vol,
                        'price': price_val,
                        'last_updated': int(time.time()),
                        'source': 'real_report'
                    }
            if not market_data and xlsx_entry:
                mc = xlsx_entry.get('market_cap', 0)
                vol = xlsx_entry.get('volume_24h', 0)
                price_val = xlsx_entry.get('price', 0)
                if mc or vol or price_val:
                    market_data = {
                        'market_cap': mc,
                        'volume_24h': vol,
                        'price': price_val,
                        'last_updated': int(time.time()),
                        'source': 'real_report'
                    }
            
            # Fetch liquidity data only if needed
            if need_liquidity_data:
                print(f"  💧 Fetching liquidity data for {symbol} (Liq={existing_liquidity})")
                
                # First, check if we have good data in the fallback file
                fallback_liquidity_data = get_fallback_liquidity_data(address)
                if fallback_liquidity_data and fallback_liquidity_data.get('liquidity_score', 0) > 0:
                    print(f"  💧 Using fallback liquidity data for {symbol}")
                    liquidity_data = fallback_liquidity_data
                else:
                    # Check smart cache
                    cached_liquidity = smart_cache.get_field(address, 'liquidity_data')
                    if cached_liquidity:
                        cached_liq = cached_liquidity.get('liquidity_score', 0)
                        if cached_liq > 0:
                            print(f"  💧 Using smart cached liquidity data for {symbol}")
                            liquidity_data = cached_liquidity
                        else:
                            print(f"  💧 Cached liquidity data for {symbol} has 0 values - forcing fresh fetch")
                            liquidity_data = fetch_liquidity_data(symbol, address)
                    else:
                        print(f"  💧 No cached liquidity data for {symbol} - forcing fresh fetch")
                        liquidity_data = fetch_liquidity_data(symbol, address)
                
                # Rate limiting delay
                time.sleep(2)  # 2 seconds for liquidity APIs
            else:
                print(f"  💧 Skipping liquidity data fetch for {symbol} (Liq={existing_liquidity})")
                # Use existing data
                if existing_liquidity > 0:
                    liquidity_data = {
                        'liquidity_score': existing_liquidity,
                        'source': 'existing_cache'
                    }
            if not liquidity_data:
                fallback_liq = 0
                if report_entry:
                    fallback_liq = report_entry.get('key_metrics', {}).get('liquidity', 0)
                elif xlsx_entry:
                    fallback_liq = xlsx_entry.get('liquidity', 0)
                if fallback_liq:
                    liquidity_data = {
                        'liquidity_score': fallback_liq,
                        'liquidity_provider': 'report',
                        'source': 'real_report'
                    }
            
            # Combine data in the format expected by Token Data Viewer
            # Use existing data if new data wasn't fetched
            if market_data:
                combined_market_data = {
                    market_data.get('source', 'multi_source'): {
                        'price': market_data.get('price', 0),
                        'market_cap': market_data.get('market_cap', 0),
                        'volume_24h': market_data.get('volume_24h', 0),
                        'last_updated': market_data.get('last_updated', int(time.time())),
                        'source': market_data.get('source', 'multi_source'),
                        'sources': market_data.get('sources', [])
                    }
                }
            else:
                # Use existing market data
                combined_market_data = existing_token_data.get('market_data', {
                    'coingecko': {
                        'price': 0,
                        'market_cap': 0,
                        'volume_24h': 0,
                        'source': 'cached'
                    }
                })
            
            if liquidity_data:
                liquidity_data_dict = {
                    liquidity_data.get('source', 'webhook'): {
                        'liquidity_score': liquidity_data.get('liquidity', 0),
                        'liquidity_provider': liquidity_data.get('liquidity_provider', 'Unknown'),
                        'source': liquidity_data.get('source', 'webhook')
                    }
                }
            else:
                # Use existing liquidity data
                liquidity_data_dict = existing_token_data.get('liquidity_data', {})
            
            token_data = {
                'address': address,
                'symbol': symbol,
                'timestamp': int(time.time()),
                'market_data': combined_market_data,
                'onchain_data': {
                    'ethplorer': {
                        'holders': 0,  # NO ESTIMATED VALUES - only real data
                        'source': 'real-time'
                    }
                },
                'liquidity_data': liquidity_data_dict,
                'source': 'webhook_cache'
            }
            
            # NO ESTIMATED VALUES - only real data from APIs
            
            # Extract top-level values for Token Data Viewer compatibility
            market_cap = 0
            volume_24h = 0
            liquidity = 0
            
            # Get market cap and volume from market data
            if market_data:
                market_cap = market_data.get('market_cap', 0)
                volume_24h = market_data.get('volume_24h', 0)
            
            # Get liquidity from liquidity data
            if liquidity_data:
                liquidity = liquidity_data.get('liquidity_score', 0)
            
            # Get holders data from fallback file, try APIs if needed
            holders = get_fallback_holders_data(address)
            if holders == 0 and need_holders_data:
                holders = fetch_real_holders_data(symbol, address)
            if holders == 0:
                holders = report_entry.get('key_metrics', {}).get('holders', 0) if report_entry else 0
            if holders == 0 and xlsx_entry:
                holders = xlsx_entry.get('holders', 0)
            
            # Add top-level fields for Token Data Viewer
            token_data['market_cap'] = market_cap
            token_data['volume_24h'] = volume_24h
            token_data['liquidity'] = liquidity
            token_data['holders'] = holders
            token_data['price'] = market_data.get('price', 0) if market_data else existing_token_data.get('price', 0)
            token_data['name'] = name
            token_data['risk_score'] = report_entry.get('risk_score', xlsx_entry.get('risk_score', 0))
            token_data['total_score_minus_social'] = report_entry.get('total_score_minus_social', 0)
            token_data['risk_category'] = report_entry.get('risk_category', xlsx_entry.get('risk_category', ''))
            token_data['is_stablecoin'] = report_entry.get('is_stablecoin', xlsx_entry.get('is_stablecoin', False))
            token_data['eu_compliance_status'] = report_entry.get('eu_compliance_status', xlsx_entry.get('eu_compliance_status', ''))
            token_data['component_scores'] = report_entry.get('component_scores', {})
            token_data['red_flags'] = report_entry.get('red_flags', [])
            
            # Store by token address (lowercase) as expected by Token Data Viewer
            cache_data['tokens'][address.lower()] = token_data
            updated_count += 1
            
            # Update smart cache with the new data
            if market_data:
                smart_cache.update_field(address, 'market_data', market_data, 'Multi-source')
            if liquidity_data:
                smart_cache.update_field(address, 'liquidity_data', liquidity_data, 'Multi-source')
            
            print(f"✅ {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Liq=${liquidity:,.0f}")
            
            # Add delay between tokens to avoid rate limits
            time.sleep(5)
            
        except Exception as e:
            print(f"❌ Error updating {symbol}: {e}")
    
    last_update = int(time.time())
    cache_data['last_updated'] = last_update
    cache_data['update_count'] = updated_count
    
    # Save to file
    save_cache()
    
    print(f"✅ Cache updated: {updated_count} tokens")
    
    # Update fallback file with the collected data
    update_fallback_file()
    
    return updated_count

def update_fallback_file():
    """Update token_fallbacks.json with data from webhook cache, respecting 48-hour age policy"""
    try:
        fallback_file = os.path.join(DATA_DIR, 'fallbacks', 'token_fallbacks.json')
        current_time = int(time.time())
        age_threshold = 48 * 3600  # 48 hours in seconds
        
        # Load existing fallback data
        fallback_data = {}
        if os.path.exists(fallback_file):
            with open(fallback_file, 'r') as f:
                fallback_data = json.load(f)
        
        # Initialize token_mappings if not exists
        if 'token_mappings' not in fallback_data:
            fallback_data['token_mappings'] = {}
        
        # Remove any existing "Unknown" tokens from fallback file
        unknown_tokens = []
        for addr, token_data in fallback_data['token_mappings'].items():
            if token_data.get('symbol') == 'Unknown' or token_data.get('name') == 'Unknown':
                unknown_tokens.append(addr)
        
        for addr in unknown_tokens:
            del fallback_data['token_mappings'][addr]
            print(f"  🗑️ Removed unknown token {addr} from fallback file")
        
        updated_count = 0
        preserved_count = 0
        
        # Update with webhook cache data, respecting age policy
        for token_address, token_data in cache_data.get('tokens', {}).items():
            if isinstance(token_data, dict):
                # Skip tokens that don't have proper symbol/name mapping
                if token_data.get('symbol') == 'Unknown' or token_data.get('name') == 'Unknown':
                    print(f"  ⚠️ Skipping unknown token {token_address}")
                    continue
                
                existing_entry = fallback_data['token_mappings'].get(token_address, {})
                existing_timestamp = existing_entry.get('timestamp', 0)
                data_age = current_time - existing_timestamp
                
                # Check if existing data is older than 48 hours
                if data_age > age_threshold or not existing_entry:
                    # Data is old or doesn't exist - update it
                    fallback_entry = {
                        'address': token_address,
                        'name': token_data.get('symbol', 'Unknown'),
                        'symbol': token_data.get('symbol', 'Unknown'),
                        'timestamp': token_data.get('timestamp', current_time),
                        'market_data': token_data.get('market_data', {}),
                        'onchain_data': token_data.get('onchain_data', {}),
                        'liquidity_data': token_data.get('liquidity_data', {}),
                        'source': 'webhook_cache'
                    }
                    
                    fallback_data['token_mappings'][token_address] = fallback_entry
                    updated_count += 1
                    print(f"  🔄 Updated {token_data.get('symbol', 'Unknown')} (age: {data_age/3600:.1f}h)")
                else:
                    # Data is fresh - preserve existing values but update only missing/zero values
                    preserved_entry = existing_entry.copy()
                    
                    # Only update liquidity_data if it's missing or has zero values
                    existing_liquidity = existing_entry.get('liquidity_data', {})
                    new_liquidity = token_data.get('liquidity_data', {})
                    
                    if not existing_liquidity or _has_zero_liquidity(existing_liquidity):
                        preserved_entry['liquidity_data'] = new_liquidity
                        print(f"  💧 Updated liquidity for {token_data.get('symbol', 'Unknown')} (preserved other data)")
                    
                    # Only update market_data if it has zero values
                    existing_market = existing_entry.get('market_data', {})
                    new_market = token_data.get('market_data', {})
                    
                    if _has_zero_market_data(existing_market):
                        preserved_entry['market_data'] = new_market
                        print(f"  📊 Updated market data for {token_data.get('symbol', 'Unknown')} (preserved other data)")
                    
                    # Only update onchain_data if it has zero values
                    existing_onchain = existing_entry.get('onchain_data', {})
                    new_onchain = token_data.get('onchain_data', {})
                    
                    if _has_zero_onchain_data(existing_onchain):
                        preserved_entry['onchain_data'] = new_onchain
                        print(f"  ⛓️ Updated onchain data for {token_data.get('symbol', 'Unknown')} (preserved other data)")
                    
                    fallback_data['token_mappings'][token_address] = preserved_entry
                    preserved_count += 1
                    print(f"  ✅ Preserved {token_data.get('symbol', 'Unknown')} (age: {data_age/3600:.1f}h)")
        
        # Save updated fallback file
        with open(fallback_file, 'w') as f:
            json.dump(fallback_data, f, indent=2)
        
        print(f"✅ Fallback file updated: {updated_count} tokens refreshed, {preserved_count} tokens preserved")
        
    except Exception as e:
        print(f"❌ Error updating fallback file: {e}")

def _has_zero_liquidity(liquidity_data):
    """Check if liquidity data has only zero values"""
    if not liquidity_data:
        return True
    
    for source, data in liquidity_data.items():
        if isinstance(data, dict) and data.get('liquidity_score', 0) > 0:
            return False
    return True

def _has_zero_market_data(market_data):
    """Check if market data has only zero values"""
    if not market_data:
        return True
    
    for source, data in market_data.items():
        if isinstance(data, dict):
            if data.get('market_cap', 0) > 0 or data.get('volume_24h', 0) > 0:
                return False
    return True

def _has_zero_onchain_data(onchain_data):
    """Check if onchain data has only zero values"""
    if not onchain_data:
        return True
    
    for source, data in onchain_data.items():
        if isinstance(data, dict) and data.get('holders', 0) > 0:
            return False
    return True

def cache_monitor_loop():
    """Background cache monitoring loop"""
    global monitoring_active
    
    print("🔄 Cache monitor thread started")
    
    while monitoring_active:
        try:
            # Check if cache needs updating
            cache_age_hours = (time.time() - last_update) / 3600
            settings = load_settings()
            
            # Get refresh interval from settings
            refresh_interval = settings.get('cache', {}).get('auto_refresh_interval', '1 hour')
            
            # Parse interval (simple parsing for demo)
            if 'hour' in refresh_interval:
                interval_hours = 1
            elif 'minute' in refresh_interval:
                interval_hours = 1/60
            else:
                interval_hours = 1
            
            if cache_age_hours > interval_hours:
                print(f"Cache is {cache_age_hours:.1f} hours old, refreshing...")
                update_cache_data()
            else:
                print(f"Cache is fresh ({cache_age_hours:.1f} hours old)")
            
            # Sleep for 10 minutes before next check
            time.sleep(600)
            
        except Exception as e:
            print(f"⚠️ Cache monitor error: {e}")
            time.sleep(300)  # Wait 5 minutes on error

def start_cache_monitoring():
    """Start background cache monitoring"""
    global monitoring_active, monitor_thread
    
    if monitoring_active:
        print("⚠️ Cache monitoring already active")
        return False
    
    settings = load_settings()
    if not settings.get('cache', {}).get('background_monitoring', False):
        print("⚠️ Background monitoring disabled in settings")
        return False

    monitoring_active = True
    monitor_thread = threading.Thread(target=cache_monitor_loop, daemon=True)
    monitor_thread.start()
    
    print("✅ Cache monitoring started")
    return True

def stop_cache_monitoring():
    """Stop background cache monitoring"""
    global monitoring_active
    
    monitoring_active = False
    if monitor_thread and monitor_thread.is_alive():
        monitor_thread.join(timeout=5)
    
    print("🛑 Cache monitoring stopped")

# Flask routes

@app.route('/webhook/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time()),
        'cache_tokens': len(cache_data.get('tokens', {})),
        'last_update': last_update
    })

@app.route('/webhook/status', methods=['GET'])
def status_check():
    """Status check endpoint"""
    cache_age_hours = (time.time() - last_update) / 3600
    
    return jsonify({
        'status': 'running',
        'monitoring_active': monitoring_active,
        'cache_age_hours': round(cache_age_hours, 2),
        'cache_tokens': len(cache_data.get('tokens', {})),
        'last_update': last_update,
        'timestamp': int(time.time())
    })

@app.route('/webhook/update_all', methods=['POST'])
def update_all():
    """Update all cache data"""
    try:
        updated_count = update_cache_data()
        return jsonify({
            'status': 'success',
            'updated_tokens': updated_count,
            'timestamp': int(time.time())
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/webhook/update_token', methods=['POST'])
def update_token():
    """Update specific token data"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        address = data.get('address')
        
        if not symbol or not address:
            return jsonify({
                'status': 'error',
                'error': 'Missing symbol or address'
            }), 400
        
        # Actually fetch real data for the specific token
        print(f"🔄 Fetching real data for {symbol}...")
        
        # Fetch market data
        market_data = fetch_market_data_from_multiple_sources(symbol, address)
        time.sleep(2)  # Rate limiting
        
        # Fetch liquidity data
        liquidity_data = fetch_liquidity_data(symbol, address)
        time.sleep(2)  # Rate limiting
        
        # Get holders data (reject estimated values), try APIs if needed
        holders = get_fallback_holders_data(address)
        if holders == 0:
            holders = fetch_real_holders_data(symbol, address)
        
        # Extract values
        market_cap = 0
        volume_24h = 0
        liquidity = 0
        
        if market_data:
            market_cap = market_data.get('market_cap', 0)
            volume_24h = market_data.get('volume_24h', 0)
        
        if liquidity_data:
            liquidity = liquidity_data.get('liquidity_score', 0)
        
        # Create token data with real values
        token_data = {
            'symbol': symbol,
            'address': address,
            'market_cap': market_cap,
            'volume_24h': volume_24h,
            'holders': holders,
            'liquidity': liquidity,
            'price': market_data.get('price', 0) if market_data else 0,
            'last_updated': int(time.time()),
            'market_data': {market_data.get('source', 'multi_source'): market_data} if market_data else {},
            'liquidity_data': {liquidity_data.get('source', 'webhook'): liquidity_data} if liquidity_data else {},
            'onchain_data': {
                'ethplorer': {
                    'holders': holders,
                    'source': 'real-time' if holders > 0 else 'no-data'
                }
            }
        }
        
        cache_data['tokens'][address.lower()] = token_data
        print(f"✅ {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
        
        # Save the updated cache to file
        save_cache()
        
        return jsonify({
            'status': 'success',
            'symbol': symbol,
            'timestamp': int(time.time())
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/webhook/cache', methods=['GET'])
def get_cache():
    """Get current cache data"""
    return jsonify(cache_data)

@app.route('/webhook/enable_monitoring', methods=['POST'])
def enable_monitoring():
    """Enable background cache monitoring"""
    try:
        settings = load_settings()
        settings['cache']['background_monitoring'] = True
        save_settings(settings)
        
        success = start_cache_monitoring()
        
        return jsonify({
            'status': 'success' if success else 'error',
            'monitoring_active': monitoring_active,
            'message': 'Monitoring enabled' if success else 'Failed to start monitoring'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/webhook/disable_monitoring', methods=['POST'])
def disable_monitoring():
    """Disable background cache monitoring"""
    try:
        settings = load_settings()
        settings['cache']['background_monitoring'] = False
        save_settings(settings)
        
        stop_cache_monitoring()
        
        return jsonify({
            'status': 'success',
            'monitoring_active': monitoring_active,
            'message': 'Monitoring disabled'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Webhook Server...")
    
    # Load initial cache
    load_cache()
    
    # Start monitoring if enabled in settings
    settings = load_settings()
    if settings.get('cache', {}).get('background_monitoring', False):
        start_cache_monitoring()
    
    print("✅ Webhook server ready on http://localhost:5001")
    print("📊 Endpoints:")
    print("   GET  /webhook/health - Health check")
    print("   GET  /webhook/status - Status check")
    print("   GET  /webhook/cache - Get cache data")
    print("   POST /webhook/update_all - Update all cache")
    print("   POST /webhook/update_token - Update specific token")
    print("   POST /webhook/enable_monitoring - Enable monitoring")
    print("   POST /webhook/disable_monitoring - Disable monitoring")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
