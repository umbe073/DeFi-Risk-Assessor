#!/bin/bash
# Final Unified Icon Solution
# This script completely eliminates Python icons from the dock

# Set the project root
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
cd "$PROJECT_ROOT"

# CRITICAL: Set environment variables BEFORE any Python execution
export LSUIElement="true"
export NSApplicationActivationPolicy="accessory"
export NSWindowCollectionBehavior="NSWindowCollectionBehaviorParticipatesInCycle"
export NSWindowLevel="Normal"

# Bundle identification
export BUNDLE_IDENTIFIER="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export CFBundleIdentifier="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"

# Performance optimizations
export PYTHONUNBUFFERED="1"
export PYTHONDONTWRITEBYTECODE="1"

# Set Python path
export PYTHONPATH="$PROJECT_ROOT/scripts/v2.0"

# CRITICAL: Launch with environment variables directly in command
echo "🚀 Launching DeFi Risk Assessment with final unified icon solution..."
LSUIElement=1 NSApplicationActivationPolicy=accessory python3 "$PROJECT_ROOT/scripts/v2.0/dashboard/system_tray.py"


