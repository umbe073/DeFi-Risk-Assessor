#!/usr/bin/env python3
"""
Minimal test for API dashboard to isolate hanging issue
"""

import os
import sys

# Set environment variables to avoid tkinter crashes
os.environ['TK_SILENCE_DEPRECATION'] = '1'
os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
os.environ['TK_FRAMEWORK'] = '1'
os.environ['DISPLAY'] = ':0'

print("Step 1: Environment variables set")

# Apply C extension patch BEFORE importing tkinter
if sys.platform == "darwin":
    macos_patch = None
    try:
        import macos_patch  # type: ignore
        macos_patch.patch_nsapplication()
        print("Step 2: macOS compatibility fix applied (C extension patch)")
        
        # Now initialize NSApplication
        import AppKit
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
        print("Step 2b: NSApplication initialized")
    except ImportError:
        print("Step 2: C extension not available, continuing with environment variables only")

print("Step 3: About to import tkinter")

try:
    import tkinter as tk
    from tkinter import ttk
    print("Step 4: Tkinter imported successfully")
    
    # Test basic tkinter functionality
    root = tk.Tk()
    print("Step 5: Root window created")
    
    root.title("Test")
    root.geometry("300x200")
    print("Step 6: Window configured")
    
    label = ttk.Label(root, text="API Dashboard Test")
    label.pack(pady=20)
    print("Step 7: Widget created")
    
    # Test environment loading
    print("Step 8: About to load environment")
    from dotenv import load_dotenv
    load_dotenv()
    print("Step 9: Environment loaded")
    
    print("Step 10: About to start mainloop")
    root.mainloop()
    print("Step 11: Mainloop finished")
    
except Exception as e:
    print(f"❌ Error at step: {e}")
    import traceback
    traceback.print_exc()
