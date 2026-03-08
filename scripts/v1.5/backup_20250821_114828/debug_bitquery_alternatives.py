#!/usr/bin/env python3
"""
Debug BitQuery Authentication - Find the working method
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def test_bitquery_methods():
    """Test all possible BitQuery authentication methods"""
    
    # Your BitQuery access token
    bitquery_token = "ory_at_-FednFPbTxaiuu8phvKlKHWiE3t1vYNQqyxdjtSWd6M.GSPEM_9iBY5ZHt6xLKD-yXZEF0TRSazU94I6Q8tXK7Y"
    
    print("🔍 Testing All BitQuery Authentication Methods")
    print("=" * 50)
    
    url = "https://graphql.bitquery.io"
    
    # Test different authentication methods
    test_methods = [
        {
            'name': 'Bearer Token (current)',
            'headers': {
                'Authorization': f'Bearer {bitquery_token}',
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'X-API-KEY Header',
            'headers': {
                'X-API-KEY': bitquery_token,
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'API-Key Header',
            'headers': {
                'API-Key': bitquery_token,
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'X-API-KEY (different case)',
            'headers': {
                'X-API-KEY': bitquery_token,
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'Authorization Basic',
            'headers': {
                'Authorization': f'Basic {bitquery_token}',
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'No Authorization (public endpoint)',
            'headers': {
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'User-Agent with token',
            'headers': {
                'User-Agent': f'BitQuery-Client/{bitquery_token}',
                'Content-Type': 'application/json'
            }
        }
    ]
    
    # Different query types to test
    test_queries = [
        {
            'name': 'Simple Block Query',
            'query': "{ ethereum { blocks(limit: 1) { height } } }"
        },
        {
            'name': 'Public Data Query',
            'query': "{ ethereum { network } }"
        },
        {
            'name': 'Token Info Query',
            'query': "{ ethereum { address(address: {is: \"0xdAC17F958D2ee523a2206206994597C13D831ec7\"}) { smartContract { contractType } } } }"
        },
        {
            'name': 'Network Status Query',
            'query': "{ ethereum { blocks(limit: 1) { timestamp { time } } } }"
        }
    ]
    
    for method in test_methods:
        print(f"\n🔍 Testing: {method['name']}")
        print("-" * 40)
        
        for query_test in test_queries:
            print(f"  Query: {query_test['name']}")
            
            payload = {
                "query": query_test['query']
            }
            
            try:
                response = requests.post(url, json=payload, headers=method['headers'], timeout=10)
                
                print(f"    Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"    ✅ SUCCESS!")
                    data = response.json()
                    if 'data' in data and data['data']:
                        print(f"    📊 Data received: {str(data['data'])[:100]}...")
                    else:
                        print(f"    📊 Empty data response")
                    return method, query_test
                elif response.status_code == 401:
                    print(f"    ❌ Unauthorized")
                elif response.status_code == 402:
                    print(f"    ⚠️  Billing required")
                elif response.status_code == 403:
                    print(f"    ❌ Forbidden")
                else:
                    print(f"    ❌ Error: {response.status_code}")
                    if response.text:
                        print(f"    Details: {response.text[:200]}")
                        
            except Exception as e:
                print(f"    ❌ Exception: {str(e)}")
    
    return None, None

def test_alternative_endpoints():
    """Test alternative BitQuery endpoints"""
    print("\n🔍 Testing Alternative BitQuery Endpoints")
    print("=" * 45)
    
    bitquery_token = "ory_at_-FednFPbTxaiuu8phvKlKHWiE3t1vYNQqyxdjtSWd6M.GSPEM_9iBY5ZHt6xLKD-yXZEF0TRSazU94I6Q8tXK7Y"
    
    alternative_endpoints = [
        "https://graphql.bitquery.io",
        "https://api.bitquery.io/graphql",
        "https://streaming.bitquery.io/graphql",
        "https://bitquery.io/graphql",
        "https://graphql.bitquery.io/graphql"
    ]
    
    headers = {
        'Authorization': f'Bearer {bitquery_token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "query": "{ ethereum { blocks(limit: 1) { height } } }"
    }
    
    for endpoint in alternative_endpoints:
        print(f"\n🔍 Testing endpoint: {endpoint}")
        
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                return endpoint
            elif response.status_code == 401:
                print(f"  ❌ Unauthorized")
            elif response.status_code == 402:
                print(f"  ⚠️  Billing required")
            else:
                print(f"  ❌ Error: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
    
    return None

def test_public_queries():
    """Test if there are any public queries that don't require authentication"""
    print("\n🔍 Testing Public BitQuery Queries")
    print("=" * 40)
    
    url = "https://graphql.bitquery.io"
    
    public_queries = [
        {
            'name': 'Network Info',
            'query': "{ ethereum { network } }"
        },
        {
            'name': 'Block Height',
            'query': "{ ethereum { blocks(limit: 1) { height } } }"
        },
        {
            'name': 'Simple Query',
            'query': "{ __schema { types { name } } }"
        }
    ]
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    for query_test in public_queries:
        print(f"\n🔍 Testing: {query_test['name']}")
        
        payload = {
            "query": query_test['query']
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS! Public query works!")
                data = response.json()
                print(f"  📊 Response: {str(data)[:200]}...")
                return query_test
            else:
                print(f"  ❌ Failed: {response.status_code}")
                if response.text:
                    print(f"  Details: {response.text[:200]}")
                    
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
    
    return None

def check_bitquery_documentation():
    """Check BitQuery documentation for correct usage"""
    print("\n📚 BitQuery Documentation Check")
    print("=" * 35)
    
    print("🔍 Checking BitQuery docs for authentication methods...")
    print("\nPossible solutions:")
    print("1. Check if token needs to be refreshed")
    print("2. Verify if there's a different endpoint for free tier")
    print("3. Check if there are public queries available")
    print("4. Verify if token format is correct")
    print("5. Check if there's a different authentication method")
    
    print("\n💡 Next steps:")
    print("• Visit https://bitquery.io/docs")
    print("• Check if there's a free tier endpoint")
    print("• Verify token format and expiration")
    print("• Look for public API access")

if __name__ == "__main__":
    # Test all authentication methods
    working_method, working_query = test_bitquery_methods()
    
    if working_method:
        print(f"\n🎉 SUCCESS! Found working method:")
        print(f"Method: {working_method['name']}")
        print(f"Query: {working_query['name']}")
    else:
        print("\n❌ No working authentication method found")
        
        # Test alternative endpoints
        working_endpoint = test_alternative_endpoints()
        if working_endpoint:
            print(f"\n🎉 Found working endpoint: {working_endpoint}")
        
        # Test public queries
        working_public = test_public_queries()
        if working_public:
            print(f"\n🎉 Found working public query: {working_public['name']}")
        
        # Check documentation
        check_bitquery_documentation()
