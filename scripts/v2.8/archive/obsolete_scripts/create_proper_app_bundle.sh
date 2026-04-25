#!/bin/bash
# Create Proper App Bundle Script
# This script creates a proper app bundle with correct structure and permissions

APP_NAME="Token Risk Assessment Tool"
APP_PATH="/Applications/${APP_NAME}.app"
CONTENTS_PATH="$APP_PATH/Contents"
RESOURCES_PATH="$CONTENTS_PATH/Resources"
MACOS_PATH="$CONTENTS_PATH/MacOS"
SCRIPTS_PATH="$RESOURCES_PATH/Scripts"

# Create app bundle structure
mkdir -p "$MACOS_PATH"
mkdir -p "$RESOURCES_PATH"
mkdir -p "$SCRIPTS_PATH"

# Create the main executable (a simple launcher)
cat > "$MACOS_PATH/applet" << 'EOF'
#!/bin/bash
# Main executable for Token Risk Assessment Tool

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOURCES_DIR="$SCRIPT_DIR/../Resources"

# Launch the AppleScript
osascript "$RESOURCES_DIR/Scripts/main.scpt"
EOF

# Make the executable executable
chmod +x "$MACOS_PATH/applet"

# Create the AppleScript
cat > "$SCRIPTS_PATH/main.scpt" << 'EOF'
try
    do shell script "cd /Users/amlfreak/Desktop/venv/scripts/v2.0 && screen -dmS 'DeFi_System_Tray' bash -c 'export LSUIElement=1 NSApplicationActivationPolicy=accessory NSWindowCollectionBehavior=NSWindowCollectionBehaviorParticipatesInCycle NSWindowLevel=Normal PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1; cd /Users/amlfreak/Desktop/venv/scripts/v2.0; python3 dashboard/system_tray.py; exec bash'"
on error errMsg
    display dialog "Error launching DeFi Risk Assessment: " & errMsg buttons {"OK"} default button "OK" with icon stop
end try
EOF

# Copy the crypto icon
cp "/Users/amlfreak/Desktop/venv/docs/Logos/crypto.icns" "$RESOURCES_PATH/"

# Create Info.plist
cat > "$CONTENTS_PATH/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleAllowMixedLocalizations</key>
    <true/>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>applet</string>
    <key>CFBundleIconFile</key>
    <string>crypto</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Token Risk Assessment Tool</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0</string>
    <key>CFBundleSignature</key>
    <string>aplt</string>
    <key>CFBundleVersion</key>
    <string>2.0</string>
    <key>LSMinimumSystemVersionByArchitecture</key>
    <dict>
        <key>x86_64</key>
        <string>10.6</string>
    </dict>
    <key>LSRequiresCarbon</key>
    <true/>
    <key>NSAppleEventsUsageDescription</key>
    <string>This application needs to control other applications to run.</string>
    <key>OSAAppletShowStartupScreen</key>
    <false/>
</dict>
</plist>
EOF

# Create PkgInfo
echo "APPLaplt" > "$CONTENTS_PATH/PkgInfo"

# Set proper permissions
chmod -R 755 "$APP_PATH"
chown -R amlfreak:staff "$APP_PATH"

echo "✅ Proper app bundle created at: $APP_PATH"
echo "🔧 App bundle has correct structure and permissions"
echo "🎯 App bundle should now work with the crypto.icns icon"





