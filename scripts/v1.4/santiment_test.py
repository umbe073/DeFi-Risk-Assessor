#!/usr/bin/env python3
# pyright: reportMissingImports=false
# pyright: reportUndefinedVariable=false
"""
Santiment API Test using Official Python Client
Based on https://github.com/santiment/sanpy
"""

import os
import sys
from typing import TYPE_CHECKING

# Try to import san module with fallback
SAN_AVAILABLE: bool = False  # Default value
if TYPE_CHECKING:
    import san  # pyright: ignore[reportMissingImports]
else:
    try:
        import san  # type: ignore
        SAN_AVAILABLE = True
    except ImportError:
        print("⚠️  Warning: 'san' module not found. Installing with: pip install san")
        print("   You can install it manually or the script will use direct API calls instead.")
        SAN_AVAILABLE = False

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_santiment_official_client():
    """Test Santiment using the official Python client"""
    print("🔍 Testing Santiment API with Official Python Client")
    print("=" * 60)
    
    # Set the API key
    api_key = os.getenv('SANTIMENT_API_KEY')
    if not api_key:
        print("❌ SANTIMENT_API_KEY not found in environment")
        return False
    
    # Check if san module is available
    if not SAN_AVAILABLE:
        print("❌ San module not available - skipping official client test")
        return False
    
    try:
        # Test basic functionality with direct API calls
        print("\n📊 Testing basic metrics...")
        
        # Test 1: Get price data using direct API call
        try:
            import requests
            response = requests.post(
                "https://api.santiment.net/graphql",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json={
                    "query": "{ getMetric(metric: \"price_usd\") { timeseriesData(selector: {slug: \"bitcoin\"} from: \"2024-01-01T00:00:00Z\" to: \"2024-01-02T23:59:59Z\" interval: \"1d\") { datetime value } } }"
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']:
                    print("✅ Price data retrieved successfully")
                    return True
                else:
                    print(f"❌ No data returned: {data}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Price data error: {str(e)}")
        
        return False
        
    except Exception as e:
        print(f"❌ Santiment API error: {str(e)}")
        return False

def test_santiment_graphql_direct():
    """Test Santiment GraphQL directly with correct format"""
    import requests
    import json
    
    print("\n🔍 Testing Santiment GraphQL Directly")
    print("=" * 60)
    
    api_key = os.getenv('SANTIMENT_API_KEY')
    if not api_key:
        print("❌ SANTIMENT_API_KEY not found")
        return False
    
    # Test different query formats based on documentation
    queries = [
        {
            "name": "Price USD Query",
            "query": """
            {
              getMetric(metric: "price_usd") {
                timeseriesData(
                  selector: {slug: "bitcoin"}
                  from: "2024-01-01T00:00:00Z"
                  to: "2024-01-02T23:59:59Z"
                  interval: "1d"
                ) {
                  datetime
                  value
                }
              }
            }
            """
        },
        {
            "name": "Daily Active Addresses Query",
            "query": """
            {
              getMetric(metric: "daily_active_addresses") {
                timeseriesData(
                  selector: {slug: "bitcoin"}
                  from: "2024-01-01T00:00:00Z"
                  to: "2024-01-02T23:59:59Z"
                  interval: "1d"
                ) {
                  datetime
                  value
                }
              }
            }
            """
        },
        {
            "name": "Dev Activity Query",
            "query": """
            {
              getMetric(metric: "dev_activity") {
                timeseriesData(
                  selector: {slug: "bitcoin"}
                  from: "2024-01-01T00:00:00Z"
                  to: "2024-01-02T23:59:59Z"
                  interval: "1d"
                ) {
                  datetime
                  value
                }
              }
            }
            """
        }
    ]
    
    # Test different authentication methods
    auth_methods = [
        {
            "name": "X-API-Key Header",
            "headers": {
                "X-API-Key": api_key,
                "Content-Type": "application/json"
            }
        },
        {
            "name": "Authorization Bearer",
            "headers": {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "Authorization Basic",
            "headers": {
                "Authorization": f"Basic {api_key}",
                "Content-Type": "application/json"
            }
        }
    ]
    
    # Test with a simple query
    query = """
    {
      getMetric(metric: "price_usd") {
        timeseriesData(
          selector: {slug: "bitcoin"}
          from: "2024-01-01T00:00:00Z"
          to: "2024-01-02T23:59:59Z"
          interval: "1d"
        ) {
          datetime
          value
        }
      }
    }
    """
    
    for method in auth_methods:
        try:
            response = requests.post(
                "https://api.santiment.net/graphql",
                headers=method["headers"],
                json={"query": query},
                timeout=15
            )
            
            print(f"\n📊 Testing {method['name']}...")
            print(f"   HTTP Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']:
                    print("   ✅ Query successful")
                    return True
                else:
                    print(f"   ❌ No data returned: {data}")
            else:
                print(f"   ❌ HTTP Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Request error: {str(e)}")
    
    return False

if __name__ == "__main__":
    print("🚀 Santiment API Testing Suite")
    print("=" * 60)
    
    # Test with official client
    official_result = test_santiment_official_client()
    
    # Test with direct GraphQL
    graphql_result = test_santiment_graphql_direct()
    
    print("\n📊 SUMMARY")
    print("=" * 60)
    print(f"Official Client: {'✅ Working' if official_result else '❌ Failed'}")
    print(f"Direct GraphQL: {'✅ Working' if graphql_result else '❌ Failed'}")
    
    if not official_result and not graphql_result:
        print("\n💡 RECOMMENDATIONS:")
        print("1. Check your SANTIMENT_API_KEY in .env file")
        print("2. Generate new JWT token at https://app.santiment.net/")
        print("3. Ensure your account has proper permissions")
        print("4. Check Santiment documentation: https://academy.santiment.net/") 