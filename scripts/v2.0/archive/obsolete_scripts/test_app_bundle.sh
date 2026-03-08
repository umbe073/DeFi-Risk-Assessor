#!/bin/bash
"""
Test script to verify the Token Risk Assessment Tool.app launches correctly
"""

echo "🧪 Testing Token Risk Assessment Tool.app launch..."

# Test the app bundle launch
if [ -d "/Applications/Token Risk Assessment Tool.app" ]; then
    echo "✅ App bundle found"
    
    # Test the AppleScript directly
    echo "🔍 Testing AppleScript execution..."
    osascript "/Applications/Token Risk Assessment Tool.app/Contents/Resources/Scripts/main.scpt"
    
    echo "✅ App bundle test completed"
else
    echo "❌ App bundle not found"
    exit 1
fi

