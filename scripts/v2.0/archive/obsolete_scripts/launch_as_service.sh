#!/bin/bash
# Launch as Service Script
# This script launches Python processes as background services to avoid dock icons

SCRIPT_PATH="$1"
SERVICE_NAME="$2"

if [ -z "$SCRIPT_PATH" ]; then
    echo "Usage: $0 <script_path> [service_name]"
    exit 1
fi

if [ -z "$SERVICE_NAME" ]; then
    SERVICE_NAME="python_service"
fi

# Create a plist file for the service
PLIST_FILE="/tmp/${SERVICE_NAME}.plist"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/env</string>
        <string>LSUIElement=1</string>
        <string>NSApplicationActivationPolicy=accessory</string>
        <string>python3</string>
        <string>${SCRIPT_PATH}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Users/amlfreak/Desktop/venv/scripts/v2.0</string>
    <key>StandardOutPath</key>
    <string>/tmp/${SERVICE_NAME}.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/${SERVICE_NAME}.error.log</string>
</dict>
</plist>
EOF

echo "🚀 Launching $SERVICE_NAME as background service..."

# Load the service
launchctl load "$PLIST_FILE"

if [ $? -eq 0 ]; then
    echo "✅ $SERVICE_NAME launched as background service"
    echo "📱 Service should not show in dock"
else
    echo "❌ Failed to launch $SERVICE_NAME"
    exit 1
fi





