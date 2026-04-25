# Dynamic Token Mappings System

## Overview

The token mappings system has been completely redesigned to be dynamic and automatically generated from the `data/tokens.csv` file. This eliminates the need for manual maintenance of token mappings and ensures consistency across the entire system.

## How It Works

### 1. Source of Truth: `data/tokens.csv`

All token information is stored in `data/tokens.csv` with the following format:
```csv
address,chain,symbol,name
0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9,ethereum,AAVE,Aave
0x3506424f91fd33084466f402d5d97f05f8e3b4af,ethereum,CHZ,Chiliz
...
```

### 2. Automatic Generation: `generate_token_mappings.py`

This script reads `tokens.csv` and generates `token_mappings.py` with:
- Address to name mappings
- Address to symbol mappings  
- CoinGecko ID mappings
- CoinPaprika ID mappings
- Market cap estimates
- Holder estimates
- Token types

### 3. Auto-Regeneration

If `token_mappings.py` is missing or outdated, the system automatically:
1. Detects the missing file
2. Runs `generate_token_mappings.py`
3. Imports the newly generated mappings
4. Continues normal operation

## Usage

### Adding a New Token

1. **Edit `data/tokens.csv`**:
   ```csv
   0x1234567890123456789012345678901234567890,ethereum,NEW,New Token
   ```

2. **Regenerate mappings**:
   ```bash
   cd scripts/v2.0
   ./update_token_mappings.sh
   ```

3. **Done!** The system will automatically use the new token.

### Removing a Token

1. **Remove the line from `data/tokens.csv`**
2. **Run the update script**:
   ```bash
   ./update_token_mappings.sh
   ```

### Manual Regeneration

If you need to regenerate mappings manually:
```bash
cd scripts/v2.0
python3 generate_token_mappings.py
```

## Benefits

✅ **No Manual Maintenance**: Token mappings are always in sync with the CSV file
✅ **Automatic Recovery**: System regenerates mappings if missing
✅ **Consistency**: All components use the same token data
✅ **Easy Updates**: Just edit the CSV file and regenerate
✅ **Version Control**: CSV file can be easily tracked in git
✅ **Backward Compatibility**: All existing code continues to work

## File Structure

```
scripts/v2.0/
├── generate_token_mappings.py    # Generator script
├── update_token_mappings.sh      # Update script
├── token_mappings.py            # Generated mappings (auto-generated)
└── TOKEN_MAPPINGS_GUIDE.md      # This guide

data/
└── tokens.csv                   # Source of truth for all tokens
```

## Important Notes

⚠️ **DO NOT EDIT `token_mappings.py` MANUALLY** - It will be overwritten
✅ **ALWAYS EDIT `data/tokens.csv`** - This is the source of truth
🔄 **RUN UPDATE SCRIPT** after any CSV changes
💾 **COMMIT CSV CHANGES** to version control

## Troubleshooting

### "Module not found" errors
The system will automatically regenerate `token_mappings.py` if it's missing.

### Outdated mappings
Run `./update_token_mappings.sh` to regenerate from the latest CSV.

### CSV format errors
Ensure your CSV follows the exact format: `address,chain,symbol,name`
