#!/usr/bin/env python3
"""
Centralized Token Data Viewer Updater
======================================

This script updates the Token Data Viewer CSV using ONLY:
1. tokens.csv - for token list
2. centralized_token_manager.py - for token data management
3. Real-time data caches - for market data

NO HARDCODED TOKEN ADDRESSES OR MAPPINGS!

When you add/remove tokens in tokens.csv, run this script to update the viewer.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime
import requests
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(Path(__file__).parent))

# Import centralized token manager
from centralized_token_manager import TokenManager

class TokenDataViewerUpdater:
    """
    Token Data Viewer Updater using Centralized Token Manager
    
    This class updates the token data viewer CSV using ONLY the centralized
    token manager. NO hardcoded addresses or mappings!
    """
    
    def __init__(self):
        """Initialize the updater"""
        self.token_manager = TokenManager()
        self.cache_data = self.load_cache_data()
        
        # NO KNOWN CORRECTIONS - ONLY REAL DATA!
        # Per user requirement: no estimates, no simulated data, no placeholder values
        # All data must come from real API sources or show N/A
        self.known_corrections = {}
        
        # Smart caching to avoid re-checking failed tokens (persistent across sessions)
        self.failed_liquidity_cache = self._load_failed_liquidity_cache()
        self.successful_liquidity_cache = self._load_successful_liquidity_cache()
        
        # Import multi_api_fetcher for liquidity when webhook cache fails
        try:
            from multi_api_fetcher import MultiAPIFetcher
            self.multi_api_fetcher = MultiAPIFetcher()
            print("✅ Multi API fetcher loaded for liquidity fallback")
        except ImportError as e:
            print(f"⚠️  Multi API fetcher not available: {e}")
            self.multi_api_fetcher = None
    
    def _load_failed_liquidity_cache(self):
        """Load failed liquidity cache from file"""
        cache_file = PROJECT_ROOT / 'data' / 'failed_liquidity_cache.json'
        try:
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('failed_tokens', []))
        except Exception as e:
            print(f"⚠️  Could not load failed liquidity cache: {e}")
        return set()
    
    def _load_successful_liquidity_cache(self):
        """Load successful liquidity cache from file"""
        cache_file = PROJECT_ROOT / 'data' / 'successful_liquidity_cache.json'
        try:
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load successful liquidity cache: {e}")
        return {}
    
    def _save_failed_liquidity_cache(self):
        """Save failed liquidity cache to file"""
        cache_file = PROJECT_ROOT / 'data' / 'failed_liquidity_cache.json'
        try:
            with open(cache_file, 'w') as f:
                json.dump({'failed_tokens': list(self.failed_liquidity_cache)}, f)
        except Exception as e:
            print(f"⚠️  Could not save failed liquidity cache: {e}")
    
    def _save_successful_liquidity_cache(self):
        """Save successful liquidity cache to file"""
        cache_file = PROJECT_ROOT / 'data' / 'successful_liquidity_cache.json'
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.successful_liquidity_cache, f)
        except Exception as e:
            print(f"⚠️  Could not save successful liquidity cache: {e}")
    
    def load_cache_data(self):
        """Load data from cache sources"""
        cache = {'real_data': {}, 'fallbacks': {}}
        
        # Load real data cache
        real_cache_path = PROJECT_ROOT / 'data' / 'real_data_cache.json'
        try:
            with open(real_cache_path, 'r') as f:
                real_cache = json.load(f)
                cache['real_data'] = real_cache.get('tokens', {})
                print(f"✅ Loaded real data cache with {len(cache['real_data'])} tokens")
        except Exception as e:
            print(f"⚠️  Could not load real data cache: {e}")
        
        # Load token fallbacks
        fallback_path = PROJECT_ROOT / 'data' / 'token_fallbacks.json'
        try:
            with open(fallback_path, 'r') as f:
                fallback_data = json.load(f)
                cache['fallbacks'] = fallback_data.get('token_mappings', {})
                print(f"✅ Loaded fallback data with {len(cache['fallbacks'])} tokens")
        except Exception as e:
            print(f"⚠️  Could not load fallback data: {e}")
        
        return cache
    
    def extract_token_data(self, token):
        """
        Extract comprehensive data for a token
        
        Args:
            token (dict): Token info from token manager
        
        Returns:
            dict: Extracted market data
        """
        address = token['address']
        symbol = token['symbol']
        name = token['name']
        
        result = {
            'market_cap': 0,
            'volume_24h': 0,
            'price': 0,
            'holders': 0,
            'liquidity': 0,
            'data_source': 'N/A'
        }
        
        # 1. Check known corrections first (for problematic tokens)
        if symbol in self.known_corrections:
            correction = self.known_corrections[symbol]
            result.update(correction)
            result['data_source'] = 'known_corrections'
            print(f"  📋 Using known corrections for {symbol}")
            return result
        
        # 2. Try real data cache
        if address in self.cache_data['real_data']:
            token_data = self.cache_data['real_data'][address]
            extracted = self._extract_from_cache(token_data, 'real_data')
            if any(v > 0 for k, v in extracted.items() if k != 'data_source'):
                result.update(extracted)
                result['data_source'] = 'real_data_cache'
                print(f"  💾 Extracted from real data cache for {symbol}")
                # Don't return early - continue to check for liquidity improvements
        
        # 3. Try fallback cache
        if address in self.cache_data['fallbacks']:
            token_data = self.cache_data['fallbacks'][address]
            extracted = self._extract_from_cache(token_data, 'fallbacks')
            if any(v > 0 for k, v in extracted.items() if k != 'data_source'):
                result.update(extracted)
                result['data_source'] = 'fallback_cache'
                print(f"  🔄 Extracted from fallback cache for {symbol}")
                # Don't return early - continue to check for liquidity improvements
        
        # 4. Try multi_api_fetcher for liquidity if webhook cache has no liquidity
        if not result.get('liquidity', 0) and self.multi_api_fetcher:
            # Check if we already have liquidity data for this token (use cached success)
            if symbol in self.successful_liquidity_cache:
                result['liquidity'] = self.successful_liquidity_cache[symbol]
                print(f"        💾 Using cached liquidity for {symbol}: ${result['liquidity']:,.2f}")
            # Check if we already tried this token and found no liquidity (skip to avoid repeated failures)
            elif hasattr(self, 'failed_liquidity_cache') and f"no_liquidity_{symbol}" in self.failed_liquidity_cache:
                print(f"        ⏭️  Skipping {symbol} - already checked, no liquidity found")
            else:
                print(f"        🔄 Webhook cache has no liquidity, trying multi_api_fetcher...")
                try:
                    # Get token address from token manager
                    token_info = self.token_manager.get_token_by_symbol(symbol)
                    if token_info and 'address' in token_info:
                        address = token_info['address']
                        print(f"        🌐 Fetching liquidity from APIs for {symbol} ({address})")
                        
                        # Use multi_api_fetcher to get liquidity (with caching and rate limiting)
                        api_result = self.multi_api_fetcher.fetch_all_apis(address, symbol)
                        if api_result and 'liquidity' in api_result and api_result['liquidity'] > 0:
                            result['liquidity'] = api_result['liquidity']
                            print(f"        ✅ Multi API fetcher found liquidity: ${api_result['liquidity']:,.2f}")
                            # Cache this success for future use
                            self.successful_liquidity_cache[symbol] = api_result['liquidity']
                            self._save_successful_liquidity_cache()
                        else:
                            print(f"        ❌ Multi API fetcher found no liquidity for {symbol}")
                            # Cache this failure to avoid checking again
                            if not hasattr(self, 'failed_liquidity_cache'):
                                self.failed_liquidity_cache = set()
                            self.failed_liquidity_cache.add(f"no_liquidity_{symbol}")
                            self._save_failed_liquidity_cache()
                    else:
                        print(f"        ❌ No address found for {symbol} in token manager")
                except Exception as e:
                    print(f"        ⚠️  Multi API fetcher error for {symbol}: {e}")
                    # Cache this failure to avoid checking again
                    if not hasattr(self, 'failed_liquidity_cache'):
                        self.failed_liquidity_cache = set()
                    self.failed_liquidity_cache.add(f"no_liquidity_{symbol}")
                    self._save_failed_liquidity_cache()
        
        # 5. Try CoinGecko as last resort
        try:
            coingecko_id = self.token_manager.get_coingecko_id(symbol)
            if coingecko_id:
                coingecko_data = self._fetch_coingecko_data(coingecko_id)
                if coingecko_data:
                    result.update(coingecko_data)
                    result['data_source'] = 'coingecko_live'
                    print(f"  🦎 Fetched live data from CoinGecko for {symbol}")
                    return result
        except Exception as e:
            print(f"  ❌ CoinGecko fetch failed for {symbol}: {e}")
        
        print(f"  ⚠️  No data found for {symbol}")
        return result
    
    def _extract_from_cache(self, token_data, source_type):
        """Extract data from cache structure - REAL DATA ONLY (no estimates)"""
        result = {'market_cap': 0, 'volume_24h': 0, 'price': 0, 'holders': 0, 'liquidity': 0}
        
        # Extract from aggregates if available
        if 'aggregates' in token_data:
            aggregates = token_data['aggregates']
            market = aggregates.get('market', {})
            onchain = aggregates.get('onchain', {})
            liquidity = aggregates.get('liquidity', {})
            
            result['market_cap'] = market.get('market_cap', 0)
            result['volume_24h'] = market.get('volume_24h', 0)
            result['price'] = market.get('price', 0)
            result['holders'] = onchain.get('holders', 0)
            result['liquidity'] = liquidity.get('liquidity', 0)
            
            # Validate: Check if aggregates came from estimates
            # Need to verify onchain data sources
            onchain_data = token_data.get('onchain_data', {})
            for source, data in onchain_data.items():
                if isinstance(data, dict):
                    data_source = data.get('source', '')
                    # Skip estimates and L2-estimates
                    if 'estimate' in data_source.lower():
                        result['holders'] = 0  # Reject estimate
                        print(f"      ⚠️  Rejecting holders from {source} (source={data_source}, is estimate)")
            
            return result
        
        # Extract from individual data sections
        # Market data
        market_data = token_data.get('market_data', {})
        for source, data in market_data.items():
            if isinstance(data, dict) and data.get('source') == 'real-time':
                result['market_cap'] = max(result['market_cap'], data.get('market_cap', 0))
                result['volume_24h'] = max(result['volume_24h'], data.get('volume_24h', 0))
                result['price'] = max(result['price'], data.get('price', 0))
        
        # Onchain data - ONLY accept real-time data (not estimates!)
        onchain_data = token_data.get('onchain_data', {})
        for source, data in onchain_data.items():
            if isinstance(data, dict):
                data_source = data.get('source', '')
                # ONLY use real-time data, NOT estimates or l2-estimates
                if data_source == 'real-time':
                    result['holders'] = max(result['holders'], data.get('holders', 0))
                elif 'estimate' in data_source.lower():
                    print(f"      ⚠️  Skipping {source} holders (source={data_source}, is estimate)")
        
        # Liquidity data - ONLY real-time
        liquidity_data = token_data.get('liquidity_data', {})
        for source, data in liquidity_data.items():
            if isinstance(data, dict) and data.get('source') == 'real-time':
                result['liquidity'] = max(result['liquidity'], data.get('liquidity', 0))
        
        return result
    
    def _fetch_coingecko_data(self, coingecko_id):
        """Fetch live data from CoinGecko"""
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'ids': coingecko_id,
                'order': 'market_cap_desc',
                'per_page': 1,
                'page': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data:
                    token = data[0]
                    return {
                        'market_cap': token.get('market_cap', 0),
                        'volume_24h': token.get('total_volume', 0),
                        'price': token.get('current_price', 0)
                    }
        except Exception as e:
            print(f"    CoinGecko error: {e}")
        
        return None
    
    def calculate_risk_score(self, data):
        """
        Calculate risk score based on token metrics
        
        Risk factors (0-100, lower is better):
        - Market cap (higher = safer)
        - Volume (higher = more liquid = safer)
        - Holders (more = more distributed = safer)
        - Liquidity (higher = safer)
        
        Score ranges:
        - 0-20: Very Low Risk
        - 21-40: Low Risk
        - 41-60: Medium Risk
        - 61-80: High Risk
        - 81-100: Very High Risk
        """
        score = 50  # Base score (medium risk)
        
        # Market cap factor (weight: 30%)
        market_cap = data.get('market_cap', 0)
        if market_cap > 10_000_000_000:  # > $10B
            score -= 20
        elif market_cap > 1_000_000_000:  # > $1B
            score -= 10
        elif market_cap > 100_000_000:  # > $100M
            score -= 5
        elif market_cap < 10_000_000:  # < $10M
            score += 25
        elif market_cap < 100_000_000:  # < $100M
            score += 15
        
        # Volume factor (weight: 25%)
        volume = data.get('volume_24h', 0)
        if volume > 100_000_000:  # > $100M
            score -= 15
        elif volume > 10_000_000:  # > $10M
            score -= 5
        elif volume < 100_000:  # < $100K
            score += 20
        elif volume < 1_000_000:  # < $1M
            score += 10
        
        # Holders factor (weight: 20%)
        holders = data.get('holders', 0)
        if holders > 500_000:
            score -= 10
        elif holders > 100_000:
            score -= 5
        elif holders < 10_000:
            score += 15
        elif holders < 50_000:
            score += 5
        
        # Liquidity factor (weight: 25%)
        liquidity = data.get('liquidity', 0)
        if liquidity > 1_000_000_000:  # > $1B
            score -= 15
        elif liquidity > 100_000_000:  # > $100M
            score -= 5
        elif liquidity < 10_000_000:  # < $10M
            score += 20
        elif liquidity < 100_000_000:  # < $100M
            score += 10
        
        # Clamp score to 0-100 range
        return max(0, min(100, score))
    
    def update_token_data_viewer(self):
        """Update the Token Data Viewer CSV files"""
        print("🔄 Updating Token Data Viewer")
        print("=" * 60)
        
        # Get all tokens from centralized manager
        tokens = self.token_manager.get_all_tokens()
        print(f"📋 Processing {len(tokens)} tokens from tokens.csv")
        
        # Process each token
        viewer_rows = []
        
        for token in tokens:
            print(f"\n🔍 Processing {token['name']} ({token['symbol']})")
            
            # Extract comprehensive data
            data = self.extract_token_data(token)
            
            # Calculate risk score
            risk_score = self.calculate_risk_score(data)
            
            # Format values for display
            viewer_row = {
                'Token': token['name'],
                'Symbol': token['symbol'],
                'Chain': token['chain'],
                'Market Cap': f"${data['market_cap']:,.2f}" if data['market_cap'] > 0 else "N/A",
                'Volume 24h': f"${data['volume_24h']:,.2f}" if data['volume_24h'] > 0 else "N/A",
                'Holders': f"{data['holders']:,}" if data['holders'] > 0 else "N/A",
                'Liquidity': f"${data['liquidity']:,.0f}" if data['liquidity'] > 0 else "N/A",
                'Price': f"${data['price']:.6f}" if 0 < data['price'] < 0.01 else (f"${data['price']:,.2f}" if data['price'] > 0 else "N/A"),
                'Risk Score': f"{risk_score}/100",
                'Data Source': data['data_source'],
                'Last Updated': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            
            viewer_rows.append(viewer_row)
            
            print(f"  ✅ MC={viewer_row['Market Cap']}, Vol={viewer_row['Volume 24h']}, Price={viewer_row['Price']}, Risk={risk_score}/100")
        
        # Create DataFrame
        df = pd.DataFrame(viewer_rows)
        
        # Save to CSV files
        output_files = [
            PROJECT_ROOT / 'data' / 'token_data_viewer.csv',
            PROJECT_ROOT / 'data' / 'token_data_viewer_export.csv',
            PROJECT_ROOT / 'data' / 'tokens_enhanced.csv'
        ]
        
        for output_file in output_files:
            try:
                df.to_csv(output_file, index=False)
                print(f"✅ Saved to {output_file.name}")
            except Exception as e:
                print(f"❌ Failed to save {output_file.name}: {e}")
        
        # Generate summary report
        self._generate_summary(df)
        
        return True
    
    def _generate_summary(self, df):
        """Generate summary report"""
        print(f"\n📊 Summary Report")
        print("=" * 60)
        
        total_tokens = len(df)
        print(f"Total Tokens: {total_tokens}")
        
        # Data completeness
        market_cap_count = len(df[df['Market Cap'] != 'N/A'])
        volume_count = len(df[df['Volume 24h'] != 'N/A'])
        price_count = len(df[df['Price'] != 'N/A'])
        holders_count = len(df[df['Holders'] != 'N/A'])
        liquidity_count = len(df[df['Liquidity'] != 'N/A'])
        
        print(f"\n📈 Data Completeness:")
        print(f"  Market Cap:  {market_cap_count}/{total_tokens} ({(market_cap_count/total_tokens)*100:.1f}%)")
        print(f"  Volume 24h:  {volume_count}/{total_tokens} ({(volume_count/total_tokens)*100:.1f}%)")
        print(f"  Price:       {price_count}/{total_tokens} ({(price_count/total_tokens)*100:.1f}%)")
        print(f"  Holders:     {holders_count}/{total_tokens} ({(holders_count/total_tokens)*100:.1f}%)")
        print(f"  Liquidity:   {liquidity_count}/{total_tokens} ({(liquidity_count/total_tokens)*100:.1f}%)")
        
        # Data sources
        print(f"\n📡 Data Sources:")
        for source in df['Data Source'].unique():
            count = len(df[df['Data Source'] == source])
            print(f"  {source:<20} {count}/{total_tokens} ({(count/total_tokens)*100:.1f}%)")

def main():
    """Main function"""
    print("🚀 Centralized Token Data Viewer Updater")
    print("=" * 60)
    print("📌 Using ONLY tokens.csv and centralized_token_manager.py")
    print("📌 NO hardcoded addresses or mappings!")
    print()
    
    updater = TokenDataViewerUpdater()
    success = updater.update_token_data_viewer()
    
    if success:
        print("\n✅ Token Data Viewer updated successfully!")
        print("🔄 All data is now sourced from tokens.csv")
        print("💡 To add/remove tokens, edit tokens.csv and run this script again")
    else:
        print("\n❌ Token Data Viewer update failed!")

if __name__ == "__main__":
    main()

