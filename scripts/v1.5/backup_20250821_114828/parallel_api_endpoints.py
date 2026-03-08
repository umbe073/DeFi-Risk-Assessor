# Parallel API Endpoints Implementation
# This file implements multiple endpoints for each API service with parallelized requests

import asyncio
import aiohttp
import concurrent.futures
from typing import List, Dict, Any, Optional
import time
import json

class ParallelAPIEndpoints:
    """Parallel API endpoints for improved data fetching"""
    
    def __init__(self):
        self.session = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def parallel_request(self, urls: List[str], headers: Dict = None, params: Dict = None, timeout: int = 15):
        """Make parallel requests to multiple endpoints"""
        results = []
        
        def make_request(url):
            try:
                import requests
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
        
        # Collect results
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
        
        return results

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
    },
    
    'social': {
        'twitter': [
            'https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10',
            'https://api.twitter.com/2/users/by/username/{username}',
            'https://api.twitter.com/2/tweets/counts/recent?query={query}'
        ],
        'telegram': [
            'https://api.telegram.org/bot{token}/getUpdates',
            'https://api.telegram.org/bot{token}/getMe',
            'https://api.telegram.org/bot{token}/getChat?chat_id={chat_id}'
        ],
        'reddit': [
            'https://www.reddit.com/r/{subreddit}/search.json?q={query}&t=month',
            'https://www.reddit.com/r/{subreddit}/hot.json',
            'https://www.reddit.com/r/{subreddit}/new.json'
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
    
    with ParallelAPIEndpoints() as api:
        results = api.parallel_request(urls, headers=headers)
    
    # Return the first successful result
    for result in results:
        if result['success'] and result['data']:
            return result['data']
    
    return None

# Example usage functions
def fetch_etherscan_data_parallel(token_address: str, api_key: str):
    """Fetch Etherscan data from multiple endpoints"""
    return parallel_fetch_data(
        'etherscan', 
        'contract_verification', 
        address=token_address, 
        key=api_key
    )

def fetch_coingecko_data_parallel(token_address: str, token_id: str = None):
    """Fetch CoinGecko data from multiple endpoints"""
    if token_id:
        return parallel_fetch_data(
            'coingecko', 
            'market_data', 
            id=token_id
        )
    else:
        return parallel_fetch_data(
            'coingecko', 
            'token_info', 
            address=token_address
        )

def fetch_moralis_data_parallel(token_address: str, api_key: str):
    """Fetch Moralis data from multiple endpoints"""
    headers = {'X-API-Key': api_key}
    return parallel_fetch_data(
        'moralis', 
        'token_metadata', 
        headers=headers,
        address=token_address
    )

def fetch_1inch_data_parallel(token_address: str, api_key: str):
    """Fetch 1inch data from multiple endpoints"""
    headers = {'Authorization': f'Bearer {api_key}'}
    return parallel_fetch_data(
        '1inch', 
        'token_metadata', 
        headers=headers,
        address=token_address
    )

if __name__ == "__main__":
    # Test parallel fetching
    print("Testing parallel API endpoints...")
    
    # Test with a sample token
    test_address = "0x6b175474e89094c44da98b954eedeac495271d0f"  # DAI
    
    # Test Etherscan
    print(f"\nTesting Etherscan parallel endpoints for {test_address}...")
    etherscan_result = fetch_etherscan_data_parallel(test_address, "YOUR_API_KEY")
    print(f"Etherscan result: {'Success' if etherscan_result else 'Failed'}")
    
    # Test CoinGecko
    print(f"\nTesting CoinGecko parallel endpoints for {test_address}...")
    coingecko_result = fetch_coingecko_data_parallel(test_address)
    print(f"CoinGecko result: {'Success' if coingecko_result else 'Failed'}")
    
    print("\nParallel API endpoints test completed!") 