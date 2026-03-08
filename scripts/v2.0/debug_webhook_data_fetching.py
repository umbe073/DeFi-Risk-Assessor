#!/usr/bin/env python3
"""
Debug webhook data fetching to identify why cache has empty data
"""

import os
import sys
import json

# Add project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v2.0'))
sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v1.5'))

# Import webhook server
from webhook_server import WebhookServer

def test_token_symbol_mapping():
    """Test if token symbol mapping is working"""
    print("\n🔍 Testing Token Symbol Mapping")
    print("=" * 60)
    
    webhook = WebhookServer()
    
    test_tokens = [
        "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",  # UNI
        "0x514910771af9ca656af840dff83e8264ecf986ca",  # LINK
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"   # USDC
    ]
    
    for token_address in test_tokens:
        print(f"\n📋 Testing {token_address}")
        symbol = webhook.get_symbol_from_address(token_address)
        print(f"   Symbol: {symbol}")
        
        if symbol:
            # Test CoinGecko mapping
            try:
                from token_mappings import get_coingecko_id
                coingecko_id = get_coingecko_id(symbol)
                print(f"   CoinGecko ID: {coingecko_id}")
            except Exception as e:
                print(f"   CoinGecko ID error: {e}")

def test_individual_api_methods():
    """Test individual API methods in webhook server"""
    print("\n🔍 Testing Individual API Methods")
    print("=" * 60)
    
    webhook = WebhookServer()
    
    # Test with known working token (UNI)
    test_symbol = "UNI"
    test_address = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
    
    print(f"📋 Testing API methods for {test_symbol} ({test_address})")
    
    # Test CoinGecko
    print(f"\n🔍 Testing CoinGecko API:")
    try:
        coingecko_data = webhook.fetch_coingecko_data(test_symbol)
        if coingecko_data:
            print(f"   ✅ Success: {coingecko_data}")
        else:
            print(f"   ❌ No data returned")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test CoinMarketCap
    print(f"\n🔍 Testing CoinMarketCap API:")
    try:
        cmc_data = webhook.fetch_cmc_data(test_symbol)
        if cmc_data:
            print(f"   ✅ Success: {cmc_data}")
        else:
            print(f"   ❌ No data returned")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test Ethplorer
    print(f"\n🔍 Testing Ethplorer API:")
    try:
        ethplorer_data = webhook.fetch_ethplorer_data(test_address)
        if ethplorer_data:
            print(f"   ✅ Success: {ethplorer_data}")
        else:
            print(f"   ❌ No data returned")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    # Test Etherscan
    print(f"\n🔍 Testing Etherscan API:")
    try:
        etherscan_data = webhook.fetch_etherscan_data(test_address)
        if etherscan_data:
            print(f"   ✅ Success: {etherscan_data}")
        else:
            print(f"   ❌ No data returned")
    except Exception as e:
        print(f"   ❌ Exception: {e}")

def test_full_data_fetching():
    """Test the complete data fetching process"""
    print("\n🔍 Testing Complete Data Fetching Process")
    print("=" * 60)
    
    webhook = WebhookServer()
    
    test_address = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"  # UNI
    
    print(f"📋 Testing complete fetch for {test_address}")
    
    try:
        result = webhook.fetch_real_time_data(test_address)
        
        if result:
            print(f"✅ Fetch completed!")
            print(f"   Market data sources: {list(result.get('market_data', {}).keys())}")
            print(f"   Onchain data sources: {list(result.get('onchain_data', {}).keys())}")
            
            # Check market data content
            for source, data in result.get('market_data', {}).items():
                print(f"   {source} market data: {data}")
                
            # Check onchain data content
            for source, data in result.get('onchain_data', {}).items():
                print(f"   {source} onchain data: {data}")
                
        else:
            print(f"❌ No data returned from complete fetch")
            
    except Exception as e:
        print(f"❌ Exception in complete fetch: {e}")

def check_csv_tokens():
    """Check what tokens are in the CSV file"""
    print("\n🔍 Checking CSV Tokens")
    print("=" * 60)
    
    webhook = WebhookServer()
    
    try:
        tokens = webhook.load_tokens_from_csv()
        print(f"Found {len(tokens)} tokens in CSV:")
        
        for i, token in enumerate(tokens[:5]):  # Show first 5
            print(f"   {i+1}. {token}")
            
        if len(tokens) > 5:
            print(f"   ... and {len(tokens) - 5} more")
            
    except Exception as e:
        print(f"❌ Error loading CSV tokens: {e}")

if __name__ == "__main__":
    print("🧪 Webhook Data Fetching Debug")
    print("=" * 60)
    
    check_csv_tokens()
    test_token_symbol_mapping()
    test_individual_api_methods()
    test_full_data_fetching()
    
    print(f"\n✅ Debug testing completed!")
    print("💡 Check the results above to identify why cache data is empty")
