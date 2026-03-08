#!/bin/bash
"""
Launch DeFi Risk Assessment from App Bundle
This script launches the system tray directly from the app bundle to ensure unified icon
"""

# Set the project root
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
APP_BUNDLE="/Applications/Token Risk Assessment Tool.app"

# Check if app bundle exists
if [ ! -d "$APP_BUNDLE" ]; then
    echo "❌ App bundle not found: $APP_BUNDLE"
    exit 1
fi

# Set unified app icon environment variables with CORRECT bundle identifier
export BUNDLE_IDENTIFIER="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export APP_BUNDLE="true"
export CFBundleIdentifier="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export CFBundleName="Token Risk Assessment Tool"
export CFBundleDisplayName="Token Risk Assessment Tool"
export PARENT_BUNDLE_ID="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export INHERIT_BUNDLE_ID="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"

# Set activation policy for background operation
export NSApplicationActivationPolicy="accessory"
export LSUIElement="true"

# Tkinter compatibility
export TK_SILENCE_DEPRECATION="1"
export PYTHON_CONFIGURE_OPTS="--enable-framework"
export TK_FRAMEWORK="1"
export DISPLAY=":0"

# Security enhancements
export NSDocumentRevisionsKeepEveryOne="1"
export NSAppTransportSecurity="true"

# Force basic mode and skip all macOS checks
export TK_FORCE_BASIC_MODE="1"
export TK_SKIP_ALL_MACOS_CHECKS="1"
export TK_DISABLE_ALL_MACOS_FEATURES="1"
export TK_DISABLE_MACOS_VERSION_CALLS="1"
export TK_SKIP_MACOS_VERSION_CHECK="1"
export TK_DISABLE_MACOS_VERSION_METHOD="1"
export TK_USE_LEGACY_MODE="1"
export TK_DISABLE_NATIVE_FEATURES="1"
export TK_FORCE_COMPATIBILITY_MODE="1"

# Basic window behavior
export NSWindowCollectionBehavior="NSWindowCollectionBehaviorParticipatesInCycle"
export NSWindowLevel="Normal"

# Additional variables to prevent Python icon from showing
export PYTHON_CONFIGURE_OPTS="--enable-framework"
export TK_FRAMEWORK="1"
export TK_SILENCE_DEPRECATION="1"

# Performance optimizations
export PYTHONUNBUFFERED="1"
export PYTHONDONTWRITEBYTECODE="1"

# Set Python path
export PYTHONPATH="$PROJECT_ROOT/scripts/v2.0"

# Change to project directory
cd "$PROJECT_ROOT"

echo "🚀 Launching DeFi Risk Assessment from app bundle with unified icon..."

# Launch using the app bundle's Python executable if available
if [ -f "$APP_BUNDLE/Contents/MacOS/applet" ]; then
    echo "✅ Using app bundle executable"
    "$APP_BUNDLE/Contents/MacOS/applet" "$PROJECT_ROOT/scripts/v2.0/dashboard/system_tray.py"
else
    echo "⚠️ App bundle executable not found, using system Python"
    python3 "$PROJECT_ROOT/scripts/v2.0/dashboard/system_tray.py"
fi

