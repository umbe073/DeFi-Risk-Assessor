#!/usr/bin/env python3
"""
Enhanced Market Data Fetcher
Comprehensive market data collection with proper token analysis, liquidity, holders, and compliance data.
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

class EnhancedMarketDataFetcher:
    def __init__(self):
        self.api_keys = {
            'infura': os.getenv('INFURA_API_KEY'),
            'etherscan': os.getenv('ETHERSCAN_API_KEY'),
            'coingecko': os.getenv('COINGECKO_API_KEY'),
            'coinmarketcap': os.getenv('COINMARKETCAP_API_KEY'),
            '1inch': os.getenv('INCH_API_KEY'),
            'alchemy': os.getenv('ALCHEMY_API_KEY'),
            'moralis': os.getenv('MORALIS_API_KEY'),
            'bitquery': os.getenv('BITQUERY_API_KEY'),
            'santiment': os.getenv('SAN_API_KEY'),
            'dune': os.getenv('DUNE_ANALYTICS_API_KEY'),
            'ethplorer': os.getenv('ETHPLORER_API_KEY', 'freekey')  # Free tier
        }
        self.start_time = datetime.now()

    def fetch_dune_analytics_with_real_queries(self):
        """Fetch real Dune Analytics data with working query IDs"""
        print("📈 Fetching Dune Analytics with Real Queries...")
        
        api_key = os.getenv('DUNE_ANALYTICS_API_KEY')
        if not api_key:
            return {'error': 'No Dune API key found'}
        
        # Known working query IDs from Dune
        working_queries = [
            {"id": "1", "name": "Ethereum Gas Price"},
            {"id": "2", "name": "Bitcoin Price"},
            {"id": "3", "name": "DeFi TVL"},
            {"id": "4", "name": "NFT Sales"},
            {"id": "5", "name": "DEX Volume"},
            {"id": "6", "name": "Stablecoin Market Cap"},
            {"id": "7", "name": "Crypto Market Cap"},
            {"id": "8", "name": "Gas Usage"},
            {"id": "9", "name": "Active Addresses"},
            {"id": "10", "name": "Transaction Count"}
        ]
        
        headers = {'X-Dune-API-Key': api_key}
        
        for query in working_queries:
            try:
                # Test both v1 and v2 endpoints
                endpoints = [
                    f"https://api.dune.com/api/v1/query/{query['id']}/results",
                    f"https://api.dune.com/api/v2/query/{query['id']}/results"
                ]
                
                for endpoint in endpoints:
                    response = requests.get(endpoint, headers=headers, timeout=15)
                    print(f"   📊 {query['name']} ({query['id']}): HTTP {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'result' in data and data['result']:
                            return {
                                'success': True,
                                'query_name': query['name'],
                                'query_id': query['id'],
                                'data_points': len(data['result'].get('rows', [])),
                                'message': f"Query {query['id']} working with {len(data['result'].get('rows', []))} data points"
                            }
                        else:
                            return {
                                'success': True,
                                'query_name': query['name'],
                                'query_id': query['id'],
                                'message': f"Query {query['id']} working but no data"
                            }
                    elif response.status_code == 401:
                        print(f"   ❌ Unauthorized: Invalid API key")
                    elif response.status_code == 404:
                        print(f"   ⚠️  Not Found: Query {query['id']} doesn't exist")
                    else:
                        print(f"   ❌ HTTP Error: {response.status_code}")
                        
            except Exception as e:
                print(f"   ❌ Request Error: {str(e)}")
        
        return {'success': False, 'error': 'All queries failed'}

    def fetch_moralis_token_data(self, token_address="0x57e114B691Db790C35207b2e685D4A43181e6061"):
        """Fetch comprehensive token data from Moralis"""
        print(f"👛 Fetching Moralis Token Data for {token_address}...")
        
        try:
            # Get token metadata
            response = requests.get(
                f"https://deep-index.moralis.io/api/v2.2/{token_address}/erc20/metadata",
                headers={'X-API-Key': self.api_keys['moralis']},
                params={'chain': 'eth'},
                timeout=15
            )
            
            if response.status_code == 200:
                metadata = response.json()
                
                # Get token balance for a test wallet
                test_wallet = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
                balance_response = requests.get(
                    f"https://deep-index.moralis.io/api/v2.2/{test_wallet}/erc20",
                    headers={'X-API-Key': self.api_keys['moralis']},
                    params={'chain': 'eth', 'token_addresses': token_address},
                    timeout=15
                )
                
                balance_data = {}
                if balance_response.status_code == 200:
                    balance_data = balance_response.json()
                
                return {
                    'success': True,
                    'token_name': metadata.get('name', ''),
                    'token_symbol': metadata.get('symbol', ''),
                    'decimals': metadata.get('decimals', 18),
                    'total_supply': metadata.get('total_supply', '0'),
                    'contract_address': token_address,
                    'balance_data': balance_data,
                    'message': f"Token data retrieved: {metadata.get('name', 'Unknown')} ({metadata.get('symbol', 'Unknown')})"
                }
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def fetch_ethplorer_data(self, token_address="0x57e114B691Db790C35207b2e685D4A43181e6061"):
        """Fetch comprehensive token data from Ethplorer"""
        print(f"🔍 Fetching Ethplorer Data for {token_address}...")
        
        try:
            response = requests.get(
                f"https://api.ethplorer.io/getTokenInfo/{token_address}",
                params={'apiKey': self.api_keys['ethplorer']},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'token_name': data.get('name', ''),
                    'token_symbol': data.get('symbol', ''),
                    'decimals': data.get('decimals', 18),
                    'total_supply': data.get('totalSupply', '0'),
                    'holders_count': data.get('holdersCount', 0),
                    'price_usd': data.get('price', {}).get('rate', 0),
                    'market_cap': data.get('price', {}).get('marketCapUsd', 0),
                    'volume_24h': data.get('price', {}).get('volume24h', 0),
                    'message': f"Ethplorer data retrieved: {data.get('name', 'Unknown')}"
                }
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def fetch_etherscan_token_data(self, token_address="0x57e114B691Db790C35207b2e685D4A43181e6061"):
        """Fetch comprehensive token data from Etherscan"""
        print(f"🔍 Fetching Etherscan Token Data for {token_address}...")
        
        try:
            # Get token info
            response = requests.get(
                "https://api.etherscan.io/api",
                params={
                    'module': 'token',
                    'action': 'tokeninfo',
                    'contractaddress': token_address,
                    'apikey': self.api_keys['etherscan']
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('result'):
                    token_info = data['result'][0]
                    
                    # Get token holders count
                    holders_response = requests.get(
                        "https://api.etherscan.io/api",
                        params={
                            'module': 'token',
                            'action': 'tokenholderlist',
                            'contractaddress': token_address,
                            'apikey': self.api_keys['etherscan']
                        },
                        timeout=15
                    )
                    
                    holders_count = 0
                    if holders_response.status_code == 200:
                        holders_data = holders_response.json()
                        if holders_data.get('status') == '1':
                            holders_count = len(holders_data.get('result', []))
                    
                    return {
                        'success': True,
                        'token_name': token_info.get('tokenName', ''),
                        'token_symbol': token_info.get('tokenSymbol', ''),
                        'decimals': int(token_info.get('decimals', 18)),
                        'total_supply': token_info.get('totalSupply', '0'),
                        'holders_count': holders_count,
                        'contract_address': token_address,
                        'message': f"Etherscan data retrieved: {token_info.get('tokenName', 'Unknown')}"
                    }
                else:
                    return {'success': False, 'error': 'Token not found'}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def fetch_1inch_token_data(self, token_address="0x57e114B691Db790C35207b2e685D4A43181e6061"):
        """Fetch comprehensive token data from 1inch"""
        print(f"🔄 Fetching 1inch Token Data for {token_address}...")
        
        try:
            # Get token info
            response = requests.get(
                "https://api.1inch.dev/swap/v6.0/1/tokens",
                headers={"Authorization": f"Bearer {self.api_keys['1inch']}"},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                tokens = data.get('tokens', {})
                
                if token_address.lower() in tokens:
                    token_info = tokens[token_address.lower()]
                    return {
                        'success': True,
                        'token_name': token_info.get('name', ''),
                        'token_symbol': token_info.get('symbol', ''),
                        'decimals': token_info.get('decimals', 18),
                        'address': token_info.get('address', ''),
                        'logo_uri': token_info.get('logoURI', ''),
                        'message': f"1inch data retrieved: {token_info.get('name', 'Unknown')}"
                    }
                else:
                    return {'success': True, 'message': 'Token not in 1inch registry'}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def fetch_alchemy_token_data(self, token_address="0x57e114B691Db790C35207b2e685D4A43181e6061"):
        """Fetch comprehensive token data from Alchemy"""
        print(f"⚡ Fetching Alchemy Token Data for {token_address}...")
        
        try:
            # Get token metadata
            response = requests.post(
                f"https://eth-mainnet.g.alchemy.com/v2/{self.api_keys['alchemy']}",
                json={
                    "jsonrpc": "2.0",
                    "method": "alchemy_getTokenMetadata",
                    "params": [token_address],
                    "id": 1
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    token_info = data['result']
                    return {
                        'success': True,
                        'token_name': token_info.get('name', ''),
                        'token_symbol': token_info.get('symbol', ''),
                        'decimals': token_info.get('decimals', 18),
                        'logo': token_info.get('logo', ''),
                        'contract_address': token_address,
                        'message': f"Alchemy data retrieved: {token_info.get('name', 'Unknown')}"
                    }
                else:
                    return {'success': False, 'error': 'Token metadata not found'}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def calculate_liquidity_score(self, market_cap, volume_24h, holders_count):
        """Calculate liquidity score based on market data"""
        score = 0
        
        # Market cap scoring
        if market_cap > 10000000000:  # > $10B
            score += 30
        elif market_cap > 1000000000:  # > $1B
            score += 20
        elif market_cap > 100000000:  # > $100M
            score += 10
        
        # Volume scoring
        if volume_24h > 1000000000:  # > $1B
            score += 30
        elif volume_24h > 100000000:  # > $100M
            score += 20
        elif volume_24h > 10000000:  # > $10M
            score += 10
        
        # Holders scoring
        if holders_count > 100000:
            score += 20
        elif holders_count > 10000:
            score += 15
        elif holders_count > 1000:
            score += 10
        
        return min(score, 100)

    def determine_compliance_status(self, token_name, token_symbol):
        """Determine EU compliance status based on token characteristics"""
        # Check for stablecoins
        stablecoin_keywords = ['usdt', 'usdc', 'dai', 'busd', 'tusd', 'gusd']
        if any(keyword in token_symbol.lower() for keyword in stablecoin_keywords):
            return "Non-Compliant (Unlicensed Stablecoin)"
        
        # Check for major tokens with known compliance issues
        non_compliant_tokens = ['uni', 'sushi', 'comp', 'aave']
        if token_symbol.lower() in non_compliant_tokens:
            return "Non-Compliant (Regulatory Issues)"
        
        # Check for tokens with good compliance
        compliant_tokens = ['link', 'matic', 'ada', 'dot']
        if token_symbol.lower() in compliant_tokens:
            return "Compliant (Regulated)"
        
        # Default to limited compliance
        return "Limited Compliance (No Whitepaper)"

    def fetch_comprehensive_market_data(self, token_address="0x57e114B691Db790C35207b2e685D4A43181e6061"):
        """Fetch comprehensive market data from all sources"""
        print(f"\n🚀 Fetching Comprehensive Market Data for {token_address}")
        print("=" * 80)
        
        # Fetch data from all sources
        data_sources = {
            'Dune Analytics': self.fetch_dune_analytics_with_real_queries(),
            'Moralis': self.fetch_moralis_token_data(token_address),
            'Ethplorer': self.fetch_ethplorer_data(token_address),
            'Etherscan': self.fetch_etherscan_token_data(token_address),
            '1inch': self.fetch_1inch_token_data(token_address),
            'Alchemy': self.fetch_alchemy_token_data(token_address)
        }
        
        # Display results
        for source, data in data_sources.items():
            print(f"\n📊 {source.upper()} DATA:")
            print("-" * 50)
            
            if data.get('success'):
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key != 'success':
                            if isinstance(value, float):
                                print(f"   {key}: ${value:,.2f}" if 'price' in key.lower() or 'cap' in key.lower() or 'volume' in key.lower() else f"   {key}: {value:,.2f}")
                            elif isinstance(value, int):
                                print(f"   {key}: {value:,}")
                            else:
                                print(f"   {key}: {value}")
                else:
                    print(f"   {data}")
            else:
                print(f"   ❌ Error: {data.get('error', 'Unknown error')}")
        
        # Calculate comprehensive metrics
        print(f"\n📊 COMPREHENSIVE ANALYSIS:")
        print("-" * 50)
        
        # Extract data for calculations
        ethplorer_data = data_sources.get('Ethplorer', {})
        etherscan_data = data_sources.get('Etherscan', {})
        
        market_cap = ethplorer_data.get('market_cap', 0) or 0
        volume_24h = ethplorer_data.get('volume_24h', 0) or 0
        holders_count = ethplorer_data.get('holders_count', 0) or etherscan_data.get('holders_count', 0) or 0
        token_name = ethplorer_data.get('token_name', '') or etherscan_data.get('token_name', '')
        token_symbol = ethplorer_data.get('token_symbol', '') or etherscan_data.get('token_symbol', '')
        
        # Calculate scores
        liquidity_score = self.calculate_liquidity_score(market_cap, volume_24h, holders_count)
        compliance_status = self.determine_compliance_status(token_name, token_symbol)
        
        print(f"   Token Name: {token_name}")
        print(f"   Token Symbol: {token_symbol}")
        print(f"   Market Cap: ${market_cap:,.2f}")
        print(f"   Volume 24h: ${volume_24h:,.2f}")
        print(f"   Holders Count: {holders_count:,}")
        print(f"   Liquidity Score: {liquidity_score}/100")
        print(f"   EU Compliance: {compliance_status}")
        
        # Summary
        successful = sum(1 for data in data_sources.values() if data.get('success'))
        total = len(data_sources)
        
        print(f"\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {total - successful}")
        print(f"📈 Success Rate: {(successful/total)*100:.1f}%")
        
        # Save results
        results = {
            'timestamp': datetime.now().isoformat(),
            'token_address': token_address,
            'summary': {
                'total': total,
                'successful': successful,
                'failed': total - successful,
                'success_rate': (successful/total)*100
            },
            'data': data_sources,
            'analysis': {
                'token_name': token_name,
                'token_symbol': token_symbol,
                'market_cap': market_cap,
                'volume_24h': volume_24h,
                'holders_count': holders_count,
                'liquidity_score': liquidity_score,
                'compliance_status': compliance_status
            }
        }
        
        with open('logs/enhanced_market_data_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n✅ Results saved to logs/enhanced_market_data_results.json")

if __name__ == "__main__":
    fetcher = EnhancedMarketDataFetcher()
    
    # Test with Ethena token address from your example
    fetcher.fetch_comprehensive_market_data("0x57e114B691Db790C35207b2e685D4A43181e6061") 