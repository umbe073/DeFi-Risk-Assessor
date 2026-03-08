---
header-includes:
  - \usepackage[table]{xcolor}
  - \definecolor{lowrisk}{HTML}{28a745}
  - \definecolor{mediumrisk}{HTML}{ffc107}
  - \definecolor{highrisk}{HTML}{fd7e14}
  - \definecolor{extremerisk}{HTML}{dc3545}
  - \definecolor{headerblue}{HTML}{1e3a8a}
  - \usepackage{array}
  - \usepackage{longtable}
---

<style>
body {
    margin: 0;
    padding: 10px;
    font-family: 'Arial', 'Helvetica', sans-serif;
    line-height: 1.6;
    font-size: 22px;
    font-weight: bold;
    text-align: center;
}

h1 {
    font-size: 80pt !important;
    font-weight: 900 !important;
    color: #1e3a8a !important;
    text-align: center !important;
    margin: 10px 0 10px 0 !important;
    border-bottom: 6px solid #1e3a8a !important;
    padding-bottom: 10px !important;
    text-transform: uppercase !important;
    line-height: 1.1 !important;
    letter-spacing: 2px !important;
}

table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 10px 0 !important;
    border: 2px solid #000 !important;
    background-color: #f8f9fa !important;
}

th, td {
    padding: 8px !important;
    text-align: left !important;
    border: 1.5px solid #000 !important;
    font-weight: bold !important;
    font-size: 16px !important;
}

/* Header row */
tr:first-child td {
    background-color: #1e3a8a !important;
    color: white !important;
    font-weight: bold !important;
}

/* Risk category rows */
tr:nth-child(2) td {
    background-color: #28a745 !important;
    color: white !important;
    font-weight: bold !important;
}

tr:nth-child(3) td {
    background-color: #ffc107 !important;
    color: #000 !important;
    font-weight: bold !important;
}

tr:nth-child(4) td {
    background-color: #fd7e14 !important;
    color: white !important;
    font-weight: bold !important;
}

tr:nth-child(5) td {
    background-color: #dc3545 !important;
    color: white !important;
    font-weight: bold !important;
}
</style>

# DeFi Tokens Automated Risk Assessment Guide

## Overview

The DeFi Tokens Automated Risk Assessment Tool is a comprehensive system designed to evaluate cryptocurrency tokens across multiple risk dimensions. This tool provides detailed risk scoring and analysis for DeFi tokens, helping investors and analysts make informed decisions.

## Risk Assessment Methodology

The tool evaluates tokens across multiple dimensions using a sophisticated scoring system:

### Risk Categories

| Risk Level                | Description                                                                                   |
|--------------------------|----------------------------------------------------------------------------------------------|
| **Low Risk (0-50)**      | Well-established tokens with strong fundamentals, verified contracts, high liquidity, and active development |
| **Medium Risk (51-100)** | Moderate risk with some concerns, may have unverified contracts or limited liquidity          |
| **High Risk (101-120)**  | Significant risk factors present, including unverified contracts, low liquidity, or poor community engagement |
| **Extreme Risk (121-140)** | Multiple critical risk factors, including security vulnerabilities, no audits, and minimal development activity |

### Assessment Components
1. **Industry Impact** - Market positioning and sector relevance
2. **Tech Innovation** - Technological advancement and uniqueness
3. **Whitepaper Quality** - Documentation and project clarity
4. **Roadmap Adherence** - Project execution and timeline compliance
5. **Business Model** - Revenue generation and sustainability
6. **Team Expertise** - Developer and management capabilities
7. **Management Strategy** - Leadership and governance quality
8. **Global Reach** - Market penetration and adoption
9. **Code Security** - Smart contract safety and audits
10. **Developer Activity** - Ongoing development and maintenance
11. **Legal Compliance** - Regulatory adherence and legal structure
12. **Market Dynamics** - Trading patterns and market behavior
13. **Marketing Demand** - Community engagement and marketing effectiveness
14. **ESG Impact** - Environmental, social, and governance factors

## Risk Weights for Red Flags and Categories

The final risk score is a weighted sum of the component scores (each 1–10, weighted as below, scaled to 0–140), plus any red flag boosts.

### Red Flag Risk Boosts

| Red Flag                       | Risk Boost (added to score) |
|--------------------------------|-----------------------------|
| Proxy contract                 | +20                         |
| Honeypot pattern               | +30                         |
| Owner change in last 24h       | +15                         |
| LP lock expiring soon          | +25                         |
| Unverified contract            | +15                         |
| Low liquidity                  | +12                         |
| High concentration             | +15                         |
| EU unlicensed stablecoin       | +50 (forces Extreme Risk)   |
| EU regulatory issues           | +40 (forces Extreme Risk)   |
| MiCA non-compliant             | +35 (High Risk)             |
| MiCA no whitepaper             | +0 (flag only, no boost)    |

## Token Data Collection

For each token in your input file, the script fetches comprehensive data from the following services:

### Blockchain Data Sources
- **Etherscan** - Ethereum contract verification, token info, holder data, transaction history
- **Infura** - Ethereum blockchain access, transaction data, gas price information
- **BitQuery** - On-chain analytics, transfer data, wallet analysis, transaction patterns
- **Ethplorer** - Token holder information, supply data, contract interactions

### Market Data Sources
- **CoinGecko** - Market data, price, volume, market cap, community metrics, social sentiment
- **CoinMarketCap** - Cryptocurrency mapping, additional market data, global metrics
- **Coinpaprika** - Alternative market data, price feeds, trading volume analytics
- **1inch** - Aggregated DEX data, price comparison, liquidity sources

### Security & Analytics
- **Breadcrumbs** - Address risk scoring, token analysis, wallet profiling
- **Santiment** - Social volume, developer activity metrics, sentiment analysis
- **Certik** - Security audits, vulnerability assessments, smart contract analysis
- **Dune Analytics** - Custom blockchain analytics, on-chain metrics, data queries
- **DefiLlama** - DeFi protocol data, TVL information, yield analytics (Free API - no key required)
- **DeBank** - Wallet portfolio analysis, DeFi position tracking
- **Zapper** - DeFi dashboard data, portfolio analytics, protocol interactions

### Additional Services
- **Li.Fi** - Cross-chain liquidity, routing data, bridge information
- **The Graph** - Indexed blockchain data, subgraph queries, historical analytics
- **Covalent** - Multi-chain data aggregation, token metadata, transaction history
- **Moralis** - Web3 data APIs, NFT information, blockchain analytics

## Required API Keys

<div style="page-break-after: always;"></div>

Create a `.env` file in your project root with the following API keys:

```env
# Required APIs
INFURA_API_KEY=your_infura_key
ETHERSCAN_API_KEY=your_etherscan_key
ETHPLORER_API_KEY=your_ethplorer_key

# Market Data APIs
COINGECKO_API_KEY=your_coingecko_key
COINMARKETCAP_API_KEY=your_cmc_key
COINPAPRIKA_API_KEY=your_coinpaprika_key
1INCH_API_KEY=your_1inch_key

# Analytics APIs
BITQUERY_API_KEY=your_bitquery_key
BREADCRUMBS_API_KEY=your_breadcrumbs_key
SANTIMENT_API_KEY=your_santiment_key
DEBANK_API_KEY=your_debank_key
ZAPPER_API_KEY=your_zapper_key

# Security APIs
CERTIK_API_KEY=your_certik_key

# Additional APIs
LI_FI_API_KEY=your_lifi_key
DUNE_ANALYTICS_API_KEY=your_dune_key
THE_GRAPH_API_KEY=your_thegraph_key
COVALENT_API_KEY=your_covalent_key
MORALIS_API_KEY=your_moralis_key
```

### API Key Setup Instructions

1. **Obtain API Keys**: Visit each service's website to register and obtain your API keys
2. **Create .env File**: Create a `.env` file in your project root directory
3. **Add Keys**: Copy the template above and replace `your_*_key` with your actual API keys
4. **Verify Format**: Ensure there are no spaces around the `=` sign and no quotes around the values
5. **Test Keys**: Run a test assessment to verify all API keys are working correctly

### Important Notes

- **Free Tier Limits**: Monitor API usage to avoid exceeding limits
- **Key Security**: Never commit `.env` file to version control
- **Backup Keys**: Keep secure backups of API keys
- **Service Status**: APIs may have downtime, tool includes fallbacks

### API Key Validation

The tool validates API keys during startup and reports any issues. Check logs for authentication errors.

<div style="page-break-after: always;"></div>

## How to Use

### Initial Setup

1. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Keys**
   - Create a `.env` file in the project root
   - Add all required API keys (see section above)
   - Ensure the `.env` file is in the same directory as the scripts

3. **Prepare Token Data**
   - Create a `tokens.csv` file in the `data/` directory
   - Format: `address,chain` (e.g., `0x1234...abcd,eth`)
   - Supported chains: `eth`, `bsc`, `polygon`, `arbitrum`, `optimism`

4. **Set Up Excel Template**
   - Ensure `DeFi Tokens Risk Assessment Results.xlsx` exists in the `data/` directory
   - The script will automatically update this file with results

5. **Configure App Environment**
   - Ensure the `Token Risk Assessment Tool.app` is properly configured
   - Verify all file permissions are set correctly
   - Test the app execution before running full assessments
   - Make sure the app has access to all required directories and files
   - Verify Python environment is properly configured within the app bundle

6. **Verify File Structure**
   - Ensure all required directories exist: `data/`, `logs/`, `scripts/`
   - Verify the app can access the project root directory
   - Check that all dependency files are in the correct locations

### Running the Assessment

#### Option 1: Using the .app File (Recommended)
1. Double-click the `Token Risk Assessment Tool.app`
2. The app will automatically:
   - Run the risk assessment for all tokens
   - Update the Excel spreadsheet
   - Show completion dialog when finished
   - Generate all necessary log files

#### Option 2: Manual Execution
```bash
cd /path/to/your/project
./scripts/v1.0/run_risk_assessment.sh
```

### Expected Runtime
- **Small token list (1-10 tokens)**: 3-5 minutes
- **Medium token list (10-50 tokens)**: 10-20 minutes
- **Large token list (50+ tokens)**: 30+ minutes

## Reporting

The script generates comprehensive reports in multiple formats:

### Output Files Location
All reports are saved in the `data/` directory:

- **`risk_report.csv`** - Detailed CSV report with all assessment data
- **`risk_report.json`** - Structured JSON data for programmatic access
- **`DeFi Tokens Risk Assessment Results.xlsx`** - Updated Excel spreadsheet with formatted results

### Log Files Location
Detailed logs are saved in the `logs/` directory:

- **`defi_complete_risk_assessment.log`** - Risk assessment execution logs
- **`update_risk_assessment_xlsx.log`** - Excel update process logs
- **`risk_assessment_verbose.log`** - Detailed API calls and processing logs
- **`risk_assessment_summary.txt`** - Summary of assessment results

### Important Note for .app Users
When running through the .app file, results are **not displayed in the terminal**. Instead, check the log files in the `logs/` directory for detailed execution information and any error messages. This is normal behavior for macOS applications and ensures a clean user experience.

**To access your results when using the .app file:**
1. Navigate to the `logs/` directory in your project folder
2. Open `defi_complete_risk_assessment.log` for execution status
3. Open `risk_assessment_summary.txt` for a quick overview of results
4. Check `data/` directory for the updated Excel file and CSV/JSON reports

## Troubleshooting

### Common Issues

1. **"ModuleNotFoundError: No module named '...'"**
   - Solution: Install dependencies with `pip install -r requirements.txt`

2. **API Key Errors**
   - Check your `.env` file exists and contains valid API keys
   - Verify API keys are active and have sufficient quota

3. **File Not Found Errors**
   - Ensure `tokens.csv` exists in the `data/` directory
   - Ensure `DeFi Tokens Risk Assessment Results.xlsx` is present in the `data/` directory
   - Check that all required scripts are in the `scripts/` directory
   - Make sure you are running the tool from the project root

4. **Permission Errors**
   - Make sure the script has execute permissions: `chmod +x scripts/v1.0/run_risk_assessment.sh`

5. **App Execution Issues**
   - Verify the .app file has proper permissions
   - Check System Preferences > Security & Privacy for app execution permissions
   - Ensure all required files are in the correct locations
   - Verify the app bundle contains all necessary dependencies

### Debug Information
The script automatically creates debug files:
- `data/debug_python_env.txt` - Python environment information
- Check log files in `logs/` directory for detailed error messages

## Data Attribution

### CoinGecko Attribution
Market data is provided by CoinGecko. Please ensure proper attribution when using this data.

**CoinGecko** - [https://www.coingecko.com](https://www.coingecko.com)

*CoinGecko provides comprehensive cryptocurrency market data, including prices, trading volumes, market capitalization, and community metrics. Their API is widely used across the cryptocurrency industry for reliable market information.*

## Disclaimer

The results of this assessment may not be precise and may vary according to the availability of the API endpoints from which the data is taken. This tool is for informational purposes only and should not be considered as financial advice. Always conduct your own research before making investment decisions.

## Support

For technical support or questions about the DeFi Tokens Automated Risk Assessment Tool, please refer to the log files in the `logs/` directory for detailed execution information.

## If you encounter issues not listed here:

- Review the log files in the `logs/` directory for detailed error messages
- Consult the official documentation for each API provider
- Reach out to the project maintainers/creator or your direct superior if you retain the results unreliable, before uploading them online, or for further assistance
---

*Last Updated: July 2024*
*Version: 1.0* 