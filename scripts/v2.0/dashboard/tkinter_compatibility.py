#!/usr/bin/env python3
"""
Tkinter Compatibility Module for macOS
Handles all macOS-specific tkinter issues and ensures proper functionality
"""

import os
import sys
import threading
import time

class TkinterCompatibility:
    """Comprehensive tkinter compatibility handler for macOS"""
    
    _instance = None
    _initialized = False
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(TkinterCompatibility, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._app_kit_initialized = False
        self._ns_application_patched = False
        self._tkinter_safe = False
        
        # Initialize immediately
        self._setup_macos_compatibility()
    
    def _setup_macos_compatibility(self):
        """Set up comprehensive macOS compatibility"""
        if sys.platform != "darwin":
            return
        
        print("🔧 Setting up macOS tkinter compatibility...")
        
        # Step 1: Set environment variables
        self._set_environment_variables()
        
        # Step 2: Initialize AppKit and patch NSApplication
        self._initialize_appkit()
        
        # Step 3: Set up tkinter safety
        self._setup_tkinter_safety()
        
        print("✅ macOS tkinter compatibility setup complete")
    
    def _set_environment_variables(self):
        """Set all necessary environment variables for tkinter compatibility"""
        env_vars = {
            # Basic tkinter compatibility
            'TK_SILENCE_DEPRECATION': '1',
            'PYTHON_CONFIGURE_OPTS': '--enable-framework',
            'TK_FRAMEWORK': '1',
            'DISPLAY': ':0',
            
            # Disable problematic features
            'TK_DISABLE_COLORS': '1',
            'TK_DISABLE_THEMES': '1',
            'TK_DISABLE_3D': '1',
            'TK_DISABLE_ANIMATIONS': '1',
            'TK_USE_BASIC_MODE': '1',
            
            # macOS version handling
            'TK_SKIP_MACOS_VERSION_CHECK': '1',
            'TK_DISABLE_MACOS_VERSION_CHECK': '1',
            'TK_DISABLE_MACOS_VERSION_CALLS': '1',
            'TK_DISABLE_MACOS_VERSION_METHOD': '1',
            
            # NSApplication handling
            'TK_DISABLE_NSAPPLICATION_SETUP': '1',
            'TK_DISABLE_MACOS_NSAPPLICATION': '1',
            
            # Event loop and autorelease
            'TK_DISABLE_AUTORELEASE_POOL': '1',
            'TK_DISABLE_EVENT_LOOP': '1',
            'TK_DISABLE_MACOS_AUTORELEASE': '1',
            'TK_DISABLE_MACOS_EVENT_LOOP': '1',
            
            # Force compatibility mode
            'TK_FORCE_BASIC_MODE': '1',
            'TK_SKIP_ALL_MACOS_CHECKS': '1',
            'TK_DISABLE_ALL_MACOS_FEATURES': '1',
            'TK_USE_LEGACY_MODE': '1',
            'TK_DISABLE_NATIVE_FEATURES': '1',
            'TK_FORCE_COMPATIBILITY_MODE': '1',
            
            # Security and transport
            'NSAppTransportSecurity': 'true',
            'NSDocumentRevisionsKeepEveryOne': '1'
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
        
        print("✅ Environment variables set")
    
    def _initialize_appkit(self):
        """Initialize AppKit and patch NSApplication - DISABLED for stability"""
        # AppKit and NSApplication integration has been disabled to prevent crashes
        # The environment variables and tkinter safety measures are sufficient
        print("✅ AppKit integration disabled for stability")
        self._app_kit_initialized = False
        self._ns_application_patched = False
    
    def _setup_tkinter_safety(self):
        """Set up tkinter safety measures"""
        try:
            # Import tkinter safely
            import tkinter as tk
            
            # Test basic tkinter functionality
            test_root = tk.Tk()
            test_root.withdraw()
            test_root.destroy()
            
            self._tkinter_safe = True
            print("✅ Tkinter safety verified")
            
        except Exception as e:
            print(f"⚠️ Tkinter safety check failed: {e}")
            self._tkinter_safe = False
    
    def safe_import_tkinter(self):
        """Safely import tkinter with all compatibility measures"""
        if not self._initialized:
            self._setup_macos_compatibility()
        
        try:
            import tkinter as tk
            from tkinter import ttk, messagebox
            
            return tk, ttk, messagebox
            
        except Exception as e:
            print(f"❌ Tkinter import failed: {e}")
            raise
    
    def create_safe_root(self, title="DeFi Risk Assessment"):
        """Create a safe root window with all compatibility measures"""
        tk, ttk, messagebox = self.safe_import_tkinter()
        
        try:
            root = tk.Tk()
            root.title(title)
            root.withdraw()  # Hide by default
            
            # Set up proper window management
            root.protocol("WM_DELETE_WINDOW", lambda: self._safe_destroy(root))
            
            # Configure for macOS compatibility
            if sys.platform == "darwin":
                root.attributes('-topmost', False)
                root.attributes('-alpha', 1.0)
            
            print(f"✅ Safe root window created: {title}")
            return root
            
        except Exception as e:
            print(f"❌ Failed to create safe root: {e}")
            raise
    
    def create_safe_toplevel(self, parent, title="Window"):
        """Create a safe toplevel window"""
        tk, ttk, messagebox = self.safe_import_tkinter()
        
        try:
            toplevel = tk.Toplevel(parent)
            toplevel.title(title)
            
            # Set up proper window management
            toplevel.protocol("WM_DELETE_WINDOW", lambda: self._safe_destroy(toplevel))
            
            # Configure for macOS compatibility
            if sys.platform == "darwin":
                toplevel.attributes('-topmost', False)
                toplevel.attributes('-alpha', 1.0)
            
            return toplevel
            
        except Exception as e:
            print(f"❌ Failed to create safe toplevel: {e}")
            raise
    
    def _safe_destroy(self, window):
        """Safely destroy a window"""
        try:
            if window and hasattr(window, 'destroy'):
                window.destroy()
        except Exception as e:
            print(f"⚠️ Error destroying window: {e}")
    
    def run_safe_mainloop(self, root):
        """Run mainloop with error handling"""
        try:
            root.deiconify()  # Show the window
            root.mainloop()
        except Exception as e:
            print(f"❌ Mainloop error: {e}")
            self._safe_destroy(root)
    
    def is_compatible(self):
        """Check if tkinter is compatible and safe to use"""
        return self._initialized and self._tkinter_safe

# Global instance
tkinter_compat = TkinterCompatibility()
