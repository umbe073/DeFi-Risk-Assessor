#!/usr/bin/env python3
"""
Fix Token Data Viewer with Real Values
Directly updates the problematic tokens with their real market data
"""

import pandas as pd
import json

def fix_token_data_viewer():
    """Fix the Token Data Viewer CSV with real data"""
    print("🔧 Fixing Token Data Viewer with Real Data")
    print("=" * 50)
    
    # Load the CSV
    csv_file = '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv'
    df = pd.read_csv(csv_file)
    
    # Real data for problematic tokens (from our fetch)
    real_data = {
        'DAI': {'market_cap': 4576288980, 'volume_24h': 141509431},
        'MKR': {'market_cap': 0, 'volume_24h': 836097},  # MKR has 0 market cap but some volume
        'SUSHI': {'market_cap': 130561549, 'volume_24h': 26350949},
        'GRT': {'market_cap': 866372367, 'volume_24h': 26915416},
        '1INCH': {'market_cap': 347305992, 'volume_24h': 19855735}
    }
    
    # Update the DataFrame
    updated_count = 0
    
    for index, row in df.iterrows():
        symbol = row.get('Symbol', '')
        
        if symbol in real_data:
            data = real_data[symbol]
            
            # Update market cap
            if data['market_cap'] > 0:
                df.at[index, 'Market Cap'] = f"${data['market_cap']:,.2f}"
            else:
                df.at[index, 'Market Cap'] = "N/A"
            
            # Update volume
            if data['volume_24h'] > 0:
                df.at[index, 'Volume 24h'] = f"${data['volume_24h']:,.2f}"
            else:
                df.at[index, 'Volume 24h'] = "N/A"
            
            updated_count += 1
            print(f"✅ Updated {symbol}: MC=${data['market_cap']:,.0f}, Vol=${data['volume_24h']:,.0f}")
    
    # Save the updated CSV
    output_files = [
        '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv',
        '/Users/amlfreak/Desktop/venv/data/token_data_viewer_export.csv',
        '/Users/amlfreak/Desktop/venv/data/tokens_enhanced.csv'
    ]
    
    for output_file in output_files:
        df.to_csv(output_file, index=False)
        print(f"✅ Saved to {output_file}")
    
    print(f"\n📊 Updated {updated_count} tokens with real data")
    return True

if __name__ == "__main__":
    fix_token_data_viewer()









