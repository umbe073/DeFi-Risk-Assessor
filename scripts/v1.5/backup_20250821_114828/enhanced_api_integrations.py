#!/usr/bin/env python3
"""
Enhanced API Integrations for Li-Fi, Zapper, and The Graph
==========================================================
This module provides enhanced functionality for Li-Fi, Zapper, and The Graph APIs
to improve the scoring logic and data collection capabilities.
"""

import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EnhancedAPIIntegrations:
    def __init__(self):
        self.lifi_api_key = os.getenv('LI_FI_API_KEY')  # Fixed: LI_FI_API_KEY instead of LIFI_API_KEY
        self.zapper_api_key = os.getenv('ZAPPER_API_KEY')
        self.the_graph_api_key = os.getenv('THE_GRAPH_API_KEY')
        
    def fetch_lifi_quote(self, from_token, to_token, amount, from_chain=1, to_chain=1):
        """Fetch Li-Fi quote for cross-chain swaps"""
        if not self.lifi_api_key:
            print(f"    ⚠️  Li-Fi API key missing (optional service)")
            # Try public endpoint as fallback
            try:
                url = "https://li.quest/v1/quote"
                params = {
                    'fromChain': from_chain,
                    'toChain': to_chain,
                    'fromToken': from_token,
                    'toToken': to_token,
                    'fromAmount': amount
                }
                
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"      ✅ Li-Fi public quote found")
                    return {
                        'success': True,
                        'data': data,
                        'liquidity_score': self.calculate_lifi_liquidity_score(data),
                        'cross_chain_score': self.calculate_cross_chain_score(data),
                        'note': 'Using public endpoint (no API key required)'
                    }
                else:
                    print(f"      ❌ Li-Fi public endpoint failed: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"      ❌ Li-Fi public endpoint error: {e}")
                return None
        
        try:
            url = "https://li.quest/v1/quote"
            params = {
                'fromChain': from_chain,
                'toChain': to_chain,
                'fromToken': from_token,
                'toToken': to_token,
                'fromAmount': amount
            }
            headers = {'Authorization': f'Bearer {self.lifi_api_key}'}
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                print(f"      ✅ Li-Fi quote found")
                return {
                    'success': True,
                    'data': data,
                    'liquidity_score': self.calculate_lifi_liquidity_score(data),
                    'cross_chain_score': self.calculate_cross_chain_score(data)
                }
            else:
                print(f"      ❌ Li-Fi API failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"      ❌ Li-Fi error: {e}")
            return None
    
    def fetch_lifi_tokens(self, chain_id=1):
        """Fetch Li-Fi supported tokens"""
        if not self.lifi_api_key:
            return None
        
        try:
            url = f"https://li.quest/v1/tokens?chains={chain_id}"
            headers = {'Authorization': f'Bearer {self.lifi_api_key}'}
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'tokens': data.get('tokens', {}),
                    'token_count': len(data.get('tokens', {}))
                }
            else:
                print(f"      ❌ Li-Fi tokens API failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"      ❌ Li-Fi tokens error: {e}")
            return None
    
    def fetch_zapper_enhanced_portfolio(self, address):
        """Fetch enhanced portfolio data from Zapper"""
        if not self.zapper_api_key:
            print(f"    ⚠️  Zapper API key missing")
            return None
        
        try:
            # Current Zapper API structure (2024-2025) - GraphQL endpoint
            graphql_endpoint = "https://public.zapper.xyz/graphql"
            
            # GraphQL query for portfolio data
            query = """
            query PortfolioV2($addresses: [Address!]!, $networks: [Network!]) {
              portfolioV2(addresses: $addresses, networks: $networks) {
                metadata {
                  addresses
                  networks
                }
                tokenBalances {
                  totalBalanceUSD
                  byToken(first: 10) {
                    edges {
                      node {
                        token {
                          address
                          symbol
                          name
                          decimals
                          network
                        }
                        balance
                        balanceUSD
                      }
                    }
                  }
                }
                appBalances {
                  totalBalanceUSD
                  byApp(first: 10) {
                    edges {
                      node {
                        app {
                          name
                          slug
                          category
                        }
                        balanceUSD
                      }
                    }
                  }
                }
              }
            }
            """
            
            variables = {
                "addresses": [address],
                "networks": ["ethereum", "polygon", "arbitrum", "optimism"]
            }
            
            # Try different authentication methods for Zapper
            headers_options = [
                {'Authorization': f'Basic {self.zapper_api_key}'},
                {'Authorization': f'Bearer {self.zapper_api_key}'},
                {'X-API-Key': self.zapper_api_key},
                {'X-Zapper-API-Key': self.zapper_api_key},
                {}  # Try without authentication
            ]
            
            # Try each authentication method
            for i, headers in enumerate(headers_options):
                try:
                    print(f"      🔍 Trying Zapper auth method {i+1}/{len(headers_options)}...")
                    response = requests.post(
                        graphql_endpoint,
                        json={'query': query, 'variables': variables},
                        headers=headers,
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'errors' in data:
                            print(f"      ❌ Zapper GraphQL errors: {data['errors']}")
                            continue
                        else:
                            print(f"      ✅ Zapper GraphQL API working with auth method {i+1}")
                            portfolio_data = data.get('data', {}).get('portfolioV2', {})
                            return {
                                'success': True,
                                'portfolio': portfolio_data,
                                'protocols': {},  # Will be fetched separately if needed
                                'portfolio_score': self.calculate_zapper_portfolio_score(portfolio_data),
                                'protocol_diversity': self.calculate_protocol_diversity(portfolio_data)
                            }
                    elif response.status_code == 401:
                        print(f"      ❌ Zapper API authentication failed (method {i+1})")
                        continue
                    else:
                        print(f"      ⚠️  Zapper GraphQL API returned {response.status_code} (method {i+1})")
                        continue
                        
                except Exception as e:
                    print(f"      ❌ Zapper GraphQL API error (method {i+1}): {str(e)}")
                    continue
            
            # If GraphQL request fails, return error
            print(f"      ❌ Zapper GraphQL API failed")
            print(f"      ⚠️  Note: Zapper API now uses GraphQL endpoint")
            print(f"      📝 Recommendation: Check Zapper documentation for current API structure")
            return {
                'success': False,
                'error': 'Zapper GraphQL API failed',
                'note': 'Zapper now uses GraphQL endpoint at https://public.zapper.xyz/graphql'
            }
                
        except Exception as e:
            print(f"      ❌ Zapper error: {e}")
            return None
    
    def fetch_zapper_protocol_analytics(self, protocol):
        """Fetch detailed protocol analytics from Zapper"""
        if not self.zapper_api_key:
            return None
        
        try:
            url = f"https://api.zapper.xyz/v2/protocols/{protocol}/analytics"
            headers = {'Authorization': f'Basic {self.zapper_api_key}'}
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'analytics': data,
                    'risk_score': self.calculate_protocol_risk_score(data)
                }
            else:
                print(f"      ❌ Zapper analytics API failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"      ❌ Zapper analytics error: {e}")
            return None
    
    def fetch_the_graph_subgraph_data(self, subgraph_name):
        """Fetch subgraph data from The Graph"""
        if not self.the_graph_api_key:
            print(f"    ⚠️  The Graph API key missing")
            return None
        
        try:
            # Try multiple The Graph endpoints
            endpoints = [
                "https://gateway.thegraph.com/api/",
                "https://api.thegraph.com/subgraphs/name/",
                "https://api.studio.thegraph.com/query/"
            ]
            
            headers = {'Authorization': f'Bearer {self.the_graph_api_key}'}
            
            # Try different query approaches
            queries = [
                # Subgraph status query
                """
                {
                  indexingStatusForCurrentVersion(subgraphName: "%s") {
                    synced
                    health
                    fatalError {
                      message
                    }
                    chains {
                      chainHeadBlock {
                        number
                      }
                      latestBlock {
                        number
                      }
                    }
                  }
                }
                """ % subgraph_name,
                
                # Simple health check query
                """
                {
                  _meta {
                    block {
                      number
                    }
                  }
                }
                """,
                
                # Protocol data query
                """
                {
                  factory(id: "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984") {
                    totalVolumeUSD
                    totalFeesUSD
                    poolCount
                  }
                }
                """
            ]
            
            for endpoint in endpoints:
                for query in queries:
                    try:
                        response = requests.post(
                            endpoint, 
                            headers=headers, 
                            json={'query': query}, 
                            timeout=15
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if 'data' in data and data['data']:
                                if 'indexingStatusForCurrentVersion' in data['data']:
                                    subgraph_data = data['data']['indexingStatusForCurrentVersion']
                                    return {
                                        'success': True,
                                        'data': subgraph_data,
                                        'sync_score': self.calculate_sync_score(subgraph_data),
                                        'health_score': self.calculate_health_score(subgraph_data)
                                    }
                                else:
                                    return {
                                        'success': True,
                                        'data': data['data'],
                                        'message': "The Graph API working"
                                    }
                            else:
                                continue
                        elif response.status_code == 404:
                            continue  # Try next endpoint/query
                        else:
                            continue
                            
                    except Exception:
                        continue
            
            # If all endpoints fail, try public endpoint
            try:
                response = requests.post(
                    "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
                    json={'query': '{ factory(id: "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984") { totalVolumeUSD } }'},
                    timeout=15
                )
                if response.status_code == 200:
                    return {'success': True, 'message': "The Graph public endpoint working"}
                else:
                    print(f"      ❌ The Graph API failed: All endpoints returned errors")
                    return None
            except Exception as e:
                print(f"      ❌ The Graph error: {e}")
                return None
                
        except Exception as e:
            print(f"      ❌ The Graph error: {e}")
            return None
    
    def fetch_the_graph_dex_data(self, dex_name):
        """Fetch DEX data from The Graph"""
        if not self.the_graph_api_key:
            return None
        
        try:
            url = "https://gateway.thegraph.com/api/"
            headers = {'Authorization': f'Bearer {self.the_graph_api_key}'}
            
            # Query for DEX data (example for Uniswap V3)
            query = """
            {
              factory(id: "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984") {
                totalVolumeUSD
                totalFeesUSD
                poolCount
              }
            }
            """
            
            response = requests.post(url, headers=headers, json={'query': query}, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']:
                    dex_data = data['data']['factory']
                    return {
                        'success': True,
                        'data': dex_data,
                        'volume_score': self.calculate_volume_score(dex_data),
                        'liquidity_score': self.calculate_dex_liquidity_score(dex_data)
                    }
                else:
                    print(f"      ⚠️  The Graph no DEX data for {dex_name}")
                    return None
            else:
                print(f"      ❌ The Graph DEX API failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"      ❌ The Graph DEX error: {e}")
            return None
    
    # Scoring functions for Li-Fi
    def calculate_lifi_liquidity_score(self, quote_data):
        """Calculate liquidity score based on Li-Fi quote data"""
        try:
            if not quote_data or 'estimate' not in quote_data:
                return 0
            
            estimate = quote_data['estimate']
            
            # Factors to consider:
            # 1. Gas cost efficiency
            # 2. Slippage tolerance
            # 3. Route availability
            # 4. Price impact
            
            score = 0
            
            # Gas cost scoring (lower is better)
            if 'gasCosts' in estimate:
                gas_costs = estimate['gasCosts']
                total_gas = sum(float(cost.get('estimate', 0)) for cost in gas_costs)
                if total_gas < 50:
                    score += 30
                elif total_gas < 100:
                    score += 20
                elif total_gas < 200:
                    score += 10
            
            # Slippage scoring (lower is better)
            if 'toAmountMin' in estimate and 'toAmount' in estimate:
                slippage = (float(estimate['toAmount']) - float(estimate['toAmountMin'])) / float(estimate['toAmount'])
                if slippage < 0.01:  # < 1%
                    score += 25
                elif slippage < 0.05:  # < 5%
                    score += 15
                elif slippage < 0.10:  # < 10%
                    score += 5
            
            # Route availability scoring
            if 'routes' in estimate and len(estimate['routes']) > 0:
                score += 25
            
            # Price impact scoring
            if 'priceImpact' in estimate:
                price_impact = abs(float(estimate['priceImpact']))
                if price_impact < 0.01:  # < 1%
                    score += 20
                elif price_impact < 0.05:  # < 5%
                    score += 10
            
            return min(score, 100)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating Li-Fi liquidity score: {e}")
            return 0
    
    def calculate_cross_chain_score(self, quote_data):
        """Calculate cross-chain functionality score"""
        try:
            if not quote_data:
                return 0
            
            score = 0
            
            # Check if it's a cross-chain swap
            if 'fromChain' in quote_data and 'toChain' in quote_data:
                if quote_data['fromChain'] != quote_data['toChain']:
                    score += 50  # Cross-chain functionality
            
            # Check for bridge availability
            if 'routes' in quote_data:
                for route in quote_data['routes']:
                    if 'steps' in route:
                        for step in route['steps']:
                            if 'tool' in step and 'bridge' in step['tool'].lower():
                                score += 25  # Bridge available
                                break
            
            # Check for multiple route options
            if 'routes' in quote_data and len(quote_data['routes']) > 1:
                score += 25  # Multiple routes available
            
            return min(score, 100)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating cross-chain score: {e}")
            return 0
    
    # Scoring functions for Zapper
    def calculate_zapper_portfolio_score(self, portfolio_data):
        """Calculate portfolio health score based on Zapper data"""
        try:
            if not portfolio_data or 'balances' not in portfolio_data:
                return 0
            
            balances = portfolio_data['balances']
            score = 0
            
            # Calculate total portfolio value
            total_value = 0
            for balance in balances:
                if 'balanceUSD' in balance:
                    total_value += float(balance['balanceUSD'])
            
            # Portfolio value scoring
            if total_value > 10000:
                score += 30
            elif total_value > 1000:
                score += 20
            elif total_value > 100:
                score += 10
            
            # Token diversity scoring
            unique_tokens = len(set(balance.get('token', {}).get('symbol', '') for balance in balances))
            if unique_tokens > 10:
                score += 25
            elif unique_tokens > 5:
                score += 15
            elif unique_tokens > 2:
                score += 10
            
            # Protocol diversity scoring
            protocols = set()
            for balance in balances:
                if 'protocol' in balance:
                    protocols.add(balance['protocol'])
            
            if len(protocols) > 5:
                score += 25
            elif len(protocols) > 3:
                score += 15
            elif len(protocols) > 1:
                score += 10
            
            # Liquidity scoring
            liquid_tokens = sum(1 for balance in balances if balance.get('balanceUSD', 0) > 10)
            if liquid_tokens > 5:
                score += 20
            elif liquid_tokens > 2:
                score += 10
            
            return min(score, 100)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating Zapper portfolio score: {e}")
            return 0
    
    def calculate_protocol_diversity(self, portfolio_data):
        """Calculate protocol diversity score"""
        try:
            if not portfolio_data or 'balances' not in portfolio_data:
                return 0
            
            protocols = set()
            for balance in portfolio_data['balances']:
                if 'protocol' in balance:
                    protocols.add(balance['protocol'])
            
            # Diversity scoring
            if len(protocols) > 10:
                return 100
            elif len(protocols) > 7:
                return 80
            elif len(protocols) > 5:
                return 60
            elif len(protocols) > 3:
                return 40
            elif len(protocols) > 1:
                return 20
            else:
                return 0
                
        except Exception as e:
            print(f"      ⚠️  Error calculating protocol diversity: {e}")
            return 0
    
    def calculate_protocol_risk_score(self, analytics_data):
        """Calculate protocol risk score based on analytics"""
        try:
            if not analytics_data:
                return 0
            
            score = 0
            
            # TVL scoring
            if 'tvl' in analytics_data:
                tvl = float(analytics_data['tvl'])
                if tvl > 1000000:  # > $1M
                    score += 30
                elif tvl > 100000:  # > $100K
                    score += 20
                elif tvl > 10000:  # > $10K
                    score += 10
            
            # Volume scoring
            if 'volume24h' in analytics_data:
                volume = float(analytics_data['volume24h'])
                if volume > 1000000:  # > $1M
                    score += 25
                elif volume > 100000:  # > $100K
                    score += 15
                elif volume > 10000:  # > $10K
                    score += 5
            
            # User count scoring
            if 'userCount' in analytics_data:
                users = int(analytics_data['userCount'])
                if users > 10000:
                    score += 25
                elif users > 1000:
                    score += 15
                elif users > 100:
                    score += 5
            
            # Age scoring (if available)
            if 'createdAt' in analytics_data:
                created_date = datetime.fromisoformat(analytics_data['createdAt'].replace('Z', '+00:00'))
                age_days = (datetime.now() - created_date).days
                if age_days > 365:  # > 1 year
                    score += 20
                elif age_days > 180:  # > 6 months
                    score += 10
            
            return min(score, 100)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating protocol risk score: {e}")
            return 0
    
    # Scoring functions for The Graph
    def calculate_sync_score(self, subgraph_data):
        """Calculate sync status score"""
        try:
            if not subgraph_data:
                return 0
            
            score = 0
            
            # Sync status scoring
            if subgraph_data.get('synced', False):
                score += 50
            
            # Health scoring
            health = subgraph_data.get('health', 'unknown')
            if health == 'healthy':
                score += 30
            elif health == 'unhealthy':
                score += 10
            
            # Chain sync scoring
            if 'chains' in subgraph_data:
                for chain in subgraph_data['chains']:
                    if 'chainHeadBlock' in chain and 'latestBlock' in chain:
                        head_block = int(chain['chainHeadBlock']['number'])
                        latest_block = int(chain['latestBlock']['number'])
                        
                        if head_block > 0 and latest_block > 0:
                            sync_percentage = (latest_block / head_block) * 100
                            if sync_percentage > 95:
                                score += 20
                            elif sync_percentage > 80:
                                score += 10
            
            return min(score, 100)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating sync score: {e}")
            return 0
    
    def calculate_health_score(self, subgraph_data):
        """Calculate health score"""
        try:
            if not subgraph_data:
                return 0
            
            score = 0
            
            # Health status scoring
            health = subgraph_data.get('health', 'unknown')
            if health == 'healthy':
                score += 60
            elif health == 'unhealthy':
                score += 20
            
            # Error checking
            if 'fatalError' in subgraph_data and subgraph_data['fatalError']:
                score -= 40  # Penalty for fatal errors
            
            # Chain health scoring
            if 'chains' in subgraph_data:
                healthy_chains = 0
                total_chains = len(subgraph_data['chains'])
                
                for chain in subgraph_data['chains']:
                    if 'latestBlock' in chain and chain['latestBlock']['number']:
                        healthy_chains += 1
                
                if total_chains > 0:
                    health_percentage = (healthy_chains / total_chains) * 100
                    score += (health_percentage * 0.4)  # Up to 40 points
            
            return max(min(score, 100), 0)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating health score: {e}")
            return 0
    
    def calculate_volume_score(self, dex_data):
        """Calculate volume score for DEX data"""
        try:
            if not dex_data:
                return 0
            
            score = 0
            
            # Volume scoring
            if 'totalVolumeUSD' in dex_data:
                volume = float(dex_data['totalVolumeUSD'])
                if volume > 1000000000:  # > $1B
                    score += 40
                elif volume > 100000000:  # > $100M
                    score += 30
                elif volume > 10000000:  # > $10M
                    score += 20
                elif volume > 1000000:  # > $1M
                    score += 10
            
            # Fee scoring
            if 'totalFeesUSD' in dex_data:
                fees = float(dex_data['totalFeesUSD'])
                if fees > 10000000:  # > $10M
                    score += 30
                elif fees > 1000000:  # > $1M
                    score += 20
                elif fees > 100000:  # > $100K
                    score += 10
            
            # Pool count scoring
            if 'poolCount' in dex_data:
                pools = int(dex_data['poolCount'])
                if pools > 1000:
                    score += 30
                elif pools > 100:
                    score += 20
                elif pools > 10:
                    score += 10
            
            return min(score, 100)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating volume score: {e}")
            return 0
    
    def calculate_dex_liquidity_score(self, dex_data):
        """Calculate liquidity score for DEX data"""
        try:
            if not dex_data:
                return 0
            
            score = 0
            
            # Pool count as liquidity indicator
            if 'poolCount' in dex_data:
                pools = int(dex_data['poolCount'])
                if pools > 5000:
                    score += 50
                elif pools > 1000:
                    score += 40
                elif pools > 500:
                    score += 30
                elif pools > 100:
                    score += 20
                elif pools > 10:
                    score += 10
            
            # Volume as liquidity indicator
            if 'totalVolumeUSD' in dex_data:
                volume = float(dex_data['totalVolumeUSD'])
                if volume > 1000000000:  # > $1B
                    score += 50
                elif volume > 100000000:  # > $100M
                    score += 40
                elif volume > 10000000:  # > $10M
                    score += 30
                elif volume > 1000000:  # > $1M
                    score += 20
                elif volume > 100000:  # > $100K
                    score += 10
            
            return min(score, 100)
            
        except Exception as e:
            print(f"      ⚠️  Error calculating DEX liquidity score: {e}")
            return 0

def main():
    """Test enhanced API integrations"""
    print("🔧 Testing Enhanced API Integrations")
    print("=" * 50)
    
    integrations = EnhancedAPIIntegrations()
    
    # Test Li-Fi
    print("\n🌉 Testing Li-Fi API:")
    lifi_result = integrations.fetch_lifi_quote(
        "0x0000000000000000000000000000000000000000",  # ETH
        "0xA0b86a33E6441b8c4b8C8C8C8C8C8C8C8C8C8C8C",  # USDC
        "1000000000000000000"  # 1 ETH
    )
    
    if lifi_result and lifi_result['success']:
        print(f"  ✅ Li-Fi: Quote found with liquidity score {lifi_result['liquidity_score']}")
        print(f"  ✅ Cross-chain score: {lifi_result['cross_chain_score']}")
    else:
        print("  ❌ Li-Fi: Failed to get quote")
    
    # Test Zapper
    print("\n📊 Testing Zapper API:")
    zapper_result = integrations.fetch_zapper_enhanced_portfolio(
        "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # Vitalik's wallet
    )
    
    if zapper_result and zapper_result['success']:
        print(f"  ✅ Zapper: Portfolio data found with score {zapper_result['portfolio_score']}")
        print(f"  ✅ Protocol diversity: {zapper_result['protocol_diversity']}")
    else:
        print("  ❌ Zapper: Failed to get portfolio data")
    
    # Test The Graph
    print("\n📈 Testing The Graph API:")
    graph_result = integrations.fetch_the_graph_subgraph_data("uniswap/uniswap-v3")
    
    if graph_result and graph_result['success']:
        if 'sync_score' in graph_result:
            print(f"  ✅ The Graph: Subgraph data found with sync score {graph_result['sync_score']}")
            print(f"  ✅ Health score: {graph_result['health_score']}")
        else:
            print(f"  ✅ The Graph: {graph_result.get('message', 'API working')}")
    else:
        print("  ❌ The Graph: Failed to get subgraph data")
    
    print("\n🎉 Enhanced API integration testing complete!")

if __name__ == "__main__":
    main() 