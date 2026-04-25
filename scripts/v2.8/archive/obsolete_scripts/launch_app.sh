#!/bin/bash

# DeFi Risk Assessment App Launcher
# This script launches the system tray directly

# Set the project root
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
cd "$PROJECT_ROOT"

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT/scripts/v2.0:$PYTHONPATH"
export DISPLAY=":0"
export TK_SILENCE_DEPRECATION="1"

# Launch the system tray
echo "🚀 Launching DeFi System Tray..."
"$PROJECT_ROOT/bin/python3" "$PROJECT_ROOT/scripts/v2.0/dashboard/system_tray.py"
