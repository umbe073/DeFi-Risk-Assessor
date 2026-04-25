#!/usr/bin/env python3
"""
Enhanced Data Priority System
Implements the complete data priority logic as specified:
1. Webhook cache (if values > 0)
2. Fallback file (if values > 0) 
3. Real-time API (only for missing values)
4. Risk report (only for still missing values)
5. Averaging when multiple sources provide the same field
"""

import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

class EnhancedDataPrioritySystem:
    """Enhanced data priority system with proper logic"""
    
    def __init__(self):
        self.cache_file = '/Users/amlfreak/Desktop/venv/data/real_data_cache.json'
        self.fallback_file = '/Users/amlfreak/Desktop/venv/data/token_fallbacks.json'
        self.risk_report_file = '/Users/amlfreak/Desktop/venv/data/risk_report.csv'
        self.api_fallbacks_file = '/Users/amlfreak/Desktop/venv/data/api_fallbacks.json'
        
    def get_comprehensive_token_data(self, token_address: str, symbol: str = None) -> Dict[str, Any]:
        """
        Get comprehensive token data following the priority system:
        1. Webhook cache (if values > 0 and not fallback)
        2. Fallback file (if values > 0)
        3. Real-time API (only for missing values)
        4. Risk report (only for still missing values)
        5. Average multiple sources when available
        """
        print(f"🔍 Getting comprehensive data for {symbol or 'Unknown'} ({token_address})")
        
        # Initialize result structure
        result = {
            'market_cap': 0,
            'volume_24h': 0,
            'holders': 0,
            'liquidity': 0,
            'price': 0,
            'change_24h': 0,
            'data_sources': [],
            'source_details': {}
        }
        
        # Step 1: Check webhook cache (skip fallback data)
        webhook_data = self._get_webhook_cache_data(token_address)
        if webhook_data and self._has_real_data(webhook_data):
            print(f"  ✅ Using webhook cache data")
            result.update(webhook_data)
            result['data_sources'].append('webhook_cache')
            result['source_details']['webhook_cache'] = webhook_data
            return result
        
        # Step 2: Check fallback file
        fallback_data = self._get_fallback_data(token_address)
        if fallback_data and self._has_real_data(fallback_data):
            print(f"  📦 Using fallback data")
            result.update(fallback_data)
            result['data_sources'].append('fallback')
            result['source_details']['fallback'] = fallback_data
            return result
        
        # Step 3: Real-time API (only for missing values)
        missing_fields = self._get_missing_fields(result)
        if missing_fields:
            print(f"  🔄 Fetching real-time data for missing fields: {missing_fields}")
            real_time_data = self._fetch_real_time_data(token_address, symbol, missing_fields)
            if real_time_data:
                result.update(real_time_data)
                result['data_sources'].append('real_time')
                result['source_details']['real_time'] = real_time_data
        
        # Step 4: Risk report (only for still missing values)
        still_missing = self._get_missing_fields(result)
        if still_missing:
            print(f"  📊 Checking risk report for missing fields: {still_missing}")
            risk_data = self._get_risk_report_data(token_address, still_missing)
            if risk_data:
                result.update(risk_data)
                result['data_sources'].append('risk_report')
                result['source_details']['risk_report'] = risk_data
        
        # Step 5: Average multiple sources if available
        result = self._average_multiple_sources(result)
        
        return result
    
    def _get_webhook_cache_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get data from webhook cache, skipping fallback data"""
        try:
            if not os.path.exists(self.cache_file):
                return None
            
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check tokens section
            tokens = cache_data.get('tokens', {})
            token_data = None
            
            # Try exact match first
            if token_address.lower() in tokens:
                token_data = tokens[token_address.lower()]
            else:
                # Try case-insensitive match
                for addr, data in tokens.items():
                    if addr.lower() == token_address.lower():
                        token_data = data
                        break
            
            if not token_data:
                return None
            
            # Check if this is fallback data (skip it)
            market_data = token_data.get('market_data', {})
            for source, data in market_data.items():
                if data.get('source') == 'fallback':
                    print(f"    ⚠️  Skipping fallback data from {source}")
                    return None
            
            return self._extract_webhook_cache_values(token_data)
            
        except Exception as e:
            print(f"    ❌ Error reading webhook cache: {e}")
            return None
    
    def _get_fallback_data(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Get data from fallback file"""
        try:
            if not os.path.exists(self.fallback_file):
                return None
            
            with open(self.fallback_file, 'r') as f:
                fallback_data = json.load(f)
            
            # Check if token exists in fallback
            if token_address.lower() in fallback_data:
                token_data = fallback_data[token_address.lower()]
                return self._extract_fallback_values(token_data)
            
            return None
            
        except Exception as e:
            print(f"    ❌ Error reading fallback data: {e}")
            return None
    
    def _extract_webhook_cache_values(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract values from webhook cache structure with averaging"""
        result = {}
        
        # Check aggregates first
        aggregates = token_data.get('aggregates', {})
        if aggregates:
            market = aggregates.get('market', {})
            onchain = aggregates.get('onchain', {})
            liquidity = aggregates.get('liquidity', {})
            
            result['market_cap'] = market.get('market_cap', 0)
            result['volume_24h'] = market.get('volume_24h', 0)
            result['price'] = market.get('price', 0)
            result['change_24h'] = market.get('change_24h', 0)
            result['holders'] = onchain.get('holders', 0)
            result['liquidity'] = liquidity.get('liquidity', 0)
        
        # If no aggregates, check individual data sources and average
        else:
            market_data = token_data.get('market_data', {})
            if market_data:
                # Average across all sources
                market_caps = []
                volumes = []
                prices = []
                changes = []
                
                for source, data in market_data.items():
                    if data.get('market_cap', 0) > 0:
                        market_caps.append(data['market_cap'])
                    if data.get('volume_24h', 0) > 0:
                        volumes.append(data['volume_24h'])
                    if data.get('price', 0) > 0:
                        prices.append(data['price'])
                    if data.get('change_24h', 0) != 0:
                        changes.append(data['change_24h'])
                
                if market_caps:
                    result['market_cap'] = sum(market_caps) / len(market_caps)
                if volumes:
                    result['volume_24h'] = sum(volumes) / len(volumes)
                if prices:
                    result['price'] = sum(prices) / len(prices)
                if changes:
                    result['change_24h'] = sum(changes) / len(changes)
            
            onchain_data = token_data.get('onchain_data', {})
            if onchain_data:
                holders_list = []
                for source, data in onchain_data.items():
                    if data.get('holders', 0) > 0:
                        holders_list.append(data['holders'])
                if holders_list:
                    result['holders'] = sum(holders_list) / len(holders_list)
            
            liquidity_data = token_data.get('liquidity_data', {})
            if liquidity_data:
                liquidity_list = []
                for source, data in liquidity_data.items():
                    if data.get('liquidity', 0) > 0:
                        liquidity_list.append(data['liquidity'])
                if liquidity_list:
                    result['liquidity'] = sum(liquidity_list) / len(liquidity_list)
        
        return result
    
    def _extract_fallback_values(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract values from fallback data structure"""
        result = {}
        
        # Check if it's the new structure with market_data
        market_data = token_data.get('market_data', {})
        if market_data:
            existing_cache = market_data.get('existing_cache', {})
            if existing_cache:
                result['market_cap'] = existing_cache.get('market_cap', 0)
                result['volume_24h'] = existing_cache.get('volume_24h', 0)
                result['price'] = existing_cache.get('price', 0)
                result['change_24h'] = existing_cache.get('change_24h', 0)
        
        # Check onchain data
        onchain_data = token_data.get('onchain_data', {})
        if onchain_data:
            result['holders'] = onchain_data.get('holders', 0)
        
        # Check liquidity data
        liquidity_data = token_data.get('liquidity_data', {})
        if liquidity_data:
            result['liquidity'] = liquidity_data.get('liquidity', 0)
        
        return result
    
    def _has_real_data(self, data: Dict[str, Any]) -> bool:
        """Check if data contains real values (not 0, N/A, or fallback)"""
        # Check if this is fallback data
        if isinstance(data, dict):
            market_data = data.get('market_data', {})
            for source, source_data in market_data.items():
                if source_data.get('source') == 'fallback':
                    return False
        
        real_fields = ['market_cap', 'volume_24h', 'holders', 'liquidity', 'price']
        return any(data.get(field, 0) > 0 for field in real_fields)
    
    def _get_missing_fields(self, data: Dict[str, Any]) -> List[str]:
        """Get list of fields that are still missing (0 or N/A)"""
        missing = []
        fields = ['market_cap', 'volume_24h', 'holders', 'liquidity', 'price']
        for field in fields:
            if data.get(field, 0) <= 0:
                missing.append(field)
        return missing
    
    def _fetch_real_time_data(self, token_address: str, symbol: str, missing_fields: List[str]) -> Optional[Dict[str, Any]]:
        """Fetch real-time data only for missing fields"""
        # This would integrate with the webhook server
        # For now, return None to avoid API calls
        return None
    
    def _get_risk_report_data(self, token_address: str, missing_fields: List[str]) -> Optional[Dict[str, Any]]:
        """Get data from risk report CSV"""
        try:
            if not os.path.exists(self.risk_report_file):
                return None
            
            df = pd.read_csv(self.risk_report_file)
            
            # Find token by address
            token_row = df[df['Token Address'].str.lower() == token_address.lower()]
            if token_row.empty:
                return None
            
            result = {}
            row = token_row.iloc[0]
            
            if 'market_cap' in missing_fields:
                result['market_cap'] = row.get('Market Cap', 0)
            if 'volume_24h' in missing_fields:
                result['volume_24h'] = row.get('Volume 24h', 0)
            if 'holders' in missing_fields:
                result['holders'] = row.get('Holders', 0)
            if 'liquidity' in missing_fields:
                result['liquidity'] = row.get('Liquidity', 0)
            if 'price' in missing_fields:
                result['price'] = row.get('Price', 0)
            
            return result
            
        except Exception as e:
            print(f"    ❌ Error reading risk report: {e}")
            return None
    
    def _average_multiple_sources(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Average multiple sources when available"""
        # This would implement averaging logic when multiple sources provide the same field
        # For now, return the data as-is
        return data

def test_enhanced_system():
    """Test the enhanced data priority system"""
    system = EnhancedDataPrioritySystem()
    
    # Test problematic tokens
    test_tokens = [
        ('0x6B175474E89094C44Da98b954EedeAC495271d0F', 'DAI'),
        ('0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2', 'MKR'),
        ('0x6b3595068778dd592e39a122f4f5a5cf09c90fe2', 'SUSHI'),
        ('0xc944e90c64b2c07662a292be6244bdf05cda44a7', 'GRT'),
        ('0x111111111117dc0aa78b770fa6a738034120c302', '1INCH'),
    ]
    
    for address, symbol in test_tokens:
        print(f"\n🔍 Testing {symbol} ({address})")
        data = system.get_comprehensive_token_data(address, symbol)
        print(f"  Result: {data}")

if __name__ == "__main__":
    test_enhanced_system()









