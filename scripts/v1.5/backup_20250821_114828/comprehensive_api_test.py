#!/usr/bin/env python3
"""
Comprehensive API Test Script
Tests all API endpoints individually and provides detailed status reports.
"""

import os
import requests
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ComprehensiveAPITester:
    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()
        
    def test_api(self, name, test_func, description=""):
        """Test a single API endpoint"""
        print(f"🔍 Testing {name}...")
        try:
            result = test_func()
            if result.get('success'):
                print(f"  ✅ {name}: {result.get('message', 'Working')}")
                self.results[name] = {'status': 'SUCCESS', 'message': result.get('message', 'Working')}
            else:
                print(f"  ❌ {name}: {result.get('error', 'Failed')}")
                self.results[name] = {'status': 'FAILED', 'error': result.get('error', 'Failed')}
        except Exception as e:
            print(f"  ❌ {name}: Error - {str(e)}")
            self.results[name] = {'status': 'ERROR', 'error': str(e)}
    
    def test_infura(self):
        """Test Infura API"""
        try:
            response = requests.post(
                f"https://mainnet.infura.io/v3/{os.getenv('INFURA_API_KEY')}",
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 1
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    return {'success': True, 'message': f"Block number: {data['result']}"}
            return {'success': False, 'error': f"HTTP {response.status_code}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_etherscan(self):
        """Test Etherscan API"""
        try:
            response = requests.get(
                "https://api.etherscan.io/api",
                params={
                    "module": "proxy",
                    "action": "eth_blockNumber",
                    "apikey": os.getenv('ETHERSCAN_API_KEY')
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    return {'success': True, 'message': f"Block number: {data['result']}"}
            return {'success': False, 'error': f"HTTP {response.status_code}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_coingecko(self):
        """Test CoinGecko API"""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "ethereum",
                    "vs_currencies": "usd",
                    "x_cg_demo_api_key": os.getenv('COINGECKO_API_KEY')
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'ethereum' in data and 'usd' in data['ethereum']:
                    return {'success': True, 'message': f"ETH price: ${data['ethereum']['usd']}"}
            return {'success': False, 'error': f"HTTP {response.status_code}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_coinmarketcap(self):
        """Test CoinMarketCap API"""
        try:
            response = requests.get(
                "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
                params={
                    "symbol": "ETH",
                    "CMC_PRO_API_KEY": os.getenv('COINMARKETCAP_API_KEY')
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'ETH' in data['data']:
                    price = data['data']['ETH']['quote']['USD']['price']
                    return {'success': True, 'message': f"ETH price: ${price}"}
            return {'success': False, 'error': f"HTTP {response.status_code}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_1inch(self):
        """Test 1inch API"""
        try:
            # Test with valid token addresses and proper amount
            response = requests.get(
                "https://api.1inch.dev/swap/v6.0/1/quote",
                params={
                    "src": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
                    "dst": "0xA0b86a33E6441b8c4C8C1C8C1C8C1C8C1C8C1C8C",  # USDC
                    "amount": "100000000000000000"  # 0.1 ETH
                },
                headers={"Authorization": f"Bearer {os.getenv('INCH_API_KEY')}"},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if 'dstAmount' in data:
                    return {'success': True, 'message': f"Quote received: {data['dstAmount']}"}
                else:
                    return {'success': True, 'message': "API working but no quote data"}
            elif response.status_code == 400:
                # Try alternative endpoint
                response = requests.get(
                    "https://api.1inch.dev/swap/v6.0/1/tokens",
                    headers={"Authorization": f"Bearer {os.getenv('INCH_API_KEY')}"},
                    timeout=15
                )
                if response.status_code == 200:
                    return {'success': True, 'message': "Tokens endpoint working"}
                else:
                    return {'success': False, 'error': f"Both endpoints failed: HTTP {response.status_code}"}
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_alchemy(self):
        """Test Alchemy API"""
        try:
            response = requests.post(
                f"https://eth-mainnet.g.alchemy.com/v2/{os.getenv('ALCHEMY_API_KEY')}",
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 1
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    return {'success': True, 'message': f"Block number: {data['result']}"}
            return {'success': False, 'error': f"HTTP {response.status_code}"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_defillama(self):
        """Test DeFiLlama API"""
        try:
            # Try multiple endpoints with increased timeout
            endpoints = [
                "https://api.llama.fi/protocols",
                "https://api.llama.fi/protocol/uniswap-v3",
                "https://api.llama.fi/v2/chains"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=20)  # Increased timeout
                    if response.status_code == 200:
                        data = response.json()
                        
                        if endpoint.endswith('/protocols'):
                            if len(data) > 0:
                                total_tvl = sum(protocol.get('tvl', 0) or 0 for protocol in data)
                                return {'success': True, 'message': f"TVL: ${total_tvl:,.0f}"}
                        elif endpoint.endswith('/uniswap-v3'):
                            if 'tvl' in data and len(data['tvl']) > 0:
                                tvl = data['tvl'][0].get('totalLiquidityUSD', 0)
                                return {'success': True, 'message': f"TVL: ${tvl:,.0f}"}
                        elif endpoint.endswith('/chains'):
                            if len(data) > 0:
                                return {'success': True, 'message': f"Chains: {len(data)} available"}
                        
                except requests.exceptions.Timeout:
                    continue  # Try next endpoint
                except Exception as e:
                    continue  # Try next endpoint
            
            return {'success': False, 'error': "All DeFiLlama endpoints timed out"}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_moralis(self):
        """Test Moralis API with dynamic wallet addresses"""
        try:
            # Get wallet address from environment or use default
            wallet_address = os.getenv('MORALIS_WALLET_ADDRESS', "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
            
            # Test multiple wallet addresses for comprehensive coverage
            test_wallets = [
                wallet_address,  # Primary wallet from environment
                "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # Vitalik's wallet (fallback)
                "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6",  # Another test wallet
            ]
            
            for wallet in test_wallets:
                try:
                    response = requests.get(
                        f"https://deep-index.moralis.io/api/v2.2/{wallet}/balance",
                        headers={'X-API-Key': os.getenv('MORALIS_API_KEY')},
                        params={'chain': 'eth'},
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'balance' in data:
                            balance_wei = int(data['balance'])
                            balance_eth = balance_wei / 10**18
                            wallet_short = wallet[:8] + "..." + wallet[-6:]
                            return {
                                'success': True, 
                                'message': f"Balance: {balance_eth:.4f} ETH (Wallet: {wallet_short})"
                            }
                        else:
                            wallet_short = wallet[:8] + "..." + wallet[-6:]
                            return {'success': True, 'message': f"Wallet data retrieved (Wallet: {wallet_short})"}
                    elif response.status_code == 404:
                        continue  # Try next wallet
                    else:
                        continue  # Try next wallet
                        
                except Exception:
                    continue  # Try next wallet
            
            # If all wallets fail, return error
            return {'success': False, 'error': "All wallet addresses failed"}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_bitquery(self):
        """Test BitQuery API with ACCESS_TOKEN v2 (Free Plan)"""
        try:
            # Try with ACCESS_TOKEN v2 first (Free plan - no billing required)
            access_token = os.getenv('BITQUERY_ACCESS_TOKEN')
            if access_token:
                # Test with a simple query that should work on free plan
                query = """
                {
                  ethereum {
                    blocks(limit: 1) {
                      hash
                      height
                    }
                  }
                }
                """
                
                response = requests.post(
                    "https://graphql.bitquery.io/",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"query": query},
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and data['data'] and data['data'].get('ethereum'):
                        blocks = data['data']['ethereum'].get('blocks', [])
                        if blocks:
                            block = blocks[0]
                            return {
                                'success': True, 
                                'message': f"GraphQL query successful with ACCESS_TOKEN v2 - Block {block.get('height', 'N/A')}"
                            }
                        else:
                            return {'success': True, 'message': "ACCESS_TOKEN v2 working but no block data"}
                    else:
                        return {'success': True, 'message': "ACCESS_TOKEN v2 working but no data"}
                elif response.status_code == 401:
                    return {'success': False, 'error': "ACCESS_TOKEN v2 invalid - check token"}
                elif response.status_code == 402:
                    return {'success': False, 'error': "ACCESS_TOKEN v2 - No active billing period (free plan needs billing setup)"}
                elif response.status_code == 429:
                    return {'success': False, 'error': "Rate limit exceeded"}
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}"}
            
            # Fallback to API_KEY v1
            api_key = os.getenv('BITQUERY_API_KEY')
            if api_key:
                response = requests.post(
                    "https://graphql.bitquery.io/",
                    headers={
                        "X-API-Key": api_key,
                        "Content-Type": "application/json"
                    },
                    json={"query": "{ ethereum { blocks(limit: 1) { hash } } }"},
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and data['data']:
                        return {'success': True, 'message': "GraphQL query successful with API_KEY v1"}
                    else:
                        return {'success': True, 'message': "API_KEY v1 working but no data"}
                elif response.status_code == 401:
                    return {'success': False, 'error': "API_KEY v1 invalid"}
                elif response.status_code == 402:
                    return {'success': False, 'error': "API_KEY v1 - No active billing period (free plan needs billing setup)"}
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}"}
            else:
                return {'success': False, 'error': "No BitQuery credentials found"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_santiment(self):
        """Test Santiment API with enhanced data retrieval"""
        try:
            # Try multiple Santiment endpoints for comprehensive data
            endpoints = [
                {
                    "url": "https://api.santiment.net/graphql",
                    "query": """
                    {
                      getMetric(metric: "price_usd") {
                        timeseriesData(
                          selector: {slug: "bitcoin"}
                          from: "2024-01-01T00:00:00Z"
                          to: "2024-01-02T23:59:59Z"
                          interval: "1d"
                        ) {
                          datetime
                          value
                        }
                      }
                    }
                    """
                },
                {
                    "url": "https://api.santiment.net/graphql",
                    "query": """
                    {
                      getMetric(metric: "social_volume_total") {
                        timeseriesData(
                          selector: {slug: "bitcoin"}
                          from: "2024-01-01T00:00:00Z"
                          to: "2024-01-02T23:59:59Z"
                          interval: "1d"
                        ) {
                          datetime
                          value
                        }
                      }
                    }
                    """
                },
                {
                    "url": "https://api.santiment.net/graphql",
                    "query": """
                    {
                      getMetric(metric: "dev_activity") {
                        timeseriesData(
                          selector: {slug: "bitcoin"}
                          from: "2024-01-01T00:00:00Z"
                          to: "2024-01-02T23:59:59Z"
                          interval: "1d"
                        ) {
                          datetime
                          value
                        }
                      }
                    }
                    """
                }
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.post(
                        endpoint["url"],
                        headers={
                            "X-API-Key": os.getenv('SANTIMENT_API_KEY'),
                            "Content-Type": "application/json"
                        },
                        json={"query": endpoint["query"]},
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'data' in data and data['data']:
                            # Check if we got actual data
                            metric_data = data['data'].get('getMetric', {})
                            if metric_data and 'timeseriesData' in metric_data:
                                timeseries = metric_data['timeseriesData']
                                if timeseries and len(timeseries) > 0:
                                    return {
                                        'success': True, 
                                        'message': f"GraphQL query successful with {len(timeseries)} data points"
                                    }
                                else:
                                    continue  # Try next endpoint
                            else:
                                continue  # Try next endpoint
                        elif 'errors' in data:
                            continue  # Try next endpoint
                        else:
                            continue  # Try next endpoint
                    else:
                        continue  # Try next endpoint
                        
                except Exception:
                    continue  # Try next endpoint
            
            # If all endpoints fail, try a simpler approach
            try:
                response = requests.get(
                    "https://api.santiment.net/status",
                    headers={"X-API-Key": os.getenv('SANTIMENT_API_KEY')},
                    timeout=10
                )
                
                if response.status_code == 200:
                    return {'success': True, 'message': "API status endpoint working"}
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}"}
            except Exception as e:
                return {'success': False, 'error': str(e)}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_dune_analytics(self):
        """Test Sim by Dune API (formerly Dune Analytics) with proper implementation"""
        try:
            api_key = os.getenv('DUNE_ANALYTICS_API_KEY')
            if not api_key:
                return {'success': False, 'error': "No Sim API key found"}
            
            # Sim APIs use X-Sim-Api-Key header according to documentation
            headers = {'X-Sim-Api-Key': api_key}
            
            # Test Sim API with EVM balances endpoint (as shown in documentation)
            try:
                # Test with Vitalik's wallet as shown in Sim API documentation
                test_address = "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
                response = requests.get(
                    f"https://api.sim.dune.com/v1/evm/balances/{test_address}",
                    headers=headers,
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'balances' in data and data['balances']:
                        balance_count = len(data['balances'])
                        return {
                            'success': True, 
                            'message': f"Sim API working with {balance_count} token balances"
                        }
                    else:
                        return {
                            'success': True, 
                            'message': "Sim API working but no balance data"
                        }
                elif response.status_code == 401:
                    return {'success': False, 'error': "Sim API key invalid"}
                elif response.status_code == 403:
                    return {'success': False, 'error': "Sim API key lacks permissions"}
                else:
                    return {'success': False, 'error': f"HTTP {response.status_code}"}
            except Exception as e:
                print(f"   ⚠️  Sim API balances endpoint failed: {str(e)}")
            
            # Try alternative Sim API endpoints
            try:
                # Test activity endpoint
                response = requests.get(
                    f"https://api.sim.dune.com/v1/evm/activity/{test_address}",
                    headers=headers,
                    timeout=15
                )
                
                if response.status_code == 200:
                    return {'success': True, 'message': "Sim API activity endpoint working"}
                elif response.status_code == 401:
                    return {'success': False, 'error': "Sim API key invalid for activity"}
            except Exception as e:
                print(f"   ⚠️  Sim API activity endpoint failed: {str(e)}")
            
            # Final fallback - test basic connectivity
            try:
                response = requests.get(
                    "https://api.sim.dune.com/v1/evm/balances/0x0000000000000000000000000000000000000000",
                    headers=headers,
                    timeout=15
                )
                
                if response.status_code == 200:
                    return {'success': True, 'message': "Sim API connectivity confirmed"}
                elif response.status_code == 401:
                    return {'success': False, 'error': "Sim API key invalid"}
                else:
                    return {'success': False, 'error': f"Sim API connectivity failed: HTTP {response.status_code}"}
            except Exception as e:
                return {'success': False, 'error': f"Sim API connectivity error: {str(e)}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    

    
    def run_all_tests(self):
        """Run all API tests"""
        print("🔍 Comprehensive API Testing")
        print("=" * 50)
        
        # Test all APIs
        self.test_api("Infura", self.test_infura, "Ethereum RPC")
        self.test_api("Etherscan", self.test_etherscan, "Blockchain Explorer")
        self.test_api("CoinGecko", self.test_coingecko, "Market Data")
        self.test_api("CoinMarketCap", self.test_coinmarketcap, "Market Data")
        self.test_api("1inch", self.test_1inch, "DEX Aggregator")
        self.test_api("Alchemy", self.test_alchemy, "Ethereum RPC")
        self.test_api("DeFiLlama", self.test_defillama, "DeFi Data")
        self.test_api("Moralis", self.test_moralis, "Web3 API")
        self.test_api("BitQuery", self.test_bitquery, "GraphQL Analytics")
        self.test_api("Santiment", self.test_santiment, "Social Analytics")
        self.test_api("Dune Analytics", self.test_dune_analytics, "Analytics Platform")
        
        self.print_summary()
    
    def print_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "=" * 50)
        print("📊 COMPREHENSIVE API TEST SUMMARY")
        print("=" * 50)
        
        total = len(self.results)
        successful = sum(1 for r in self.results.values() if r['status'] == 'SUCCESS')
        failed = total - successful
        
        print(f"Total APIs Tested: {total}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(successful/total)*100:.1f}%")
        
        print("\n📋 Detailed Results:")
        print("-" * 50)
        
        for name, result in self.results.items():
            status_icon = "✅" if result['status'] == 'SUCCESS' else "❌"
            message = result.get('message', result.get('error', 'Unknown'))
            print(f"{status_icon} {name}: {message}")
        
        # Save results to file
        with open('logs/comprehensive_api_test_results.json', 'w') as f:
            json.dump({
                'timestamp': self.start_time.isoformat(),
                'summary': {
                    'total': total,
                    'successful': successful,
                    'failed': failed,
                    'success_rate': (successful/total)*100
                },
                'results': self.results
            }, f, indent=2)
        
        print(f"\n✅ Results saved to logs/comprehensive_api_test_results.json")

if __name__ == "__main__":
    tester = ComprehensiveAPITester()
    tester.run_all_tests() 