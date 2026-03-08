#!/bin/bash

# DeFi System Tray Launcher with Secure Credential Management
# This script launches the Python system tray tool with secure Vespia integration
# Merged functionality from run_with_venv.py for unified management

# Get the directory where this script is located (already set above)

# Set up the Python environment
VENV_PATH="/Users/amlfreak/Desktop/venv"
PYTHON_PATH="$VENV_PATH/bin/python3"
# Always launch the v2.0 system tray
SCRIPT_FILE="dashboard/system_tray.py"

# Webhook server files
WEBHOOK_SERVER="$SCRIPT_DIR/webhook_server.py"
WEBHOOK_PID_FILE="$VENV_PATH/webhook_server.pid"

# Set app icon environment variables for subprocesses
export BUNDLE_IDENTIFIER="com.defi.riskassessment"
export APP_BUNDLE="true"
export CFBundleIdentifier="com.defi.riskassessment"

# Update paths for v1.5
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
    sys.exit(0)
except ImportError:
    print('❌ Cryptography library not found. Installing...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'cryptography'], check=True)
    print('✅ Cryptography installed successfully!')
    sys.exit(0)
except Exception as e:
    print(f'❌ Error checking dependencies: {e}')
    sys.exit(1)
"
    return $?
}

# Function to run secure credentials management
run_secure_credentials() {
    local command="$1"
    local script_path="$SCRIPT_DIR/credential_management/secure_credentials.py"
    local setup_script="$SCRIPT_DIR/credential_management/setup_vespia.py"
    
    if [ ! -f "$script_path" ]; then
        echo "❌ Secure credentials script not found at $script_path"
        return 1
    fi
    
    case "$command" in
        "setup_vespia")
            if [ -f "$setup_script" ]; then
                echo "🔐 Running Vespia setup wizard..."
                "$PYTHON_PATH" "$setup_script"
            else
                echo "❌ Vespia setup script not found"
                return 1
            fi
            ;;
        "test")
            echo "🔐 Testing Vespia credentials..."
            "$PYTHON_PATH" "$script_path" test
            ;;
        "setup")
            echo "🔐 Setting up Vespia credentials..."
            "$PYTHON_PATH" "$script_path" setup
            ;;
        "list")
            echo "🔐 Listing stored services..."
            "$PYTHON_PATH" "$script_path" list
            ;;
        "remove")
            echo "🔐 Removing Vespia credentials..."
            "$PYTHON_PATH" "$script_path" remove
            ;;
        *)
            echo "🔐 Secure Credential Management"
            echo "================================"
            echo "Usage:"
            echo "  $0 credentials setup         - Setup Vespia credentials"
            echo "  $0 credentials list          - List stored services"
            echo "  $0 credentials remove        - Remove Vespia credentials"
            echo "  $0 credentials test          - Test Vespia credentials"
            echo "  $0 credentials setup_vespia  - Run Vespia setup wizard"
            ;;
    esac
}

# Function to run system tray
run_system_tray() {
    echo "🖥️  Launching DeFi System Tray (unified)..."
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
    
    # Set environment variables for unified app icon
    export BUNDLE_IDENTIFIER="com.defi.riskassessment"
    export APP_BUNDLE="true"
    export CFBundleIdentifier="com.defi.riskassessment"
    export CFBundleName="Token Risk Assessment Tool"
    export CFBundleDisplayName="Token Risk Assessment Tool"
    export PARENT_BUNDLE_ID="com.defi.riskassessment"
    export INHERIT_BUNDLE_ID="com.defi.riskassessment"
    
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
    
    echo "🔧 Environment variables set for unified app icon"
    
    # Start webhook server proactively to ensure dashboards have data
    local webhook_script="$SCRIPT_DIR/../v2.0/webhook_server.py"
    if [ -f "$webhook_script" ]; then
        if ! nc -z localhost 5001 2>/dev/null; then
            echo "🌐 Bootstrapping webhook server on port 5001..."
            "$PYTHON_PATH" "$webhook_script" >/dev/null 2>&1 &
            sleep 2
        fi
    fi

    # Launch tray (which also auto-opens Main Dashboard)
    # Set PROJECT_ROOT and TRAY_ICON_PATH if not already set
    echo "🔍 DEBUG: TRAY_ICON_PATH at start: '$TRAY_ICON_PATH'"
    echo "🔍 DEBUG: PROJECT_ROOT at start: '$PROJECT_ROOT'"
    
    if [ -z "$PROJECT_ROOT" ]; then
        PROJECT_ROOT="/Users/amlfreak/Desktop/venv"
    fi
    
    if [ -z "$TRAY_ICON_PATH" ]; then
        if [ -f "$PROJECT_ROOT/docs/Logos/crypto_tiny.png" ]; then
            export TRAY_ICON_PATH="$PROJECT_ROOT/docs/Logos/crypto_tiny.png"
        elif [ -f "$PROJECT_ROOT/docs/Logos/crypto_small.png" ]; then
            export TRAY_ICON_PATH="$PROJECT_ROOT/docs/Logos/crypto_small.png"
        elif [ -f "$PROJECT_ROOT/docs/Logos/crypto.png" ]; then
            export TRAY_ICON_PATH="$PROJECT_ROOT/docs/Logos/crypto.png"
        fi
    fi
    echo "🔍 Setting TRAY_ICON_PATH to: $TRAY_ICON_PATH"
    TRAY_ICON_PATH="$TRAY_ICON_PATH" "$PYTHON_PATH" "$SCRIPT_FILE"
}

# Function to run credential management tool
run_manage_credentials() {
    local manage_script="$SCRIPT_DIR/credential_management/manage_credentials.py"
    
    if [ -f "$manage_script" ]; then
        echo "🔐 Running credential management tool..."
        "$PYTHON_PATH" "$manage_script"
    else
        echo "❌ Credential management script not found at $manage_script"
        return 1
    fi
}

# Function to handle credential verification with countdown
handle_credential_verification() {
    echo ""
    echo "🔐 Secure Credential Verification"
    echo "================================="
    echo "Press any key within 5 seconds to verify Vespia credentials..."
    echo "If no key is pressed, the script will continue without credential verification."
    echo ""
    
    # Countdown with key detection
    local key_pressed=false
    for i in {5..1}; do
        echo -n "⏰ Countdown: $i seconds remaining... "
        
        # Read a single character with timeout
        if read -n 1 -t 1 key; then
            echo "✅ Key pressed!"
            key_pressed=true
            break
        else
            echo ""
        fi
    done
    
    if [ "$key_pressed" = true ]; then
        echo ""
        echo "🔐 Proceeding with credential verification..."
        echo "Enter master password when prompted:"
        echo ""
        
        # Check if Vespia credentials are configured
        if ! run_secure_credentials test > /dev/null 2>&1; then
            echo "⚠️  Vespia credentials not configured."
            echo "📝 Would you like to set up Vespia credentials now? (y/N)"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                echo "🔐 Setting up Vespia credentials..."
                if ! run_secure_credentials setup_vespia; then
                    echo "❌ Vespia setup failed!"
                    echo "💡 You can still run the system tray without Vespia integration."
                fi
            else
                echo "💡 Continuing without Vespia integration..."
            fi
        else
            echo "✅ Vespia credentials configured!"
        fi
    else
        echo ""
        echo "⏭️  Skipping credential verification - continuing automatically..."
        echo "💡 You can manually verify credentials later using: $0 credentials test"
    fi
}

# Enhanced system functions
start_webhook_server() {
    echo "🚀 Starting webhook server..."
    if [ -f "$WEBHOOK_PID_FILE" ]; then
        PID=$(cat "$WEBHOOK_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Webhook server already running (PID: $PID)"
            return 0
        fi
    fi
    
    nohup "$PYTHON_PATH" "$WEBHOOK_SERVER" > /dev/null 2>&1 &
    echo $! > "$WEBHOOK_PID_FILE"
    sleep 2
    echo "✅ Webhook server started"
}

stop_webhook_server() {
    if [ -f "$WEBHOOK_PID_FILE" ]; then
        PID=$(cat "$WEBHOOK_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill "$PID" 2>/dev/null
            rm -f "$WEBHOOK_PID_FILE"
            echo "✅ Webhook server stopped"
        fi
    fi
}

run_enhanced_system() {
    echo "🔄 Running enhanced data collection..."
    
    # Start webhook server if not running
    start_webhook_server
    
    # Verify tokens.csv exists and has correct format
    echo "📝 Verifying tokens.csv..."
    "$PYTHON_PATH" -c "
import pandas as pd
import os
import sys

data_dir = '$VENV_PATH/data'
tokens_csv = os.path.join(data_dir, 'tokens.csv')

# Check if tokens.csv exists
if not os.path.exists(tokens_csv):
    print('❌ Error: tokens.csv not found at', tokens_csv)
    sys.exit(1)

# Load and verify the CSV
try:
    df = pd.read_csv(tokens_csv)
    # Support both legacy lowercase headers and canonical headers
    column_aliases = {
        'address': 'Contract Address',
        'chain': 'Chain',
        'symbol': 'Symbol',
        'name': 'Token Name',
    }
    for src, dest in column_aliases.items():
        if src in df.columns and dest not in df.columns:
            df[dest] = df[src]
    required_columns = ['Contract Address', 'Token Name', 'Symbol', 'Chain']
    
    # Check if all required columns exist after alias fill
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f'❌ Error: Missing columns in tokens.csv: {missing_columns}')
        print(f'   Current columns: {list(df.columns)}')
        sys.exit(1)
    
    # Remove empty rows if any
    df = df.dropna(how='all')
    df = df[df['Contract Address'].notna()]
    
    # Save cleaned version if needed
    df.to_csv(tokens_csv, index=False)
    
    print(f'✅ tokens.csv verified: {len(df)} tokens loaded')
    print(f'   Columns: {list(df.columns)}')
    
except Exception as e:
    print(f'❌ Error reading tokens.csv: {e}')
    sys.exit(1)
"
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to verify tokens.csv"
        return 1
    fi
    
    # Trigger cache refresh via webhook
    echo "📊 Refreshing data cache..."
    curl -X POST http://localhost:5000/refresh_cache 2>/dev/null || echo "⚠️ Cache refresh failed"
    
    # Update Token Data Viewer CSV
    echo "📊 Updating Token Data Viewer CSV..."
    "$PYTHON_PATH" "$SCRIPT_DIR/update_token_data_viewer.py" || echo "⚠️ Token Data Viewer update failed"
    
    echo "✅ Enhanced data collection complete"
}

# Main execution logic
main() {
    # Check if any command line arguments were provided
    if [ $# -eq 0 ]; then
        # No arguments - run the full system tray workflow
        echo "🚀 Launching DeFi System Tray..."
        echo "📁 Working directory: $SCRIPT_DIR"
        echo "🐍 Python: $PYTHON_PATH"
        echo "📄 Script: $SCRIPT_FILE"
        echo "🔐 Secure credentials: Enabled"
        echo ""
        
        # Check dependencies first
        if ! check_dependencies; then
            echo "❌ Dependency check failed!"
            exit 1
        fi
        
        echo ""
        echo "🖥️  Starting system tray..."
        echo "=================================================="
        
        # Launch the system tray
        run_system_tray
        
        # Check exit status
        if [ $? -eq 0 ]; then
            echo ""
            echo "✅ System tray launched successfully!"
            echo "🖥️  System tray is now running in the background"
            echo "📊 Access the dashboard through the system tray icon"
        else
            echo ""
            echo "❌ System tray failed to start!"
            echo "📝 Check the logs for error details"
            exit 1
        fi
    else
        # Handle specific commands
        case "$1" in
            "credentials")
                run_secure_credentials "${2:-}"
                ;;
            "manage_creds")
                run_manage_credentials
                ;;
            "system_tray")
                run_system_tray
                ;;
            "check_deps")
                check_dependencies
                ;;
            "enhanced")
                run_enhanced_system
                ;;
            "webhook")
                if [ "${2:-}" = "stop" ]; then
                    stop_webhook_server
                else
                    start_webhook_server
                fi
                ;;
            "update_viewer")
                echo "📊 Updating Token Data Viewer CSV..."
                "$PYTHON_PATH" "$SCRIPT_DIR/update_token_data_viewer.py"
                ;;
            *)
                echo "🚀 DeFi System Tray Launcher"
                echo "============================"
                echo "Usage:"
                echo "  $0                                    - Launch system tray"
                echo "  $0 credentials [command]              - Manage secure credentials"
                echo "  $0 manage_creds                       - Easy credential management"
                echo "  $0 system_tray                        - Launch system tray only"
                echo "  $0 enhanced                           - Run enhanced data collection only"
                echo "  $0 webhook [stop]                     - Start/stop webhook server"
                echo "  $0 update_viewer                      - Update Token Data Viewer CSV"
                echo "  $0 check_deps                         - Check dependencies"
                echo ""
                echo "Credential commands:"
                echo "  $0 credentials setup                  - Setup Vespia credentials"
                echo "  $0 credentials list                   - List stored services"
                echo "  $0 credentials remove                 - Remove Vespia credentials"
                echo "  $0 credentials test                   - Test Vespia credentials"
                echo "  $0 credentials setup_vespia           - Run Vespia setup wizard"
                ;;
        esac
    fi
}

# Run the main function with all arguments
main "$@"