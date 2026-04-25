#!/bin/bash
"""
Token Mappings Update Script
============================

This script regenerates token_mappings.py from tokens.csv
Run this script whenever you add or remove tokens from tokens.csv

Usage:
    ./update_token_mappings.sh
"""

echo "🔄 Updating token mappings from tokens.csv..."

# Change to the script directory
cd "$(dirname "$0")"

# Run the Python script to generate new mappings
python3 generate_token_mappings.py

if [ $? -eq 0 ]; then
    echo "✅ Token mappings updated successfully!"
    echo "💡 The system will now use the updated mappings."
else
    echo "❌ Failed to update token mappings"
    exit 1
fi
