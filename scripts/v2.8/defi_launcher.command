#!/bin/bash
# DeFi Risk Assessment Launcher (.command file)
# This file can be double-clicked to launch the DeFi Risk Assessment system

echo "🚀 Launching DeFi Risk Assessment..."

# Repo root (…/DeFi-Risk-Assessor), then app tree under scripts/v2.8
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

# Check if system tray is already running
if pgrep -f "system_tray.py" > /dev/null; then
    echo "⚠️ System tray is already running"
    echo "🔍 Check your menu bar for the system tray icon"
else
    # Launch system tray using screen approach
    screen -dmS "DeFi_System_Tray" bash -c "
export LSUIElement=1
export NSApplicationActivationPolicy=accessory
export NSWindowCollectionBehavior=NSWindowCollectionBehaviorParticipatesInCycle
export NSWindowLevel=Normal
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

cd $PROJECT_ROOT
python3 dashboard/system_tray.py
exec bash
"

    if [ $? -eq 0 ]; then
        echo "✅ DeFi Risk Assessment launched successfully"
        echo "🔍 Check your menu bar for the system tray icon"
        echo "📱 The system tray should be running in the background"
    else
        echo "❌ Failed to launch DeFi Risk Assessment"
        exit 1
    fi
fi

echo ""
echo "Press any key to close this window..."
read -n 1


















