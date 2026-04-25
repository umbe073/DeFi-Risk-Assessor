#!/usr/bin/env python3
"""
Comprehensive API System
Calls multiple alternative APIs to find missing values
Etherscan, CoinMarketCap, DeFi protocols, and more
"""

import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime
import time

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

class ComprehensiveAPISystem:
    """Comprehensive system that calls multiple APIs to find missing values"""
    
    def __init__(self):
        self.api_keys = self.load_api_keys()
        self.data_sources = {
            'coingecko': self.fetch_coingecko_data,
            'etherscan': self.fetch_etherscan_data,
            'coinmarketcap': self.fetch_coinmarketcap_data,
            'defillama': self.fetch_defillama_data,
            'moralis': self.fetch_moralis_data,
            'alchemy': self.fetch_alchemy_data
        }
    
    def load_api_keys(self):
        """Load API keys from environment"""
        from dotenv import load_dotenv
        load_dotenv()
        
        return {
            'ETHERSCAN_API_KEY': os.getenv('ETHERSCAN_API_KEY'),
            'COINMARKETCAP_API_KEY': os.getenv('COINMARKETCAP_API_KEY'),
            'MORALIS_API_KEY': os.getenv('MORALIS_API_KEY'),
            'ALCHEMY_API_KEY': os.getenv('ALCHEMY_API_KEY')
        }
    
    def fetch_coingecko_data(self, symbol, address):
        """Fetch data from CoinGecko API"""
        try:
            # Map symbol to CoinGecko ID
            symbol_to_id = {
                'AAVE': 'aave', 'CHZ': 'chiliz', 'COMP': 'compound-governance-token',
                'USDC': 'usd-coin', 'USDT': 'tether', 'WBTC': 'wrapped-bitcoin',
                'LINK': 'chainlink', '1INCH': '1inch', 'POL': 'polygon',
                'UNI': 'uniswap', 'DAI': 'dai', 'GRT': 'the-graph',
                'MKR': 'maker', 'SUSHI': 'sushi', 'QNT': 'quant-network',
                'GALA': 'galaxy', 'MANA': 'decentraland', 'SAND': 'the-sandbox',
                'BAT': 'basic-attention-token', 'OP': 'optimism', 'TRX': 'tron'
            }
            
            coin_id = symbol_to_id.get(symbol)
            if not coin_id:
                return None
            
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                market_data = data.get('market_data', {})
                
                return {
                    'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                    'volume_24h': market_data.get('total_volume', {}).get('usd', 0),
                    'price': market_data.get('current_price', {}).get('usd', 0),
                    'source': 'coingecko'
                }
        except Exception as e:
            print(f"    ❌ CoinGecko error: {e}")
        return None
    
    def fetch_etherscan_data(self, address):
        """Fetch data from Etherscan API"""
        try:
            api_key = self.api_keys.get('ETHERSCAN_API_KEY')
            if not api_key:
                return None
            
            # Get token info from Etherscan
            url = "https://api.etherscan.io/api"
            params = {
                'module': 'token',
                'action': 'tokeninfo',
                'contractaddress': address,
                'apikey': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    result = data.get('result', [{}])[0]
                    
                    return {
                        'holders': int(result.get('holders', 0)),
                        'total_supply': int(result.get('totalSupply', 0)),
                        'source': 'etherscan'
                    }
        except Exception as e:
            print(f"    ❌ Etherscan error: {e}")
        return None
    
    def fetch_coinmarketcap_data(self, symbol):
        """Fetch data from CoinMarketCap API"""
        try:
            api_key = self.api_keys.get('COINMARKETCAP_API_KEY')
            if not api_key:
                return None
            
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
            headers = {
                'X-CMC_PRO_API_KEY': api_key,
                'Accept': 'application/json'
            }
            params = {'symbol': symbol}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and symbol in data['data']:
                    token_data = data['data'][symbol]
                    quote = token_data.get('quote', {}).get('USD', {})
                    
                    return {
                        'market_cap': quote.get('market_cap', 0),
                        'volume_24h': quote.get('volume_24h', 0),
                        'price': quote.get('price', 0),
                        'source': 'coinmarketcap'
                    }
        except Exception as e:
            print(f"    ❌ CoinMarketCap error: {e}")
        return None
    
    def fetch_defillama_data(self, address):
        """Fetch liquidity data from DeFiLlama API"""
        try:
            # Try to get token data from DeFiLlama
            url = f"https://api.llama.fi/token/{address}"
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'liquidity': data.get('tvl', 0),
                    'source': 'defillama'
                }
        except Exception as e:
            print(f"    ❌ DeFiLlama error: {e}")
        return None
    
    def fetch_moralis_data(self, address):
        """Fetch data from Moralis API"""
        try:
            api_key = self.api_keys.get('MORALIS_API_KEY')
            if not api_key:
                return None
            
            # Get token holders from Moralis
            url = f"https://deep-index.moralis.io/api/v2/{address}/owners"
            headers = {
                'X-API-Key': api_key,
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                return {
                    'holders': data.get('total', 0),
                    'source': 'moralis'
                }
        except Exception as e:
            print(f"    ❌ Moralis error: {e}")
        return None
    
    def fetch_alchemy_data(self, address):
        """Fetch data from Alchemy API"""
        try:
            api_key = self.api_keys.get('ALCHEMY_API_KEY')
            if not api_key:
                return None
            
            # Get token metadata from Alchemy
            url = f"https://eth-mainnet.g.alchemy.com/v2/{api_key}"
            headers = {'Content-Type': 'application/json'}
            payload = {
                'jsonrpc': '2.0',
                'method': 'alchemy_getTokenMetadata',
                'params': [address],
                'id': 1
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    result = data['result']
                    
                    return {
                        'name': result.get('name'),
                        'symbol': result.get('symbol'),
                        'decimals': result.get('decimals'),
                        'source': 'alchemy'
                    }
        except Exception as e:
            print(f"    ❌ Alchemy error: {e}")
        return None
    
    def get_comprehensive_data(self, symbol, token_name, address):
        """Get comprehensive data from all available sources"""
        print(f"\n🔍 Comprehensive Data for {token_name} ({symbol})")
        
        # Collect data from all sources
        market_caps = []
        volumes = []
        holders = []
        liquidity_values = []
        prices = []
        
        # Try all data sources
        for source_name, fetch_func in self.data_sources.items():
            try:
                if source_name == 'coingecko':
                    data = fetch_func(symbol, address)
                else:
                    data = fetch_func(address)
                
                if data:
                    print(f"  📊 {source_name.title()}: {data.get('source', 'unknown')}")
                    
                    # Collect market data
                    if data.get('market_cap', 0) > 0:
                        market_caps.append(data['market_cap'])
                        print(f"    Market Cap: ${data['market_cap']:,.0f}")
                    
                    if data.get('volume_24h', 0) > 0:
                        volumes.append(data['volume_24h'])
                        print(f"    Volume 24h: ${data['volume_24h']:,.0f}")
                    
                    if data.get('holders', 0) > 0:
                        holders.append(data['holders'])
                        print(f"    Holders: {data['holders']:,.0f}")
                    
                    if data.get('liquidity', 0) > 0:
                        liquidity_values.append(data['liquidity'])
                        print(f"    Liquidity: ${data['liquidity']:,.0f}")
                    
                    if data.get('price', 0) > 0:
                        prices.append(data['price'])
                        print(f"    Price: ${data['price']:,.2f}")
            
            except Exception as e:
                print(f"    ⚠️  {source_name.title()} error: {e}")
        
        # Calculate averages from real values only (discard zeros)
        result = {}
        
        if market_caps:
            result['market_cap'] = sum(market_caps) / len(market_caps)
            print(f"  ✅ Average Market Cap: ${result['market_cap']:,.0f} (from {len(market_caps)} sources)")
        
        if volumes:
            result['volume_24h'] = sum(volumes) / len(volumes)
            print(f"  ✅ Average Volume: ${result['volume_24h']:,.0f} (from {len(volumes)} sources)")
        
        if holders:
            result['holders'] = sum(holders) / len(holders)
            print(f"  ✅ Average Holders: {result['holders']:,.0f} (from {len(holders)} sources)")
        
        if liquidity_values:
            result['liquidity'] = sum(liquidity_values) / len(liquidity_values)
            print(f"  ✅ Average Liquidity: ${result['liquidity']:,.0f} (from {len(liquidity_values)} sources)")
        
        if prices:
            result['price'] = sum(prices) / len(prices)
            print(f"  ✅ Average Price: ${result['price']:,.2f} (from {len(prices)} sources)")
        
        return result
    
    def update_csv_with_comprehensive_data(self):
        """Update CSV with comprehensive data from all sources"""
        print("\n🔧 Comprehensive Data Update")
        print("=" * 50)
        
        # Load current CSV
        csv_file = '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv'
        df = pd.read_csv(csv_file)
        
        # Token address mappings
        token_addresses = {
            'AAVE': '0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9',
            'CHZ': '0x3506424f91fd33084466f402d5d97f05f8e3b4af',
            'COMP': '0xc00e94cb662c3520282e6f5717214004a7f26888',
            'USDC': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'USDT': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'WBTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
            'LINK': '0x514910771af9ca656af840dff83e8264ecf986ca',
            '1INCH': '0x111111111117dc0aa78b770fa6a738034120c302',
            'POL': '0x455e53CBB86018Ac2B8092FdCd39d8444aFFC3F6',
            'UNI': '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984',
            'DAI': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'GRT': '0xc944e90c64b2c07662a292be6244bdf05cda44a7',
            'MKR': '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2',
            'SUSHI': '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2',
            'QNT': '0x4a220e6096b25eadb88358cb44068a3248254675',
            'GALA': '0x15D4c048F83bd7e37d49eA4C83a07267Ec4203dA',
            'MANA': '0x0f5d2fb29fb7d3cfee444a200298f468908cc942',
            'SAND': '0x3845badAde8e6dFF049820680d1F14bD3903a5d0',
            'BAT': '0x0d8775f648430679a709e98d2b0cb6250d2887ef',
            'OP': '0x4200000000000000000000000000000000000042',
            'TRX': '0xf230b790e05390fc8295f4d3f60332c93bed42e2',
            'S': '0x00000000000000000000000000000000000SONIC'
        }
        
        updated_count = 0
        
        for index, row in df.iterrows():
            symbol = row.get('Symbol', '')
            token_name = row.get('Token', '')
            
            # Ensure symbol is a string and not None
            if not symbol or not isinstance(symbol, str):
                print(f"  ⚠️  Invalid symbol for row {index}: {symbol}")
                continue
                
            address = token_addresses.get(symbol)
            
            if address:
                # Get comprehensive data for this token
                comprehensive_data = self.get_comprehensive_data(symbol, token_name, address)
                
                if comprehensive_data:
                    # Update the DataFrame with comprehensive data
                    if 'market_cap' in comprehensive_data:
                        df.at[index, 'Market Cap'] = f"${comprehensive_data['market_cap']:,.2f}"
                    
                    if 'volume_24h' in comprehensive_data:
                        df.at[index, 'Volume 24h'] = f"${comprehensive_data['volume_24h']:,.2f}"
                    
                    if 'holders' in comprehensive_data:
                        df.at[index, 'Holders'] = f"{comprehensive_data['holders']:,.0f}"
                    
                    if 'liquidity' in comprehensive_data:
                        df.at[index, 'Liquidity'] = f"${comprehensive_data['liquidity']:,.0f}"
                    
                    if 'price' in comprehensive_data:
                        df.at[index, 'Price'] = f"${comprehensive_data['price']:,.2f}"
                    
                    updated_count += 1
                else:
                    print(f"  ❌ No comprehensive data found for {symbol}")
            else:
                print(f"  ⚠️  No address mapping for {symbol}")
        
        # Save updated CSV files
        output_files = [
            '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv',
            '/Users/amlfreak/Desktop/venv/data/token_data_viewer_export.csv',
            '/Users/amlfreak/Desktop/venv/data/tokens_enhanced.csv'
        ]
        
        for output_file in output_files:
            try:
                df.to_csv(output_file, index=False)
                print(f"✅ Saved comprehensive data to {output_file}")
            except Exception as e:
                print(f"❌ Failed to save {output_file}: {e}")
        
        print(f"\n📊 Summary:")
        print(f"  Updated {updated_count} tokens with comprehensive data")
        print(f"  Used multiple APIs: CoinGecko, Etherscan, CoinMarketCap, DeFiLlama, Moralis, Alchemy")
        
        return True

def main():
    """Main function to run the comprehensive API system"""
    print("🔧 Comprehensive API System - Multiple Sources")
    print("=" * 60)
    
    # Initialize system
    system = ComprehensiveAPISystem()
    
    # Update CSV with comprehensive data
    success = system.update_csv_with_comprehensive_data()
    
    if success:
        print("\n✅ Comprehensive API system completed!")
    else:
        print("\n❌ Comprehensive API system failed!")

if __name__ == "__main__":
    main()
