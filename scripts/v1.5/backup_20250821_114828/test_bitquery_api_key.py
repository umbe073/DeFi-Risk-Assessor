#!/usr/bin/env python3
"""
Test BitQuery with regular API key format
"""

import requests
import json

def test_bitquery_api_key_format():
    """Test if BitQuery works with regular API key format"""
    
    print("🔍 Testing BitQuery API Key Format")
    print("=" * 40)
    
    # Your current token (might work as API key)
    current_token = "ory_at_-FednFPbTxaiuu8phvKlKHWiE3t1vYNQqyxdjtSWd6M.GSPEM_9iBY5ZHt6xLKD-yXZEF0TRSazU94I6Q8tXK7Y"
    
    url = "https://graphql.bitquery.io"
    
    # Test with X-API-KEY header (regular API key format)
    headers = {
        'X-API-KEY': current_token,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "query": "{ ethereum { blocks(limit: 1) { height } } }"
    }
    
    print(f"Testing with X-API-KEY header...")
    print(f"Token: {current_token[:20]}...{current_token[-20:]}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS! BitQuery works with X-API-KEY format!")
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:200]}...")
            return True
        elif response.status_code == 401:
            print("❌ Still unauthorized - need different API key")
        elif response.status_code == 402:
            print("⚠️ Billing required - but API key format might be correct")
        else:
            print(f"❌ Error: {response.status_code}")
            if response.text:
                print(f"Details: {response.text[:200]}")
                
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
    
    return False

def provide_solution():
    """Provide the solution"""
    print("\n💡 SOLUTION:")
    print("-" * 15)
    print("You need to get a REGULAR API KEY from BitQuery, not an Ory token.")
    print("\nSteps:")
    print("1. Go to https://bitquery.io/")
    print("2. Login to your account")
    print("3. Look for 'API Keys' or 'Developer' section")
    print("4. Generate a new API key (should be shorter, like 32 chars)")
    print("5. Use X-API-KEY header format")
    print("\nThe current token is an Ory access token, which requires billing setup.")
    print("A regular API key should work without billing requirements.")

if __name__ == "__main__":
    success = test_bitquery_api_key_format()
    
    if not success:
        provide_solution()
