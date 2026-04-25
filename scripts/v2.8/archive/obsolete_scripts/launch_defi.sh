#!/bin/bash
# DeFi Risk Assessment Launcher
# This script launches the DeFi Risk Assessment system tray

echo "🚀 Launching DeFi Risk Assessment..."

# Set the project root
PROJECT_ROOT="/Users/amlfreak/Desktop/venv/scripts/v2.0"
cd "$PROJECT_ROOT"

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

# Keep the script running for a moment to show the message
sleep 3





