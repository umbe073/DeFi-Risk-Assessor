#!/usr/bin/env python3
"""
Test the new BitQuery API key
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def test_new_bitquery_key():
    """Test the new BitQuery API key"""
    
    # Get the new API key from .env
    new_api_key = os.getenv('BITQUERY_API_KEY')
    
    print("🔍 Testing New BitQuery API Key")
    print("=" * 40)
    print(f"New API Key: {new_api_key}")
    print(f"Format: UUID (looks correct!)")
    
    url = "https://graphql.bitquery.io"
    
    # Test with X-API-KEY header (correct format for API keys)
    headers = {
        'X-API-KEY': new_api_key,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "query": "{ ethereum { blocks(limit: 1) { height } } }"
    }
    
    print(f"\nTesting with X-API-KEY header...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS! BitQuery is working!")
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:200]}...")
            return True
        elif response.status_code == 401:
            print("❌ Still unauthorized")
            if response.text:
                print(f"Error: {response.text[:200]}")
        elif response.status_code == 402:
            print("⚠️ Billing required")
            if response.text:
                print(f"Error: {response.text[:200]}")
        else:
            print(f"❌ Error: {response.status_code}")
            if response.text:
                print(f"Details: {response.text[:200]}")
                
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

def test_alternative_headers():
    """Test alternative header formats"""
    
    new_api_key = os.getenv('BITQUERY_API_KEY')
    url = "https://graphql.bitquery.io"
    
    print(f"\n🔍 Testing Alternative Header Formats")
    print("=" * 45)
    
    test_headers = [
        {
            'name': 'Authorization Bearer',
            'headers': {
                'Authorization': f'Bearer {new_api_key}',
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'API-Key Header',
            'headers': {
                'API-Key': new_api_key,
                'Content-Type': 'application/json'
            }
        },
        {
            'name': 'X-API-KEY (current)',
            'headers': {
                'X-API-KEY': new_api_key,
                'Content-Type': 'application/json'
            }
        }
    ]
    
    payload = {
        "query": "{ ethereum { blocks(limit: 1) { height } } }"
    }
    
    for test in test_headers:
        print(f"\nTesting: {test['name']}")
        
        try:
            response = requests.post(url, json=payload, headers=test['headers'], timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                return test['name']
            elif response.status_code == 401:
                print(f"  ❌ Unauthorized")
            elif response.status_code == 402:
                print(f"  ⚠️  Billing required")
            else:
                print(f"  ❌ Error: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
    
    return None

if __name__ == "__main__":
    success = test_new_bitquery_key()
    
    if not success:
        working_method = test_alternative_headers()
        if working_method:
            print(f"\n🎉 Found working method: {working_method}")
        else:
            print(f"\n❌ No working method found")
            print(f"💡 The API key might need activation or different format")
