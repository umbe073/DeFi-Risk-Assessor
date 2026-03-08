#!/bin/bash

# DeFi Risk Assessment Launcher
# This script launches the Python risk assessment tool with native progress bar

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Set up the Python environment
VENV_PATH="/Users/amlfreak/Desktop/venv"
PYTHON_PATH="$VENV_PATH/bin/python3"
SCRIPT_FILE="defi_complete_risk_assessment.py"

# Check if Python script exists
if [ ! -f "$SCRIPT_FILE" ]; then
    echo "Error: $SCRIPT_FILE not found in $SCRIPT_DIR"
    exit 1
fi

# Check if Python environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: Python environment not found at $PYTHON_PATH"
    echo "Please ensure the virtual environment is set up correctly."
    exit 1
fi

echo "🚀 Launching DeFi Risk Assessment Tool..."
echo "📁 Working directory: $SCRIPT_DIR"
echo "🐍 Python: $PYTHON_PATH"
echo "📄 Script: $SCRIPT_FILE"
echo ""

# Launch the Python script with progress bar
cd "$SCRIPT_DIR"
"$PYTHON_PATH" "$SCRIPT_FILE"

# Update the Excel report after the main script completes
"$PYTHON_PATH" update_risk_assessment_xlsx.py

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Risk assessment completed successfully!"
    echo "📊 Check the '../../../data/' directory for results"
    echo "📝 Check the '../../../logs/' directory for detailed logs"
else
    echo ""
    echo "❌ Risk assessment failed!"
    echo "📝 Check the logs for error details"
    exit 1
fi