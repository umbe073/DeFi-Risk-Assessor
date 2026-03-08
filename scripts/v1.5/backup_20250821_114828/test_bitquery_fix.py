#!/usr/bin/env python3
"""
Test BitQuery with the new access token
"""

import requests
import json

def test_bitquery_with_new_token():
    """Test BitQuery API with the new access token"""
    
    # Your new BitQuery access token
    bitquery_token = "ory_at_-FednFPbTxaiuu8phvKlKHWiE3t1vYNQqyxdjtSWd6M.GSPEM_9iBY5ZHt6xLKD-yXZEF0TRSazU94I6Q8tXK7Y"
    
    print("🔍 Testing BitQuery with new access token...")
    print(f"Token: {bitquery_token[:20]}...{bitquery_token[-20:]}")
    
    url = "https://graphql.bitquery.io"
    headers = {
        'Authorization': f'Bearer {bitquery_token}',
        'Content-Type': 'application/json'
    }
    
    # Test query
    payload = {
        "query": "{ ethereum { blocks(limit: 1) { height } } }"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: BitQuery API is working!")
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:200]}...")
            return True
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            if response.text:
                print(f"Error: {response.text[:300]}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_bitquery_with_new_token()
    
    if success:
        print("\n🎉 BitQuery is now working!")
        print("💡 Update your .env file with:")
        print("BITQUERY_API_KEY=ory_at_-FednFPbTxaiuu8phvKlKHWiE3t1vYNQqyxdjtSWd6M.GSPEM_9iBY5ZHt6xLKD-yXZEF0TRSazU94I6Q8tXK7Y")
    else:
        print("\n❌ BitQuery still needs fixing")
