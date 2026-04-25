#!/bin/bash
# Create New App Bundle Script
# This script creates a new app bundle from scratch

# Create the AppleScript content
cat > temp_script.scpt << 'EOF'
try
    do shell script "/Users/amlfreak/Desktop/venv/scripts/v2.0/simple_launcher.sh"
on error errMsg
    display dialog "Error launching DeFi Risk Assessment: " & errMsg buttons {"OK"} default button "OK" with icon stop
end try
EOF

# Compile the AppleScript into an app bundle
osacompile -o "/Applications/Token Risk Assessment Tool.app" temp_script.scpt

# Clean up temporary file
rm temp_script.scpt

echo "✅ New app bundle created at /Applications/Token Risk Assessment Tool.app"
echo "🔧 Now we need to add the crypto.icns icon..."

# Copy the crypto.icns icon to the new app bundle
cp "/Users/amlfreak/Desktop/venv/docs/Logos/crypto.icns" "/Applications/Token Risk Assessment Tool.app/Contents/Resources/"

echo "✅ Crypto icon copied to app bundle"
echo "🎯 App bundle should now work with the crypto.icns icon"
