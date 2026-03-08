#!/bin/bash

# Santiment Test Runner Script
# This script ensures the virtual environment is activated and dependencies are installed

echo "🚀 Setting up Santiment API Test Environment"
echo "============================================="

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "📦 Activating virtual environment..."
    
    # Try to find and activate the virtual environment
    if [ -f "pyvenv.cfg" ]; then
        echo "✅ Found virtual environment in current directory"
        source bin/activate
    elif [ -f "../pyvenv.cfg" ]; then
        echo "✅ Found virtual environment in parent directory"
        source ../bin/activate
    else
        echo "⚠️  No virtual environment found. Please ensure you're in the correct directory."
        echo "   Expected: /Users/amlfreak/Desktop/venv"
        exit 1
    fi
else
    echo "✅ Virtual environment already activated: $VIRTUAL_ENV"
fi

# Install required dependencies
echo "📦 Installing/updating required packages..."
pip install -q san python-dotenv requests

# Run the test script
echo "🧪 Running Santiment API tests..."
python3 santiment_test.py

echo "✅ Test completed!" 