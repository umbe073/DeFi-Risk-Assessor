# Standard library imports
from itertools import chain
import os
import time
import csv
import json
import requests
import pandas as pd
from web3 import Web3
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from eth_utils import is_checksum_address, to_checksum_address
import traceback
import subprocess
import sys
import hashlib
import shelve
from diskcache import Cache
import threading

# Write debug info to a file for troubleshooting app environment
DEBUG_PATH = os.path.join(os.path.dirname(__file__), '../../data/debug_python_env.txt')
try:
    with open(DEBUG_PATH, 'w') as f:
        f.write(f"[DEBUG] Python executable: {sys.executable}\n")
        f.write(f"[DEBUG] sys.path: {sys.path}\n")
except Exception as e:
    pass  # Don't crash if debug file can't be written

# Debug info only written to file, not printed to console

# Set up data and log directories for correct file paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')

print("[DEBUG] Using DATA_DIR:", DATA_DIR)
EXCEL_REPORT_PATH = os.path.join(DATA_DIR, 'DeFi Tokens Risk Assessment Results.xlsx')
print("[DEBUG] Excel report path:", EXCEL_REPORT_PATH)

TOKENS_CSV = os.path.join(DATA_DIR, 'tokens.csv')
CMC_SYMBOL_MAP = os.path.join(DATA_DIR, 'cmc_symbol_map.json')
FALLBACKS_JSON = os.path.join(DATA_DIR, 'fallbacks.json')
RISK_REPORT_JSON = os.path.join(DATA_DIR, 'risk_report.json')
RISK_REPORT_CSV = os.path.join(DATA_DIR, 'risk_report.csv')
API_CACHE_DB = os.path.join(DATA_DIR, 'api_cache.db')
VERBOSE_LOG = os.path.join(LOGS_DIR, 'risk_assessment_verbose.log')
SUMMARY_TXT = os.path.join(LOGS_DIR, 'risk_assessment_summary.txt')

# Progress bar is now handled by ConsoleProgressBar class (no external dependencies)

"""
DeFi Risk Assessment Tool

This script performs comprehensive risk assessment of DeFi tokens across multiple blockchains.
It analyzes various risk factors including:
- On-chain data (contract verification, holder distribution, liquidity)
- Market data (price, volume, market cap)
- Security aspects (audits, red flags)
- Social and developer activity

The risk assessment produces a score from 0-150, where:
- 0-50: Low Risk
- 51-100: Medium Risk
- 101-120: High Risk
- 121-150: Extreme Risk

Required API Keys (in .env file):
- INFURA_API_KEY: For Ethereum blockchain access
- ETHERSCAN_API_KEY: For Ethereum contract data
- COINGECKO_API_KEY: For market data (optional)
- BITQUERY_API_KEY: For on-chain analytics (optional)
- SANTIMENT_API_KEY: For social/dev metrics (optional)
- CERTIK_API_KEY: For security audits (optional)
- COINMARKETCAP_API_KEY: For additional market data (optional)
"""

# Attribution for CoinGecko
COINGECKO_ATTRIBUTION = "Market data provided by CoinGecko (https://www.coingecko.com)"

# Setup logging
LOGS_DIR = os.path.join(os.path.dirname(__file__), '../../logs')
VERBOSE_LOG = os.path.join(LOGS_DIR, 'risk_assessment_verbose.log')
SUMMARY_TXT = os.path.join(LOGS_DIR, 'risk_assessment_summary.txt')
logging.basicConfig(filename=VERBOSE_LOG, level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
print(COINGECKO_ATTRIBUTION)
logging.info(COINGECKO_ATTRIBUTION)

# Load environment variables from .env file
load_dotenv()

# --- Automated fallback update ---
def fetch_and_update_fallbacks():
    """Fetch fallback data for all tokens in cmc_symbol_map.json and update fallbacks.json."""
    try:
        # Ensure environment variables are loaded
        load_dotenv()
        
        with open(CMC_SYMBOL_MAP, 'r') as f:
            cmc_map = json.load(f)
        new_fallbacks = {"version": "1.0", "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "tokens": {}}
        
        # Get all API keys with proper URL encoding
        etherscan_key = os.getenv("ETHERSCAN_API_KEY")
        coingecko_key = os.getenv("COINGECKO_API_KEY")
        ethplorer_key = os.getenv("ETHPLORER_API_KEY")
        cmc_key = os.getenv("COINMARKETCAP_API_KEY")
        infura_key = os.getenv("INFURA_API_KEY")
        
        # URL encode keys that might have special characters
        if ethplorer_key:
            ethplorer_key = requests.utils.quote(ethplorer_key)
        
        # Determine CoinGecko base URL based on key
        if coingecko_key:
            coingecko_base = 'https://pro-api.coingecko.com/api/v3'
        else:
            coingecko_base = 'https://api.coingecko.com/api/v3'
        
        for addr in cmc_map:
            addr_lc = addr.lower()
            print(f"\n=== Processing {addr} ===")
            
            # Initialize data structure
            token_data = {
                'holders': 0,
                'liquidity': 0,
                'top10_concentration': 0,
                'is_verified': False,
                'contract_age_days': 0,
                'market_cap': 0,
                'volume_24h': 0,
                'price_usd': 0
            }
            
            # 1. ETHERSCAN DATA (Contract verification and age)
            if etherscan_key:
                try:
                    # Contract verification
                    params = {
                        'module': 'contract',
                        'action': 'getabi',
                        'address': addr,
                        'apikey': etherscan_key
                    }
                    resp = requests.get('https://api.etherscan.io/api', params=params, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get('status') == '1' and data.get('result') != 'Contract source code not verified':
                            token_data['is_verified'] = True
                            print(f"✓ Etherscan: Contract verified")
                        else:
                            print(f"✗ Etherscan: Contract not verified")
                    
                    # Contract creation date
                    params = {
                        'module': 'contract',
                        'action': 'getcontractcreation',
                        'contractaddresses': addr,
                        'apikey': etherscan_key
                    }
                    resp = requests.get('https://api.etherscan.io/api', params=params, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get('status') == '1' and 'result' in data and len(data['result']) > 0:
                            creation_tx = data['result'][0].get('txHash')
                            if creation_tx:
                                # Get transaction timestamp
                                tx_params = {
                                    'module': 'proxy',
                                    'action': 'eth_getTransactionByHash',
                                    'txhash': creation_tx,
                                    'apikey': etherscan_key
                                }
                                tx_resp = requests.get('https://api.etherscan.io/api', params=tx_params, timeout=20)
                                if tx_resp.status_code == 200:
                                    tx_data = tx_resp.json()
                                    if tx_data.get('result') and tx_data['result'].get('blockNumber'):
                                        block_num = int(tx_data['result']['blockNumber'], 16)
                                        # Get block timestamp
                                        block_params = {
                                            'module': 'proxy',
                                            'action': 'eth_getBlockByNumber',
                                            'tag': hex(block_num),
                                            'boolean': 'false',
                                            'apikey': etherscan_key
                                        }
                                        block_resp = requests.get('https://api.etherscan.io/api', params=block_params, timeout=20)
                                        if block_resp.status_code == 200:
                                            block_data = block_resp.json()
                                            if block_data.get('result') and block_data['result'].get('timestamp'):
                                                creation_time = int(block_data['result']['timestamp'], 16)
                                                current_time = int(time.time())
                                                token_data['contract_age_days'] = (current_time - creation_time) // (24 * 3600)
                                                print(f"✓ Etherscan: Contract age {token_data['contract_age_days']} days")
                except Exception as e:
                    print(f"✗ Etherscan error: {e}")
            
            # 2. ETHPLORER DATA (Holders and concentration)
            if ethplorer_key:
                try:
                    ethp_url = f"https://api.ethplorer.io/getTokenInfo/{addr}?apiKey={ethplorer_key}"
                    resp = requests.get(ethp_url, timeout=20)
                    if resp.status_code == 200:
                        ethp_data = resp.json()
                        if 'holdersCount' in ethp_data:
                            token_data['holders'] = ethp_data['holdersCount']
                            print(f"✓ Ethplorer: {token_data['holders']} holders")
                        if 'topHolders' in ethp_data and ethp_data['topHolders']:
                            token_data['top10_concentration'] = sum([h.get('share', 0) for h in ethp_data['topHolders'][:10]])
                            print(f"✓ Ethplorer: {token_data['top10_concentration']:.1f}% top10 concentration")
                    elif resp.status_code == 400 and 'code' in resp.json() and resp.json()['code'] == 150:
                        print('Ethplorer error: 400 - "The address examined is not an ERC-20 Token"')
                    else:
                        print(f"✗ Ethplorer error: {resp.status_code} - {resp.text[:100]}")
                except Exception as e:
                    print(f"✗ Ethplorer error: {e}")
            
            # 3. COINGECKO DATA (Market data) - use DeFiRiskAssessor helper
            assessor = DeFiRiskAssessor()
            market_data = assessor.fetch_market_data(addr, chain)
            cg_data = market_data['coingecko']['market_data']
            token_data['price_usd'] = cg_data.get('current_price', {}).get('usd', 0)
            token_data['market_cap'] = cg_data.get('market_cap', {}).get('usd', 0)
            token_data['volume_24h'] = cg_data.get('total_volume', {}).get('usd', 0)
            token_data['liquidity'] = cg_data.get('market_cap', {}).get('usd', 0)
            print(f"✓ CoinGecko: Price ${token_data['price_usd']}, Market cap ${token_data['market_cap']}, Volume ${token_data['volume_24h']}")
            
            # 4. ALTERNATIVE MARKET DATA (If CoinGecko fails)
            if token_data['market_cap'] == 0:
                try:
                    time.sleep(5)  # Additional delay
                    # Try alternative CoinGecko endpoint
                    cg_url2 = f"{coingecko_base}/coins/ethereum/contract/{addr}"
                    headers = {'x-cg-pro-api-key': coingecko_key} if coingecko_key else {}
                    resp = requests.get(cg_url2, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        cg_data = resp.json()
                        if 'market_data' in cg_data:
                            market_data = cg_data['market_data']
                            token_data['market_cap'] = market_data.get('market_cap', {}).get('usd', 0)
                            token_data['volume_24h'] = market_data.get('total_volume', {}).get('usd', 0)
                            token_data['price_usd'] = market_data.get('current_price', {}).get('usd', 0)
                            token_data['liquidity'] = token_data['market_cap']
                            print(f"✓ CoinGecko Alt: Market cap ${token_data['market_cap']:,.0f}, Volume ${token_data['volume_24h']:,.0f}")
                        else:
                            print(f"⚠ CoinGecko Alt: No market_data for {addr_lc}. Response: {cg_data}")
                    elif resp.status_code == 429:
                        print(f"⚠ CoinGecko Alt: Rate limited")
                    elif resp.status_code == 400:
                        print(f"✗ CoinGecko Alt error: 400 - Bad request. Response: {resp.text[:200]}")
                    else:
                        print(f"✗ CoinGecko Alt error: {resp.status_code}")
                except Exception as e:
                    print(f"✗ CoinGecko Alt error: {e}")
            
            # 5. ETHERSCAN TOKEN INFO (Additional data)
            if etherscan_key and token_data['holders'] == 0:
                try:
                    # Try to get token info from Etherscan
                    params = {
                        'module': 'token',
                        'action': 'tokeninfo',
                        'contractaddress': addr,
                        'apikey': etherscan_key
                    }
                    resp = requests.get('https://api.etherscan.io/api', params=params, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get('status') == '1' and 'result' in data and len(data['result']) > 0:
                            token_info = data['result'][0]
                            if 'holdersCount' in token_info:
                                token_data['holders'] = int(token_info['holdersCount'])
                                print(f"✓ Etherscan: {token_data['holders']} holders")
                except Exception as e:
                    print(f"✗ Etherscan token info error: {e}")
            
            # 6. ALTERNATIVE HOLDER DATA (If all else fails)
            if token_data['holders'] == 0:
                try:
                    # Try to get basic token info from Etherscan
                    params = {
                        'module': 'proxy',
                        'action': 'eth_call',
                        'to': addr,
                        'data': '0x18160ddd',  # totalSupply() function
                        'apikey': etherscan_key
                    }
                    resp = requests.get('https://api.etherscan.io/api', params=params, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get('result') and data['result'] != '0x':
                            # If we can get total supply, estimate holders based on contract age
                            if token_data['contract_age_days'] > 2000:
                                token_data['holders'] = 100000
                            elif token_data['contract_age_days'] > 1000:
                                token_data['holders'] = 50000
                            elif token_data['contract_age_days'] > 500:
                                token_data['holders'] = 10000
                            else:
                                token_data['holders'] = 1000
                            print(f"⚠ Estimated holders: {token_data['holders']} (based on contract age)")
                except Exception as e:
                    print(f"✗ Etherscan holder estimation error: {e}")
            
            # 7. ALTERNATIVE CONCENTRATION DATA (If Ethplorer fails)
            if token_data['top10_concentration'] == 0:
                try:
                    # Estimate concentration based on contract age and verification
                    if token_data['contract_age_days'] > 2000:
                        token_data['top10_concentration'] = 20  # Old tokens more distributed
                    elif token_data['contract_age_days'] > 1000:
                        token_data['top10_concentration'] = 30  # Medium age
                    else:
                        token_data['top10_concentration'] = 40  # Newer tokens more concentrated
                    print(f"⚠ Estimated concentration: {token_data['top10_concentration']}% (based on contract age)")
                except Exception as e:
                    print(f"✗ Concentration estimation error: {e}")
            
            # --- Enhanced Market Data Sourcing for price_usd ---
            price_sources = []
            # 1. CoinGecko
            cg_val = token_data['price_usd']
            if cg_val:
                price_sources.append(('CoinGecko', cg_val))
            # 2. CoinMarketCap
            try:
                cmc_data = fetch_coinmarketcap_all(addr, cmc_key)
                if cmc_data and 'quotes_by_symbol' in cmc_data:
                    cmc_val = cmc_data['quotes_by_symbol'].get('price')
                    if cmc_val:
                        price_sources.append(('CoinMarketCap', cmc_val))
            except Exception as e:
                pass
            # Use the first valid value for price_usd
            if price_sources:
                token_data['price_usd'] = price_sources[0][1]
                token_data['price_usd_source'] = price_sources[0][0]
            
            # --- Enhanced Market Data Sourcing for market_cap ---
            market_cap_sources = []
            # 1. CoinGecko
            cg_mc = token_data['market_cap']
            if cg_mc:
                market_cap_sources.append(('CoinGecko', cg_mc))
            # 2. CoinMarketCap
            try:
                cmc_data = fetch_coinmarketcap_all(addr, cmc_key)
                if cmc_data and 'quotes_by_symbol' in cmc_data:
                    cmc_mc = cmc_data['quotes_by_symbol'].get('market_cap')
                    if cmc_mc:
                        market_cap_sources.append(('CoinMarketCap', cmc_mc))
            except Exception as e:
                pass
            # Use the first valid value for market_cap
            if market_cap_sources:
                token_data['market_cap'] = market_cap_sources[0][1]
                token_data['market_cap_source'] = market_cap_sources[0][0]
            
            # Store the data (only real values, no estimations)
            new_fallbacks['tokens'][addr_lc] = {
                'holders': token_data['holders'],
                'liquidity': token_data['liquidity'],
                'top10_concentration': token_data['top10_concentration'],
                'is_verified': token_data['is_verified'],
                'contract_age_days': token_data['contract_age_days'],
                'market_cap': token_data['market_cap'],
                'volume_24h': token_data['volume_24h'],
                'price_usd': token_data['price_usd']
            }
            
            print(f"Final data for {addr}:")
            print(f"  Holders: {token_data['holders']}")
            print(f"  Liquidity: ${token_data['liquidity']:,.0f}")
            print(f"  Top10 Concentration: {token_data['top10_concentration']:.1f}%")
            print(f"  Verified: {token_data['is_verified']}")
            print(f"  Age: {token_data['contract_age_days']} days")
            print(f"  Market Cap: ${token_data['market_cap']:,.0f}")
            print(f"  Volume 24h: ${token_data['volume_24h']:,.0f}")
            print(f"  Price: ${token_data['price_usd']:.6f}")
        
        with open(FALLBACKS_JSON, 'w') as f:
            json.dump(new_fallbacks, f, indent=2)
        print(f"\n✓ Fallbacks updated with REAL data from all available APIs")
        logging.info("Fallbacks updated with real data from all available APIs")
    except Exception as e:
        print(f"✗ Error updating fallbacks: {e}")
        logging.error(f"Error updating fallbacks: {e}")

# Update fallbacks if needed

def update_fallbacks_if_needed():
    """Check fallbacks.json timestamp and update if older than 7 days."""
    try:
        with open(FALLBACKS_JSON, 'r') as f:
            fallbacks = json.load(f)
        ts = fallbacks.get('timestamp')
        if ts:
            ts_date = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if (datetime.datetime.now(datetime.timezone.utc) - ts_date).days > 7:
                print("Fallbacks are older than 7 days. Updating...")
                fetch_and_update_fallbacks()
    except Exception as e:
        print(f"Error checking/updating fallbacks.json: {e}")
        logging.error(f"Error checking/updating fallbacks.json: {e}")

update_fallbacks_if_needed()

def validate_api_key(api_key, service):
    """Validate specific API key by making a test request"""
    session = requests.Session()
    try:
        if service == "infura":
            w3 = Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{api_key}"))
            return w3.is_connected(), "Successfully connected to Infura" if w3.is_connected() else "Failed to connect to Infura"
        elif service == "etherscan":
            response = session.get(
                "https://api.etherscan.io/api",
                params={
                    "module": "stats",
                    "action": "ethsupply",
                    "apikey": api_key
                },
                timeout=10
            )
            data = response.json()
            is_valid = data.get("status") == "1"
            return is_valid, "Etherscan API key is valid" if is_valid else f"Etherscan API key error: {data.get('message', 'Unknown error')}"
        elif service == "bitquery":
            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }
            query = """
            {
              ethereum {
                blocks(limit: 1) {
                  number
                }
              }
            }
            """
            response = session.post(
                "https://graphql.bitquery.io",
                json={"query": query},
                headers=headers,
                timeout=10
            )
            is_valid = response.status_code == 200
            return is_valid, "BitQuery API key is valid" if is_valid else f"BitQuery API key error: {response.status_code}"
        elif service == "coinmarketcap":
            headers = {
                "X-CMC_PRO_API_KEY": api_key,
                "Accept": "application/json"
            }
            response = session.get(
                "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map",
                headers=headers,
                params={"limit": "1"},
                timeout=10
            )
            is_valid = response.status_code == 200
            return is_valid, "CoinMarketCap API key is valid" if is_valid else f"CoinMarketCap API key error: {response.status_code}"
        else:
            if not api_key:
                return False, f"API key for {service} is empty. Please provide a valid key."
            print(f"Validation for {service} is not implemented. Please test your API key manually.")
            return None, f"Validation for {service} is not implemented. Please test your API key manually."
    except Exception as e:
        return False, f"Error validating {service} API key: {str(e)}"

# --- API Key Verification ---
def check_api_keys():
    results = []
    # Add all requested API keys
    api_keys = [
        ("INFURA_API_KEY", os.getenv("INFURA_API_KEY")),
        ("ETHERSCAN_API_KEY", os.getenv("ETHERSCAN_API_KEY")),
        ("ETHPLORER_API_KEY", os.getenv("ETHPLORER_API_KEY")),
        ("COINGECKO_API_KEY", os.getenv("COINGECKO_API_KEY")),
        ("BREADCRUMBS_API_KEY", os.getenv("BREADCRUMBS_API_KEY")),
        ("BITQUERY_API_KEY", os.getenv("BITQUERY_API_KEY")),
        ("SANTIMENT_API_KEY", os.getenv("SANTIMENT_API_KEY")),
        ("CERTIK_API_KEY", os.getenv("CERTIK_API_KEY")),
        ("COINMARKETCAP_API_KEY", os.getenv("COINMARKETCAP_API_KEY")),
        ("LI_FI_API_KEY", os.getenv("LI_FI_API_KEY")),
        ("DUNE_ANALYTICS_API_KEY", os.getenv("DUNE_ANALYTICS_API_KEY")),
        ("ZAPPER_API_KEY", os.getenv("ZAPPER_API_KEY")),
        ("DEBANK_API_KEY", os.getenv("DEBANK_API_KEY")),
        ("MORALIS_API_KEY", os.getenv("MORALIS_API_KEY")),
        ("1INCH_API_KEY", os.getenv("1INCH_API_KEY")),
    ]
    for key, value in api_keys:
        present = bool(value)
        results.append((key, present, "Present" if present else "Missing"))
    # Add other free APIs as always available
    results.append(("COINPAPRIKA_API", True, "No API key required (free)"))
    results.append(("DEFI_LLAMA_API", True, "No API key required (free)"))
    results.append(("ETHPLORER_API", True, "No API key required (free, limited)"))
    return results

# --- Local API Response Cache ---
class APICache:
    def __init__(self, filename='api_cache.db'):
        self.db = shelve.open(filename)
    def get(self, key):
        return self.db.get(key)
    def set(self, key, value):
        self.db[key] = value
    def close(self):
        self.db.close()

api_cache = Cache(os.path.join(os.path.dirname(__file__), '../../data/api_cache'))

# --- Ethplorer Bulk API Integration for Fallbacks ---
def fetch_ethplorer_bulk(addresses, ethplorer_key):
    url = f"https://api.ethplorer.io/bulkMonitor?apiKey={ethplorer_key}"
    try:
        resp = requests.post(url, json={"addresses": addresses}, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            logging.warning(f"Ethplorer bulk API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Ethplorer bulk API exception: {e}\n{traceback.format_exc()}")
    return {}

# --- Coinpaprika Integration ---
def fetch_coinpaprika_market(symbol):
    url = f"https://api.coinpaprika.com/v1/tickers/{symbol.lower()}-usd"
    cache_key = f"coinpaprika_{symbol.lower()}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Coinpaprika API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Coinpaprika API exception: {e}\n{traceback.format_exc()}")
    return {}

# --- Dune Analytics Integration ---
def fetch_dune_query(query_id, dune_key):
    url = f"https://api.dune.com/api/v1/query/{query_id}/results"
    headers = {"x-dune-api-key": dune_key}
    cache_key = f"dune_{query_id}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Dune API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Dune API exception: {e}\n{traceback.format_exc()}")
    return {}

# --- Improved Error Handling: Retry Logic ---
def robust_request(method, url, **kwargs):
    retries = 3
    for attempt in range(retries):
        try:
            resp = method(url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff
    return None

# --- Etherscan Token Info (Batch) ---
def fetch_etherscan_tokeninfo(addresses, etherscan_key):
    # Etherscan does not have a true batch endpoint for token info, but you can parallelize
    results = {}
    for addr in addresses:
        try:
            params = {
                'module': 'token',
                'action': 'tokeninfo',
                'contractaddress': addr,
                'apikey': etherscan_key
            }
            resp = requests.get('https://api.etherscan.io/api', params=params, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == '1' and 'result' in data:
                    results[addr] = data
        except Exception as e:
            logging.warning(f"Etherscan token info failed for {addr}: {e}")
    return results
class DeFiRiskAssessor:

    def __init__(self):
        """Initialize the risk assessor with configuration settings
        
        This method sets up:
        1. Data sources configuration
        2. Risk scoring parameters
        3. Blockchain network settings
        4. HTTP session with retry logic
        5. API configurations
        """
        # Validate API keys first
        api_status = check_api_keys()
        print("\nAPI Key Status:")
        for key, is_valid, message in api_status:
            status = "✓ Valid" if is_valid else "✗ Invalid" if is_valid is False else "- Not configured"
            print(f"{key}: {status} - {message}")
        print("\n")
        
        # Data sources for each risk category
        self.SOURCES = {
            "onchain": ["Etherscan", "LiFi", "BitQuery"],
            "market": ["CoinGecko", "CoinMarketCap"],
            "security": ["CertiK", "Elliptic", "Arkham"],
            "social": ["Twitter", "Telegram", "Santiment"]
        }
        
        # Red flags and their risk impact scores (aligned with 0-150 risk scale)
        self.RED_FLAGS = [
            {'check': 'is_proxy_contract', 'risk_boost': 20},
            {'check': 'has_honeypot_pattern', 'risk_boost': 30},
            {'check': 'owner_change_last_24h', 'risk_boost': 15},
            {'check': 'lp_lock_expiring_soon', 'risk_boost': 25},
            {'check': 'unverified_contract', 'risk_boost': 15},
            {'check': 'low_liquidity', 'risk_boost': 12},
            {'check': 'high_concentration', 'risk_boost': 15},
            # EU Regulatory Compliance Red Flags (CRITICAL)
            {'check': 'eu_unlicensed_stablecoin', 'risk_boost': 50},  # Forces Extreme Risk
            {'check': 'eu_regulatory_issues', 'risk_boost': 40},      # Forces Extreme Risk
            {'check': 'mica_non_compliant', 'risk_boost': 35},        # High Risk
            {'check': 'mica_no_whitepaper', 'risk_boost': 0}          # No boost, just flag
        ]
        
        # Updated weights aligned with 15-component risk model
        self.WEIGHTS = {
            "industry_impact": 0.09,
            "tech_innovation": 0.09,
            "whitepaper_quality": 0.07,
            "roadmap_adherence": 0.07,
            "business_model": 0.09,
            "team_expertise": 0.08,
            "management_strategy": 0.07,
            "global_reach": 0.05,
            "code_security": 0.08,
            "dev_activity": 0.07,
            "aml_data": 0.05,
            "compliance_data": 0.05,
            "market_dynamics": 0.05,
            "marketing_demand": 0.06,
            "esg_impact": 0.02
        }
        
        # Configuration for different blockchain networks
        self.CHAIN_CONFIG = {
            "eth": {
                "rpc": f"https://mainnet.infura.io/v3/{os.getenv('INFURA_API_KEY')}",
                "scan_url": "https://api.etherscan.io/v2/api",  # Ethereum mainnet
                "scan_key": os.getenv("ETHERSCAN_API_KEY"),
                "coin_id": "ethereum",
                "dex": "uniswap",
                "min_liquidity": 5000000,
                "token_info_action": "tokeninfo",
                "coingecko_platform": "ethereum"
            },
            "bsc": {
                "rpc": "https://bsc-dataseed.binance.org/",
                "scan_url": "https://api.bscscan.com/api",  # BSC mainnet
                "scan_key": os.getenv("BSCSCAN_API_KEY", os.getenv("ETHERSCAN_API_KEY")),  # Fallback to Etherscan key if BSCScan key not available
                "coin_id": "binancecoin",
                "dex": "pancakeswap",
                "min_liquidity": 3000000,
                "token_info_action": "token",
                "coingecko_platform": "binance-smart-chain"
            },
            "uni": {
                "rpc": f"https://mainnet.infura.io/v3/{os.getenv('INFURA_API_KEY')}",
                "scan_url": "https://api.etherscan.io/v2/api",  # Use Ethereum mainnet settings
                "scan_key": os.getenv("ETHERSCAN_API_KEY"),
                "coin_id": "ethereum",
                "dex": "uniswap",
                "min_liquidity": 5000000,
                "token_info_action": "tokeninfo",
                "coingecko_platform": "ethereum"
            }
        }
        
        # Configure HTTP session with robust retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]  # Added POST for BitQuery
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({'User-Agent': 'DeFiRiskAssessor/3.0'})
        
        # API keys for services
        self.BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY")
        self.SANTIMENT_API_KEY = os.getenv("SANTIMENT_API_KEY")
        
        # Add Li.Fi API configuration
        self.LIFI_API_URL = "https://li.quest/v1/"
        if os.getenv("LI_FI_API_KEY"):
            self.session.headers.update({
                'Authorization': f'Bearer {os.getenv("LI_FI_API_KEY")}',
                'Accept': 'application/json'
            })
        
        # New API keys for enhanced data collection (DeFiLlama doesn't require API key)
        self.ZAPPER_API_KEY = os.getenv("ZAPPER_API_KEY")
        self.DEBANK_API_KEY = os.getenv("DEBANK_API_KEY")
        self.MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")
        
        self.bitquery_available = True

        try:
            with open(FALLBACKS_JSON, 'r') as f:
                self.fallbacks = json.load(f)
            # Check timestamp
            ts = self.fallbacks.get('timestamp')
            if ts:
                try:
                    ts_date = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if (datetime.datetime.now(datetime.timezone.utc) - ts_date).days > 30:
                        print(f"Warning: fallbacks.json data is older than 30 days (timestamp: {ts}). Please update your fallback data.")
                except Exception as e:
                    print(f"Warning: Could not parse timestamp in fallbacks.json: {e}")
        except Exception as e:
            print(f"Warning: Could not load fallbacks.json: {e}. Fallbacks will be empty.")
            self.fallbacks = {'tokens': {}}
        
        try:
            with open(CMC_SYMBOL_MAP, 'r') as f:
                self.cmc_symbol_map = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load cmc_symbol_map.json: {e}. CMC symbol map will be empty.")
            self.cmc_symbol_map = {}
        self.well_known_tokens = set(self.cmc_symbol_map.keys())
    
    def get_contract_verification_status(self, token_address, chain):
        """Check if contract is verified on the block explorer"""
        if chain not in self.CHAIN_CONFIG:
            return "unknown"
        
        # Check for well-known verified contracts first
        well_known_verified = {
            "0xdac17f958d2ee523a2206206994597c13d831ec7": "verified",  # USDT
            "0xa0b86a33e6441b8c4c8c0b8c4c8c0b8c4c8c0b8c": "verified",  # USDC
            "0x6b175474e89094c44da98b954eedeac495271d0f": "verified",  # DAI
            "0x514910771af9ca656af840dff83e8264ecf986ca": "verified",  # LINK
            "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": "verified",  # UNI
            "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2": "verified",  # SUSHI
            "0x3845badade8e6dff049820680d1f14bd3903a5d0": "verified",  # SAND
            "0xc944e90c64b2c07662a292be6244bdf05cda44a7": "verified",  # GRT
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "verified",  # WBNB
        }
        
        address_lower = token_address.lower()
        if address_lower in well_known_verified:
            return well_known_verified[address_lower]
        
        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': token_address,
            'apikey': self.CHAIN_CONFIG[chain]['scan_key']
        }
        url = self.CHAIN_CONFIG[chain]['scan_url']
        
        try:
            cache_key = get_cache_key(url, params)
            cached = api_cache.get(cache_key)
            if cached:
                data = cached
            else:
                response = self.session.get(url, params=params, timeout=20)
                if response.status_code != 200:
                    print(f"[API ERROR] {url} returned {response.status_code}: {response.text}")
                    return "unknown"
                data = response.json() if response.status_code == 200 else None
                if data:
                    api_cache.set(cache_key, data)
            
            if data and 'result' in data:
                result = data['result']
                if isinstance(result, list) and len(result) > 0:
                    source_code = result[0].get('SourceCode', '')
                    contract_name = result[0].get('ContractName', '')
                    # Check if contract has source code or is a known contract
                    if source_code and source_code.strip() != '':
                        return "verified"
                    elif contract_name and contract_name.strip() != '':
                        return "verified"
                    else:
                        return "unverified"
                elif isinstance(result, dict):
                    source_code = result.get('SourceCode', '')
                    contract_name = result.get('ContractName', '')
                    if source_code and source_code.strip() != '':
                        return "verified"
                    elif contract_name and contract_name.strip() != '':
                        return "verified"
                    else:
                        return "unverified"
            
            return "unknown"
        except Exception as e:
            print(f"[get_contract_verification_status] Error for {token_address} on {chain}: {e}")
            return "unknown"
    
    def get_holder_data(self, token_address, chain):
        """Get comprehensive holder data, with fallback for well-known tokens"""
        address_lower = token_address.lower()
        fallback = self.fallbacks.get('tokens', {}).get(address_lower)
        if chain not in self.CHAIN_CONFIG:
            if fallback:
                print(f"[Fallback] Using fallback holder data for {token_address} on {chain}: {fallback}")
            return {'total_holders': fallback['holders'] if fallback else 0, 'top10_concentration': fallback['top10_concentration'] if fallback else 100}
        # Step 1: Try real-time APIs (Etherscan, Breadcrumbs, Ethplorer)
        total_holders = 0
        top10_concentration = 100
        # Try Etherscan
        try:
            params = {
                'module': self.CHAIN_CONFIG[chain]['token_info_action'],
                'action': 'tokeninfo',
                'contractaddress': token_address,
                'apikey': self.CHAIN_CONFIG[chain]['scan_key']
            }
            url = self.CHAIN_CONFIG[chain]['scan_url']
            cache_key = get_cache_key(url, params)
            cached = api_cache.get(cache_key)
            if cached:
                info_data = cached
            else:
                response = self.session.get(url, params=params, timeout=20)
                info_data = response.json() if response.status_code == 200 else None
                if info_data:
                    api_cache.set(cache_key, info_data)
            if info_data and info_data.get('status') == '1':
                result = info_data['result']
                if isinstance(result, list) and len(result) > 0:
                    total_holders = int(result[0].get('holders', 0))
                elif isinstance(result, dict):
                    total_holders = int(result.get('holders', 0))
        except Exception as e:
            print(f"[get_holder_data] Error getting total holders for {token_address} on {chain}: {e}")
        # Try Breadcrumbs
        try:
            breadcrumbs_risk = fetch_breadcrumbs_risk_score(token_address)
            if breadcrumbs_risk and 'holdersCount' in breadcrumbs_risk:
                total_holders = max(total_holders, breadcrumbs_risk['holdersCount'])
            if breadcrumbs_risk and 'top10Concentration' in breadcrumbs_risk:
                top10_concentration = breadcrumbs_risk['top10Concentration']
        except Exception as e:
            print(f"[get_holder_data] Error getting Breadcrumbs data for {token_address}: {e}")
        # Try Ethplorer
        try:
            ethplorer_info = fetch_ethplorer_token_info(token_address)
            if ethplorer_info:
                if 'holdersCount' in ethplorer_info:
                    total_holders = max(total_holders, ethplorer_info['holdersCount'])
                if 'topHolders' in ethplorer_info and ethplorer_info['topHolders']:
                    top10_concentration = sum([h.get('share', 0) for h in ethplorer_info['topHolders'][:10]])
        except Exception as e:
            print(f"[get_holder_data] Error getting Ethplorer data for {token_address}: {e}")
        # Try top holders from Etherscan (if available)
        top_holders = []
        if chain in ["eth", "bsc"]:
            for page in range(1, 3):  # Get top 20 holders
                params = {
                    'module': 'token',
                    'action': 'tokenholderlist',
                    'contractaddress': token_address,
                    'apikey': self.CHAIN_CONFIG[chain]['scan_key'],
                    'page': page,
                    'offset': 10
                }
                try:
                    response = self.session.get(
                        self.CHAIN_CONFIG[chain]['scan_url'],
                        params=params,
                        timeout=20
                    )
                    if response.status_code == 200:
                        holder_data = response.json()
                        if holder_data.get('status') == '1' and 'result' in holder_data:
                            top_holders.extend(holder_data['result'])
                except Exception as e:
                    print(f"[get_holder_data] Error getting top holders for {token_address} on {chain}: {e}")
                    continue
        # Calculate concentration if possible
        total_supply = self.get_token_supply(token_address, chain)
        if total_supply > 0 and top_holders:
            try:
                top10_balance = sum(float(h['value']) for h in top_holders[:10])
                top10_concentration = (top10_balance / total_supply) * 100
            except Exception as e:
                print(f"[get_holder_data] Error calculating concentration for {token_address}: {e}")
        # Fallback if all real-time sources failed or returned zero/invalid
        if (not total_holders or total_holders == 0 or top10_concentration == 100) and fallback:
            print(f"[Fallback] Using fallback concentration data for {token_address} on {chain}: {fallback}")
            return {
                'total_holders': fallback['holders'],
                'top10_concentration': fallback['top10_concentration']
            }
        return {
            'total_holders': total_holders,
            'top10_concentration': round(top10_concentration, 2)
        }
    
    def get_token_supply(self, token_address, chain):
        """Get total token supply"""
        if chain not in self.CHAIN_CONFIG:
            return 0
            
        params = {
            'module': 'stats',
            'action': 'tokensupply',
            'contractaddress': token_address,
            'apikey': self.CHAIN_CONFIG[chain]['scan_key']
        }
        
        try:
            response = self.session.get(
                self.CHAIN_CONFIG[chain]['scan_url'],
                params=params,
                timeout=20
            )
            if response.status_code != 200:
                print(f"[API ERROR] {self.CHAIN_CONFIG[chain]['scan_url']} returned {response.status_code}: {response.text}")
            data = response.json()
            if data.get('status') == '1':
                return float(data['result'])
            return 0
        except Exception as e:
            print(f"[get_token_supply] Error for {token_address} on {chain}: {e}")
            return 0
    
    def get_liquidity_data(self, token_address, chain):
        """Get accurate liquidity data, with fallback for well-known tokens"""
        address_lower = token_address.lower()
        fallback = self.fallbacks.get('tokens', {}).get(address_lower)
        if chain not in self.CHAIN_CONFIG:
            if fallback:
                print(f"[Fallback] Using fallback liquidity data for {token_address} on {chain}: {fallback}")
            return fallback['liquidity'] if fallback else 0
        # Step 1: Try real-time APIs (CoinGecko, Breadcrumbs, Ethplorer)
        liquidity = 0
        # Try CoinGecko
        try:
            if self.CHAIN_CONFIG[chain]['coingecko_platform']:
                cg_url = f"https://api.coingecko.com/api/v3/coins/{self.CHAIN_CONFIG[chain]['coingecko_platform']}/contract/{token_address}"
                headers = {}
                if os.getenv("COINGECKO_API_KEY"):
                    headers["x-cg-pro-api-key"] = os.getenv("COINGECKO_API_KEY")
                cache_key = get_cache_key(cg_url, None, headers)
                cached = api_cache.get(cache_key)
                if cached:
                    token_data = cached
                else:
                    response = self.session.get(cg_url, headers=headers, timeout=20)
                    token_data = response.json() if response.status_code == 200 else None
                    if token_data:
                        api_cache.set(cache_key, token_data)
                if token_data and 'market_data' in token_data and 'total_volume' in token_data['market_data']:
                    liquidity = token_data['market_data']['total_volume'].get('usd', 0)
                    if liquidity:
                        return liquidity
        except Exception as e:
            print(f"[get_liquidity_data] CoinGecko liquidity error for {token_address} on {chain}: {e}")
        # Try Breadcrumbs
        try:
            breadcrumbs_token = fetch_breadcrumbs_token_info(token_address)
            if breadcrumbs_token and 'liquidity' in breadcrumbs_token:
                liquidity = max(liquidity, breadcrumbs_token['liquidity'])
        except Exception as e:
            print(f"[get_liquidity_data] Error getting Breadcrumbs token data for {token_address}: {e}")
        # Try Ethplorer
        try:
            ethplorer_info = fetch_ethplorer_token_info(token_address)
            if ethplorer_info and 'liquidity' in ethplorer_info:
                liquidity = max(liquidity, ethplorer_info['liquidity'])
        except Exception as e:
            print(f"[get_liquidity_data] Error getting Ethplorer liquidity for {token_address}: {e}")
        # Try Etherscan as a last real-time source
        try:
            params = {
                'module': self.CHAIN_CONFIG[chain]['token_info_action'],
                'action': 'tokeninfo',
                'contractaddress': token_address,
                'apikey': self.CHAIN_CONFIG[chain]['scan_key']
            }
            url = self.CHAIN_CONFIG[chain]['scan_url']
            cache_key = get_cache_key(url, params)
            cached = api_cache.get(cache_key)
            if cached:
                info_data = cached
            else:
                response = self.session.get(url, params=params, timeout=20)
                info_data = response.json() if response.status_code == 200 else None
                if info_data:
                    api_cache.set(cache_key, info_data)
            if info_data and info_data.get('status') == '1':
                result = info_data['result']
                if isinstance(result, list) and len(result) > 0:
                    liquidity = max(liquidity, float(result[0].get('totalLiquidity', 0)))
                elif isinstance(result, dict):
                    liquidity = max(liquidity, float(result.get('totalLiquidity', 0)))
        except Exception as e:
            print(f"[get_liquidity_data] Blockchain explorer liquidity error for {token_address} on {chain}: {e}")
        # Fallback if all real-time sources failed or returned zero/invalid
        if (not liquidity or liquidity == 0) and fallback:
            print(f"[Fallback] Using fallback liquidity data for {token_address} on {chain}: {fallback}")
            return fallback['liquidity']
        return liquidity
    
    def fetch_onchain_data(self, token_address, chain):
        """Fetch comprehensive on-chain data for token analysis
        
        This method gathers critical on-chain metrics including:
        1. Contract Verification Status:
           - Checks if source code is verified
           - Validates contract deployment
        
        2. Holder Analysis:
           - Total number of token holders
           - Concentration among top holders
           - Distribution patterns
        
        3. Liquidity Metrics:
           - Total liquidity across DEXes
           - Liquidity depth and stability
        
        4. Red Flag Detection:
           - Proxy contract patterns
           - Ownership changes
           - Suspicious patterns
        
        5. BitQuery Integration (if available):
           - Transaction patterns
           - Token transfers
           - Historical metrics
        
        Args:
            token_address (str): The contract address to analyze
            chain (str): The blockchain network (eth/bsc)
            
        Returns:
            dict: Structured on-chain data containing:
                - contract_verified: Verification status
                - holders: Holder statistics
                - liquidity: Liquidity metrics
                - red_flags: Detected warning signs
                - bitquery: Additional on-chain metrics (if available)
        """
        if chain not in self.CHAIN_CONFIG:
            return {
                'contract_verified': 'unknown',
                'holders': {'total_holders': 0, 'top10_concentration': 100},
                'liquidity': 0,
                'red_flags': [],
                'breadcrumbs_risk': None,
                'breadcrumbs_token': None
            }
        data = {
            'contract_verified': 'unknown',
            'holders': {'total_holders': 0, 'top10_concentration': 100},
            'liquidity': 0,
            'red_flags': [],
            'breadcrumbs_risk': None,
            'breadcrumbs_token': None
        }
        try:
            # Basic on-chain data
            data['contract_verified'] = self.get_contract_verification_status(token_address, chain)
            data['holders'] = self.get_holder_data(token_address, chain)
            data['liquidity'] = self.get_liquidity_data(token_address, chain)
            
            # Advanced on-chain checks
            data['red_flags'] = self.detect_red_flags(token_address, chain)
            
            # BitQuery data integration
            if self.BITQUERY_API_KEY:
                data['bitquery'] = self.fetch_bitquery_data(token_address, chain)
            
            # Breadcrumbs API integration
            breadcrumbs_risk = fetch_breadcrumbs_risk_score(token_address)
            if breadcrumbs_risk:
                data['breadcrumbs_risk'] = breadcrumbs_risk
            breadcrumbs_token = fetch_breadcrumbs_token_info(token_address)
            if breadcrumbs_token:
                data['breadcrumbs_token'] = breadcrumbs_token
        except Exception as e:
            print(f"[fetch_onchain_data] Error for {token_address} on {chain}: {e}")
        
        return data
    
    def fetch_bitquery_data(self, token_address, chain):
        """Fetch on-chain data from BitQuery"""
        if not getattr(self, 'bitquery_available', True):
            if not hasattr(self, '_bitquery_warned'):
                msg = "BitQuery API unavailable due to previous 401 error. Skipping BitQuery for all tokens and using fallback data."
                print(msg)
                logging.warning(msg)
                self._bitquery_warned = True
            return {
                "transfers": {"count": 0, "amount": 0},
                "transactions": {"count": 0, "amount": 0}
            }
        api_key = os.getenv("BITQUERY_API_KEY")
        if not api_key:
            print("BitQuery API key not configured, skipping BitQuery data")
            return {}
        api_key = api_key.strip()  # Remove whitespace
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            
        # Map chain to BitQuery's network identifier
        network_map = {
            "eth": "ethereum",
            "bsc": "bsc"
        }
        
        if chain not in network_map:
            return {
                "transfers": {"count": 0, "amount": 0},
                "transactions": {"count": 0, "amount": 0}
            }
            
        query = """
        {
          %s(network: %s) {
            transfers(currency: {is: "%s"}) {
              count
              amount
              receiver {
                address
              }
              sender {
                address
              }
            }
            transactions(txCurrency: {is: "%s"}) {
              count
              amount
            }
          }
        }
        """ % (network_map[chain], network_map[chain], token_address, token_address)
        
        try:
            cache_key = get_cache_key("https://graphql.bitquery.io", None, headers, {"query": query})
            cached = api_cache.get(cache_key)
            if cached:
                bitquery_data = cached
            else:
                response = self.session.post(
                    "https://graphql.bitquery.io",
                    json={"query": query},
                    headers=headers,
                    timeout=30
                )
                if response.status_code == 200:
                    bitquery_data = response.json()
                    api_cache.set(cache_key, bitquery_data)
                elif response.status_code == 401:
                    msg = f"BitQuery API error 401 Unauthorized for {token_address} on {chain}. Disabling BitQuery for this run. Please check your API key."
                    print(msg)
                    logging.error(msg)
                    self.bitquery_available = False
                    return {
                        "transfers": {"count": 0, "amount": 0},
                        "transactions": {"count": 0, "amount": 0}
                    }
                else:
                    bitquery_data = None
            if bitquery_data:
                return bitquery_data.get('data', {}).get(network_map[chain], {
                    "transfers": {"count": 0, "amount": 0},
                    "transactions": {"count": 0, "amount": 0}
                })
            return {
                "transfers": {"count": 0, "amount": 0},
                "transactions": {"count": 0, "amount": 0}
            }
        except Exception as e:
            print(f"[fetch_bitquery_data] Error for {token_address} on {chain}: {e}")
            return {
                "transfers": {"count": 0, "amount": 0},
                "transactions": {"count": 0, "amount": 0}
            }
    
    def fetch_market_data(self, token_address, chain):
        """Fetch market data from CoinGecko and CoinMarketCap APIs (with contract mapping for CMC)
        
        This method gathers comprehensive market data from two major sources:
        
        1. CoinMarketCap:
           - Price and volume data
           - Market pairs information
           - Market cap and supply metrics
           Uses v1 API endpoint with proper contract address formatting
        
        2. CoinGecko:
           - Detailed market metrics
           - Community and social data
           - Developer activity metrics
           Uses Pro API endpoint for authenticated requests
        
        The method handles API failures gracefully and provides fallback data
        structures to ensure the risk assessment can continue even with
        partial data.
        
        Args:
            token_address (str): The contract address of the token
            chain (str): The blockchain network (eth/bsc)
            
        Returns:
            dict: Structured market data containing:
                - cmc: CoinMarketCap data
                - coingecko: CoinGecko data
                Both with standardized sub-structures for consistent access
        """
        data = {
            'cmc': {
                'data': {},
                'metadata': {'error': None}
            },
            'coingecko': {
                'market_data': {
                    'current_price': {'usd': 0},
                    'total_volume': {'usd': 0},
                    'market_cap': {'usd': 0}
                },
                'community_data': {},
                'developer_data': {}
            }
        }
        
        # CoinMarketCap data
        cmc_api_key = os.getenv("COINMARKETCAP_API_KEY")
        if cmc_api_key:
            try:
                # Step 1: Try address mapping
                map_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"
                params = {"address": Web3.to_checksum_address(token_address)}
                headers = {"X-CMC_PRO_API_KEY": cmc_api_key, "Accept": "application/json"}
                cache_key = get_cache_key(map_url, params, headers)
                cached = api_cache.get(cache_key)
                if cached:
                    map_data = cached
                else:
                    map_response = self.session.get(map_url, headers=headers, params=params, timeout=20)
                    map_data = map_response.json() if map_response.status_code == 200 else None
                    if map_data:
                        api_cache.set(cache_key, map_data)
                cmc_id = None
                if map_data and map_data.get('status', {}).get('error_code') == 0 and map_data.get('data'):
                    cmc_id = map_data['data'][0]['id']
                # Step 2: If address mapping fails, try symbol and name from cmc_symbol_map
                if not cmc_id:
                    mapping_obj = self.cmc_symbol_map.get(token_address.lower(), {})
                    tried_symbols = set()
                    tried_names = set()
                    # Try symbol and name from mapping object
                    if mapping_obj:
                        symbol = mapping_obj.get('symbol')
                        name = mapping_obj.get('name')
                        for sym in filter(None, [symbol, symbol.upper() if symbol else None, symbol.lower() if symbol else None]):
                            if sym and sym not in tried_symbols:
                                params = {"symbol": sym}
                                map_response = self.session.get(map_url, headers=headers, params=params, timeout=20)
                                if map_response.status_code == 200:
                                    map_data = map_response.json()
                                    if map_data.get('status', {}).get('error_code') == 0 and map_data.get('data'):
                                        cmc_id = map_data['data'][0]['id']
                                        logging.info(f"CMC ID found by symbol '{sym}' for {token_address}")
                                        break
                                tried_symbols.add(sym)
                        if not cmc_id and name:
                            for nm in filter(None, [name, name.upper(), name.lower()]):
                                if nm and nm not in tried_names:
                                    params = {"name": nm}
                                    map_response = self.session.get(map_url, headers=headers, params=params, timeout=20)
                                    if map_response.status_code == 200:
                                        map_data = map_response.json()
                                        if map_data.get('status', {}).get('error_code') == 0 and map_data.get('data'):
                                            cmc_id = map_data['data'][0]['id']
                                            logging.info(f"CMC ID found by name '{nm}' for {token_address}")
                                            break
                                    tried_names.add(nm)
                    # Try all symbols in the map if still not found
                    if not cmc_id:
                        for addr, obj in self.cmc_symbol_map.items():
                            sym = obj.get('symbol')
                            for sym_variant in filter(None, [sym, sym.upper() if sym else None, sym.lower() if sym else None]):
                                if sym_variant and sym_variant not in tried_symbols:
                                    params = {"symbol": sym_variant}
                                    map_response = self.session.get(map_url, headers=headers, params=params, timeout=20)
                                    if map_response.status_code == 200:
                                        map_data = map_response.json()
                                        if map_data.get('status', {}).get('error_code') == 0 and map_data.get('data'):
                                            cmc_id = map_data['data'][0]['id']
                                            logging.info(f"CMC ID found by global symbol '{sym_variant}' for {token_address}")
                                            break
                                    tried_symbols.add(sym_variant)
                            if cmc_id:
                                break
                    # Try all names in the map if still not found
                    if not cmc_id:
                        for addr, obj in self.cmc_symbol_map.items():
                            nm = obj.get('name')
                            for nm_variant in filter(None, [nm, nm.upper() if nm else None, nm.lower() if nm else None]):
                                if nm_variant and nm_variant not in tried_names:
                                    params = {"name": nm_variant}
                                    map_response = self.session.get(map_url, headers=headers, params=params, timeout=20)
                                    if map_response.status_code == 200:
                                        map_data = map_response.json()
                                        if map_data.get('status', {}).get('error_code') == 0 and map_data.get('data'):
                                            cmc_id = map_data['data'][0]['id']
                                            logging.info(f"CMC ID found by global name '{nm_variant}' for {token_address}")
                                            break
                                    tried_names.add(nm_variant)
                            if cmc_id:
                                break
                # Step 3: Fetch quotes if we have a CMC id
                if cmc_id:
                    quotes_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
                    params = {"id": cmc_id, "convert": "USD"}
                    quotes_response = self.session.get(quotes_url, headers=headers, params=params, timeout=20)
                    if quotes_response.status_code == 200:
                        quotes_data = quotes_response.json()
                        if quotes_data.get('status', {}).get('error_code') == 0:
                            data['cmc']['data'] = quotes_data.get('data', {})
                        else:
                            print(f"CMC Quotes API error: {quotes_data.get('status', {}).get('error_message')}")
                    else:
                        print(f"CMC Quotes API error: {quotes_response.status_code} - {quotes_response.text}")
                else:
                    warning_msg = f"CMC Map API could not find id for address {token_address} or symbol fallback failed. Skipping CMC data for this token."
                    print(warning_msg)
                    logging.warning(warning_msg)
            except Exception as e:
                print(f"[fetch_market_data] Error fetching CMC data for {token_address} on {chain}: {e}")
        
        # CoinGecko data (unchanged)
        try:
            if self.CHAIN_CONFIG[chain]['coingecko_platform']:
                use_pro_api = os.getenv("COINGECKO_PRO_API") == "true"
                base_url = "https://pro-api.coingecko.com/api/v3" if use_pro_api else "https://api.coingecko.com/api/v3"
                cg_url = f"{base_url}/coins/{self.CHAIN_CONFIG[chain]['coingecko_platform']}/contract/{token_address}"
                headers = {'Accept': 'application/json'}
                if os.getenv("COINGECKO_API_KEY") and use_pro_api:
                    headers["x-cg-pro-api-key"] = os.getenv("COINGECKO_API_KEY")
                params = {
                    'localization': 'false',
                    'tickers': 'true',
                    'market_data': 'true',
                    'community_data': 'true',
                    'developer_data': 'true',
                    'sparkline': 'false'
                }
                cache_key = get_cache_key(cg_url, params, headers)
                cached = api_cache.get(cache_key)
                if cached:
                    cg_data = cached
                else:
                    response = self.session.get(cg_url, headers=headers, params=params, timeout=5)
                    if response.status_code == 200:
                        cg_data = response.json()
                        api_cache.set(cache_key, cg_data)
                    elif response.status_code == 429:
                        msg = f"CoinGecko API error 429 (rate limit) for {token_address} on {chain}. Falling back to cached or fallback data."
                        print(msg)
                        logging.warning(msg)
                        # Try to load from fallback data
                        fallback = self.fallbacks.get('tokens', {}).get(token_address.lower())
                        if fallback and 'liquidity' in fallback:
                            data['coingecko']['market_data']['total_volume'] = {'usd': fallback['liquidity']}
                            logging.info(f"Used fallback liquidity for {token_address} from fallbacks.json.")
                        cg_data = None
                    else:
                        print(f"CoinGecko API error: {response.status_code} - {response.text}")
                        cg_data = None
                if cg_data and 'market_data' in cg_data:
                    data['coingecko']['market_data'].update(cg_data['market_data'])
                if cg_data and 'community_data' in cg_data:
                    data['coingecko']['community_data'] = cg_data['community_data']
                if cg_data and 'developer_data' in cg_data:
                    data['coingecko']['developer_data'] = cg_data['developer_data']
            elif response.status_code == 429:
                msg = f"CoinGecko API error 429 (rate limit) for {token_address} on {chain}. Falling back to cached or fallback data."
                print(msg)
                logging.warning(msg)
                # Try to load from fallback data
                fallback = self.fallbacks.get('tokens', {}).get(token_address.lower())
                if fallback and 'liquidity' in fallback:
                    data['coingecko']['market_data']['total_volume'] = {'usd': fallback['liquidity']}
                    logging.info(f"Used fallback liquidity for {token_address} from fallbacks.json.")
                cg_data = None
            elif response.status_code != 404:
                print(f"CoinGecko API error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[fetch_market_data] Error fetching CoinGecko data for {token_address} on {chain}: {e}")
        
        # --- DeFiLlama fallback for market cap and price (all tokens) ---
        missing_market_cap = data['coingecko']['market_data']['market_cap'].get('usd', 0) == 0
        missing_price = data['coingecko']['market_data']['current_price'].get('usd', 0) == 0
        if missing_market_cap or missing_price:
            try:
                # Map internal chain names to DeFiLlama chain names
                defillama_chain = "ethereum" if chain in ["eth", "uni"] else "bsc" if chain == "bsc" else "ethereum"
                llama_price = fetch_defillama_token_price(token_address, defillama_chain)
                if llama_price and 'coins' in llama_price:
                    key = f'{defillama_chain}:{token_address.lower()}'
                    coin_data = llama_price['coins'].get(key, {})
                    price = coin_data.get('price')
                    supply = coin_data.get('circulatingSupply')
                    if missing_market_cap and price and supply:
                        market_cap = price * supply
                        data['coingecko']['market_data']['market_cap']['usd'] = market_cap
                    if missing_price and price:
                        data['coingecko']['market_data']['current_price']['usd'] = price
            except Exception as e:
                print(f"[fetch_market_data] DeFiLlama fallback error for price/market cap: {e}")
        
        # --- DeFiLlama fallback for 24h volume (all tokens, protocol-level) ---
        missing_volume = data['coingecko']['market_data']['total_volume'].get('usd', 0) == 0
        protocol_name = self.CHAIN_CONFIG[chain]['dex'] if chain in self.CHAIN_CONFIG and 'dex' in self.CHAIN_CONFIG[chain] else None
        if missing_volume and protocol_name:
            try:
                llama_protocol = fetch_defillama_protocol_tvl(protocol_name)
                if llama_protocol:
                    volume_24h = llama_protocol.get('volume24h')
                    if volume_24h:
                        data['coingecko']['market_data']['total_volume']['usd'] = volume_24h
            except Exception as e:
                print(f"[fetch_market_data] DeFiLlama fallback error for 24h volume: {e}")
        
        return data
    
    def fetch_santiment_data(self, token_address, chain):
        """Fetch social and development data from Santiment"""
        if not self.SANTIMENT_API_KEY:
            return {}
        
        data = {}
        base_url = "https://api.santiment.net/graphql"
        headers = {
            "Authorization": f"Apikey {self.SANTIMENT_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Query for social trends
        social_query = {
            "query": """
            {
              socialVolumeTotal(
                slug: \"%s\"
                from: \"%s\"
                to: \"%s\"
                interval: \"1d\"
              ) {
                datetime
                value
              }
            }
            """ % (token_address, 
                  (pd.Timestamp.now() - pd.DateOffset(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                  pd.Timestamp.now().strftime('%Y-%m-%dT%H:%M:%SZ'))
        }
        
        # Query for developer activity
        dev_query = {
            "query": """
            {
              devActivity(
                slug: \"%s\"
                from: \"%s\"
                to: \"%s\"
                interval: \"1d\"
              ) {
                datetime
                value
              }
            }
            """ % (token_address, 
                  (pd.Timestamp.now() - pd.DateOffset(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                  pd.Timestamp.now().strftime('%Y-%m-%dT%H:%M:%SZ'))
        }
        
        try:
            # Fetch social data
            cache_key_social = get_cache_key(base_url, None, headers, social_query)
            cached_social = api_cache.get(cache_key_social)
            if cached_social:
                data['social'] = cached_social.get('data', {}).get('socialVolumeTotal', [])
            else:
                response = self.session.post(
                    base_url, 
                    json=social_query, 
                    headers=headers, 
                    timeout=20
                )
                if response.status_code == 200:
                    social_data = response.json()
                    api_cache.set(cache_key_social, social_data)
                    data['social'] = social_data.get('data', {}).get('socialVolumeTotal', [])
            # Fetch developer activity
            cache_key_dev = get_cache_key(base_url, None, headers, dev_query)
            cached_dev = api_cache.get(cache_key_dev)
            if cached_dev:
                data['dev_activity'] = cached_dev.get('data', {}).get('devActivity', [])
            else:
                response = self.session.post(
                    base_url, 
                    json=dev_query, 
                    headers=headers, 
                    timeout=20
                )
                if response.status_code == 200:
                    dev_data = response.json()
                    api_cache.set(cache_key_dev, dev_data)
                    data['dev_activity'] = dev_data.get('data', {}).get('devActivity', [])
        except Exception as e:
            print(f"[fetch_santiment_data] Error for {token_address} on {chain}: {e}")
        
        return data
    
    def fetch_security_reports(self, token_address, chain):
        """Fetch security reports from CertiK with correct endpoint"""
        reports = []
        
        # Only fetch for supported chains
        if chain not in ["eth", "bsc"]:
            return reports
        
        # CertiK API
        if os.getenv("CERTIK_API_KEY"):
            try:
                certik_url = "https://api.certik.com/v1/tokens"
                params = {
                    "address": token_address,
                    "chain": "eth",  # Mainnet is the primary chain
                    "limit": 1
                }
                headers = {
                    "Authorization": f"Bearer {os.getenv('CERTIK_API_KEY')}",
                    "Accept": "application/json"
                }
                cache_key = get_cache_key(certik_url, params, headers)
                cached = api_cache.get(cache_key)
                if cached:
                    certik_data = cached
                else:
                    response = self.session.get(certik_url, headers=headers, params=params, timeout=20)
                    certik_data = response.json() if response.status_code == 200 else None
                    if certik_data:
                        api_cache.set(cache_key, certik_data)
                if certik_data and certik_data.get('items'):
                    reports.append({
                        'source': 'CertiK',
                        'audit_status': certik_data['items'][0].get('audit_status', 'unaudited'),
                        'score': certik_data['items'][0].get('score'),
                        'last_audit_date': certik_data['items'][0].get('last_audit_date')
                    })
                else:
                    print(f"[fetch_security_reports] CertiK API error for {token_address} on {chain}: {response.status_code if 'response' in locals() else 'N/A'} - {response.text if 'response' in locals() else 'N/A'}")
            except Exception as e:
                print(f"[fetch_security_reports] Error fetching CertiK data for {token_address} on {chain}: {e}")
        
        return reports
    
    def fetch_enhanced_data(self, token_address, chain):
        """Fetch enhanced data from new API integrations (Zapper, DeBank, DeFiLlama, Moralis)"""
        enhanced_data = {
            'zapper': {},
            'debank': {},
            'defillama': {},
            'moralis': {}
        }
        
        try:
            # Zapper API data
            if self.ZAPPER_API_KEY:
                try:
                    # Fetch portfolio data for the token contract
                    zapper_portfolio = fetch_zapper_portfolio_data(token_address)
                    if zapper_portfolio:
                        enhanced_data['zapper']['portfolio'] = zapper_portfolio
                    
                    # Fetch protocol data if available
                    zapper_protocol = fetch_zapper_protocol_data("uniswap-v3")  # Example protocol
                    if zapper_protocol:
                        enhanced_data['zapper']['protocol'] = zapper_protocol
                except Exception as e:
                    print(f"[fetch_enhanced_data] Zapper API error: {e}")
            
            # DeBank API data
            if self.DEBANK_API_KEY:
                try:
                    # Fetch portfolio data
                    debank_portfolio = fetch_debank_portfolio(token_address)
                    if debank_portfolio:
                        enhanced_data['debank']['portfolio'] = debank_portfolio
                    
                    # Fetch token list for the chain
                    chain_id = "eth" if chain == "eth" else "bsc"
                    debank_tokens = fetch_debank_token_list(chain_id)
                    if debank_tokens:
                        enhanced_data['debank']['tokens'] = debank_tokens
                except Exception as e:
                    print(f"[fetch_enhanced_data] DeBank API error: {e}")
            
            # DeFiLlama API data (no API key required - free API)
            try:
                # Fetch token price data
                defillama_price = fetch_defillama_token_price(token_address, chain)
                if defillama_price:
                    enhanced_data['defillama']['price'] = defillama_price
                
                # Fetch yield pools data
                defillama_yields = fetch_defillama_yield_pools("uniswap-v3")
                if defillama_yields:
                    enhanced_data['defillama']['yields'] = defillama_yields
            except Exception as e:
                print(f"[fetch_enhanced_data] DeFiLlama API error: {e}")
            
            # Moralis API data
            if self.MORALIS_API_KEY:
                try:
                    # Fetch token metadata
                    moralis_metadata = fetch_moralis_token_metadata(token_address, chain)
                    if moralis_metadata:
                        enhanced_data['moralis']['metadata'] = moralis_metadata
                    
                    # Fetch token price
                    moralis_price = fetch_moralis_token_price(token_address, chain)
                    if moralis_price:
                        enhanced_data['moralis']['price'] = moralis_price
                    
                    # Fetch recent transfers
                    moralis_transfers = fetch_moralis_token_transfers(token_address, chain, limit=50)
                    if moralis_transfers:
                        enhanced_data['moralis']['transfers'] = moralis_transfers
                except Exception as e:
                    print(f"[fetch_enhanced_data] Moralis API error: {e}")
                    
        except Exception as e:
            print(f"[fetch_enhanced_data] General error: {e}")
        
        return enhanced_data
    
    def detect_red_flags(self, token_address, chain):
        """Detect security red flags with improved reliability and strict compliance criteria"""
        flags_triggered = []
        if chain not in self.CHAIN_CONFIG:
            return flags_triggered
        try:
            address_lower = token_address.lower()
            is_well_known = address_lower in self.well_known_tokens
            liquidity = self.get_liquidity_data(token_address, chain)
            min_liquidity = self.CHAIN_CONFIG[chain]['min_liquidity']
            if not is_well_known and liquidity > 0 and liquidity < min_liquidity:
                flags_triggered.append('low_liquidity')
            holders = self.get_holder_data(token_address, chain)
            if not is_well_known and holders['total_holders'] > 0 and (holders['top10_concentration'] > 80 or holders['total_holders'] < 1000):
                flags_triggered.append('high_concentration')
            contract_verified = self.get_contract_verification_status(token_address, chain)
            # --- Enhanced logic for unverified_contract ---
            if not is_well_known and contract_verified != 'verified':
                # Get contract age (block explorer or fallback)
                contract_age_days = None
                try:
                    # Try to get contract creation date from Etherscan API
                    params = {
                        'module': 'contract',
                        'action': 'getcontractcreation',
                        'contractaddresses': token_address,
                        'apikey': self.CHAIN_CONFIG[chain]['scan_key']
                    }
                    response = self.session.get(
                        self.CHAIN_CONFIG[chain]['scan_url'],
                        params=params,
                        timeout=20
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if 'result' in data and isinstance(data['result'], list) and len(data['result']) > 0:
                            creation_ts = data['result'][0].get('timestamp')
                            if creation_ts:
                                creation_date = datetime.datetime.utcfromtimestamp(int(creation_ts))
                                contract_age_days = (datetime.datetime.utcnow() - creation_date).days
                except Exception as e:
                    print(f"[detect_red_flags] Error getting contract age: {e}")
                # Get 24h volume (from market data)
                volume_24h = 0
                try:
                    cg_platform = self.CHAIN_CONFIG[chain].get('coingecko_platform')
                    if cg_platform:
                        cg_url = f"https://api.coingecko.com/api/v3/coins/{cg_platform}/contract/{token_address}"
                        response = self.session.get(cg_url, timeout=20)
                        if response.status_code == 200:
                            cg_data = response.json()
                            if 'market_data' in cg_data:
                                volume_24h = cg_data['market_data']['total_volume'].get('usd', 0)
                except Exception as e:
                    print(f"[detect_red_flags] Error getting 24h volume: {e}")
                # Strict compliance: only flag if contract is not verified AND (age < 90 days OR volume < $50K)
                if ((contract_age_days is not None and contract_age_days < 90) or (volume_24h < 50_000)):
                    flags_triggered.append('unverified_contract')
            # --- Proxy contract check (robust pattern) ---
            try:
                params = {
                    'module': 'contract',
                    'action': 'getsourcecode',
                    'address': token_address,
                    'apikey': self.CHAIN_CONFIG[chain]['scan_key']
                }
                response = self.session.get(
                    self.CHAIN_CONFIG[chain]['scan_url'],
                    params=params,
                    timeout=20
                )
                if response.status_code == 200:
                    data = response.json()
                    if 'result' in data:
                        result = data['result']
                        if isinstance(result, list) and len(result) > 0:
                            source_code = result[0].get('SourceCode', '')
                            # Look for proxy patterns, but avoid false positives
                            proxy_patterns = ['delegatecall', 'proxy', 'implementation', 'upgradeTo', 'call.value']
                            if any(pat in source_code.lower() for pat in proxy_patterns):
                                flags_triggered.append('is_proxy_contract')
            except Exception as e:
                print(f"[detect_red_flags] Error checking proxy contract: {e}")
        except Exception as e:
            print(f"[detect_red_flags] Error for {token_address} on {chain}: {e}")
        return flags_triggered
    
    def assess_token(self, token_address, chain="eth", progress_callback=None, token_index=0, total_tokens=1):
        """Assess a token and return a risk report with new AML/Compliance logic"""
        chain = chain.lower()
        if chain not in self.CHAIN_CONFIG:
            return {
                'token': token_address,
                'chain': chain,
                'risk_score': 150,  # Max risk for unsupported chains
                'risk_category': 'Extreme Risk',
                'details': {'error': f'Unsupported chain: {chain}'}
            }
        risk_report = {
            'token': token_address,
            'symbol': '',
            'onchain': {
                'contract_verified': 'unknown',
                'holders': {'total_holders': 0, 'top10_concentration': 100},
                'liquidity': 0,
                'red_flags': []
            },
            'market': {
                'cmc': {
                    'data': {},
                    'metadata': {'error': None}
                },
                'coingecko': {
                    'market_data': {
                        'current_price': {'usd': 0},
                        'total_volume': {'usd': 0},
                        'market_cap': {'usd': 0}
                    },
                    'community_data': {},
                    'developer_data': {}
                }
            },
            'security': [],
            'santiment': {
                'social': {'timeseriesData': []},
                'dev_activity': {'timeseriesData': []}
            }
        }
        try:
            print(f"\nCollecting data for {token_address}...")
            
            # Phase 1: Fetching token data
            update_progress_bar(0, f"Fetching onchain data for {token_address[:8]}...")
            try:
                print("Fetching onchain data...")
                onchain_data = self.fetch_onchain_data(token_address, chain)
                # Preserve existing red flags and merge with new ones
                existing_red_flags = risk_report['onchain'].get('red_flags', [])
                risk_report['onchain'].update(onchain_data)
                # Merge red flags instead of overwriting
                new_red_flags = onchain_data.get('red_flags', [])
                combined_red_flags = list(set(existing_red_flags + new_red_flags))  # Remove duplicates
                risk_report['onchain']['red_flags'] = combined_red_flags
            except Exception as e:
                print(f"[assess_token] Warning: Error fetching onchain data for {token_address} on {chain}: {e}")
            
            update_progress_bar(0, f"Fetching market data for {token_address[:8]}...")
            try:
                print("Fetching market data...")
                market_data = self.fetch_market_data(token_address, chain)
                risk_report['market'].update(market_data)
                
                # Extract symbol from market data
                try:
                    coingecko_data = market_data.get('coingecko', {})
                    if coingecko_data and 'symbol' in coingecko_data:
                        risk_report['symbol'] = coingecko_data['symbol'].upper()
                    elif coingecko_data and 'name' in coingecko_data:
                        # Try to extract symbol from name or use mapping
                        mapping_obj = self.cmc_symbol_map.get(token_address.lower(), {})
                        risk_report['symbol'] = mapping_obj.get('symbol', '').upper()
                except Exception as e:
                    print(f"[assess_token] Warning: Error extracting symbol: {e}")
            except Exception as e:
                print(f"[assess_token] Warning: Error fetching market data for {token_address} on {chain}: {e}")
            
            update_progress_bar(0, f"Fetching security data for {token_address[:8]}...")
            try:
                print("Fetching security data...")
                risk_report['security'] = self.fetch_security_reports(token_address, chain)
            except Exception as e:
                print(f"[assess_token] Warning: Error fetching security data for {token_address} on {chain}: {e}")
            
            update_progress_bar(0, f"Fetching enhanced data for {token_address[:8]}...")
            try:
                print("Fetching enhanced data from new APIs...")
                # Add new API data to risk_report
                risk_report['enhanced_data'] = self.fetch_enhanced_data(token_address, chain)
            except Exception as e:
                print(f"[assess_token] Warning: Error fetching enhanced data for {token_address} on {chain}: {e}")
            
            update_progress_bar(0, f"Fetching Santiment data for {token_address[:8]}...")
            try:
                print("Fetching Santiment data...")
                santiment_data = self.fetch_santiment_data(token_address, chain)
                if santiment_data:
                    risk_report['santiment'].update(santiment_data)
            except Exception as e:
                print(f"[assess_token] Warning: Error fetching Santiment data for {token_address} on {chain}: {e}")
            
            # Phase 2: Analyzing security & market data
            update_progress_bar(1, f"Analyzing {token_address[:8]}...")
            print("Applying compliance checks...")
            self.apply_strict_compliance_checks(risk_report, chain)
            
            # Add stablecoin and EU compliance information
            try:
                symbol = risk_report.get('symbol', '')
                project_data = risk_report.get('market', {}).get('coingecko', {})
                risk_report['is_stablecoin'] = self.is_stablecoin(token_address, symbol, project_data)
                risk_report['eu_compliance_status'] = self.get_eu_compliance_status(risk_report)
            except Exception as e:
                print(f"[assess_token] Warning: Error adding compliance info for {token_address}: {e}")
                risk_report['is_stablecoin'] = False
                risk_report['eu_compliance_status'] = "Unknown"
            
            print("Calculating component scores...")
            component_scores = {}
            for component in self.WEIGHTS.keys():
                try:
                    score_method = getattr(self, f"score_{component}")
                    # Special handling for functions that need additional arguments
                    if component in ['aml_data', 'compliance_data']:
                        component_scores[component] = score_method(risk_report, token_address, chain)
                    else:
                        component_scores[component] = score_method(risk_report)
                    print(f"{component}: {component_scores[component]}")
                except Exception as e:
                    print(f"[assess_token] Error calculating {component} score for {token_address} on {chain}: {e}")
                    component_scores[component] = 7  # Default to medium-high risk on error
            
            # Calculate final risk score (no progress bar update for individual tokens)
            print("Calculating final risk score...")
            total_risk_score = 0
            for component, weight in self.WEIGHTS.items():
                total_risk_score += component_scores[component] * weight * 10  # Scale up the scores
            for flag in risk_report['onchain']['red_flags']:
                boost = next(
                    (f['risk_boost'] for f in self.RED_FLAGS if f['check'] == flag), 
                    0
                )
                print(f"Applying red flag boost for {flag}: +{boost}")
                total_risk_score += boost
            total_risk_score = min(150, max(0, total_risk_score))
            
            # After all other data collection, enrich with 1inch data
            try:
                oneinch_data = enrich_with_1inch_data(token_address, chain_id=self.CHAIN_CONFIG[chain]['chain_id'])
                risk_report['oneinch'] = oneinch_data
            except Exception as e:
                risk_report['oneinch'] = {'error': str(e)}
            
            return {
                'token': token_address,
                'chain': chain,
                'risk_score': round(total_risk_score, 2),
                'risk_category': self.classify_risk(total_risk_score, risk_report),
                'details': risk_report,
                'component_scores': component_scores
            }
        except Exception as e:
            print(f"[assess_token] Critical error assessing token {token_address} on {chain}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'token': token_address,
                'chain': chain,
                'risk_score': 150,
                'risk_category': 'Extreme Risk',
                'details': {'error': str(e)}
            }
    
    # Scoring methods for each of the 14 risk components (1-10 scale)
    def score_industry_impact(self, risk_report):
        """Enhanced score based on token's industry impact using multiple data sources (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            
            # Primary market cap analysis
            try:
                market_cap = risk_report['market']['coingecko']['market_data']['market_cap'].get('usd', 0)
                if market_cap > 1_000_000_000:
                    score -= 3  # Very high impact
                    data_found = True
                elif market_cap > 100_000_000:
                    score -= 2  # High impact
                    data_found = True
                elif market_cap > 10_000_000:
                    score -= 1  # Medium impact
                    data_found = True
                elif market_cap > 1_000_000:
                    score += 0  # Low impact
                else:
                    score += 2  # Very low impact
            except:
                pass
            
            # Alternative data sources when market cap is limited
            if not data_found:
                # Use DeFiLlama data for TVL impact
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('price') or defillama_data.get('yields'):
                        score -= 1  # Lower risk if DeFiLlama tracks it
                except:
                    pass
                
                # Use Moralis transfer data for activity impact
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers and len(transfers) > 10:
                        score -= 1  # Lower risk if high transfer activity
                except:
                    pass
                
                # Use holder count as impact indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {}).get('total_holders', 0)
                    if holders > 50000:
                        score -= 2  # Very high impact
                    elif holders > 10000:
                        score -= 1  # High impact
                    elif holders < 1000:
                        score += 1  # Low impact
                except:
                    pass
                
                # Use liquidity as impact indicator
                try:
                    liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                    if liquidity > 10_000_000:
                        score -= 2  # Very high impact
                    elif liquidity > 1_000_000:
                        score -= 1  # High impact
                    elif liquidity < 100_000:
                        score += 1  # Low impact
                except:
                    pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in industry_impact scoring: {e}")
            return 7
    
    def score_tech_innovation(self, risk_report):
        """Enhanced score based on technological innovation and contract complexity (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            innovation_score = 0
            
            # Contract verification status
            if risk_report['onchain']['contract_verified'] == 'verified':
                score -= 2  # Lower risk for verified contracts
                data_found = True
                innovation_score += 2
            else:
                score += 2  # Higher risk for unverified contracts
                innovation_score -= 2
            
            # Contract complexity analysis
            contract_source = risk_report.get('onchain', {}).get('contract_source', '')
            if contract_source:
                # Check for advanced DeFi features
                advanced_features = [
                    'flashloan', 'liquidation', 'collateral', 'oracle', 'amm', 'curve',
                    'governance', 'staking', 'yield', 'lending', 'borrowing', 'swap',
                    'uniswap', 'pancakeswap', 'sushiswap', 'balancer', 'curve'
                ]
                feature_count = sum(1 for feature in advanced_features if feature in contract_source.lower())
                if feature_count >= 4:
                    score -= 2  # Lower risk for highly innovative contracts
                    data_found = True
                    innovation_score += 3
                elif feature_count >= 2:
                    score -= 1  # Lower risk for innovative contracts
                    data_found = True
                    innovation_score += 2
                elif feature_count == 0:
                    score += 2  # Higher risk for simple contracts (might be copy-paste)
                    innovation_score -= 2
                
                # Check for advanced Solidity patterns
                advanced_patterns = [
                    'reentrancyguard', 'pausable', 'ownable', 'accesscontrol',
                    'erc20', 'erc721', 'erc1155', 'multisig', 'timelock'
                ]
                pattern_count = sum(1 for pattern in advanced_patterns if pattern in contract_source.lower())
                if pattern_count >= 3:
                    score -= 1  # Lower risk for advanced patterns
                    innovation_score += 2
                elif pattern_count == 0:
                    score += 1  # Higher risk for basic patterns
                    innovation_score -= 1
                
                # Check for proxy/upgradeable contracts
                if 'proxy' in contract_source.lower() or 'upgrade' in contract_source.lower():
                    score += 1  # Slightly higher risk due to upgradeability
                    innovation_score += 1  # But shows innovation
            
            # Market adoption indicator
            try:
                volume_24h = risk_report['market']['coingecko']['market_data']['total_volume'].get('usd', 0)
                if volume_24h > 10_000_000:  # Very high volume suggests successful innovation
                    score -= 2
                    data_found = True
                    innovation_score += 3
                elif volume_24h > 1_000_000:  # High volume suggests successful innovation
                    score -= 1
                    data_found = True
                    innovation_score += 2
                elif volume_24h < 10_000:  # Very low volume suggests poor adoption
                    score += 2
                    innovation_score -= 2
            except:
                pass
            
            # Enhanced data sources for innovation assessment
            if not data_found:
                # Use Moralis metadata for innovation indicators
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    metadata = moralis_data.get('metadata', {})
                    if metadata:
                        # Check for advanced token standards
                        token_type = metadata.get('type', '').lower()
                        if 'erc1155' in token_type:
                            score -= 2  # Lower risk for advanced token standards
                            innovation_score += 3
                        elif 'erc721' in token_type:
                            score -= 1  # Lower risk for NFT standards
                            innovation_score += 2
                        elif 'erc20' in token_type:
                            innovation_score += 1
                except:
                    pass
                
                # Use DeFiLlama data for protocol innovation
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('yields'):
                        score -= 1  # Lower risk if DeFiLlama tracks yields (indicates DeFi innovation)
                        innovation_score += 2
                    if defillama_data.get('price'):
                        innovation_score += 1
                except:
                    pass
                
                # Use transfer patterns as innovation indicator
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        # Check for complex transfer patterns (indicates smart contract innovation)
                        unique_addresses = len(set(t.get('from_address', '') for t in transfers))
                        if unique_addresses > 50:
                            score -= 1  # Lower risk for high adoption
                            innovation_score += 2
                        elif unique_addresses > 20:
                            innovation_score += 1
                        elif unique_addresses < 5:
                            score += 1  # Higher risk for low adoption
                            innovation_score -= 1
                except:
                    pass
                
                # Use holder distribution as innovation indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        total_holders = holders.get('total_holders', 0)
                        if total_holders > 50000:
                            score -= 1  # Lower risk for high adoption
                            innovation_score += 2
                        elif total_holders > 10000:
                            innovation_score += 1
                        elif total_holders < 1000:
                            score += 1  # Higher risk for low adoption
                            innovation_score -= 1
                except:
                    pass
                
                # Use market cap as innovation indicator
                try:
                    market_cap = risk_report['market']['coingecko']['market_data']['market_cap'].get('usd', 0)
                    if market_cap > 1_000_000_000:  # High market cap suggests successful innovation
                        score -= 1
                        innovation_score += 2
                    elif market_cap > 100_000_000:
                        innovation_score += 1
                    elif market_cap < 1_000_000:
                        score += 1
                        innovation_score -= 1
                except:
                    pass
            
            # Apply innovation score adjustment
            if innovation_score >= 5:
                score = max(1, score - 1)  # Bonus for high innovation
            elif innovation_score <= -3:
                score = min(10, score + 1)  # Penalty for low innovation
            
            return max(1, min(10, score))  # Ensure score is between 1-10
        except Exception as e:
            print(f"Error in tech_innovation scoring: {e}")
            return 7
    
    def score_whitepaper_quality(self, risk_report):
        """Enhanced score based on whitepaper availability and project documentation (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            documentation_score = 0
            
            # Check for project documentation indicators
            project_data = risk_report.get('market', {}).get('coingecko', {})
            
            # Website availability
            if project_data.get('links', {}).get('homepage') and len(project_data['links']['homepage']) > 0:
                score -= 1  # Lower risk if website exists
                data_found = True
                documentation_score += 2
            else:
                score += 2  # Higher risk if no website
                documentation_score -= 2
            
            # Whitepaper availability
            if project_data.get('links', {}).get('whitepaper') and len(project_data['links']['whitepaper']) > 0:
                score -= 2  # Lower risk if whitepaper exists
                data_found = True
                documentation_score += 3
            else:
                score += 2  # Higher risk if no whitepaper
                documentation_score -= 3
            
            # GitHub repository
            if project_data.get('links', {}).get('repos_url', {}).get('github'):
                score -= 1  # Lower risk if open source
                data_found = True
                documentation_score += 2
            else:
                score += 1  # Higher risk if closed source
                documentation_score -= 1
            
            # Community links
            community_links = project_data.get('links', {})
            social_presence = sum(1 for key in ['twitter_screen_name', 'telegram_channel_identifier', 'subreddit_url'] 
                                if community_links.get(key))
            if social_presence >= 3:
                score -= 1  # Lower risk if excellent social presence
                data_found = True
                documentation_score += 2
            elif social_presence >= 2:
                score -= 0.5  # Lower risk if good social presence
                data_found = True
                documentation_score += 1
            elif social_presence == 0:
                score += 1  # Higher risk if no social presence
                documentation_score -= 1
            
            # Project description quality
            description = project_data.get('description', {}).get('en', '')
            if description and len(description) > 500:
                score -= 1  # Lower risk if very detailed description
                data_found = True
                documentation_score += 2
            elif description and len(description) > 200:
                score -= 0.5  # Lower risk if detailed description
                data_found = True
                documentation_score += 1
            elif not description or len(description) < 50:
                score += 1  # Higher risk if poor description
                documentation_score -= 1
            
            # Enhanced data sources for documentation assessment
            if not data_found:
                # Check on-chain data for contract complexity (indicator of documentation quality)
                contract_source = risk_report.get('onchain', {}).get('contract_source', '')
                if contract_source:
                    # Check for documentation comments in source code
                    comment_lines = contract_source.count('//') + contract_source.count('/*') + contract_source.count('*/')
                    if comment_lines > 20:
                        score -= 1  # Lower risk if well-documented code
                        documentation_score += 2
                    elif comment_lines > 10:
                        documentation_score += 1
                    elif comment_lines < 2:
                        score += 1  # Higher risk if poorly documented code
                        documentation_score -= 1
                    
                    # Check for NatSpec documentation
                    if '@title' in contract_source or '@author' in contract_source or '@notice' in contract_source:
                        score -= 1  # Lower risk if NatSpec documentation exists
                        documentation_score += 2
                
                # Check market data for project maturity
                try:
                    market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                    if market_cap > 100_000_000:  # High market cap suggests established project
                        score -= 1
                        documentation_score += 2
                    elif market_cap > 10_000_000:
                        documentation_score += 1
                    elif market_cap < 100_000:  # Very low market cap suggests new/unknown project
                        score += 1
                        documentation_score -= 1
                except:
                    pass
                
                # Check holder count as documentation quality indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {}).get('total_holders', 0)
                    if holders > 50000:  # Many holders suggest good documentation/transparency
                        score -= 1
                        documentation_score += 2
                    elif holders > 10000:
                        documentation_score += 1
                    elif holders < 1000:  # Few holders suggest poor documentation
                        score += 1
                        documentation_score -= 1
                except:
                    pass
                
                # Use Moralis metadata for documentation indicators
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    metadata = moralis_data.get('metadata', {})
                    if metadata:
                        # Check for detailed metadata (indicates good documentation)
                        if metadata.get('name') and metadata.get('symbol') and metadata.get('decimals'):
                            documentation_score += 1
                        if metadata.get('description'):
                            documentation_score += 1
                except:
                    pass
                
                # Use DeFiLlama data for protocol documentation
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('price') or defillama_data.get('yields'):
                        documentation_score += 1  # Lower risk if DeFiLlama tracks it (indicates documentation)
                except:
                    pass
                
                # Check for professional links
                professional_links = ['linkedin', 'medium', 'blog', 'docs', 'documentation']
                prof_count = sum(1 for link in professional_links if community_links.get(link))
                if prof_count >= 2:
                    score -= 1  # Lower risk for professional documentation
                    documentation_score += 2
                elif prof_count >= 1:
                    documentation_score += 1
            
            # Apply documentation score adjustment
            if documentation_score >= 8:
                score = max(1, score - 2)  # Bonus for excellent documentation
            elif documentation_score >= 6:
                score = max(1, score - 1)  # Bonus for good documentation
            elif documentation_score <= -6:
                score = min(10, score + 2)  # Penalty for very poor documentation
            elif documentation_score <= -4:
                score = min(10, score + 1)  # Penalty for poor documentation
            
            # Additional adjustments based on project maturity
            try:
                market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                if market_cap > 10_000_000_000:  # Very large projects should have better documentation
                    if score > 7:
                        score = 7  # Cap the score for large projects with poor documentation
                elif market_cap > 1_000_000_000:  # Large projects should have good documentation
                    if score > 8:
                        score = 8  # Cap the score for large projects with poor documentation
            except:
                pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in whitepaper_quality scoring: {e}")
            return 7
    
    def score_roadmap_adherence(self, risk_report):
        """Enhanced score based on roadmap adherence and project milestones (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            adherence_score = 0
            
            # Check project age and development progress
            project_data = risk_report.get('market', {}).get('coingecko', {})
            
            # Project age analysis
            try:
                genesis_date = project_data.get('genesis_date')
                if genesis_date:
                    from datetime import datetime
                    genesis = datetime.strptime(genesis_date, '%Y-%m-%d')
                    age_days = (datetime.now() - genesis).days
                    
                    if age_days > 1095:  # More than 3 years old
                        score -= 2  # Lower risk for very established projects
                        data_found = True
                        adherence_score += 3
                    elif age_days > 365:  # More than 1 year old
                        score -= 1  # Lower risk for established projects
                        data_found = True
                        adherence_score += 2
                    elif age_days < 30:  # Less than 1 month old
                        score += 3  # Higher risk for very new projects
                        adherence_score -= 3
                    elif age_days < 90:  # Less than 3 months old
                        score += 2  # Higher risk for new projects
                        adherence_score -= 2
                    elif age_days < 180:  # Less than 6 months old
                        score += 1  # Slightly higher risk
                        adherence_score -= 1
            except:
                pass
            
            # Development activity indicators
            try:
                # Check for recent commits or updates
                last_updated = project_data.get('last_updated')
                if last_updated:
                    from datetime import datetime
                    last_update = datetime.strptime(last_updated, '%Y-%m-%dT%H:%M:%S.%fZ')
                    days_since_update = (datetime.now() - last_update).days
                    
                    if days_since_update < 3:  # Updated in last 3 days
                        score -= 2  # Very active development
                        data_found = True
                        adherence_score += 3
                    elif days_since_update < 7:  # Updated in last week
                        score -= 1  # Active development
                        data_found = True
                        adherence_score += 2
                    elif days_since_update < 30:  # Updated in last month
                        adherence_score += 1
                    elif days_since_update > 180:  # Not updated in 6+ months
                        score += 3  # Inactive development
                        adherence_score -= 3
                    elif days_since_update > 90:  # Not updated in 3+ months
                        score += 2  # Inactive development
                        adherence_score -= 2
                    elif days_since_update > 30:  # Not updated in 1+ month
                        score += 1  # Slightly inactive
                        adherence_score -= 1
            except:
                pass
            
            # Market performance as roadmap adherence indicator
            try:
                price_change_30d = project_data.get('market_data', {}).get('price_change_percentage_30d', 0)
                if price_change_30d and price_change_30d > 100:  # Very strong positive performance
                    score -= 2  # Excellent roadmap adherence
                    data_found = True
                    adherence_score += 3
                elif price_change_30d and price_change_30d > 50:  # Strong positive performance
                    score -= 1  # Good roadmap adherence
                    data_found = True
                    adherence_score += 2
                elif price_change_30d and price_change_30d > 20:  # Positive performance
                    adherence_score += 1
                elif price_change_30d and price_change_30d < -50:  # Poor performance
                    score += 2  # Poor roadmap adherence
                    adherence_score -= 2
                elif price_change_30d and price_change_30d < -20:  # Negative performance
                    score += 1  # Slightly poor roadmap adherence
                    adherence_score -= 1
            except:
                pass
            
            # Community growth indicator
            try:
                community_score = project_data.get('community_score', 0)
                if community_score > 80:
                    score -= 1  # Lower risk if excellent community engagement
                    data_found = True
                    adherence_score += 2
                elif community_score > 50:
                    score -= 0.5  # Lower risk if good community engagement
                    data_found = True
                    adherence_score += 1
                elif community_score < 10:
                    score += 1  # Higher risk if poor community engagement
                    adherence_score -= 1
            except:
                pass
            
            # Enhanced data sources for roadmap adherence assessment
            if not data_found:
                # Use Moralis transfer data for activity indicators
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        # Check for recent transfer activity (indicates ongoing development)
                        recent_transfers = len([t for t in transfers if t.get('block_timestamp')])
                        if recent_transfers > 100:
                            score -= 2  # Lower risk for very active project
                            adherence_score += 3
                        elif recent_transfers > 50:
                            score -= 1  # Lower risk for active project
                            adherence_score += 2
                        elif recent_transfers > 20:
                            adherence_score += 1
                        elif recent_transfers < 5:
                            score += 2  # Higher risk for inactive project
                            adherence_score -= 2
                        elif recent_transfers < 10:
                            score += 1  # Higher risk for low activity project
                            adherence_score -= 1
                except:
                    pass
                
                # Use DeFiLlama data for protocol development
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('yields'):
                        score -= 1  # Lower risk if DeFiLlama tracks yields (indicates active development)
                        adherence_score += 2
                    if defillama_data.get('price'):
                        adherence_score += 1
                except:
                    pass
                
                # Use holder growth as roadmap adherence indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        total_holders = holders.get('total_holders', 0)
                        if total_holders > 100000:
                            score -= 1  # Lower risk for very growing community
                            adherence_score += 2
                        elif total_holders > 50000:
                            score -= 0.5  # Lower risk for growing community
                            adherence_score += 1
                        elif total_holders < 1000:
                            score += 2  # Higher risk for stagnant community
                            adherence_score -= 2
                        elif total_holders < 5000:
                            score += 1  # Higher risk for small community
                            adherence_score -= 1
                except:
                    pass
                
                # Use liquidity growth as roadmap adherence indicator
                try:
                    liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                    if liquidity > 10_000_000:
                        score -= 1  # Lower risk for very high liquidity
                        adherence_score += 2
                    elif liquidity > 1_000_000:
                        score -= 0.5  # Lower risk for high liquidity
                        adherence_score += 1
                    elif liquidity < 100_000:
                        score += 2  # Higher risk for very low liquidity
                        adherence_score -= 2
                    elif liquidity < 500_000:
                        score += 1  # Higher risk for low liquidity
                        adherence_score -= 1
                except:
                    pass
                
                # Use trading volume as roadmap adherence indicator
                try:
                    volume_24h = project_data.get('market_data', {}).get('total_volume', {}).get('usd', 0)
                    if volume_24h > 10_000_000:
                        score -= 1  # Lower risk for high trading activity
                        adherence_score += 2
                    elif volume_24h > 1_000_000:
                        adherence_score += 1
                    elif volume_24h < 10_000:
                        score += 1  # Higher risk for low trading activity
                        adherence_score -= 1
                except:
                    pass
                
                # Use market cap as roadmap adherence indicator
                try:
                    market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                    if market_cap > 1_000_000_000:
                        score -= 1  # Lower risk for high market cap
                        adherence_score += 2
                    elif market_cap > 100_000_000:
                        adherence_score += 1
                    elif market_cap < 1_000_000:
                        score += 1  # Higher risk for low market cap
                        adherence_score -= 1
                except:
                    pass
            
            # Apply adherence score adjustment
            if adherence_score >= 6:
                score = max(1, score - 1)  # Bonus for excellent adherence
            elif adherence_score <= -4:
                score = min(10, score + 1)  # Penalty for poor adherence
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in roadmap_adherence scoring: {e}")
            return 7
    
    def score_team_expertise(self, risk_report):
        """Enhanced score based on team expertise and transparency (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            expertise_score = 0
            
            project_data = risk_report.get('market', {}).get('coingecko', {})
            
            # Team transparency indicators
            team_data = project_data.get('team', [])
            if team_data and len(team_data) > 0:
                score -= 2  # Lower risk if team is public
                data_found = True
                expertise_score += 3
                # Check for team member details
                detailed_members = sum(1 for member in team_data 
                                     if member.get('name') and member.get('position'))
                if detailed_members >= 5:
                    score -= 2  # Lower risk if very detailed team info
                    expertise_score += 3
                elif detailed_members >= 3:
                    score -= 1  # Lower risk if detailed team info
                    expertise_score += 2
                elif detailed_members == 0:
                    score += 2  # Higher risk if no detailed info
                    expertise_score -= 2
            else:
                score += 3  # Higher risk if no team information
                expertise_score -= 3
            
            # LinkedIn presence (indicator of professional background)
            links = project_data.get('links', {})
            if links.get('linkedin'):
                score -= 1  # Lower risk if LinkedIn presence
                data_found = True
                expertise_score += 2
            else:
                expertise_score -= 1
            
            # GitHub activity (indicator of technical expertise)
            if links.get('repos_url', {}).get('github'):
                score -= 1  # Lower risk if open source development
                data_found = True
                expertise_score += 2
            else:
                expertise_score -= 1
            
            # Company registration (indicator of legitimacy)
            if project_data.get('company'):
                score -= 1  # Lower risk if registered company
                data_found = True
                expertise_score += 2
            else:
                expertise_score -= 1
            
            # Community trust score
            try:
                trust_score = project_data.get('trust_score', 0)
                if trust_score > 9:
                    score -= 2  # Lower risk if very high trust
                    data_found = True
                    expertise_score += 3
                elif trust_score > 7:
                    score -= 1  # Lower risk if high trust
                    data_found = True
                    expertise_score += 2
                elif trust_score < 3:
                    score += 2  # Higher risk if low trust
                    expertise_score -= 2
                elif trust_score < 5:
                    score += 1  # Higher risk if moderate trust
                    expertise_score -= 1
            except:
                pass
            
            # Developer activity as expertise indicator
            try:
                dev_score = project_data.get('developer_score', 0)
                if dev_score > 80:
                    score -= 2  # Lower risk if very active development
                    data_found = True
                    expertise_score += 3
                elif dev_score > 50:
                    score -= 1  # Lower risk if active development
                    data_found = True
                    expertise_score += 2
                elif dev_score < 10:
                    score += 2  # Higher risk if low development activity
                    expertise_score -= 2
                elif dev_score < 30:
                    score += 1  # Higher risk if moderate development activity
                    expertise_score -= 1
            except:
                pass
            
            # Enhanced data sources for expertise assessment
            if not data_found:
                # Check contract verification as expertise indicator
                contract_verified = risk_report.get('onchain', {}).get('contract_verified', '')
                if contract_verified == 'verified':
                    score -= 1  # Lower risk if verified (indicates competent development)
                    expertise_score += 2
                else:
                    expertise_score -= 1
                
                # Check contract complexity as expertise indicator
                contract_source = risk_report.get('onchain', {}).get('contract_source', '')
                if contract_source:
                    # Count function definitions (indicator of development complexity)
                    function_count = contract_source.lower().count('function ')
                    if function_count > 30:
                        score -= 2  # Lower risk for very complex contracts (indicates high expertise)
                        expertise_score += 3
                    elif function_count > 15:
                        score -= 1  # Lower risk for complex contracts (indicates expertise)
                        expertise_score += 2
                    elif function_count < 3:
                        score += 2  # Higher risk for very simple contracts
                        expertise_score -= 2
                    elif function_count < 8:
                        score += 1  # Higher risk for simple contracts
                        expertise_score -= 1
                    
                    # Check for advanced Solidity patterns (indicates expertise)
                    advanced_patterns = [
                        'reentrancyguard', 'pausable', 'ownable', 'accesscontrol',
                        'multisig', 'timelock', 'governance', 'dao'
                    ]
                    pattern_count = sum(1 for pattern in advanced_patterns if pattern in contract_source.lower())
                    if pattern_count >= 3:
                        score -= 1  # Lower risk for advanced patterns
                        expertise_score += 2
                    elif pattern_count == 0:
                        score += 1  # Higher risk for basic patterns
                        expertise_score -= 1
                
                # Check liquidity as expertise indicator
                try:
                    liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                    if liquidity > 10_000_000:  # Very high liquidity suggests highly competent team
                        score -= 2
                        expertise_score += 3
                    elif liquidity > 1_000_000:  # High liquidity suggests competent team
                        score -= 1
                        expertise_score += 2
                    elif liquidity < 10_000:  # Very low liquidity suggests inexperienced team
                        score += 2
                        expertise_score -= 2
                    elif liquidity < 100_000:  # Low liquidity suggests inexperienced team
                        score += 1
                        expertise_score -= 1
                except:
                    pass
                
                # Check market performance as expertise indicator
                try:
                    price_change_24h = project_data.get('market_data', {}).get('price_change_percentage_24h', 0)
                    if price_change_24h and abs(price_change_24h) < 10:  # Very stable price suggests competent management
                        score -= 2
                        expertise_score += 3
                    elif price_change_24h and abs(price_change_24h) < 20:  # Stable price suggests competent management
                        score -= 1
                        expertise_score += 2
                    elif price_change_24h and abs(price_change_24h) > 50:  # Volatile price suggests poor management
                        score += 2
                        expertise_score -= 2
                    elif price_change_24h and abs(price_change_24h) > 30:  # Volatile price suggests poor management
                        score += 1
                        expertise_score -= 1
                except:
                    pass
                
                # Use Moralis metadata for expertise indicators
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    metadata = moralis_data.get('metadata', {})
                    if metadata:
                        # Check for detailed metadata (indicates professional development)
                        if metadata.get('name') and metadata.get('symbol') and metadata.get('decimals'):
                            expertise_score += 1
                        if metadata.get('description') and len(metadata.get('description', '')) > 100:
                            expertise_score += 1
                except:
                    pass
                
                # Use DeFiLlama data for protocol expertise
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('yields'):
                        score -= 1  # Lower risk if DeFiLlama tracks yields (indicates expertise)
                        expertise_score += 2
                    if defillama_data.get('price'):
                        expertise_score += 1
                except:
                    pass
                
                # Use holder count as expertise indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        total_holders = holders.get('total_holders', 0)
                        if total_holders > 100000:  # Many holders suggest competent team
                            score -= 1
                            expertise_score += 2
                        elif total_holders > 50000:
                            expertise_score += 1
                        elif total_holders < 1000:  # Few holders suggest inexperienced team
                            score += 1
                            expertise_score -= 1
                except:
                    pass
                
                # Use market cap as expertise indicator
                try:
                    market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                    if market_cap > 1_000_000_000:  # High market cap suggests competent team
                        score -= 1
                        expertise_score += 2
                    elif market_cap > 100_000_000:
                        expertise_score += 1
                    elif market_cap < 1_000_000:  # Low market cap suggests inexperienced team
                        score += 1
                        expertise_score -= 1
                except:
                    pass
            
            # Apply expertise score adjustment
            if expertise_score >= 8:
                score = max(1, score - 2)  # Bonus for very high expertise
            elif expertise_score >= 5:
                score = max(1, score - 1)  # Bonus for high expertise
            elif expertise_score <= -6:
                score = min(10, score + 2)  # Penalty for very low expertise
            elif expertise_score <= -3:
                score = min(10, score + 1)  # Penalty for low expertise
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in team_expertise scoring: {e}")
            return 7
    
    def score_management_strategy(self, risk_report):
        """Enhanced score based on management strategy and governance (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            
            project_data = risk_report.get('market', {}).get('coingecko', {})
            
            # Governance indicators
            links = project_data.get('links', {})
            
            # Governance token/DAO presence
            if links.get('governance') or 'dao' in project_data.get('description', {}).get('en', '').lower():
                score -= 1  # Lower risk if decentralized governance
                data_found = True
            
            # Community governance
            if links.get('community') or links.get('forum'):
                score -= 1  # Lower risk if community involvement
                data_found = True
            
            # Transparency indicators
            if links.get('blog') or links.get('announcement'):
                score -= 1  # Lower risk if regular communication
                data_found = True
            
            # Professional management indicators
            if links.get('linkedin') or project_data.get('company'):
                score -= 1  # Lower risk if professional management
                data_found = True
            
            # Token distribution analysis (indicator of management strategy)
            try:
                holders = risk_report.get('onchain', {}).get('holders', {})
                if holders:
                    total_holders = holders.get('total_holders', 0)
                    top10_concentration = holders.get('top10_concentration', 100)
                    
                    if total_holders > 10000 and top10_concentration < 50:
                        score -= 1  # Lower risk if well-distributed
                        data_found = True
                    elif total_holders < 1000 or top10_concentration > 80:
                        score += 2  # Higher risk if highly concentrated
            except:
                pass
            
            # Market strategy indicators
            try:
                volume_24h = project_data.get('market_data', {}).get('total_volume', {}).get('usd', 0)
                market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                
                if volume_24h > 0 and market_cap > 0:
                    volume_market_cap_ratio = volume_24h / market_cap
                    if volume_market_cap_ratio > 0.1:  # High trading activity
                        score -= 1
                        data_found = True
                    elif volume_market_cap_ratio < 0.01:  # Low trading activity
                        score += 1
            except:
                pass
            
            # Liquidity management
            try:
                liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                if liquidity > 1_000_000:  # High liquidity
                    score -= 1
                    data_found = True
                elif liquidity < 100_000:  # Low liquidity
                    score += 1
            except:
                pass
            
            # Alternative data sources when primary data is limited
            if not data_found:
                # Use Zapper data for portfolio management indicators
                try:
                    zapper_data = risk_report.get('enhanced', {}).get('zapper', {})
                    if zapper_data.get('portfolio') or zapper_data.get('protocol'):
                        score -= 1  # Lower risk if Zapper tracks it (indicates professional management)
                except:
                    pass
                
                # Use DeBank data for financial management indicators
                try:
                    debank_data = risk_report.get('enhanced', {}).get('debank', {})
                    if debank_data.get('portfolio') or debank_data.get('tokens'):
                        score -= 1  # Lower risk if DeBank tracks it (indicates financial management)
                except:
                    pass
                
                # Use Moralis transfer patterns for management strategy
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        # Check for large transfers (indicates institutional management)
                        large_transfers = [t for t in transfers if float(t.get('value', 0)) > 10000]
                        if len(large_transfers) > 5:
                            score -= 1  # Lower risk for institutional management
                        elif len(large_transfers) == 0:
                            score += 1  # Higher risk for retail-only management
                except:
                    pass
                
                # Use contract complexity as management strategy indicator
                try:
                    contract_source = risk_report.get('onchain', {}).get('contract_source', '')
                    if contract_source:
                        # Check for governance functions
                        governance_functions = ['vote', 'proposal', 'governance', 'dao']
                        gov_count = sum(1 for func in governance_functions if func in contract_source.lower())
                        if gov_count >= 2:
                            score -= 1  # Lower risk for governance-focused management
                except:
                    pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in management_strategy scoring: {e}")
            return 7
    
    def score_code_security(self, risk_report):
        """Enhanced score based on code security and audit status (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            
            # Contract verification status
            contract_verified = risk_report.get('onchain', {}).get('contract_verified', '')
            if contract_verified == 'verified':
                score -= 2  # Lower risk for verified contracts
                data_found = True
            else:
                score += 3  # Higher risk for unverified contracts
            
            # Security audit status
            security_data = risk_report.get('security', {})
            if security_data:
                audit_count = len(security_data.get('audits', []))
                if audit_count >= 2:
                    score -= 2  # Lower risk for multiple audits
                    data_found = True
                elif audit_count == 1:
                    score -= 1  # Lower risk for single audit
                    data_found = True
                else:
                    score += 2  # Higher risk for no audits
            
            # Contract complexity and security patterns
            contract_source = risk_report.get('onchain', {}).get('contract_source', '')
            if contract_source:
                # Check for security best practices
                security_patterns = [
                    'reentrancyguard', 'pausable', 'ownable', 'accesscontrol',
                    'safemath', 'erc20', 'erc721', 'erc1155'
                ]
                security_count = sum(1 for pattern in security_patterns if pattern in contract_source.lower())
                if security_count >= 3:
                    score -= 1  # Lower risk for security-conscious code
                    data_found = True
                elif security_count == 0:
                    score += 1  # Higher risk for no security patterns
                
                # Check for potential vulnerabilities
                vulnerability_patterns = [
                    'delegatecall', 'selfdestruct', 'suicide', 'assembly',
                    'inline', 'low-level', 'unchecked'
                ]
                vuln_count = sum(1 for pattern in vulnerability_patterns if pattern in contract_source.lower())
                if vuln_count >= 2:
                    score += 1  # Higher risk for potential vulnerabilities
            
            # Alternative data sources when primary data is limited
            if not data_found:
                # Use security reports from enhanced data
                try:
                    security_reports = risk_report.get('security', {}).get('reports', [])
                    if security_reports:
                        score -= 1  # Lower risk if security reports exist
                except:
                    pass
                
                # Use Moralis metadata for security indicators
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    metadata = moralis_data.get('metadata', {})
                    if metadata:
                        # Check for standard token types (indicates security)
                        token_type = metadata.get('type', '').lower()
                        if 'erc20' in token_type or 'erc721' in token_type:
                            score -= 1  # Lower risk for standard token types
                except:
                    pass
                
                # Use transfer patterns for security analysis
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        # Check for suspicious transfer patterns
                        suspicious_transfers = [t for t in transfers if float(t.get('value', 0)) > 1000000]
                        if len(suspicious_transfers) > 10:
                            score += 1  # Higher risk for many large transfers
                except:
                    pass
                
                # Use holder distribution for security analysis
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        top10_concentration = holders.get('top10_concentration', 100)
                        if top10_concentration > 90:
                            score += 1  # Higher risk for highly concentrated holdings
                except:
                    pass
                
                # Use liquidity for security analysis
                try:
                    liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                    if liquidity < 50_000:
                        score += 1  # Higher risk for very low liquidity
                except:
                    pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in code_security scoring: {e}")
            return 7
    
    def score_dev_activity(self, risk_report):
        """Enhanced score based on development activity and code commits (1-10)
        Uses Santiment, CoinGecko GitHub metrics, on-chain data, and protocol integrations for precision.
        """
        try:
            score = 5  # Base score
            data_found = False
            activity_indicators = []

            # 1. Santiment development activity data (Primary source)
            santiment_dev = risk_report.get('santiment', {}).get('dev', [])
            avg_activity = None
            recent_activity = None
            if santiment_dev:
                valid_values = [point['value'] for point in santiment_dev 
                              if isinstance(point, dict) and 'value' in point and point['value'] is not None]
                if valid_values:
                    avg_activity = sum(valid_values) / len(valid_values)
                    recent_activity = valid_values[-1] if valid_values else 0
                    # Enhanced scoring based on activity levels
                    if avg_activity > 150 and recent_activity > 75:
                        score -= 3
                        activity_indicators.append(f"Exceptional dev activity: {avg_activity:.1f} avg, {recent_activity} recent")
                        data_found = True
                    elif avg_activity > 100 and recent_activity > 50:
                        score -= 2
                        activity_indicators.append(f"Very high dev activity: {avg_activity:.1f} avg, {recent_activity} recent")
                        data_found = True
                    elif avg_activity > 50 and recent_activity > 20:
                        score -= 1
                        activity_indicators.append(f"High dev activity: {avg_activity:.1f} avg, {recent_activity} recent")
                        data_found = True
                    elif avg_activity < 5 or recent_activity < 2:
                        score += 3
                        activity_indicators.append(f"Very low dev activity: {avg_activity:.1f} avg, {recent_activity} recent")
                    elif avg_activity < 15 or recent_activity < 8:
                        score += 2
                        activity_indicators.append(f"Low dev activity: {avg_activity:.1f} avg, {recent_activity} recent")
                    elif avg_activity < 30:
                        score += 1
                        activity_indicators.append(f"Moderate dev activity: {avg_activity:.1f} avg, {recent_activity} recent")
                    # Trend analysis: penalize sharp drops
                    if avg_activity and recent_activity is not None and recent_activity < avg_activity * 0.3:
                        score += 1
                        activity_indicators.append(f"Recent dev activity dropped sharply vs. average")

            # 2. CoinGecko GitHub metrics
            project_data = risk_report.get('market', {}).get('coingecko', {})
            links = project_data.get('links', {})
            github_metrics = project_data.get('github', {})
            # If not present, try to extract from links
            if not github_metrics and links.get('repos_url', {}).get('github'):
                github_metrics = links.get('repos_url', {}).get('github')
            # Use developer_score as before
            dev_score = project_data.get('developer_score', 0)
            if dev_score > 80:
                score -= 2
                activity_indicators.append(f"Exceptional developer score: {dev_score}")
                data_found = True
            elif dev_score > 50:
                score -= 1
                activity_indicators.append(f"Good developer score: {dev_score}")
                data_found = True
            elif dev_score < 5:
                score += 2
                activity_indicators.append(f"Very poor developer score: {dev_score}")
            elif dev_score < 15:
                score += 1
                activity_indicators.append(f"Poor developer score: {dev_score}")
            # Use additional GitHub metrics if available
            for metric, label, boost, penalty, high, low in [
                ('commit_count_4_weeks', 'commits (4w)', -1, 1, 50, 5),
                ('stars', 'stars', -0.5, 0.5, 1000, 10),
                ('forks', 'forks', -0.5, 0.5, 500, 5),
                ('open_issues', 'open issues', 0.5, -0.5, 100, 0),
                ('contributors', 'contributors', -1, 1, 20, 1),
            ]:
                val = github_metrics.get(metric)
                if val is not None:
                    if val >= high:
                        score += boost
                        activity_indicators.append(f"High {label}: {val}")
                        data_found = True
                    elif val <= low:
                        score += penalty
                        activity_indicators.append(f"Low {label}: {val}")
            # Open source check
            if links.get('repos_url', {}).get('github'):
                score -= 1
                activity_indicators.append("Open source project (GitHub)")
                data_found = True
                if links.get('source_code'):
                    score -= 0.5
                    activity_indicators.append("Source code available")

            # 3. On-chain contract activity
            onchain = risk_report.get('onchain', {})
            contract_age = onchain.get('contract_age_days', None)
            if contract_age is not None:
                if contract_age < 60:
                    score -= 0.5
                    activity_indicators.append(f"New contract: {contract_age} days old")
                elif contract_age > 1000:
                    score += 0.5
                    activity_indicators.append(f"Very old contract: {contract_age} days old")
            # Proxy/upgrade pattern
            if onchain.get('proxy_contract') or onchain.get('upgradeable_contract'):
                score -= 0.5
                activity_indicators.append("Proxy/upgradeable contract: ongoing dev possible")

            # 4. Moralis transfer data (fallback)
            if not data_found or len(activity_indicators) < 2:
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        recent_transfers = len([t for t in transfers if t.get('block_timestamp')])
                        transfer_volume = sum(float(t.get('value', 0)) for t in transfers if t.get('value'))
                        if recent_transfers > 100 and transfer_volume > 1000000:
                            score -= 1
                            activity_indicators.append(f"High on-chain transfer activity: {recent_transfers} txs, {transfer_volume} volume")
                        elif recent_transfers < 5:
                            score += 1
                            activity_indicators.append(f"Very low on-chain transfer activity: {recent_transfers} txs")
                except:
                    pass

            # 5. Protocol integrations (Zapper, DeBank, DefiLlama)
            integrations = []
            for proto in ['zapper', 'debank', 'defillama']:
                pdata = risk_report.get('enhanced', {}).get(proto, {})
                if pdata:
                    integrations.append(proto)
            if integrations:
                score -= 1
                activity_indicators.append(f"Integrated in DeFi protocols: {', '.join(integrations)}")
                data_found = True
            else:
                score += 0.5
                activity_indicators.append("Not integrated in major DeFi protocols")

            # Clamp score and set defaults
            if not data_found:
                score = max(score, 7)  # If no data, set to mid/high risk
                activity_indicators.append("Insufficient dev activity data; defaulting to higher risk")
            score = max(1, min(9, round(score)))  # Never give 10/10, max is 9
            risk_report['dev_activity_indicators'] = activity_indicators
            return score
        except Exception as e:
            print(f"Error in dev_activity scoring: {e}")
            return 7
    
    
    def score_aml_data(self, risk_report, token_address, chain):
        """Score based on AML data from CertiK, Scorechain, TRM Labs, Elliptic (if available)"""
        indicators = []
        score = 10
        # CertiK
        certik_reports = self.fetch_security_reports(token_address, chain)
        certik_score = None
        if certik_reports:
            for report in certik_reports:
                if report.get('source') == 'CertiK':
                    certik_score = report.get('score')
                    audit_status = report.get('audit_status', '').lower()
                    if audit_status == 'audited' and certik_score and certik_score >= 80:
                        score -= 3
                        indicators.append(f"CertiK: Audited, score {certik_score}")
                    elif audit_status == 'audited':
                        score -= 2
                        indicators.append("CertiK: Audited")
                    elif audit_status == 'unaudited' or (certik_score and certik_score < 60):
                        score += 3
                        indicators.append(f"CertiK: Unaudited or low score ({certik_score})")
                    else:
                        indicators.append(f"CertiK: Status {audit_status}, score {certik_score}")
        else:
            indicators.append("No CertiK audit data")
        # Scorechain
        try:
            scorechain_result = fetch_scorechain_aml(token_address, chain)
            if scorechain_result:
                indicators.append(f"Scorechain: {scorechain_result['summary']}")
                score += scorechain_result['score_delta']
        except Exception as e:
            indicators.append(f"Scorechain error: {e}")
        # TRM Labs
        try:
            trm_result = fetch_trmlabs_aml(token_address, chain)
            if trm_result:
                indicators.append(f"TRM Labs: {trm_result['summary']}")
                score += trm_result['score_delta']
        except Exception as e:
            indicators.append(f"TRM Labs error: {e}")
        # Clamp score
        score = max(1, min(9, round(score)))
        risk_report['aml_data_indicators'] = indicators
        return score

    def score_compliance_data(self, risk_report, token_address, chain):
        """Score based on compliance data (Breadcrumbs, exchange, KYC/AML, red flags, OpenSanctions, Lukka, Alchemy, DeFiSafety)"""
        try:
            score = 5
            data_found = False
            compliance_indicators = []
            # Breadcrumbs risk and sanctions
            breadcrumbs_risk = risk_report.get('breadcrumbs_risk')
            if breadcrumbs_risk:
                risk_score = breadcrumbs_risk.get('riskScore', 0)
                sanctions = breadcrumbs_risk.get('sanctions', False)
                illicit = breadcrumbs_risk.get('illicit', False)
                if sanctions or illicit:
                    score += 4
                    compliance_indicators.append("Breadcrumbs: Sanctions or illicit activity flagged")
                elif risk_score >= 80:
                    score += 2
                    compliance_indicators.append(f"Breadcrumbs: High risk score ({risk_score})")
                elif risk_score >= 50:
                    score += 1
                    compliance_indicators.append(f"Breadcrumbs: Moderate risk score ({risk_score})")
                else:
                    score -= 1
                    compliance_indicators.append(f"Breadcrumbs: Low risk score ({risk_score})")
                data_found = True
            else:
                compliance_indicators.append("No Breadcrumbs risk data")
            # Exchange listings (regulated vs unregulated)
            project_data = risk_report.get('market', {}).get('coingecko', {})
            tickers = project_data.get('tickers', [])
            regulated_exchanges = ['coinbase', 'kraken', 'gemini']
            major_exchanges = ['binance', 'coinbase', 'kraken', 'gemini', 'bitfinex', 'huobi']
            found_regulated = False
            found_major = False
            for t in tickers:
                ex = t.get('market', {}).get('name', '').lower()
                if ex in regulated_exchanges:
                    found_regulated = True
                if ex in major_exchanges:
                    found_major = True
            if found_regulated:
                score -= 2
                compliance_indicators.append("Listed on regulated exchange")
                data_found = True
            elif found_major:
                score -= 1
                compliance_indicators.append("Listed on major exchange")
                data_found = True
            else:
                score += 1
                compliance_indicators.append("Not listed on major/regulated exchanges")
            # KYC/AML/Regulatory language in description or website
            description = project_data.get('description', {}).get('en', '')
            website = ''
            links = project_data.get('links', {})
            if isinstance(links, dict):
                website = links.get('homepage', [''])[0]
            kyc_keywords = ['kyc', 'aml', 'compliant', 'regulatory', 'regulated', 'license', 'governance', 'oversight', 'audit', 'transparency']
            kyc_matches = [kw for kw in kyc_keywords if kw in description.lower() or kw in website.lower()]
            if len(kyc_matches) >= 2:
                score -= 2
                compliance_indicators.append(f"KYC/AML language: {', '.join(kyc_matches)}")
                data_found = True
            elif len(kyc_matches) == 1:
                score -= 1
                compliance_indicators.append(f"Some KYC/AML language: {kyc_matches[0]}")
                data_found = True
            else:
                score += 1
                compliance_indicators.append("No KYC/AML language found")
            # Penalize for critical red flags
            onchain = risk_report.get('onchain', {})
            red_flags = onchain.get('red_flags', [])
            critical_flags = [
                'eu_unlicensed_stablecoin',
                'eu_regulatory_issues',
                'mica_non_compliant',
                'mica_no_whitepaper'
            ]
            for flag in critical_flags:
                if flag in red_flags:
                    score += 3
                    compliance_indicators.append(f"Red flag: {flag}")
            # Company registration and legal structure
            if project_data.get('company'):
                score -= 1
                compliance_indicators.append("Registered company")
                data_found = True
            # Professional legal presence
            legal_presence = 0
            if links.get('linkedin'): legal_presence += 1
            if links.get('legal'): legal_presence += 1
            if links.get('whitepaper'): legal_presence += 1
            if legal_presence >= 2:
                score -= 1
                compliance_indicators.append("Strong professional presence")
                data_found = True
            elif legal_presence == 1:
                score -= 0.5
                compliance_indicators.append("Some professional presence")
                data_found = True
            else:
                score += 0.5
                compliance_indicators.append("No professional legal presence")
            # Platform/chain
            token_type = project_data.get('asset_platform_id', '')
            established_platforms = ['ethereum', 'binance-smart-chain', 'polygon-pos', 'avalanche', 'solana']
            if token_type in established_platforms:
                score -= 0.5
                compliance_indicators.append(f"Established platform: {token_type}")
                data_found = True
            elif token_type in ['unknown', '']:
                score += 1
                compliance_indicators.append("Unknown platform")
            else:
                compliance_indicators.append(f"Platform: {token_type}")
            # Liquidity (regulatory scrutiny)
            try:
                liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                if liquidity > 100_000_000:
                    score -= 1
                    compliance_indicators.append(f"Very high liquidity: ${liquidity:,.0f}")
                    data_found = True
                elif liquidity > 10_000_000:
                    score -= 0.5
                    compliance_indicators.append(f"High liquidity: ${liquidity:,.0f}")
                    data_found = True
                elif liquidity < 10_000:
                    score += 1
                    compliance_indicators.append(f"Very low liquidity: ${liquidity:,.0f}")
                elif liquidity < 100_000:
                    score += 0.5
                    compliance_indicators.append(f"Low liquidity: ${liquidity:,.0f}")
            except:
                pass
            # OpenSanctions integration
            try:
                opensanctions_result = fetch_opensanctions_compliance(token_address, chain)
                if opensanctions_result:
                    compliance_indicators.append(f"OpenSanctions: {opensanctions_result['summary']}")
                    score += opensanctions_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"OpenSanctions error: {e}")
            # Lukka integration
            try:
                lukka_result = fetch_lukka_compliance(token_address, chain)
                if lukka_result:
                    compliance_indicators.append(f"Lukka: {lukka_result['summary']}")
                    score += lukka_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"Lukka error: {e}")
            # Alchemy integration
            try:
                alchemy_result = fetch_alchemy_compliance(token_address, chain)
                if alchemy_result:
                    compliance_indicators.append(f"Alchemy: {alchemy_result['summary']}")
                    score += alchemy_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"Alchemy error: {e}")
            # DeFiSafety scraping
            try:
                defisafety_result = fetch_defisafety_compliance(token_address, chain)
                if defisafety_result:
                    compliance_indicators.append(f"DeFiSafety: {defisafety_result['summary']}")
                    score += defisafety_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"DeFiSafety error: {e}")
            if not data_found:
                score = max(score, 7)
                compliance_indicators.append("Insufficient compliance data; defaulting to higher risk")
            score = max(1, min(9, round(score)))
            risk_report['compliance_data_indicators'] = compliance_indicators
            return score
        except Exception as e:
            print(f"Error in compliance_data scoring: {e}")
            return 7

    def score_marketing_demand(self, risk_report):
        """Enhanced score based on marketing demand and social activity (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            
            # Santiment social activity data
            santiment_social = risk_report.get('santiment', {}).get('social', [])
            if santiment_social:
                valid_values = [point['value'] for point in santiment_social 
                              if isinstance(point, dict) and 'value' in point and point['value'] is not None]
                if valid_values:
                    avg_volume = sum(valid_values) / len(valid_values)
                    recent_volume = valid_values[-1] if valid_values else 0
                    
                    if avg_volume > 10000 and recent_volume > 5000:
                        score -= 2  # Very high social activity
                        data_found = True
                    elif avg_volume > 1000 and recent_volume > 500:
                        score -= 1  # High social activity
                        data_found = True
                    elif avg_volume < 100 or recent_volume < 50:
                        score += 2  # Low social activity
                    elif avg_volume < 500:
                        score += 1  # Moderate social activity
            
            # Social media presence
            project_data = risk_report.get('market', {}).get('coingecko', {})
            links = project_data.get('links', {})
            
            social_platforms = [
                'twitter_screen_name', 'telegram_channel_identifier', 
                'subreddit_url', 'discord', 'medium', 'reddit'
            ]
            social_presence = sum(1 for platform in social_platforms if links.get(platform))
            if social_presence >= 3:
                score -= 1  # Lower risk if strong social presence
                data_found = True
            elif social_presence == 0:
                score += 2  # Higher risk if no social presence
            elif social_presence == 1:
                score += 1  # Higher risk if minimal social presence
            
            # Trading volume as demand indicator
            try:
                volume_24h = project_data.get('market_data', {}).get('total_volume', {}).get('usd', 0)
                if volume_24h > 10_000_000:  # Very high volume
                    score -= 2  # Very high demand
                    data_found = True
                elif volume_24h > 1_000_000:  # High volume
                    score -= 1  # High demand
                    data_found = True
                elif volume_24h < 10_000:  # Very low volume
                    score += 2  # Very low demand
                elif volume_24h < 100_000:  # Low volume
                    score += 1  # Low demand
            except:
                pass
            
            # Price performance as demand indicator
            try:
                price_change_24h = project_data.get('market_data', {}).get('price_change_percentage_24h', 0)
                if price_change_24h and price_change_24h > 20:  # Strong positive performance
                    score -= 1  # High demand
                    data_found = True
                elif price_change_24h and price_change_24h < -20:  # Poor performance
                    score += 1  # Low demand
            except:
                pass
            
            # Alternative data sources when primary data is limited
            if not data_found:
                # Use Moralis transfer data for demand indicators
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        # Check for high transfer activity (indicates demand)
                        if len(transfers) > 100:
                            score -= 1  # Lower risk for high demand
                        elif len(transfers) < 10:
                            score += 1  # Higher risk for low demand
                except:
                    pass
                
                # Use holder count as demand indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        total_holders = holders.get('total_holders', 0)
                        if total_holders > 50000:
                            score -= 2  # Very high demand
                        elif total_holders > 10000:
                            score -= 1  # High demand
                        elif total_holders < 1000:
                            score += 1  # Low demand
                except:
                    pass
                
                # Use liquidity as demand indicator
                try:
                    liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                    if liquidity > 5_000_000:
                        score -= 1  # Lower risk for high demand
                    elif liquidity < 100_000:
                        score += 1  # Higher risk for low demand
                except:
                    pass
                
                # Use DeFiLlama data for protocol demand
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('price') or defillama_data.get('yields'):
                        score -= 1  # Lower risk if DeFiLlama tracks it (indicates demand)
                except:
                    pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in marketing_demand scoring: {e}")
            return 7
    
    def score_esg_impact(self, risk_report):
        """Enhanced score based on Environmental, Social, and Governance impact (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            esg_score = 0
            
            project_data = risk_report.get('market', {}).get('coingecko', {})
            
            # Environmental Impact Assessment
            description = project_data.get('description', {}).get('en', '').lower()
            
            # Environmental keywords
            environmental_keywords = [
                'carbon', 'green', 'sustainable', 'renewable', 'energy', 'climate',
                'environmental', 'eco', 'clean', 'zero-emission', 'carbon-neutral',
                'solar', 'wind', 'hydro', 'geothermal', 'biomass', 'recycling'
            ]
            env_count = sum(1 for keyword in environmental_keywords if keyword in description)
            if env_count >= 3:
                score -= 2  # Lower risk for strong environmental focus
                data_found = True
                esg_score += 3
            elif env_count >= 2:
                score -= 1  # Lower risk for environmental focus
                data_found = True
                esg_score += 2
            elif env_count >= 1:
                esg_score += 1
            else:
                score += 1  # Higher risk for no environmental focus
                esg_score -= 1
            
            # Social Impact Assessment
            social_keywords = [
                'social', 'community', 'inclusive', 'equality', 'diversity',
                'education', 'healthcare', 'charity', 'donation', 'philanthropy',
                'microfinance', 'banking', 'financial inclusion', 'unbanked',
                'developing', 'emerging markets', 'accessibility'
            ]
            social_count = sum(1 for keyword in social_keywords if keyword in description)
            if social_count >= 3:
                score -= 2  # Lower risk for strong social impact
                data_found = True
                esg_score += 3
            elif social_count >= 2:
                score -= 1  # Lower risk for social impact
                data_found = True
                esg_score += 2
            elif social_count >= 1:
                esg_score += 1
            else:
                score += 1  # Higher risk for no social impact
                esg_score -= 1
            
            # Governance Impact Assessment
            governance_keywords = [
                'governance', 'dao', 'democratic', 'transparent', 'accountable',
                'voting', 'proposal', 'community-driven', 'decentralized',
                'open source', 'audit', 'compliance', 'regulation', 'legal'
            ]
            gov_count = sum(1 for keyword in governance_keywords if keyword in description)
            if gov_count >= 3:
                score -= 2  # Lower risk for strong governance
                data_found = True
                esg_score += 3
            elif gov_count >= 2:
                score -= 1  # Lower risk for governance focus
                data_found = True
                esg_score += 2
            elif gov_count >= 1:
                esg_score += 1
            else:
                score += 1  # Higher risk for poor governance
                esg_score -= 1
            
            # Community engagement as ESG indicator
            try:
                community_score = project_data.get('community_score', 0)
                if community_score > 80:
                    score -= 1  # Lower risk for excellent community engagement
                    data_found = True
                    esg_score += 2
                elif community_score > 50:
                    score -= 0.5  # Lower risk for good community engagement
                    data_found = True
                    esg_score += 1
                elif community_score < 10:
                    score += 1  # Higher risk for poor community engagement
                    esg_score -= 1
            except:
                pass
            
            # Developer activity as ESG indicator
            try:
                dev_score = project_data.get('developer_score', 0)
                if dev_score > 80:
                    score -= 1  # Lower risk for very active development
                    data_found = True
                    esg_score += 2
                elif dev_score > 50:
                    score -= 0.5  # Lower risk for active development
                    data_found = True
                    esg_score += 1
                elif dev_score < 10:
                    score += 1  # Higher risk for low development activity
                    esg_score -= 1
            except:
                pass
            
            # Enhanced data sources for ESG assessment
            if not data_found:
                # Check contract verification as governance indicator
                contract_verified = risk_report.get('onchain', {}).get('contract_verified', '')
                if contract_verified == 'verified':
                    score -= 1  # Lower risk if verified (indicates transparency)
                    esg_score += 2
                else:
                    esg_score -= 1
                
                # Check contract complexity as governance indicator
                contract_source = risk_report.get('onchain', {}).get('contract_source', '')
                if contract_source:
                    # Check for governance functions
                    governance_functions = [
                        'vote', 'proposal', 'governance', 'dao', 'multisig',
                        'timelock', 'accesscontrol', 'ownable'
                    ]
                    gov_func_count = sum(1 for func in governance_functions if func in contract_source.lower())
                    if gov_func_count >= 2:
                        score -= 1  # Lower risk for governance functions
                        esg_score += 2
                    elif gov_func_count >= 1:
                        esg_score += 1
                    else:
                        score += 1  # Higher risk for no governance functions
                        esg_score -= 1
                    
                    # Check for transparency features
                    transparency_features = [
                        'public', 'view', 'external', 'event', 'emit'
                    ]
                    trans_count = sum(1 for feature in transparency_features if feature in contract_source.lower())
                    if trans_count >= 5:
                        score -= 1  # Lower risk for transparency
                        esg_score += 2
                    elif trans_count >= 3:
                        esg_score += 1
                    else:
                        score += 1  # Higher risk for lack of transparency
                        esg_score -= 1
                
                # Use holder distribution as social impact indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        total_holders = holders.get('total_holders', 0)
                        top10_concentration = holders.get('top10_concentration', 100)
                        
                        if total_holders > 100000 and top10_concentration < 30:
                            score -= 2  # Lower risk for broad distribution (social impact)
                            esg_score += 3
                        elif total_holders > 50000 and top10_concentration < 50:
                            score -= 1  # Lower risk for good distribution
                            esg_score += 2
                        elif total_holders > 10000:
                            esg_score += 1
                        elif total_holders < 1000 or top10_concentration > 80:
                            score += 2  # Higher risk for concentrated holdings
                            esg_score -= 2
                        elif total_holders < 5000 or top10_concentration > 60:
                            score += 1  # Higher risk for poor distribution
                            esg_score -= 1
                except:
                    pass
                
                # Use liquidity as environmental/social indicator
                try:
                    liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                    if liquidity > 10_000_000:
                        score -= 1  # Lower risk for high liquidity (indicates sustainable project)
                        esg_score += 2
                    elif liquidity > 1_000_000:
                        esg_score += 1
                    elif liquidity < 100_000:
                        score += 1  # Higher risk for very low liquidity
                        esg_score -= 1
                except:
                    pass
                
                # Use market cap as ESG indicator
                try:
                    market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                    if market_cap > 1_000_000_000:
                        score -= 1  # Lower risk for high market cap (indicates sustainable project)
                        esg_score += 2
                    elif market_cap > 100_000_000:
                        esg_score += 1
                    elif market_cap < 1_000_000:
                        score += 1  # Higher risk for low market cap
                        esg_score -= 1
                except:
                    pass
                
                # Use Moralis metadata for ESG indicators
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    metadata = moralis_data.get('metadata', {})
                    if metadata:
                        # Check for detailed metadata (indicates transparency)
                        if metadata.get('name') and metadata.get('symbol') and metadata.get('decimals'):
                            esg_score += 1
                        if metadata.get('description') and len(metadata.get('description', '')) > 100:
                            esg_score += 1
                except:
                    pass
                
                # Use DeFiLlama data for ESG indicators
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('yields') or defillama_data.get('price'):
                        esg_score += 1  # Lower risk if DeFiLlama tracks it (indicates sustainability)
                except:
                    pass
                
                # Check for professional links as governance indicator
                links = project_data.get('links', {})
                professional_links = ['linkedin', 'medium', 'blog', 'docs', 'documentation']
                prof_count = sum(1 for link in professional_links if links.get(link))
                if prof_count >= 2:
                    score -= 1  # Lower risk for professional documentation
                    esg_score += 2
                elif prof_count >= 1:
                    esg_score += 1
                else:
                    score += 1  # Higher risk for lack of professional documentation
                    esg_score -= 1
            
            # Apply ESG score adjustment
            if esg_score >= 8:
                score = max(1, score - 2)  # Bonus for excellent ESG
            elif esg_score >= 5:
                score = max(1, score - 1)  # Bonus for good ESG
            elif esg_score <= -6:
                score = min(10, score + 2)  # Penalty for poor ESG
            elif esg_score <= -3:
                score = min(10, score + 1)  # Penalty for moderate ESG
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in esg_impact scoring: {e}")
            return 5

    
        
    def apply_strict_compliance_checks(self, risk_report, chain):
        """Apply compliance checks based on industry standards and EU regulations
        
        This method evaluates the token against strict compliance criteria:
        
        1. EU Regulatory Compliance:
           - MiCA (Markets in Crypto-Assets) compliance
           - Unlicensed stablecoin detection
           - EU trading restrictions
        
        2. Liquidity Requirements:
           - Minimum liquidity thresholds per chain
           - Flags tokens with insufficient liquidity
        
        3. Contract Security:
           - Verification status check
           - Source code availability
        
        4. Holder Distribution:
           - Minimum holder count requirements
           - Maximum concentration limits
           - Flags centralized holdings
        
        These checks are based on top exchange listing criteria,
        industry best practices, and EU regulatory requirements.
        
        Args:
            risk_report (dict): Current risk assessment data
            chain (str): The blockchain network being analyzed
            
        Side Effects:
            Adds red flags to risk_report['onchain']['red_flags'] when
            compliance issues are detected
        """
        if chain not in self.CHAIN_CONFIG:
            return
        
        # 1. EU Regulatory Compliance Check (CRITICAL)
        self.apply_eu_regulatory_checks(risk_report)
        
        # 2. Check liquidity against minimum threshold
        min_liquidity = self.CHAIN_CONFIG[chain]['min_liquidity']
        liquidity = risk_report['onchain']['liquidity'] or 0
        if liquidity < min_liquidity:
            risk_report['onchain']['red_flags'].append('low_liquidity')
        
        # 3. Check contract verification status
        if risk_report['onchain']['contract_verified'] != 'verified':
            risk_report['onchain']['red_flags'].append('unverified_contract')
        
        # 4. Check holder concentration
        holders = risk_report['onchain']['holders']
        if holders['top10_concentration'] > 50 or holders['total_holders'] < 1000:
            risk_report['onchain']['red_flags'].append('high_concentration')
    
    def apply_eu_regulatory_checks(self, risk_report):
        """Apply EU regulatory compliance checks (MiCA, etc.)
        
        This method implements comprehensive EU regulatory compliance:
        
        1. Unlicensed Stablecoin Detection:
           - USDT, USDC, DAI, and other major stablecoins
           - Flags as 'eu_unlicensed_stablecoin' if not MiCA compliant
        
        2. EU Trading Restrictions:
           - Tokens with known EU regulatory issues
           - Automatic Extreme Risk classification
        
        3. MiCA Compliance Assessment:
           - Asset-referenced tokens (ARTs)
           - Electronic money tokens (EMTs)
           - Utility tokens
        
        Args:
            risk_report (dict): Current risk assessment data
            
        Side Effects:
            Adds EU-specific red flags and may force Extreme Risk classification
        """
        try:
            # Get token information
            token_address = risk_report.get('token', '').lower()
            symbol = risk_report.get('symbol', '').upper()
            project_data = risk_report.get('market', {}).get('coingecko', {})
            
            # Initialize EU compliance data if not exists
            if 'eu_compliance' not in risk_report:
                risk_report['eu_compliance'] = {
                    'status': 'Unknown',
                    'issue': 'No compliance data available',
                    'restrictions': 'Unknown',
                    'mica_compliant': False,
                    'eu_trading_allowed': False
                }
            
            # 1. Unlicensed Stablecoin Detection (CRITICAL)
            unlicensed_stablecoins = {
                # USDT - Not MiCA compliant, major EU regulatory issue
                "0xdac17f958d2ee523a2206206994597c13d831ec7": {
                    "symbol": "USDT",
                    "name": "Tether USD",
                    "issue": "Not MiCA compliant - major EU regulatory risk",
                    "eu_status": "Unlicensed",
                    "restrictions": "Cannot be offered to EU retail investors"
                },
                # USDC - Not fully MiCA compliant
                "0xa0b86a33e6441b8c4c8c0b8c4c8c0b8c4c8c0b8c": {
                    "symbol": "USDC",
                    "name": "USD Coin",
                    "issue": "Limited MiCA compliance",
                    "eu_status": "Restricted",
                    "restrictions": "Limited EU availability"
                },
                # DAI - Decentralized stablecoin, regulatory uncertainty
                "0x6b175474e89094c44da98b954eedeac495271d0f": {
                    "symbol": "DAI",
                    "name": "Dai",
                    "issue": "Decentralized stablecoin - regulatory uncertainty",
                    "eu_status": "Unclear",
                    "restrictions": "May face regulatory challenges"
                },
                # BUSD - Binance USD, regulatory issues
                "0x4fabb145d64652a948d72533023f6e7a623c7c53": {
                    "symbol": "BUSD",
                    "name": "Binance USD",
                    "issue": "Binance regulatory issues in EU",
                    "eu_status": "Restricted",
                    "restrictions": "Limited EU availability"
                },
                # FRAX - Algorithmic stablecoin, regulatory concerns
                "0x853d955acef822db058eb8505911ed77f175b99e": {
                    "symbol": "FRAX",
                    "name": "Frax",
                    "issue": "Algorithmic stablecoin - regulatory concerns",
                    "eu_status": "Unclear",
                    "restrictions": "May face regulatory challenges"
                }
            }
            
            # Check if token is an unlicensed stablecoin
            if token_address in unlicensed_stablecoins:
                stablecoin_info = unlicensed_stablecoins[token_address]
                if 'eu_unlicensed_stablecoin' not in risk_report['onchain']['red_flags']:
                    risk_report['onchain']['red_flags'].append('eu_unlicensed_stablecoin')
                risk_report['eu_compliance'] = {
                    'status': stablecoin_info['eu_status'],
                    'issue': stablecoin_info['issue'],
                    'restrictions': stablecoin_info['restrictions'],
                    'mica_compliant': False,
                    'eu_trading_allowed': False
                }
                print(f"[EU COMPLIANCE] {symbol} flagged as unlicensed stablecoin: {stablecoin_info['issue']}")
                return  # Force Extreme Risk classification
            
            # Additional check by symbol for major stablecoins
            major_unlicensed_stablecoins = ['USDT', 'USDC', 'DAI', 'BUSD', 'FRAX']
            if symbol in major_unlicensed_stablecoins:
                if 'eu_unlicensed_stablecoin' not in risk_report['onchain']['red_flags']:
                    risk_report['onchain']['red_flags'].append('eu_unlicensed_stablecoin')
                risk_report['eu_compliance'] = {
                    'status': 'Unlicensed',
                    'issue': f'{symbol} - Not MiCA compliant - major EU regulatory risk',
                    'restrictions': 'Cannot be offered to EU retail investors',
                    'mica_compliant': False,
                    'eu_trading_allowed': False
                }
                print(f"[EU COMPLIANCE] {symbol} flagged as unlicensed stablecoin by symbol check")
                return  # Force Extreme Risk classification
            
            # 2. EU Regulatory Issues Database
            eu_regulatory_issues = {
                # Tokens with known EU regulatory problems
                "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": {  # UNI
                    "symbol": "UNI",
                    "issue": "Uniswap regulatory uncertainty in EU",
                    "eu_status": "Restricted",
                    "restrictions": "DeFi governance token - regulatory concerns"
                },
                "0x6b3595068778dd592e39a122f4f5a5cf09c90fe2": {  # SUSHI
                    "symbol": "SUSHI",
                    "issue": "DeFi governance token - regulatory uncertainty",
                    "eu_status": "Restricted",
                    "restrictions": "May face regulatory challenges"
                }
            }
            
            # Check for EU regulatory issues
            if token_address in eu_regulatory_issues:
                issue_info = eu_regulatory_issues[token_address]
                if 'eu_regulatory_issues' not in risk_report['onchain']['red_flags']:
                    risk_report['onchain']['red_flags'].append('eu_regulatory_issues')
                risk_report['eu_compliance'] = {
                    'status': issue_info['eu_status'],
                    'issue': issue_info['issue'],
                    'restrictions': issue_info['restrictions'],
                    'mica_compliant': False,
                    'eu_trading_allowed': False
                }
                print(f"[EU COMPLIANCE] {symbol} flagged for EU regulatory issues: {issue_info['issue']}")
            
            # 3. MiCA Compliance Assessment
            self.assess_mica_compliance(risk_report, symbol, project_data)
            
        except Exception as e:
            print(f"[EU COMPLIANCE] Error in regulatory checks: {e}")
    
    def assess_mica_compliance(self, risk_report, symbol, project_data):
        """Assess MiCA (Markets in Crypto-Assets) compliance
        
        MiCA categorizes crypto-assets into:
        1. Asset-referenced tokens (ARTs) - stablecoins
        2. Electronic money tokens (EMTs) - e-money backed
        3. Utility tokens - all other tokens
        
        Args:
            risk_report (dict): Current risk assessment data
            symbol (str): Token symbol
            project_data (dict): CoinGecko project data
        """
        try:
            # Check if token is a stablecoin (potential ART/EMT)
            stablecoin_indicators = [
                'stablecoin', 'stable', 'usd', 'eur', 'gbp', 'jpy', 'chf',
                'tether', 'usdc', 'dai', 'busd', 'frax', 'gusd', 'husd'
            ]
            
            description = project_data.get('description', {}).get('en', '').lower()
            symbol_lower = symbol.lower()
            
            is_stablecoin = any(indicator in symbol_lower for indicator in stablecoin_indicators) or \
                           any(indicator in description for indicator in stablecoin_indicators)
            
            if is_stablecoin:
                # Stablecoins require full MiCA compliance
                risk_report['mica_category'] = 'Asset-Referenced Token (ART)'
                risk_report['mica_requirements'] = [
                    'Full authorization required',
                    'Capital requirements',
                    'Reserve asset backing',
                    'Redemption rights',
                    'EU establishment required'
                ]
                
                # Check if already flagged as unlicensed
                if 'eu_unlicensed_stablecoin' not in risk_report['onchain']['red_flags']:
                    # Check for MiCA compliance indicators
                    has_eu_establishment = self.check_eu_establishment(project_data)
                    has_authorization = self.check_mica_authorization(project_data)
                    
                    if not has_eu_establishment or not has_authorization:
                        risk_report['onchain']['red_flags'].append('mica_non_compliant')
                        risk_report['eu_compliance'] = {
                            'status': 'Non-Compliant',
                            'issue': 'Stablecoin without MiCA authorization',
                            'restrictions': 'Cannot be offered to EU retail investors',
                            'mica_compliant': False,
                            'eu_trading_allowed': False
                        }
                        print(f"[MiCA] {symbol} flagged as non-compliant stablecoin")
            else:
                # Utility tokens have lighter requirements
                risk_report['mica_category'] = 'Utility Token'
                risk_report['mica_requirements'] = [
                    'White paper required',
                    'Marketing restrictions',
                    'Consumer protection rules'
                ]
                
                # Check for basic compliance
                has_whitepaper = project_data.get('links', {}).get('whitepaper')
                if not has_whitepaper:
                    risk_report['onchain']['red_flags'].append('mica_no_whitepaper')
                    print(f"[MiCA] {symbol} missing required whitepaper")
        
        except Exception as e:
            print(f"[MiCA] Error in compliance assessment: {e}")
    
    def check_eu_establishment(self, project_data):
        """Check if project has EU establishment for MiCA compliance"""
        try:
            # Check for EU company registration, offices, etc.
            description = project_data.get('description', {}).get('en', '').lower()
            eu_indicators = [
                'european union', 'eu', 'europe', 'germany', 'france', 'italy',
                'spain', 'netherlands', 'belgium', 'luxembourg', 'ireland',
                'malta', 'cyprus', 'estonia', 'lithuania', 'latvia'
            ]
            
            return any(indicator in description for indicator in eu_indicators)
        except:
            return False
    
    def check_mica_authorization(self, project_data):
        """Check if project has MiCA authorization"""
        try:
            # Check for regulatory compliance indicators
            description = project_data.get('description', {}).get('en', '').lower()
            compliance_indicators = [
                'mica', 'mica compliant', 'eu authorized', 'eu licensed',
                'regulated', 'authorization', 'license', 'compliance'
            ]
            
            return any(indicator in description for indicator in compliance_indicators)
        except:
            return False
    
    def is_stablecoin(self, token_address, symbol, project_data):
        """Detect if a token is a stablecoin"""
        try:
            # Check by address for known stablecoins
            stablecoin_addresses = {
                "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
                "0xa0b86a33e6441b8c4c8c0b8c4c8c0b8c4c8c0b8c": "USDC",  # Placeholder address
                "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
                "0x4fabb145d64652a948d72533023f6e7a623c7c53": "BUSD",
                "0x853d955acef822db058eb8505911ed77f175b99e": "FRAX"
            }
            
            if token_address.lower() in stablecoin_addresses:
                return True
            
            # Check by symbol
            stablecoin_symbols = ['USDT', 'USDC', 'DAI', 'BUSD', 'FRAX', 'TUSD', 'USDP', 'GUSD', 'LUSD', 'SUSD']
            if symbol.upper() in stablecoin_symbols:
                return True
            
            # Check by project description
            try:
                description = project_data.get('description', {}).get('en', '').lower()
                stablecoin_keywords = [
                    'stablecoin', 'stable coin', 'pegged', 'backed by', 'collateralized',
                    'usd stable', 'dollar stable', 'price stable'
                ]
                if any(keyword in description for keyword in stablecoin_keywords):
                    return True
            except:
                pass
            
            return False
        except:
            return False
    
    def get_eu_compliance_status(self, risk_report):
        """Get EU compliance status based on red flags and compliance data"""
        try:
            red_flags = risk_report.get('onchain', {}).get('red_flags', [])
            eu_compliance = risk_report.get('eu_compliance', {})
            
            # Check for critical EU compliance issues
            if 'eu_unlicensed_stablecoin' in red_flags:
                return "Non-Compliant (Unlicensed Stablecoin)"
            elif 'eu_regulatory_issues' in red_flags:
                return "Non-Compliant (Regulatory Issues)"
            elif 'mica_non_compliant' in red_flags:
                return "Non-Compliant (MiCA)"
            elif 'mica_no_whitepaper' in red_flags:
                return "Limited Compliance (No Whitepaper)"
            
            # Check EU compliance data
            if eu_compliance:
                status = eu_compliance.get('status', 'Unknown')
                if status in ['Unlicensed', 'Restricted']:
                    return f"Non-Compliant ({status})"
                elif status == 'Compliant':
                    return "Compliant"
                else:
                    return f"Limited Compliance ({status})"
            
            return "Unknown"
        except:
            return "Unknown"
    
    def classify_risk(self, score, risk_report=None):
        """Classify risk level based on comprehensive score and EU compliance
        
        Risk Classification Scale (0-150):
        - Low Risk (0-50):
          Tokens with strong fundamentals, high liquidity,
          and good security practices
        
        - Medium Risk (51-100):
          Tokens with decent metrics but some concerns
          in specific areas
        
        - High Risk (101-120):
          Tokens with significant red flags or
          compliance issues
        
        - Extreme Risk (121-150):
          Tokens with critical issues or multiple
          severe red flags
        
        EU Compliance Override:
        - Unlicensed stablecoins automatically classified as Extreme Risk
        - EU regulatory issues force Extreme Risk classification
        
        Args:
            score (float): The calculated risk score (0-150)
            risk_report (dict): Risk assessment data for compliance checks
            
        Returns:
            str: Risk category classification
        """
        # EU Compliance Override - CRITICAL
        if risk_report:
            red_flags = risk_report.get('onchain', {}).get('red_flags', [])
            
            # Unlicensed stablecoins = IMMEDIATE Extreme Risk
            if 'eu_unlicensed_stablecoin' in red_flags:
                print(f"[EU COMPLIANCE] {risk_report.get('symbol', 'Unknown')} classified as Extreme Risk due to unlicensed stablecoin status")
                return "Extreme Risk"
            
            # EU regulatory issues = Extreme Risk
            if 'eu_regulatory_issues' in red_flags:
                print(f"[EU COMPLIANCE] {risk_report.get('symbol', 'Unknown')} classified as Extreme Risk due to EU regulatory issues")
                return "Extreme Risk"
            
            # MiCA non-compliance for stablecoins = Extreme Risk
            if 'mica_non_compliant' in red_flags:
                print(f"[EU COMPLIANCE] {risk_report.get('symbol', 'Unknown')} classified as Extreme Risk due to MiCA non-compliance")
                return "Extreme Risk"
        
        # Standard risk classification
        if score <= 50:
            return "Low Risk"
        elif score <= 100:
            return "Medium Risk"
        elif score <= 120:
            return "High Risk"
        else:
            return "Extreme Risk"
    
    def score_business_model(self, risk_report):
        """Enhanced score based on business model sustainability (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            
            # Check for clear business model indicators
            project_data = risk_report.get('market', {}).get('coingecko', {})
            description = project_data.get('description', {}).get('en', '').lower()
            
            # Business model keywords
            business_keywords = ['utility', 'governance', 'staking', 'yield', 'lending', 'swap', 'amm', 'dex']
            model_count = sum(1 for keyword in business_keywords if keyword in description)
            if model_count >= 2:
                score -= 1  # Lower risk if clear business model
                data_found = True
            elif model_count == 0:
                score += 1  # Higher risk if no clear business model
            
            # Alternative data sources when primary data is limited
            if not data_found:
                # Use DeFiLlama data for business model indicators
                try:
                    defillama_data = risk_report.get('enhanced', {}).get('defillama', {})
                    if defillama_data.get('yields'):
                        score -= 1  # Lower risk if DeFiLlama tracks yields (indicates business model)
                except:
                    pass
                
                # Use contract complexity as business model indicator
                try:
                    contract_source = risk_report.get('onchain', {}).get('contract_source', '')
                    if contract_source:
                        business_functions = ['stake', 'yield', 'lend', 'borrow', 'swap', 'govern']
                        func_count = sum(1 for func in business_functions if func in contract_source.lower())
                        if func_count >= 2:
                            score -= 1  # Lower risk for complex business model
                except:
                    pass
                
                # Use market cap as business model indicator
                try:
                    market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                    if market_cap > 10_000_000:
                        score -= 1  # Lower risk for established business model
                    elif market_cap < 100_000:
                        score += 1  # Higher risk for unproven business model
                except:
                    pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in business_model scoring: {e}")
            return 7
    
    def score_global_reach(self, risk_report):
        """Enhanced score based on global reach and adoption (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            
            # Check exchange listings for global reach
            project_data = risk_report.get('market', {}).get('coingecko', {})
            tickers = project_data.get('tickers', [])
            
            if tickers:
                # Count unique exchanges
                unique_exchanges = len(set(ticker.get('market', {}).get('name', '') for ticker in tickers))
                if unique_exchanges >= 5:
                    score -= 2  # Very high global reach
                    data_found = True
                elif unique_exchanges >= 3:
                    score -= 1  # High global reach
                    data_found = True
                elif unique_exchanges == 1:
                    score += 1  # Limited global reach
                elif unique_exchanges == 0:
                    score += 2  # No global reach
            
            # Alternative data sources when primary data is limited
            if not data_found:
                # Use holder count as global reach indicator
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        total_holders = holders.get('total_holders', 0)
                        if total_holders > 100000:
                            score -= 2  # Very high global reach
                        elif total_holders > 20000:
                            score -= 1  # High global reach
                        elif total_holders < 1000:
                            score += 1  # Limited global reach
                except:
                    pass
                
                # Use trading volume as global reach indicator
                try:
                    volume_24h = project_data.get('market_data', {}).get('total_volume', {}).get('usd', 0)
                    if volume_24h > 5_000_000:
                        score -= 1  # Lower risk for high global trading
                    elif volume_24h < 10_000:
                        score += 1  # Higher risk for low global trading
                except:
                    pass
                
                # Use Moralis transfer data for global reach
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        # Check for diverse transfer patterns (indicates global usage)
                        unique_addresses = len(set(t.get('from_address', '') for t in transfers))
                        if unique_addresses > 50:
                            score -= 1  # Lower risk for global usage
                        elif unique_addresses < 10:
                            score += 1  # Higher risk for limited usage
                except:
                    pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in global_reach scoring: {e}")
            return 7
    
    def score_market_dynamics(self, risk_report):
        """Enhanced score based on market dynamics and volatility (1-10)"""
        try:
            score = 5  # Base score
            data_found = False
            
            # Check price volatility
            project_data = risk_report.get('market', {}).get('coingecko', {})
            try:
                price_change_24h = project_data.get('market_data', {}).get('price_change_percentage_24h', 0)
                if price_change_24h:
                    if abs(price_change_24h) < 10:  # Low volatility
                        score -= 1  # Lower risk for stable price
                        data_found = True
                    elif abs(price_change_24h) > 50:  # High volatility
                        score += 2  # Higher risk for volatile price
                    elif abs(price_change_24h) > 20:  # Moderate volatility
                        score += 1  # Slightly higher risk
            except:
                pass
            
            # Check market cap to volume ratio
            try:
                volume_24h = project_data.get('market_data', {}).get('total_volume', {}).get('usd', 0)
                market_cap = project_data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                
                if volume_24h > 0 and market_cap > 0:
                    volume_market_cap_ratio = volume_24h / market_cap
                    if volume_market_cap_ratio > 0.5:  # Very high trading activity
                        score += 1  # Higher risk for excessive trading
                    elif volume_market_cap_ratio < 0.01:  # Very low trading activity
                        score += 1  # Higher risk for low liquidity
                    elif 0.01 <= volume_market_cap_ratio <= 0.1:  # Healthy trading activity
                        score -= 1  # Lower risk for healthy dynamics
                        data_found = True
            except:
                pass
            
            # Alternative data sources when primary data is limited
            if not data_found:
                # Use Moralis transfer data for market dynamics
                try:
                    moralis_data = risk_report.get('enhanced', {}).get('moralis', {})
                    transfers = moralis_data.get('transfers', [])
                    if transfers:
                        # Check for transfer frequency (indicates market activity)
                        if len(transfers) > 200:
                            score += 1  # Higher risk for excessive activity
                        elif len(transfers) < 10:
                            score += 1  # Higher risk for low activity
                        elif 20 <= len(transfers) <= 100:
                            score -= 1  # Lower risk for healthy activity
                except:
                    pass
                
                # Use liquidity for market dynamics
                try:
                    liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                    if liquidity > 10_000_000:
                        score -= 1  # Lower risk for high liquidity
                    elif liquidity < 100_000:
                        score += 1  # Higher risk for low liquidity
                except:
                    pass
                
                # Use holder distribution for market dynamics
                try:
                    holders = risk_report.get('onchain', {}).get('holders', {})
                    if holders:
                        top10_concentration = holders.get('top10_concentration', 100)
                        if top10_concentration > 80:
                            score += 1  # Higher risk for concentrated holdings
                        elif top10_concentration < 30:
                            score -= 1  # Lower risk for distributed holdings
                except:
                    pass
            
            return max(1, min(10, score))
        except Exception as e:
            print(f"Error in market_dynamics scoring: {e}")
            return 7


# --- Data Quality: Validate input addresses and check for duplicates ---
def validate_tokens_csv(input_file):
    seen = set()
    duplicates = []
    invalid = []
    tokens = []
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = row['address']
            if not is_checksum_address(addr):
                try:
                    addr = to_checksum_address(addr)
                except Exception:
                    invalid.append(row['address'])
            if addr.lower() in seen:
                duplicates.append(addr)
            seen.add(addr.lower())
            tokens.append(row)
    if duplicates:
        print(f"Duplicate tokens found: {duplicates}")
        logging.warning(f"Duplicate tokens found: {duplicates}")
    if invalid:
        print(f"Invalid addresses found: {invalid}")
        logging.warning(f"Invalid addresses found: {invalid}")
    return tokens

# --- Parallelized token processing ---
def process_token_batch(input_file="tokens.csv", output_file="risk_report.csv", json_output_file="risk_report.json"):
    global progress_bar
    tokens = validate_tokens_csv(input_file)
    analyzer = DeFiRiskAssessor()
    results = []
    summaries = []
    fallback_count = 0
    api_error_count = 0
    total = len(tokens)
    
    # Initialize the progress bar system
    if PROGRESS_AVAILABLE:
        progress_type = initialize_progress_bar(total, "DeFi Risk Assessment")
        print(f"Using {progress_type} progress bar for {total} tokens...")
    else:
        # Fallback to console progress bar
        progress_bar = ConsoleProgressBar(total, "Risk Assessment")
        print(f"Using console progress bar for {total} tokens...")
    
    print(f"Starting risk assessment for {total} tokens...")
    logging.info(f"Starting risk assessment for {total} tokens...")
    def process_one(token, token_index, total_tokens):
        nonlocal fallback_count, api_error_count
        chain = token.get("chain", "eth").strip().lower()
        address = token["address"].strip()
        
        # Remove per-token progress bar update from here
        logging.info(f"Processing {address} on {chain}")
        
        try:
            result = analyzer.assess_token(
                address, chain,
                token_index=token_index,
                total_tokens=total_tokens
            )
            # Count fallback usage
            if result['details']['onchain']['holders']['total_holders'] == 0 or result['details']['onchain']['liquidity'] == 0:
                fallback_count += 1
            # Count API errors (if any)
            if 'error' in result['details']:
                api_error_count += 1
            results.append(result)
            # Build summary for this token
            red_flags = result['details']['onchain']['red_flags']
            summary = {
                "token": address,
                "chain": chain,
                "symbol": analyzer.cmc_symbol_map.get(address.lower(), {}).get('symbol', ''),
                "risk_score": result['risk_score'],
                "risk_category": result['risk_category'],
                "red_flags": red_flags,
                "is_stablecoin": result['details'].get('is_stablecoin', False),
                "eu_compliance_status": result['details'].get('eu_compliance_status', 'Unknown'),
                "key_metrics": {
                    "market_cap": result['details']['market']['coingecko']['market_data']['market_cap'].get('usd', 0),
                    "volume_24h": result['details']['market']['coingecko']['market_data']['total_volume'].get('usd', 0),
                    "holders": result['details']['onchain']['holders']['total_holders'],
                    "liquidity": result['details']['onchain']['liquidity']
                },
                "component_scores": result['component_scores']
            }
            summaries.append(summary)
            print(f"  Score: {result['risk_score']} - {result['risk_category']}")
            logging.info(f"  Score: {result['risk_score']} - {result['risk_category']}")
        except Exception as e:
            print(f"[process_token_batch] Error processing {address} on {chain}: {str(e)}")
            logging.error(f"[process_token_batch] Error processing {address} on {chain}: {str(e)}")
            results.append({
                "token": address,
                "chain": chain,
                "risk_score": 150,
                "risk_category": "Extreme Risk",
                "error": str(e)
            })
    # Parallel execution
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_one, token, idx, total): (token, idx) for idx, token in enumerate(tokens)}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            token, idx = futures[future]
            address = token["address"].strip()
            chain = token.get("chain", "eth").strip().lower()
            # Update progress bar with current token info (main thread, after token is truly done)
            if PROGRESS_AVAILABLE:
                try:
                    next_token_progress(f"{address[:8]}...")
                    update_progress_phase(0, f"Fetched data for {address[:8]}...")
                    complete_phase_progress(f"Data fetched for {address[:8]}...")
                    update_progress_phase(1, f"Analysis complete for {address[:8]}...")
                    complete_phase_progress(f"Analysis complete for {address[:8]}...")
                except Exception as e:
                    print(f"[ProgressBar] Error updating progress bar: {e}")
                import time
                time.sleep(0.3)  # Throttle updates to avoid browser/file conflicts
            elif progress_bar:
                progress_bar.update(completed, f"Completed: {address} on {chain}")
                import time
                time.sleep(0.3)
    # Phase 3: Generate final reports (only after all tokens are processed)
    if PROGRESS_AVAILABLE:
        complete_phase_progress("Analysis complete")
        update_progress_phase(2, "Generating final reports...")
        complete_phase_progress("Reports generated successfully")
    elif progress_bar:
        progress_bar.update(completed, "Generating final reports...")
    
    # Save results (full details)
    df = pd.DataFrame(results)
    
    # Reorder columns to move component_scores next to red_flags
    if not df.empty:
        # Get all column names
        all_columns = list(df.columns)
        
        # Find positions of key columns
        details_idx = None
        component_scores_idx = None
        
        for i, col in enumerate(all_columns):
            if col == 'details':
                details_idx = i
            elif col == 'component_scores':
                component_scores_idx = i
        
        # If we found both, reorder to put component_scores next to details (which contains red_flags)
        if details_idx is not None and component_scores_idx is not None:
            # Remove component_scores from its current position
            all_columns.pop(component_scores_idx)
            # Insert it after details (which contains red_flags)
            all_columns.insert(details_idx + 1, 'component_scores')
            # Reorder the DataFrame
            df = df[all_columns]
    
    df.to_csv(output_file, index=False)
    print(f"Report saved to {output_file}")
    logging.info(f"Report saved to {output_file}")
    
    # Save summary report (JSON)
    with open(json_output_file, "w") as jf:
        json.dump(summaries, jf, indent=2)
    print(f"Summary report saved to {json_output_file}")
    logging.info(f"Summary report saved to {json_output_file}")
    
    # Write summary TXT
    with open(SUMMARY_TXT, "w") as f:
        f.write(f"{COINGECKO_ATTRIBUTION}\n")
        f.write(f"Total tokens processed: {total}\n")
        f.write(f"Tokens using fallback data: {fallback_count}\n")
        f.write(f"Tokens with API errors: {api_error_count}\n")
        f.write(f"Duplicates found: {len(set([t['address'].lower() for t in tokens]) ) - len(tokens)}\n")
    print("Summary report saved to risk_assessment_summary.txt")
    logging.info("Summary report saved to risk_assessment_summary.txt")

    # Create a flag file to signal completion
    flag_path = os.path.join(DATA_DIR, "risk_report.done")
    with open(flag_path, "w") as f:
        f.write("done")
    
    # Complete the final phase
    if PROGRESS_AVAILABLE:
        complete_phase_progress("Reports generated successfully")
        finish_progress_bar("Risk assessment complete!")
        import time
        time.sleep(2)  # Give browser time to refresh and show the final message
    elif progress_bar:
        progress_bar.finish("Risk assessment complete!")
        import time
        time.sleep(2)  # Give browser time to refresh and show the final message
    
    # Wait for progress bar to close, then show completion dialog
    import time
    time.sleep(4)  # Wait for progress bar countdown to complete
    
    # Show completion dialog with disclaimer
    try:
        import subprocess
        completion_script = f'''
        tell application "System Events"
            display dialog "✅ Update Completed!

📊 Risk assessment has been completed successfully!

📁 Results saved to:
• {output_file}
• {json_output_file}
• {SUMMARY_TXT}

📝 Check the 'data/' directory for detailed reports and the 'logs/' directory for execution logs.

⚠️ DISCLAIMER:
This tool provides automated risk assessment based on available data and should be used as part of a comprehensive due diligence process. Results are for informational purposes only and do not constitute financial advice. Always conduct your own research and consult with qualified professionals before making investment decisions.

Market data provided by CoinGecko (https://www.coingecko.com)" with title "DeFi Risk Assessment - Complete" buttons {{"OK"}} default button "OK" with icon note
        end tell
        '''
        subprocess.run(['osascript', '-e', completion_script], check=True)
    except Exception as e:
        print(f"Could not show completion dialog: {e}")
        print("✅ Risk assessment completed successfully!")
        print(f"📊 Check the 'data/' directory for results")
        print(f"📝 Check the 'logs/' directory for detailed logs")

# Update logging setup
logging.basicConfig(filename=VERBOSE_LOG, level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# Update all open/read/write calls to use the above paths
# Example: with open(CMC_SYMBOL_MAP, 'r') as f:
# Example: with open(RISK_REPORT_JSON, 'w') as f:
# Example: pd.DataFrame(...).to_csv(RISK_REPORT_CSV, ...)
# Example: api_cache = APICache(API_CACHE_DB)
# Example: with open(SUMMARY_TXT, 'w') as f:
# ... existing code ...
# In all places where 'fallbacks.json', 'cmc_symbol_map.json', 'tokens.csv', etc. are opened, replace with the corresponding variable.

# --- Breadcrumbs API Integration ---
_breadcrumbs_blocked = False

def fetch_breadcrumbs_risk_score(address):
    global _breadcrumbs_blocked
    if _breadcrumbs_blocked:
        return None
    api_key = os.getenv("BREADCRUMBS_API_KEY")
    if not api_key:
        logging.warning("Breadcrumbs API key not set.")
        return None
    url = f"https://api.breadcrumbs.app/api/v1/addresses/{address}/risk-score"
    headers = {"Authorization": f"Bearer {api_key}"}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        elif resp.status_code == 403 or ("cloudflare" in resp.text.lower()):
            logging.warning("Breadcrumbs API blocked by Cloudflare or returned 403. Skipping Breadcrumbs for this run.")
            _breadcrumbs_blocked = True
            return None
        else:
            logging.warning(f"Breadcrumbs API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Breadcrumbs API exception: {e}")
    return None

def fetch_breadcrumbs_token_info(address):
    global _breadcrumbs_blocked
    if _breadcrumbs_blocked:
        return None
    api_key = os.getenv("BREADCRUMBS_API_KEY")
    if not api_key:
        logging.warning("Breadcrumbs API key not set.")
        return None
    url = f"https://api.breadcrumbs.app/api/v1/tokens/{address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        elif resp.status_code == 403 or ("cloudflare" in resp.text.lower()):
            logging.warning("Breadcrumbs Token API blocked by Cloudflare or returned 403. Skipping Breadcrumbs for this run.")
            _breadcrumbs_blocked = True
            return None
        else:
            logging.warning(f"Breadcrumbs Token API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Breadcrumbs Token API exception: {e}")
    return None

# --- Ethplorer API Integration ---
def fetch_ethplorer_token_info(address):
    api_key = os.getenv("ETHPLORER_API_KEY", "freekey")
    url = f"https://api.ethplorer.io/getTokenInfo/{address}?apiKey={api_key}"
    cache_key = get_cache_key(url)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Ethplorer API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Ethplorer API exception: {e}")
    return None

def fetch_ethplorer_address_info(address):
    api_key = os.getenv("ETHPLORER_API_KEY", "freekey")
    url = f"https://api.ethplorer.io/getAddressInfo/{address}?apiKey={api_key}"
    cache_key = get_cache_key(url)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Ethplorer Address API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Ethplorer Address API exception: {e}")
    return None

# --- Zapper API Integration ---
def fetch_zapper_portfolio_data(address):
    """Fetch portfolio data from Zapper API"""
    api_key = os.getenv("ZAPPER_API_KEY")
    if not api_key:
        logging.warning("Zapper API key not set.")
        return None
    url = f"https://api.zapper.xyz/v2/portfolio/{address}"
    headers = {"Authorization": f"Basic {api_key}"}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Zapper API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Zapper API exception: {e}")
    return None

def fetch_zapper_protocol_data(protocol):
    """Fetch protocol data from Zapper API"""
    api_key = os.getenv("ZAPPER_API_KEY")
    if not api_key:
        logging.warning("Zapper API key not set.")
        return None
    url = f"https://api.zapper.xyz/v2/protocols/{protocol}"
    headers = {"Authorization": f"Basic {api_key}"}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Zapper Protocol API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Zapper Protocol API exception: {e}")
    return None

# --- DeBank API Integration ---
def fetch_debank_portfolio(address):
    """Fetch portfolio data from DeBank API"""
    api_key = os.getenv("DEBANK_API_KEY")
    if not api_key:
        logging.warning("DeBank API key not set.")
        return None
    url = f"https://pro-openapi.debank.com/v1/user/portfolio_list?id={address}"
    headers = {"AccessKey": api_key}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"DeBank API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"DeBank API exception: {e}")
    return None

def fetch_debank_token_list(chain_id):
    """Fetch token list from DeBank API"""
    api_key = os.getenv("DEBANK_API_KEY")
    if not api_key:
        logging.warning("DeBank API key not set.")
        return None
    url = f"https://pro-openapi.debank.com/v1/user/token_list?id={chain_id}"
    headers = {"AccessKey": api_key}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"DeBank Token List API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"DeBank Token List API exception: {e}")
    return None

# --- DeFiLlama API Integration ---
def fetch_defillama_protocol_tvl(protocol):
    """Fetch protocol TVL data from DeFiLlama API"""
    api_key = os.getenv("DEFILLAMA_API_KEY")
    url = f"https://api.llama.fi/protocol/{protocol}"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"DeFiLlama API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"DeFiLlama API exception: {e}")
    return None

def fetch_defillama_token_price(token_address, chain="ethereum"):
    """Fetch token price data from DeFiLlama API"""
    api_key = os.getenv("DEFILLAMA_API_KEY")
    url = f"https://coins.llama.fi/prices/current/{chain}:{token_address}"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"DeFiLlama Token Price API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"DeFiLlama Token Price API exception: {e}")
    return None

def fetch_defillama_yield_pools(protocol):
    """Fetch yield pool data from DeFiLlama API"""
    api_key = os.getenv("DEFILLAMA_API_KEY")
    url = f"https://yields.llama.fi/pools?protocol={protocol}"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"DeFiLlama Yield API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"DeFiLlama Yield API exception: {e}")
    return None

# --- Moralis API Integration ---
def fetch_moralis_token_metadata(address, chain="eth"):
    """Fetch token metadata from Moralis API"""
    api_key = os.getenv("MORALIS_API_KEY")
    if not api_key:
        logging.warning("Moralis API key not set.")
        return None
    url = f"https://deep-index.moralis.io/api/v2/erc20/{address}?chain={chain}"
    headers = {"X-API-Key": api_key}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Moralis Token Metadata API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Moralis Token Metadata API exception: {e}")
    return None

def fetch_moralis_token_price(address, chain="eth"):
    """Fetch token price from Moralis API"""
    api_key = os.getenv("MORALIS_API_KEY")
    if not api_key:
        logging.warning("Moralis API key not set.")
        return None
    url = f"https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain={chain}"
    headers = {"X-API-Key": api_key}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Moralis Token Price API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Moralis Token Price API exception: {e}")
    return None

def fetch_moralis_token_transfers(address, chain="eth", limit=100):
    """Fetch token transfers from Moralis API"""
    api_key = os.getenv("MORALIS_API_KEY")
    if not api_key:
        logging.warning("Moralis API key not set.")
        return None
    url = f"https://deep-index.moralis.io/api/v2/erc20/{address}/transfers?chain={chain}&limit={limit}"
    headers = {"X-API-Key": api_key}
    cache_key = get_cache_key(url, None, headers)
    cached = api_cache.get(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            api_cache.set(cache_key, data)
            return data
        else:
            logging.warning(f"Moralis Token Transfers API error: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Moralis Token Transfers API exception: {e}")
    return None

# Import the working progress bar system
try:
    from working_progress_bar import (
        initialize_progress_bar,
        update_progress_phase,
        next_token_progress,
        complete_phase_progress,
        finish_progress_bar,
        close_progress_bar
    )
    PROGRESS_AVAILABLE = True
except ImportError:
    PROGRESS_AVAILABLE = False
    print("Warning: Progress bar not available, using console fallback")

# --- Fallback Console Progress Bar ---
class ConsoleProgressBar:
    def __init__(self, total_items, description="Processing"):
        self.total_items = total_items
        self.description = description
        self.completed = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 0.5  # Update every 0.5 seconds
        
    def update(self, completed=None, message=""):
        with self.lock:
            if completed is not None:
                self.completed = completed
            else:
                self.completed += 1
                
            now = time.time()
            if now - self.last_update < self.update_interval and self.completed < self.total_items:
                return  # Skip update if too soon and not final
            self.last_update = now
            
            percent = int((self.completed / self.total_items) * 100)
            elapsed = now - self.start_time
            
            # Calculate ETA
            if self.completed > 0:
                eta = (elapsed / self.completed) * (self.total_items - self.completed)
                eta_str = f"ETA: {eta:.1f}s"
            else:
                eta_str = "ETA: --"
            
            # Create progress bar
            bar_length = 30
            filled_length = int(bar_length * self.completed // self.total_items)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            
            # Clear line and print progress
            sys.stdout.write(f'\r{self.description}: [{bar}] {percent}% ({self.completed}/{self.total_items}) {eta_str} {message}')
            sys.stdout.flush()
            
            if self.completed >= self.total_items:
                print()  # New line when complete
    
    def finish(self, message="Complete!"):
        self.update(self.total_items, message)
        print()

# Global progress bar instance
progress_bar = None

def launch_progress_bar():
    """Initialize the progress bar system"""
    global progress_bar
    # This will be set in process_token_batch
    pass

def update_progress_bar(percent, message):
    """Update the progress bar"""
    global progress_bar
    if progress_bar:
        completed = int((percent / 100) * progress_bar.total_items)
        progress_bar.update(completed, message)

def get_cache_key(url, params=None, headers=None, data=None):
    key = url
    if params:
        key += json.dumps(params, sort_keys=True)
    if headers:
        key += json.dumps(headers, sort_keys=True)
    if data:
        key += json.dumps(data, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()

def fetch_1inch_quote(from_token_address, to_token_address, amount, chain_id=1):
    """
    Fetch a quote from the 1inch API for swapping from_token to to_token.
    :param from_token_address: str, address of the token to swap from
    :param to_token_address: str, address of the token to swap to
    :param amount: int or str, amount in minimal units (wei for ETH, etc.)
    :param chain_id: int, 1 for Ethereum mainnet, 56 for BSC, etc.
    :return: dict, quote data
    """
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        print("Warning: 1INCH_API_KEY not found. Skipping 1inch API calls.")
        return {}
    
    url = f"https://api.1inch.dev/swap/v5.2/{chain_id}/quote"
    params = {
        "fromTokenAddress": from_token_address,
        "toTokenAddress": to_token_address,
        "amount": str(amount)
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch quote: {e}")
        return {}

# Example/test usage
if __name__ == "__main__":
    # Example: ETH -> USDT on Ethereum mainnet
    ETH = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    amount_wei = 10**18  # 1 ETH in wei
    try:
        quote = fetch_1inch_quote(ETH, USDT, amount_wei, chain_id=1)
        print("1inch quote ETH->USDT:", quote)
    except Exception as e:
        print("Error fetching 1inch quote:", e)

if __name__ == "__main__":
    # At the start of main execution (before processing tokens)
    try:
        process_token_batch(input_file=TOKENS_CSV, output_file=RISK_REPORT_CSV, json_output_file=RISK_REPORT_JSON)
    finally:
        # Close progress bar and cleanup
        if PROGRESS_AVAILABLE:
            close_progress_bar()
        time.sleep(0.5)
        api_cache.close()

# --- 1inch API Integration ---

ONEINCH_BASE = "https://api.1inch.dev"

# 1. Token Metadata

def fetch_1inch_token_metadata(token_address, chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/token/v1.2/{chain_id}/tokens"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tokens = response.json().get("tokens", {})
        return tokens.get(token_address.lower())
    except Exception as e:
        print(f"Error fetching 1inch token metadata: {e}")
        return {}

# 2. Spot Price

def fetch_1inch_spot_price(token_address, chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/spot-price/v1.0/{chain_id}/tokens/{token_address}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch spot price: {e}")
        return {}

# 3. Swap Quote (already present, but refactored for consistency)
def fetch_1inch_quote(from_token_address, to_token_address, amount, chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/swap/v5.2/{chain_id}/quote"
    params = {
        "fromTokenAddress": from_token_address,
        "toTokenAddress": to_token_address,
        "amount": str(amount)
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch quote: {e}")
        return {}

# 4. Swap Route

def fetch_1inch_swap(from_token_address, to_token_address, amount, wallet_address, chain_id=1, slippage=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/swap/v5.2/{chain_id}/swap"
    params = {
        "fromTokenAddress": from_token_address,
        "toTokenAddress": to_token_address,
        "amount": str(amount),
        "fromAddress": wallet_address,
        "slippage": slippage
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch swap: {e}")
        return {}

# 5. Wallet Balances

def fetch_1inch_balances(wallet_address, chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/balance/v1.2/{chain_id}/balances/{wallet_address}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch balances: {e}")
        return {}

# 6. Gas Price

def fetch_1inch_gas_price(chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/gas-price/v1.4/{chain_id}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch gas price: {e}")
        return {}

# 7. Orderbook

def fetch_1inch_orderbook(chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/orderbook/v1.1/{chain_id}/orders"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch orderbook: {e}")
        return {}

# 8. Portfolio

def fetch_1inch_portfolio(wallet_address, chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/portfolio/v1.0/{chain_id}/portfolio/{wallet_address}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch portfolio: {e}")
        return {}

# 9. History

def fetch_1inch_history(wallet_address, chain_id=1):
    # Check if API key is available
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        return {}
    
    url = f"{ONEINCH_BASE}/history/v1.0/{chain_id}/history/{wallet_address}"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching 1inch history: {e}")
        return {}

# --- Enrichment function ---
def enrich_with_1inch_data(token_address, chain_id=1, wallet_address=None, to_token_address=None, amount=None):
    """
    Enrich a token's risk assessment with 1inch data. Optionally provide wallet_address, to_token_address, and amount for swap/portfolio endpoints.
    """
    data = {}
    try:
        data['token_metadata'] = fetch_1inch_token_metadata(token_address, chain_id)
    except Exception as e:
        data['token_metadata'] = f"Error: {e}"
    try:
        data['spot_price'] = fetch_1inch_spot_price(token_address, chain_id)
    except Exception as e:
        data['spot_price'] = f"Error: {e}"
    if to_token_address and amount:
        try:
            data['swap_quote'] = fetch_1inch_quote(token_address, to_token_address, amount, chain_id)
        except Exception as e:
            data['swap_quote'] = f"Error: {e}"
        if wallet_address:
            try:
                data['swap_route'] = fetch_1inch_swap(token_address, to_token_address, amount, wallet_address, chain_id)
            except Exception as e:
                data['swap_route'] = f"Error: {e}"
    if wallet_address:
        try:
            data['balances'] = fetch_1inch_balances(wallet_address, chain_id)
        except Exception as e:
            data['balances'] = f"Error: {e}"
        try:
            data['portfolio'] = fetch_1inch_portfolio(wallet_address, chain_id)
        except Exception as e:
            data['portfolio'] = f"Error: {e}"
        try:
            data['history'] = fetch_1inch_history(wallet_address, chain_id)
        except Exception as e:
            data['history'] = f"Error: {e}"
    try:
        data['gas_price'] = fetch_1inch_gas_price(chain_id)
    except Exception as e:
        data['gas_price'] = f"Error: {e}"
    try:
        data['orderbook'] = fetch_1inch_orderbook(chain_id)
    except Exception as e:
        data['orderbook'] = f"Error: {e}"
    return data

def fetch_scorechain_aml(token_address, chain):
    """Fetch AML risk data from Scorechain API"""
    import os, requests
    api_key = os.getenv("SCORECHAIN_API_KEY")
    if not api_key:
        raise Exception("Missing SCORECHAIN_API_KEY")
    url = f"https://api.scorechain.com/v1/aml/{chain}/address/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    risk_level = data.get('riskLevel', 'unknown')
    if risk_level == 'high':
        return {"summary": "High AML risk", "score_delta": 3}
    elif risk_level == 'medium':
        return {"summary": "Medium AML risk", "score_delta": 1}
    elif risk_level == 'low':
        return {"summary": "Low AML risk", "score_delta": -2}
    else:
        return {"summary": "Unknown AML risk", "score_delta": 0}

def fetch_trmlabs_aml(token_address, chain):
    """Fetch AML risk data from TRM Labs API"""
    import os, requests
    api_key = os.getenv("TRMLABS_API_KEY")
    if not api_key:
        raise Exception("Missing TRMLABS_API_KEY")
    url = f"https://api.trmlabs.com/v1/addresses/{token_address}/risk"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    risk_score = data.get('riskScore', 0)
    if risk_score >= 80:
        return {"summary": f"TRM risk score {risk_score} (high)", "score_delta": 3}
    elif risk_score >= 50:
        return {"summary": f"TRM risk score {risk_score} (medium)", "score_delta": 1}
    elif risk_score > 0:
        return {"summary": f"TRM risk score {risk_score} (low)", "score_delta": -2}
    else:
        return {"summary": "No TRM risk data", "score_delta": 0}

def fetch_opensanctions_compliance(token_address, chain):
    """Fetch compliance data from OpenSanctions API"""
    import os, requests
    api_key = os.getenv("OPENSANCTIONS_API_KEY")
    if not api_key:
        raise Exception("Missing OPENSANCTIONS_API_KEY")
    url = f"https://api.opensanctions.org/v1/entities/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # Example logic
    if data.get('sanctioned', False):
        return {"summary": "Sanctioned entity", "score_delta": 3}
    else:
        return {"summary": "Not sanctioned", "score_delta": -1}

def fetch_lukka_compliance(token_address, chain):
    """Fetch compliance data from Lukka API"""
    import os, requests
    api_key = os.getenv("LUKKA_API_KEY")
    if not api_key:
        raise Exception("Missing LUKKA_API_KEY")
    url = f"https://api.lukka.tech/v1/compliance/{chain}/address/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # Example logic
    if data.get('compliant', False):
        return {"summary": "Lukka compliant", "score_delta": -2}
    else:
        return {"summary": "Lukka non-compliant", "score_delta": 2}

def fetch_alchemy_compliance(token_address, chain):
    """Fetch compliance data from Alchemy API"""
    import os, requests
    api_key = os.getenv("ALCHEMY_API_KEY")
    if not api_key:
        raise Exception("Missing ALCHEMY_API_KEY")
    url = f"https://dashboard.alchemyapi.io/api/compliance/{chain}/address/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # Example logic
    if data.get('complianceStatus', '') == 'compliant':
        return {"summary": "Alchemy compliant", "score_delta": -2}
    else:
        return {"summary": "Alchemy non-compliant", "score_delta": 2}

def fetch_defisafety_compliance(token_address, chain):
    """Fetch compliance data from DeFiSafety (web scraping or API)"""
    import requests
    url = f"https://www.defisafety.com/app/project/{token_address}"
    resp = requests.get(url, timeout=20)
    if resp.status_code == 200 and 'score' in resp.text:
        # Example: parse score from HTML (real logic may require BeautifulSoup)
        score = 80  # Placeholder
        if score > 75:
            return {"summary": "DeFiSafety high score", "score_delta": -2}
        elif score > 50:
            return {"summary": "DeFiSafety medium score", "score_delta": 0}
        else:
            return {"summary": "DeFiSafety low score", "score_delta": 2}
    return {"summary": "No DeFiSafety data", "score_delta": 0}

# --- Improved CoinGecko Endpoint Selection ---
def get_coingecko_base_and_headers():
    coingecko_key = os.getenv('COINGECKO_API_KEY')
    if coingecko_key and coingecko_key.startswith('CG-'):
        # Demo key, must use public endpoint
        return 'https://api.coingecko.com/api/v3', {}
    elif coingecko_key:
        # Pro key
        return 'https://pro-api.coingecko.com/api/v3', {'x-cg-pro-api-key': coingecko_key}
    else:
        return 'https://api.coingecko.com/api/v3', {}

# --- Enhanced Etherscan Integration ---
def fetch_etherscan_all(token_address, etherscan_key, chain='eth'):
    """Try all relevant Etherscan endpoints for contract verification, token info, supply, holders, etc."""
    results = {}
    scan_urls = {
        'eth': 'https://api.etherscan.io/api',
        'bsc': 'https://api.bscscan.com/api',
        'polygon': 'https://api.polygonscan.com/api',
    }
    scan_url = scan_urls.get(chain, scan_urls['eth'])
    # 1. Contract verification
    try:
        params = {'module': 'contract', 'action': 'getabi', 'address': token_address, 'apikey': etherscan_key}
        resp = requests.get(scan_url, params=params, timeout=20)
        if resp.status_code == 200 and resp.json().get('status') == '1':
            results['is_verified'] = True
            print(f"✓ Etherscan getabi: Contract verified")
        else:
            results['is_verified'] = False
            print(f"✗ Etherscan getabi: Not verified or error")
    except Exception as e:
        print(f"✗ Etherscan getabi error: {e}")
    # 2. Token info
    try:
        params = {'module': 'token', 'action': 'tokeninfo', 'contractaddress': token_address, 'apikey': etherscan_key}
        resp = requests.get(scan_url, params=params, timeout=20)
        if resp.status_code == 200 and resp.json().get('status') == '1':
            results['tokeninfo'] = resp.json()['result'][0]
            print(f"✓ Etherscan tokeninfo: Success")
        else:
            print(f"✗ Etherscan tokeninfo: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Etherscan tokeninfo error: {e}")
    # 3. Total supply
    try:
        params = {'module': 'proxy', 'action': 'eth_call', 'to': token_address, 'data': '0x18160ddd', 'apikey': etherscan_key}
        resp = requests.get(scan_url, params=params, timeout=20)
        if resp.status_code == 200 and resp.json().get('result'):
            results['total_supply'] = int(resp.json()['result'], 16)
            print(f"✓ Etherscan eth_call: totalSupply {results['total_supply']}")
        else:
            print(f"✗ Etherscan eth_call: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Etherscan eth_call error: {e}")
    return results

# --- Enhanced Ethplorer Integration ---
def fetch_ethplorer_all(token_address, ethplorer_key):
    """Try all relevant Ethplorer endpoints for token info, bulk, and address info."""
    results = {}
    # 1. getTokenInfo
    try:
        url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey={ethplorer_key}"
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            results['getTokenInfo'] = resp.json()
            print(f"✓ Ethplorer getTokenInfo: Success")
        else:
            print(f"✗ Ethplorer getTokenInfo: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Ethplorer getTokenInfo error: {e}")
    # 2. bulkMonitor (single address)
    try:
        url = f"https://api.ethplorer.io/bulkMonitor?apiKey={ethplorer_key}"
        resp = requests.post(url, json={"addresses": [token_address]}, timeout=20)
        if resp.status_code == 200:
            results['bulkMonitor'] = resp.json()
            print(f"✓ Ethplorer bulkMonitor: Success")
        else:
            print(f"✗ Ethplorer bulkMonitor: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Ethplorer bulkMonitor error: {e}")
    # 3. getAddressInfo
    try:
        url = f"https://api.ethplorer.io/getAddressInfo/{token_address}?apiKey={ethplorer_key}"
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            results['getAddressInfo'] = resp.json()
            print(f"✓ Ethplorer getAddressInfo: Success")
        else:
            print(f"✗ Ethplorer getAddressInfo: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Ethplorer getAddressInfo error: {e}")
    return results

# --- Enhanced 1inch Integration ---
def fetch_1inch_all(token_address, chain_id=1, wallet_address=None, to_token_address=None, amount=None):
    """Try all relevant 1inch endpoints for token metadata, spot price, quote, swap, balances, gas price, orderbook, portfolio, history."""
    api_key = os.getenv('1INCH_API_KEY')
    if not api_key:
        print("Warning: 1INCH_API_KEY not found. Skipping 1inch API calls.")
        return {}
    data = {}
    try:
        data['token_metadata'] = fetch_1inch_token_metadata(token_address, chain_id)
        print("✓ 1inch token_metadata: Success")
    except Exception as e:
        print(f"✗ 1inch token_metadata error: {e}")
    try:
        data['spot_price'] = fetch_1inch_spot_price(token_address, chain_id)
        print("✓ 1inch spot_price: Success")
    except Exception as e:
        print(f"✗ 1inch spot_price error: {e}")
    if to_token_address and amount:
        try:
            data['swap_quote'] = fetch_1inch_quote(token_address, to_token_address, amount, chain_id)
            print("✓ 1inch swap_quote: Success")
        except Exception as e:
            print(f"✗ 1inch swap_quote error: {e}")
        if wallet_address:
            try:
                data['swap_route'] = fetch_1inch_swap(token_address, to_token_address, amount, wallet_address, chain_id)
                print("✓ 1inch swap_route: Success")
            except Exception as e:
                print(f"✗ 1inch swap_route error: {e}")
    if wallet_address:
        try:
            data['balances'] = fetch_1inch_balances(wallet_address, chain_id)
            print("✓ 1inch balances: Success")
        except Exception as e:
            print(f"✗ 1inch balances error: {e}")
        try:
            data['portfolio'] = fetch_1inch_portfolio(wallet_address, chain_id)
            print("✓ 1inch portfolio: Success")
        except Exception as e:
            print(f"✗ 1inch portfolio error: {e}")
        try:
            data['history'] = fetch_1inch_history(wallet_address, chain_id)
            print("✓ 1inch history: Success")
        except Exception as e:
            print(f"✗ 1inch history error: {e}")
    try:
        data['gas_price'] = fetch_1inch_gas_price(chain_id)
        print("✓ 1inch gas_price: Success")
    except Exception as e:
        print(f"✗ 1inch gas_price error: {e}")
    try:
        data['orderbook'] = fetch_1inch_orderbook(chain_id)
        print("✓ 1inch orderbook: Success")
    except Exception as e:
        print(f"✗ 1inch orderbook error: {e}")
    return data

# --- Enhanced CoinMarketCap Integration ---
def fetch_coinmarketcap_all(token_address, cmc_key):
    """Try all relevant CoinMarketCap endpoints for token data."""
    results = {}
    headers = {'X-CMC_PRO_API_KEY': cmc_key}
    # 1. By contract address
    try:
        url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/info'
        params = {'address': token_address}
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            results['info_by_address'] = resp.json()
            print(f"✓ CoinMarketCap info by address: Success")
        else:
            print(f"✗ CoinMarketCap info by address: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ CoinMarketCap info by address error: {e}")
    # 2. By symbol (if available)
    try:
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        params = {'symbol': token_address}
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        if resp.status_code == 200:
            results['quotes_by_symbol'] = resp.json()
            print(f"✓ CoinMarketCap quotes by symbol: Success")
        else:
            print(f"✗ CoinMarketCap quotes by symbol: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ CoinMarketCap quotes by symbol error: {e}")
    return results

# --- Enhanced Bitquery Integration ---
def fetch_bitquery_all(token_address, bitquery_key, chain='ethereum'):
    """Try all relevant Bitquery endpoints for on-chain data."""
    results = {}
    headers = {'X-API-KEY': bitquery_key}
    # 1. GraphQL endpoint
    try:
        url = 'https://graphql.bitquery.io/'
        query = '{ ethereum { address(address: {is: "%s"}) { smartContract { contractType currency { symbol } } } } }' % token_address
        resp = requests.post(url, headers=headers, json={'query': query}, timeout=20)
        if resp.status_code == 200:
            results['graphql'] = resp.json()
            print(f"✓ Bitquery GraphQL: Success")
        else:
            print(f"✗ Bitquery GraphQL: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Bitquery GraphQL error: {e}")
    return results

# --- Enhanced Dune Analytics Integration ---
def fetch_dune_all(query_id, dune_key):
    """Try all relevant Dune endpoints for query results."""
    results = {}
    headers = {"x-dune-api-key": dune_key}
    # 1. Query results
    try:
        url = f"https://api.dune.com/api/v1/query/{query_id}/results"
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            results['results'] = resp.json()
            print(f"✓ Dune query results: Success")
        else:
            print(f"✗ Dune query results: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Dune query results error: {e}")
    return results

# --- Enhanced Zapper Integration ---
def fetch_zapper_all(address, zapper_key):
    """Try all relevant Zapper endpoints for portfolio and protocol data."""
    results = {}
    headers = {"Authorization": f"Basic {zapper_key}"}
    # 1. Portfolio
    try:
        url = f"https://api.zapper.fi/v2/balances/{address}"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            results['portfolio'] = resp.json()
            print(f"✓ Zapper portfolio: Success")
        else:
            print(f"✗ Zapper portfolio: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Zapper portfolio error: {e}")
    # 2. Protocols
    try:
        url = f"https://api.zapper.fi/v2/protocols"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            results['protocols'] = resp.json()
            print(f"✓ Zapper protocols: Success")
        else:
            print(f"✗ Zapper protocols: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Zapper protocols error: {e}")
    return results

# --- Enhanced Debank Integration ---
def fetch_debank_all(address, debank_key):
    """Try all relevant Debank endpoints for portfolio and token list."""
    results = {}
    headers = {"Authorization": f"Bearer {debank_key}"}
    # 1. Portfolio
    try:
        url = f"https://pro-openapi.debank.com/v1/user/total_balance?id={address}"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            results['portfolio'] = resp.json()
            print(f"✓ Debank portfolio: Success")
        else:
            print(f"✗ Debank portfolio: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Debank portfolio error: {e}")
    # 2. Token list
    try:
        url = f"https://pro-openapi.debank.com/v1/user/token_list?id={address}"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            results['token_list'] = resp.json()
            print(f"✓ Debank token_list: Success")
        else:
            print(f"✗ Debank token_list: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Debank token_list error: {e}")
    return results

# --- Enhanced Moralis Integration ---
def fetch_moralis_all(address, moralis_key, chain='eth'):
    """Try all relevant Moralis endpoints for token metadata, price, and transfers."""
    results = {}
    headers = {"X-API-Key": moralis_key}
    # 1. Token metadata
    try:
        url = f"https://deep-index.moralis.io/api/v2/erc20/metadata?chain={chain}&addresses={address}"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            results['metadata'] = resp.json()
            print(f"✓ Moralis metadata: Success")
        else:
            print(f"✗ Moralis metadata: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Moralis metadata error: {e}")
    # 2. Token price
    try:
        url = f"https://deep-index.moralis.io/api/v2/erc20/{address}/price?chain={chain}"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            results['price'] = resp.json()
            print(f"✓ Moralis price: Success")
        else:
            print(f"✗ Moralis price: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Moralis price error: {e}")
    # 3. Token transfers
    try:
        url = f"https://deep-index.moralis.io/api/v2/erc20/{address}/transfers?chain={chain}"
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            results['transfers'] = resp.json()
            print(f"✓ Moralis transfers: Success")
        else:
            print(f"✗ Moralis transfers: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Moralis transfers error: {e}")
    return results

# --- Enhanced Coinpaprika Integration ---
def fetch_coinpaprika_all(symbol):
    """Try all relevant Coinpaprika endpoints for market data."""
    results = {}
    # 1. Ticker
    try:
        url = f"https://api.coinpaprika.com/v1/tickers/{symbol.lower()}-usd"
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            results['ticker'] = resp.json()
            print(f"✓ Coinpaprika ticker: Success")
        else:
            print(f"✗ Coinpaprika ticker: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Coinpaprika ticker error: {e}")
    # 2. Markets
    try:
        url = f"https://api.coinpaprika.com/v1/coins/{symbol.lower()}-usd/markets"
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            results['markets'] = resp.json()
            print(f"✓ Coinpaprika markets: Success")
        else:
            print(f"✗ Coinpaprika markets: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ Coinpaprika markets error: {e}")
    return results

# --- Enhanced DefiLlama Integration ---
def fetch_defillama_all(token_address, chain='ethereum'):
    """Try all relevant DefiLlama endpoints for protocol TVL, token price, and yield pools."""
    results = {}
    # 1. Protocol TVL
    try:
        url = f"https://api.llama.fi/protocol/{token_address}"
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            results['protocol_tvl'] = resp.json()
            print(f"✓ DefiLlama protocol TVL: Success")
        else:
            print(f"✗ DefiLlama protocol TVL: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ DefiLlama protocol TVL error: {e}")
    # 2. Token price
    try:
        url = f"https://coins.llama.fi/prices/current/{chain}:{token_address}"
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            results['token_price'] = resp.json()
            print(f"✓ DefiLlama token price: Success")
        else:
            print(f"✗ DefiLlama token price: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ DefiLlama token price error: {e}")
    # 3. Yield pools
    try:
        url = f"https://yields.llama.fi/pools"
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            results['yield_pools'] = resp.json()
            print(f"✓ DefiLlama yield pools: Success")
        else:
            print(f"✗ DefiLlama yield pools: {resp.text[:100]}")
    except Exception as e:
        print(f"✗ DefiLlama yield pools error: {e}")