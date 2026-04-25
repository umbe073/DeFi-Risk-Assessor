#!/usr/bin/env python3
"""
Update Token Data Viewer with Fixed Data
Updates the Token Data Viewer CSV with real data instead of fallback values
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def update_token_data_viewer():
    """Update Token Data Viewer with real data"""
    print("🔄 Updating Token Data Viewer with Real Data")
    print("=" * 60)
    
    # Load the current CSV
    csv_file = '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv'
    try:
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} tokens from CSV")
    except Exception as e:
        print(f"❌ Failed to load CSV: {e}")
        return False
    
    # Load real data from webhook cache
    cache_file = '/Users/amlfreak/Desktop/venv/data/real_data_cache.json'
    real_data = {}
    
    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        tokens = cache_data.get('tokens', {})
        for address, data in tokens.items():
            aggregates = data.get('aggregates', {})
            market = aggregates.get('market', {})
            
            if market.get('market_cap', 0) > 0:
                real_data[address.lower()] = {
                    'market_cap': market.get('market_cap', 0),
                    'volume_24h': market.get('volume_24h', 0),
                    'price': market.get('price', 0),
                    'change_24h': market.get('change_24h', 0)
                }
        
        print(f"✅ Loaded real data for {len(real_data)} tokens from cache")
        
    except Exception as e:
        print(f"❌ Failed to load real data: {e}")
        return False
    
    # Create mapping of tokens to their real data
    token_mapping = {
        '0x6B175474E89094C44Da98b954EedeAC495271d0F': 'DAI',
        '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2': 'MKR', 
        '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2': 'SUSHI',
        '0xc944e90c64b2c07662a292be6244bdf05cda44a7': 'GRT',
        '0x111111111117dc0aa78b770fa6a738034120c302': '1INCH'
    }
    
    # Update the DataFrame with real data
    updated_count = 0
    
    for index, row in df.iterrows():
        symbol = row.get('Symbol', '')
        
        # Find matching real data by symbol
        real_data_found = None
        for address, data in real_data.items():
            # Check exact match first
            if address in token_mapping and token_mapping[address] == symbol:
                real_data_found = data
                break
            
            # Check case-insensitive match - simplified approach
            if address.lower() in [k.lower() for k in token_mapping.keys()]:
                mapped_symbol = token_mapping.get(address)
                if mapped_symbol == symbol:
                    real_data_found = data
                    break
        
        if real_data_found:
            # Update with real data
            df.at[index, 'Market Cap'] = f"${real_data_found['market_cap']:,.2f}"
            df.at[index, 'Volume 24h'] = f"${real_data_found['volume_24h']:,.2f}"
            
            updated_count += 1
            print(f"✅ Updated {symbol}: MC=${real_data_found['market_cap']:,.0f}, Vol=${real_data_found['volume_24h']:,.0f}")
    
    # Remove extra columns to match the 7 required columns
    required_columns = ['Token', 'Symbol', 'Chain', 'Market Cap', 'Volume 24h', 'Holders', 'Liquidity']
    df = df[required_columns]
    
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
    print(f"  Updated {updated_count} tokens with real data")
    print(f"  CSV now has {len(df)} tokens with {len(required_columns)} columns")
    
    return True

if __name__ == "__main__":
    success = update_token_data_viewer()
    if success:
        print("\n✅ Token Data Viewer updated successfully!")
    else:
        print("\n❌ Token Data Viewer update failed!")
