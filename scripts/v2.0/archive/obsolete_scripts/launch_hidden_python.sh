#!/bin/bash
# Launch Hidden Python Script
# This script launches Python processes in a way that completely hides them from the dock

# Set the project root
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
cd "$PROJECT_ROOT"

# AGGRESSIVE unified app icon environment variables
export BUNDLE_IDENTIFIER="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export APP_BUNDLE="true"
export CFBundleIdentifier="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export CFBundleName="Token Risk Assessment Tool"
export CFBundleDisplayName="Token Risk Assessment Tool"
export PARENT_BUNDLE_ID="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"
export INHERIT_BUNDLE_ID="com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool"

# CRITICAL: Force Python to run as a background process
export NSApplicationActivationPolicy="accessory"
export LSUIElement="true"
export NSWindowCollectionBehavior="NSWindowCollectionBehaviorParticipatesInCycle"
export NSWindowLevel="Normal"

# AGGRESSIVE: Force tkinter to use framework mode
export TK_SILENCE_DEPRECATION="1"
export PYTHON_CONFIGURE_OPTS="--enable-framework"
export TK_FRAMEWORK="1"
export DISPLAY=":0"

# Security enhancements
export NSDocumentRevisionsKeepEveryOne="1"
export NSAppTransportSecurity="true"

# AGGRESSIVE: Force basic mode and skip ALL macOS checks
export TK_FORCE_BASIC_MODE="1"
export TK_SKIP_ALL_MACOS_CHECKS="1"
export TK_DISABLE_ALL_MACOS_FEATURES="1"
export TK_DISABLE_MACOS_VERSION_CALLS="1"
export TK_SKIP_MACOS_VERSION_CHECK="1"
export TK_DISABLE_MACOS_VERSION_METHOD="1"
export TK_USE_LEGACY_MODE="1"
export TK_DISABLE_NATIVE_FEATURES="1"
export TK_FORCE_COMPATIBILITY_MODE="1"

# Performance optimizations
export PYTHONUNBUFFERED="1"
export PYTHONDONTWRITEBYTECODE="1"

# Set Python path
export PYTHONPATH="$PROJECT_ROOT/scripts/v2.0"

# CRITICAL: Launch Python with special flags to hide from dock
echo "🚀 Launching Python process with hidden dock icon..."
nohup python3 -c "
import os
import sys
import subprocess

# Set environment variables for the subprocess
env = os.environ.copy()
env['NSApplicationActivationPolicy'] = 'accessory'
env['LSUIElement'] = 'true'
env['BUNDLE_IDENTIFIER'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
env['CFBundleIdentifier'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'

# Launch the system tray
subprocess.run(['python3', '$PROJECT_ROOT/scripts/v2.0/dashboard/system_tray.py'], env=env)
" > /dev/null 2>&1 &

echo "✅ Python process launched in background with hidden dock icon"

