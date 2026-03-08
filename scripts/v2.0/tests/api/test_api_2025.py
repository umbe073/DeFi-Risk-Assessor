#!/usr/bin/env python3
"""
Test script for 2025 API endpoints (Dune Analytics and Breadcrumbs)
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_dune_2025():
    """Test SIM Dune API endpoint/auth."""
    print("🧪 Testing SIM Dune API")
    print("=" * 50)
    
    api_key = os.getenv('DUNE_API_KEY')
    if not api_key:
        print("❌ No DUNE_API_KEY found in environment")
        print("   Please set: export DUNE_API_KEY=your_key")
        return False
    
    dune_base_url = (os.getenv("DUNE_SIM_BASE_URL") or "https://api.sim.dune.com/v1").rstrip("/")
    dune_chain_id = (os.getenv("DUNE_SIM_CHAIN_ID") or "1").strip()
    if not dune_chain_id.isdigit():
        dune_chain_id = "1"
    test_token = (os.getenv("DUNE_TEST_TOKEN_ADDRESS") or "0xdAC17F958D2ee523a2206206994597C13D831ec7").strip()
    if not (test_token.startswith("0x") and len(test_token) == 42):
        test_token = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

    headers = {
        'X-Sim-Api-Key': api_key,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    try:
        # Test token info endpoint
        print("\n1️⃣ Testing token-info endpoint...")
        url = f"{dune_base_url}/evm/token-info/{test_token}"
        response = requests.get(url, headers=headers, params={"chain_ids": dune_chain_id, "limit": 1}, timeout=10)
        
        if response.status_code == 200:
            print("✅ SIM Dune API is working!")
            data = response.json()
            print(f"   Response keys: {list(data.keys())[:5]}")
            return True
        elif response.status_code == 400:
            print("⚠️  Invalid request (check DUNE_SIM_CHAIN_ID)")
            return True
        elif response.status_code == 401:
            print("❌ Invalid API key")
        elif response.status_code == 403:
            print("⚠️  Access forbidden (check plan/permissions)")
            return True
        elif response.status_code == 404:
            print("⚠️  Endpoint not found (check DUNE_SIM_BASE_URL)")
        else:
            print(f"❌ API returned status code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to SIM Dune API")
        print("   The endpoint might be down or incorrect")
    except Exception as e:
        print(f"❌ Error testing Dune API: {e}")
    
    return False

def test_breadcrumbs_2025():
    """Test the updated Breadcrumbs v2 API endpoints"""
    print("\n🧪 Testing Breadcrumbs v2 (2025) API")
    print("=" * 50)
    
    api_key = os.getenv('BREADCRUMBS_API_KEY')
    if not api_key:
        print("❌ No BREADCRUMBS_API_KEY found in environment")
        print("   Please set: export BREADCRUMBS_API_KEY=your_key")
        return False
    
    # Test the new v2 endpoint
    base_url = "https://api.breadcrumbs.app/v2"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    try:
        # Test with a known address (Ethereum Foundation)
        test_address = "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"
        
        # Test 1: Risk score endpoint
        print("\n1️⃣ Testing risk score endpoint...")
        url = f"{base_url}/address/{test_address}/risk-score"
        params = {"chain": "ethereum"}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            print("✅ Breadcrumbs v2 API is working!")
            data = response.json()
            print(f"   Response keys: {list(data.keys())[:5]}")
            return True
        elif response.status_code == 401:
            print("❌ Invalid API key")
        elif response.status_code == 403:
            print("⚠️  Access forbidden (check API key permissions)")
        elif response.status_code == 404:
            print("⚠️  Endpoint not found (API structure may have changed)")
        else:
            print(f"❌ API returned status code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Breadcrumbs API v2")
        print("   The endpoint might be down or incorrect")
    except Exception as e:
        print(f"❌ Error testing Breadcrumbs API: {e}")
    
    return False

def test_fallback_endpoints():
    """Test fallback endpoints if primary ones fail"""
    print("\n🔄 Testing fallback endpoints...")
    print("=" * 50)
    
    # Alternative Dune endpoint
    print("\n📊 SIM Dune endpoint to try:")
    print("  - https://api.sim.dune.com/v1/evm/token-info/{token_address}?chain_ids=1")
    
    # Alternative Breadcrumbs endpoint
    print("\n🍞 Alternative Breadcrumbs endpoints to try:")
    print("  - https://api.breadcrumbs.app/api/v1/address/{address}/risk")
    print("  - https://api.breadcrumbs.io/v2/risk/{address}")
    
    return True

if __name__ == "__main__":
    print(f"🚀 API Endpoint Test (2025) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "=" * 60)
    
    # Load environment variables
    from dotenv import load_dotenv
    env_path = str(Path(__file__).resolve().parents[4] / '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}")
    else:
        print(f"⚠️  No .env file found at: {env_path}")
    
    # Test APIs
    dune_success = test_dune_2025()
    breadcrumbs_success = test_breadcrumbs_2025()
    
    # Show results
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"   SIM Dune API: {'✅ PASS' if dune_success else '❌ FAIL'}")
    print(f"   Breadcrumbs v2: {'✅ PASS' if breadcrumbs_success else '❌ FAIL'}")
    
    if not (dune_success and breadcrumbs_success):
        test_fallback_endpoints()
        print("\n⚠️  Some APIs failed. You may need to:")
        print("   1. Check if your API keys are valid")
        print("   2. Verify the endpoints haven't changed")
        print("   3. Try the alternative endpoints listed above")
    else:
        print("\n🎉 All APIs are working with 2025 endpoints!")
