#!/usr/bin/env python3
"""
Token Data Loader with Multi-Source Workflow
=============================================

This module implements the exact workflow logic for loading token data:

1. Load tokens from tokens.csv (single source of truth)
2. Fetch data in priority order:
   2.1 - Webhook cache (real-time)
   2.2 - Fallback file (if values are 0 or N/A)
   2.3 - API endpoints (if values are still 0 or N/A)
   2.4 - Latest risk report (final fallback)
3. Calculate averages when multiple values found
4. Ignore 0 or N/A values when calculating averages
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import requests
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(Path(__file__).parent))

# Import centralized token manager
from centralized_token_manager import TokenManager

class TokenDataLoader:
    """
    Token Data Loader with Multi-Source Workflow
    
    Implements the exact workflow:
    1. Webhook cache (real-time)
    2. Fallback file (secondary)
    3. API endpoints (tertiary)
    4. Risk report (final fallback)
    
    Calculates averages when multiple valid values found.
    Ignores 0 or N/A values.
    """
    
    def __init__(self):
        """Initialize the loader"""
        self.token_manager = TokenManager()
        self.data_dir = PROJECT_ROOT / 'data'
    
    def load_all_token_data(self):
        """
        Load token data following the priority workflow
        
        Returns:
            list: List of token data dictionaries
        """
        print("🔄 Loading Token Data with Multi-Source Workflow")
        print("=" * 60)
        
        # Get all tokens from tokens.csv
        tokens = self.token_manager.get_all_tokens()
        print(f"📋 Processing {len(tokens)} tokens from tokens.csv")
        
        results = []
        
        for token in tokens:
            print(f"\n🔍 {token['name']} ({token['symbol']})")
            print("-" * 40)
            
            # Collect data from all sources
            token_data = self._fetch_multi_source_data(token)
            results.append(token_data)
        
        return results
    
    def _fetch_multi_source_data(self, token: Dict) -> Dict:
        """
        Fetch token data following the priority workflow
        
        Args:
            token: Token info from token manager
        
        Returns:
            dict: Aggregated token data
        """
        address = token['address']
        symbol = token['symbol']
        name = token['name']
        chain = token['chain']
        
        # Initialize result
        result = {
            'address': address,
            'name': name,
            'symbol': symbol,
            'chain': chain,
            'market_cap': None,
            'volume_24h': None,
            'price': None,
            'holders': None,
            'liquidity': None,
            'data_sources': []
        }
        
        # Storage for multiple values (for averaging)
        values_collected = {
            'market_cap': [],
            'volume_24h': [],
            'price': [],
            'holders': [],
            'liquidity': []
        }
        
        # Step 2.1: Webhook Cache (Real-time)
        webhook_data = self._fetch_webhook_cache(address)
        if webhook_data:
            self._collect_values(values_collected, webhook_data, 'webhook_cache')
            print(f"  ✅ Webhook cache data found")
        
        # Step 2.2: Fallback File (if values missing)
        if self._has_missing_values(values_collected):
            fallback_data = self._fetch_fallback_file(address)
            if fallback_data:
                self._collect_values(values_collected, fallback_data, 'fallback_file')
                print(f"  ✅ Fallback file data found")
        
        # Step 2.3: API Endpoints (if values still missing)
        if self._has_missing_values(values_collected):
            api_data = self._fetch_api_data(address, symbol)
            if api_data:
                self._collect_values(values_collected, api_data, 'api_endpoints')
                print(f"  ✅ API endpoints data found (multiple APIs)")
        
        # Step 2.4: Latest Risk Report (final fallback)
        if self._has_missing_values(values_collected):
            risk_report_data = self._fetch_risk_report(address, symbol)
            if risk_report_data:
                self._collect_values(values_collected, risk_report_data, 'risk_report')
                print(f"  ✅ Risk report data found")
        
        # Calculate averages (ignoring 0 and None values)
        result['market_cap'] = self._calculate_average(values_collected['market_cap'])
        result['volume_24h'] = self._calculate_average(values_collected['volume_24h'])
        result['price'] = self._calculate_average(values_collected['price'])
        result['holders'] = self._calculate_average(values_collected['holders'])
        result['liquidity'] = self._calculate_average(values_collected['liquidity'])
        
        # Report final values
        print(f"  📊 Final values:")
        print(f"     Market Cap: {self._format_value(result['market_cap'], is_currency=True)}")
        print(f"     Volume 24h: {self._format_value(result['volume_24h'], is_currency=True)}")
        print(f"     Price: {self._format_value(result['price'], is_currency=True, is_price=True)}")
        print(f"     Holders: {self._format_value(result['holders'], is_currency=False)}")
        print(f"     Liquidity: {self._format_value(result['liquidity'], is_currency=True)}")
        
        return result
    
    def _fetch_webhook_cache(self, address: str) -> Optional[Dict]:
        """Fetch data from webhook cache"""
        try:
            cache_file = self.data_dir / 'real_data_cache.json'
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            tokens = cache_data.get('tokens', {})
            token_data = tokens.get(address.lower())
            
            if not token_data:
                return None
            
            # Extract from aggregates if available
            result = {}
            
            if 'aggregates' in token_data:
                agg = token_data['aggregates']
                market = agg.get('market', {})
                onchain = agg.get('onchain', {})
                liquidity = agg.get('liquidity', {})
                
                result['market_cap'] = market.get('market_cap')
                result['volume_24h'] = market.get('volume_24h')
                result['price'] = market.get('price')
                result['holders'] = onchain.get('holders')
                result['liquidity'] = liquidity.get('liquidity')
            else:
                # Extract from individual sections
                market_data = token_data.get('market_data', {})
                for source, data in market_data.items():
                    if isinstance(data, dict) and data.get('source') == 'real-time':
                        result['market_cap'] = data.get('market_cap')
                        result['volume_24h'] = data.get('volume_24h')
                        result['price'] = data.get('price')
                        break
                
                onchain_data = token_data.get('onchain_data', {})
                for source, data in onchain_data.items():
                    if isinstance(data, dict) and data.get('source') == 'real-time':
                        result['holders'] = data.get('holders')
                        break
                
                liquidity_data = token_data.get('liquidity_data', {})
                for source, data in liquidity_data.items():
                    if isinstance(data, dict) and data.get('source') == 'real-time':
                        result['liquidity'] = data.get('liquidity')
                        break
            
            return result if any(v for v in result.values() if v and v > 0) else None
            
        except Exception as e:
            print(f"     ⚠️  Webhook cache error: {e}")
            return None
    
    def _fetch_fallback_file(self, address: str) -> Optional[Dict]:
        """Fetch data from fallback file"""
        try:
            fallback_file = self.data_dir / 'token_fallbacks.json'
            if not fallback_file.exists():
                return None
            
            with open(fallback_file, 'r') as f:
                fallback_data = json.load(f)
            
            token_mappings = fallback_data.get('token_mappings', {})
            token_data = token_mappings.get(address)
            
            if not token_data:
                return None
            
            result = {}
            
            # Extract market data
            market_data = token_data.get('market_data', {})
            for source, data in market_data.items():
                if isinstance(data, dict):
                    if data.get('market_cap'):
                        result['market_cap'] = data['market_cap']
                    if data.get('volume_24h'):
                        result['volume_24h'] = data['volume_24h']
                    if data.get('price'):
                        result['price'] = data['price']
            
            # Extract onchain data
            onchain_data = token_data.get('onchain_data', {})
            for source, data in onchain_data.items():
                if isinstance(data, dict) and data.get('holders'):
                    result['holders'] = data['holders']
            
            # Extract liquidity data
            liquidity_data = token_data.get('liquidity_data', {})
            for source, data in liquidity_data.items():
                if isinstance(data, dict) and data.get('liquidity'):
                    result['liquidity'] = data['liquidity']
            
            return result if any(v for v in result.values() if v and v > 0) else None
            
        except Exception as e:
            print(f"     ⚠️  Fallback file error: {e}")
            return None
    
    def _fetch_api_data(self, address: str, symbol: str) -> Optional[Dict]:
        """Fetch data from ALL available API endpoints"""
        try:
            # Import multi-API fetcher
            from multi_api_fetcher import MultiAPIFetcher
            
            # Fetch from ALL APIs
            fetcher = MultiAPIFetcher()
            data = fetcher.fetch_all_apis(address, symbol)
            
            return data if data else None
            
        except Exception as e:
            print(f"     ⚠️  API endpoints error: {e}")
            return None
    
    def _fetch_risk_report(self, address: str, symbol: str) -> Optional[Dict]:
        """Fetch data from latest risk report"""
        try:
            # Try token_data_viewer.csv first
            viewer_file = self.data_dir / 'token_data_viewer.csv'
            if viewer_file.exists():
                df = pd.read_csv(viewer_file)
                # Find row matching symbol
                row = df[df['Symbol'] == symbol]
                if not row.empty:
                    row = row.iloc[0]
                    return self._extract_from_csv_row(row)
            
            # Try risk_report.csv files
            risk_files = list(self.data_dir.glob('risk_report*.csv'))
            if risk_files:
                # Use the most recent one
                latest_file = max(risk_files, key=lambda p: p.stat().st_mtime)
                df = pd.read_csv(latest_file)
                
                # Try to find by symbol or address
                row = df[df['symbol'] == symbol] if 'symbol' in df.columns else pd.DataFrame()
                if row.empty and 'token_address' in df.columns:
                    row = df[df['token_address'].str.lower() == address.lower()]
                
                if not row.empty:
                    return self._extract_from_csv_row(row.iloc[0])
            
            return None
            
        except Exception as e:
            print(f"     ⚠️  Risk report error: {e}")
            return None
    
    def _extract_from_csv_row(self, row) -> Dict:
        """Extract data from CSV row"""
        result = {}
        
        # Try different column name variations
        for field in ['market_cap', 'Market Cap', 'market cap']:
            if field in row.index:
                result['market_cap'] = self._parse_number(row[field])
                break
        
        for field in ['volume_24h', 'Volume 24h', 'volume 24h']:
            if field in row.index:
                result['volume_24h'] = self._parse_number(row[field])
                break
        
        for field in ['price', 'Price']:
            if field in row.index:
                result['price'] = self._parse_number(row[field])
                break
        
        for field in ['holders', 'Holders']:
            if field in row.index:
                result['holders'] = self._parse_number(row[field])
                break
        
        for field in ['liquidity', 'Liquidity']:
            if field in row.index:
                result['liquidity'] = self._parse_number(row[field])
                break
        
        return result
    
    def _parse_number(self, value) -> Optional[float]:
        """Parse a number from various formats"""
        if pd.isna(value) or value == 'N/A':
            return None
        
        if isinstance(value, (int, float)):
            return float(value) if value > 0 else None
        
        if isinstance(value, str):
            # Remove currency symbols and commas
            clean = value.replace('$', '').replace(',', '').strip()
            try:
                num = float(clean)
                return num if num > 0 else None
            except ValueError:
                return None
        
        return None
    
    def _collect_values(self, values_collected: Dict, data: Dict, source: str):
        """Collect values from a data source"""
        for key in ['market_cap', 'volume_24h', 'price', 'holders', 'liquidity']:
            value = data.get(key)
            if value and value > 0:
                values_collected[key].append({
                    'value': value,
                    'source': source
                })
    
    def _has_missing_values(self, values_collected: Dict) -> bool:
        """Check if any values are still missing"""
        return any(len(values_collected[key]) == 0 for key in values_collected)
    
    def _calculate_average(self, value_list: List[Dict]) -> Optional[float]:
        """
        Calculate average from list of values, ignoring 0 and None
        
        Args:
            value_list: List of dicts with 'value' and 'source' keys
        
        Returns:
            float or None: Average value or None if no valid values
        """
        if not value_list:
            return None
        
        # Filter out 0 and None values
        valid_values = [item['value'] for item in value_list if item['value'] and item['value'] > 0]
        
        if not valid_values:
            return None
        
        # Calculate average
        average = sum(valid_values) / len(valid_values)
        
        # Log if multiple values were averaged
        if len(valid_values) > 1:
            sources = [item['source'] for item in value_list if item['value'] and item['value'] > 0]
            print(f"     📊 Averaged {len(valid_values)} values from: {', '.join(sources)}")
        
        return average
    
    def _format_value(self, value: Optional[float], is_currency: bool = False, is_price: bool = False) -> str:
        """Format value for display"""
        if value is None or value == 0:
            return "N/A"
        
        if is_price and value < 0.01:
            return f"${value:.6f}"
        elif is_currency:
            return f"${value:,.2f}"
        else:
            return f"{value:,.0f}"
    
    def save_to_csv(self, token_data_list: List[Dict], output_file: Path = None):
        """
        Save token data to CSV file
        
        Args:
            token_data_list: List of token data dictionaries
            output_file: Output file path (default: token_data_viewer.csv)
        """
        if output_file is None:
            output_file = self.data_dir / 'token_data_viewer.csv'
        
        # Convert to DataFrame
        rows = []
        for token in token_data_list:
            row = {
                'Token': token['name'],
                'Symbol': token['symbol'],
                'Chain': token['chain'],
                'Market Cap': self._format_value(token['market_cap'], is_currency=True),
                'Volume 24h': self._format_value(token['volume_24h'], is_currency=True),
                'Holders': self._format_value(token['holders'], is_currency=False),
                'Liquidity': self._format_value(token['liquidity'], is_currency=True),
                'Price': self._format_value(token['price'], is_currency=True, is_price=True),
                'Last Updated': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(output_file, index=False)
        print(f"\n✅ Saved to {output_file}")

def main():
    """Main function"""
    print("🚀 Token Data Loader with Multi-Source Workflow")
    print("=" * 60)
    print("📌 Priority Order:")
    print("   1. Webhook Cache (real-time)")
    print("   2. Fallback File")
    print("   3. API Endpoints")
    print("   4. Risk Report")
    print("📌 Averages calculated when multiple values found")
    print("📌 Zero and N/A values ignored\n")
    
    loader = TokenDataLoader()
    token_data = loader.load_all_token_data()
    
    # Save to CSV
    loader.save_to_csv(token_data)
    
    print("\n✅ Token data loading complete!")
    print(f"📊 Processed {len(token_data)} tokens")

if __name__ == "__main__":
    main()

