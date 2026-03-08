#!/usr/bin/env python3
"""
Complete Fallback Data Script
Adds missing tokens from tokens.csv to the fallback data
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def complete_fallback_data():
    """Add missing tokens from CSV to fallback data"""
    
    # Load existing fallback data
    fallback_file = os.path.join(PROJECT_ROOT, 'data', 'token_fallbacks.json')
    
    if os.path.exists(fallback_file):
        with open(fallback_file, 'r') as f:
            fallback_data = json.load(f)
    else:
        fallback_data = {
            "token_mappings": {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "2.0",
                "description": "Complete fallback data"
            }
        }
    
    # Load tokens from CSV
    csv_file = os.path.join(PROJECT_ROOT, 'data', 'tokens.csv')
    
    if not os.path.exists(csv_file):
        print(f"❌ tokens.csv not found at {csv_file}")
        return
    
    df = pd.read_csv(csv_file)
    existing_addresses = set(fallback_data.get('token_mappings', {}).keys())
    added_count = 0
    
    for _, row in df.iterrows():
        address = row['address'].lower()
        symbol = row['symbol']
        name = row['name']
        chain = row['chain']
        
        # Add missing tokens
        if address not in existing_addresses:
            # Determine token type based on symbol/name
            token_type = 'defi'
            if symbol in ['USDT', 'USDC', 'DAI', 'BUSD']:
                token_type = 'stablecoin'
            elif symbol in ['WBTC', 'WETH']:
                token_type = 'wrapped'
            elif symbol in ['OP', 'POL']:
                token_type = 'layer2'
            elif symbol == 'S':
                token_type = 'sonic'
            
            fallback_data['token_mappings'][address] = {
                "symbol": symbol,
                "name": name,
                "type": token_type,
                "chain": chain,
                "verified": True,
                "added_from_csv": True,
                "timestamp": datetime.now().isoformat()
            }
            added_count += 1
            print(f"  ➕ Added: {address} -> {symbol} ({name})")
    
    # Update metadata
    fallback_data['metadata']['last_updated'] = datetime.now().isoformat()
    fallback_data['metadata']['total_tokens'] = len(fallback_data['token_mappings'])
    fallback_data['metadata']['description'] = "Complete fallback data with all CSV tokens"
    
    # Save updated data
    with open(fallback_file, 'w') as f:
        json.dump(fallback_data, f, indent=2)
    
    print(f"✅ Completed fallback data")
    print(f"📊 Added: {added_count} tokens")
    print(f"📊 Total tokens: {len(fallback_data['token_mappings'])}")
    
    return fallback_data

if __name__ == "__main__":
    complete_fallback_data()
