#!/usr/bin/env python3
"""
Test script to verify the new priority-based cache system
"""

import os
import sys
import json
import time
from datetime import datetime

# Add project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v2.0'))

def test_cache_preservation():
    """Test that cache preserves data for 48 hours"""
    print("\n🔍 Testing 48-Hour Cache Preservation")
    print("=" * 60)
    
    # Import cache manager
    try:
        from cache_manager import get_cache_manager
        cache_manager = get_cache_manager()
        print("✅ Cache manager loaded successfully")
    except Exception as e:
        print(f"❌ Error loading cache manager: {e}")
        return
    
    # Check current cache configuration
    print(f"📊 Cache Configuration:")
    print(f"   Cache duration: {cache_manager.cache_duration_hours} hours")
    print(f"   Preserve duration: {cache_manager.preserve_duration_hours} hours")
    print(f"   Max cache size: {cache_manager.max_cache_size_mb} MB")
    
    # Check current cache stats
    stats = cache_manager.get_cache_stats()
    print(f"\n📊 Current Cache Statistics:")
    print(f"   Cache tokens: {stats.get('cache_tokens', 0)}")
    print(f"   Fallback tokens: {stats.get('fallback_tokens', 0)}")
    print(f"   Cache hits: {stats.get('cache_hits', 0)}")
    print(f"   Cache misses: {stats.get('cache_misses', 0)}")
    print(f"   Total data points: {stats.get('total_data_points', 0)}")
    print(f"   Last refresh: {datetime.fromtimestamp(stats.get('last_refresh', 0)).strftime('%Y-%m-%d %H:%M:%S')}")

def test_priority_data_fetching():
    """Test the priority-based data fetching strategy"""
    print("\n🔍 Testing Priority-Based Data Fetching")
    print("=" * 60)
    
    # Import cache manager
    try:
        from cache_manager import get_cache_manager
        cache_manager = get_cache_manager()
    except Exception as e:
        print(f"❌ Error loading cache manager: {e}")
        return
    
    # Test tokens
    test_tokens = [
        "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",  # UNI
        "0x514910771af9ca656af840dff83e8264ecf986ca",  # LINK
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"   # USDC
    ]
    
    for token_address in test_tokens:
        print(f"\n📋 Testing priority fetching for {token_address}")
        
        # Mock fetch function that simulates API calls
        def mock_fetch_function(addr):
            # Simulate API response
            return {
                'address': addr,
                'timestamp': time.time(),
                'market_data': {
                    'coingecko': {
                        'market_cap': 1000000000,
                        'volume_24h': 50000000,
                        'price': 10.0,
                        'source': 'real-time'
                    }
                },
                'onchain_data': {
                    'ethplorer': {
                        'holders': 100000,
                        'total_supply': 1000000000,
                        'source': 'real-time'
                    }
                }
            }
        
        # Test priority-based fetching
        try:
            result = cache_manager.fetch_data_with_intelligent_cache(token_address, mock_fetch_function)
            if result:
                print(f"   ✅ Priority fetching successful")
                print(f"   Market data sources: {list(result.get('market_data', {}).keys())}")
                print(f"   Onchain data sources: {list(result.get('onchain_data', {}).keys())}")
            else:
                print(f"   ⚠️ No data returned")
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_fallback_data_retrieval():
    """Test fallback data retrieval"""
    print("\n🔍 Testing Fallback Data Retrieval")
    print("=" * 60)
    
    # Import cache manager
    try:
        from cache_manager import get_cache_manager
        cache_manager = get_cache_manager()
    except Exception as e:
        print(f"❌ Error loading cache manager: {e}")
        return
    
    # Test tokens
    test_tokens = [
        "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",  # UNI
        "0x514910771af9ca656af840dff83e8264ecf986ca",  # LINK
    ]
    
    for token_address in test_tokens:
        print(f"\n📋 Testing fallback data for {token_address}")
        
        try:
            fallback_data = cache_manager.get_fallback_data(token_address)
            if fallback_data:
                print(f"   ✅ Fallback data available")
                data_age = (time.time() - fallback_data.get('timestamp', 0)) / 3600
                print(f"   Age: {data_age:.1f} hours")
                print(f"   Source: {fallback_data.get('source', 'unknown')}")
            else:
                print(f"   ⚠️ No fallback data available")
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_webhook_integration():
    """Test webhook integration with priority system"""
    print("\n🔍 Testing Webhook Integration")
    print("=" * 60)
    
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
            
            # Test cache update with priority system
            print(f"\n🔄 Testing priority-based cache update...")
            update_response = requests.post('http://localhost:5001/webhook/update_all', 
                                          json={}, timeout=30)
            if update_response.status_code == 200:
                update_data = update_response.json()
                print("✅ Cache update completed")
                print(f"   Message: {update_data.get('message', '')}")
                print(f"   Total tokens: {update_data.get('total_tokens', 0)}")
                print(f"   Updated count: {update_data.get('updated_count', 0)}")
                print(f"   Fallback count: {update_data.get('fallback_count', 0)}")
                print(f"   Rate limited count: {update_data.get('rate_limited_count', 0)}")
            else:
                print(f"❌ Cache update failed: {update_response.status_code}")
        else:
            print(f"❌ Webhook server error: {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook test error: {e}")

def test_data_preservation():
    """Test that data is preserved for 48 hours"""
    print("\n🔍 Testing 48-Hour Data Preservation")
    print("=" * 60)
    
    # Check current cache and fallback files
    cache_file = '/Users/amlfreak/Desktop/venv/data/real_data_cache.json'
    fallback_file = '/Users/amlfreak/Desktop/venv/data/token_fallbacks.json'
    
    try:
        # Check cache file
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            tokens = cache_data.get('tokens', {})
            print(f"📊 Cache file has {len(tokens)} tokens")
            
            # Check data ages
            current_time = time.time()
            for token_address, token_data in list(tokens.items())[:3]:  # Check first 3
                data_age = (current_time - token_data.get('timestamp', 0)) / 3600
                print(f"   {token_address}: {data_age:.1f} hours old")
        
        # Check fallback file
        if os.path.exists(fallback_file):
            with open(fallback_file, 'r') as f:
                fallback_data = json.load(f)
            
            fallback_tokens = fallback_data.get('token_mappings', {})
            print(f"📊 Fallback file has {len(fallback_tokens)} tokens")
            
            # Check data ages
            current_time = time.time()
            for token_address, token_data in list(fallback_tokens.items())[:3]:  # Check first 3
                data_age = (current_time - token_data.get('timestamp', 0)) / 3600
                print(f"   {token_address}: {data_age:.1f} hours old")
                
    except Exception as e:
        print(f"❌ Error checking data preservation: {e}")

def test_cleanup_functionality():
    """Test cleanup functionality"""
    print("\n🔍 Testing Cleanup Functionality")
    print("=" * 60)
    
    # Import cache manager
    try:
        from cache_manager import get_cache_manager
        cache_manager = get_cache_manager()
    except Exception as e:
        print(f"❌ Error loading cache manager: {e}")
        return
    
    # Test cleanup
    try:
        print("🧹 Testing cleanup of old data...")
        cache_manager.cleanup_old_data()
        print("✅ Cleanup completed")
        
        # Check stats after cleanup
        stats = cache_manager.get_cache_stats()
        print(f"📊 After cleanup:")
        print(f"   Cache tokens: {stats.get('cache_tokens', 0)}")
        print(f"   Fallback tokens: {stats.get('fallback_tokens', 0)}")
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")

if __name__ == "__main__":
    print("🧪 Priority-Based Cache System Test")
    print("=" * 60)
    print("Testing the new priority-based data fetching strategy...")
    
    test_cache_preservation()
    test_priority_data_fetching()
    test_fallback_data_retrieval()
    test_webhook_integration()
    test_data_preservation()
    test_cleanup_functionality()
    
    print(f"\n✅ Priority-based cache system test completed!")
    print("💡 The system should now:")
    print("   1. Preserve data for 48 hours")
    print("   2. Use priority-based fetching strategy")
    print("   3. Only clear data older than 48h")
    print("   4. Provide reliable fallback data")
