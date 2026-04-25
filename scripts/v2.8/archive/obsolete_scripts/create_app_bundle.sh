#!/bin/bash
set -euo pipefail

# Create a robust .app bundle that runs macos_dock_app.py with crypto.icns

PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
APP_NAME="DeFi Risk Assessment"
BUNDLE_ID="com.defi.riskassessment"
APP_DIR="$PROJECT_ROOT/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
ICON_SRC="$PROJECT_ROOT/docs/Logos/crypto.icns"
ENTRY_PY="$PROJECT_ROOT/scripts/v2.0/macos_dock_app.py"
VENV_PY="$PROJECT_ROOT/bin/python3"

echo "Creating app bundle at: $APP_DIR"
rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

# Info.plist
cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><false/>
  <key>NSHighResolutionCapable</key><true/>
  <key>CFBundleIconFile</key><string>crypto.icns</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.finance</string>
</dict>
</plist>
PLIST

# Icon
if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$RESOURCES/crypto.icns"
fi

# Launcher script that uses the project's venv python
cat > "$MACOS/launcher" <<'LAUNCH'
#!/bin/bash
set -e
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
PY="$PROJECT_ROOT/bin/python3"

# Set up environment variables for unified app behavior
export APP_BUNDLE=true
export BUNDLE_IDENTIFIER=com.defi.riskassessment
export CFBundleIdentifier=com.defi.riskassessment
export PARENT_BUNDLE_ID=com.defi.riskassessment
export INHERIT_BUNDLE_ID=com.defi.riskassessment

# Set TRAY_ICON_PATH for the system tray
if [ -f "$PROJECT_ROOT/docs/Logos/crypto_tiny.png" ]; then
    export TRAY_ICON_PATH="$PROJECT_ROOT/docs/Logos/crypto_tiny.png"
elif [ -f "$PROJECT_ROOT/docs/Logos/crypto_small.png" ]; then
    export TRAY_ICON_PATH="$PROJECT_ROOT/docs/Logos/crypto_small.png"
elif [ -f "$PROJECT_ROOT/docs/Logos/crypto.png" ]; then
    export TRAY_ICON_PATH="$PROJECT_ROOT/docs/Logos/crypto.png"
fi

exec "$PY" "$PROJECT_ROOT/scripts/v2.0/macos_dock_app.py"
LAUNCH
chmod +x "$MACOS/launcher"

echo "App bundle created."

echo "Note: To sign and staple the app, run:"
echo "  codesign --deep --force --options runtime --entitlements \"$PROJECT_ROOT/scripts/v2.0/macos_entitlements.plist\" -s \"Developer ID Application: YOUR_NAME (TEAMID)\" \"$APP_DIR\""
echo "  xcrun stapler staple \"$APP_DIR\""


