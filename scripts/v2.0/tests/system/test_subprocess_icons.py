#!/usr/bin/env python3
"""
Test script to verify if environment variables hide Python icons in subprocesses
"""

import subprocess
import os
import sys
import time

def test_subprocess_with_env_vars():
    """Test launching a subprocess with environment variables to hide Python icon"""
    
    # Set environment variables to hide Python icon
    env = os.environ.copy()
    env['LSUIElement'] = '1'
    env['NSApplicationActivationPolicy'] = 'accessory'
    
    print("🔧 Testing subprocess with environment variables...")
    print(f"LSUIElement: {env.get('LSUIElement', 'NOT SET')}")
    print(f"NSApplicationActivationPolicy: {env.get('NSApplicationActivationPolicy', 'NOT SET')}")
    
    # Create a simple test script that shows a window
    test_script = '''
import tkinter as tk
import time

root = tk.Tk()
root.title("Test Window - Should Not Show Python Icon")
root.geometry("300x200")
root.configure(bg='lightblue')

label = tk.Label(root, text="This window should NOT show a Python icon in the dock", 
                bg='lightblue', font=('Arial', 12), wraplength=250)
label.pack(pady=50)

print("✅ Test window created - check dock for Python icon")
print("⏰ Window will close in 10 seconds...")

root.after(10000, root.destroy)
root.mainloop()
'''
    
    # Write test script to file
    with open('temp_test_window.py', 'w') as f:
        f.write(test_script)
    
    try:
        # Launch subprocess with environment variables
        print("🚀 Launching test subprocess...")
        
        # Method 1: Direct subprocess with env
        process1 = subprocess.Popen([
            sys.executable, 'temp_test_window.py'
        ], env=env)
        
        print(f"✅ Process 1 started with PID: {process1.pid}")
        
        # Method 2: Shell wrapper with env vars
        shell_cmd = f'LSUIElement=1 NSApplicationActivationPolicy=accessory {sys.executable} temp_test_window.py'
        process2 = subprocess.Popen([
            '/bin/bash', '-c', shell_cmd
        ], env=env)
        
        print(f"✅ Process 2 started with PID: {process2.pid}")
        
        print("\n🔍 Please check your dock:")
        print("   - Do you see Python rocket icons for these test windows?")
        print("   - If not, the environment variables are working!")
        print("   - Windows will close automatically in 10 seconds...")
        
        # Wait for processes to finish
        process1.wait()
        process2.wait()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        # Clean up
        if os.path.exists('temp_test_window.py'):
            os.remove('temp_test_window.py')

if __name__ == "__main__":
    test_subprocess_with_env_vars()

