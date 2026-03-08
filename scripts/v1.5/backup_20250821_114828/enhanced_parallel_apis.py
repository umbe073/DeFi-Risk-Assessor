# Enhanced Parallel API Functions
# This file provides parallel API endpoints for improved data fetching

import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import List, Dict, Any, Optional

class ParallelAPIManager:
    """Manages parallel API requests for multiple endpoints"""
    
    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
    
    def parallel_request(self, urls: List[str], headers: Dict = None, params: Dict = None, timeout: int = 15):
        """Make parallel requests to multiple endpoints and return first successful result"""
        def make_request(url):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
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
        
        # Return the first successful result
        for future in as_completed(futures):
            result = future.result()
            if result['success'] and result['data']:
                return result['data']
        
        return None

# Multiple endpoints for each API service
API_ENDPOINTS = {
    'etherscan': {
        'contract_verification': [
            'https://api.etherscan.io/api?module=contract&action=getsourcecode&address={address}&apikey={key}',
            'https://api.etherscan.io/api?module=contract&action=getabi&address={address}&apikey={key}',
            'https://api.etherscan.io/api?module=contract&action=getcontractcreation&contractaddresses={address}&apikey={key}'
        ],
        'holder_data': [
            'https://api.etherscan.io/api?module=token&action=tokenholderlist&contractaddress={address}&apikey={key}',
            'https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={address}&apikey={key}',
            'https://api.etherscan.io/api?module=stats&action=tokensupply&contractaddress={address}&apikey={key}'
        ]
    },
    
    'coingecko': {
        'token_info': [
            'https://api.coingecko.com/api/v3/coins/ethereum/contract/{address}',
            'https://api.coingecko.com/api/v3/coins/{id}',
            'https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={address}&vs_currencies=usd,eur,btc'
        ],
        'market_data': [
            'https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days=30',
            'https://api.coingecko.com/api/v3/coins/{id}/tickers',
            'https://api.coingecko.com/api/v3/coins/{id}/market_chart/range?vs_currency=usd&from={from}&to={to}'
        ]
    },
    
    'moralis': {
        'token_metadata': [
            'https://deep-index.moralis.io/api/v2/erc20/{address}',
            'https://deep-index.moralis.io/api/v2/erc20/{address}?chain=eth',
            'https://deep-index.moralis.io/api/v2/erc20/{address}?chain=bsc'
        ],
        'token_price': [
            'https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain=eth',
            'https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain=bsc',
            'https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain=polygon'
        ]
    },
    
    '1inch': {
        'token_metadata': [
            'https://api.1inch.dev/token/v1.0/1/metadata?address={address}',
            'https://api.1inch.dev/token/v1.1/1/metadata?address={address}',
            'https://api.1inch.dev/token/v1.2/1/metadata?address={address}'
        ],
        'quote': [
            'https://api.1inch.dev/swap/v5.2/1/quote?src={src}&dst={dst}&amount={amount}',
            'https://api.1inch.dev/swap/v5.0/1/quote?src={src}&dst={dst}&amount={amount}',
            'https://api.1inch.dev/swap/v4.0/1/quote?src={src}&dst={dst}&amount={amount}'
        ]
    },
    
    'zapper': {
        'portfolio': [
            'https://api.zapper.xyz/v2/portfolio/{address}',
            'https://api.zapper.xyz/v1/portfolio/{address}',
            'https://public.zapper.xyz/graphql'
        ]
    },
    
    'defillama': {
        'token_info': [
            'https://api.llama.fi/v2/tokens/ethereum:{address}',
            'https://api.llama.fi/v2/tokens/bsc:{address}',
            'https://api.llama.fi/v2/tokens/polygon:{address}'
        ],
        'protocols': [
            'https://api.llama.fi/v2/protocols',
            'https://api.llama.fi/v2/protocol/{protocol}',
            'https://api.llama.fi/v2/chains'
        ]
    },
    
    'ethplorer': {
        'token_info': [
            'https://api.ethplorer.io/getTokenInfo/{address}?apiKey={key}',
            'https://api.ethplorer.io/getAddressInfo/{address}?apiKey={key}',
            'https://api.ethplorer.io/getAddressHistory/{address}?apiKey={key}'
        ]
    }
}

def get_parallel_endpoints(service: str, endpoint_type: str, **kwargs) -> List[str]:
    """Get formatted URLs for parallel requests"""
    if service not in API_ENDPOINTS or endpoint_type not in API_ENDPOINTS[service]:
        return []
    
    urls = []
    for url_template in API_ENDPOINTS[service][endpoint_type]:
        try:
            formatted_url = url_template.format(**kwargs)
            urls.append(formatted_url)
        except KeyError as e:
            print(f"Missing parameter for {service} {endpoint_type}: {e}")
            continue
    
    return urls

def parallel_fetch_data(service: str, endpoint_type: str, headers: Dict = None, **kwargs):
    """Fetch data from multiple endpoints in parallel"""
    urls = get_parallel_endpoints(service, endpoint_type, **kwargs)
    
    if not urls:
        return None
    
    with ParallelAPIManager() as api:
        return api.parallel_request(urls, headers=headers)

# Enhanced API functions for the main script
def fetch_etherscan_parallel(token_address: str, api_key: str, endpoint_type: str = 'contract_verification'):
    """Fetch Etherscan data from multiple endpoints in parallel"""
    return parallel_fetch_data(
        'etherscan', 
        endpoint_type, 
        address=token_address, 
        key=api_key
    )

def fetch_coingecko_parallel(token_address: str = None, token_id: str = None, endpoint_type: str = 'token_info'):
    """Fetch CoinGecko data from multiple endpoints in parallel"""
    if token_id:
        return parallel_fetch_data(
            'coingecko', 
            endpoint_type, 
            id=token_id
        )
    else:
        return parallel_fetch_data(
            'coingecko', 
            endpoint_type, 
            address=token_address
        )

def fetch_moralis_parallel(token_address: str, api_key: str, endpoint_type: str = 'token_metadata'):
    """Fetch Moralis data from multiple endpoints in parallel"""
    headers = {'X-API-Key': api_key}
    return parallel_fetch_data(
        'moralis', 
        endpoint_type, 
        headers=headers,
        address=token_address
    )

def fetch_1inch_parallel(token_address: str, api_key: str, endpoint_type: str = 'token_metadata'):
    """Fetch 1inch data from multiple endpoints in parallel"""
    headers = {'Authorization': f'Bearer {api_key}'}
    return parallel_fetch_data(
        '1inch', 
        endpoint_type, 
        headers=headers,
        address=token_address
    )

def fetch_defillama_parallel(token_address: str, endpoint_type: str = 'token_info'):
    """Fetch DeFiLlama data from multiple endpoints in parallel"""
    return parallel_fetch_data(
        'defillama', 
        endpoint_type, 
        address=token_address
    )

def fetch_ethplorer_parallel(token_address: str, api_key: str, endpoint_type: str = 'token_info'):
    """Fetch Ethplorer data from multiple endpoints in parallel"""
    return parallel_fetch_data(
        'ethplorer', 
        endpoint_type, 
        address=token_address,
        key=api_key
    )

# Test function
def test_parallel_apis():
    """Test parallel API functionality"""
    print("Testing parallel API endpoints...")
    
    # Test with DAI token
    test_address = "0x6b175474e89094c44da98b954eedeac495271d0f"
    api_key = "BV4MJ4DCANJS1X7PCP6WZJN5SFGBIJ8KX8"  # Etherscan key
    
    # Test Etherscan
    print(f"\nTesting Etherscan parallel endpoints for {test_address}...")
    etherscan_result = fetch_etherscan_parallel(test_address, api_key)
    print(f"Etherscan result: {'Success' if etherscan_result else 'Failed'}")
    
    # Test CoinGecko
    print(f"\nTesting CoinGecko parallel endpoints for {test_address}...")
    coingecko_result = fetch_coingecko_parallel(test_address)
    print(f"CoinGecko result: {'Success' if coingecko_result else 'Failed'}")
    
    print("\nParallel API test completed!")

if __name__ == "__main__":
    test_parallel_apis() 