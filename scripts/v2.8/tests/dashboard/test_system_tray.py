#!/usr/bin/env python3
"""
Test script for system tray service launching
This script tests the ability to launch various services from the system tray
"""

import os
import sys
import subprocess
import tempfile
import json
import time

# Add the current directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))

def test_file_exists(file_path, name):
    """Test if a file exists"""
    if os.path.exists(file_path):
        print(f"✅ {name}: {file_path}")
        return True
    else:
        print(f"❌ {name}: {file_path} (NOT FOUND)")
        return False

def test_service_launch(script_path, service_name):
    """Test launching a service"""
    try:
        print(f"\n🔍 Testing {service_name} launch...")
        
        if not os.path.exists(script_path):
            print(f"❌ Script not found: {script_path}")
            return False
        
        env = os.environ.copy()
        env['PYTHONPATH'] = PROJECT_ROOT
        env['APP_BUNDLE'] = 'true'
        env['BUNDLE_IDENTIFIER'] = 'com.defi.riskassessment'
        
        print(f"🚀 Launching {service_name}...")
        process = subprocess.Popen([
            sys.executable, script_path
        ], env=env, cwd=PROJECT_ROOT)
        
        print(f"✅ Process started with PID: {process.pid}")
        
        # Wait a bit to see if it starts successfully
        time.sleep(2)
        
        # Check if process is still running
        try:
            os.kill(process.pid, 0)
            print(f"✅ {service_name} is running (PID: {process.pid})")
            
            # Terminate the test process
            process.terminate()
            time.sleep(1)
            
            # Force kill if still running
            try:
                os.kill(process.pid, 0)
                process.kill()
                print(f"⚠️ Force killed {service_name}")
            except OSError:
                pass
                
            return True
        except OSError:
            print(f"❌ {service_name} process died unexpectedly")
            return False
            
    except Exception as e:
        print(f"❌ Error testing {service_name}: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Testing System Tray Service Launching")
    print("=" * 50)
    
    # Test file existence
    print("\n📁 Checking required files...")
    files_to_test = {
        'Main Dashboard': os.path.join(current_dir, 'defi_dashboard.py'),
        'API Dashboard': os.path.join(current_dir, 'api_service_dashboard.py'),
        'Credential Manager': os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management', 'gui_credentials.py'),
        'Chain Manager': os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management', 'gui_chains.py'),
        'Assessment Script': os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'defi_complete_risk_assessment_clean.py')
    }
    
    all_files_exist = True
    for name, path in files_to_test.items():
        if not test_file_exists(path, name):
            all_files_exist = False
    
    if not all_files_exist:
        print("\n❌ Some required files are missing. Please check the file paths.")
        return
    
    print("\n✅ All required files found!")
    
    # Test service launching (only test credential manager to avoid opening too many windows)
    print("\n🚀 Testing service launching...")
    
    # Test credential manager (this should open a GUI window)
    cred_path = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management', 'gui_credentials.py')
    if test_service_launch(cred_path, "Credential Manager"):
        print("✅ Credential Manager launch test passed")
    else:
        print("❌ Credential Manager launch test failed")
    
    print("\n🧪 Test completed!")
    print("\nNote: Only tested Credential Manager to avoid opening too many windows.")
    print("The system tray should be able to launch all services if this test passes.")

if __name__ == "__main__":
    main()
