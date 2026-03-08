#!/usr/bin/env python3
"""
Test Enhanced API Endpoints
Tests the enhanced webhook server to ensure it fetches comprehensive data
"""

import os
import sys
import json
import time
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def test_enhanced_api():
    """Test the enhanced API endpoints"""
    print("🧪 Testing Enhanced API Endpoints")
    print("=" * 50)
    
    # Import the webhook server
    try:
        from webhook_server import WebhookServer
        server = WebhookServer()
        print("✅ Webhook server imported successfully")
    except Exception as e:
        print(f"❌ Failed to import webhook server: {e}")
        return False
    
    # Test tokens
    test_tokens = [
        '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9',  # AAVE
        '0x3506424f91fd33084466f402d5d97f05f8e3b4af',  # CHZ
        '0xc00e94cb662c3520282e6f5717214004a7f26888',  # COMP
    ]
    
    results = {}
    
    for token_address in test_tokens:
        print(f"\n🔍 Testing token: {token_address}")
        print("-" * 30)
        
        try:
            # Fetch comprehensive data
            start_time = time.time()
            data = server.fetch_real_time_data(token_address)
            end_time = time.time()
            
            fetch_time = end_time - start_time
            print(f"⏱️  Fetch time: {fetch_time:.2f} seconds")
            
            # Analyze the data
            analysis = analyze_token_data(data)
            results[token_address] = {
                'fetch_time': fetch_time,
                'analysis': analysis,
                'data': data
            }
            
            print(f"📊 Data Analysis:")
            print(f"  Market Data Sources: {len(data.get('market_data', {}))}")
            print(f"  Onchain Data Sources: {len(data.get('onchain_data', {}))}")
            print(f"  Liquidity Data Sources: {len(data.get('liquidity_data', {}))}")
            print(f"  Social Data Sources: {len(data.get('social_data', {}))}")
            
            # Check aggregates
            aggregates = data.get('aggregates', {})
            if aggregates:
                print(f"  📈 Aggregates:")
                for category, values in aggregates.items():
                    print(f"    {category}: {values}")
            
        except Exception as e:
            print(f"❌ Error testing {token_address}: {e}")
            results[token_address] = {'error': str(e)}
    
    # Generate summary report
    print(f"\n📋 Summary Report")
    print("=" * 50)
    
    successful_tests = 0
    total_tests = len(test_tokens)
    
    for token_address, result in results.items():
        if 'error' not in result:
            successful_tests += 1
            analysis = result['analysis']
            print(f"✅ {token_address}: {analysis['completeness']:.1f}% complete")
        else:
            print(f"❌ {token_address}: {result['error']}")
    
    print(f"\n📊 Overall Results:")
    print(f"  Successful: {successful_tests}/{total_tests}")
    print(f"  Success Rate: {(successful_tests/total_tests)*100:.1f}%")
    
    # Save detailed results
    save_results(results)
    
    return successful_tests == total_tests

def analyze_token_data(data):
    """Analyze the completeness of token data"""
    analysis = {
        'market_data_sources': len(data.get('market_data', {})),
        'onchain_data_sources': len(data.get('onchain_data', {})),
        'liquidity_data_sources': len(data.get('liquidity_data', {})),
        'social_data_sources': len(data.get('social_data', {})),
        'completeness': 0
    }
    
    # Calculate completeness score
    total_fields = 0
    filled_fields = 0
    
    # Check market data
    market_data = data.get('market_data', {})
    if market_data:
        for source, data in market_data.items():
            if data.get('market_cap', 0) > 0: filled_fields += 1
            if data.get('volume_24h', 0) > 0: filled_fields += 1
            if data.get('price', 0) > 0: filled_fields += 1
            total_fields += 3
    
    # Check onchain data
    onchain_data = data.get('onchain_data', {})
    if onchain_data:
        for source, data in onchain_data.items():
            if data.get('holders', 0) > 0: filled_fields += 1
            if data.get('total_supply', 0) > 0: filled_fields += 1
            total_fields += 2
    
    # Check liquidity data
    liquidity_data = data.get('liquidity_data', {})
    if liquidity_data:
        for source, data in liquidity_data.items():
            if data.get('liquidity', 0) > 0: filled_fields += 1
            if data.get('volume_24h', 0) > 0: filled_fields += 1
            total_fields += 2
    
    if total_fields > 0:
        analysis['completeness'] = (filled_fields / total_fields) * 100
    
    return analysis

def save_results(results):
    """Save test results to file"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/Users/amlfreak/Desktop/venv/data/enhanced_api_test_{timestamp}.json"
        
        # Convert results to JSON-serializable format
        json_results = {}
        for token_address, result in results.items():
            if 'error' in result:
                json_results[token_address] = {'error': result['error']}
            else:
                json_results[token_address] = {
                    'fetch_time': result['fetch_time'],
                    'analysis': result['analysis']
                }
        
        with open(filename, 'w') as f:
            json.dump(json_results, f, indent=2)
        
        print(f"💾 Results saved to: {filename}")
        
    except Exception as e:
        print(f"⚠️  Failed to save results: {e}")

if __name__ == "__main__":
    success = test_enhanced_api()
    if success:
        print("\n✅ Enhanced API test completed successfully!")
    else:
        print("\n❌ Enhanced API test completed with errors!")









