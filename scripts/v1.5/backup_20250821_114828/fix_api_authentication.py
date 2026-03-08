#!/usr/bin/env python3
"""
Fix API Authentication for Zapper, Breadcrumbs, and Twitter
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def test_zapper_authentication():
    """Test different Zapper authentication methods"""
    
    zapper_key = os.getenv('ZAPPER_API_KEY')
    
    print("🔍 Testing Zapper Authentication Methods")
    print("=" * 45)
    print(f"Zapper Key: {zapper_key[:10]}...{zapper_key[-10:]}")
    print(f"Format: UUID (looks correct)")
    
    url = "https://api.zapper.xyz/v2/prices"
    
    # Test different authentication methods
    test_methods = [
        {
            'name': 'Basic Auth (current)',
            'headers': {'Authorization': f'Basic {zapper_key}'}
        },
        {
            'name': 'Bearer Token',
            'headers': {'Authorization': f'Bearer {zapper_key}'}
        },
        {
            'name': 'API Key Header',
            'headers': {'X-API-Key': zapper_key}
        },
        {
            'name': 'Zapper API Key Header',
            'headers': {'X-Zapper-API-Key': zapper_key}
        },
        {
            'name': 'API Key in URL',
            'headers': {},
            'url_suffix': f'?apiKey={zapper_key}'
        }
    ]
    
    for method in test_methods:
        print(f"\n🔍 Testing: {method['name']}")
        
        test_url = url
        if 'url_suffix' in method:
            test_url += method['url_suffix']
        
        try:
            response = requests.get(test_url, headers=method['headers'], timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                data = response.json()
                print(f"  📊 Data received: {str(data)[:100]}...")
                return method['name']
            elif response.status_code == 401:
                print(f"  ❌ Unauthorized")
                if response.text:
                    print(f"  Error: {response.text[:100]}")
            elif response.status_code == 403:
                print(f"  ❌ Forbidden")
                if response.text:
                    print(f"  Error: {response.text[:100]}")
            else:
                print(f"  ❌ Error: {response.status_code}")
                if response.text:
                    print(f"  Details: {response.text[:100]}")
                    
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
    
    return None

def test_breadcrumbs_authentication():
    """Test different Breadcrumbs authentication methods"""
    
    breadcrumbs_key = os.getenv('BREADCRUMBS_API_KEY')
    
    print("\n🔍 Testing Breadcrumbs Authentication Methods")
    print("=" * 50)
    print(f"Breadcrumbs Key: {breadcrumbs_key[:10]}...{breadcrumbs_key[-10:]}")
    print(f"Format: Alphanumeric (looks like Bearer token)")
    
    url = "https://api.breadcrumbs.app/v1/addresses/0xdAC17F958D2ee523a2206206994597C13D831ec7"
    
    # Test different authentication methods
    test_methods = [
        {
            'name': 'Bearer Token (current)',
            'headers': {'Authorization': f'Bearer {breadcrumbs_key}'}
        },
        {
            'name': 'API Key Header',
            'headers': {'X-API-Key': breadcrumbs_key}
        },
        {
            'name': 'Breadcrumbs API Key',
            'headers': {'X-Breadcrumbs-API-Key': breadcrumbs_key}
        },
        {
            'name': 'Basic Auth',
            'headers': {'Authorization': f'Basic {breadcrumbs_key}'}
        },
        {
            'name': 'API Key in URL',
            'headers': {},
            'url_suffix': f'?apiKey={breadcrumbs_key}'
        }
    ]
    
    for method in test_methods:
        print(f"\n🔍 Testing: {method['name']}")
        
        test_url = url
        if 'url_suffix' in method:
            test_url += method['url_suffix']
        
        try:
            response = requests.get(test_url, headers=method['headers'], timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                data = response.json()
                print(f"  📊 Data received: {str(data)[:100]}...")
                return method['name']
            elif response.status_code == 401:
                print(f"  ❌ Unauthorized")
                if response.text:
                    print(f"  Error: {response.text[:100]}")
            elif response.status_code == 403:
                print(f"  ❌ Forbidden")
                if response.text:
                    print(f"  Error: {response.text[:100]}")
            else:
                print(f"  ❌ Error: {response.status_code}")
                if response.text:
                    print(f"  Details: {response.text[:100]}")
                    
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
    
    return None

def test_twitter_authentication():
    """Test different Twitter authentication methods"""
    
    twitter_key = os.getenv('TWITTER_API_KEY')
    
    print("\n🔍 Testing Twitter Authentication Methods")
    print("=" * 45)
    print(f"Twitter Key: {twitter_key[:10]}...{twitter_key[-10:]}")
    print(f"Format: Short alphanumeric (might be incomplete)")
    
    url = "https://api.twitter.com/2/users/by/username/elonmusk"
    
    # Test different authentication methods
    test_methods = [
        {
            'name': 'Bearer Token (current)',
            'headers': {'Authorization': f'Bearer {twitter_key}'}
        },
        {
            'name': 'OAuth2 Bearer',
            'headers': {'Authorization': f'Bearer {twitter_key}'}
        },
        {
            'name': 'API Key Header',
            'headers': {'X-API-Key': twitter_key}
        },
        {
            'name': 'Twitter API Key',
            'headers': {'X-Twitter-API-Key': twitter_key}
        }
    ]
    
    for method in test_methods:
        print(f"\n🔍 Testing: {method['name']}")
        
        try:
            response = requests.get(url, headers=method['headers'], timeout=10)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS!")
                data = response.json()
                print(f"  📊 Data received: {str(data)[:100]}...")
                return method['name']
            elif response.status_code == 401:
                print(f"  ❌ Unauthorized")
                if response.text:
                    print(f"  Error: {response.text[:100]}")
            elif response.status_code == 403:
                print(f"  ❌ Forbidden")
                if response.text:
                    print(f"  Error: {response.text[:100]}")
            elif response.status_code == 429:
                print(f"  ⚠️  Rate Limited (API working)")
                return method['name']
            else:
                print(f"  ❌ Error: {response.status_code}")
                if response.text:
                    print(f"  Details: {response.text[:100]}")
                    
        except Exception as e:
            print(f"  ❌ Exception: {str(e)}")
    
    return None

def provide_fix_instructions():
    """Provide specific fix instructions for each API"""
    
    print("\n💡 Fix Instructions for Each API")
    print("=" * 40)
    
    print("\n1️⃣ Zapper API Fix:")
    print("-" * 20)
    print("• Go to: https://zapper.xyz/")
    print("• Login to your account")
    print("• Go to Developer/API section")
    print("• Generate a new API key")
    print("• Check if it's a different format (not UUID)")
    print("• Try both Basic and Bearer authentication")
    
    print("\n2️⃣ Breadcrumbs API Fix:")
    print("-" * 25)
    print("• Go to: https://breadcrumbs.app/")
    print("• Login to your account")
    print("• Go to API section")
    print("• Generate a new Bearer token")
    print("• Make sure it's a proper Bearer token format")
    print("• Check if account needs activation")
    
    print("\n3️⃣ Twitter API Fix:")
    print("-" * 20)
    print("• Go to: https://developer.twitter.com/")
    print("• Login to your account")
    print("• Go to your app settings")
    print("• Get a proper Bearer Token")
    print("• Current key seems too short (25 chars)")
    print("• Twitter Bearer tokens are usually longer")
    
    print("\n🔧 Alternative Solutions:")
    print("-" * 25)
    print("• Use Etherscan/Ethplorer instead of Zapper")
    print("• Use CertiK instead of Breadcrumbs")
    print("• Use Reddit/Telegram instead of Twitter")

if __name__ == "__main__":
    print("🔧 Fixing API Authentication Issues")
    print("=" * 45)
    
    # Test each API
    zapper_method = test_zapper_authentication()
    breadcrumbs_method = test_breadcrumbs_authentication()
    twitter_method = test_twitter_authentication()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Authentication Test Results")
    print("=" * 50)
    
    if zapper_method:
        print(f"✅ Zapper: Working with {zapper_method}")
    else:
        print(f"❌ Zapper: Needs authentication fix")
    
    if breadcrumbs_method:
        print(f"✅ Breadcrumbs: Working with {breadcrumbs_method}")
    else:
        print(f"❌ Breadcrumbs: Needs authentication fix")
    
    if twitter_method:
        print(f"✅ Twitter: Working with {twitter_method}")
    else:
        print(f"❌ Twitter: Needs authentication fix")
    
    # Provide fix instructions
    provide_fix_instructions()
