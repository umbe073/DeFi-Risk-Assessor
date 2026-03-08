#!/bin/bash

# DeFi Risk Assessment Launcher with Secure Credential Management
# This script launches the Python risk assessment tool with secure Vespia integration
# Merged functionality from run_with_venv.py for unified management

# Get the directory where this script is located (already set above)

# Set up the Python environment
VENV_PATH="/Users/amlfreak/Desktop/venv"
PYTHON_PATH="$VENV_PATH/bin/python3"
SCRIPT_FILE="defi_complete_risk_assessment.py"

# Update paths for v1.4
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

# Function to run risk assessment
run_risk_assessment() {
    echo "🔍 Running DeFi Risk Assessment..."
    echo "Using Python: $PYTHON_PATH"
    echo "=================================================="
    
    "$PYTHON_PATH" "$SCRIPT_FILE"
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
                    echo "💡 You can still run the risk assessment without Vespia integration."
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

# Main execution logic
main() {
    # Check if any command line arguments were provided
    if [ $# -eq 0 ]; then
        # No arguments - run the full risk assessment workflow
        echo "🚀 Launching DeFi Risk Assessment Tool with Secure Vespia Integration..."
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
        
        # Credential verification is now handled within the Python script
        echo "🔐 Credential verification will be handled by the Python script..."
        
        echo ""
        echo "🔍 Starting risk assessment..."
        echo "=================================================="
        
        # Launch the risk assessment
        run_risk_assessment
        
        # Update the Excel report after the main script completes (if it exists)
        if [ -f "update_risk_assessment_xlsx.py" ]; then
            "$PYTHON_PATH" update_risk_assessment_xlsx.py
        fi
        
        # Check exit status
        if [ $? -eq 0 ]; then
            echo ""
            echo "✅ Risk assessment completed successfully!"
            echo "📊 Check the '../../data/' directory for results"
            echo "📝 Check the '../../logs/' directory for detailed logs"
        else
            echo ""
            echo "❌ Risk assessment failed!"
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
            "risk_assessment")
                run_risk_assessment
                ;;
            "check_deps")
                check_dependencies
                ;;
            *)
                echo "🚀 Application Runner"
                echo "===================="
                echo "Usage:"
                echo "  $0                                    - Run full risk assessment workflow"
                echo "  $0 credentials [command]              - Manage secure credentials"
                echo "  $0 manage_creds                       - Easy credential management"
                echo "  $0 risk_assessment                    - Run risk assessment only"
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