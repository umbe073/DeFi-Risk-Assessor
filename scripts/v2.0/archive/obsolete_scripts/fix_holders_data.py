#!/usr/bin/env python3
"""
Fix Holders Data - Get Real Holders from Webhook Cache
Properly extracts real holders data for each token
"""

import os
import sys
import json
import pandas as pd

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def fix_holders_data():
    """Fix holders data by getting real values from webhook cache"""
    print("👥 Fixing Holders Data - Real Values Only")
    print("=" * 50)
    
    # Load current CSV
    csv_file = '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv'
    df = pd.read_csv(csv_file)
    
    # Load webhook cache
    cache_file = '/Users/amlfreak/Desktop/venv/data/real_data_cache.json'
    cache_data = {}
    
    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        print(f"✅ Loaded webhook cache with {len(cache_data.get('tokens', {}))} tokens")
    except Exception as e:
        print(f"❌ Failed to load webhook cache: {e}")
        return False
    
    # Token address mappings
    token_addresses = {
        'AAVE': '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9',
        'CHZ': '0x3506424f91fd33084466f402d5d97f05f8e3b4af',
        'COMP': '0xc00e94cb662c3520282e6f5717214004a7f26888',
        'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'USDT': '0xdac17f958d2ee523a2206206994597c13d831ec7',
        'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
        'LINK': '0x514910771af9ca656af840dff83e8264ecf986ca',
        '1INCH': '0x111111111117dc0aa78b770fa6a738034120c302',
        'POL': '0x455e53CBB86018Ac2B8092FdCd39d8444aFFC3F6',
        'UNI': '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984',
        'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
        'GRT': '0xc944e90c64b2c07662a292be6244bdf05cda44a7',
        'MKR': '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2',
        'SUSHI': '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2',
        'QNT': '0x4a220e6096b25eadb88358cb44068a3248254675',
        'GALA': '0x15D4c048F83bd7e37d49eA4C83a07267Ec4203dA',
        'MANA': '0x0f5d2fb29fb7d3cfee444a200298f468908cc942',
        'SAND': '0x3845badAde8e6dFF049820680d1F14bD3903a5d0',
        'BAT': '0x0d8775f648430679a709e98d2b0cb6250d2887ef',
        'OP': '0x4200000000000000000000000000000000000042',
        'TRX': '0xf230b790e05390fc8295f4d3f60332c93bed42e2',
        'S': '0x00000000000000000000000000000000000SONIC'
    }
    
    updated_count = 0
    
    for index, row in df.iterrows():
        symbol = row.get('Symbol', '')
        token_name = row.get('Token', '')
        
        if symbol in token_addresses:
            address = token_addresses[symbol]
            print(f"\n🔍 Processing {token_name} ({symbol})")
            
            # Get real holders data from cache
            holders_data = get_real_holders_from_cache(cache_data, address)
            
            if holders_data > 0:
                df.at[index, 'Holders'] = f"{holders_data:,.0f}"
                print(f"  ✅ Updated Holders: {holders_data:,.0f}")
                updated_count += 1
            else:
                print(f"  ⚠️  No holders data found for {symbol}")
    
    # Save updated CSV files
    output_files = [
        '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv',
        '/Users/amlfreak/Desktop/venv/data/token_data_viewer_export.csv',
        '/Users/amlfreak/Desktop/venv/data/tokens_enhanced.csv'
    ]
    
    for output_file in output_files:
        try:
            df.to_csv(output_file, index=False)
            print(f"✅ Saved updated data to {output_file}")
        except Exception as e:
            print(f"❌ Failed to save {output_file}: {e}")
    
    print(f"\n📊 Summary:")
    print(f"  Updated {updated_count} tokens with real holders data")
    
    return True

def get_real_holders_from_cache(cache_data, address):
    """Get real holders data from webhook cache"""
    try:
        tokens = cache_data.get('tokens', {})
        
        # Try exact match first
        if address in tokens:
            token_data = tokens[address]
            aggregates = token_data.get('aggregates', {})
            onchain = aggregates.get('onchain', {})
            holders = onchain.get('holders', 0)
            
            if holders > 0:
                return holders
        
        # Try case-insensitive match
        for cache_address, token_data in tokens.items():
            if cache_address.lower() == address.lower():
                aggregates = token_data.get('aggregates', {})
                onchain = aggregates.get('onchain', {})
                holders = onchain.get('holders', 0)
                
                if holders > 0:
                    return holders
        
        # Try to find by checking individual data sources
        for cache_address, token_data in tokens.items():
            if cache_address.lower() == address.lower():
                # Check individual data sources
                onchain_data = token_data.get('onchain_data', {})
                for source, data in onchain_data.items():
                    if isinstance(data, dict) and 'holders' in data:
                        holders = data['holders']
                        if holders > 0:
                            return holders
                
                # Check market data sources for holders
                market_data = token_data.get('market_data', {})
                for source, data in market_data.items():
                    if isinstance(data, dict) and 'holders' in data:
                        holders = data['holders']
                        if holders > 0:
                            return holders
        
        return 0
        
    except Exception as e:
        print(f"    ❌ Cache lookup error: {e}")
        return 0

if __name__ == "__main__":
    success = fix_holders_data()
    
    if success:
        print("\n✅ Holders data fix completed!")
    else:
        print("\n❌ Holders data fix failed!")









