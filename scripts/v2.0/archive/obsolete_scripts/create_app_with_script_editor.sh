#!/bin/bash
# Create App Bundle with Script Editor
# This script creates a new app bundle using osacompile

# Create a simple AppleScript file
cat > temp_script.scpt << 'EOF'
try
    do shell script "cd /Users/amlfreak/Desktop/venv/scripts/v2.0 && python3 dashboard/system_tray.py"
on error errMsg
    display dialog "Error launching DeFi Risk Assessment: " & errMsg buttons {"OK"} default button "OK" with icon stop
end try
EOF

# Compile the AppleScript into an app bundle
osacompile -o "/Applications/Token Risk Assessment Tool.app" temp_script.scpt

# Clean up temporary file
rm temp_script.scpt

echo "✅ New app bundle created at /Applications/Token Risk Assessment Tool.app"

# Copy the crypto.icns icon
cp "/Users/amlfreak/Desktop/venv/docs/Logos/crypto.icns" "/Applications/Token Risk Assessment Tool.app/Contents/Resources/"

echo "✅ Crypto icon copied to app bundle"

# Update the Info.plist to use the crypto icon
sed -i '' 's/<string>applet<\/string>/<string>crypto<\/string>/g' "/Applications/Token Risk Assessment Tool.app/Contents/Info.plist"

echo "✅ Info.plist updated to use crypto icon"
echo "🎯 App bundle should now work with the crypto.icns icon"





