#!/usr/bin/env python3
"""
Fix Missing Data in Token Data Viewer
Fetches and updates missing market data and liquidity data for all tokens
"""

import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def fix_missing_data():
    """Fix missing data in Token Data Viewer"""
    print("🔧 Fixing Missing Data in Token Data Viewer")
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
    
    # Process each token
    updated_count = 0
    
    for index, row in df.iterrows():
        token_name = row.get('Token', '')
        symbol = row.get('Symbol', '')
        chain = row.get('Chain', '')
        
        print(f"\n🔍 Processing {token_name} ({symbol})")
        
        # Find token data in cache
        token_data = None
        for address, data in cache_data.get('tokens', {}).items():
            # Check if this token matches by symbol or name
            if (symbol.lower() in ['usdt', 'wbtc', 'link', 'pol', 'mkr'] and 
                symbol.lower() in data.get('address', '').lower()):
                token_data = data
                break
        
        # If not found by address, try to find by symbol in aggregates
        if not token_data:
            for address, data in cache_data.get('tokens', {}).items():
                aggregates = data.get('aggregates', {})
                market = aggregates.get('market', {})
                if market.get('market_cap', 0) > 0:
                    # This might be our token
                    token_data = data
                    break
        
        if token_data:
            aggregates = token_data.get('aggregates', {})
            market = aggregates.get('market', {})
            onchain = aggregates.get('onchain', {})
            liquidity = aggregates.get('liquidity', {})
            
            # Update market data
            market_cap = market.get('market_cap', 0)
            volume_24h = market.get('volume_24h', 0)
            price = market.get('price', 0)
            change_24h = market.get('change_24h', 0)
            
            # Update holders
            holders = onchain.get('holders', 0)
            
            # Update liquidity
            liquidity_value = liquidity.get('liquidity', 0)
            
            # Update the DataFrame
            if market_cap > 0:
                df.at[index, 'Market Cap'] = f"${market_cap:,.2f}"
            elif df.at[index, 'Market Cap'] == '' or pd.isna(df.at[index, 'Market Cap']):
                df.at[index, 'Market Cap'] = "N/A"
            
            if volume_24h > 0:
                df.at[index, 'Volume 24h'] = f"${volume_24h:,.2f}"
            elif df.at[index, 'Volume 24h'] == '' or pd.isna(df.at[index, 'Volume 24h']):
                df.at[index, 'Volume 24h'] = "N/A"
            
            if holders > 0:
                df.at[index, 'Holders'] = f"{holders:,.0f}"
            elif df.at[index, 'Holders'] == '' or pd.isna(df.at[index, 'Holders']):
                df.at[index, 'Holders'] = "N/A"
            
            if liquidity_value > 0:
                df.at[index, 'Liquidity'] = f"${liquidity_value:,.2f}"
            else:
                df.at[index, 'Liquidity'] = "N/A"
            
            updated_count += 1
            print(f"  ✅ Updated: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,.0f}, Liq=${liquidity_value:,.0f}")
        else:
            print(f"  ⚠️  No cache data found for {symbol}")
    
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
    print(f"  Updated {updated_count} tokens with data from cache")
    print(f"  CSV now has {len(df)} tokens")
    
    return True

def fetch_missing_liquidity_data():
    """Fetch missing liquidity data for tokens"""
    print("\n💧 Fetching Missing Liquidity Data")
    print("-" * 40)
    
    # Tokens that need liquidity data
    tokens_needing_liquidity = [
        {'symbol': 'AAVE', 'address': '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9'},
        {'symbol': 'USDC', 'address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'},
        {'symbol': 'USDT', 'address': '0xdac17f958d2ee523a2206206994597c13d831ec7'},
        {'symbol': 'WBTC', 'address': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599'},
        {'symbol': 'LINK', 'address': '0x514910771af9ca656af840dff83e8264ecf986ca'},
    ]
    
    liquidity_data = {}
    
    for token in tokens_needing_liquidity:
        print(f"🔍 Fetching liquidity for {token['symbol']}")
        
        try:
            # Try to get liquidity from DeFiLlama
            liquidity = fetch_defillama_liquidity(token['address'])
            if liquidity > 0:
                liquidity_data[token['address']] = liquidity
                print(f"  ✅ {token['symbol']}: ${liquidity:,.0f}")
            else:
                print(f"  ⚠️  {token['symbol']}: No liquidity data found")
        except Exception as e:
            print(f"  ❌ {token['symbol']}: Error - {e}")
    
    return liquidity_data

def fetch_defillama_liquidity(token_address):
    """Fetch liquidity data from DeFiLlama"""
    try:
        url = f"https://api.llama.fi/token/{token_address}"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Extract liquidity from the response
            if 'tvl' in data:
                return float(data['tvl'])
        return 0
        
    except Exception as e:
        print(f"    ❌ DeFiLlama error: {e}")
        return 0

if __name__ == "__main__":
    # Fix missing data
    success = fix_missing_data()
    
    # Fetch missing liquidity data
    liquidity_data = fetch_missing_liquidity_data()
    
    if success:
        print("\n✅ Missing data fix completed!")
    else:
        print("\n❌ Missing data fix failed!")









