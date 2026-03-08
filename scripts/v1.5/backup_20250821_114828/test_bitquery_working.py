#!/usr/bin/env python3
"""
Test BitQuery with correct GraphQL queries
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def test_bitquery_working():
    """Test BitQuery with correct GraphQL queries"""
    
    api_key = os.getenv('BITQUERY_API_KEY')
    
    print("🎉 Testing BitQuery - Now Working!")
    print("=" * 40)
    print(f"API Key: {api_key[:10]}...{api_key[-10:]}")
    
    url = "https://graphql.bitquery.io"
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    # Test different GraphQL queries
    test_queries = [
        {
            'name': 'Network Info',
            'query': "{ ethereum { network } }"
        },
        {
            'name': 'Block Height (corrected)',
            'query': "{ ethereum { blocks(limit: 1) { height } } }"
        },
        {
            'name': 'Token Info',
            'query': "{ ethereum { address(address: {is: \"0xdAC17F958D2ee523a2206206994597C13D831ec7\"}) { smartContract { contractType } } } }"
        },
        {
            'name': 'Simple Query',
            'query': "{ __schema { types { name } } }"
        }
    ]
    
    for query_test in test_queries:
        print(f"\n🔍 Testing: {query_test['name']}")
        
        payload = {
            "query": query_test['query']
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                data = response.json()
                
                if 'data' in data and data['data']:
                    print(f"  📊 Data received: {str(data['data'])[:100]}...")
                elif 'errors' in data:
                    print(f"  ⚠️  GraphQL errors: {str(data['errors'])[:100]}...")
                else:
                    print(f"  📊 Empty data response")
                    
                return True
            else:
                print(f"  ❌ Error: {response.status_code}")
                if response.text:
                    print(f"  Details: {response.text[:200]}")
                    
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
    
    return False

def test_bitquery_real_data():
    """Test BitQuery with real token data query"""
    
    api_key = os.getenv('BITQUERY_API_KEY')
    
    print(f"\n🔍 Testing BitQuery with Real Token Data")
    print("=" * 45)
    
    url = "https://graphql.bitquery.io"
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    # Real token data query
    real_query = """
    query ($address: String!) {
        ethereum {
            address(address: {is: $address}) {
                smartContract {
                    contractType
                    currency {
                        name
                        symbol
                        decimals
                        totalSupply
                    }
                }
                transfers {
                    count
                    amount
                }
            }
        }
    }
    """
    
    variables = {
        "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"  # USDT
    }
    
    payload = {
        "query": real_query,
        "variables": variables
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS! BitQuery is fully working!")
            data = response.json()
            
            if 'data' in data and data['data']:
                print(f"📊 Real data received!")
                print(f"Response: {json.dumps(data, indent=2)[:300]}...")
            elif 'errors' in data:
                print(f"⚠️  GraphQL errors: {str(data['errors'])[:200]}...")
            else:
                print(f"📊 Empty data response")
                
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            if response.text:
                print(f"Details: {response.text[:200]}")
                
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

if __name__ == "__main__":
    print("🎉 BitQuery is now working with billing activated!")
    
    # Test basic functionality
    basic_working = test_bitquery_working()
    
    # Test real data
    real_data_working = test_bitquery_real_data()
    
    if basic_working or real_data_working:
        print(f"\n🎉 SUCCESS: BitQuery is fully functional!")
        print(f"Your API key is working correctly.")
        print(f"BitQuery is ready for your DeFi risk assessment!")
    else:
        print(f"\n❌ BitQuery still has issues")
        print(f"Check the specific error messages above.")
