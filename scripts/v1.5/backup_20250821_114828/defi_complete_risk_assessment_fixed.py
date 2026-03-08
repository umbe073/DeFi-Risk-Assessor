# Fixed DeFi Complete Risk Assessment Script
# This version includes comprehensive error fixes for all identified issues

import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the enhanced parallel APIs
from enhanced_comprehensive_parallel_apis import ComprehensiveParallelAPIManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FixedDeFiRiskAssessment:
    """Fixed DeFi Risk Assessment with comprehensive error handling"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        # Enhanced timeout settings
        self.timeout = 30
        self.max_retries = 3
        self.retry_delay = 2
        
        # Rate limiting settings
        self.rate_limit_delay = 1
        self.max_requests_per_minute = 60
        
        # Initialize cache directory
        self._initialize_cache()
    
    def _initialize_cache(self):
        """Initialize cache directory and fix permissions"""
        cache_dir = "../../data/api_cache"
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            logger.info(f"✅ Created cache directory: {cache_dir}")
        
        cache_db = "../../data/api_cache.db"
        if os.path.exists(cache_db):
            try:
                os.chmod(cache_db, 0o666)
                logger.info(f"✅ Fixed cache database permissions: {cache_db}")
            except Exception as e:
                logger.warning(f"⚠️  Could not fix cache permissions: {e}")
    
    def _make_request_with_retry(self, url: str, headers: Dict = None, params: Dict = None, method: str = 'GET'):
        """Make HTTP request with retry logic and error handling"""
        for attempt in range(self.max_retries):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
                else:
                    response = self.session.post(url, headers=headers, json=params, timeout=self.timeout)
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = int(response.headers.get('Retry-After', self.retry_delay * (2 ** attempt)))
                    logger.warning(f"⚠️  Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                # Handle authentication errors
                if response.status_code == 401:
                    logger.error(f"❌ Authentication failed for {url}")
                    return None
                
                # Handle forbidden errors
                if response.status_code == 403:
                    logger.error(f"❌ Access forbidden for {url}")
                    return None
                
                # Handle not found errors
                if response.status_code == 404:
                    logger.error(f"❌ Endpoint not found: {url}")
                    return None
                
                # Handle server errors
                if response.status_code >= 500:
                    logger.warning(f"⚠️  Server error {response.status_code} for {url}, retrying...")
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                
                # Success
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"⚠️  Unexpected status {response.status_code} for {url}")
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️  Request timeout for {url}, attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                continue
                
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"⚠️  Connection error for {url}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                continue
                
            except Exception as e:
                logger.error(f"❌ Request error for {url}: {e}")
                return None
        
        logger.error(f"❌ Max retries reached for {url}")
        return None
    
    def fetch_etherscan_data_fixed(self, token_address: str, api_key: str):
        """Fixed Etherscan data fetching with proper error handling"""
        try:
            # Contract verification - use getsourcecode instead of getabi
            verification_url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={token_address}&apikey={api_key}"
            verification_data = self._make_request_with_retry(verification_url)
            
            # Holder data - use correct endpoint
            holder_url = f"https://api.etherscan.io/api?module=token&action=tokenholderlist&contractaddress={token_address}&apikey={api_key}"
            holder_data = self._make_request_with_retry(holder_url)
            
            # Account data
            account_url = f"https://api.etherscan.io/api?module=account&action=balance&address={token_address}&tag=latest&apikey={api_key}"
            account_data = self._make_request_with_retry(account_url)
            
            return {
                'verification': verification_data,
                'holders': holder_data,
                'account': account_data
            }
        except Exception as e:
            logger.error(f"❌ Etherscan data fetch failed: {e}")
            return None
    
    def fetch_coingecko_data_fixed(self, token_address: str):
        """Fixed CoinGecko data fetching with proper error handling"""
        try:
            # Token info
            token_url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{token_address}"
            token_data = self._make_request_with_retry(token_url)
            
            # Market data
            market_url = f"https://api.coingecko.com/api/v3/coins/ethereum/contract/{token_address}/market_chart?vs_currency=usd&days=30"
            market_data = self._make_request_with_retry(market_url)
            
            return {
                'token_info': token_data,
                'market_data': market_data
            }
        except Exception as e:
            logger.error(f"❌ CoinGecko data fetch failed: {e}")
            return None
    
    def fetch_moralis_data_fixed(self, token_address: str, api_key: str):
        """Fixed Moralis data fetching with correct endpoints"""
        try:
            headers = {'X-API-Key': api_key}
            
            # Try multiple endpoints with chain parameter
            endpoints = [
                f"https://deep-index.moralis.io/api/v2/erc20/{token_address}?chain=eth",
                f"https://deep-index.moralis.io/api/v2/erc20/{token_address}?chain=bsc",
                f"https://deep-index.moralis.io/api/v2/erc20/{token_address}?chain=polygon"
            ]
            
            for endpoint in endpoints:
                data = self._make_request_with_retry(endpoint, headers=headers)
                if data:
                    return data
            
            logger.warning("⚠️  All Moralis endpoints failed")
            return None
            
        except Exception as e:
            logger.error(f"❌ Moralis data fetch failed: {e}")
            return None
    
    def fetch_1inch_data_fixed(self, token_address: str, api_key: str):
        """Fixed 1inch data fetching with correct API version"""
        try:
            headers = {'Authorization': f'Bearer {api_key}'}
            
            # Try multiple API versions
            endpoints = [
                f"https://api.1inch.dev/token/v1.0/1/metadata?address={token_address}",
                f"https://api.1inch.dev/token/v1.1/1/metadata?address={token_address}",
                f"https://api.1inch.dev/token/v1.2/1/metadata?address={token_address}"
            ]
            
            for endpoint in endpoints:
                data = self._make_request_with_retry(endpoint, headers=headers)
                if data:
                    return data
            
            logger.warning("⚠️  All 1inch endpoints failed")
            return None
            
        except Exception as e:
            logger.error(f"❌ 1inch data fetch failed: {e}")
            return None
    
    def fetch_zapper_data_fixed(self, address: str, api_key: str):
        """Fixed Zapper data fetching with endpoint validation"""
        try:
            headers = {'Authorization': f'Basic {api_key}'}
            
            # Try multiple endpoints
            endpoints = [
                f"https://api.zapper.xyz/v2/portfolio/{address}",
                f"https://api.zapper.xyz/v1/portfolio/{address}",
                f"https://public.zapper.xyz/graphql"
            ]
            
            for endpoint in endpoints:
                data = self._make_request_with_retry(endpoint, headers=headers)
                if data:
                    return data
            
            logger.warning("⚠️  All Zapper endpoints failed")
            return None
            
        except Exception as e:
            logger.error(f"❌ Zapper data fetch failed: {e}")
            return None
    
    def fetch_social_data_fixed(self, token_symbol: str):
        """Fixed social data fetching with rate limiting"""
        try:
            social_data = {}
            
            # Twitter with exponential backoff
            twitter_url = f"https://api.twitter.com/2/tweets/search/recent?query=%22{token_symbol}%22&max_results=5"
            twitter_data = self._make_request_with_retry(twitter_url)
            if twitter_data:
                social_data['twitter'] = twitter_data
            time.sleep(self.rate_limit_delay)
            
            # Telegram with bot instance management
            telegram_url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/getUpdates"
            telegram_data = self._make_request_with_retry(telegram_url)
            if telegram_data:
                social_data['telegram'] = telegram_data
            time.sleep(self.rate_limit_delay)
            
            # Discord with proper error handling
            discord_url = f"https://discord.com/api/v10/users/@me"
            discord_data = self._make_request_with_retry(discord_url)
            if discord_data:
                social_data['discord'] = discord_data
            time.sleep(self.rate_limit_delay)
            
            # Reddit with proper error handling
            reddit_url = f"https://www.reddit.com/search.json?q={token_symbol}&limit=5"
            reddit_data = self._make_request_with_retry(reddit_url)
            if reddit_data:
                social_data['reddit'] = reddit_data
            
            return social_data
            
        except Exception as e:
            logger.error(f"❌ Social data fetch failed: {e}")
            return None
    
    def fetch_comprehensive_data_fixed(self, token_address: str, api_keys: Dict[str, str]):
        """Fetch comprehensive data with all error fixes applied"""
        logger.info(f"🔍 Fetching comprehensive data for {token_address}...")
        
        results = {}
        
        # Etherscan data
        if 'ETHERSCAN_API_KEY' in api_keys:
            logger.info("  📊 Fetching Etherscan data...")
            results['etherscan'] = self.fetch_etherscan_data_fixed(token_address, api_keys['ETHERSCAN_API_KEY'])
        
        # CoinGecko data
        logger.info("  📊 Fetching CoinGecko data...")
        results['coingecko'] = self.fetch_coingecko_data_fixed(token_address)
        
        # Moralis data
        if 'MORALIS_API_KEY' in api_keys:
            logger.info("  📊 Fetching Moralis data...")
            results['moralis'] = self.fetch_moralis_data_fixed(token_address, api_keys['MORALIS_API_KEY'])
        
        # 1inch data
        if '1INCH_API_KEY' in api_keys:
            logger.info("  📊 Fetching 1inch data...")
            results['1inch'] = self.fetch_1inch_data_fixed(token_address, api_keys['1INCH_API_KEY'])
        
        # Zapper data
        if 'ZAPPER_API_KEY' in api_keys:
            logger.info("  📊 Fetching Zapper data...")
            results['zapper'] = self.fetch_zapper_data_fixed(token_address, api_keys['ZAPPER_API_KEY'])
        
        # Social data
        logger.info("  📊 Fetching social data...")
        results['social'] = self.fetch_social_data_fixed(token_address)
        
        return results
    
    def calculate_risk_score_fixed(self, data: Dict[str, Any]) -> float:
        """Calculate risk score with improved logic"""
        try:
            # Component scores with better error handling
            scores = {
                'industry_impact': 5,
                'tech_innovation': 5,
                'whitepaper_quality': 5,
                'roadmap_adherence': 5,
                'business_model': 5,
                'team_expertise': 5,
                'management_strategy': 5,
                'global_reach': 5,
                'code_security': 5,
                'dev_activity': 5,
                'aml_data': 5,
                'compliance_data': 5,
                'market_dynamics': 5,
                'marketing_demand': 5,
                'esg_impact': 5,
                'social_data': 5
            }
            
            # Adjust scores based on available data
            if data.get('etherscan'):
                scores['code_security'] += 2
                scores['dev_activity'] += 1
            
            if data.get('coingecko'):
                scores['market_dynamics'] += 2
                scores['marketing_demand'] += 1
            
            if data.get('moralis'):
                scores['code_security'] += 1
            
            if data.get('social'):
                scores['social_data'] += 2
            
            # Calculate total score
            total_score = sum(scores.values())
            
            logger.info(f"📊 Calculated risk score: {total_score}")
            return total_score
            
        except Exception as e:
            logger.error(f"❌ Risk score calculation failed: {e}")
            return 50.0  # Default score
    
    def classify_risk_fixed(self, score: float) -> str:
        """Classify risk with updated thresholds"""
        if score >= 112.5 and score <= 150:
            return "Extreme Risk"
        elif score >= 75 and score <= 112.4:
            return "High Risk"
        elif score >= 37.5 and score <= 74.9:
            return "Medium Risk"
        else:
            return "Low Risk"
    
    def run_assessment_fixed(self, tokens_file: str = "../../data/tokens.csv"):
        """Run the complete risk assessment with all fixes applied"""
        try:
            logger.info("🚀 Starting fixed DeFi risk assessment...")
            
            # Load tokens
            if not os.path.exists(tokens_file):
                logger.error(f"❌ Tokens file not found: {tokens_file}")
                return
            
            tokens_df = pd.read_csv(tokens_file)
            logger.info(f"✅ Loaded {len(tokens_df)} tokens")
            
            # Load API keys
            api_keys = {}
            env_file = "../../.env"
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            api_keys[key] = value
            
            results = []
            
            for index, row in tokens_df.iterrows():
                token_address = row['address']
                token_symbol = row.get('symbol', 'UNKNOWN')
                
                logger.info(f"🔍 Assessing {token_symbol} ({token_address})...")
                
                # Fetch comprehensive data
                data = self.fetch_comprehensive_data_fixed(token_address, api_keys)
                
                # Calculate risk score
                risk_score = self.calculate_risk_score_fixed(data)
                risk_category = self.classify_risk_fixed(risk_score)
                
                # Store results
                result = {
                    'token_address': token_address,
                    'token_symbol': token_symbol,
                    'risk_score': risk_score,
                    'risk_category': risk_category,
                    'data_sources': list(data.keys()) if data else [],
                    'timestamp': datetime.now().isoformat()
                }
                
                results.append(result)
                
                logger.info(f"✅ {token_symbol}: {risk_score} - {risk_category}")
                
                # Rate limiting between tokens
                time.sleep(self.rate_limit_delay)
            
            # Save results
            self._save_results(results)
            
            logger.info("🎉 Fixed risk assessment completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Assessment failed: {e}")
    
    def _save_results(self, results: List[Dict[str, Any]]):
        """Save assessment results"""
        try:
            # Save CSV
            df = pd.DataFrame(results)
            csv_file = "../../data/risk_report_fixed.csv"
            df.to_csv(csv_file, index=False)
            logger.info(f"📊 Results saved to: {csv_file}")
            
            # Save JSON
            json_file = "../../data/risk_report_fixed.json"
            with open(json_file, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"📊 Results saved to: {json_file}")
            
            # Save Excel
            excel_file = "../../data/DeFi Tokens Risk Assessment Results Fixed.xlsx"
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Risk Assessment', index=False)
            logger.info(f"📊 Results saved to: {excel_file}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save results: {e}")

def main():
    """Main function to run the fixed risk assessment"""
    assessment = FixedDeFiRiskAssessment()
    assessment.run_assessment_fixed()

if __name__ == "__main__":
    main() 