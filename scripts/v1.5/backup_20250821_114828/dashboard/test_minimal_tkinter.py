#!/usr/bin/env python3
"""
Minimal tkinter test to check if basic functionality works
"""

import os
import sys

# Set environment variables to avoid tkinter crashes
os.environ['TK_SILENCE_DEPRECATION'] = '1'
os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
os.environ['TK_FRAMEWORK'] = '1'
os.environ['DISPLAY'] = ':0'

# Disable problematic features
os.environ['TK_DISABLE_COLORS'] = '1'
os.environ['TK_DISABLE_THEMES'] = '1'
os.environ['TK_DISABLE_3D'] = '1'
os.environ['TK_DISABLE_ANIMATIONS'] = '1'
os.environ['TK_USE_BASIC_MODE'] = '1'

try:
    import tkinter as tk
    from tkinter import ttk
    
    print("✅ Tkinter imported successfully")
    
    # Create a minimal window
    root = tk.Tk()
    root.title("Minimal Test")
    root.geometry("300x200")
    
    # Add a simple label
    label = ttk.Label(root, text="Hello, World!")
    label.pack(pady=20)
    
    # Add a button
    button = ttk.Button(root, text="Click Me", command=lambda: print("Button clicked!"))
    button.pack(pady=10)
    
    print("✅ Window created successfully")
    
    # Start the main loop
    root.mainloop()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
