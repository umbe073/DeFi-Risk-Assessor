#!/usr/bin/env python3
"""
API Implementations for DeFi Risk Assessment
Updated for 2025 with proper error handling and latest endpoints
"""

import os
import requests
import json
import time
import hashlib
import hmac
import base64
import urllib.parse
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ArkhamAPI:
    """Arkham Intelligence API implementation with API key authentication"""
    
    def __init__(self):
        self.api_key = os.getenv('ARKHAM_API_KEY')
        self.base_url = 'https://api.arkhamintelligence.com'
        self.session = requests.Session()
        
        # Set up headers with API key authentication
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'DeFi-Risk-Assessment/1.5'
        })
        
        # Add API key to headers based on Arkham's current API
        if self.api_key:
            # Use the correct header format that works
            self.session.headers.update({
                'API-Key': self.api_key
            })
    
    def _make_request(self, method: str, path: str, params: dict = None) -> requests.Response:
        """
        Make a request to Arkham API with API key authentication and timestamp
        """
        try:
            url = f"{self.base_url}{path}"
            
            # Add timestamp as header (current time in microseconds)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'DeFi-Risk-Assessment/1.5',
                'X-Timestamp': str(int(time.time() * 1_000_000))
            }
            
            # Make the request
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers, timeout=30)
            else:
                response = self.session.post(url, params=params, headers=headers, timeout=30)
            
            return response
            
        except Exception as e:
            print(f"Error making request: {e}")
            return None
    
    def get_entity_intelligence(self, address: str) -> Dict:
        """Get entity intelligence for an address using API key authentication"""
        try:
            if not self.api_key:
                return {'error': 'API key not configured'}
            
            # Try different endpoint paths based on current Arkham API
            paths = [
                f"/intelligence/address/{address}",
                f"/intelligence/entity/{address}",
                f"/api/v1/address/{address}",
                f"/api/v1/entity/{address}",
                f"/intelligence/address?address={address}",
                f"/intelligence/entity?address={address}"
            ]
            
            for path in paths:
                try:
                    response = self._make_request('GET', path)
                    
                    if response is None:
                        continue
                    
                    if response.status_code == 200:
                        data = response.json()
                        return self._parse_entity_data(data)
                    elif response.status_code == 401:
                        error_text = response.text.lower()
                        if 'please sign up for an api key' in error_text:
                            return {'error': 'API key not activated - please sign up and activate your API key at Arkham Intelligence'}
                        else:
                            return {'error': 'Invalid API key - please check your API key'}
                    elif response.status_code == 403:
                        return {'error': 'Access forbidden - check API key permissions'}
                    elif response.status_code == 429:
                        return {'error': 'Rate limit exceeded - try again later'}
                    elif response.status_code == 400:
                        error_text = response.text.lower()
                        if 'invalid timestamp format' in error_text:
                            return {'error': 'API requires timestamp authentication - check Arkham documentation'}
                        else:
                            print(f"Debug: {path} returned 400: {response.text[:100]}")
                            continue
                    elif response.status_code == 404:
                        continue  # Try next endpoint
                    else:
                        print(f"Debug: {path} returned {response.status_code}")
                        continue
                        
                except requests.exceptions.Timeout:
                    continue
                except requests.exceptions.RequestException:
                    continue
                except Exception as e:
                    print(f"Error with {path}: {e}")
                    continue
            
            # If all endpoints fail, return error
            return {'error': 'No valid endpoint found - API may be temporarily unavailable'}
                
        except Exception as e:
            return {'error': f'Unexpected error: {str(e)}'}
    
    def get_address_labels(self, address: str) -> Dict:
        """Get address labels and metadata using API key authentication"""
        try:
            if not self.api_key:
                return {'error': 'API key not configured'}
            
            # Try different endpoint paths
            paths = [
                f"/intelligence/address/{address}/labels",
                f"/api/v1/address/{address}/labels",
                f"/labels/{address}",
                f"/api/v1/labels/{address}"
            ]
            
            for path in paths:
                try:
                    response = self._make_request('GET', path)
                    
                    if response is None:
                        continue
                    
                    if response.status_code == 200:
                        data = response.json()
                        return self._parse_address_data(data)
                    elif response.status_code == 401:
                        error_text = response.text.lower()
                        if 'please sign up for an api key' in error_text:
                            return {'error': 'API key not activated - please sign up and activate your API key at Arkham Intelligence'}
                        else:
                            return {'error': 'Invalid API key - please check your API key'}
                    elif response.status_code == 429:
                        return {'error': 'Rate limit exceeded - try again later'}
                    elif response.status_code == 400:
                        error_text = response.text.lower()
                        if 'invalid timestamp format' in error_text:
                            return {'error': 'API requires timestamp authentication - check Arkham documentation'}
                        else:
                            print(f"Debug: {path} returned 400: {response.text[:100]}")
                            continue
                    elif response.status_code == 404:
                        continue  # Try next endpoint
                    else:
                        print(f"Debug: {path} returned {response.status_code}")
                        continue
                        
                except requests.exceptions.Timeout:
                    continue
                except requests.exceptions.RequestException:
                    continue
                except Exception as e:
                    print(f"Error with {path}: {e}")
                    continue
            
            # If all endpoints fail, return error
            return {'error': 'No valid endpoint found'}
                
        except Exception as e:
            return {'error': f'Unexpected error: {str(e)}'}
    
    def get_risk_score(self, address: str) -> Dict:
        """Get comprehensive risk score for an address"""
        try:
            if not self.api_key:
                return {'error': 'API key not configured'}
            
            # Try to get entity intelligence
            entity_data = self.get_entity_intelligence(address)
            
            # Try to get address labels
            label_data = self.get_address_labels(address)
            
            # If both fail, return a basic risk assessment
            if 'error' in entity_data and 'error' in label_data:
                return {
                    'error': 'Unable to fetch data from Arkham API',
                    'risk_score': 5.0,
                    'risk_factors': ['API endpoint not available'],
                    'fallback': True
                }
            
            # Combine and calculate risk score
            risk_data = {
                'entity_intelligence': entity_data if 'error' not in entity_data else {},
                'address_labels': label_data if 'error' not in label_data else {},
                'risk_score': self._calculate_risk_score(entity_data, label_data),
                'risk_factors': self._identify_risk_factors(entity_data, label_data)
            }
            
            return risk_data
            
        except Exception as e:
            return {'error': f'Risk assessment failed: {str(e)}'}
    
    def _parse_entity_data(self, data: Dict) -> Dict:
        """Parse entity intelligence data from Arkham API response"""
        try:
            # Handle the actual Arkham API response format
            if 'arkhamEntity' in data:
                entity = data['arkhamEntity']
                return {
                    'entity_name': entity.get('name', 'Unknown'),
                    'entity_type': entity.get('type', 'Unknown'),
                    'risk_level': 'Low' if entity.get('type') == 'stablecoin' else 'Medium',
                    'tags': [entity.get('type', '')] if entity.get('type') else [],
                    'description': entity.get('note', ''),
                    'last_updated': '',
                    'confidence_score': 0.8 if entity.get('name') else 0.3,
                    'website': entity.get('website', ''),
                    'twitter': entity.get('twitter', ''),
                    'entity_id': entity.get('id', '')
                }
            elif 'arkhamLabel' in data:
                label = data['arkhamLabel']
                return {
                    'entity_name': label.get('name', 'Unknown'),
                    'entity_type': 'Contract' if data.get('contract') else 'Address',
                    'risk_level': 'Low' if 'stablecoin' in label.get('name', '').lower() else 'Medium',
                    'tags': ['contract'] if data.get('contract') else ['address'],
                    'description': f"Chain: {data.get('chain', 'Unknown')}",
                    'last_updated': '',
                    'confidence_score': 0.9,
                    'chain': data.get('chain', ''),
                    'chain_type': label.get('chainType', '')
                }
            else:
                return {
                    'entity_name': 'Unknown',
                    'entity_type': 'Unknown',
                    'risk_level': 'Unknown',
                    'tags': [],
                    'description': '',
                    'last_updated': '',
                    'confidence_score': 0
                }
        except Exception as e:
            return {'error': f'Failed to parse entity data: {str(e)}'}
    
    def _parse_address_data(self, data: Dict) -> Dict:
        """Parse address data"""
        try:
            return {
                'address': data.get('address', ''),
                'labels': data.get('labels', []),
                'metadata': data.get('metadata', {}),
                'risk_indicators': data.get('risk_indicators', []),
                'last_activity': data.get('last_activity', ''),
                'total_volume': data.get('total_volume', 0)
            }
        except Exception:
            return {'error': 'Failed to parse address data'}
    
    def _calculate_risk_score(self, entity_data: Dict, label_data: Dict) -> float:
        """Calculate risk score from entity and label data"""
        try:
            score = 5.0  # Base score
            
            # Entity risk factors
            if 'error' not in entity_data:
                risk_level = entity_data.get('risk_level', 'Unknown').lower()
                if risk_level == 'high':
                    score += 3.0
                elif risk_level == 'medium':
                    score += 1.5
                elif risk_level == 'low':
                    score -= 1.0
            
            # Label risk factors
            if 'error' not in label_data:
                labels = label_data.get('labels', [])
                risk_indicators = label_data.get('risk_indicators', [])
                
                # High-risk labels
                high_risk_labels = ['mixer', 'tornado', 'sanctions', 'scam', 'hack']
                for label in labels:
                    if any(risk in label.lower() for risk in high_risk_labels):
                        score += 2.0
                
                # Risk indicators
                score += len(risk_indicators) * 0.5
            
            return max(1.0, min(10.0, score))
            
        except Exception:
            return 5.0
    
    def _identify_risk_factors(self, entity_data: Dict, label_data: Dict) -> List[str]:
        """Identify specific risk factors"""
        risk_factors = []
        
        try:
            # Entity-based risks
            if 'error' not in entity_data:
                risk_level = entity_data.get('risk_level', 'Unknown')
                if risk_level.lower() == 'high':
                    risk_factors.append('High-risk entity')
                
                tags = entity_data.get('tags', [])
                for tag in tags:
                    if any(risk in tag.lower() for risk in ['mixer', 'sanctions', 'scam']):
                        risk_factors.append(f'Risk tag: {tag}')
            
            # Label-based risks
            if 'error' not in label_data:
                labels = label_data.get('labels', [])
                for label in labels:
                    if any(risk in label.lower() for risk in ['mixer', 'tornado', 'sanctions']):
                        risk_factors.append(f'Risk label: {label}')
                
                risk_indicators = label_data.get('risk_indicators', [])
                for indicator in risk_indicators:
                    risk_factors.append(f'Risk indicator: {indicator}')
                
        except Exception:
            risk_factors.append('Error analyzing risk factors')
        
        return risk_factors

class BreadcrumbsAPI:
    """Breadcrumbs API implementation for sanctions compliance"""
    
    def __init__(self):
        self.api_key = os.getenv('BREADCRUMBS_API_KEY')
        self.base_url = 'https://api.breadcrumbs.one'
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-KEY': self.api_key,
            'Accept': 'application/json',
            'User-Agent': 'DeFi-Risk-Assessment/1.5'
        })
    
    def check_sanctions(self, address: str, chain: str = 'ETH') -> Dict:
        """Check if address is on sanctions list"""
        try:
            if not self.api_key:
                return {'error': 'API key not configured'}
            
            # Try different endpoint formats
            endpoints = [
                f"{self.base_url}/sanctions/address?chain={chain}&address={address}",
                f"{self.base_url}/api/v1/sanctions/address?chain={chain}&address={address}",
                f"{self.base_url}/check/{chain}/{address}",
                f"{self.base_url}/api/v1/check/{chain}/{address}"
            ]
            
            for url in endpoints:
                try:
                    response = self.session.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        return self._parse_sanctions_data(data)
                    elif response.status_code == 401:
                        return {'error': 'Invalid API key'}
                    elif response.status_code == 403:
                        return {'error': 'Access forbidden - check API key permissions'}
                    elif response.status_code == 429:
                        return {'error': 'Rate limit exceeded'}
                    elif response.status_code == 404:
                        continue  # Try next endpoint
                    else:
                        print(f"Debug: {url} returned {response.status_code}")
                        continue
                        
                except requests.exceptions.Timeout:
                    continue
                except requests.exceptions.RequestException:
                    continue
            
            # If all endpoints fail, return error
            return {'error': 'No valid endpoint found'}
                
        except Exception as e:
            return {'error': f'Unexpected error: {str(e)}'}
    
    def get_address_risk(self, address: str, chain: str = 'ETH') -> Dict:
        """Get comprehensive risk assessment for an address"""
        try:
            if not self.api_key:
                return {'error': 'API key not configured'}
            
            # Check sanctions
            sanctions_data = self.check_sanctions(address, chain)
            
            # If sanctions check fails, return basic assessment
            if 'error' in sanctions_data:
                return {
                    'error': 'Unable to fetch data from Breadcrumbs API',
                    'risk_score': 5.0,
                    'risk_factors': ['API endpoint not available'],
                    'fallback': True
                }
            
            # Get additional risk data
            risk_data = self._get_additional_risk_data(address, chain)
            
            # Combine data
            comprehensive_data = {
                'sanctions_check': sanctions_data,
                'risk_assessment': risk_data,
                'overall_risk_score': self._calculate_overall_risk(sanctions_data, risk_data),
                'risk_factors': self._identify_risk_factors(sanctions_data, risk_data)
            }
            
            return comprehensive_data
            
        except Exception as e:
            return {'error': f'Risk assessment failed: {str(e)}'}
    
    def _parse_sanctions_data(self, data: Dict) -> Dict:
        """Parse sanctions check data"""
        try:
            return {
                'is_sanctioned': data.get('is_sanctioned', False),
                'sanction_lists': data.get('sanction_lists', []),
                'risk_level': data.get('risk_level', 'Unknown'),
                'last_checked': data.get('last_checked', ''),
                'confidence': data.get('confidence', 0),
                'details': data.get('details', {})
            }
        except Exception:
            return {'error': 'Failed to parse sanctions data'}
    
    def _get_additional_risk_data(self, address: str, chain: str) -> Dict:
        """Get additional risk data for the address"""
        try:
            # This would include additional endpoints if available
            # For now, return basic structure
            return {
                'transaction_count': 0,
                'total_volume': 0,
                'risk_indicators': [],
                'compliance_status': 'Unknown'
            }
        except Exception:
            return {'error': 'Failed to get additional risk data'}
    
    def _calculate_overall_risk(self, sanctions_data: Dict, risk_data: Dict) -> float:
        """Calculate overall risk score"""
        try:
            score = 5.0  # Base score
            
            # Sanctions risk
            if sanctions_data.get('is_sanctioned', False):
                score += 4.0
            
            risk_level = sanctions_data.get('risk_level', 'Unknown').lower()
            if risk_level == 'high':
                score += 2.0
            elif risk_level == 'medium':
                score += 1.0
            elif risk_level == 'low':
                score -= 0.5
            
            # Additional risk factors
            risk_indicators = risk_data.get('risk_indicators', [])
            score += len(risk_indicators) * 0.5
            
            return max(1.0, min(10.0, score))
            
        except Exception:
            return 5.0
    
    def _identify_risk_factors(self, sanctions_data: Dict, risk_data: Dict) -> List[str]:
        """Identify specific risk factors"""
        risk_factors = []
        
        try:
            # Sanctions-based risks
            if sanctions_data.get('is_sanctioned', False):
                risk_factors.append('Address on sanctions list')
            
            sanction_lists = sanctions_data.get('sanction_lists', [])
            for list_name in sanction_lists:
                risk_factors.append(f'Listed on: {list_name}')
            
            risk_level = sanctions_data.get('risk_level', 'Unknown')
            if risk_level.lower() == 'high':
                risk_factors.append('High risk level')
            
            # Additional risk factors
            risk_indicators = risk_data.get('risk_indicators', [])
            for indicator in risk_indicators:
                risk_factors.append(f'Risk indicator: {indicator}')
                
        except Exception:
            risk_factors.append('Error analyzing risk factors')
        
        return risk_factors

def test_arkham_api():
    """Test Arkham API functionality"""
    print("🧪 Testing Arkham API...")
    
    arkham = ArkhamAPI()
    
    # Test with a known address (USDT)
    test_address = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    
    print(f"Testing address: {test_address}")
    
    # Test entity intelligence
    print("\n1. Testing entity intelligence...")
    entity_data = arkham.get_entity_intelligence(test_address)
    print(f"Result: {entity_data}")
    
    # Test address labels
    print("\n2. Testing address labels...")
    label_data = arkham.get_address_labels(test_address)
    print(f"Result: {label_data}")
    
    # Test risk score
    print("\n3. Testing risk score...")
    risk_data = arkham.get_risk_score(test_address)
    print(f"Result: {risk_data}")

def test_breadcrumbs_api():
    """Test Breadcrumbs API functionality"""
    print("🧪 Testing Breadcrumbs API...")
    
    breadcrumbs = BreadcrumbsAPI()
    
    # Test with a known address (USDT)
    test_address = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    
    print(f"Testing address: {test_address}")
    
    # Test sanctions check
    print("\n1. Testing sanctions check...")
    sanctions_data = breadcrumbs.check_sanctions(test_address)
    print(f"Result: {sanctions_data}")
    
    # Test risk assessment
    print("\n2. Testing risk assessment...")
    risk_data = breadcrumbs.get_address_risk(test_address)
    print(f"Result: {risk_data}")

if __name__ == "__main__":
    print("🚀 Testing API Implementations")
    print("=" * 50)
    
    test_arkham_api()
    print("\n" + "=" * 50)
    test_breadcrumbs_api()
