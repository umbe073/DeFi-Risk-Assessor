#!/usr/bin/env python3
"""
Fetch Real Data for Problematic Tokens
Fetches real market data for tokens that are showing fallback/simulated values
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def fetch_real_data_for_tokens():
    """Fetch real data for problematic tokens"""
    print("🔄 Fetching Real Data for Problematic Tokens")
    print("=" * 60)
    
    # Problematic tokens that are showing fallback data
    problematic_tokens = [
        {
            'address': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'symbol': 'DAI',
            'name': 'Dai',
            'coingecko_id': 'dai'
        },
        {
            'address': '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2',
            'symbol': 'MKR',
            'name': 'MakerDAO',
            'coingecko_id': 'maker'
        },
        {
            'address': '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2',
            'symbol': 'SUSHI',
            'name': 'SushiSwap',
            'coingecko_id': 'sushi'
        },
        {
            'address': '0xc944e90c64b2c07662a292be6244bdf05cda44a7',
            'symbol': 'GRT',
            'name': 'The Graph',
            'coingecko_id': 'the-graph'
        },
        {
            'address': '0x111111111117dc0aa78b770fa6a738034120c302',
            'symbol': '1INCH',
            'name': '1inch',
            'coingecko_id': '1inch'
        }
    ]
    
    results = {}
    
    for token in problematic_tokens:
        print(f"\n🔍 Fetching real data for {token['name']} ({token['symbol']})")
        print("-" * 40)
        
        try:
            # Fetch from CoinGecko
            real_data = fetch_coingecko_data(token['coingecko_id'])
            if real_data:
                results[token['address']] = real_data
                print(f"✅ {token['symbol']}: MC=${real_data['market_cap']:,.0f}, Vol=${real_data['volume_24h']:,.0f}")
            else:
                print(f"❌ {token['symbol']}: No real data found")
                
        except Exception as e:
            print(f"❌ Error fetching {token['symbol']}: {e}")
    
    # Save results to a file
    if results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/Users/amlfreak/Desktop/venv/data/real_data_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Real data saved to: {filename}")
        
        # Update the webhook cache with real data
        update_webhook_cache(results)
    
    return results

def fetch_coingecko_data(coin_id):
    """Fetch real data from CoinGecko"""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true',
            'include_24hr_change': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if coin_id in data:
                coin_data = data[coin_id]
                return {
                    'market_cap': coin_data.get('usd_market_cap', 0),
                    'volume_24h': coin_data.get('usd_24h_vol', 0),
                    'price': coin_data.get('usd', 0),
                    'change_24h': coin_data.get('usd_24h_change', 0),
                    'source': 'real-time',
                    'timestamp': time.time()
                }
        else:
            print(f"    ❌ CoinGecko API error: {response.status_code}")
            
    except Exception as e:
        print(f"    ❌ CoinGecko fetch failed: {e}")
    
    return None

def update_webhook_cache(real_data):
    """Update webhook cache with real data"""
    try:
        cache_file = '/Users/amlfreak/Desktop/venv/data/real_data_cache.json'
        
        # Load existing cache
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
        else:
            cache_data = {'tokens': {}}
        
        # Update with real data
        for address, data in real_data.items():
            if 'tokens' not in cache_data:
                cache_data['tokens'] = {}
            
            cache_data['tokens'][address.lower()] = {
                'address': address,
                'timestamp': time.time(),
                'market_data': {
                    'coingecko': data
                },
                'aggregates': {
                    'market': {
                        'market_cap': data['market_cap'],
                        'volume_24h': data['volume_24h'],
                        'price': data['price'],
                        'change_24h': data['change_24h']
                    }
                },
                'source': 'real_time'
            }
        
        # Save updated cache
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"✅ Updated webhook cache with real data")
        
    except Exception as e:
        print(f"❌ Error updating webhook cache: {e}")

if __name__ == "__main__":
    results = fetch_real_data_for_tokens()
    if results:
        print(f"\n✅ Successfully fetched real data for {len(results)} tokens!")
    else:
        print(f"\n❌ No real data was fetched!")








