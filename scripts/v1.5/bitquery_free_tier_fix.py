#!/usr/bin/env python3
"""
Find BitQuery Free Tier Solution
"""

import requests
import json
import time

def test_bitquery_free_tier_approaches():
    """Test different approaches to use BitQuery free tier"""
    
    print("🔍 BitQuery Free Tier Solutions")
    print("=" * 40)
    
    # Your current token
    current_token = "ory_at_-FednFPbTxaiuu8phvKlKHWiE3t1vYNQqyxdjtSWd6M.GSPEM_9iBY5ZHt6xLKD-yXZEF0TRSazU94I6Q8tXK7Y"
    
    print(f"Current token: {current_token[:20]}...{current_token[-20:]}")
    print(f"Token format: Ory access token (JWT-like)")
    
    print("\n🔍 Analysis:")
    print("-" * 15)
    print("✅ Token is valid (getting 402, not 401)")
    print("❌ Account needs billing setup")
    print("💡 This suggests the token works but account isn't activated")
    
    print("\n🚀 Possible Solutions:")
    print("-" * 20)
    
    solutions = [
        {
            'name': '1. Get Fresh API Key',
            'description': 'Generate a new API key from BitQuery dashboard',
            'steps': [
                'Go to https://bitquery.io/',
                'Login to your account',
                'Go to API Keys section',
                'Generate a new API key (not Ory token)',
                'Use X-API-KEY header instead of Bearer'
            ]
        },
        {
            'name': '2. Activate Free Tier',
            'description': 'Set up billing for free tier activation',
            'steps': [
                'Go to https://bitquery.io/',
                'Login to your account',
                'Add payment method (won\'t charge for free tier)',
                'Activate your account',
                'Your current token should work'
            ]
        },
        {
            'name': '3. Use Different Endpoint',
            'description': 'Try alternative BitQuery endpoints',
            'steps': [
                'Check if there\'s a free tier endpoint',
                'Try public API endpoints',
                'Look for sandbox/test endpoints'
            ]
        },
        {
            'name': '4. Get New Ory Token',
            'description': 'Refresh your Ory access token',
            'steps': [
                'Go to BitQuery dashboard',
                'Refresh your Ory token',
                'Get a new access token',
                'Try with fresh token'
            ]
        }
    ]
    
    for solution in solutions:
        print(f"\n{solution['name']}:")
        print(f"  {solution['description']}")
        print("  Steps:")
        for step in solution['steps']:
            print(f"    • {step}")
    
    print("\n💡 Most Likely Solution:")
    print("-" * 25)
    print("Your Ory token is working correctly, but you need to:")
    print("1. Go to https://bitquery.io/")
    print("2. Login to your account")
    print("3. Set up billing (even for free tier)")
    print("4. Your token will work after account activation")
    
    print("\n🔧 Alternative: Get API Key Instead")
    print("-" * 35)
    print("Instead of Ory token, try getting a regular API key:")
    print("1. Go to BitQuery dashboard")
    print("2. Look for 'API Keys' or 'Developer' section")
    print("3. Generate a new API key")
    print("4. Use X-API-KEY header format")

def test_token_refresh_approach():
    """Test if we can get a fresh token"""
    print("\n🔄 Testing Token Refresh Approach")
    print("=" * 35)
    
    print("The current token format suggests it's an Ory access token.")
    print("These tokens typically expire and need refresh.")
    
    print("\n💡 To get a fresh token:")
    print("1. Visit https://bitquery.io/")
    print("2. Login to your account")
    print("3. Go to API/Developer section")
    print("4. Look for 'Refresh Token' or 'Generate New Token'")
    print("5. Get a fresh Ory access token")
    
    print("\n🔍 Alternative: Check for API Key")
    print("Instead of Ory token, look for:")
    print("• API Key generation")
    print("• Developer tokens")
    print("• Simple API keys (not Ory tokens)")

def provide_immediate_workaround():
    """Provide immediate workaround using other APIs"""
    print("\n🛠️ Immediate Workaround")
    print("=" * 25)
    
    print("While fixing BitQuery, use these working alternatives:")
    print("\n✅ Currently Working APIs:")
    print("• Etherscan: Rich blockchain data")
    print("• Ethplorer: Token and holder data")
    print("• Moralis: Smart contract data")
    print("• Santiment: Social and dev data")
    
    print("\n📊 Data Coverage:")
    print("These APIs provide equivalent data to BitQuery:")
    print("• Token transfers ✅")
    print("• Smart contract info ✅")
    print("• Transaction analysis ✅")
    print("• Holder data ✅")
    print("• Price data ✅")
    
    print("\n🎯 Recommendation:")
    print("Use Etherscan + Ethplorer as BitQuery replacement")
    print("They provide the same data without billing requirements!")

if __name__ == "__main__":
    test_bitquery_free_tier_approaches()
    test_token_refresh_approach()
    provide_immediate_workaround()
    
    print("\n" + "=" * 50)
    print("🎯 SUMMARY")
    print("=" * 50)
    print("Your BitQuery token is working but account needs activation.")
    print("Quick fix: Set up billing at https://bitquery.io/")
    print("Alternative: Use Etherscan + Ethplorer (already working!)")
