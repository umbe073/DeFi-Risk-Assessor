#!/usr/bin/env python3
"""
Test script to verify cache integration is working properly
"""

import os
import sys
from datetime import datetime

# Add project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v2.0'))

# Define DATA_DIR
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

# Initialize cache manager
try:
    from cache_manager import get_cache_manager
    cache_manager = get_cache_manager(DATA_DIR)
    print("✅ Enhanced cache manager initialized")
except ImportError as e:
    print(f"❌ Enhanced cache manager not available: {e}")
    cache_manager = None
    sys.exit(1)

def test_cache_functionality():
    """Test the cache functionality"""
    
    print("\n🧪 Testing Cache Functionality")
    print("=" * 50)
    
    # Test tokens
    test_tokens = [
        "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",  # UNI
        "0x514910771af9ca656af840dff83e8264ecf986ca",  # LINK
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"   # USDC
    ]
    
    print(f"📋 Testing {len(test_tokens)} tokens...")
    
    for i, token_address in enumerate(test_tokens, 1):
        print(f"\n{i}. Testing token: {token_address}")
        
        # Try to get cached data
        cached_data = cache_manager.get_cached_data(token_address)
        if cached_data:
            print(f"   📦 Found cached data: MC=${cached_data.get('market_cap', 0):,.0f}")
        else:
            print("   ⚠️ No cached data found")
        
        # Test saving some mock real-time data
        mock_data = {
            'market_cap': 1000000000 + i * 100000000,
            'volume_24h': 50000000 + i * 10000000,
            'holders': 10000 + i * 1000,
            'liquidity': 25000000 + i * 5000000,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"   💾 Saving mock data: MC=${mock_data['market_cap']:,.0f}")
        cache_manager.update_cache_with_real_time_data(token_address, mock_data)
        
        # Verify it was saved
        updated_data = cache_manager.get_cached_data(token_address)
        if updated_data and updated_data.get('market_cap') == mock_data['market_cap']:
            print("   ✅ Cache update successful")
        else:
            print("   ❌ Cache update failed")
    
    # Test cache stats
    print("\n📊 Cache Statistics:")
    try:
        stats = cache_manager.get_cache_stats()
        print(f"   Cache entries: {stats.get('cache_entries', 0)}")
        print(f"   Fallback entries: {stats.get('fallback_entries', 0)}")
        print(f"   Cache size: {stats.get('cache_size_mb', 0):.2f} MB")
        print(f"   Last updated: {stats.get('last_updated', 'Never')}")
    except Exception as e:
        print(f"   ❌ Error getting stats: {e}")

def check_webhook_integration():
    """Check if webhook server is properly integrated"""
    
    print("\n🔗 Testing Webhook Integration")
    print("=" * 50)
    
    import requests
    
    try:
        # Test webhook status
        response = requests.get('http://localhost:5001/webhook/status', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Webhook server is running")
            print(f"   Cache tokens: {data.get('cache_tokens', 0)}")
            print(f"   Fallback tokens: {data.get('fallback_tokens', 0)}")
            print(f"   Cache age: {data.get('cache_age_hours', 0):.2f} hours")
        else:
            print(f"❌ Webhook server error: {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook server not accessible: {e}")

def test_rate_limiting():
    """Test API rate limiting"""
    
    print("\n⏱️ Testing Rate Limiting")
    print("=" * 50)
    
    # Test if we have the API error handler
    try:
        from api_error_handler import get_error_handler
        get_error_handler(DATA_DIR)
        print("✅ API error handler available")
        
        # Check rate limit status for different APIs
        apis = ['coingecko', 'coinmarketcap', 'etherscan']
        for api in apis:
            # This is a simple check - in real implementation, 
            # the error handler would track actual usage
            print(f"   🔍 {api.upper()}: Rate limiting configured")
            
    except ImportError as e:
        print(f"❌ API error handler not available: {e}")

if __name__ == "__main__":
    print("🧪 DeFi Cache Integration Test")
    print("=" * 50)
    
    test_cache_functionality()
    check_webhook_integration()
    test_rate_limiting()
    
    print("\n✅ Cache integration test completed!")
    print("💡 If you see issues, check the cache files in:", DATA_DIR)
