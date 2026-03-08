#!/usr/bin/env python3
"""
Dashboard Wrapper
Handles tkinter compatibility issues on macOS
"""

import os
import sys
import subprocess
import signal
import time

def setup_macos_environment():
    """Setup macOS environment for tkinter compatibility"""
    if sys.platform == "darwin":
        # Set environment variables for tkinter compatibility
        os.environ['TK_SILENCE_DEPRECATION'] = '1'
        os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
        os.environ['TK_FRAMEWORK'] = '1'
        
        # Additional environment variables
        os.environ['DISPLAY'] = ':0'
        os.environ['TCL_LIBRARY'] = '/System/Library/Frameworks/Tcl.framework/Versions/8.6/Resources/Scripts'
        os.environ['TK_LIBRARY'] = '/System/Library/Frameworks/Tk.framework/Versions/8.6/Resources/Scripts'

def launch_dashboard():
    """Launch the dashboard with proper environment"""
    setup_macos_environment()
    
    # Get the path to the dashboard script
    dashboard_script = os.path.join(os.path.dirname(__file__), 'defi_dashboard.py')
    
    if not os.path.exists(dashboard_script):
        print(f"❌ Dashboard script not found: {dashboard_script}")
        return False
    
    try:
        print("🚀 Launching DeFi Dashboard...")
        
        # Launch the dashboard with the current Python interpreter
        process = subprocess.Popen([
            sys.executable, dashboard_script
        ], env=os.environ.copy())
        
        print(f"✅ Dashboard process started with PID: {process.pid}")
        
        # Wait a moment to see if it crashes
        time.sleep(2)
        
        # Check if process is still running
        try:
            os.kill(process.pid, 0)
            print("✅ Dashboard is running successfully")
            return True
        except OSError:
            print("❌ Dashboard crashed or stopped unexpectedly")
            return False
            
    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")
        return False

def main():
    """Main function"""
    print("🔧 DeFi Dashboard Wrapper")
    print("=" * 40)
    
    success = launch_dashboard()
    
    if success:
        print("\n🎉 Dashboard launched successfully!")
        print("The dashboard window should now be visible.")
    else:
        print("\n❌ Failed to launch dashboard")
        print("Please check the error messages above.")

if __name__ == "__main__":
    main()
