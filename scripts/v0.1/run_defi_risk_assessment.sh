#!/bin/bash
# Run the DeFi Risk Assessment Script and print the summary report

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

python3 ./defi_complete_risk_assessment.py

if [ -f risk_report.json ]; then
    echo "\n=== Risk Assessment Summary ==="
    cat risk_report.json
else
    echo "risk_report.json not found."
fi 