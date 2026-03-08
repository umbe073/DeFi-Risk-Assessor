#!/usr/bin/env python3
"""
Cleanup Fallback Data Script
Cleans up fallback data to only include tokens from tokens.csv
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def cleanup_fallback_data():
    """Clean up fallback data to match tokens.csv"""
    
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
                "description": "Cleaned fallback data"
            }
        }
    
    # Load tokens from CSV
    csv_file = os.path.join(PROJECT_ROOT, 'data', 'tokens.csv')
    
    if not os.path.exists(csv_file):
        print(f"❌ tokens.csv not found at {csv_file}")
        return
    
    df = pd.read_csv(csv_file)
    csv_addresses = set(row['address'].lower() for _, row in df.iterrows())
    
    # Keep only tokens that are in the CSV
    original_count = len(fallback_data.get('token_mappings', {}))
    cleaned_mappings = {}
    
    for address, data in fallback_data.get('token_mappings', {}).items():
        if address.lower() in csv_addresses:
            cleaned_mappings[address] = data
    
    fallback_data['token_mappings'] = cleaned_mappings
    cleaned_count = len(cleaned_mappings)
    
    # Update metadata
    fallback_data['metadata']['last_updated'] = datetime.now().isoformat()
    fallback_data['metadata']['total_tokens'] = cleaned_count
    fallback_data['metadata']['description'] = "Cleaned fallback data matching tokens.csv"
    
    # Save cleaned data
    with open(fallback_file, 'w') as f:
        json.dump(fallback_data, f, indent=2)
    
    print(f"✅ Cleaned fallback data")
    print(f"📊 Original tokens: {original_count}")
    print(f"📊 Cleaned tokens: {cleaned_count}")
    print(f"🗑️  Removed: {original_count - cleaned_count} tokens")
    
    return fallback_data

if __name__ == "__main__":
    cleanup_fallback_data()
