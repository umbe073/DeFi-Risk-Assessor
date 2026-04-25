#!/usr/bin/env python3
"""
Dune Analytics API Integration
This module provides comprehensive access to SIM Dune API endpoints
"""

import requests
import json
import os
from typing import Dict, List, Optional, Union
from datetime import datetime
import time

class DuneAnalyticsAPI:
    """SIM Dune API client for fetching blockchain data"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize SIM Dune API client."""
        self.base_url = (os.getenv("DUNE_SIM_BASE_URL") or "https://api.sim.dune.com/v1").rstrip("/")
        self.api_key = api_key or self._load_api_key()
        self.session = requests.Session()
        
        if self.api_key:
            self.session.headers.update({
                'X-Sim-Api-Key': self.api_key,
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
    
    def _load_api_key(self) -> Optional[str]:
        """Load API key from .env file"""
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('DUNE_API_KEY='):
                            return line.strip().split('=', 1)[1].strip('"\'')
        except Exception as e:
            print(f"Warning: Could not load SIM Dune API key from .env: {e}")
        return None

    def _normalize_chain_ids(self, chain_ids: Union[str, int, List[int]]) -> str:
        """SIM Dune endpoints require a single chain_id value."""
        if isinstance(chain_ids, int):
            return str(chain_ids)
        if isinstance(chain_ids, list):
            if not chain_ids:
                return "1"
            return str(chain_ids[0])
        text = str(chain_ids or "1").strip()
        if text.lower() in {"all", "any"}:
            return "1"
        if "," in text:
            text = text.split(",", 1)[0].strip()
        return text or "1"
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make API request to Dune Analytics
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {"error": str(e)}
    
    def get_activity(self, uri: str, chain_ids: Union[str, int, List[int]] = 1,
                    offset: Optional[str] = None, limit: int = 20) -> Dict:
        """Get EVM activity for a given address."""
        params: Dict[str, int | str] = {"limit": min(limit, 100)}
        params["chain_ids"] = self._normalize_chain_ids(chain_ids)
        if offset:
            params["offset"] = offset
            
        return self._make_request(f"/evm/activity/{uri}", params)
    
    def get_token_holders(self, chain_id: int, token_address: str,
                         limit: int = 500, offset: Optional[str] = None) -> Dict:
        """Get token holders for a specific token."""
        params: Dict[str, int | str] = {"limit": min(limit, 500)}
        if offset:
            params["offset"] = offset
            
        return self._make_request(f"/evm/token-holders/{chain_id}/{token_address}", params)
    
    def get_token_info(self, uri: str, chain_ids: Union[str, int, List[int]] = 1,
                      historical_prices: Optional[Union[int, List[int]]] = None,
                      limit: Optional[int] = None, offset: Optional[str] = None) -> Dict:
        """Get token information and metadata."""
        params: Dict[str, int | str] = {"chain_ids": self._normalize_chain_ids(chain_ids)}
        
        if historical_prices:
            if isinstance(historical_prices, list):
                params["historical_prices"] = ",".join(map(str, historical_prices[:3]))
            else:
                params["historical_prices"] = str(historical_prices)
        
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
            
        return self._make_request(f"/evm/token-info/{uri}", params)
    
    def get_balances(self, uri: str, chain_ids: Union[str, int, List[int]] = 1,
                    limit: Optional[int] = None, offset: Optional[str] = None) -> Dict:
        """Get token balances for a wallet address."""
        params: Dict[str, int | str] = {"chain_ids": self._normalize_chain_ids(chain_ids)}
        
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
            
        return self._make_request(f"/evm/balances/{uri}", params)
    
    def get_transactions(self, uri: str, chain_ids: Union[str, int, List[int]] = 1,
                        limit: Optional[int] = None, offset: Optional[str] = None) -> Dict:
        """Get transaction history for a wallet address."""
        params: Dict[str, int | str] = {"chain_ids": self._normalize_chain_ids(chain_ids)}
        
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
            
        return self._make_request(f"/evm/transactions/{uri}", params)
    
    def get_collectibles(self, uri: str, chain_ids: Union[str, int, List[int]] = 1,
                        limit: Optional[int] = None, offset: Optional[str] = None) -> Dict:
        """Get NFT/collectible data for a wallet address."""
        params: Dict[str, int | str] = {"chain_ids": self._normalize_chain_ids(chain_ids)}
        
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
            
        return self._make_request(f"/evm/collectibles/{uri}", params)

# Utility functions for common use cases
def get_wallet_activity(wallet_address: str, api_key: Optional[str] = None, limit: int = 20) -> Dict:
    """Get recent activity for a wallet address"""
    api = DuneAnalyticsAPI(api_key)
    return api.get_activity(wallet_address, limit=limit)

def get_token_holder_analysis(token_address: str, chain_id: int = 8453, 
                             api_key: Optional[str] = None, limit: int = 100) -> Dict:
    """Get token holder analysis for a specific token"""
    api = DuneAnalyticsAPI(api_key)
    return api.get_token_holders(chain_id, token_address, limit=limit)

def get_token_market_data(token_address: str, api_key: Optional[str] = None) -> Dict:
    """Get comprehensive token market data"""
    api = DuneAnalyticsAPI(api_key)
    return api.get_token_info(token_address, chain_ids=1)

def get_wallet_portfolio(wallet_address: str, api_key: Optional[str] = None) -> Dict:
    """Get complete wallet portfolio including balances and transactions"""
    api = DuneAnalyticsAPI(api_key)
    
    portfolio = {
        "wallet_address": wallet_address,
        "balances": api.get_balances(wallet_address),
        "transactions": api.get_transactions(wallet_address, limit=50),
        "activity": api.get_activity(wallet_address, limit=20),
        "collectibles": api.get_collectibles(wallet_address)
    }
    
    return portfolio

# Example usage and testing
if __name__ == "__main__":
    # Test the API integration
    api = DuneAnalyticsAPI()
    
    if not api.api_key:
        print("Warning: No SIM Dune API key found. Please set DUNE_API_KEY in your .env file")
        print("Example usage:")
        print("1. get_wallet_activity('0x1234...')")
        print("2. get_token_holder_analysis('0x5678...')")
        print("3. get_token_market_data('0x9abc...')")
        print("4. get_wallet_portfolio('0xdef0...')")
    else:
        print("✅ SIM Dune API initialized successfully")
        print("Available functions:")
        print("- get_wallet_activity(wallet_address)")
        print("- get_token_holder_analysis(token_address, chain_id)")
        print("- get_token_market_data(token_address)")
        print("- get_wallet_portfolio(wallet_address)")


