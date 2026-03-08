#!/usr/bin/env python3
"""
Dashboard Package Initialization
Makes the dashboard directory a proper Python package for imports
"""

# Import key modules to make them available at package level
try:
    from .tkinter_compatibility import tkinter_compat
except ImportError:
    tkinter_compat = None

try:
    from .process_manager import process_manager
except ImportError:
    process_manager = None

try:
    from .system_tray import DeFiSystemTray
except ImportError:
    DeFiSystemTray = None

__all__ = [
    'tkinter_compat',
    'process_manager', 
    'DeFiSystemTray'
]
