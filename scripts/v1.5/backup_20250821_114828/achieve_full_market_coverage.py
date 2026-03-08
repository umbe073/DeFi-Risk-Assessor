#!/usr/bin/env python3
"""
Achieve Full Market Coverage
Enhanced market data extraction to achieve 21/21 token coverage using multiple methods
"""

import os
import sys
import json
import pandas as pd
import requests
import time
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

# Define data directory
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

def get_comprehensive_token_mapping():
    """Comprehensive token symbol to ID mapping for multiple APIs"""
    
    return {
        # CoinGecko IDs
        'coingecko_ids': {
            'POL': 'polygon-ecosystem-token',
            'DAI': 'dai',
            'UNI': 'uniswap',
            'GRT': 'the-graph',
            'MKR': 'maker',
            'QNT': 'quant-network',
            'MANA': 'decentraland',
            'SAND': 'the-sandbox',
            'BAT': 'basic-attention-token',
            'S': 'sonic-protocol',  # May need verification
            'OP': 'optimism',
            'TRX': 'tron',
            # Already successful tokens
            'USDC': 'usd-coin',
            'USDT': 'tether',
            'AAVE': 'aave',
            'COMP': 'compound-governance-token',
            'CHZ': 'chiliz',
            'WBTC': 'wrapped-bitcoin',
            '1INCH': '1inch',
            'SUSHI': 'sushi',
            'GALA': 'gala'
        },
        # CoinMarketCap IDs  
        'cmc_ids': {
            'POL': '26476',
            'DAI': '4943',
            'UNI': '7083',
            'GRT': '6719',
            'MKR': '1518',
            'QNT': '3155',
            'MANA': '1966',
            'SAND': '6210',
            'BAT': '1697',
            'S': '26431',  # Sonic
            'OP': '11840',
            'TRX': '1958'
        },
        # Symbol alternatives
        'symbol_alternatives': {
            'S': ['SONIC', 'S'],
            'POL': ['MATIC', 'POL'],
            'OP': ['OPTIMISM', 'OP']
        }
    }

def fetch_coingecko_by_id(token_id, symbol):
    """Fetch CoinGecko data using token ID instead of contract address"""
    
    try:
        print(f"    🦎 Fetching CoinGecko data for {symbol} (ID: {token_id})...")
        
        url = f"https://api.coingecko.com/api/v3/coins/{token_id}"
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'DeFiRiskAssessment/2.0'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            market_data = data.get('market_data', {})
            
            if market_data:
                market_cap = market_data.get('market_cap', {}).get('usd', 0)
                volume_24h = market_data.get('total_volume', {}).get('usd', 0)
                current_price = market_data.get('current_price', {}).get('usd', 0)
                
                print(f"      ✅ CoinGecko ID success: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}")
                
                return {
                    'market_cap': market_cap,
                    'volume_24h': volume_24h,
                    'current_price': current_price,
                    'source': 'CoinGecko-ID'
                }
        
        elif response.status_code == 429:
            print(f"      ⚠️  CoinGecko rate limited")
            return None
        else:
            print(f"      ❌ CoinGecko ID failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"      ❌ CoinGecko ID error: {e}")
        return None

def fetch_coingecko_simple_price(symbols):
    """Fetch multiple tokens using CoinGecko simple price API"""
    
    try:
        print(f"    🦎 Fetching CoinGecko simple prices for {len(symbols)} symbols...")
        
        # Convert symbols to CoinGecko IDs
        token_mapping = get_comprehensive_token_mapping()
        cg_ids = []
        symbol_to_id = {}
        
        for symbol in symbols:
            if symbol in token_mapping['coingecko_ids']:
                cg_id = token_mapping['coingecko_ids'][symbol]
                cg_ids.append(cg_id)
                symbol_to_id[cg_id] = symbol
        
        if not cg_ids:
            return {}
        
        # Use simple price endpoint for multiple tokens
        ids_str = ','.join(cg_ids)
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': ids_str,
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true'
        }
        
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'DeFiRiskAssessment/2.0'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = {}
            
            for cg_id, price_data in data.items():
                if cg_id in symbol_to_id:
                    symbol = symbol_to_id[cg_id]
                    results[symbol] = {
                        'market_cap': price_data.get('usd_market_cap', 0),
                        'volume_24h': price_data.get('usd_24h_vol', 0),
                        'current_price': price_data.get('usd', 0),
                        'source': 'CoinGecko-Simple'
                    }
                    
                    print(f"      ✅ {symbol}: MC=${results[symbol]['market_cap']:,.0f}, Vol=${results[symbol]['volume_24h']:,.0f}")
            
            return results
            
        elif response.status_code == 429:
            print(f"      ⚠️  CoinGecko simple price rate limited")
            return {}
        else:
            print(f"      ❌ CoinGecko simple price failed: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"      ❌ CoinGecko simple price error: {e}")
        return {}

def fetch_coinmarketcap_by_id(cmc_id, symbol):
    """Fetch CoinMarketCap data using CMC ID"""
    
    try:
        cmc_api_key = os.getenv("COINMARKETCAP_API_KEY")
        if not cmc_api_key:
            print(f"      ⚠️  CoinMarketCap API key missing")
            return None
        
        print(f"    📊 Fetching CoinMarketCap data for {symbol} (ID: {cmc_id})...")
        
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {
            'X-CMC_PRO_API_KEY': cmc_api_key,
            'Accept': 'application/json'
        }
        params = {
            'id': cmc_id,
            'convert': 'USD'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status', {}).get('error_code') == 0:
                token_data = data.get('data', {}).get(str(cmc_id), {})
                quote_data = token_data.get('quote', {}).get('USD', {})
                
                if quote_data:
                    market_cap = quote_data.get('market_cap', 0)
                    volume_24h = quote_data.get('volume_24h', 0)
                    price = quote_data.get('price', 0)
                    
                    print(f"      ✅ CoinMarketCap success: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}")
                    
                    return {
                        'market_cap': market_cap,
                        'volume_24h': volume_24h,
                        'current_price': price,
                        'source': 'CoinMarketCap'
                    }
        
        elif response.status_code == 429:
            print(f"      ⚠️  CoinMarketCap rate limited")
            return None
        else:
            print(f"      ❌ CoinMarketCap failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"      ❌ CoinMarketCap error: {e}")
        return None

def fetch_alternative_sources(symbol, token_address):
    """Try alternative data sources for market data"""
    
    results = []
    
    # Method 1: CoinPaprika
    try:
        print(f"    🪙 Trying CoinPaprika for {symbol}...")
        
        # First get coin ID from symbol
        search_url = f"https://api.coinpaprika.com/v1/search"
        params = {'q': symbol, 'c': 'coins', 'limit': 1}
        
        response = requests.get(search_url, params=params, timeout=20)
        
        if response.status_code == 200:
            search_data = response.json()
            if search_data.get('coins') and len(search_data['coins']) > 0:
                coin_id = search_data['coins'][0]['id']
                
                # Get market data
                ticker_url = f"https://api.coinpaprika.com/v1/tickers/{coin_id}"
                ticker_response = requests.get(ticker_url, timeout=20)
                
                if ticker_response.status_code == 200:
                    ticker_data = ticker_response.json()
                    quotes = ticker_data.get('quotes', {}).get('USD', {})
                    
                    if quotes:
                        market_cap = quotes.get('market_cap', 0)
                        volume_24h = quotes.get('volume_24h', 0)
                        price = quotes.get('price', 0)
                        
                        if market_cap > 0:
                            print(f"      ✅ CoinPaprika success: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}")
                            results.append({
                                'market_cap': market_cap,
                                'volume_24h': volume_24h,
                                'current_price': price,
                                'source': 'CoinPaprika'
                            })
    
    except Exception as e:
        print(f"      ❌ CoinPaprika error: {e}")
    
    # Method 2: CryptoCompare
    try:
        print(f"    💎 Trying CryptoCompare for {symbol}...")
        
        url = "https://min-api.cryptocompare.com/data/pricemultifull"
        params = {
            'fsyms': symbol,
            'tsyms': 'USD'
        }
        
        response = requests.get(url, params=params, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('Response') == 'Success':
                display_data = data.get('DISPLAY', {}).get(symbol, {}).get('USD', {})
                raw_data = data.get('RAW', {}).get(symbol, {}).get('USD', {})
                
                if raw_data:
                    market_cap = raw_data.get('MKTCAP', 0)
                    volume_24h = raw_data.get('VOLUME24HOUR', 0)
                    price = raw_data.get('PRICE', 0)
                    
                    if market_cap > 0:
                        print(f"      ✅ CryptoCompare success: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}")
                        results.append({
                            'market_cap': market_cap,
                            'volume_24h': volume_24h,
                            'current_price': price,
                            'source': 'CryptoCompare'
                        })
    
    except Exception as e:
        print(f"      ❌ CryptoCompare error: {e}")
    
    return results

def achieve_full_market_coverage():
    """Main function to achieve 21/21 market data coverage"""
    
    print("🎯 ACHIEVING FULL MARKET DATA COVERAGE (21/21)")
    print("=" * 60)
    
    # Load current data
    excel_file = os.path.join(DATA_DIR, 'DeFi Tokens Risk Assessment Results.xlsx')
    df = pd.read_excel(excel_file)
    
    # Get tokens missing market data
    missing_tokens = df[df['Market Cap'] == 0].copy()
    
    print(f"📊 Need to add market data for {len(missing_tokens)} tokens")
    print()
    
    # Get token mapping
    token_mapping = get_comprehensive_token_mapping()
    
    # Strategy 1: Try CoinGecko simple price API for multiple tokens at once
    print("🔄 Strategy 1: CoinGecko Simple Price API")
    missing_symbols = missing_tokens['Symbol'].tolist()
    
    # Add delay to respect rate limits
    time.sleep(2)
    
    simple_price_results = fetch_coingecko_simple_price(missing_symbols)
    
    # Apply results from simple price API
    for idx, token in missing_tokens.iterrows():
        symbol = token['Symbol']
        if symbol in simple_price_results:
            result = simple_price_results[symbol]
            df.at[idx, 'Market Cap'] = result['market_cap']
            df.at[idx, 'Volume 24h'] = result['volume_24h']
            print(f"  ✅ Updated {symbol} from {result['source']}")
    
    # Update missing tokens list
    missing_tokens = df[df['Market Cap'] == 0].copy()
    print(f"📊 Remaining tokens needing data: {len(missing_tokens)}")
    print()
    
    # Strategy 2: Individual CoinGecko ID lookups
    if len(missing_tokens) > 0:
        print("🔄 Strategy 2: Individual CoinGecko ID Lookups")
        
        for idx, token in missing_tokens.iterrows():
            symbol = token['Symbol']
            
            if symbol in token_mapping['coingecko_ids']:
                cg_id = token_mapping['coingecko_ids'][symbol]
                
                # Add delay between requests
                time.sleep(3)
                
                result = fetch_coingecko_by_id(cg_id, symbol)
                
                if result and result['market_cap'] > 0:
                    df.at[idx, 'Market Cap'] = result['market_cap']
                    df.at[idx, 'Volume 24h'] = result['volume_24h']
                    print(f"  ✅ Updated {symbol} from {result['source']}")
        
        # Update missing tokens list
        missing_tokens = df[df['Market Cap'] == 0].copy()
        print(f"📊 Remaining tokens needing data: {len(missing_tokens)}")
        print()
    
    # Strategy 3: CoinMarketCap as backup
    if len(missing_tokens) > 0:
        print("🔄 Strategy 3: CoinMarketCap Backup")
        
        for idx, token in missing_tokens.iterrows():
            symbol = token['Symbol']
            
            if symbol in token_mapping['cmc_ids']:
                cmc_id = token_mapping['cmc_ids'][symbol]
                
                # Add delay between requests
                time.sleep(2)
                
                result = fetch_coinmarketcap_by_id(cmc_id, symbol)
                
                if result and result['market_cap'] > 0:
                    df.at[idx, 'Market Cap'] = result['market_cap']
                    df.at[idx, 'Volume 24h'] = result['volume_24h']
                    print(f"  ✅ Updated {symbol} from {result['source']}")
        
        # Update missing tokens list
        missing_tokens = df[df['Market Cap'] == 0].copy()
        print(f"📊 Remaining tokens needing data: {len(missing_tokens)}")
        print()
    
    # Strategy 4: Alternative sources for remaining tokens
    if len(missing_tokens) > 0:
        print("🔄 Strategy 4: Alternative Sources")
        
        for idx, token in missing_tokens.iterrows():
            symbol = token['Symbol']
            address = token['Token Address']
            
            # Add delay between requests
            time.sleep(2)
            
            alt_results = fetch_alternative_sources(symbol, address)
            
            if alt_results:
                # Use the first successful result
                result = alt_results[0]
                df.at[idx, 'Market Cap'] = result['market_cap']
                df.at[idx, 'Volume 24h'] = result['volume_24h']
                print(f"  ✅ Updated {symbol} from {result['source']}")
    
    # Save results
    backup_file = excel_file.replace('.xlsx', f'_backup_full_coverage_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    df.to_excel(backup_file, index=False)
    df.to_excel(excel_file, index=False)
    
    # Final verification
    final_coverage = (df['Market Cap'] > 0).sum()
    
    print()
    print("🎉 FULL COVERAGE ACHIEVEMENT RESULTS")
    print("=" * 60)
    print(f"📊 Final Market Cap Coverage: {final_coverage}/21 tokens")
    print(f"📈 Improvement: {final_coverage - 9} additional tokens")
    
    if final_coverage == 21:
        print("✅ SUCCESS: 100% market data coverage achieved!")
    else:
        remaining = df[df['Market Cap'] == 0]
        print(f"⚠️  Still missing data for {len(remaining)} tokens:")
        for _, token in remaining.iterrows():
            print(f"   - {token['Symbol']}: {token['Token Name']}")
    
    # Show summary of sources used
    print()
    print("📋 Data Sources Summary:")
    tokens_with_data = df[df['Market Cap'] > 0]
    for _, token in tokens_with_data.iterrows():
        mc = int(token['Market Cap'])
        print(f"  {token['Symbol']}: ${mc:,}")
    
    return final_coverage == 21

def main():
    """Main function"""
    
    success = achieve_full_market_coverage()
    
    if success:
        print("\n🎉 Mission Accomplished: 21/21 market data coverage achieved!")
    else:
        print("\n⚠️  Partial success: Significant improvement but not 100% coverage yet")
    
    return success

if __name__ == "__main__":
    exit(0 if main() else 1)
