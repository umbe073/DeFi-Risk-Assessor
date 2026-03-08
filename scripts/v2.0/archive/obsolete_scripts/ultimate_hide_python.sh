#!/bin/bash
# Ultimate Python Icon Hiding Script
# This script launches Python processes in a way that hides them from the dock

# Set the project root
PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
cd "$PROJECT_ROOT/scripts/v2.0"

# Function to launch a hidden Python process
launch_hidden_python() {
    local script_path="$1"
    local process_name="$2"
    
    echo "🚀 Launching $process_name in hidden mode..."
    
    # Use nohup to detach from terminal and redirect all output
    nohup env LSUIElement=1 NSApplicationActivationPolicy=accessory python3 "$script_path" > /dev/null 2>&1 &
    
    local pid=$!
    echo "✅ $process_name started with PID: $pid (hidden from dock)"
    return $pid
}

# Launch system tray in hidden mode
echo "🔧 Launching DeFi Risk Assessment with ultimate icon hiding..."
launch_hidden_python "dashboard/system_tray.py" "System Tray"

echo "✅ System tray launched in hidden mode"
echo "🔍 Check your menu bar for the system tray icon"
echo "📱 The Python icon should NOT appear in the dock"

