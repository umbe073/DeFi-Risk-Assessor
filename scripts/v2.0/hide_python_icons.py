#!/usr/bin/env python3
"""
Script to hide Python icons from the dock using macOS-specific techniques
"""

import subprocess
import os
import sys
import time
import signal
import threading

def hide_python_from_dock():
    """Hide Python process from dock using macOS techniques"""
    
    # Method 1: Use osascript to hide the current process
    try:
        script = '''
tell application "System Events"
    set visible of process "Python" to false
end tell
'''
        subprocess.run(['osascript', '-e', script], capture_output=True)
        print("✅ Attempted to hide Python from dock using AppleScript")
    except Exception as e:
        print(f"⚠️ AppleScript method failed: {e}")

def launch_hidden_process(command, args=None):
    """Launch a process that won't show in the dock"""
    
    if args is None:
        args = []
    
    # Create environment with dock hiding variables
    env = os.environ.copy()
    env['LSUIElement'] = '1'
    env['NSApplicationActivationPolicy'] = 'accessory'
    env['NSWindowCollectionBehavior'] = 'NSWindowCollectionBehaviorParticipatesInCycle'
    
    # Use a wrapper script that sets the process type
    wrapper_script = f'''#!/bin/bash
# Hide this process from dock
export LSUIElement=1
export NSApplicationActivationPolicy=accessory
export NSWindowCollectionBehavior=NSWindowCollectionBehaviorParticipatesInCycle

# Launch the actual command
exec {command} {" ".join(args)}
'''
    
    # Write wrapper to temporary file
    wrapper_path = '/tmp/hidden_python_wrapper.sh'
    with open(wrapper_path, 'w') as f:
        f.write(wrapper_script)
    
    os.chmod(wrapper_path, 0o755)
    
    try:
        # Launch using the wrapper
        process = subprocess.Popen([
            '/bin/bash', wrapper_path
        ], env=env)
        
        print(f"✅ Launched hidden process with PID: {process.pid}")
        return process
        
    except Exception as e:
        print(f"❌ Error launching hidden process: {e}")
        return None
    finally:
        # Clean up wrapper
        if os.path.exists(wrapper_path):
            os.remove(wrapper_path)

def test_hidden_launch():
    """Test launching a hidden Python process"""
    
    print("🧪 Testing hidden Python process launch...")
    
    # Create a simple test script
    test_script = '''
import tkinter as tk
import time

root = tk.Tk()
root.title("Hidden Python Window")
root.geometry("400x300")
root.configure(bg='lightgreen')

label = tk.Label(root, text="This Python process should NOT show in the dock!", 
                bg='lightgreen', font=('Arial', 14), wraplength=350)
label.pack(pady=80)

print("✅ Hidden test window created")
print("⏰ Window will close in 15 seconds...")

root.after(15000, root.destroy)
root.mainloop()
'''
    
    # Write test script
    test_path = '/tmp/hidden_test.py'
    with open(test_path, 'w') as f:
        f.write(test_script)
    
    try:
        # Launch hidden process
        process = launch_hidden_process(sys.executable, [test_path])
        
        if process:
            print("\n🔍 Please check your dock:")
            print("   - Do you see a Python rocket icon for this window?")
            print("   - If not, the hiding method is working!")
            print("   - Window will close automatically in 15 seconds...")
            
            # Wait for process to finish
            process.wait()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        # Clean up
        if os.path.exists(test_path):
            os.remove(test_path)

if __name__ == "__main__":
    test_hidden_launch()

