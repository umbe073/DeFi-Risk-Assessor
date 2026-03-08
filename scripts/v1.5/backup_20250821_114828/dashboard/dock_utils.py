#!/usr/bin/env python3
"""
Dock utilities for DeFi System Tray
Provides dock hiding functionality for all dashboard and management scripts
"""

import os
import sys

def hide_from_dock():
    """Hide the current process from the dock when running through app bundle"""
    if sys.platform == "darwin":
        try:
            import AppKit
            
            # Check if running through app bundle
            is_running_from_app = any('Token Risk Assessment Tool.app' in arg for arg in sys.argv)
            is_bundle_env = 'APP_BUNDLE' in os.environ or 'BUNDLE_IDENTIFIER' in os.environ
            
            if is_running_from_app or is_bundle_env:
                # Hide the Python process from dock when running through app
                AppKit.NSApplication.sharedApplication()
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
                print("Running in background mode (hidden from dock)")
                return True
            else:
                # Running standalone, keep normal behavior
                print("Running in standalone mode")
                return False
                
        except ImportError:
            # AppKit not available, continue normally
            print("AppKit not available, running in normal mode")
            return False
        except Exception as e:
            print(f"Error setting dock policy: {e}")
            return False
    else:
        # Not on macOS, no dock hiding needed
        return False

def ensure_app_bundle_environment():
    """Ensure app bundle environment variables are set"""
    if 'APP_BUNDLE' not in os.environ:
        os.environ['APP_BUNDLE'] = 'true'
    if 'BUNDLE_IDENTIFIER' not in os.environ:
        os.environ['BUNDLE_IDENTIFIER'] = 'com.defi.riskassessment'

def setup_app_bundle_mode():
    """Complete setup for app bundle mode"""
    ensure_app_bundle_environment()
    return hide_from_dock()

if __name__ == "__main__":
    # Test the functionality
    print("Testing dock utilities...")
    result = setup_app_bundle_mode()
    print(f"Setup result: {result}")
