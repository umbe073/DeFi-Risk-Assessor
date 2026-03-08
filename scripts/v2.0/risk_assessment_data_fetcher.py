#!/usr/bin/env python3
"""
Risk Assessment Data Fetcher
=============================

Implements the exact priority workflow for the Main Risk Assessment:

Priority Order:
1. fallback_data.json (HIGHEST PRIORITY - check first)
2. webhook_server.py (if data missing from fallback)
3. API endpoints (ALL APIs if still missing)
4. Old reports (.xlsx, .json, .csv) (if rate limited)
5. Print 0 or N/A (if all sources fail)

This module is specifically designed for the risk assessment workflow.
"""

import os
import sys
import json
import hashlib
import hmac
import pandas as pd
import requests
from pathlib import Path
from typing import Dict, Optional
import glob
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
except Exception:
    pass

WEBHOOK_BASE_URL = str(os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5001')).strip().rstrip('/')
WEBHOOK_SHARED_SECRET = str(os.getenv('WEBHOOK_SHARED_SECRET', '')).strip()


def _webhook_headers(payload_bytes: bytes = b'', *, include_signature: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {'Accept': 'application/json'}
    if not WEBHOOK_SHARED_SECRET:
        return headers

    headers['Authorization'] = f'Bearer {WEBHOOK_SHARED_SECRET}'
    if include_signature:
        timestamp = str(int(datetime.now().timestamp()))
        signed_payload = f'{timestamp}.'.encode('utf-8') + (payload_bytes or b'')
        signature = hmac.new(
            WEBHOOK_SHARED_SECRET.encode('utf-8'),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        headers['X-Webhook-Timestamp'] = timestamp
        headers['X-Webhook-Signature'] = f'sha256={signature}'
    return headers

# Import multi-API fetcher
from multi_api_fetcher import MultiAPIFetcher

class RiskAssessmentDataFetcher:
    """
    Data Fetcher for Risk Assessment
    
    Implements the exact priority order specified for risk assessment:
    1. fallback_data.json
    2. webhook server
    3. API endpoints
    4. Old reports
    5. N/A
    """
    
    def __init__(self):
        """Initialize the fetcher"""
        self.data_dir = PROJECT_ROOT / 'data'
        self.fallback_file = self.data_dir / 'fallbacks' / 'fallback_data.json'
        # Also check root data directory
        if not self.fallback_file.exists():
            self.fallback_file = PROJECT_ROOT / 'scripts' / 'v2.0' / 'fallback_data.json'
        
        self.webhook_cache_file = self.data_dir / 'real_data_cache.json'
        self.multi_api_fetcher = MultiAPIFetcher()
    
    def fetch_token_data(self, token_address: str, symbol: str) -> Dict:
        """
        Fetch token data following the exact priority order for risk assessment
        
        Args:
            token_address: Token contract address
            symbol: Token symbol
        
        Returns:
            dict: Token data with all available metrics
        """
        print(f"\n🔍 Fetching data for {symbol} using Risk Assessment workflow")
        print("=" * 60)
        
        result = {
            'address': token_address,
            'symbol': symbol,
            'market_cap': None,
            'volume_24h': None,
            'price': None,
            'holders': None,
            'liquidity': None,
            'data_source': 'N/A'
        }
        
        # Storage for collecting values (for potential averaging if needed)
        collected_values = {
            'market_cap': [],
            'volume_24h': [],
            'price': [],
            'holders': [],
            'liquidity': []
        }
        
        # PRIORITY 1: fallback_data.json (HIGHEST PRIORITY!)
        print("📋 Priority 1: Checking fallback_data.json...")
        fallback_data = self._fetch_from_fallback_json(token_address)
        if fallback_data:
            self._collect_non_zero_values(collected_values, fallback_data, 'fallback_data.json')
            print(f"  ✅ Found data in fallback_data.json")
        else:
            print(f"  ⚠️  No data in fallback_data.json")
        
        # PRIORITY 2: webhook_server.py (if data missing)
        if self._has_missing_values(collected_values):
            print("📡 Priority 2: Checking webhook server...")
            webhook_data = self._fetch_from_webhook(token_address)
            if webhook_data:
                self._collect_non_zero_values(collected_values, webhook_data, 'webhook_server')
                print(f"  ✅ Found data from webhook server")
            else:
                print(f"  ⚠️  No data from webhook server")
        else:
            print("⏭️  Skipping webhook server (all data found in fallback)")
        
        # PRIORITY 3: API endpoints (ALL APIs if still missing)
        if self._has_missing_values(collected_values):
            print("🌐 Priority 3: Fetching from ALL API endpoints...")
            api_data = self._fetch_from_all_apis(token_address, symbol)
            if api_data:
                self._collect_non_zero_values(collected_values, api_data, 'api_endpoints')
                print(f"  ✅ Found data from API endpoints")
            else:
                print(f"  ⚠️  No data from API endpoints (may be rate limited)")
        else:
            print("⏭️  Skipping API endpoints (all data found)")
        
        # PRIORITY 4: Old reports (if rate limited or still missing)
        if self._has_missing_values(collected_values):
            print("📚 Priority 4: Checking old reports...")
            old_report_data = self._fetch_from_old_reports(token_address, symbol)
            if old_report_data:
                self._collect_non_zero_values(collected_values, old_report_data, 'old_reports')
                print(f"  ✅ Found data in old reports")
            else:
                print(f"  ⚠️  No data in old reports")
        else:
            print("⏭️  Skipping old reports (all data found)")
        
        # Calculate final values (use single value or average if multiple)
        result['market_cap'] = self._get_best_value(collected_values['market_cap'])
        result['volume_24h'] = self._get_best_value(collected_values['volume_24h'])
        result['price'] = self._get_best_value(collected_values['price'])
        result['holders'] = self._get_best_value(collected_values['holders'])
        result['liquidity'] = self._get_best_value(collected_values['liquidity'])
        
        # Determine primary data source
        sources = set()
        for key in ['market_cap', 'volume_24h', 'price', 'holders', 'liquidity']:
            if collected_values[key]:
                sources.add(collected_values[key][0]['source'])
        result['data_source'] = ', '.join(sources) if sources else 'N/A'
        
        # PRIORITY 5: Print final values (0 or N/A if not found)
        print(f"\n📊 Final values for {symbol}:")
        print(f"  Market Cap: {self._format_value(result['market_cap'])}")
        print(f"  Volume 24h: {self._format_value(result['volume_24h'])}")
        print(f"  Price: {self._format_value(result['price'], is_price=True)}")
        print(f"  Holders: {self._format_value(result['holders'], is_number=True)}")
        print(f"  Liquidity: {self._format_value(result['liquidity'])}")
        print(f"  Data Source: {result['data_source']}")
        
        return result
    
    def _fetch_from_fallback_json(self, token_address: str) -> Optional[Dict]:
        """
        PRIORITY 1: Fetch from fallback_data.json
        This is checked FIRST before any other source
        """
        try:
            if not self.fallback_file.exists():
                return None
            
            with open(self.fallback_file, 'r') as f:
                fallback_data = json.load(f)
            
            # Check token_mappings
            token_mappings = fallback_data.get('token_mappings', {})
            token_data = token_mappings.get(token_address.lower())
            
            if not token_data:
                return None
            
            # Extract values
            return {
                'market_cap': token_data.get('market_cap'),
                'volume_24h': token_data.get('volume_24h'),
                'price': token_data.get('price'),
                'holders': token_data.get('holders'),
                'liquidity': token_data.get('liquidity')
            }
            
        except Exception as e:
            print(f"    ❌ Error reading fallback_data.json: {e}")
            return None
    
    def _fetch_from_webhook(self, token_address: str) -> Optional[Dict]:
        """
        PRIORITY 2: Fetch from webhook server
        Only called if fallback_data.json has missing values
        """
        try:
            # Try webhook HTTP endpoint first
            try:
                response = requests.get(
                    f'{WEBHOOK_BASE_URL}/webhook/cache',
                    timeout=5,
                    headers=_webhook_headers(),
                )
                if response.status_code == 200:
                    cache_data = response.json()
                    tokens = cache_data.get('tokens', {})
                    token_data = tokens.get(token_address.lower())
                    
                    if token_data:
                        return self._extract_from_webhook_structure(token_data)
            except requests.RequestException:
                pass  # Webhook server not running, try file
            
            # Fallback to reading cache file directly
            if not self.webhook_cache_file.exists():
                return None
            
            with open(self.webhook_cache_file, 'r') as f:
                cache_data = json.load(f)
            
            tokens = cache_data.get('tokens', {})
            token_data = tokens.get(token_address.lower())
            
            if not token_data:
                return None
            
            return self._extract_from_webhook_structure(token_data)
            
        except Exception as e:
            print(f"    ❌ Error reading webhook cache: {e}")
            return None
    
    def _extract_from_webhook_structure(self, token_data: Dict) -> Dict:
        """Extract data from webhook cache structure"""
        result = {}
        
        # Check aggregates first
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
                    if not result.get('market_cap'):
                        result['market_cap'] = data.get('market_cap')
                    if not result.get('volume_24h'):
                        result['volume_24h'] = data.get('volume_24h')
                    if not result.get('price'):
                        result['price'] = data.get('price')
            
            onchain_data = token_data.get('onchain_data', {})
            for source, data in onchain_data.items():
                if isinstance(data, dict) and data.get('source') == 'real-time':
                    if not result.get('holders'):
                        result['holders'] = data.get('holders')
        
        return result
    
    def _fetch_from_all_apis(self, token_address: str, symbol: str) -> Optional[Dict]:
        """
        PRIORITY 3: Fetch from ALL API endpoints
        Only called if fallback and webhook have missing values
        """
        try:
            print("    🌐 Querying all available APIs...")
            return self.multi_api_fetcher.fetch_all_apis(token_address, symbol)
        except Exception as e:
            print(f"    ❌ Error fetching from APIs: {e}")
            return None
    
    def _fetch_from_old_reports(self, token_address: str, symbol: str) -> Optional[Dict]:
        """
        PRIORITY 4: Fetch from old reports
        Only called if API endpoints failed (rate limited) or have missing values
        """
        try:
            # Search for old report files
            report_files = []
            
            # Look for Excel files
            excel_files = list(self.data_dir.glob('risk_reports/*.xlsx'))
            report_files.extend([(f, 'excel') for f in excel_files])
            
            # Look for JSON files
            json_files = list(self.data_dir.glob('risk_report*.json'))
            report_files.extend([(f, 'json') for f in json_files])
            
            # Look for CSV files
            csv_files = list(self.data_dir.glob('risk_report*.csv'))
            csv_files.extend(list(self.data_dir.glob('token_data_viewer*.csv')))
            report_files.extend([(f, 'csv') for f in csv_files])
            
            if not report_files:
                return None
            
            # Sort by modification time (newest first)
            report_files.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
            
            # Try each file until we find data
            for report_file, file_type in report_files:
                try:
                    if file_type == 'json':
                        data = self._extract_from_json_report(report_file, token_address, symbol)
                    elif file_type == 'csv':
                        data = self._extract_from_csv_report(report_file, token_address, symbol)
                    elif file_type == 'excel':
                        data = self._extract_from_excel_report(report_file, token_address, symbol)
                    
                    if data and any(v for v in data.values() if v and v > 0):
                        print(f"    📄 Found data in {report_file.name}")
                        return data
                except Exception as e:
                    continue  # Try next file
            
            return None
            
        except Exception as e:
            print(f"    ❌ Error reading old reports: {e}")
            return None
    
    def _extract_from_json_report(self, file_path: Path, token_address: str, symbol: str) -> Optional[Dict]:
        """Extract data from JSON report"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Search for token by address or symbol
            if isinstance(data, list):
                for token in data:
                    if (token.get('token_address', '').lower() == token_address.lower() or
                        token.get('symbol', '') == symbol):
                        return self._extract_metrics_from_report(token)
            elif isinstance(data, dict):
                # Check if it's a single token report
                if data.get('token_address', '').lower() == token_address.lower():
                    return self._extract_metrics_from_report(data)
                # Check if it's a token collection
                for key, token in data.items():
                    if isinstance(token, dict):
                        if (token.get('token_address', '').lower() == token_address.lower() or
                            token.get('symbol', '') == symbol):
                            return self._extract_metrics_from_report(token)
            
            return None
        except Exception:
            return None
    
    def _extract_from_csv_report(self, file_path: Path, token_address: str, symbol: str) -> Optional[Dict]:
        """Extract data from CSV report"""
        try:
            df = pd.read_csv(file_path)
            
            # Try to find row by symbol or address
            row = None
            if 'Symbol' in df.columns:
                matches = df[df['Symbol'] == symbol]
                if not matches.empty:
                    row = matches.iloc[0]
            elif 'symbol' in df.columns:
                matches = df[df['symbol'] == symbol]
                if not matches.empty:
                    row = matches.iloc[0]
            
            if row is None:
                return None
            
            return self._extract_metrics_from_csv_row(row)
        except Exception:
            return None
    
    def _extract_from_excel_report(self, file_path: Path, token_address: str, symbol: str) -> Optional[Dict]:
        """Extract data from Excel report"""
        try:
            df = pd.read_excel(file_path)
            
            # Try to find row by symbol
            row = None
            if 'Symbol' in df.columns:
                matches = df[df['Symbol'] == symbol]
                if not matches.empty:
                    row = matches.iloc[0]
            
            if row is None:
                return None
            
            return self._extract_metrics_from_csv_row(row)
        except Exception:
            return None
    
    def _extract_metrics_from_report(self, token_data: Dict) -> Dict:
        """Extract metrics from report data structure"""
        result = {}
        
        # Try to extract from key_metrics
        key_metrics = token_data.get('key_metrics', {})
        if key_metrics:
            result['market_cap'] = key_metrics.get('market_cap')
            result['volume_24h'] = key_metrics.get('volume_24h')
            result['holders'] = key_metrics.get('holders')
            result['liquidity'] = key_metrics.get('liquidity')
        
        # Try to extract from market_data
        market_data = token_data.get('market_data', {})
        if isinstance(market_data, dict):
            for source, data in market_data.items():
                if isinstance(data, dict):
                    if not result.get('market_cap'):
                        result['market_cap'] = data.get('market_cap')
                    if not result.get('volume_24h'):
                        result['volume_24h'] = data.get('volume_24h')
                    if not result.get('price'):
                        result['price'] = data.get('price')
        
        # Try to extract from onchain_data
        onchain_data = token_data.get('onchain_data', {})
        if isinstance(onchain_data, dict):
            holders_data = onchain_data.get('holders', {})
            if isinstance(holders_data, dict):
                result['holders'] = holders_data.get('total_holders')
        
        return result
    
    def _extract_metrics_from_csv_row(self, row) -> Dict:
        """Extract metrics from CSV/Excel row"""
        result = {}
        
        # Try different column name variations
        for field in ['Market Cap', 'market_cap', 'market cap']:
            if field in row.index:
                result['market_cap'] = self._parse_number(row[field])
                break
        
        for field in ['Volume 24h', 'volume_24h', 'volume 24h']:
            if field in row.index:
                result['volume_24h'] = self._parse_number(row[field])
                break
        
        for field in ['Price', 'price']:
            if field in row.index:
                result['price'] = self._parse_number(row[field])
                break
        
        for field in ['Holders', 'holders']:
            if field in row.index:
                result['holders'] = self._parse_number(row[field])
                break
        
        for field in ['Liquidity', 'liquidity']:
            if field in row.index:
                result['liquidity'] = self._parse_number(row[field])
                break
        
        return result
    
    def _parse_number(self, value) -> Optional[float]:
        """Parse number from various formats"""
        if pd.isna(value) or value == 'N/A' or value == 0:
            return None
        
        if isinstance(value, (int, float)):
            return float(value) if value > 0 else None
        
        if isinstance(value, str):
            clean = value.replace('$', '').replace(',', '').strip()
            try:
                num = float(clean)
                return num if num > 0 else None
            except ValueError:
                return None
        
        return None
    
    def _collect_non_zero_values(self, collected_values: Dict, data: Dict, source: str):
        """Collect non-zero values from a data source"""
        for key in ['market_cap', 'volume_24h', 'price', 'holders', 'liquidity']:
            value = data.get(key)
            if value and value > 0:
                collected_values[key].append({
                    'value': value,
                    'source': source
                })
    
    def _has_missing_values(self, collected_values: Dict) -> bool:
        """Check if any values are still missing"""
        return any(len(collected_values[key]) == 0 for key in collected_values)
    
    def _get_best_value(self, value_list: list) -> Optional[float]:
        """Get best value from collected values"""
        if not value_list:
            return None
        
        # Filter out None and 0 values
        valid_values = [item['value'] for item in value_list if item['value'] and item['value'] > 0]
        
        if not valid_values:
            return None
        
        # If single value, return it
        if len(valid_values) == 1:
            return valid_values[0]
        
        # If multiple values, return average
        avg = sum(valid_values) / len(valid_values)
        sources = [item['source'] for item in value_list if item['value'] and item['value'] > 0]
        print(f"    📊 Averaged {len(valid_values)} values from: {', '.join(set(sources))}")
        return avg
    
    def _format_value(self, value: Optional[float], is_price: bool = False, is_number: bool = False) -> str:
        """Format value for display"""
        if value is None or value == 0:
            return "N/A"
        
        if is_number:
            return f"{value:,.0f}"
        elif is_price and value < 0.01:
            return f"${value:.6f}"
        else:
            return f"${value:,.2f}"

def test_risk_assessment_fetcher():
    """Test the risk assessment data fetcher"""
    print("🧪 Testing Risk Assessment Data Fetcher")
    print("=" * 60)
    
    fetcher = RiskAssessmentDataFetcher()
    
    # Test with AAVE
    test_token = {
        'address': '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9',
        'symbol': 'AAVE'
    }
    
    result = fetcher.fetch_token_data(test_token['address'], test_token['symbol'])
    
    print("\n✅ Test complete!")
    print(f"📊 Result: {result}")

if __name__ == "__main__":
    test_risk_assessment_fetcher()








