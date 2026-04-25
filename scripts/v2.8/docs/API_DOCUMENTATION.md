# DeFi Risk Assessment API Documentation

## 📋 Overview

This document provides comprehensive documentation for the DeFi Risk Assessment Script API endpoints, setup instructions, and usage examples.

## 🏗️ Architecture

### Modular Structure
```
scripts/v1.4/
├── modules/
│   ├── core.py              # Main risk assessor class
│   ├── data_collectors.py   # Data collection from APIs
│   ├── scorers.py           # Risk scoring algorithms
│   ├── validators.py        # Input validation
│   └── utils.py             # Utilities (logging, caching, etc.)
├── tests/                   # Unit tests
├── docs/                    # Documentation
└── config/                  # Configuration files
```

## 🔧 Setup Instructions

### 1. Environment Setup

```bash
# Install dependencies
pip install requests pandas openpyxl cryptography keyring

# Set up environment variables
export PYTHONPATH="${PYTHONPATH}:/path/to/scripts/v1.4"
```

### 2. Configuration

Create a `config.json` file:

```json
{
  "api_keys": {
    "TWITTER_BEARER_TOKEN": "your_twitter_token",
    "ETHERSCAN_API_KEY": "your_etherscan_key",
    "COINMARKETCAP_API_KEY": "your_cmc_key",
    "MORALIS_API_KEY": "your_moralis_key",
    "ALCHEMY_API_KEY": "your_alchemy_key"
  },
  "rate_limits": {
    "twitter": {"max_requests": 450, "time_window": 900},
    "etherscan": {"max_requests": 5, "time_window": 1},
    "coingecko": {"max_requests": 50, "time_window": 60}
  },
  "cache_settings": {
    "enabled": true,
    "ttl": 3600
  },
  "logging": {
    "level": "INFO",
    "file": "logs/risk_assessment.log"
  },
  "output": {
    "json": true,
    "excel": true,
    "csv": false
  }
}
```

## 🔑 API Key Setup Guide

### Twitter API
1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new app
3. Generate Bearer Token
4. Add to config: `"TWITTER_BEARER_TOKEN": "your_token"`

### Etherscan API
1. Go to [Etherscan](https://etherscan.io/apis)
2. Create account and get API key
3. Add to config: `"ETHERSCAN_API_KEY": "your_key"`

### CoinMarketCap API
1. Go to [CoinMarketCap](https://coinmarketcap.com/api/)
2. Sign up for API access
3. Add to config: `"COINMARKETCAP_API_KEY": "your_key"`

### Moralis API
1. Go to [Moralis](https://moralis.io/)
2. Create account and get API key
3. Add to config: `"MORALIS_API_KEY": "your_key"`

### Alchemy API
1. Go to [Alchemy](https://www.alchemy.com/)
2. Create account and get API key
3. Add to config: `"ALCHEMY_API_KEY": "your_key"`

### CertiK API
1. Go to [CertiK](https://certik.com/)
2. Contact for API access
3. Add to config: `"CERTIK_API_KEY": "your_key"`

### DeFiSafety API
1. Go to [DeFiSafety](https://defisafety.com/)
2. Contact for API access
3. Add to config: `"DEFISAFETY_API_KEY": "your_key"`

### Scorechain API
1. Go to [Scorechain](https://scorechain.com/)
2. Contact for API access
3. Add to config: `"SCORECHAIN_API_KEY": "your_key"`

### TRM Labs API
1. Go to [TRM Labs](https://www.trmlabs.com/)
2. Contact for API access
3. Add to config: `"TRM_API_KEY": "your_key"`

### Bitquery API
1. Go to [Bitquery](https://bitquery.io/)
2. Create account and get API key
3. Add to config: `"BITQUERY_API_KEY": "your_key"`

### Breadcrumbs API
1. Go to [Breadcrumbs](https://breadcrumbs.app/)
2. Create account and get API key
3. Add to config: `"BREADCRUMBS_API_KEY": "your_key"`

### Santiment API
1. Go to [Santiment](https://santiment.net/)
2. Create account and get API key
3. Add to config: `"SANTIMENT_API_KEY": "your_key"`

### DeBank API
1. Go to [DeBank](https://debank.com/)
2. Contact for API access
3. Add to config: `"DEBANK_API_KEY": "your_key"`

### Zapper API
1. Go to [Zapper](https://zapper.xyz/)
2. Contact for API access
3. Add to config: `"ZAPPER_API_KEY": "your_key"`

## 📊 API Endpoints Documentation

### Market Data APIs

#### CoinGecko API
- **Endpoint**: `https://api.coingecko.com/api/v3/simple/price`
- **Rate Limit**: 50 calls/minute
- **Authentication**: None required
- **Parameters**: `ids`, `vs_currencies`, `include_market_cap`, `include_24hr_vol`, `include_24hr_change`
- **Response**: Price, market cap, volume, 24h change

#### CoinMarketCap API
- **Endpoint**: `https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest`
- **Rate Limit**: 30 calls/minute
- **Authentication**: API key in header `X-CMC_PRO_API_KEY`
- **Parameters**: `symbol`
- **Response**: Price, market cap, volume, percent change

#### Coinpaprika API
- **Endpoint**: `https://api.coinpaprika.com/v1/tickers/{id}`
- **Rate Limit**: 100 calls/minute
- **Authentication**: None required
- **Parameters**: `id` (coin identifier)
- **Response**: Price, market cap, volume

### Social Data APIs

#### Twitter API v2
- **Endpoint**: `https://api.twitter.com/2/tweets/counts/recent`
- **Rate Limit**: 450 calls/15 minutes
- **Authentication**: Bearer token
- **Parameters**: `query`, `granularity`
- **Response**: Tweet counts, engagement metrics

#### Telegram Bot API
- **Endpoint**: `https://api.telegram.org/bot{token}/getUpdates`
- **Rate Limit**: 30 calls/second
- **Authentication**: Bot token
- **Parameters**: None
- **Response**: Channel information, member counts

#### Reddit API
- **Endpoint**: `https://www.reddit.com/r/{subreddit}/about.json`
- **Rate Limit**: 60 calls/minute
- **Authentication**: OAuth2 (optional)
- **Parameters**: `subreddit`
- **Response**: Subscriber count, post count

#### Bitcointalk API
- **Endpoint**: Web scraping (no official API)
- **Rate Limit**: Respectful scraping
- **Authentication**: None
- **Parameters**: Search terms
- **Response**: Thread count, post count

#### Cointelegraph RSS
- **Endpoint**: RSS feed parsing
- **Rate Limit**: None
- **Authentication**: None
- **Parameters**: Search terms
- **Response**: Article count, mentions

### Security Data APIs

#### CertiK API
- **Endpoint**: `https://api.certik.com/v1/projects/{address}`
- **Rate Limit**: Contact CertiK
- **Authentication**: API key
- **Parameters**: `address` (contract address)
- **Response**: Security score, audit status

#### DeFiSafety API
- **Endpoint**: `https://api.defisafety.com/v1/projects/{address}`
- **Rate Limit**: Contact DeFiSafety
- **Authentication**: API key
- **Parameters**: `address` (contract address)
- **Response**: Safety score, risk assessment

#### Alchemy API
- **Endpoint**: `https://eth-mainnet.alchemyapi.io/v2/{api_key}`
- **Rate Limit**: 330 calls/second
- **Authentication**: API key
- **Parameters**: Contract address
- **Response**: Contract verification, code analysis

### Compliance Data APIs

#### Scorechain API
- **Endpoint**: `https://api.scorechain.com/v1/risk/{address}`
- **Rate Limit**: Contact Scorechain
- **Authentication**: API key
- **Parameters**: `address` (contract address)
- **Response**: Risk score, compliance status

#### TRM Labs API
- **Endpoint**: `https://api.trmlabs.com/v1/risk/{address}`
- **Rate Limit**: Contact TRM Labs
- **Authentication**: API key
- **Parameters**: `address` (contract address)
- **Response**: Risk assessment, compliance data

#### OpenSanctions API
- **Endpoint**: `https://api.opensanctions.org/v1/search`
- **Rate Limit**: Contact OpenSanctions
- **Authentication**: API key
- **Parameters**: Search terms
- **Response**: Sanctions risk level

### Liquidity Data APIs

#### Etherscan API
- **Endpoint**: `https://api.etherscan.io/api`
- **Rate Limit**: 5 calls/second
- **Authentication**: API key
- **Parameters**: `module`, `action`, `address`, `apikey`
- **Response**: Transaction count, contract data

#### DeFiLlama API
- **Endpoint**: `https://api.llama.fi/protocol/{protocol}`
- **Rate Limit**: 100 calls/minute
- **Authentication**: None required
- **Parameters**: `protocol` (protocol identifier)
- **Response**: TVL, protocol data

#### 1inch API
- **Endpoint**: `https://api.1inch.io/v4.0/1/quote`
- **Rate Limit**: Contact 1inch
- **Authentication**: API key
- **Parameters**: `fromTokenAddress`, `toTokenAddress`, `amount`
- **Response**: Liquidity depth, swap data

### Transfer Data APIs

#### Moralis API
- **Endpoint**: `https://deep-index.moralis.io/api/v2/{address}/erc20/transfers`
- **Rate Limit**: 25 calls/second
- **Authentication**: API key
- **Parameters**: `address`, `chain`
- **Response**: Transfer count, transaction data

#### Bitquery API
- **Endpoint**: `https://graphql.bitquery.io/`
- **Rate Limit**: Contact Bitquery
- **Authentication**: API key
- **Parameters**: GraphQL query
- **Response**: Transfer data, transaction analysis

## 🚀 Usage Examples

### Basic Usage

```python
from modules.core import DeFiRiskAssessor

# Initialize assessor
assessor = DeFiRiskAssessor("config.json")

# Assess single token
report = assessor.assess_token(
    token_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
    symbol="LINK",
    token_name="Chainlink"
)

# Print results
print(f"Overall Risk Score: {report.risk_scores['overall']}")
print(f"Market Data Score: {report.risk_scores['market_data']}")
print(f"Social Data Score: {report.risk_scores['social_data']}")
```

### Batch Processing

```python
# Prepare token list
tokens = [
    {"address": "0x514910771AF9Ca656af840dff83E8264EcF986CA", "symbol": "LINK"},
    {"address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", "symbol": "UNI"},
    {"address": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9", "symbol": "AAVE"}
]

# Assess multiple tokens
reports = assessor.assess_batch(tokens)

# Export results
assessor.export_reports(reports, "data/")
```

### Custom Configuration

```python
# Custom config
config = {
    "api_keys": {
        "TWITTER_BEARER_TOKEN": "your_token",
        "ETHERSCAN_API_KEY": "your_key"
    },
    "rate_limits": {
        "twitter": {"max_requests": 450, "time_window": 900},
        "etherscan": {"max_requests": 5, "time_window": 1}
    },
    "cache_settings": {
        "enabled": True,
        "ttl": 3600
    }
}

# Save config
import json
with open("custom_config.json", "w") as f:
    json.dump(config, f, indent=2)

# Use custom config
assessor = DeFiRiskAssessor("custom_config.json")
```

## 🔒 Security Features

### Input Validation
- Ethereum address format validation
- API key format validation
- URL validation
- XSS injection prevention
- Input sanitization

### Rate Limiting
- Exponential backoff
- Per-API rate limiting
- Jitter implementation
- Automatic retry logic

### API Key Security
- Encrypted storage
- System keyring integration
- Key validation
- Usage tracking
- Expiry checking

## 📈 Performance Optimization

### Caching
- In-memory caching with TTL
- Cache hit rate monitoring
- Automatic cache cleanup
- Configurable cache settings

### Parallel Processing
- Concurrent API requests
- Thread-safe operations
- Progress tracking
- Resource management

### Rate Limiting
- Intelligent request spacing
- API-specific limits
- Error handling
- Fallback mechanisms

## 🧪 Testing

### Running Tests
```bash
# Run all tests
python run_tests.py

# Run specific test module
python -m unittest tests.test_core

# Run with coverage
python -m coverage run run_tests.py
python -m coverage report
```

### Test Categories
- **Unit Tests**: Core functionality, data scoring, validation
- **Integration Tests**: API interactions, data flow
- **Performance Tests**: Rate limiting, caching, throughput
- **Security Tests**: Input validation, key management

## 📝 Error Handling

### Common Errors

#### API Rate Limiting
```python
# Error: 429 Too Many Requests
# Solution: Implement exponential backoff
import time
time.sleep(2 ** attempt)  # Exponential backoff
```

#### Invalid API Keys
```python
# Error: 401 Unauthorized
# Solution: Check API key format and permissions
if not validate_api_key(key, service):
    raise ValueError(f"Invalid {service} API key")
```

#### Network Errors
```python
# Error: Connection timeout
# Solution: Implement retry logic with backoff
for attempt in range(max_retries):
    try:
        response = requests.get(url, timeout=30)
        break
    except requests.exceptions.RequestException:
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)
```

## 🔧 Troubleshooting

### Common Issues

1. **API Key Not Working**
   - Check key format and permissions
   - Verify API service status
   - Test with API documentation

2. **Rate Limiting Issues**
   - Reduce request frequency
   - Implement proper backoff
   - Check API limits

3. **Data Not Updating**
   - Clear cache: `assessor.cache.clear()`
   - Check API responses
   - Verify data sources

4. **Performance Issues**
   - Enable caching
   - Reduce concurrent requests
   - Optimize rate limiting

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check API status
for endpoint in assessor.rate_limiter.get_all_status():
    print(f"{endpoint}: {assessor.rate_limiter.get_status(endpoint)}")
```

## 📞 Support

### Getting Help
1. Check the troubleshooting section
2. Review API documentation
3. Test with minimal configuration
4. Check logs for detailed errors

### Reporting Issues
- Include error messages
- Provide configuration (without API keys)
- Describe expected vs actual behavior
- Include system information

### Contributing
1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Submit pull request

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.

## 🔄 Version History

- **v1.4.1**: Modular architecture, comprehensive testing, enhanced documentation
- **v1.4.0**: Security enhancements, rate limiting, input validation
- **v1.3.0**: Dynamic social scoring, enhanced data collection
- **v1.2.0**: Basic risk assessment functionality
- **v1.1.0**: Initial release 