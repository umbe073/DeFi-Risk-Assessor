#!/usr/bin/env python3
"""
Wrapper script to launch the chain manager with proper environment setup
"""

import os
import sys
import subprocess

def main():
    """Launch chain manager with proper environment"""
    
    # Set up environment variables for macOS compatibility
    env = os.environ.copy()
    env['PYTHONPATH'] = '/Users/amlfreak/Desktop/venv'
    
    # Unified app icon environment variables
    env['BUNDLE_IDENTIFIER'] = 'com.defi.riskassessment'
    env['APP_BUNDLE'] = 'true'
    env['CFBundleIdentifier'] = 'com.defi.riskassessment'
    env['CFBundleName'] = 'Token Risk Assessment Tool'
    env['CFBundleDisplayName'] = 'Token Risk Assessment Tool'
    env['PARENT_BUNDLE_ID'] = 'com.defi.riskassessment'
    env['INHERIT_BUNDLE_ID'] = 'com.defi.riskassessment'
    
    # Set activation policy for background operation
    env['NSApplicationActivationPolicy'] = 'accessory'
    env['LSUIElement'] = 'true'
    
    # macOS specific environment variables
    if sys.platform == "darwin":
        env['TK_SILENCE_DEPRECATION'] = '1'
        env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
        env['TK_FRAMEWORK'] = '1'
        env['TCL_LIBRARY'] = '/System/Library/Frameworks/Tcl.framework/Versions/8.6/Resources/Scripts'
        env['TK_LIBRARY'] = '/System/Library/Frameworks/Tk.framework/Versions/8.6/Resources/Scripts'
        env['DISPLAY'] = ':0'
        
        # Additional macOS environment variables
        env['NSDocumentRevisionsKeepEveryOne'] = '1'
        env['NSAppTransportSecurity'] = 'true'
        
        # Force basic mode and skip all macOS checks
        env['TK_FORCE_BASIC_MODE'] = '1'
        env['TK_SKIP_ALL_MACOS_CHECKS'] = '1'
        env['TK_DISABLE_ALL_MACOS_FEATURES'] = '1'
        env['TK_DISABLE_MACOS_VERSION_CALLS'] = '1'
        env['TK_SKIP_MACOS_VERSION_CHECK'] = '1'
        env['TK_DISABLE_MACOS_VERSION_METHOD'] = '1'
        env['TK_USE_LEGACY_MODE'] = '1'
        env['TK_DISABLE_NATIVE_FEATURES'] = '1'
        env['TK_FORCE_COMPATIBILITY_MODE'] = '1'
    
    # Path to the chain manager script
    script_path = os.path.join(os.path.dirname(__file__), 'gui_chains.py')
    
    # Use Python 3.9 for tkinter compatibility (best for Apple Silicon Macs)
    python39 = '/opt/homebrew/bin/python3.9'
    if os.path.exists(python39):
        python_executable = python39
    else:
        # Fallback to Python 3.11
        python311 = '/opt/homebrew/bin/python3.11'
        if os.path.exists(python311):
            python_executable = python311
        else:
            python_executable = sys.executable
    
    try:
        # Launch the chain manager
        subprocess.run([python_executable, script_path], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error launching chain manager: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Python 3.12 not found. Please install it with: brew install python@3.12")
        sys.exit(1)

if __name__ == "__main__":
    main()
