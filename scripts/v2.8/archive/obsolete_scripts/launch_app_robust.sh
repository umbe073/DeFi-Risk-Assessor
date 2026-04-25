#!/bin/bash

# DeFi Risk Assessment App Launcher - Robust Version
# This script handles Python path issues and environment setup

# Set absolute paths
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
PYTHON_EXECUTABLE="$PROJECT_ROOT/bin/python3"
SCRIPT_PATH="$PROJECT_ROOT/scripts/v2.0/dashboard/system_tray.py"

# Change to project directory
cd "$PROJECT_ROOT"

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT/scripts/v2.0:$PYTHONPATH"
export DISPLAY=":0"
export TK_SILENCE_DEPRECATION="1"

# Verify Python executable exists
if [ ! -f "$PYTHON_EXECUTABLE" ]; then
    echo "❌ Python executable not found: $PYTHON_EXECUTABLE"
    exit 1
fi

# Verify script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Script not found: $SCRIPT_PATH"
    exit 1
fi

# Launch the system tray
echo "🚀 Launching DeFi System Tray..."
echo "📁 Working directory: $(pwd)"
echo "🐍 Python: $PYTHON_EXECUTABLE"
echo "📄 Script: $SCRIPT_PATH"

"$PYTHON_EXECUTABLE" "$SCRIPT_PATH"
