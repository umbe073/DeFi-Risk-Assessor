#!/usr/bin/env python3
"""
Test script to verify individual API endpoints and identify issues
"""

import os
import json
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def test_coingecko_endpoints():
    """Test CoinGecko API endpoints"""
    print("\n🔍 Testing CoinGecko API Endpoints")
    print("=" * 60)
    
    # Test 1: Simple price API (free)
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': 'bitcoin,ethereum,uniswap,chainlink',
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true'
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ CoinGecko Simple Price API working")
            for coin, details in data.items():
                print(f"   {coin.upper()}: ${details.get('usd', 0):,.2f} (MC: ${details.get('usd_market_cap', 0):,.0f})")
        else:
            print(f"❌ CoinGecko Simple Price API error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ CoinGecko Simple Price API exception: {e}")
    
    # Test 2: Search API
    try:
        url = "https://api.coingecko.com/api/v3/search"
        params = {'query': 'SAND'}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            coins = data.get('coins', [])
            print(f"✅ CoinGecko Search API working ({len(coins)} results for SAND)")
            if coins:
                print(f"   First result: {coins[0].get('name')} ({coins[0].get('symbol')})")
        else:
            print(f"❌ CoinGecko Search API error: {response.status_code}")
    except Exception as e:
        print(f"❌ CoinGecko Search API exception: {e}")
    
    # Test 3: Contract address lookup
    try:
        token_address = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"  # UNI
        url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{token_address}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ CoinGecko Contract Address API working")
            market_data = data.get('market_data', {})
            print(f"   UNI Token: ${market_data.get('current_price', {}).get('usd', 0):.2f}")
        else:
            print(f"❌ CoinGecko Contract Address API error: {response.status_code}")
            if response.status_code == 429:
                print("   ⚠️ Rate limited! This might be why tokens show $0")
    except Exception as e:
        print(f"❌ CoinGecko Contract Address API exception: {e}")

def test_coinmarketcap_endpoints():
    """Test CoinMarketCap API endpoints"""
    print("\n🔍 Testing CoinMarketCap API Endpoints")
    print("=" * 60)
    
    api_key = os.getenv('COINMARKETCAP_API_KEY')
    if not api_key:
        print("❌ CoinMarketCap API key not found")
        return
    
    headers = {'X-CMC_PRO_API_KEY': api_key}
    
    # Test 1: Quotes API
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        params = {'symbol': 'BTC,ETH,UNI,LINK', 'convert': 'USD'}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', {})
            print(f"✅ CoinMarketCap Quotes API working (Credits: {status.get('credit_count', 0)})")
            
            for symbol, coin_data in data.get('data', {}).items():
                quote = coin_data.get('quote', {}).get('USD', {})
                print(f"   {symbol}: ${quote.get('price', 0):,.2f} (MC: ${quote.get('market_cap', 0):,.0f})")
        else:
            print(f"❌ CoinMarketCap Quotes API error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ CoinMarketCap Quotes API exception: {e}")
    
    # Test 2: Info API
    try:
        url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/info"
        params = {'symbol': 'BTC'}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ CoinMarketCap Info API working")
        else:
            print(f"❌ CoinMarketCap Info API error: {response.status_code}")
    except Exception as e:
        print(f"❌ CoinMarketCap Info API exception: {e}")

def test_etherscan_endpoints():
    """Test Etherscan API endpoints"""
    print("\n🔍 Testing Etherscan API Endpoints")
    print("=" * 60)
    
    api_key = os.getenv('ETHERSCAN_API_KEY')
    if not api_key:
        print("❌ Etherscan API key not found")
        return
    
    # Test 1: Token holder count
    try:
        url = "https://api.etherscan.io/api"
        params = {
            'module': 'token',
            'action': 'tokenholderlist',
            'contractaddress': '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984',  # UNI
            'page': 1,
            'offset': 1,
            'apikey': api_key
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1':
                print("✅ Etherscan Token Holder API working")
                result = data.get('result', [])
                if result:
                    print("   UNI Token holders data available")
            else:
                print(f"❌ Etherscan Token Holder API error: {data.get('message', 'Unknown error')}")
                print("   ⚠️ This might be why holder counts show 0")
        else:
            print(f"❌ Etherscan Token Holder API HTTP error: {response.status_code}")
    except Exception as e:
        print(f"❌ Etherscan Token Holder API exception: {e}")
    
    # Test 2: Basic stats (should always work)
    try:
        url = "https://api.etherscan.io/api"
        params = {
            'module': 'stats',
            'action': 'ethsupply',
            'apikey': api_key
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1':
                print("✅ Etherscan Basic Stats API working")
            else:
                print(f"❌ Etherscan Basic Stats API error: {data.get('message')}")
        else:
            print(f"❌ Etherscan Basic Stats API HTTP error: {response.status_code}")
    except Exception as e:
        print(f"❌ Etherscan Basic Stats API exception: {e}")

def test_coinpaprika_endpoints():
    """Test CoinPaprika API endpoints (free)"""
    print("\n🔍 Testing CoinPaprika API Endpoints")
    print("=" * 60)
    
    # Test ticker API
    try:
        url = "https://api.coinpaprika.com/v1/tickers/btc-bitcoin"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ CoinPaprika Ticker API working")
            quotes = data.get('quotes', {}).get('USD', {})
            print(f"   BTC: ${quotes.get('price', 0):,.2f} (MC: ${quotes.get('market_cap', 0):,.0f})")
        else:
            print(f"❌ CoinPaprika Ticker API error: {response.status_code}")
    except Exception as e:
        print(f"❌ CoinPaprika Ticker API exception: {e}")

def test_ethplorer_endpoints():
    """Test Ethplorer API endpoints (free)"""
    print("\n🔍 Testing Ethplorer API Endpoints")
    print("=" * 60)
    
    # Test token info
    try:
        token_address = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"  # UNI
        url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey=freekey"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Ethplorer Token Info API working")
            if 'holdersCount' in data:
                print(f"   UNI Holders: {data['holdersCount']:,}")
            if 'price' in data:
                print(f"   UNI Price: ${data['price'].get('rate', 0):.4f}")
        else:
            print(f"❌ Ethplorer Token Info API error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Ethplorer Token Info API exception: {e}")

def check_rate_limiting_status():
    """Check current rate limiting status"""
    print("\n⏱️ Checking Rate Limiting Status")
    print("=" * 60)
    
    # Check if we have rate limiting files
    data_dir = '/Users/amlfreak/Desktop/venv/data'
    rate_limit_file = os.path.join(data_dir, 'rate_limits.json')
    
    if os.path.exists(rate_limit_file):
        try:
            with open(rate_limit_file, 'r') as f:
                rate_limits = json.load(f)
            
            print("📊 Current Rate Limit Status:")
            for api, limits in rate_limits.items():
                print(f"   {api.upper()}:")
                for endpoint, data in limits.items():
                    last_request = data.get('last_request', 0)
                    if last_request > 0:
                        time_since = time.time() - last_request
                        print(f"     {endpoint}: {time_since:.1f}s ago")
                    else:
                        print(f"     {endpoint}: Never used")
        except Exception as e:
            print(f"❌ Error reading rate limits: {e}")
    else:
        print("⚠️ No rate limiting data found")

if __name__ == "__main__":
    print("🧪 API Endpoint Testing Suite")
    print("=" * 60)
    print("Testing individual API endpoints to identify issues...")
    
    test_coingecko_endpoints()
    time.sleep(1)  # Brief pause between API tests
    
    test_coinmarketcap_endpoints()
    time.sleep(1)
    
    test_etherscan_endpoints() 
    time.sleep(1)
    
    test_coinpaprika_endpoints()
    time.sleep(1)
    
    test_ethplorer_endpoints()
    
    check_rate_limiting_status()
    
    print("\n✅ API endpoint testing completed!")
    print("💡 Check the results above to identify which APIs are failing")
