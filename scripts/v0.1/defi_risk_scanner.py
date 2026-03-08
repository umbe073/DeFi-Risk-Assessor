import os
import time
import csv
import requests
import pandas as pd
from web3 import Web3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =====================
# CONFIGURATION
# =====================
CHAIN_CONFIG = {
    "eth": {
        "rpc": f"https://mainnet.infura.io/v3/{os.getenv('INFURA_API_KEY')}",
        "scan_url": "https://api.etherscan.io/api",
        "scan_key": os.getenv("ETHERSCAN_API_KEY"),
        "coin_id": "ethereum",
        "symbol": "ETH"
    },
    "base": {
        "rpc": "https://mainnet.base.org",
        "scan_url": "https://api.basescan.org/api",
        "scan_key": os.getenv("ETHERSCAN_API_KEY"),
        "coin_id": "base",
        "symbol": "ETH"
    },
    "arbitrum-nova": {
        "rpc": "https://nova.arbitrum.io/rpc",
        "scan_url": "https://api-nova.arbiscan.io/api",
        "scan_key": os.getenv("ETHERSCAN_API_KEY"),
        "coin_id": "arbitrum-nova",
        "symbol": "ETH"
    },
    "bsc": {
        "rpc": "https://bsc-dataseed.binance.org/",
        "scan_url": "https://api.bscscan.com/api",
        "scan_key": os.getenv("ETHERSCAN_API_KEY"),
        "coin_id": "binancecoin",
        "symbol": "BNB"
    },
    "polygon": {
        "rpc": "https://polygon-rpc.com",
        "scan_url": "https://api.polygonscan.com/api",
        "scan_key": os.getenv("ETHERSCAN_API_KEY"),
        "coin_id": "matic-network",
        "symbol": "MATIC"
    },
    "optimism": {
        "rpc": "https://mainnet.optimism.io",
        "scan_url": "https://api-optimistic.etherscan.io/api",
        "scan_key": os.getenv("ETHERSCAN_API_KEY"),
        "coin_id": "optimism",
        "symbol": "ETH"
    }
}

# API Configuration
API_CONFIG = {
    "coinmarketcap": {
        "url": "https://pro-api.coinmarketcap.com/v1/",
        "key": os.getenv("COINMARKETCAP_API_KEY"),
        "headers": {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": os.getenv("COINMARKETCAP_API_KEY")
        }
    },
    "coingecko": {
        "url": "https://api.coingecko.com/api/v3/",
        "key": os.getenv("COINGECKO_API_KEY"),
        "headers": {
            "Accepts": "application/json",
            "x-cg-demo-api-key": os.getenv("COINGECKO_API_KEY")
        }
    }
}

# Risk calculation parameters
RISK_PARAMS = {
    "weights": {
        "audit": 0.35,
        "liquidity": 0.30,
        "holders": 0.25,
        "security": 0.10
    }
}

# =====================
# CORE FUNCTIONS
# =====================
def get_web3_provider(chain_name):
    """Create Web3 provider"""
    if chain_name not in CHAIN_CONFIG:
        return None
    try:
        return Web3(Web3.HTTPProvider(CHAIN_CONFIG[chain_name]["rpc"]))
    except:
        return None

def get_contract_verification_status(contract_address, chain_name):
    """Check if contract is verified on chain explorer"""
    if chain_name not in CHAIN_CONFIG or not CHAIN_CONFIG[chain_name]["scan_key"]:
        return "unknown"
    
    try:
        params = {
            "module": "contract",
            "action": "getabi",
            "address": contract_address,
            "apikey": CHAIN_CONFIG[chain_name]["scan_key"]
        }
        response = requests.get(CHAIN_CONFIG[chain_name]["scan_url"], params=params, timeout=10)
        data = response.json()
        return "verified" if data.get("status") == "1" else "unverified"
    except:
        return "unknown"

def get_liquidity_data_from_dex(token_address, chain_name):
    """Fetch actual liquidity data from DEXs"""
    try:
        if chain_name == "eth":
            # Uniswap V2 subgraph
            url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
            query = f"""
            {{
                token(id: "{token_address.lower()}") {{
                    totalLiquidity
                }}
            }}
            """
            response = requests.post(url, json={'query': query})
            data = response.json()
            return float(data["data"]["token"]["totalLiquidity"])
        
        elif chain_name == "bsc":
            # PancakeSwap subgraph
            url = "https://api.thegraph.com/subgraphs/name/pancakeswap/exchange-v2"
            query = f"""
            {{
                token(id: "{token_address.lower()}") {{
                    totalLiquidity
                }}
            }}
            """
            response = requests.post(url, json={'query': query})
            data = response.json()
            return float(data["data"]["token"]["totalLiquidity"])
        
        # Add other DEXs as needed
        return None
    except:
        return None

def get_liquidity_score(token_address, chain_name):
    """Calculate liquidity score using real data"""
    try:
        # First try CoinMarketCap
        url = f"{API_CONFIG['coinmarketcap']['url']}cryptocurrency/market-pairs/latest"
        params = {
            "address": token_address,
            "limit": 1
        }
        response = requests.get(url, headers=API_CONFIG["coinmarketcap"]["headers"], params=params)
        data = response.json()
        
        if "data" in data and "market_pairs" in data["data"]:
            liquidity = float(data["data"]["market_pairs"][0]["quote"]["USD"]["liquidity"])
            return liquidity
        
        # Fallback to CoinGecko
        url = f"{API_CONFIG['coingecko']['url']}coins/{CHAIN_CONFIG[chain_name]['coin_id']}/tickers"
        response = requests.get(url, headers=API_CONFIG["coingecko"]["headers"])
        data = response.json()
        
        if "tickers" in data:
            # Get average liquidity from top exchanges
            liquidity = sum(float(t["converted_volume"]["usd"]) for t in data["tickers"][:3]) / 3
            return liquidity
        
        # Final fallback to DEX data
        dex_liquidity = get_liquidity_data_from_dex(token_address, chain_name)
        if dex_liquidity:
            return dex_liquidity
            
        return 0  # Default if no data found
    except:
        return 0

def get_holder_distribution(token_address, chain_name):
    """Fetch real holder concentration metrics"""
    try:
        if chain_name in ["eth", "bsc", "polygon"]:
            url = CHAIN_CONFIG[chain_name]["scan_url"]
            params = {
                "module": "token",
                "action": "tokenholderlist",
                "contractaddress": token_address,
                "page": 1,
                "offset": 10,
                "apikey": CHAIN_CONFIG[chain_name]["scan_key"]
            }
            response = requests.get(url, params=params)
            data = response.json()
            
            if data["status"] == "1":
                top10_balance = sum(float(h["value"]) for h in data["result"][:10])
                total_supply = get_total_supply(token_address, chain_name)
                return (top10_balance / total_supply) * 100 if total_supply else 50.0
                
        return 50.0  # Default if no data available
    except:
        return 50.0

def get_total_supply(token_address, chain_name):
    """Get token total supply"""
    try:
        url = CHAIN_CONFIG[chain_name]["scan_url"]
        params = {
            "module": "stats",
            "action": "tokensupply",
            "contractaddress": token_address,
            "apikey": CHAIN_CONFIG[chain_name]["scan_key"]
        }
        response = requests.get(url, params=params)
        data = response.json()
        return float(data["result"]) if data["status"] == "1" else None
    except:
        return None

def check_contract_security(w3, token_address):
    """Enhanced security checks"""
    if not w3:
        return []
    
    try:
        red_flags = []
        bytecode = w3.eth.get_code(token_address).hex()
        
        # Proxy pattern check
        if "363d3d373d3d3d363d73" in bytecode:
            red_flags.append("proxy_contract")
            
        # Selfdestruct check
        if "ff" in bytecode:
            red_flags.append("selfdestruct_capable")
            
        # Blacklisted functions check
        if "a9059cbb" in bytecode:  # transfer function
            red_flags.append("custom_transfer_logic")
            
        return red_flags
    except:
        return []

def calculate_risk_score(token_data):
    """Calculate comprehensive risk score with real data"""
    # Audit Score
    audit_score = 20 if token_data["audit_status"] == "verified" else 100
    
    # Liquidity Score (convert USD liquidity to 0-100 scale)
    liquidity_usd = token_data["liquidity_score"]
    if liquidity_usd >= 10000000:  # $10M+
        liquidity_score = 20
    elif liquidity_usd >= 1000000:  # $1M+
        liquidity_score = 40
    elif liquidity_usd >= 100000:   # $100k+
        liquidity_score = 60
    elif liquidity_usd >= 10000:    # $10k+
        liquidity_score = 80
    else:
        liquidity_score = 100
    
    # Holder Distribution Score
    holder_concentration = token_data["holder_concentration"]
    holder_score = min(100, holder_concentration * 1.5)
    
    # Security Flags
    security_flags = token_data["security_flags"]
    security_score = len(security_flags) * 20
    
    # Composite Score
    composite_score = (
        audit_score * RISK_PARAMS["weights"]["audit"] +
        liquidity_score * RISK_PARAMS["weights"]["liquidity"] +
        holder_score * RISK_PARAMS["weights"]["holders"] +
        security_score * RISK_PARAMS["weights"]["security"]
    )
    
    return min(100, composite_score)

def process_token(token_address, chain_name):
    """Process a single token with all data sources"""
    if chain_name not in CHAIN_CONFIG:
        return {
            "address": token_address,
            "chain": chain_name,
            "status": "skipped",
            "reason": "chain_not_supported"
        }
    
    try:
        w3 = get_web3_provider(chain_name)
        
        token_data = {
            "address": token_address,
            "chain": chain_name,
            "audit_status": get_contract_verification_status(token_address, chain_name),
            "liquidity_score": get_liquidity_score(token_address, chain_name),
            "holder_concentration": get_holder_distribution(token_address, chain_name),
            "security_flags": check_contract_security(w3, token_address)
        }
        
        risk_score = calculate_risk_score(token_data)
        
        return {
            "address": token_address,
            "chain": chain_name,
            "risk_score": round(risk_score, 2),
            "risk_category": (
                "Low Risk" if risk_score <= 20 else
                "Moderate" if risk_score <= 45 else
                "High Risk" if risk_score <= 70 else
                "Critical"
            ),
            "audit_status": token_data["audit_status"],
            "liquidity_usd": token_data["liquidity_score"],
            "holder_concentration": token_data["holder_concentration"],
            "security_issues": len(token_data["security_flags"])
        }
        
    except Exception as e:
        return {
            "address": token_address,
            "chain": chain_name,
            "status": "error",
            "error": str(e)
        }

def process_token_batch(input_file="tokens.csv", output_file="risk_report.csv"):
    """Process all tokens in input CSV"""
    results = []
    
    with open(input_file, "r") as f:
        reader = csv.DictReader(f)
        tokens = list(reader)
    
    print(f"Starting risk assessment for {len(tokens)} tokens...")
    
    for i, token in enumerate(tokens):
        result = process_token(token["address"], token["chain"])
        results.append(result)
        
        if "risk_score" in result:
            status = f"Score: {result['risk_score']} ({result['risk_category']})"
        else:
            status = f"Status: {result.get('status', 'error')}"
        print(f"Processed {i+1}/{len(tokens)}: {token['address']} - {status}")
        
        time.sleep(1)  # Respect API rate limits
    
    # Save results
    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False)
    print(f"Report saved to {output_file}")
    return df

if __name__ == "__main__":
    process_token_batch()
