#!/usr/bin/env python3
"""
API Authentication Debug Script
Detailed analysis of authentication issues for each API
"""

import os
import requests
import json
import base64
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def debug_api_auth():
    """Debug authentication issues for each API"""
    print("🔍 API Authentication Debug Analysis")
    print("=" * 50)
    
    # Test configurations with detailed error analysis
    test_configs = [
        {
            'name': 'BitQuery',
            'url': 'https://graphql.bitquery.io',
            'methods': [
                {
                    'name': 'X-API-KEY Header',
                    'headers': {
                        'X-API-KEY': os.getenv('BITQUERY_API_KEY'),
                        'Content-Type': 'application/json'
                    }
                },
                {
                    'name': 'Authorization Bearer',
                    'headers': {
                        'Authorization': f"Bearer {os.getenv('BITQUERY_API_KEY')}",
                        'Content-Type': 'application/json'
                    }
                },
                {
                    'name': 'X-API-KEY (different format)',
                    'headers': {
                        'X-API-KEY': os.getenv('BITQUERY_API_KEY'),
                        'Authorization': f"Bearer {os.getenv('BITQUERY_API_KEY')}",
                        'Content-Type': 'application/json'
                    }
                }
            ],
            'payload': {"query": "{ ethereum { blocks(limit: 1) { height } } }"},
            'env_key': 'BITQUERY_API_KEY'
        },
        {
            'name': 'Zapper',
            'url': 'https://api.zapper.xyz/v2/prices',
            'methods': [
                {
                    'name': 'Basic Auth',
                    'headers': {'Authorization': f"Basic {os.getenv('ZAPPER_API_KEY')}"}
                },
                {
                    'name': 'Bearer Token',
                    'headers': {'Authorization': f"Bearer {os.getenv('ZAPPER_API_KEY')}"}
                },
                {
                    'name': 'API Key Header',
                    'headers': {'X-API-Key': os.getenv('ZAPPER_API_KEY')}
                }
            ],
            'env_key': 'ZAPPER_API_KEY'
        },
        {
            'name': 'DeBank',
            'url': 'https://pro-openapi.debank.com/v1/user/token_list?id=0x5853ed4f26a3fcea565b3fbc698bb19cdf6deb85',
            'methods': [
                {
                    'name': 'AccessKey Header',
                    'headers': {'AccessKey': os.getenv('DEBANK_API_KEY')}
                },
                {
                    'name': 'Authorization Bearer',
                    'headers': {'Authorization': f"Bearer {os.getenv('DEBANK_API_KEY')}"}
                },
                {
                    'name': 'X-API-Key Header',
                    'headers': {'X-API-Key': os.getenv('DEBANK_API_KEY')}
                }
            ],
            'env_key': 'DEBANK_API_KEY'
        },
        {
            'name': 'Breadcrumbs',
            'url': 'https://api.breadcrumbs.app/v1/addresses/0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'methods': [
                {
                    'name': 'Bearer Token',
                    'headers': {'Authorization': f"Bearer {os.getenv('BREADCRUMBS_API_KEY')}"}
                },
                {
                    'name': 'API Key Header',
                    'headers': {'X-API-Key': os.getenv('BREADCRUMBS_API_KEY')}
                },
                {
                    'name': 'Basic Auth',
                    'headers': {'Authorization': f"Basic {os.getenv('BREADCRUMBS_API_KEY')}"}
                }
            ],
            'env_key': 'BREADCRUMBS_API_KEY'
        },
        {
            'name': 'Twitter',
            'url': 'https://api.twitter.com/2/users/by/username/elonmusk',
            'methods': [
                {
                    'name': 'Bearer Token',
                    'headers': {'Authorization': f"Bearer {os.getenv('TWITTER_API_KEY')}"}
                },
                {
                    'name': 'OAuth2 Bearer',
                    'headers': {'Authorization': f"Bearer {os.getenv('TWITTER_API_KEY')}"}
                }
            ],
            'env_key': 'TWITTER_API_KEY'
        }
    ]
    
    for config in test_configs:
        print(f"\n🔍 Testing {config['name']} Authentication Methods")
        print("-" * 40)
        
        api_key = os.getenv(config['env_key'])
        if not api_key:
            print(f"❌ No API key found for {config['name']} ({config['env_key']})")
            print(f"   💡 Add {config['env_key']}=your_api_key to .env file")
            continue
        
        print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
        
        for method in config['methods']:
            print(f"\n   Testing: {method['name']}")
            
            try:
                if 'payload' in config:
                    response = requests.post(
                        config['url'], 
                        headers=method['headers'], 
                        json=config['payload'],
                        timeout=10
                    )
                else:
                    response = requests.get(
                        config['url'], 
                        headers=method['headers'],
                        timeout=10
                    )
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"   ✅ SUCCESS: {method['name']} works!")
                    break
                elif response.status_code in [401, 403]:
                    error_text = response.text[:300] if response.text else "No error details"
                    print(f"   ❌ AUTH ERROR: {response.status_code}")
                    print(f"   Error: {error_text}")
                    
                    # Provide specific guidance based on error
                    if 'invalid' in error_text.lower() or 'unauthorized' in error_text.lower():
                        print(f"   💡 Suggestion: Check API key format and permissions")
                    elif 'forbidden' in error_text.lower():
                        print(f"   💡 Suggestion: API key may be valid but lacks required permissions")
                    elif 'rate limit' in error_text.lower():
                        print(f"   💡 Suggestion: Rate limit exceeded - wait and retry")
                else:
                    print(f"   ⚠️  Other error: {response.status_code}")
                    if response.text:
                        print(f"   Details: {response.text[:200]}")
                        
            except Exception as e:
                print(f"   ❌ Exception: {str(e)}")
        
        print(f"\n   📋 {config['name']} API Key Analysis:")
        print(f"      Length: {len(api_key)} characters")
        print(f"      Format: {api_key[:5]}...{api_key[-5:] if len(api_key) > 10 else ''}")
        
        # Provide specific guidance for each API
        if config['name'] == 'BitQuery':
            print(f"      💡 BitQuery typically uses X-API-KEY header with 32-character keys")
        elif config['name'] == 'Zapper':
            print(f"      💡 Zapper may require API key registration at https://zapper.xyz/")
        elif config['name'] == 'DeBank':
            print(f"      💡 DeBank requires registration at https://debank.com/")
        elif config['name'] == 'Breadcrumbs':
            print(f"      💡 Breadcrumbs requires registration at https://breadcrumbs.app/")
        elif config['name'] == 'Twitter':
            print(f"      💡 Twitter requires Bearer Token from Twitter Developer Portal")

def check_api_key_formats():
    """Check if API keys match expected formats"""
    print("\n🔑 API Key Format Analysis")
    print("=" * 30)
    
    key_formats = {
        'BITQUERY_API_KEY': {
            'expected_length': 32,
            'format': 'alphanumeric',
            'example': 'BQY...'
        },
        'ZAPPER_API_KEY': {
            'expected_length': 'variable',
            'format': 'base64 or string',
            'example': 'Zapper API key from dashboard'
        },
        'DEBANK_API_KEY': {
            'expected_length': 'variable',
            'format': 'string',
            'example': 'DeBank access key'
        },
        'BREADCRUMBS_API_KEY': {
            'expected_length': 'variable',
            'format': 'string',
            'example': 'Bearer token from Breadcrumbs'
        },
        'TWITTER_API_KEY': {
            'expected_length': 'variable',
            'format': 'Bearer token',
            'example': 'Twitter Bearer Token'
        }
    }
    
    for key_name, format_info in key_formats.items():
        api_key = os.getenv(key_name)
        if api_key:
            print(f"\n{key_name}:")
            print(f"   Length: {len(api_key)} characters")
            print(f"   Expected: {format_info['expected_length']}")
            print(f"   Format: {format_info['format']}")
            print(f"   Example: {format_info['example']}")
            
            if format_info['expected_length'] != 'variable':
                if len(api_key) == format_info['expected_length']:
                    print(f"   ✅ Length matches expected format")
                else:
                    print(f"   ⚠️  Length doesn't match expected format")
        else:
            print(f"\n{key_name}: ❌ Not found")

def provide_solutions():
    """Provide specific solutions for each API"""
    print("\n💡 Solutions for Each API")
    print("=" * 30)
    
    solutions = {
        'BitQuery': [
            "1. Register at https://bitquery.io/",
            "2. Get API key from dashboard",
            "3. Use X-API-KEY header format",
            "4. Ensure 32-character alphanumeric key"
        ],
        'Zapper': [
            "1. Register at https://zapper.xyz/",
            "2. Get API key from developer dashboard",
            "3. Try both Basic and Bearer authentication",
            "4. Check API key permissions"
        ],
        'DeBank': [
            "1. Register at https://debank.com/",
            "2. Get AccessKey from developer portal",
            "3. Use AccessKey header format",
            "4. Check API usage limits"
        ],
        'Breadcrumbs': [
            "1. Register at https://breadcrumbs.app/",
            "2. Get Bearer token from dashboard",
            "3. Use Authorization: Bearer format",
            "4. Verify API key permissions"
        ],
        'Twitter': [
            "1. Register at https://developer.twitter.com/",
            "2. Create app and get Bearer Token",
            "3. Use Authorization: Bearer format",
            "4. Check app permissions and rate limits"
        ]
    }
    
    for api, steps in solutions.items():
        print(f"\n{api}:")
        for step in steps:
            print(f"   {step}")

if __name__ == "__main__":
    debug_api_auth()
    check_api_key_formats()
    provide_solutions()
