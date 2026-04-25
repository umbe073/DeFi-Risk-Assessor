#!/bin/bash
# Launch with Unified Icon Script
# This script sets environment variables at the shell level to completely hide Python icons

# Set the project root
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
cd "$PROJECT_ROOT"

# CRITICAL: Set environment variables BEFORE launching Python
export LSUIElement="true"
export NSApplicationActivationPolicy="accessory"
export NSWindowCollectionBehavior="NSWindowCollectionBehaviorParticipatesInCycle"
export NSWindowLevel="Normal"

# Bundle identification for unified icon
export BUNDLE_IDENTIFIER="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export APP_BUNDLE="true"
export CFBundleIdentifier="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export CFBundleName="Token Risk Assessment Tool"
export CFBundleDisplayName="Token Risk Assessment Tool"
export PARENT_BUNDLE_ID="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export INHERIT_BUNDLE_ID="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"

# Performance optimizations
export PYTHONUNBUFFERED="1"
export PYTHONDONTWRITEBYTECODE="1"

# Set Python path
export PYTHONPATH="$PROJECT_ROOT/scripts/v2.0"

# CRITICAL: Launch Python with environment variables set at shell level
echo "🚀 Launching DeFi Risk Assessment with unified app icon..."
LSUIElement=1 NSApplicationActivationPolicy=accessory python3 "$PROJECT_ROOT/scripts/v2.0/dashboard/system_tray.py"


