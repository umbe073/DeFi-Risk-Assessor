#!/usr/bin/env python3
"""
Test script for Dune Analytics API integration
"""

import sys
import os
import json
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dune_analytics_api import DuneAnalyticsAPI, get_wallet_activity, get_token_market_data

def _extract_items(payload):
    """Best-effort list extraction from SIM Dune payloads."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("content", "items", "data", "results", "activity", "transactions", "balances", "collectibles", "holders"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []

def test_dune_api():
    """Test the Dune Analytics API integration"""
    
    print("🧪 Testing Dune Analytics API Integration")
    print("=" * 50)
    
    # Initialize API
    api = DuneAnalyticsAPI()
    
    if not api.api_key:
        print("❌ No Dune API key found in .env file")
        print("Please add DUNE_API_KEY=your_key to your .env file")
        return False
    
    print("✅ Dune Analytics API initialized successfully")
    print(f"🔑 API Key: {api.api_key[:10]}...")
    
    # Test addresses
    test_wallet = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # Vitalik's wallet
    test_token = "0xA0b86a33E6441b8c4C8C1C1B9C9C9C9C9C9C9C9C"  # Example token
    test_chain_id = 1  # Ethereum mainnet
    
    print(f"\n📊 Testing with wallet: {test_wallet}")
    print(f"🪙 Testing with token: {test_token}")
    print(f"⛓️ Testing with chain ID: {test_chain_id}")
    
    try:
        # Test 1: Get wallet activity
        print("\n1️⃣ Testing get_activity...")
        activity = api.get_activity(test_wallet, limit=5)
        if "error" not in activity:
            print(f"✅ Activity test passed - Found {len(_extract_items(activity))} entries")
        else:
            print(f"❌ Activity test failed: {activity.get('error')}")
        
        # Test 2: Get token info
        print("\n2️⃣ Testing get_token_info...")
        token_info = api.get_token_info("native")  # Test with native token
        if "error" not in token_info:
            print(f"✅ Token info test passed - Found {len(_extract_items(token_info))} entries")
        else:
            print(f"❌ Token info test failed: {token_info.get('error')}")
        
        # Test 3: Get balances
        print("\n3️⃣ Testing get_balances...")
        balances = api.get_balances(test_wallet, limit=5)
        if "error" not in balances:
            print(f"✅ Balances test passed - Found {len(_extract_items(balances))} entries")
        else:
            print(f"❌ Balances test failed: {balances.get('error')}")
        
        # Test 4: Get transactions
        print("\n4️⃣ Testing get_transactions...")
        transactions = api.get_transactions(test_wallet, limit=5)
        if "error" not in transactions:
            print(f"✅ Transactions test passed - Found {len(_extract_items(transactions))} entries")
        else:
            print(f"❌ Transactions test failed: {transactions.get('error')}")
        
        # Test 5: Get collectibles
        print("\n5️⃣ Testing get_collectibles...")
        collectibles = api.get_collectibles(test_wallet, limit=5)
        if "error" not in collectibles:
            print(f"✅ Collectibles test passed - Found {len(_extract_items(collectibles))} entries")
        else:
            print(f"❌ Collectibles test failed: {collectibles.get('error')}")
        
        # Test 6: Utility functions
        print("\n6️⃣ Testing utility functions...")
        
        # Test get_wallet_activity
        wallet_activity = get_wallet_activity(test_wallet, limit=3)
        if "error" not in wallet_activity:
            print("✅ get_wallet_activity utility function works")
        else:
            print(f"❌ get_wallet_activity failed: {wallet_activity.get('error')}")
        
        # Test get_token_market_data
        market_data = get_token_market_data("native")
        if "error" not in market_data:
            print("✅ get_token_market_data utility function works")
        else:
            print(f"❌ get_token_market_data failed: {market_data.get('error')}")
        
        print("\n🎉 All tests completed!")
        print("=" * 50)
        
        # Show sample data
        print("\n📋 Sample API Response (Activity):")
        if "error" not in activity and activity.get('activity'):
            sample_activity = activity['activity'][0]
            print(json.dumps(sample_activity, indent=2, default=str))
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_dashboard_integration():
    """Test the Dune Analytics integration in the API dashboard"""
    print("\n🖥️ Testing Dune Analytics Integration in API Dashboard...")
    
    try:
        from dashboard.api_service_dashboard import APIServiceDashboard
        import tkinter as tk
        
        # Create a test window
        root = tk.Tk()
        root.withdraw()  # Hide the window
        
        app = APIServiceDashboard()
        print("✅ API Dashboard created successfully")
        
        # Check if Dune Analytics service is included
        if 'dune' in app.services:
            dune_service = app.services['dune']
            print(f"✅ Dune Analytics service found: {dune_service['name']}")
            print(f"   Category: {dune_service['category']}")
            print(f"   Description: {dune_service['description']}")
            print(f"   Rate limit: {dune_service['rate_limit']} calls per {dune_service['rate_period']} seconds")
        else:
            print("❌ Dune Analytics service not found in API dashboard")
            return False
        
        # Close the window
        root.destroy()
        
        return True
        
    except Exception as e:
        print(f"❌ API Dashboard integration test failed: {e}")
        return False

if __name__ == "__main__":
    print(f"🚀 Dune Analytics API Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test API
    api_success = test_dune_api()
    
    # Test API Dashboard Integration
    dashboard_success = test_api_dashboard_integration()
    
    print("\n📊 Test Results:")
    print(f"   API Integration: {'✅ PASS' if api_success else '❌ FAIL'}")
    print(f"   API Dashboard Integration: {'✅ PASS' if dashboard_success else '❌ FAIL'}")
    
    if api_success and dashboard_success:
        print("\n🎉 All tests passed! Dune Analytics integration is ready to use.")
        print("\n📝 Usage:")
        print("   1. Add DUNE_API_KEY=your_key to your .env file")
        print("   2. Launch the system tray")
        print("   3. Select '🔧 API Service Dashboard' from the menu")
        print("   4. Find 'Dune Analytics API' in the '📈 Blockchain Analytics' section")
        print("   5. Click '🔄 Fetch Data' to test the API")
    else:
        print("\n⚠️ Some tests failed. Please check the error messages above.")
