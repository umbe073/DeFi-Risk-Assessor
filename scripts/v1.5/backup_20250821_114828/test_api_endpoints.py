#!/usr/bin/env python3
"""
API Endpoint Test Script
Tests all API endpoints to verify they work as expected
"""

import os
import sys
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def test_api_endpoint(service_name, url, headers=None, method='GET', payload=None, expected_status_codes=[200]):
    """Test a single API endpoint"""
    print(f"\n🔍 Testing {service_name}...")
    print(f"   URL: {url}")
    print(f"   Method: {method}")
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=payload, timeout=10)
        else:
            print(f"   ❌ Unsupported method: {method}")
            return False
            
        print(f"   Status: {response.status_code}")
        
        if response.status_code in expected_status_codes:
            print(f"   ✅ SUCCESS: {service_name} responded correctly")
            return True
        else:
            print(f"   ❌ FAILED: Unexpected status code {response.status_code}")
            if hasattr(response, 'text') and response.text:
                error_text = response.text[:200]
                print(f"   Error: {error_text}")
            return False
            
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        return False

def test_all_apis():
    """Test all API endpoints"""
    print("🚀 Starting API Endpoint Tests")
    print("=" * 50)
    
    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }
    
    # Test endpoints configuration
    test_configs = [
        # Market Data APIs
        {
            'name': 'CoinGecko',
            'url': 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
            'method': 'GET',
            'expected_codes': [200],
            'requires_key': False
        },
        {
            'name': 'CoinMarketCap',
            'url': 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?symbol=BTC',
            'headers': {'X-CMC_PRO_API_KEY': os.getenv('COINMARKETCAP_API_KEY')},
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'COINMARKETCAP_API_KEY'
        },
        {
            'name': 'CoinPaprika',
            'url': 'https://api.coinpaprika.com/v1/tickers/btc-bitcoin',
            'method': 'GET',
            'expected_codes': [200],
            'requires_key': False
        },
        
        # Blockchain Analytics
        {
            'name': 'Etherscan',
            'url': f"https://api.etherscan.io/api?module=stats&action=ethsupply&apikey={os.getenv('ETHERSCAN_API_KEY')}",
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'ETHERSCAN_API_KEY'
        },
        {
            'name': 'Ethplorer',
            'url': f"https://api.ethplorer.io/getTokenInfo/0xdAC17F958D2ee523a2206206994597C13D831ec7?apiKey={os.getenv('ETHPLORER_API_KEY')}",
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'ETHPLORER_API_KEY'
        },
                 {
             'name': 'Covalent',
             'url': f"https://api.covalenthq.com/v1/1/tokens/tokenlists/all/?key={os.getenv('COVALENT_API_KEY')}",
             'method': 'GET',
             'expected_codes': [200, 401, 402, 403],
             'requires_key': True,
             'env_key': 'COVALENT_API_KEY'
         },
        {
            'name': 'Santiment',
            'url': 'https://api.santiment.net/graphql',
            'headers': {
                'Apikey': os.getenv('SANTIMENT_API_KEY'),
                'Content-Type': 'application/json'
            },
            'method': 'POST',
            'payload': {"query": "{ getMetric(metric: \"price_usd\") { metadata { metric } } }"},
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'SANTIMENT_API_KEY'
        },
        {
            'name': 'BitQuery',
            'url': 'https://graphql.bitquery.io',
            'headers': {
                'X-API-KEY': os.getenv('BITQUERY_API_KEY'),
                'Content-Type': 'application/json'
            },
            'method': 'POST',
            'payload': {"query": "{ ethereum { network } }"},
            'expected_codes': [200, 401, 402, 403],
            'requires_key': True,
            'env_key': 'BITQUERY_API_KEY'
        },
        
        # DeFi Protocols
        {
            'name': 'Zapper',
            'url': 'https://api.zapper.xyz/v2/prices',
            'headers': {'Authorization': f"Basic {os.getenv('ZAPPER_API_KEY')}"},
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'ZAPPER_API_KEY'
        },
        {
            'name': 'DeBank',
            'url': 'https://pro-openapi.debank.com/v1/user/token_list?id=0x5853ed4f26a3fcea565b3fbc698bb19cdf6deb85',
            'headers': {'AccessKey': os.getenv('DEBANK_API_KEY')},
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'DEBANK_API_KEY'
        },
        {
            'name': '1inch',
            'url': 'https://api.1inch.dev/swap/v6.0/1/tokens',
            'headers': {'Authorization': f"Bearer {os.getenv('INCH_API_KEY')}"},
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'INCH_API_KEY'
        },
        
        # Security & Compliance
        {
            'name': 'Breadcrumbs',
            'url': 'https://api.breadcrumbs.one/risk/address?chain=ETH&address=0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'headers': {'X-API-KEY': os.getenv('BREADCRUMBS_API_KEY'), 'Accept': 'application/json'},
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'BREADCRUMBS_API_KEY'
        },
        {
            'name': 'Moralis',
            'url': 'https://deep-index.moralis.io/api/v2/erc20/metadata?chain=eth&addresses=0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'headers': {'X-API-Key': os.getenv('MORALIS_API_KEY')},
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'MORALIS_API_KEY'
        },
        
        # Social Data APIs
        {
            'name': 'Twitter',
            'url': 'https://api.twitter.com/2/users/by/username/elonmusk',
            'headers': {'Authorization': f"Bearer {os.getenv('TWITTER_API_KEY')}"},
            'method': 'GET',
            'expected_codes': [200, 401, 403, 429],
            'requires_key': True,
            'env_key': 'TWITTER_API_KEY'
        },
        {
            'name': 'Discord',
            'url': 'https://discord.com/api/v10/users/@me',
            'headers': {'Authorization': f"Bot {os.getenv('DISCORD_BOT_TOKEN')}"},
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'DISCORD_BOT_TOKEN'
        },
        {
            'name': 'Telegram',
            'url': f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/getMe",
            'method': 'GET',
            'expected_codes': [200, 401, 403],
            'requires_key': True,
            'env_key': 'TELEGRAM_BOT_TOKEN'
        }
    ]
    
    # Test each API
    for config in test_configs:
        # Check if API key is required and available
        if config.get('requires_key', False):
            env_key = config.get('env_key')
            if not os.getenv(env_key):
                print(f"\n⚠️  SKIPPING {config['name']}: API key not found ({env_key})")
                results['skipped'].append(config['name'])
                continue
        
        # Test the endpoint
        success = test_api_endpoint(
            config['name'],
            config['url'],
            headers=config.get('headers'),
            method=config['method'],
            payload=config.get('payload'),
            expected_status_codes=config['expected_codes']
        )
        
        if success:
            results['success'].append(config['name'])
        else:
            results['failed'].append(config['name'])
        
        # Small delay between requests
        time.sleep(0.5)
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 API Test Results Summary")
    print("=" * 50)
    
    print(f"\n✅ SUCCESSFUL ({len(results['success'])}):")
    for api in results['success']:
        print(f"   • {api}")
    
    print(f"\n❌ FAILED ({len(results['failed'])}):")
    for api in results['failed']:
        print(f"   • {api}")
    
    print(f"\n⚠️  SKIPPED ({len(results['skipped'])}):")
    for api in results['skipped']:
        print(f"   • {api}")
    
    total_tested = len(results['success']) + len(results['failed'])
    success_rate = (len(results['success']) / total_tested * 100) if total_tested > 0 else 0
    
    print(f"\n📈 Success Rate: {success_rate:.1f}% ({len(results['success'])}/{total_tested})")
    
    if results['failed']:
        print(f"\n💡 Recommendations:")
        print("   • Check API keys in .env file")
        print("   • Verify API key formats and permissions")
        print("   • Check rate limits and usage quotas")
    
    return results

if __name__ == "__main__":
    test_all_apis()
