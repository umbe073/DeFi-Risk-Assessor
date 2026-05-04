#!/usr/bin/env python3
"""
Test script to simulate dashboard data fetching
"""

import os
import sys
import json
import requests

# Add project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v2.0'))

# Test Ethplorer API directly
def test_ethplorer_direct():
    """Test Ethplorer API directly"""
    print("\n🔍 Testing Ethplorer API Direct Calls")
    print("=" * 60)
    
    test_tokens = [
        ("0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", "UNI"),
        ("0x514910771af9ca656af840dff83e8264ecf986ca", "LINK"), 
        ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USDC")
    ]
    
    for token_address, symbol in test_tokens:
        print(f"\n📋 Testing {symbol} ({token_address})")
        
        try:
            url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey=freekey"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                holders = data.get('holdersCount', 0)
                price = data.get('price', {})
                volume = data.get('volume24h', 0)
                
                print("   ✅ Success!")
                print(f"   Holders: {holders:,}")
                print(f"   Price: ${price.get('rate', 0):.4f}" if price else "   Price: N/A")
                print(f"   Volume 24h: ${volume:,.0f}")
                
                # Calculate market cap if possible
                if price and 'totalSupply' in data:
                    try:
                        price_usd = float(price.get('rate', 0))
                        supply = float(data['totalSupply'])
                        market_cap = price_usd * supply
                        print(f"   Market Cap: ${market_cap:,.0f}")
                    except:
                        print("   Market Cap: Unable to calculate")
                        
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:100]}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

def test_coingecko_direct():
    """Test CoinGecko API direct calls"""
    print("\n🔍 Testing CoinGecko API Direct Calls")
    print("=" * 60)
    
    # Test contract address lookup
    test_tokens = [
        ("0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", "UNI"),
        ("0x514910771af9ca656af840dff83e8264ecf986ca", "LINK"), 
        ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USDC")
    ]
    
    for token_address, symbol in test_tokens:
        print(f"\n📋 Testing {symbol} ({token_address})")
        
        try:
            url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{token_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                market_data = data.get('market_data', {})
                
                price = market_data.get('current_price', {}).get('usd', 0)
                market_cap = market_data.get('market_cap', {}).get('usd', 0)
                volume = market_data.get('total_volume', {}).get('usd', 0)
                
                print("   ✅ Success!")
                print(f"   Price: ${price:,.4f}")
                print(f"   Market Cap: ${market_cap:,.0f}")
                print(f"   Volume 24h: ${volume:,.0f}")
                
            elif response.status_code == 429:
                print("   ⚠️ Rate limited! This explains empty cache data")
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:100]}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

def test_simple_coingecko():
    """Test simple CoinGecko price API"""
    print("\n🔍 Testing CoinGecko Simple Price API")
    print("=" * 60)
    
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': 'uniswap,chainlink,usd-coin',
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Simple Price API Success!")
            
            for coin_id, coin_data in data.items():
                price = coin_data.get('usd', 0)
                market_cap = coin_data.get('usd_market_cap', 0)
                volume = coin_data.get('usd_24h_vol', 0)
                
                print(f"   {coin_id.upper()}:")
                print(f"     Price: ${price:,.4f}")
                print(f"     Market Cap: ${market_cap:,.0f}")
                print(f"     Volume 24h: ${volume:,.0f}")
        else:
            print(f"❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

def check_current_cache_state():
    """Check what's currently in the cache"""
    print("\n📊 Current Cache State")
    print("=" * 60)
    
    cache_file = '/Users/amlfreak/Desktop/venv/data/real_data_cache.json'
    
    try:
        with open(cache_file, 'r') as f:
            cache = json.load(f)
        
        tokens = cache.get('tokens', {})
        print(f"Cache has {len(tokens)} tokens")
        
        # Check a few specific tokens
        test_addresses = [
            "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",  # UNI
            "0x514910771af9ca656af840dff83e8264ecf986ca",  # LINK
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"   # USDC
        ]
        
        for addr in test_addresses:
            if addr in tokens:
                token_data = tokens[addr]
                market_sources = list(token_data.get('market_data', {}).keys())
                onchain_sources = list(token_data.get('onchain_data', {}).keys())
                
                print(f"\n{addr}:")
                print(f"  Market sources: {market_sources}")
                print(f"  Onchain sources: {onchain_sources}")
                
                # Check if there's actual data
                for source, data in token_data.get('market_data', {}).items():
                    if isinstance(data, dict) and data:
                        print(f"  {source} market data: {list(data.keys())}")
                        
                for source, data in token_data.get('onchain_data', {}).items():
                    if isinstance(data, dict) and data:
                        print(f"  {source} onchain data: {list(data.keys())}")
                        if 'holdersCount' in data:
                            print(f"    Holders: {data['holdersCount']:,}")
            else:
                print(f"\n{addr}: Not in cache")
                
    except Exception as e:
        print(f"❌ Error reading cache: {e}")

if __name__ == "__main__":
    print("🧪 Dashboard Data Fetching Test")
    print("=" * 60)
    
    check_current_cache_state()
    test_ethplorer_direct()
    test_coingecko_direct()
    test_simple_coingecko()
    
    print("\n✅ Dashboard data fetching test completed!")
    print("💡 Compare API results with current cache state to identify issues")
