#!/usr/bin/env python3
"""
Centralized Token Manager
=========================

This is the ONLY module that should handle token data loading and management.
All other scripts MUST import from this module instead of hardcoding token data.

Data Sources (in order of priority):
1. tokens.csv - The single source of truth for token list
2. token_mappings.py - Auto-generated mappings from tokens.csv

Usage:
    from centralized_token_manager import TokenManager
    
    manager = TokenManager()
    tokens = manager.get_all_tokens()
    token_data = manager.get_token_by_symbol('AAVE')
"""

import os
import sys
import pandas as pd
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
TOKENS_CSV = DATA_DIR / 'tokens.csv'

# Add project root to path for imports
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(Path(__file__).parent))


def normalize_token_storage_address(addr):
    """Lowercase EVM 0x+40 hex only; preserve Tron/Solana/THORChain and other opaque strings."""
    s = str(addr or "").strip()
    if not s:
        return ""
    if s.startswith("0x") and len(s) == 42:
        body = s[2:]
        if all(c in "0123456789abcdefABCDEF" for c in body):
            return s.lower()
    return s


class TokenManager:
    """
    Centralized Token Manager
    
    This class is the SINGLE SOURCE OF TRUTH for all token data.
    It reads ONLY from tokens.csv and uses token_mappings.py for lookups.
    """
    
    def __init__(self):
        """Initialize the Token Manager"""
        self.tokens_df = None
        self.token_mappings = None
        self._load_tokens()
        self._load_mappings()
    
    def _load_tokens(self):
        """Load tokens from tokens.csv"""
        try:
            if not TOKENS_CSV.exists():
                print(f"❌ ERROR: tokens.csv not found at {TOKENS_CSV}")
                print(f"   Please ensure the file exists at the correct location.")
                self.tokens_df = pd.DataFrame()
                return
            
            self.tokens_df = pd.read_csv(TOKENS_CSV)
            
            # Map column names to expected format
            column_mapping = {
                'Contract Address': 'address',
                'Token Name': 'name', 
                'Symbol': 'symbol',
                'Chain': 'chain'
            }
            
            # Rename columns to expected format
            self.tokens_df = self.tokens_df.rename(columns=column_mapping)
            
            # Clean up the dataframe (remove empty rows)
            self.tokens_df = self.tokens_df.dropna(subset=['address', 'symbol'])
            
            # Normalize EVM addresses only (multi-chain CSV may include non-EVM strings).
            self.tokens_df['address'] = self.tokens_df['address'].apply(normalize_token_storage_address)
            
            print(f"✅ Loaded {len(self.tokens_df)} tokens from tokens.csv")
            
        except Exception as e:
            print(f"❌ ERROR loading tokens.csv: {e}")
            self.tokens_df = pd.DataFrame()
    
    def _load_mappings(self):
        """Load token mappings module"""
        try:
            # Import the token_mappings module
            import token_mappings
            self.token_mappings = token_mappings
            print(f"✅ Loaded token_mappings.py")
        except ImportError as e:
            print(f"⚠️  WARNING: Could not import token_mappings.py: {e}")
            print(f"   Run: python3 scripts/v2.0/generate_token_mappings.py")
            self.token_mappings = None
    
    def get_all_tokens(self):
        """
        Get all tokens from tokens.csv
        
        Returns:
            list: List of dictionaries containing token data
        """
        if self.tokens_df is None or self.tokens_df.empty:
            print("⚠️  No tokens loaded")
            return []
        
        tokens = []
        for _, row in self.tokens_df.iterrows():
            tokens.append({
                'address': row['address'],
                'name': row['name'],
                'symbol': row['symbol'],
                'chain': row['chain']
            })
        
        return tokens
    
    def get_token_by_symbol(self, symbol):
        """
        Get token data by symbol
        
        Args:
            symbol (str): Token symbol (e.g., 'AAVE')
        
        Returns:
            dict: Token data or None if not found
        """
        if self.tokens_df is None or self.tokens_df.empty:
            return None
        
        # Case-insensitive search
        result = self.tokens_df[self.tokens_df['symbol'].str.upper() == symbol.upper()]
        
        if result.empty:
            return None
        
        row = result.iloc[0]
        return {
            'address': row['address'],
            'name': row['name'],
            'symbol': row['symbol'],
            'chain': row['chain']
        }
    
    def get_token_by_address(self, address):
        """
        Get token data by contract address
        
        Args:
            address (str): Contract address
        
        Returns:
            dict: Token data or None if not found
        """
        if self.tokens_df is None or self.tokens_df.empty:
            return None
        
        lookup_key = normalize_token_storage_address(address)
        result = self.tokens_df[self.tokens_df['address'] == lookup_key]
        
        if result.empty:
            return None
        
        row = result.iloc[0]
        return {
            'address': row['address'],
            'name': row['name'],
            'symbol': row['symbol'],
            'chain': row['chain']
        }
    
    def get_token_name(self, address):
        """Get token name from address"""
        token = self.get_token_by_address(address)
        if token:
            return token['name']
        
        # Fallback to token_mappings if available
        if self.token_mappings:
            return self.token_mappings.get_token_name(address)
        
        return 'Unknown Token'
    
    def get_token_symbol(self, address):
        """Get token symbol from address"""
        token = self.get_token_by_address(address)
        if token:
            return token['symbol']
        
        # Fallback to token_mappings if available
        if self.token_mappings:
            return self.token_mappings.get_token_symbol(address)
        
        return 'UNKNOWN'
    
    def get_coingecko_id(self, symbol):
        """Get CoinGecko ID for a token symbol"""
        if self.token_mappings:
            return self.token_mappings.get_coingecko_id(symbol)
        return None
    
    def get_paprika_id(self, symbol):
        """Get CoinPaprika ID for a token symbol"""
        if self.token_mappings:
            return self.token_mappings.get_paprika_id(symbol)
        return None
    
    def get_token_count(self):
        """Get the total number of tokens"""
        if self.tokens_df is None or self.tokens_df.empty:
            return 0
        return len(self.tokens_df)
    
    def get_symbols_list(self):
        """Get a list of all token symbols"""
        if self.tokens_df is None or self.tokens_df.empty:
            return []
        return self.tokens_df['symbol'].tolist()
    
    def get_addresses_list(self):
        """Get a list of all token addresses"""
        if self.tokens_df is None or self.tokens_df.empty:
            return []
        return self.tokens_df['address'].tolist()
    
    def reload_tokens(self):
        """Reload tokens from tokens.csv"""
        print("🔄 Reloading tokens from tokens.csv...")
        self._load_tokens()
        self._load_mappings()
        print(f"✅ Reloaded {self.get_token_count()} tokens")
    
    def validate_token_data(self):
        """Validate token data integrity"""
        if self.tokens_df is None or self.tokens_df.empty:
            print("❌ No token data to validate")
            return False
        
        print(f"\n🔍 Validating Token Data")
        print("=" * 50)
        
        issues = []
        
        # Check for required columns
        required_columns = ['address', 'name', 'symbol', 'chain']
        missing_columns = [col for col in required_columns if col not in self.tokens_df.columns]
        if missing_columns:
            issues.append(f"Missing columns: {missing_columns}")
        
        # Check for empty addresses
        empty_addresses = self.tokens_df[self.tokens_df['address'].isna()]
        if not empty_addresses.empty:
            issues.append(f"Found {len(empty_addresses)} tokens with empty addresses")
        
        # Check for duplicate addresses
        duplicates = self.tokens_df[self.tokens_df['address'].duplicated()]
        if not duplicates.empty:
            issues.append(f"Found {len(duplicates)} duplicate addresses")
        
        # Check for empty symbols
        empty_symbols = self.tokens_df[self.tokens_df['symbol'].isna()]
        if not empty_symbols.empty:
            issues.append(f"Found {len(empty_symbols)} tokens with empty symbols")
        
        if issues:
            print("⚠️  Validation Issues Found:")
            for issue in issues:
                print(f"   - {issue}")
            return False
        else:
            print("✅ All validation checks passed")
            print(f"   Total tokens: {len(self.tokens_df)}")
            print(f"   Unique symbols: {self.tokens_df['symbol'].nunique()}")
            print(f"   Chains: {', '.join(self.tokens_df['chain'].unique())}")
            return True

# Global singleton instance
_token_manager_instance = None

def get_token_manager():
    """
    Get the global TokenManager instance (singleton pattern)
    
    Returns:
        TokenManager: The global token manager instance
    """
    global _token_manager_instance
    if _token_manager_instance is None:
        _token_manager_instance = TokenManager()
    return _token_manager_instance

# Convenience functions for backward compatibility
def get_all_tokens():
    """Get all tokens"""
    return get_token_manager().get_all_tokens()

def get_token_by_symbol(symbol):
    """Get token by symbol"""
    return get_token_manager().get_token_by_symbol(symbol)

def get_token_by_address(address):
    """Get token by address"""
    return get_token_manager().get_token_by_address(address)

def get_token_name(address):
    """Get token name from address"""
    return get_token_manager().get_token_name(address)

def get_token_symbol(address):
    """Get token symbol from address"""
    return get_token_manager().get_token_symbol(address)

if __name__ == "__main__":
    """Test the Token Manager"""
    print("🧪 Testing Centralized Token Manager")
    print("=" * 60)
    
    manager = TokenManager()
    
    # Validate token data
    manager.validate_token_data()
    
    # Test getting all tokens
    print(f"\n📋 All Tokens ({manager.get_token_count()}):")
    for token in manager.get_all_tokens():
        print(f"   {token['symbol']:<10} {token['name']:<30} {token['address']}")
    
    # Test getting token by symbol
    print(f"\n🔍 Testing get_token_by_symbol('AAVE'):")
    aave = manager.get_token_by_symbol('AAVE')
    if aave:
        print(f"   Found: {aave}")
    else:
        print(f"   Not found")
    
    # Test getting token by address
    print(f"\n🔍 Testing get_token_by_address:")
    token = manager.get_token_by_address('0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9')
    if token:
        print(f"   Found: {token}")
    else:
        print(f"   Not found")
    
    print("\n✅ Token Manager tests completed!")

