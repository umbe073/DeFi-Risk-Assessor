# Dune Analytics API Integration

## Overview

The Dune Analytics API has been successfully integrated into the DeFi Risk Assessment system. Instead of creating a separate dashboard, the Dune Analytics functionality is now part of the existing **API Service Dashboard**, providing a unified interface for all API services.

## Features

The Dune Analytics integration provides access to the following endpoints:

### 🔗 Core Endpoints

- **Activity**: Get real-time blockchain activity for any wallet address
- **Token Holders**: Analyze token holder distribution and behavior
- **Token Info**: Retrieve comprehensive token metadata and market data
- **Balances**: Get wallet token balances across multiple chains
- **Transactions**: Access detailed transaction history
- **Collectibles**: Fetch NFT and collectible data

### 📊 Utility Functions

- `get_wallet_activity()`: Quick wallet activity lookup
- `get_token_holder_analysis()`: Token holder analysis
- `get_token_market_data()`: Comprehensive token market data
- `get_wallet_portfolio()`: Complete wallet portfolio analysis

## Setup

### 1. API Key Configuration

Add your Dune Analytics API key to the `.env` file:

```bash
DUNE_API_KEY=your_dune_api_key_here
```

### 2. Access the Integration

1. Launch the DeFi Risk Assessment system tray
2. Select **"🔧 API Service Dashboard"** from the menu
3. Find **"Dune Analytics API"** in the **"📈 Blockchain Analytics"** section
4. Click **"🔄 Fetch Data"** to test the API connection

## API Endpoints

### Activity Endpoint

```python
# Get wallet activity
activity = api.get_activity(wallet_address, limit=20)
```

### Token Holders Endpoint

```python
# Get token holders
holders = api.get_token_holders(chain_id, token_address, limit=500)
```

### Token Info Endpoint

```python
# Get token information
token_info = api.get_token_info(token_address, chain_ids="all")
```

### Balances Endpoint

```python
# Get wallet balances
balances = api.get_balances(wallet_address, chain_ids="all")
```

### Transactions Endpoint

```python
# Get transaction history
transactions = api.get_transactions(wallet_address, chain_ids="all")
```

### Collectibles Endpoint

```python
# Get NFT/collectible data
collectibles = api.get_collectibles(wallet_address, chain_ids="all")
```

## Rate Limits

- **Rate Limit**: 100 calls per hour
- **Rate Period**: 3600 seconds (1 hour)
- **Default Limits**:

  - Activity: 20 items
  - Token Holders: 500 holders
  - Balances: 50 balances
  - Transactions: 20 transactions
  - Collectibles: 20 collectibles

## Supported Chains

The Dune Analytics API supports multiple blockchain networks:

- Ethereum (1)
- Base (8453)
- Polygon (137)
- Arbitrum (42161)
- Optimism (10)
- And many more...

## Example Usage

### Basic Wallet Analysis

```python
from dune_analytics_api import DuneAnalyticsAPI

# Initialize API
api = DuneAnalyticsAPI()

# Get wallet activity
wallet = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
activity = api.get_activity(wallet, limit=10)

# Get wallet balances
balances = api.get_balances(wallet)

# Get transaction history
transactions = api.get_transactions(wallet, limit=20)
```

### Token Analysis

```python
# Get token information
token_address = "0xA0b86a33E6441b8c4C8C1C1B9C9C9C9C9C9C9C9C"
token_info = api.get_token_info(token_address)

# Get token holders
holders = api.get_token_holders(1, token_address, limit=100)
```

### Portfolio Analysis

```python
from dune_analytics_api import get_wallet_portfolio

# Get complete portfolio analysis
portfolio = get_wallet_portfolio(wallet_address)
```

## Integration Benefits

### ✅ Unified Interface

- All API services in one dashboard
- Consistent user experience
- Centralized rate limit management

### ✅ Real-time Data

- Live blockchain activity feeds
- Current token prices and market data
- Up-to-date holder information

### ✅ Comprehensive Analytics

- Multi-chain support
- Historical data access
- Detailed transaction analysis

### ✅ Easy Testing

- Built-in API testing functionality
- Rate limit monitoring
- Error handling and reporting

## Error Handling

The integration includes comprehensive error handling:

- API key validation
- Rate limit enforcement
- Network error recovery
- Invalid address handling
- Chain ID validation

## Testing

Run the test script to verify the integration:

```bash
python3 test_dune_api.py
```

This will test:

- API connectivity
- All endpoint functionality
- Dashboard integration
- Rate limiting
- Error handling

## Troubleshooting

### Common Issues

1. **"No API key found"**
   - Ensure `DUNE_API_KEY` is set in your `.env` file
   - Verify the key is valid and active

2. **"Rate limit exceeded"**
   - Wait for the rate limit period to reset
   - Reduce request frequency
   - Check the dashboard for current usage

3. **"Invalid address"**
   - Ensure wallet addresses are valid Ethereum addresses
   - Check token contract addresses are correct
   - Verify chain IDs are supported

4. **"Network error"**
   - Check internet connectivity
   - Verify Dune Analytics API is accessible
   - Try again after a few minutes

### Support

For issues with the Dune Analytics API integration:

1. Check the API dashboard for service status
2. Review the test script output
3. Verify your API key permissions
4. Check the Dune Analytics API documentation

## Future Enhancements

Potential improvements for the integration:

- Caching for frequently accessed data
- Batch request optimization
- Advanced filtering options
- Custom query builder
- Data export functionality
- Historical trend analysis
