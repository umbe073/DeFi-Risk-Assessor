#!/usr/bin/env python3
"""
Utility to bring DeFi Risk Assessor windows to front on macOS
"""

import os
import sys
import subprocess

def bring_to_front():
    """Bring DeFi Risk Assessor windows to front"""
    try:
        # AppleScript to bring DeFi Risk Assessor windows to front
        script = '''
        tell application "System Events"
            set appList to every application process whose name contains "Python"
            repeat with appProcess in appList
                try
                    tell appProcess
                        set windowList to every window
                        repeat with windowItem in windowList
                            if name of windowItem contains "DeFi Risk Assessor" or name of windowItem contains "Credential" or name of windowItem contains "Dashboard" then
                                set frontmost of appProcess to true
                                perform action "AXRaise" of windowItem
                                return
                            end if
                        end repeat
                    end tell
                end try
            end repeat
        end tell
        '''
        
        # Execute the AppleScript
        result = subprocess.run(["osascript", "-e", script], 
                              capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print("✅ Successfully brought DeFi Risk Assessor windows to front")
        else:
            print(f"⚠️ Could not bring windows to front: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error bringing windows to front: {e}")

def focus_python_windows():
    """Focus any Python windows that might be DeFi Risk Assessor"""
    try:
        script = '''
        tell application "System Events"
            set pythonProcesses to every application process whose name contains "Python"
            repeat with proc in pythonProcesses
                try
                    tell proc
                        if exists (window 1) then
                            set frontmost to true
                            return
                        end if
                    end tell
                end try
            end repeat
        end tell
        '''
        
        subprocess.run(["osascript", "-e", script], check=False)
        print("✅ Focused Python windows")
        
    except Exception as e:
        print(f"❌ Error focusing Python windows: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "focus":
        focus_python_windows()
    else:
        bring_to_front()
