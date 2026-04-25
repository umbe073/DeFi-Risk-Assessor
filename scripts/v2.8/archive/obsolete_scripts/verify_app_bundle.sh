#!/bin/bash
# Verification script for Token Risk Assessment Tool.app
# Tests the app bundle and confirms unified app icon functionality

echo "🧪 Verifying Token Risk Assessment Tool.app..."

# Check if app bundle exists
if [ -d "/Applications/Token Risk Assessment Tool.app" ]; then
    echo "✅ App bundle found"
else
    echo "❌ App bundle not found"
    exit 1
fi

# Check if the script exists
if [ -f "/Applications/Token Risk Assessment Tool.app/Contents/Resources/Scripts/main.scpt" ]; then
    echo "✅ AppleScript found"
else
    echo "❌ AppleScript not found"
    exit 1
fi

# Check if launch script exists
if [ -f "./launch_unified_app.sh" ]; then
    echo "✅ Launch script found"
else
    echo "❌ Launch script not found"
    exit 1
fi

# Test the AppleScript execution
echo "🔍 Testing AppleScript execution..."
if osascript "/Applications/Token Risk Assessment Tool.app/Contents/Resources/Scripts/main.scpt" > /dev/null 2>&1; then
    echo "✅ AppleScript executed successfully"
else
    echo "❌ AppleScript execution failed"
    exit 1
fi

echo "✅ App bundle verification completed successfully!"
echo ""
echo "🎯 Next steps:"
echo "1. Double-click 'Token Risk Assessment Tool.app' in Applications"
echo "2. Verify only one app icon appears in the dock"
echo "3. Launch subprocesses from the system tray menu"
echo "4. Confirm all processes run under the unified app icon"
