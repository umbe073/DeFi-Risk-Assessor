#!/usr/bin/env python3
"""
Test API calls directly to see what data we can get
"""

import requests
import time
import os
import sys

# Add project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v2.0'))

def test_coingecko_api():
    """Test CoinGecko API for a few tokens"""
    print("🔍 Testing CoinGecko API...")
    
    # Test tokens that should have market data
    test_tokens = [
        ('0x1f9840a85d5af5bf1d1762f925bdaddc4201f984', 'UNI'),
        ('0x514910771af9ca656af840dff83e8264ecf986ca', 'LINK'),
        ('0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9', 'AAVE'),
        ('0x6b175474e89094c44da98b954eedeac495271d0f', 'DAI'),
        ('0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', 'USDC'),
    ]
    
    for token_address, symbol in test_tokens:
        print(f"\n📊 Testing {symbol} ({token_address})...")
        
        try:
            # Get CoinGecko ID for the token
            from token_mappings import get_coingecko_id
            coingecko_id = get_coingecko_id(symbol)
            
            if coingecko_id:
                print(f"  CoinGecko ID: {coingecko_id}")
                
                # Fetch data from CoinGecko
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {
                    'ids': coingecko_id,
                    'vs_currencies': 'usd',
                    'include_market_cap': 'true',
                    'include_24hr_vol': 'true'
                }
                
                response = requests.get(url, params=params, timeout=10)
                print(f"  Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if coingecko_id in data:
                        token_data = data[coingecko_id]
                        print(f"  ✅ Market Cap: ${token_data.get('usd_market_cap', 0):,.0f}")
                        print(f"  ✅ Volume: ${token_data.get('usd_24h_vol', 0):,.0f}")
                        print(f"  ✅ Price: ${token_data.get('usd', 0):,.6f}")
                    else:
                        print(f"  ❌ No data for {coingecko_id}")
                else:
                    print(f"  ❌ API Error: {response.text}")
            else:
                print(f"  ❌ No CoinGecko ID found for {symbol}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Rate limiting - wait between requests
        time.sleep(1)

def test_webhook_fetching():
    """Test webhook server's data fetching directly"""
    print("\n🔍 Testing Webhook Data Fetching...")
    
    from webhook_server import WebhookServer
    
    webhook = WebhookServer()
    
    # Test a few tokens
    test_tokens = [
        ('0x1f9840a85d5af5bf1d1762f925bdaddc4201f984', 'UNI'),
        ('0x514910771af9ca656af840dff83e8264ecf986ca', 'LINK'),
        ('0x6b175474e89094c44da98b954eedeac495271d0f', 'DAI'),
    ]
    
    for token_address, symbol in test_tokens:
        print(f"\n📊 Testing {symbol} ({token_address})...")
        
        try:
            data = webhook.fetch_real_time_data(token_address)
            
            if data:
                print(f"  ✅ Got data for {symbol}")
                
                # Check market data
                market_data = data.get('market_data', {})
                print(f"    Market data sources: {list(market_data.keys())}")
                
                for source, source_data in market_data.items():
                    print(f"    {source}:")
                    print(f"      Market Cap: ${source_data.get('market_cap', 0):,.0f}")
                    print(f"      Volume: ${source_data.get('volume_24h', 0):,.0f}")
                
                # Check onchain data
                onchain_data = data.get('onchain_data', {})
                print(f"    Onchain data sources: {list(onchain_data.keys())}")
                
                for source, source_data in onchain_data.items():
                    print(f"    {source}:")
                    print(f"      Holders: {source_data.get('holders', 0):,}")
            else:
                print(f"  ❌ No data returned for {symbol}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 API Testing")
    print("=" * 50)
    
    test_coingecko_api()
    test_webhook_fetching()
    
    print("\n✅ API testing completed!")
