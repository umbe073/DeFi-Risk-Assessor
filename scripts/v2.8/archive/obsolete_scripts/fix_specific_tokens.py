#!/usr/bin/env python3
"""
Fix Specific Tokens with Missing Data
Targets USDT, WBTC, LINK, POL, MKR specifically
"""

import os
import sys
import json
import pandas as pd

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def fix_specific_tokens():
    """Fix specific tokens with missing data"""
    print("🔧 Fixing Specific Tokens with Missing Data")
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
    
    # Specific token mappings
    token_mappings = {
        'USDT': '0xdac17f958d2ee523a2206206994597c13d831ec7',
        'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
        'LINK': '0x514910771af9ca656af840dff83e8264ecf986ca',
        'POL': '0x455e53CBB86018Ac2B8092FdCd39d8444aFFC3F6',
        'MKR': '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2'
    }
    
    # Process each token
    updated_count = 0
    
    for index, row in df.iterrows():
        symbol = row.get('Symbol', '')
        
        if symbol in token_mappings:
            address = token_mappings[symbol]
            print(f"\n🔍 Processing {symbol} ({address})")
            
            # Find token data in cache
            token_data = cache_data.get('tokens', {}).get(address.lower(), {})
            
            if token_data:
                aggregates = token_data.get('aggregates', {})
                market = aggregates.get('market', {})
                onchain = aggregates.get('onchain', {})
                liquidity = aggregates.get('liquidity', {})
                
                # Update market data
                market_cap = market.get('market_cap', 0)
                volume_24h = market.get('volume_24h', 0)
                holders = onchain.get('holders', 0)
                liquidity_value = liquidity.get('liquidity', 0)
                
                print(f"  📊 Found data: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,.0f}, Liq=${liquidity_value:,.0f}")
                
                # Update the DataFrame
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
                print(f"  ❌ No cache data found for {symbol}")
    
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
    print(f"  Updated {updated_count} tokens with specific data")
    print(f"  CSV now has {len(df)} tokens")
    
    return True

if __name__ == "__main__":
    success = fix_specific_tokens()
    
    if success:
        print("\n✅ Specific token fix completed!")
    else:
        print("\n❌ Specific token fix failed!")









