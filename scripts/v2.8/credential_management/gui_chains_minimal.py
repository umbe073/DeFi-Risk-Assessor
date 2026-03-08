#!/usr/bin/env python3
"""
Minimal Chain Management GUI Test
"""

import os
import sys

# Set environment variables immediately to prevent tkinter crashes
if sys.platform == "darwin":
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

print("Environment variables set")

import tkinter as tk
from tkinter import ttk, messagebox

print("Tkinter imported successfully")

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'

class ChainManager:
    def __init__(self):
        self.env_file = os.path.join(PROJECT_ROOT, '.env')
        print("ChainManager initialized")

def main():
    print("Main function called")
    manager = ChainManager()
    print("Test completed successfully")

if __name__ == "__main__":
    main()

