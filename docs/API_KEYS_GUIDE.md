# API Keys Guide for Enhanced DeFi Risk Assessment

This guide provides step-by-step instructions for obtaining API keys for the enhanced DeFi risk assessment tool.

## 🔑 Required API Keys

### 1. **Scorechain** - AML/Compliance Data
- **Website**: https://scorechain.com/
- **API Documentation**: https://api.scorechain.com/
- **Cost**: Enterprise pricing (contact sales)
- **How to get API key**:
  1. Visit https://scorechain.com/
  2. Click "Get Started" or "Contact Sales"
  3. Fill out their enterprise contact form with your business details
  4. Schedule a demo with their sales team
  5. Complete the enterprise onboarding process
  6. Receive API credentials after approval
- **Note**: This is primarily an enterprise/B2B service focused on crypto compliance and AML

### 2. **TRM Labs** - AML/Compliance Data
- **Website**: https://www.trmlabs.com/
- **API Documentation**: https://docs.trmlabs.com/
- **Cost**: Enterprise pricing (contact sales)
- **How to get API key**:
  1. Visit https://www.trmlabs.com/
  2. Click "Get Started" or "Contact Sales"
  3. Complete their enterprise onboarding form
  4. Schedule a consultation with their compliance team
  5. Undergo business verification process
  6. Receive API access after approval
- **Note**: Enterprise-focused compliance platform for crypto risk management

### 3. **Lukka** - Compliance Data
- **Website**: https://lukka.tech/
- **API Documentation**: https://lukka.tech/api/
- **Cost**: Enterprise pricing (contact sales)
- **How to get API key**:
  1. Visit https://lukka.tech/
  2. Click "Contact Sales" or "Get Started"
  3. Fill out their enterprise contact form
  4. Schedule a demo with their team
  5. Complete enterprise onboarding process
  6. Receive API credentials after approval
- **Note**: Enterprise crypto accounting and compliance platform

### 4. **Alchemy** - Blockchain Data
- **Website**: https://www.alchemy.com/
- **API Documentation**: https://docs.alchemy.com/
- **Cost**: Free tier available, paid plans for higher limits
- **How to get API key**:
  1. Visit https://www.alchemy.com/
  2. Click "Get Started Free"
  3. Create an account with your email
  4. Verify your email address
  5. Log into the Alchemy dashboard
  6. Click "Create App"
  7. Select "Ethereum" as the chain
  8. Choose "Mainnet" as the network
  9. Give your app a name (e.g., "DeFi Risk Assessment")
  10. Click "Create App"
  11. Copy your API key from the app settings
- **Note**: Free tier includes 300M compute units per month

## 🆓 Free APIs (No Key Required)

The following APIs are already integrated and don't require API keys:

- **1inch** - DEX aggregation data
- **Coinpaprika** - Market data
- **DeFiLlama** - Protocol TVL and yield data
- **Ethplorer** - Ethereum blockchain data (limited)
- **DeFiSafety** - Protocol safety assessments (web scraping)
- **OpenSanctions** - Sanctions and compliance data

## 📝 Environment Variables Setup

Add these API keys to your `.env` file:

```bash
# Enhanced Risk Assessment APIs
SCORECHAIN_API_KEY=your_scorechain_api_key_here
TRMLABS_API_KEY=your_trmlabs_api_key_here
LUKKA_API_KEY=your_lukka_api_key_here
ALCHEMY_API_KEY=your_alchemy_api_key_here

# Existing APIs (keep these)
INFURA_API_KEY=your_infura_api_key_here
ETHERSCAN_API_KEY=your_etherscan_api_key_here
# ... (other existing API keys)
```

## ⚠️ Important Notes

1. **Enterprise Services**: Scorechain, TRM Labs, and Lukka are enterprise-focused services that require business verification and may have minimum contract requirements.

2. **Free Alternative**: If you can't obtain enterprise API keys, the system will still work with default scoring values (9/10) for AML and Compliance data categories.

3. **Alchemy Free Tier**: Alchemy offers a generous free tier that should be sufficient for most use cases.

4. **Rate Limits**: Be aware of rate limits for all APIs, especially the free tiers.

## 🔄 Testing API Keys

After adding your API keys to the `.env` file, run the risk assessment script to verify they're working:

```bash
python3 scripts/v1.0/defi_complete_risk_assessment.py
```

The script will display the status of all API keys at startup, showing which ones are valid and which are missing. 