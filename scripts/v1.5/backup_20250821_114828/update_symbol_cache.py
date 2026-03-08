#!/usr/bin/env python3
"""
Update Symbol Cache Script
Updates the symbol cache with all tokens from tokens.csv
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def update_symbol_cache():
    """Update symbol cache with all tokens from CSV"""
    
    # Load existing symbol cache
    symbol_cache_file = os.path.join(PROJECT_ROOT, 'data', 'symbol_cache.json')
    
    if os.path.exists(symbol_cache_file):
        with open(symbol_cache_file, 'r') as f:
            symbol_cache = json.load(f)
    else:
        symbol_cache = {
            "symbols": {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "2.0",
                "description": "Enhanced symbol cache with metadata"
            }
        }
    
    # Load tokens from CSV
    csv_file = os.path.join(PROJECT_ROOT, 'data', 'tokens.csv')
    
    if not os.path.exists(csv_file):
        print(f"❌ tokens.csv not found at {csv_file}")
        return
    
    df = pd.read_csv(csv_file)
    updated_count = 0
    
    for _, row in df.iterrows():
        address = row['address'].lower()
        symbol = row['symbol']
        
        # Update symbol cache
        if address not in symbol_cache['symbols']:
            symbol_cache['symbols'][address] = {
                "symbol": symbol,
                "source": "csv",
                "timestamp": datetime.now().timestamp(),
                "last_verified": datetime.now().timestamp()
            }
            updated_count += 1
        else:
            # Update existing entry
            symbol_cache['symbols'][address].update({
                "symbol": symbol,
                "source": "csv",
                "last_verified": datetime.now().timestamp()
            })
            updated_count += 1
    
    # Update metadata
    symbol_cache['metadata']['last_updated'] = datetime.now().isoformat()
    symbol_cache['metadata']['total_symbols'] = len(symbol_cache['symbols'])
    
    # Save updated cache
    with open(symbol_cache_file, 'w') as f:
        json.dump(symbol_cache, f, indent=2)
    
    print(f"✅ Updated symbol cache with {updated_count} symbols")
    print(f"📊 Total symbols in cache: {len(symbol_cache['symbols'])}")
    
    return symbol_cache

if __name__ == "__main__":
    update_symbol_cache()
