# Enhanced Comprehensive Parallel APIs
# This file implements comprehensive parallel API endpoints based on official documentation

import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import json
from typing import List, Dict, Any, Optional

class ComprehensiveParallelAPIManager:
    """Comprehensive parallel API manager with multiple endpoints per service"""
    
    def __init__(self, max_workers=15):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
    
    def parallel_request(self, urls: List[str], headers: Dict = None, params: Dict = None, timeout: int = 15):
        """Make parallel requests to multiple endpoints and return ALL successful results"""
        def make_request(url):
            try:
                response = self.session.get(url, headers=headers, params=params, timeout=timeout)
                return {
                    'url': url,
                    'status_code': response.status_code,
                    'data': response.json() if response.status_code == 200 else None,
                    'success': response.status_code == 200
                }
            except Exception as e:
                return {
                    'url': url,
                    'status_code': None,
                    'data': None,
                    'success': False,
                    'error': str(e)
                }
        
        # Submit all requests in parallel
        futures = [self.executor.submit(make_request, url) for url in urls]
        
        # Collect ALL successful results
        all_results = []
        for future in as_completed(futures):
            result = future.result()
            if result['success'] and result['data']:
                all_results.append(result['data'])
        
        return all_results if all_results else None

# Load comprehensive endpoints from research
def load_comprehensive_endpoints():
    """Load comprehensive endpoints from research file"""
    try:
        with open('comprehensive_api_endpoints.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️  comprehensive_api_endpoints.json not found, using default endpoints")
        return {}

# Enhanced API endpoints with comprehensive coverage
COMPREHENSIVE_API_ENDPOINTS = {
    'etherscan': {
        'contract_verification': [
            'https://api.etherscan.io/api?module=contract&action=getsourcecode&address={address}&apikey={key}',
            'https://api.etherscan.io/api?module=contract&action=getabi&address={address}&apikey={key}',
            'https://api.etherscan.io/api?module=contract&action=getcontractcreation&contractaddresses={address}&apikey={key}',
            'https://api.etherscan.io/api?module=contract&action=verifysourcecode&apikey={key}'
        ],
        'holder_data': [
            'https://api.etherscan.io/api?module=token&action=tokenholderlist&contractaddress={address}&apikey={key}',
            'https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={address}&apikey={key}',
            'https://api.etherscan.io/api?module=stats&action=tokensupply&contractaddress={address}&apikey={key}',
            'https://api.etherscan.io/api?module=stats&action=tokensupplyhistory&contractaddress={address}&apikey={key}'
        ],
        'account_data': [
            'https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={key}',
            'https://api.etherscan.io/api?module=account&action=balancemulti&address={address}&tag=latest&apikey={key}',
            'https://api.etherscan.io/api?module=account&action=txlist&address={address}&apikey={key}',
            'https://api.etherscan.io/api?module=account&action=txlistinternal&address={address}&apikey={key}'
        ],
        'token_transfers': [
            'https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={address}&apikey={key}',
            'https://api.etherscan.io/api?module=account&action=tokennfttx&contractaddress={address}&apikey={key}',
            'https://api.etherscan.io/api?module=account&action=token1155tx&contractaddress={address}&apikey={key}'
        ]
    },
    
    'coingecko': {
        'token_info': [
            'https://api.coingecko.com/api/v3/coins/ethereum/contract/{address}',
            'https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={address}&vs_currencies=usd,eur,btc',
            'https://api.coingecko.com/api/v3/coins/{id}',
            'https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days=30',
            'https://api.coingecko.com/api/v3/coins/{id}/tickers',
            'https://api.coingecko.com/api/v3/coins/{id}/market_chart/range?vs_currency=usd&from={from}&to={to}'
        ],
        'market_data': [
            'https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days=30',
            'https://api.coingecko.com/api/v3/coins/{id}/tickers',
            'https://api.coingecko.com/api/v3/coins/{id}/market_chart/range?vs_currency=usd&from={from}&to={to}',
            'https://api.coingecko.com/api/v3/coins/{id}/ohlc?vs_currency=usd&days=30',
            'https://api.coingecko.com/api/v3/coins/{id}/status_updates',
            'https://api.coingecko.com/api/v3/coins/{id}/community_data',
            'https://api.coingecko.com/api/v3/coins/{id}/developer_data',
            'https://api.coingecko.com/api/v3/coins/{id}/public_interest_score'
        ],
        'global_data': [
            'https://api.coingecko.com/api/v3/global',
            'https://api.coingecko.com/api/v3/global/decentralized_finance_defi',
            'https://api.coingecko.com/api/v3/coins/categories',
            'https://api.coingecko.com/api/v3/search/trending'
        ]
    },
    
    'moralis': {
        'token_metadata': [
            'https://deep-index.moralis.io/api/v2/erc20/{address}',
            'https://deep-index.moralis.io/api/v2/erc20/{address}?chain=eth',
            'https://deep-index.moralis.io/api/v2/erc20/{address}?chain=bsc',
            'https://deep-index.moralis.io/api/v2/erc20/{address}?chain=polygon'
        ],
        'token_price': [
            'https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain=eth',
            'https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain=bsc',
            'https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain=polygon'
        ],
        'account_data': [
            'https://deep-index.moralis.io/api/v2/{address}/balance?chain=eth',
            'https://deep-index.moralis.io/api/v2/{address}/erc20?chain=eth&limit=100',
            'https://deep-index.moralis.io/api/v2/{address}/nft?chain=eth&limit=100',
            'https://deep-index.moralis.io/api/v2/{address}/internal?chain=eth&limit=100'
        ],
        'token_transfers': [
            'https://deep-index.moralis.io/api/v2/erc20/{address}/transfers?chain=eth&limit=100',
            'https://deep-index.moralis.io/api/v2/{address}/erc20/transfers?chain=eth&limit=100',
            'https://deep-index.moralis.io/api/v2/erc20/{address}/holders?chain=eth&limit=100'
        ]
    },
    
    '1inch': {
        'token_metadata': [
            'https://api.1inch.dev/token/v1.0/1/metadata?address={address}',
            'https://api.1inch.dev/token/v1.1/1/metadata?address={address}',
            'https://api.1inch.dev/token/v1.2/1/metadata?address={address}',
            'https://api.1inch.dev/token/v1.0/1/price?address={address}',
            'https://api.1inch.dev/token/v1.0/1/search?query={query}'
        ],
        'quote': [
            'https://api.1inch.dev/swap/v5.2/1/quote?src={src}&dst={dst}&amount={amount}',
            'https://api.1inch.dev/swap/v5.0/1/quote?src={src}&dst={dst}&amount={amount}',
            'https://api.1inch.dev/swap/v4.0/1/quote?src={src}&dst={dst}&amount={amount}',
            'https://api.1inch.dev/swap/v5.2/1/quote?src={src}&dst={dst}&amount={amount}&meta=true'
        ],
        'portfolio': [
            'https://api.1inch.dev/portfolio/v1.0/1/portfolio?address={address}',
            'https://api.1inch.dev/portfolio/v1.0/1/portfolio/tokens?address={address}',
            'https://api.1inch.dev/portfolio/v1.0/1/portfolio/protocols?address={address}'
        ],
        'defi': [
            'https://api.1inch.dev/defi/v1.0/1/protocols',
            'https://api.1inch.dev/defi/v1.0/1/protocols/{protocol}',
            'https://api.1inch.dev/defi/v1.0/1/protocols/{protocol}/tokens'
        ]
    },
    
    'zapper': {
        'portfolio': [
            'https://api.zapper.xyz/v2/portfolio/{address}',
            'https://api.zapper.xyz/v1/portfolio/{address}',
            'https://public.zapper.xyz/graphql',
            'https://api.zapper.xyz/v2/portfolio/{address}/tokens',
            'https://api.zapper.xyz/v2/portfolio/{address}/protocols'
        ],
        'protocols': [
            'https://api.zapper.xyz/v2/protocols',
            'https://api.zapper.xyz/v2/protocols/{protocol}',
            'https://api.zapper.xyz/v2/protocols/{protocol}/tokens',
            'https://api.zapper.xyz/v2/protocols/{protocol}/pools'
        ],
        'tokens': [
            'https://api.zapper.xyz/v2/tokens',
            'https://api.zapper.xyz/v2/tokens/{token}',
            'https://api.zapper.xyz/v2/tokens/prices',
            'https://api.zapper.xyz/v2/tokens/{token}/price',
            'https://api.zapper.xyz/v2/tokens/{token}/metadata'
        ]
    },
    
    'defillama': {
        'token_info': [
            'https://api.llama.fi/v2/tokens/ethereum:{address}',
            'https://api.llama.fi/v2/tokens/bsc:{address}',
            'https://api.llama.fi/v2/tokens/polygon:{address}',
            'https://api.llama.fi/v2/tokens/{chain}:{address}/price',
            'https://api.llama.fi/v2/tokens/{chain}:{address}/chart'
        ],
        'protocols': [
            'https://api.llama.fi/v2/protocols',
            'https://api.llama.fi/v2/protocol/{protocol}',
            'https://api.llama.fi/v2/protocol/{protocol}/chart',
            'https://api.llama.fi/v2/protocol/{protocol}/tvl'
        ],
        'chains': [
            'https://api.llama.fi/v2/chains',
            'https://api.llama.fi/v2/chains/{chain}',
            'https://api.llama.fi/v2/chains/{chain}/tvl',
            'https://api.llama.fi/v2/chains/{chain}/chart'
        ],
        'trending': [
            'https://api.llama.fi/v2/trending',
            'https://api.llama.fi/v2/trending/tokens'
        ]
    },
    
    'ethplorer': {
        'token_info': [
            'https://api.ethplorer.io/getTokenInfo/{address}?apiKey={key}',
            'https://api.ethplorer.io/getAddressInfo/{address}?apiKey={key}',
            'https://api.ethplorer.io/getAddressHistory/{address}?apiKey={key}',
            'https://api.ethplorer.io/getTokenPrice/{address}?apiKey={key}',
            'https://api.ethplorer.io/getTokenHistory/{address}?apiKey={key}'
        ],
        'token_data': [
            'https://api.ethplorer.io/getTokenHolders/{address}?apiKey={key}',
            'https://api.ethplorer.io/getTokenTransactions/{address}?apiKey={key}',
            'https://api.ethplorer.io/getTokenTransfers/{address}?apiKey={key}',
            'https://api.ethplorer.io/getTokenOperations/{address}?apiKey={key}'
        ],
        'stats': [
            'https://api.ethplorer.io/getTopTokens?apiKey={key}',
            'https://api.ethplorer.io/getTopTokensByHolders?apiKey={key}',
            'https://api.ethplorer.io/getTopTokensByOperations?apiKey={key}',
            'https://api.ethplorer.io/getTopTokensByTransfers?apiKey={key}',
            'https://api.ethplorer.io/getTopTokensByVolume?apiKey={key}',
            'https://api.ethplorer.io/getTopTokensByMarketCap?apiKey={key}'
        ]
    }
}

def get_comprehensive_endpoints(service: str, endpoint_type: str, **kwargs) -> List[str]:
    """Get formatted URLs for comprehensive parallel requests"""
    if service not in COMPREHENSIVE_API_ENDPOINTS or endpoint_type not in COMPREHENSIVE_API_ENDPOINTS[service]:
        return []
    
    urls = []
    for url_template in COMPREHENSIVE_API_ENDPOINTS[service][endpoint_type]:
        try:
            formatted_url = url_template.format(**kwargs)
            urls.append(formatted_url)
        except KeyError as e:
            print(f"Missing parameter for {service} {endpoint_type}: {e}")
            continue
    
    return urls

def comprehensive_parallel_fetch(service: str, endpoint_type: str, headers: Dict = None, **kwargs):
    """Fetch data from comprehensive parallel endpoints - returns ALL successful results"""
    urls = get_comprehensive_endpoints(service, endpoint_type, **kwargs)
    
    if not urls:
        return None
    
    with ComprehensiveParallelAPIManager() as api:
        results = api.parallel_request(urls, headers=headers)
        if results:
            print(f"✅ {service} {endpoint_type}: {len(results)} successful results")
        return results

# Enhanced API functions for comprehensive data fetching
def fetch_etherscan_comprehensive(token_address: str, api_key: str, endpoint_type: str = 'contract_verification'):
    """Fetch Etherscan data from comprehensive parallel endpoints"""
    return comprehensive_parallel_fetch(
        'etherscan', 
        endpoint_type, 
        address=token_address, 
        key=api_key
    )

def fetch_coingecko_comprehensive(token_address: str = None, token_id: str = None, endpoint_type: str = 'token_info'):
    """Fetch CoinGecko data from comprehensive parallel endpoints"""
    if token_id:
        return comprehensive_parallel_fetch(
            'coingecko', 
            endpoint_type, 
            id=token_id
        )
    else:
        return comprehensive_parallel_fetch(
            'coingecko', 
            endpoint_type, 
            address=token_address
        )

def fetch_moralis_comprehensive(token_address: str, api_key: str, endpoint_type: str = 'token_metadata'):
    """Fetch Moralis data from comprehensive parallel endpoints"""
    headers = {'X-API-Key': api_key}
    return comprehensive_parallel_fetch(
        'moralis', 
        endpoint_type, 
        headers=headers,
        address=token_address
    )

def fetch_1inch_comprehensive(token_address: str, api_key: str, endpoint_type: str = 'token_metadata'):
    """Fetch 1inch data from comprehensive parallel endpoints"""
    headers = {'Authorization': f'Bearer {api_key}'}
    return comprehensive_parallel_fetch(
        '1inch', 
        endpoint_type, 
        headers=headers,
        address=token_address
    )

def fetch_zapper_comprehensive(address: str, api_key: str, endpoint_type: str = 'portfolio'):
    """Fetch Zapper data from comprehensive parallel endpoints"""
    headers = {'Authorization': f'Basic {api_key}'}
    return comprehensive_parallel_fetch(
        'zapper', 
        endpoint_type, 
        headers=headers,
        address=address
    )

def fetch_defillama_comprehensive(token_address: str, endpoint_type: str = 'token_info'):
    """Fetch DeFiLlama data from comprehensive parallel endpoints"""
    return comprehensive_parallel_fetch(
        'defillama', 
        endpoint_type, 
        address=token_address
    )

def fetch_ethplorer_comprehensive(token_address: str, api_key: str, endpoint_type: str = 'token_info'):
    """Fetch Ethplorer data from comprehensive parallel endpoints"""
    return comprehensive_parallel_fetch(
        'ethplorer', 
        endpoint_type, 
        address=token_address,
        key=api_key
    )

# Comprehensive data fetching function
def fetch_comprehensive_token_data(token_address: str, api_keys: Dict[str, str]):
    """Fetch comprehensive token data from all available APIs - returns ALL results"""
    print(f"🔍 Fetching comprehensive data for {token_address}...")
    
    results = {}
    
    # Etherscan data
    if 'ETHERSCAN_API_KEY' in api_keys:
        print("  📊 Fetching Etherscan data...")
        results['etherscan'] = {
            'contract_verification': fetch_etherscan_comprehensive(token_address, api_keys['ETHERSCAN_API_KEY'], 'contract_verification'),
            'holder_data': fetch_etherscan_comprehensive(token_address, api_keys['ETHERSCAN_API_KEY'], 'holder_data'),
            'account_data': fetch_etherscan_comprehensive(token_address, api_keys['ETHERSCAN_API_KEY'], 'account_data'),
            'token_transfers': fetch_etherscan_comprehensive(token_address, api_keys['ETHERSCAN_API_KEY'], 'token_transfers')
        }
    
    # CoinGecko data
    print("  📊 Fetching CoinGecko data...")
    results['coingecko'] = {
        'token_info': fetch_coingecko_comprehensive(token_address, endpoint_type='token_info'),
        'market_data': fetch_coingecko_comprehensive(token_address, endpoint_type='market_data'),
        'global_data': fetch_coingecko_comprehensive(token_address, endpoint_type='global_data')
    }
    
    # Moralis data
    if 'MORALIS_API_KEY' in api_keys:
        print("  📊 Fetching Moralis data...")
        results['moralis'] = {
            'token_metadata': fetch_moralis_comprehensive(token_address, api_keys['MORALIS_API_KEY'], 'token_metadata'),
            'token_price': fetch_moralis_comprehensive(token_address, api_keys['MORALIS_API_KEY'], 'token_price'),
            'account_data': fetch_moralis_comprehensive(token_address, api_keys['MORALIS_API_KEY'], 'account_data'),
            'token_transfers': fetch_moralis_comprehensive(token_address, api_keys['MORALIS_API_KEY'], 'token_transfers')
        }
    
    # 1inch data
    if '1INCH_API_KEY' in api_keys:
        print("  📊 Fetching 1inch data...")
        results['1inch'] = {
            'token_metadata': fetch_1inch_comprehensive(token_address, api_keys['1INCH_API_KEY'], 'token_metadata'),
            'quote': fetch_1inch_comprehensive(token_address, api_keys['1INCH_API_KEY'], 'quote'),
            'portfolio': fetch_1inch_comprehensive(token_address, api_keys['1INCH_API_KEY'], 'portfolio'),
            'defi': fetch_1inch_comprehensive(token_address, api_keys['1INCH_API_KEY'], 'defi')
        }
    
    # Zapper data
    if 'ZAPPER_API_KEY' in api_keys:
        print("  📊 Fetching Zapper data...")
        results['zapper'] = {
            'portfolio': fetch_zapper_comprehensive(token_address, api_keys['ZAPPER_API_KEY'], 'portfolio'),
            'protocols': fetch_zapper_comprehensive(token_address, api_keys['ZAPPER_API_KEY'], 'protocols'),
            'tokens': fetch_zapper_comprehensive(token_address, api_keys['ZAPPER_API_KEY'], 'tokens')
        }
    
    # DeFiLlama data
    print("  📊 Fetching DeFiLlama data...")
    results['defillama'] = {
        'token_info': fetch_defillama_comprehensive(token_address, 'token_info'),
        'protocols': fetch_defillama_comprehensive(token_address, 'protocols'),
        'chains': fetch_defillama_comprehensive(token_address, 'chains'),
        'trending': fetch_defillama_comprehensive(token_address, 'trending')
    }
    
    # Ethplorer data
    if 'ETHPLORER_API_KEY' in api_keys:
        print("  📊 Fetching Ethplorer data...")
        results['ethplorer'] = {
            'token_info': fetch_ethplorer_comprehensive(token_address, api_keys['ETHPLORER_API_KEY'], 'token_info'),
            'token_data': fetch_ethplorer_comprehensive(token_address, api_keys['ETHPLORER_API_KEY'], 'token_data'),
            'stats': fetch_ethplorer_comprehensive(token_address, api_keys['ETHPLORER_API_KEY'], 'stats')
        }
    
    return results

# Test function
def test_comprehensive_apis():
    """Test comprehensive API functionality"""
    print("🧪 Testing comprehensive parallel APIs...")
    
    # Test with DAI token
    test_address = "0x6b175474e89094c44da98b954eedeac495271d0f"
    api_keys = {
        'ETHERSCAN_API_KEY': 'BV4MJ4DCANJS1X7PCP6WZJN5SFGBIJ8KX8'
    }
    
    # Test comprehensive data fetching
    results = fetch_comprehensive_token_data(test_address, api_keys)
    
    print(f"\n✅ Comprehensive API test completed!")
    print(f"📊 Fetched data from {len(results)} services")
    
    for service, data in results.items():
        successful_endpoints = sum(1 for endpoint_data in data.values() if endpoint_data is not None)
        total_endpoints = len(data)
        print(f"  {service.upper()}: {successful_endpoints}/{total_endpoints} endpoints successful")
    
    return results

if __name__ == "__main__":
    test_comprehensive_apis() 