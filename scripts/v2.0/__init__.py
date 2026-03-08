#!/usr/bin/env python3
"""
DeFi Risk Assessment v2.0 Package
Main package for the DeFi Risk Assessment Tool v2.0
"""

__version__ = "2.0.0"
__author__ = "DeFi Risk Assessment Team"

# Import key modules
try:
    from .dashboard import tkinter_compat, process_manager, DeFiSystemTray
except ImportError:
    tkinter_compat = None
    process_manager = None
    DeFiSystemTray = None

__all__ = [
    'tkinter_compat',
    'process_manager',
    'DeFiSystemTray'
]
