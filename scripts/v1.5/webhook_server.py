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
from datetime import datetime

# Import required packages
from flask import Flask, request, jsonify
import requests

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

app = Flask(__name__)

# Configuration
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CACHE_FILE = os.path.join(DATA_DIR, 'real_data_cache.json')
FALLBACK_FILE = os.path.join(DATA_DIR, 'token_fallbacks.json')
SYMBOL_CACHE_FILE = os.path.join(DATA_DIR, 'symbol_cache.json')

class WebhookServer:
    def __init__(self):
        self.cache_data = {}
        self.fallback_data = {}
        self.symbol_cache = {}
        self.load_existing_data()
        
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
    
    def fetch_real_time_data(self, token_address):
        """Fetch real-time data for a token"""
        
        print(f"🔄 Fetching real-time data for {token_address}")
        
        # Clean the token address (remove chain suffix like _eth, _polygon, etc.)
        clean_address = token_address.split('_')[0] if '_' in token_address else token_address
        
        token_data = {
            'address': clean_address,
            'timestamp': time.time(),
            'market_data': {},
            'onchain_data': {},
            'social_data': {}
        }
        
        # Get token symbol from address
        symbol = self.get_symbol_from_address(token_address)
        
        # Try CoinGecko for market data
        if symbol:
            try:
                print(f"  📊 Fetching CoinGecko data for {symbol}...")
                coingecko_data = self.fetch_coingecko_data(symbol)
                if coingecko_data:
                    token_data['market_data']['coingecko'] = coingecko_data
            except Exception as e:
                print(f"  ❌ CoinGecko failed: {e}")
        
        # Try CoinMarketCap for market data
        if symbol:
            try:
                print(f"  📊 Fetching CoinMarketCap data for {symbol}...")
                cmc_data = self.fetch_cmc_data(symbol)
                if cmc_data:
                    token_data['market_data']['coinmarketcap'] = cmc_data
            except Exception as e:
                print(f"  ❌ CoinMarketCap failed: {e}")
        
        # Try Etherscan for onchain data
        try:
            print(f"  ⛓️  Fetching Etherscan data...")
            etherscan_data = self.fetch_etherscan_data(clean_address)
            if etherscan_data:
                token_data['onchain_data']['etherscan'] = etherscan_data
        except Exception as e:
            print(f"  ❌ Etherscan failed: {e}")
        
        # Try Ethplorer for additional onchain data
        try:
            print(f"  ⛓️  Fetching Ethplorer data...")
            ethplorer_data = self.fetch_ethplorer_data(clean_address)
            if ethplorer_data:
                token_data['onchain_data']['ethplorer'] = ethplorer_data
        except Exception as e:
            print(f"  ❌ Ethplorer failed: {e}")
        
        # Try to fetch REAL liquidity data
        try:
            print(f"  💧 Fetching REAL liquidity data...")
            liquidity_data = self.fetch_liquidity_data(clean_address)
            if liquidity_data:
                token_data['liquidity_data'] = {
                    liquidity_data['source']: {
                        'liquidity_score': liquidity_data['liquidity'],
                        'source': liquidity_data['source']
                    }
                }
                print(f"  ✅ Real liquidity data found: ${liquidity_data['liquidity']:,.0f} from {liquidity_data['source']}")
            else:
                print(f"  ❌ No real liquidity data available for {clean_address}")
        except Exception as e:
            print(f"  ❌ Liquidity fetch failed: {e}")
        
        return token_data
    
    def get_symbol_from_address(self, token_address):
        """Get symbol from token address using external mappings"""
        try:
            # Clean the token address (remove chain suffix like _eth, _polygon, etc.)
            clean_address = token_address.split('_')[0] if '_' in token_address else token_address
            
            # Import token mappings
            sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v1.5'))
            from token_mappings import get_token_symbol
            symbol = get_token_symbol(clean_address)
            
            if symbol and symbol != 'Unknown':
                print(f"  ✅ Found symbol for {clean_address}: {symbol}")
                return symbol
            else:
                print(f"  ⚠️  No symbol mapping found for {clean_address}")
                return None
        except Exception as e:
            print(f"  ❌ Error getting symbol for {token_address}: {e}")
            return None
    
    def fetch_coingecko_data(self, symbol):
        """Fetch real data from CoinGecko API"""
        try:
            # Get CoinGecko ID
            sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v1.5'))
            from token_mappings import get_coingecko_id
            coin_id = get_coingecko_id(symbol)
            
            if not coin_id:
                return None
            
            # Fetch from CoinGecko
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd',
                'include_market_cap': 'true',
                'include_24hr_vol': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if coin_id in data:
                    coin_data = data[coin_id]
                    return {
                        'market_cap': coin_data.get('usd_market_cap', 0),
                        'volume_24h': coin_data.get('usd_24h_vol', 0),
                        'price': coin_data.get('usd', 0),
                        'source': 'real-time'
                    }
        except Exception as e:
            print(f"  ❌ CoinGecko API error: {e}")
        return None
    
    def fetch_cmc_data(self, symbol):
        """Fetch real data from CoinMarketCap API"""
        try:
            # Get CMC ID
            sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v1.5'))
            from token_mappings import get_cmc_id
            cmc_id = get_cmc_id(symbol)
            
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
        except Exception as e:
            print(f"  ❌ CoinMarketCap API error: {e}")
        return None
    
    def fetch_liquidity_data(self, token_address):
        """Fetch REAL liquidity data from multiple sources"""
        try:
            # 1. Try Uniswap V3 API for real liquidity data
            uniswap_v3_url = f"https://api.uniswap.org/v1/pools"
            params = {
                'token0': token_address,
                'token1': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                'fee': '3000'  # 0.3% fee tier
            }
            
            response = requests.get(uniswap_v3_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'pools' in data and len(data['pools']) > 0:
                    pool = data['pools'][0]
                    liquidity = float(pool.get('totalValueLockedUSD', 0))
                    if liquidity > 0:
                        print(f"  💧 Real Uniswap V3 liquidity: ${liquidity:,.0f}")
                        return {
                            'liquidity': liquidity,
                            'source': 'uniswap-v3'
                        }
            
            # 2. Try SushiSwap API for real liquidity data
            sushiswap_url = f"https://api.sushi.com/v1/pairs"
            params = {
                'token0': token_address,
                'token1': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'  # WETH
            }
            
            response = requests.get(sushiswap_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'pairs' in data and len(data['pairs']) > 0:
                    pair = data['pairs'][0]
                    liquidity = float(pair.get('liquidityUSD', 0))
                    if liquidity > 0:
                        print(f"  💧 Real SushiSwap liquidity: ${liquidity:,.0f}")
                        return {
                            'liquidity': liquidity,
                            'source': 'sushiswap'
                        }
            
            # 3. Try 1inch API for real liquidity data
            inch_url = f"https://api.1inch.dev/swap/v5.2/1/quote"
            headers = {
                'Authorization': 'Bearer YOUR_1INCH_API_KEY',  # You'll need to add your 1inch API key
                'Accept': 'application/json'
            }
            params = {
                'src': token_address,
                'dst': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
                'amount': '1000000000000000000'  # 1 WETH
            }
            
            # Only try if API key is available
            if 'YOUR_1INCH_API_KEY' not in headers['Authorization']:
                response = requests.get(inch_url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'toAmount' in data:
                        # Calculate real liquidity from quote
                        liquidity = float(data.get('toAmount', 0)) / 1e18 * 1000  # Rough calculation
                        if liquidity > 0:
                            print(f"  💧 Real 1inch liquidity: ${liquidity:,.0f}")
                            return {
                                'liquidity': liquidity,
                                'source': '1inch'
                            }
            
            # 4. Try CoinGecko API for real liquidity data
            try:
                # Get token symbol first
                symbol = self.get_symbol_from_address(token_address)
                if symbol:
                    coingecko_url = f"https://api.coingecko.com/api/v3/coins/{symbol.lower()}"
                    response = requests.get(coingecko_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if 'market_data' in data:
                            liquidity = data['market_data'].get('total_liquidity', 0)
                            if liquidity > 0:
                                print(f"  💧 Real CoinGecko liquidity: ${liquidity:,.0f}")
                                return {
                                    'liquidity': liquidity,
                                    'source': 'coingecko'
                                }
            except Exception as e:
                print(f"  ❌ CoinGecko liquidity fetch error: {e}")
            
            print(f"  ❌ No real liquidity data found for {token_address}")
            return None
            
        except Exception as e:
            print(f"  ❌ Liquidity fetch error: {e}")
            return None

    def fetch_etherscan_data(self, token_address):
        """Fetch real data from Etherscan API"""
        try:
            # Load API key
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv('ETHERSCAN_API_KEY')
            
            if not api_key:
                return None
            
            # Get token holders
            url = "https://api.etherscan.io/api"
            params = {
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
        except Exception as e:
            print(f"  ❌ Etherscan API error: {e}")
        return None
    
    def fetch_ethplorer_data(self, token_address):
        """Fetch real data from Ethplorer API"""
        try:
            url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey=freekey"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'holders': int(data.get('holdersCount', 0)),
                    'total_supply': float(data.get('totalSupply', 0)),
                    'source': 'real-time'
                }
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
        
        # Merge real-time data if available
        if real_time_data:
            current_data.update({
                'last_real_time_update': time.time(),
                'market_data': real_time_data.get('market_data', {}),
                'onchain_data': real_time_data.get('onchain_data', {}),
                'social_data': real_time_data.get('social_data', {}),
                'liquidity_data': real_time_data.get('liquidity_data', {}),
                'data_source': 'real-time'
            })
            print(f"✅ Updated {token_address} with real-time data")
        
        # Use fallback data if real-time failed
        elif fallback_data:
            current_data.update({
                'last_fallback_update': time.time(),
                'symbol': fallback_data.get('symbol'),
                'name': fallback_data.get('name'),
                'type': fallback_data.get('type'),
                'verified': fallback_data.get('verified', False),
                'data_source': 'fallback'
            })
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
            
            for _, row in df.iterrows():
                address = row['address']
                # Use clean address without chain suffix for consistency
                tokens.append(address)
            
            print(f"✅ Loaded {len(tokens)} tokens from tokens.csv")
            return tokens
            
        except Exception as e:
            print(f"❌ Error loading tokens from CSV: {e}")
            return []

    def update_all_cache(self):
        """Update all cached data"""
        
        print("🔄 Triggered cache update for all tokens")
        
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
            
            # Save updated cache
            self.save_cache_data()
            
            return {
                'status': 'success',
                'message': f'Updated {updated_count} tokens with real-time data, {fallback_count} with fallback data',
                'total_tokens': len(tokens_to_update)
            }
            
        except Exception as e:
            print(f"❌ Error in update_all_cache: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

# Initialize webhook server
webhook_server = WebhookServer()

@app.route('/webhook/update_all', methods=['POST'])
def update_all_cache():
    """Update all cached data"""
    
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

@app.route('/webhook/update_token', methods=['POST'])
def update_single_token():
    """Update a single token's data"""
    
    data = request.get_json()
    token_address = data.get('address')
    
    if not token_address:
        return jsonify({'status': 'error', 'message': 'Token address required'}), 400
    
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
    
    cache_age = (time.time() - webhook_server.cache_data.get('last_updated', 0)) / 3600
    
    return jsonify({
        'status': 'running',
        'cache_tokens': len(webhook_server.cache_data.get('tokens', {})),
        'fallback_tokens': len(webhook_server.fallback_data.get('token_mappings', {})),
        'symbol_cache_size': len(webhook_server.symbol_cache.get('symbols', {})),
        'cache_age_hours': round(cache_age, 2),
        'last_updated': webhook_server.cache_data.get('last_updated', 0),
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/webhook/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

def run_webhook_server():
    """Run the webhook server"""
    print("🚀 Starting webhook server on port 5001...")
    print("📡 Available endpoints:")
    print("  • POST /webhook/update_all - Update all token cache")
    print("  • POST /webhook/update_token - Update single token")
    print("  • GET /webhook/status - Get server status")
    print("  • GET /webhook/health - Health check")
    
    app.run(host='127.0.0.1', port=5001, debug=False, threaded=True)

if __name__ == "__main__":
    run_webhook_server()
