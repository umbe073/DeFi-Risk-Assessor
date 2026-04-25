#!/usr/bin/env python3
"""
Comprehensive Data Fix for Token Data Viewer
Fixes all missing data issues systematically
"""

import os
import sys
import json
import pandas as pd

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def comprehensive_data_fix():
    """Comprehensive fix for all data issues"""
    print("🔧 Comprehensive Data Fix for Token Data Viewer")
    print("=" * 60)
    
    # Load current CSV
    csv_file = '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv'
    df = pd.read_csv(csv_file)
    
    # Load webhook cache data
    cache_file = '/Users/amlfreak/Desktop/venv/data/real_data_cache.json'
    cache_data = {}
    
    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        print(f"✅ Loaded webhook cache with {len(cache_data.get('tokens', {}))} tokens")
    except Exception as e:
        print(f"❌ Failed to load webhook cache: {e}")
        return False
    
    # Load fallback data
    fallback_file = '/Users/amlfreak/Desktop/venv/data/token_fallbacks.json'
    fallback_data = {}
    
    try:
        with open(fallback_file, 'r') as f:
            fallback_data = json.load(f)
        print(f"✅ Loaded fallback data with {len(fallback_data)} tokens")
    except Exception as e:
        print(f"⚠️  No fallback data found: {e}")
    
    # Token address mappings
    token_mappings = {
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
    
    # Process each token
    updated_count = 0
    
    for index, row in df.iterrows():
        symbol = row.get('Symbol', '')
        token_name = row.get('Token', '')
        
        print(f"\n🔍 Processing {token_name} ({symbol})")
        
        # Get token address
        address = token_mappings.get(symbol)
        if not address:
            print(f"  ⚠️  No address mapping found for {symbol}")
            continue
        
        # Try to get data from webhook cache first
        token_data = cache_data.get('tokens', {}).get(address.lower(), {})
        
        if token_data:
            aggregates = token_data.get('aggregates', {})
            market = aggregates.get('market', {})
            onchain = aggregates.get('onchain', {})
            liquidity = aggregates.get('liquidity', {})
            
            market_cap = market.get('market_cap', 0)
            volume_24h = market.get('volume_24h', 0)
            holders = onchain.get('holders', 0)
            liquidity_value = liquidity.get('liquidity', 0)
            
            print(f"  📊 Cache data: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,.0f}, Liq=${liquidity_value:,.0f}")
            
            # Update the DataFrame with cache data
            if market_cap > 0:
                df.at[index, 'Market Cap'] = f"${market_cap:,.2f}"
                print(f"  ✅ Updated Market Cap: ${market_cap:,.2f}")
            
            if volume_24h > 0:
                df.at[index, 'Volume 24h'] = f"${volume_24h:,.2f}"
                print(f"  ✅ Updated Volume 24h: ${volume_24h:,.2f}")
            
            if holders > 0:
                df.at[index, 'Holders'] = f"{holders:,.0f}"
                print(f"  ✅ Updated Holders: {holders:,.0f}")
            
            if liquidity_value > 0:
                df.at[index, 'Liquidity'] = f"${liquidity_value:,.2f}"
                print(f"  ✅ Updated Liquidity: ${liquidity_value:,.2f}")
            else:
                df.at[index, 'Liquidity'] = "N/A"
                print(f"  ⚠️  No liquidity data, set to N/A")
            
            updated_count += 1
        else:
            # Try fallback data
            fallback_token = fallback_data.get(address.lower(), {})
            if fallback_token:
                market_data = fallback_token.get('market_data', {}).get('existing_cache', {})
                onchain_data = fallback_token.get('onchain_data', {}).get('existing_cache', {})
                
                market_cap = market_data.get('market_cap', 0)
                volume_24h = market_data.get('volume_24h', 0)
                holders = onchain_data.get('holders', 0)
                
                print(f"  📊 Fallback data: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,.0f}")
                
                if market_cap > 0:
                    df.at[index, 'Market Cap'] = f"${market_cap:,.2f}"
                    print(f"  ✅ Updated Market Cap from fallback: ${market_cap:,.2f}")
                
                if volume_24h > 0:
                    df.at[index, 'Volume 24h'] = f"${volume_24h:,.2f}"
                    print(f"  ✅ Updated Volume 24h from fallback: ${volume_24h:,.2f}")
                
                if holders > 0:
                    df.at[index, 'Holders'] = f"{holders:,.0f}"
                    print(f"  ✅ Updated Holders from fallback: {holders:,.0f}")
                
                df.at[index, 'Liquidity'] = "N/A"
                print(f"  ⚠️  No liquidity data in fallback, set to N/A")
                
                updated_count += 1
            else:
                print(f"  ❌ No data found for {symbol}")
    
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
    print(f"  Updated {updated_count} tokens with data")
    print(f"  CSV now has {len(df)} tokens")
    
    return True

if __name__ == "__main__":
    success = comprehensive_data_fix()
    
    if success:
        print("\n✅ Comprehensive data fix completed!")
    else:
        print("\n❌ Comprehensive data fix failed!")









