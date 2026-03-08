#!/usr/bin/env python3
"""
API Issues Diagnostic and Fix Script
====================================

This script diagnoses and helps fix API key issues for:
- Breadcrumbs API
- Zapper API  
- BitQuery API
- Covalent API
- And other DeFi APIs

It provides:
1. API key status check
2. API connectivity testing
3. Error diagnosis
4. Fix suggestions
5. Test API endpoints
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

# Import credential management
try:
    sys.path.append(os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management'))
    from secure_credentials import read_store, project_paths
except ImportError as e:
    print(f"⚠️  Could not import credential management: {e}")
    print("   This is normal if credentials haven't been set up yet.")

class APIDiagnostic:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.data_dir = os.path.join(PROJECT_ROOT, 'data')
        self.api_keys = {}
        self.test_results = {}
        
    def load_api_keys(self):
        """Load API keys from environment and credential store"""
        
        print("🔑 LOADING API KEYS")
        print("-" * 40)
        
        # Try to load from credential store first
        try:
            paths = project_paths()
            creds = read_store()
            if creds:
                self.api_keys.update(creds)
                print(f"✅ Loaded {len(creds)} keys from credential store")
            else:
                print("⚠️  No credentials found in store")
        except Exception as e:
            print(f"⚠️  Could not load credential store: {e}")
        
        # Load from environment variables
        env_keys = {
            'BREADCRUMBS_API_KEY': os.getenv('BREADCRUMBS_API_KEY'),
            'ZAPPER_API_KEY': os.getenv('ZAPPER_API_KEY'),
            'BITQUERY_API_KEY': os.getenv('BITQUERY_API_KEY'),
            'COVALENT_API_KEY': os.getenv('COVALENT_API_KEY'),
            'ETHERSCAN_API_KEY': os.getenv('ETHERSCAN_API_KEY'),
            'COINGECKO_API_KEY': os.getenv('COINGECKO_API_KEY'),
            'MORALIS_API_KEY': os.getenv('MORALIS_API_KEY'),
            'INFURA_API_KEY': os.getenv('INFURA_API_KEY'),
            'ALCHEMY_API_KEY': os.getenv('ALCHEMY_API_KEY'),
        }
        
        # Add environment keys that aren't already loaded
        for key, value in env_keys.items():
            if value and key not in self.api_keys:
                self.api_keys[key] = value
                print(f"✅ Loaded {key} from environment")
        
        # Show summary
        print(f"\n📊 API Key Summary:")
        for key_name in sorted(self.api_keys.keys()):
            key_value = self.api_keys[key_name]
            if key_value:
                masked_value = key_value[:8] + "..." + key_value[-4:] if len(key_value) > 12 else "***"
                print(f"   ✅ {key_name}: {masked_value}")
            else:
                print(f"   ❌ {key_name}: Missing")
    
    def test_api_connectivity(self, api_name, url, headers=None, params=None, timeout=10):
        """Test API connectivity"""
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            if response.status_code == 200:
                return True, f"✅ {api_name}: Connected successfully"
            elif response.status_code == 401:
                return False, f"❌ {api_name}: Authentication failed (check API key)"
            elif response.status_code == 403:
                return False, f"❌ {api_name}: Access forbidden (check permissions)"
            elif response.status_code == 429:
                return False, f"⚠️  {api_name}: Rate limited"
            elif response.status_code == 404:
                return False, f"❌ {api_name}: Endpoint not found"
            else:
                return False, f"❌ {api_name}: HTTP {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return False, f"❌ {api_name}: Connection failed (check internet/URL)"
        except requests.exceptions.Timeout:
            return False, f"❌ {api_name}: Request timeout"
        except Exception as e:
            return False, f"❌ {api_name}: Error - {str(e)}"
    
    def test_breadcrumbs_api(self):
        """Test Breadcrumbs API"""
        
        print("\n🔍 TESTING BREADCRUMBS API")
        print("-" * 30)
        
        api_key = self.api_keys.get('BREADCRUMBS_API_KEY')
        if not api_key:
            print("❌ BREADCRUMBS_API_KEY: Missing")
            print("   💡 Fix: Get API key from https://breadcrumbs.app/")
            return False
        
        # Test endpoints
        test_address = "0xdac17f958d2ee523a2206206994597c13d831ec7"  # USDT
        
        endpoints = [
            ("Risk Score v2", f"https://api.breadcrumbs.app/api/v2/addresses/{test_address}/risk-score", 
             {"Authorization": f"Bearer {api_key}"}),
            ("Risk Score v1", f"https://api.breadcrumbs.app/api/v1/addresses/{test_address}/risk-score",
             {"Authorization": f"Bearer {api_key}"}),
            ("Token Info", f"https://api.breadcrumbs.app/api/v1/tokens/{test_address}",
             {"Authorization": f"Bearer {api_key}"}),
        ]
        
        success_count = 0
        for name, url, headers in endpoints:
            success, message = self.test_api_connectivity(name, url, headers)
            print(f"   {message}")
            if success:
                success_count += 1
        
        return success_count > 0
    
    def test_zapper_api(self):
        """Test Zapper API"""
        
        print("\n🔍 TESTING ZAPPER API")
        print("-" * 30)
        
        api_key = self.api_keys.get('ZAPPER_API_KEY')
        if not api_key:
            print("❌ ZAPPER_API_KEY: Missing")
            print("   💡 Fix: Get API key from https://zapper.xyz/")
            return False
        
        # Test endpoints
        test_address = "0xdac17f958d2ee523a2206206994597c13d831ec7"  # USDT
        
        endpoints = [
            ("Portfolio v2", f"https://api.zapper.xyz/v2/portfolio/{test_address}",
             {"Authorization": f"Basic {api_key}"}),
            ("Portfolio v1", f"https://api.zapper.xyz/v1/portfolio/{test_address}",
             {"Authorization": f"Basic {api_key}"}),
            ("Protocols", "https://api.zapper.xyz/v2/protocols",
             {"Authorization": f"Basic {api_key}"}),
        ]
        
        success_count = 0
        for name, url, headers in endpoints:
            success, message = self.test_api_connectivity(name, url, headers)
            print(f"   {message}")
            if success:
                success_count += 1
        
        return success_count > 0
    
    def test_bitquery_api(self):
        """Test BitQuery API"""
        
        print("\n🔍 TESTING BITQUERY API")
        print("-" * 30)
        
        api_key = self.api_keys.get('BITQUERY_API_KEY')
        if not api_key:
            print("❌ BITQUERY_API_KEY: Missing")
            print("   💡 Fix: Get API key from https://bitquery.io/")
            return False
        
        # Test GraphQL endpoint
        url = "https://graphql.bitquery.io"
        headers = {'X-API-KEY': api_key}
        
        # Simple GraphQL query
        query = """
        {
          ethereum {
            blocks(limit: 1) {
              hash
            }
          }
        }
        """
        
        try:
            response = requests.post(url, headers=headers, json={'query': query}, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    print(f"   ❌ BitQuery: GraphQL errors - {data['errors']}")
                    return False
                else:
                    print(f"   ✅ BitQuery: GraphQL query successful")
                    return True
            else:
                print(f"   ❌ BitQuery: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ BitQuery: Error - {str(e)}")
            return False
    
    def test_covalent_api(self):
        """Test Covalent API"""
        
        print("\n🔍 TESTING COVALENT API")
        print("-" * 30)
        
        api_key = self.api_keys.get('COVALENT_API_KEY')
        if not api_key:
            print("❌ COVALENT_API_KEY: Missing")
            print("   💡 Fix: Get API key from https://www.covalenthq.com/")
            return False
        
        # Test endpoints
        endpoints = [
            ("Chain List", "https://api.covalenthq.com/v1/chains/",
             {"Authorization": f"Bearer {api_key}"}),
            ("Token Balances", f"https://api.covalenthq.com/v1/1/address/0xdac17f958d2ee523a2206206994597c13d831ec7/balances_v3/",
             {"Authorization": f"Bearer {api_key}"}),
        ]
        
        success_count = 0
        for name, url, headers in endpoints:
            success, message = self.test_api_connectivity(name, url, headers)
            print(f"   {message}")
            if success:
                success_count += 1
        
        return success_count > 0
    
    def test_other_apis(self):
        """Test other important APIs"""
        
        print("\n🔍 TESTING OTHER APIS")
        print("-" * 30)
        
        # Test Etherscan
        etherscan_key = self.api_keys.get('ETHERSCAN_API_KEY')
        if etherscan_key:
            success, message = self.test_api_connectivity(
                "Etherscan", 
                "https://api.etherscan.io/api",
                params={"module": "stats", "action": "ethsupply", "apikey": etherscan_key}
            )
            print(f"   {message}")
        else:
            print("   ⚠️  ETHERSCAN_API_KEY: Missing")
        
        # Test CoinGecko (free tier)
        success, message = self.test_api_connectivity(
            "CoinGecko", 
            "https://api.coingecko.com/api/v3/ping"
        )
        print(f"   {message}")
        
        # Test Moralis
        moralis_key = self.api_keys.get('MORALIS_API_KEY')
        if moralis_key:
            success, message = self.test_api_connectivity(
                "Moralis",
                "https://deep-index.moralis.io/api/v2/0xdac17f958d2ee523a2206206994597c13d831ec7",
                headers={"X-API-Key": moralis_key}
            )
            print(f"   {message}")
        else:
            print("   ⚠️  MORALIS_API_KEY: Missing")
    
    def generate_fix_guide(self):
        """Generate a fix guide for missing API keys"""
        
        print("\n🔧 API KEY FIX GUIDE")
        print("=" * 50)
        
        missing_apis = []
        
        if not self.api_keys.get('BREADCRUMBS_API_KEY'):
            missing_apis.append(('Breadcrumbs', 'https://breadcrumbs.app/', 'Free tier available'))
        
        if not self.api_keys.get('ZAPPER_API_KEY'):
            missing_apis.append(('Zapper', 'https://zapper.xyz/', 'Free tier available'))
        
        if not self.api_keys.get('BITQUERY_API_KEY'):
            missing_apis.append(('BitQuery', 'https://bitquery.io/', 'Free tier available'))
        
        if not self.api_keys.get('COVALENT_API_KEY'):
            missing_apis.append(('Covalent', 'https://www.covalenthq.com/', 'Free tier available'))
        
        if not self.api_keys.get('ETHERSCAN_API_KEY'):
            missing_apis.append(('Etherscan', 'https://etherscan.io/apis', 'Free tier available'))
        
        if not self.api_keys.get('MORALIS_API_KEY'):
            missing_apis.append(('Moralis', 'https://moralis.io/', 'Free tier available'))
        
        if missing_apis:
            print("❌ Missing API Keys:")
            for name, url, note in missing_apis:
                print(f"   • {name}: {url} ({note})")
            
            print("\n📝 How to add API keys:")
            print("1. Visit the credential manager: python3 scripts/v1.5/credential_management/gui_credentials.py")
            print("2. Or set environment variables in your shell")
            print("3. Or add to .env file in project root")
            
            print("\n💡 Quick fix commands:")
            print("export BREADCRUMBS_API_KEY='your_key_here'")
            print("export ZAPPER_API_KEY='your_key_here'")
            print("export BITQUERY_API_KEY='your_key_here'")
            print("export COVALENT_API_KEY='your_key_here'")
        else:
            print("✅ All API keys are configured!")
    
    def run_diagnostic(self):
        """Run complete API diagnostic"""
        
        print("🔍 API ISSUES DIAGNOSTIC")
        print("=" * 60)
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Load API keys
        self.load_api_keys()
        
        # Test each API
        results = {}
        
        results['breadcrumbs'] = self.test_breadcrumbs_api()
        results['zapper'] = self.test_zapper_api()
        results['bitquery'] = self.test_bitquery_api()
        results['covalent'] = self.test_covalent_api()
        self.test_other_apis()
        
        # Generate fix guide
        self.generate_fix_guide()
        
        # Summary
        print("\n📊 DIAGNOSTIC SUMMARY")
        print("=" * 50)
        
        working_apis = sum(results.values())
        total_apis = len(results)
        
        print(f"✅ Working APIs: {working_apis}/{total_apis}")
        print(f"❌ Failed APIs: {total_apis - working_apis}/{total_apis}")
        
        for api, working in results.items():
            status = "✅" if working else "❌"
            print(f"   {status} {api.title()}")
        
        if working_apis == total_apis:
            print("\n🎉 All APIs are working correctly!")
        else:
            print(f"\n⚠️  {total_apis - working_apis} APIs need attention")
            print("   Follow the fix guide above to resolve issues")
        
        return working_apis == total_apis

def main():
    """Main function"""
    
    diagnostic = APIDiagnostic()
    success = diagnostic.run_diagnostic()
    
    print(f"\n📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
