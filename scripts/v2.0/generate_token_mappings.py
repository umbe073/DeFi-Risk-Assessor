#!/usr/bin/env python3
"""
Dynamic Token Mappings Generator
================================

This script automatically generates token_mappings.py from tokens.csv
When tokens.csv is updated, run this script to regenerate the mappings.

Usage:
    python3 generate_token_mappings.py
"""

import os
import sys
import pandas as pd
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
TOKENS_CSV = DATA_DIR / 'tokens.csv'
TOKEN_MAPPINGS_FILE = Path(__file__).parent / 'token_mappings.py'

def load_tokens_from_csv():
    """Load tokens from tokens.csv file"""
    try:
        if not TOKENS_CSV.exists():
            print(f"❌ tokens.csv not found at {TOKENS_CSV}")
            return None
        
        df = pd.read_csv(TOKENS_CSV)
        print(f"✅ Loaded {len(df)} tokens from {TOKENS_CSV}")
        return df
    except Exception as e:
        print(f"❌ Error loading tokens.csv: {e}")
        return None

def generate_token_mappings(df):
    """Generate token mappings from DataFrame"""
    if df is None or df.empty:
        print("❌ No tokens to process")
        return None
    
    # Initialize mappings
    address_mappings = {}
    symbol_mappings = {}
    coingecko_mappings = {}
    paprika_mappings = {}
    market_cap_estimates = {}
    holder_estimates = {}
    token_types = {}
    
    # Process each token
    for _, row in df.iterrows():
        # Handle both old and new CSV formats
        if 'address' in row:
            address = row['address'].lower()
            symbol = row['symbol']
            name = row['name']
            chain = row['chain']
        elif 'Contract Address' in row:
            address = row['Contract Address'].lower()
            symbol = row['Symbol']
            name = row['Token Name']
            chain = row['Chain']
        else:
            print(f"⚠️  Unknown column format in CSV: {list(row.keys())}")
            continue
        
        # Address to name mapping
        address_mappings[address] = name
        
        # Address to symbol mapping
        symbol_mappings[address] = symbol
        
        # Generate CoinGecko ID (lowercase, hyphenated)
        coingecko_id = generate_coingecko_id(symbol, name)
        if coingecko_id:
            coingecko_mappings[symbol] = coingecko_id
        
        # Generate CoinPaprika ID
        paprika_id = generate_paprika_id(symbol, name)
        if paprika_id:
            paprika_mappings[symbol] = paprika_id
        
        # Set token type based on chain
        token_types[symbol] = get_token_type(chain)
        
        # Set default market cap and holder estimates (will be updated by APIs)
        market_cap_estimates[symbol] = 0
        holder_estimates[symbol] = 0
    
    return {
        'address_mappings': address_mappings,
        'symbol_mappings': symbol_mappings,
        'coingecko_mappings': coingecko_mappings,
        'paprika_mappings': paprika_mappings,
        'market_cap_estimates': market_cap_estimates,
        'holder_estimates': holder_estimates,
        'token_types': token_types
    }

def generate_coingecko_id(symbol, name):
    """Generate CoinGecko ID from symbol and name"""
    # Common CoinGecko ID patterns
    coingecko_patterns = {
        'AAVE': 'aave',
        'CHZ': 'chiliz',
        'COMP': 'compound-governance-token',
        'USDC': 'usd-coin',
        'USDT': 'tether',
        'WBTC': 'wrapped-bitcoin',
        'LINK': 'chainlink',
        '1INCH': '1inch',
        'POL': 'matic-network',
        'UNI': 'uniswap',
        'DAI': 'dai',
        'GRT': 'the-graph',
        'MKR': 'maker',
        'SUSHI': 'sushi',
        'QNT': 'quant-network',
        'GALA': 'gala',
        'MANA': 'decentraland',
        'SAND': 'the-sandbox',
        'BAT': 'basic-attention-token',
        'OP': 'optimism',
        'TRX': 'tron',
        'S': 'sonic'
    }
    
    return coingecko_patterns.get(symbol, None)

def generate_paprika_id(symbol, name):
    """Generate CoinPaprika ID from symbol and name"""
    # Common CoinPaprika ID patterns
    paprika_patterns = {
        'AAVE': 'aave-aave',
        'CHZ': 'chz-chiliz',
        'COMP': 'comp-compound',
        'USDC': 'usdc-usd-coin',
        'USDT': 'usdt-tether',
        'WBTC': 'wbtc-wrapped-bitcoin',
        'LINK': 'link-chainlink',
        '1INCH': '1inch-1inch',
        'POL': 'matic-polygon',
        'UNI': 'uni-uniswap',
        'DAI': 'dai-dai',
        'GRT': 'grt-the-graph',
        'MKR': 'mkr-maker',
        'SUSHI': 'sushi-sushiswap',
        'QNT': 'qnt-quant',
        'GALA': 'gala-gala',
        'MANA': 'mana-decentraland',
        'SAND': 'sand-the-sandbox',
        'BAT': 'bat-basic-attention-token',
        'OP': 'op-optimism',
        'TRX': 'trx-tron',
        'S': 'sonic-sonic'
    }
    
    return paprika_patterns.get(symbol, None)

def get_token_type(chain):
    """Determine token type based on chain"""
    chain_types = {
        'ethereum': 'ERC-20',
        'polygon': 'ERC-20',
        'op': 'ERC-20',
        'sonic': 'ERC-20',
        'bsc': 'BEP-20',
        'arbitrum': 'ERC-20'
    }
    return chain_types.get(chain.lower(), 'Unknown')

def write_token_mappings_file(mappings):
    """Write the token mappings to token_mappings.py"""
    if not mappings:
        print("❌ No mappings to write")
        return False
    
    try:
        # Generate the Python file content
        content = f'''"""
Token Mappings Configuration File
================================

This file is AUTO-GENERATED from tokens.csv
DO NOT EDIT THIS FILE MANUALLY

To update token mappings:
1. Edit data/tokens.csv
2. Run: python3 scripts/v2.0/generate_token_mappings.py

Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

# Address to token name mappings (auto-generated from tokens.csv)
ADDRESS_MAPPINGS = {{
{chr(10).join(f"    '{addr}': '{name}'," for addr, name in mappings['address_mappings'].items())}
}}

# Address to symbol mappings (auto-generated from tokens.csv)
SYMBOL_MAPPINGS = {{
{chr(10).join(f"    '{addr}': '{symbol}'," for addr, symbol in mappings['symbol_mappings'].items())}
}}

# CoinGecko ID mappings (auto-generated with common patterns)
COINGECKO_MAPPINGS = {{
{chr(10).join(f"    '{symbol}': '{coingecko_id}'," for symbol, coingecko_id in mappings['coingecko_mappings'].items())}
}}

# CoinPaprika ID mappings (auto-generated with common patterns)
PAPRIKA_MAPPINGS = {{
{chr(10).join(f"    '{symbol}': '{paprika_id}'," for symbol, paprika_id in mappings['paprika_mappings'].items())}
}}

# Market cap estimates (will be updated by APIs)
MARKET_CAP_ESTIMATES = {{
{chr(10).join(f"    '{symbol}': {estimate}," for symbol, estimate in mappings['market_cap_estimates'].items())}
}}

# Holder estimates (will be updated by APIs)
HOLDER_ESTIMATES = {{
{chr(10).join(f"    '{symbol}': {estimate}," for symbol, estimate in mappings['holder_estimates'].items())}
}}

# Token types (based on chain)
TOKEN_TYPES = {{
{chr(10).join(f"    '{symbol}': '{token_type}'," for symbol, token_type in mappings['token_types'].items())}
}}

# Helper functions
def get_token_name(address):
    """Get token name from address"""
    return ADDRESS_MAPPINGS.get(address.lower(), 'Unknown Token')

def get_token_symbol(address):
    """Get token symbol from address"""
    return SYMBOL_MAPPINGS.get(address.lower(), 'Unknown')

def get_coingecko_id(symbol):
    """Get CoinGecko ID from symbol"""
    return COINGECKO_MAPPINGS.get(symbol.upper(), None)

def get_paprika_id(symbol):
    """Get CoinPaprika ID from symbol"""
    return PAPRIKA_MAPPINGS.get(symbol.upper(), None)

def get_market_cap_estimate(symbol):
    """Get market cap estimate from symbol"""
    return MARKET_CAP_ESTIMATES.get(symbol.upper(), 0)

def get_holder_estimate(symbol):
    """Get holder estimate from symbol"""
    return HOLDER_ESTIMATES.get(symbol.upper(), 0)

def get_token_type(symbol):
    """Get token type from symbol"""
    return TOKEN_TYPES.get(symbol.upper(), 'Unknown')

# Legacy function names for backward compatibility
def get_cmc_id(symbol):
    """Get CoinMarketCap ID from symbol (placeholder)"""
    return None

def get_cmc_name(symbol):
    """Get CoinMarketCap name from symbol (placeholder)"""
    return get_token_name(symbol)

def get_cmc_slug(symbol):
    """Get CoinMarketCap slug from symbol (placeholder)"""
    return symbol.lower()
'''
        
        # Write the file
        with open(TOKEN_MAPPINGS_FILE, 'w') as f:
            f.write(content)
        
        print(f"✅ Generated token_mappings.py with {len(mappings['address_mappings'])} tokens")
        print(f"📁 File location: {TOKEN_MAPPINGS_FILE}")
        return True
        
    except Exception as e:
        print(f"❌ Error writing token_mappings.py: {e}")
        return False

def main():
    """Main function"""
    print("🔄 Generating token mappings from tokens.csv...")
    
    # Load tokens from CSV
    df = load_tokens_from_csv()
    if df is None:
        return False
    
    # Generate mappings
    mappings = generate_token_mappings(df)
    if mappings is None:
        return False
    
    # Write to file
    success = write_token_mappings_file(mappings)
    
    if success:
        print("✅ Token mappings generated successfully!")
        print("💡 The system will now use the updated token mappings.")
        print("🔄 You can run this script anytime tokens.csv is updated.")
    else:
        print("❌ Failed to generate token mappings")
    
    return success

if __name__ == "__main__":
    main()
