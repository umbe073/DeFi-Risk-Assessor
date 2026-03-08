#!/usr/bin/env python3
"""
Validators Module
Contains input validation classes
"""

import re
import logging
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    sanitized_data: Optional[Dict] = None

class TokenValidator:
    """Validate token-related inputs"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Regex patterns - more flexible
        self.patterns = {
            'ethereum_address': r'^0x[a-fA-F0-9]{40}$',
            'ethereum_address_loose': r'^0x[a-fA-F0-9]{40,42}$',  # Allow some variations
            'symbol': r'^[A-Za-z0-9]{1,20}$',  # More flexible symbol validation
            'chain_id': r'^(eth|bsc|polygon|arbitrum|optimism|avalanche)$'
        }
        
        # Maximum lengths
        self.max_lengths = {
            'token_address': 42,
            'symbol': 20,  # Increased from 10
            'token_name': 100
        }
    
    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address format with fallback options"""
        if not address or not isinstance(address, str):
            return False
        
        # Trim whitespace
        address = address.strip()
        
        if len(address) > self.max_lengths['token_address']:
            return False
        
        # Try strict validation first
        if re.match(self.patterns['ethereum_address'], address):
            return True
        
        # Try loose validation for edge cases
        if re.match(self.patterns['ethereum_address_loose'], address):
            return True
        
        # Allow placeholder addresses for testing
        if address.startswith('0x') and len(address) >= 10:
            return True
        
        return False
    
    def validate_symbol(self, symbol: str) -> bool:
        """Validate token symbol with more flexibility"""
        if not symbol or not isinstance(symbol, str):
            return False
        
        # Trim whitespace
        symbol = symbol.strip()
        
        if len(symbol) > self.max_lengths['symbol']:
            return False
        
        # More flexible symbol validation
        return bool(re.match(self.patterns['symbol'], symbol))
    
    def sanitize_address(self, address: str) -> str:
        """Sanitize and normalize address format"""
        if not address:
            return ""
        
        address = address.strip().lower()
        
        # Ensure proper length
        if len(address) < 42:
            # Pad with zeros if needed
            address = address + "0" * (42 - len(address))
        elif len(address) > 42:
            # Truncate if too long
            address = address[:42]
        
        return address
    
    def sanitize_symbol(self, symbol: str) -> str:
        """Sanitize and normalize symbol format"""
        if not symbol:
            return ""
        
        symbol = symbol.strip().upper()
        
        # Remove any non-alphanumeric characters
        symbol = re.sub(r'[^A-Za-z0-9]', '', symbol)
        
        # Limit length
        if len(symbol) > self.max_lengths['symbol']:
            symbol = symbol[:self.max_lengths['symbol']]
        
        return symbol
    
    def validate_chain(self, chain: str) -> bool:
        """Validate blockchain chain identifier"""
        if not chain or not isinstance(chain, str):
            return False
        
        chain_lower = chain.lower().strip()
        return bool(re.match(self.patterns['chain_id'], chain_lower))
    
    def validate_token_data(self, token_data: Dict) -> ValidationResult:
        """Validate complete token data structure"""
        errors = []
        warnings = []
        sanitized_data = {}
        
        # Required fields
        required_fields = ['address']
        for field in required_fields:
            if field not in token_data:
                errors.append(f"Missing required field: {field}")
            elif not token_data[field]:
                errors.append(f"Empty required field: {field}")
        
        # Validate address
        if 'address' in token_data:
            if not self.validate_address(token_data['address']):
                errors.append("Invalid token address format")
            else:
                sanitized_data['address'] = token_data['address'].lower()
        
        # Validate symbol (optional)
        if 'symbol' in token_data and token_data['symbol']:
            if not self.validate_symbol(token_data['symbol']):
                warnings.append("Invalid token symbol format")
            else:
                sanitized_data['symbol'] = token_data['symbol'].upper()
        
        # Validate name (optional)
        if 'name' in token_data and token_data['name']:
            if len(token_data['name']) > self.max_lengths['token_name']:
                warnings.append("Token name too long")
            else:
                sanitized_data['name'] = token_data['name'].strip()
        
        # Validate chain (optional)
        if 'chain' in token_data and token_data['chain']:
            if not self.validate_chain(token_data['chain']):
                warnings.append("Invalid blockchain chain identifier")
            else:
                sanitized_data['chain'] = token_data['chain'].lower().strip()
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            sanitized_data=sanitized_data if is_valid else None
        )

class ConfigValidator:
    """Validate configuration data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # API key patterns
        self.api_patterns = {
            'twitter': r'^[a-zA-Z0-9]{20,100}$',
            'etherscan': r'^[a-zA-Z0-9]{30,100}$',
            'coingecko': r'^[a-zA-Z0-9]{20,100}$',
            'coinmarketcap': r'^[a-zA-Z0-9]{20,100}$'
        }
        
        # URL pattern
        self.url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    
    def validate_api_key(self, api_key: str, service: str) -> bool:
        """Validate API key format"""
        if not api_key or not isinstance(api_key, str):
            return False
        
        # Service-specific validation
        if service.lower() in self.api_patterns:
            return bool(re.match(self.api_patterns[service.lower()], api_key))
        
        # Generic validation
        return len(api_key) >= 10 and api_key.isalnum()
    
    def validate_url(self, url: str) -> bool:
        """Validate URL format"""
        if not url or not isinstance(url, str):
            return False
        
        return bool(re.match(self.url_pattern, url))
    
    def validate_config(self, config: Dict) -> ValidationResult:
        """Validate configuration structure"""
        errors = []
        warnings = []
        sanitized_config = {}
        
        # Validate API keys
        api_keys = config.get('api_keys', {})
        for service, key in api_keys.items():
            if not self.validate_api_key(key, service):
                errors.append(f"Invalid API key format for {service}")
            else:
                sanitized_config[service] = key
        
        # Validate rate limits
        rate_limits = config.get('rate_limits', {})
        for service, limits in rate_limits.items():
            if not isinstance(limits, dict):
                errors.append(f"Invalid rate limit format for {service}")
            else:
                sanitized_config[f'rate_limit_{service}'] = limits
        
        # Validate cache settings
        cache_settings = config.get('cache_settings', {})
        if not isinstance(cache_settings, dict):
            errors.append("Invalid cache settings format")
        else:
            sanitized_config['cache_settings'] = cache_settings
        
        # Validate logging settings
        logging_settings = config.get('logging', {})
        if not isinstance(logging_settings, dict):
            errors.append("Invalid logging settings format")
        else:
            sanitized_config['logging'] = logging_settings
        
        # Validate output settings
        output_settings = config.get('output', {})
        if not isinstance(output_settings, dict):
            errors.append("Invalid output settings format")
        else:
            sanitized_config['output'] = output_settings
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            sanitized_data=sanitized_config if is_valid else None
        ) 