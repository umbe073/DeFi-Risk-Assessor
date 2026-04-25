#!/usr/bin/env python3
"""
Test script to verify Python icon hiding
"""

import sys
import os

# CRITICAL: Set unified app icon environment variables BEFORE any other imports
if sys.platform == "darwin":
    # CRITICAL: Force Python to hide from dock (MUST BE FIRST)
    os.environ['LSUIElement'] = 'true'
    os.environ['NSApplicationActivationPolicy'] = 'accessory'
    
    # Unified app icon environment variables with CORRECT bundle identifier
    os.environ['BUNDLE_IDENTIFIER'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['APP_BUNDLE'] = 'true'
    os.environ['CFBundleIdentifier'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['CFBundleName'] = 'Token Risk Assessment Tool'
    os.environ['CFBundleDisplayName'] = 'Token Risk Assessment Tool'
    os.environ['PARENT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    os.environ['INHERIT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
    
    # Performance optimizations
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    
    # Basic tkinter compatibility
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

import tkinter as tk
from tkinter import messagebox

def main():
    root = tk.Tk()
    root.title("Python Icon Hiding Test")
    root.geometry("400x200")
    
    label = tk.Label(root, text="This window should appear with the unified crypto.icns icon\nand NOT show a Python rocket icon in the dock.", 
                     font=("Arial", 12), wraplength=350)
    label.pack(pady=50)
    
    def show_info():
        messagebox.showinfo("Test", "If you see this message, the window is working correctly!")
    
    button = tk.Button(root, text="Test Button", command=show_info)
    button.pack(pady=20)
    
    print("✅ Test window created with unified app icon environment variables")
    print("🔍 Check the dock - you should see only the crypto.icns icon, not Python rockets")
    
    root.mainloop()

if __name__ == "__main__":
    main()


