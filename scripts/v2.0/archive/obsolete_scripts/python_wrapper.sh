#!/bin/bash
# Python Wrapper Script
# This script sets environment variables at the shell level to hide Python icons

# Set critical environment variables BEFORE launching Python
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

# Launch Python with the provided arguments
exec python3 "$@"

