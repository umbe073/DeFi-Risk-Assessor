#!/bin/bash

# DeFi Risk Assessment Complete Launcher
# This script launches the system tray with all necessary subprocesses and dependencies

# Set up the Python environment
VENV_PATH="/Users/amlfreak/Desktop/venv"
PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
SCRIPT_FILE="dashboard/system_tray.py"



# Update paths for v2.0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python script exists
if [ ! -f "$SCRIPT_FILE" ]; then
    echo "Error: $SCRIPT_FILE not found in $SCRIPT_DIR"
    exit 1
fi

# Check if Python environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: Python environment not found at $PYTHON_PATH"
    echo "Please ensure the virtual environment is set up correctly."
    exit 1
fi

# Function to check dependencies
check_dependencies() {
    echo "🔧 Checking dependencies..."
    "$PYTHON_PATH" -c "
import subprocess
import sys
try:
    import cryptography
    print('✅ Cryptography library is available')
except ImportError:
    print('❌ Cryptography library not found. Installing...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'cryptography'], check=True)
    print('✅ Cryptography installed successfully!')

try:
    import PIL
    print('✅ PIL (Pillow) library is available')
except ImportError:
    print('❌ PIL library not found. Installing...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pillow'], check=True)
    print('✅ PIL installed successfully!')

try:
    import pystray
    print('✅ pystray library is available')
except ImportError:
    print('❌ pystray library not found. Installing...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pystray'], check=True)
    print('✅ pystray installed successfully!')

try:
    import requests
    print('✅ requests library is available')
except ImportError:
    print('❌ requests library not found. Installing...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], check=True)
    print('✅ requests installed successfully!')

try:
    import psutil
    print('✅ psutil library is available')
except ImportError:
    print('❌ psutil library not found. Installing...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'psutil'], check=True)
    print('✅ psutil installed successfully!')

try:
    import flask
    print('✅ flask library is available')
except ImportError:
    print('❌ flask library not found. Installing...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'flask'], check=True)
    print('✅ flask installed successfully!')

print('✅ All dependencies verified!')
sys.exit(0)
"
    return $?
}

# Function to start webhook server
start_webhook_server() {
    echo "🚀 Starting webhook server..."
    WEBHOOK_SCRIPT="$VENV_PATH/scripts/v1.5/webhook_server.py"
    
    if [ -f "$WEBHOOK_SCRIPT" ]; then
        # Check if webhook server is already running
        if ! nc -z localhost 5001 2>/dev/null; then
            # Start webhook server in background
            "$PYTHON_PATH" "$WEBHOOK_SCRIPT" > /dev/null 2>&1 &
            WEBHOOK_PID=$!
            echo "✅ Webhook server started with PID: $WEBHOOK_PID"
            
            # Wait for server to start
            sleep 3
            
            # Verify server is running
            if nc -z localhost 5001 2>/dev/null; then
                echo "✅ Webhook server is running on port 5001"
            else
                echo "⚠️ Webhook server may not have started properly"
            fi
        else
            echo "✅ Webhook server already running on port 5001"
        fi
    else
        echo "⚠️ Webhook server script not found at $WEBHOOK_SCRIPT"
    fi
}

# Function to run system tray
run_system_tray() {
    echo "🖥️  Launching DeFi System Tray..."
    echo "Using Python: $PYTHON_PATH"
    echo "=================================================="
    
    # Check if system tray is already running
    local lock_dir="/tmp/defi_dashboard_locks"
    local lock_file="$lock_dir/system_tray.lock"
    
    if [ -f "$lock_file" ]; then
        echo "⚠️  System tray is already running!"
        echo "💡 Check the menu bar for the system tray icon"
        return 0
    fi
    

    
    # Set activation policy for background operation
    export NSApplicationActivationPolicy="accessory"
    export LSUIElement="true"
    
    # Additional macOS environment variables
    export NSDocumentRevisionsKeepEveryOne="1"
    export NSAppTransportSecurity="true"
    
    # Force basic mode and skip all macOS checks
    export TK_FORCE_BASIC_MODE="1"
    export TK_SKIP_ALL_MACOS_CHECKS="1"
    export TK_DISABLE_ALL_MACOS_FEATURES="1"
    export TK_DISABLE_MACOS_VERSION_CALLS="1"
    export TK_SKIP_MACOS_VERSION_CHECK="1"
    export TK_DISABLE_MACOS_VERSION_METHOD="1"
    export TK_USE_LEGACY_MODE="1"
    export TK_DISABLE_NATIVE_FEATURES="1"
    export TK_FORCE_COMPATIBILITY_MODE="1"
    
    echo "🔧 Environment variables set"
    
    # Start webhook server first
    start_webhook_server
    
    # Launch the system tray
    echo ""
    echo "✅ System launched successfully!"
    echo "🖥️  System tray is now running in the background"
    echo "📊 Access the dashboard through the system tray icon"
    echo ""
    
    "$PYTHON_PATH" "$SCRIPT_FILE"
}

# Main execution logic
main() {
    echo "🚀 Launching DeFi Risk Assessment Complete System..."
    echo "📁 Working directory: $SCRIPT_DIR"
    echo "🐍 Python: $PYTHON_PATH"
    echo "📄 Script: $SCRIPT_FILE"
    echo "🔐 Secure credentials: Enabled"
    echo "🌐 Webhook server: Enabled"
    echo ""
    
    # Check dependencies first
    if ! check_dependencies; then
        echo "❌ Dependency check failed!"
        exit 1
    fi
    
    echo ""
    echo "🖥️  Starting complete system..."
    echo "=================================================="
    
    # Launch the system tray with all subprocesses
    run_system_tray
    
    # Check exit status - this runs when the system tray closes
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo ""
        echo "🔄 System tray stopped normally"
    elif [ $exit_code -eq 130 ] || [ $exit_code -eq 143 ]; then
        # SIGINT (Ctrl+C) or SIGTERM - user interrupted
        echo ""
        echo "🔄 System tray stopped by user"
    else
        echo ""
        echo "❌ System tray crashed or failed!"
        echo "📝 Check the logs for error details"
        exit 1
    fi
}

# Run the main function
main "$@"
