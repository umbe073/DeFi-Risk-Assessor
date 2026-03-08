#!/usr/bin/env python3
"""
DeFi System Settings Window
Interactive settings management for DeFi Risk Assessment
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox

# macOS compatibility fixes
if sys.platform == "darwin":
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

class SettingsWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DeFi System Settings")
        self.root.geometry("500x700")
        self.root.resizable(False, False)
        
        # Center window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() // 2) - 250,
            (self.root.winfo_screenheight() // 2) - 350
        ))
        
        # Load current settings
        self.settings_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'settings.json')
        self.current_settings = self.load_settings()
        
        # Create GUI
        self.create_gui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show window
        self.root.lift()
        self.root.focus_force()
        
    def load_settings(self):
        """Load current settings from file"""
        default_settings = {
            "cache": {
                "auto_refresh_interval": "10 minutes",
                "cache_retention": "24 hours",
                "background_monitoring": False
            },
            "security": {
                "vespia_integration": True,
                "credential_encryption": True,
                "auto_lock_timeout": "30 minutes"
            },
            "dashboard": {
                "default_dashboard": "Main Dashboard",
                "auto_start_services": False,
                "window_positioning": "Centered"
            },
            "api": {
                "rate_limiting": True,
                "fallback_data": True,
                "api_monitoring": True
            },
            "display": {
                "theme": "System default",
                "font_size": "Medium",
                "notifications": True
            }
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        return default_settings
    
    def save_settings(self):
        """Save settings to file"""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.current_settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def create_gui(self):
        """Create the GUI"""
        # Initialize settings variables dictionary first
        self.settings_vars = {}
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="⚙️ DeFi System Settings", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Create scrollable frame
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Settings sections
        self.create_cache_settings(scrollable_frame)
        self.create_security_settings(scrollable_frame)
        self.create_dashboard_settings(scrollable_frame)
        self.create_api_settings(scrollable_frame)
        self.create_display_settings(scrollable_frame)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Apply Changes button (initially disabled)
        self.apply_btn = ttk.Button(button_frame, text="Apply Changes", 
                                   command=self.apply_changes, state='disabled')
        self.apply_btn.pack(side=tk.LEFT, padx=10)
        
        # Close button
        close_btn = ttk.Button(button_frame, text="Close", command=self.on_closing)
        close_btn.pack(side=tk.RIGHT, padx=10)
    
    def create_cache_settings(self, parent):
        """Create cache settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔄 Cache Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Auto-refresh interval
        ttk.Label(section_frame, text="Auto-refresh interval:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["cache"]["auto_refresh_interval"])
        combo = ttk.Combobox(section_frame, textvariable=var, 
                            values=["5 minutes", "10 minutes", "15 minutes", "30 minutes"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_auto_refresh"] = var
        
        # Cache retention
        ttk.Label(section_frame, text="Cache retention:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["cache"]["cache_retention"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["12 hours", "24 hours", "48 hours", "72 hours"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_retention"] = var
        
        # Background monitoring
        var = tk.BooleanVar(value=self.current_settings["cache"]["background_monitoring"])
        check = ttk.Checkbutton(section_frame, text="Background monitoring", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["cache_monitoring"] = var
        
        # Bind change events
        for var in [self.settings_vars["cache_auto_refresh"], self.settings_vars["cache_retention"], self.settings_vars["cache_monitoring"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_security_settings(self, parent):
        """Create security settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔐 Security Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Vespia integration
        var = tk.BooleanVar(value=self.current_settings["security"]["vespia_integration"])
        check = ttk.Checkbutton(section_frame, text="Vespia integration", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["security_vespia"] = var
        
        # Credential encryption
        var = tk.BooleanVar(value=self.current_settings["security"]["credential_encryption"])
        check = ttk.Checkbutton(section_frame, text="Credential encryption", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["security_encryption"] = var
        
        # Auto-lock timeout
        ttk.Label(section_frame, text="Auto-lock timeout:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["security"]["auto_lock_timeout"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["15 minutes", "30 minutes", "1 hour", "2 hours"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["security_timeout"] = var
        
        # Bind change events
        for var in [self.settings_vars["security_vespia"], self.settings_vars["security_encryption"], self.settings_vars["security_timeout"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_dashboard_settings(self, parent):
        """Create dashboard settings section"""
        section_frame = ttk.LabelFrame(parent, text="📊 Dashboard Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Default dashboard
        ttk.Label(section_frame, text="Default dashboard:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["dashboard"]["default_dashboard"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Main Dashboard", "API Dashboard", "Credential Manager"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["dashboard_default"] = var
        
        # Auto-start services
        var = tk.BooleanVar(value=self.current_settings["dashboard"]["auto_start_services"])
        check = ttk.Checkbutton(section_frame, text="Auto-start services", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["dashboard_auto_start"] = var
        
        # Window positioning
        ttk.Label(section_frame, text="Window positioning:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["dashboard"]["window_positioning"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Centered", "Top-left", "Top-right", "Bottom-left", "Bottom-right"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["dashboard_positioning"] = var
        
        # Bind change events
        for var in [self.settings_vars["dashboard_default"], self.settings_vars["dashboard_auto_start"], self.settings_vars["dashboard_positioning"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_api_settings(self, parent):
        """Create API settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔗 API Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Rate limiting
        var = tk.BooleanVar(value=self.current_settings["api"]["rate_limiting"])
        check = ttk.Checkbutton(section_frame, text="Rate limiting", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_rate_limiting"] = var
        
        # Fallback data
        var = tk.BooleanVar(value=self.current_settings["api"]["fallback_data"])
        check = ttk.Checkbutton(section_frame, text="Fallback data", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_fallback"] = var
        
        # API monitoring
        var = tk.BooleanVar(value=self.current_settings["api"]["api_monitoring"])
        check = ttk.Checkbutton(section_frame, text="API monitoring", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_monitoring"] = var
        
        # Bind change events
        for var in [self.settings_vars["api_rate_limiting"], self.settings_vars["api_fallback"], self.settings_vars["api_monitoring"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_display_settings(self, parent):
        """Create display settings section"""
        section_frame = ttk.LabelFrame(parent, text="📈 Display Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Theme
        ttk.Label(section_frame, text="Theme:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["display"]["theme"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["System default", "Light", "Dark"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["display_theme"] = var
        
        # Font size
        ttk.Label(section_frame, text="Font size:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["display"]["font_size"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Small", "Medium", "Large"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["display_font_size"] = var
        
        # Notifications
        var = tk.BooleanVar(value=self.current_settings["display"]["notifications"])
        check = ttk.Checkbutton(section_frame, text="Notifications", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["display_notifications"] = var
        
        # Bind change events
        for var in [self.settings_vars["display_theme"], self.settings_vars["display_font_size"], self.settings_vars["display_notifications"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def on_setting_change(self, *args):
        """Called when any setting is changed"""
        self.apply_btn.config(state='normal')
    
    def apply_changes(self):
        """Apply the changes and save settings"""
        try:
            # Update current settings with new values
            self.current_settings["cache"]["auto_refresh_interval"] = self.settings_vars["cache_auto_refresh"].get()
            self.current_settings["cache"]["cache_retention"] = self.settings_vars["cache_retention"].get()
            self.current_settings["cache"]["background_monitoring"] = self.settings_vars["cache_monitoring"].get()
            
            self.current_settings["security"]["vespia_integration"] = self.settings_vars["security_vespia"].get()
            self.current_settings["security"]["credential_encryption"] = self.settings_vars["security_encryption"].get()
            self.current_settings["security"]["auto_lock_timeout"] = self.settings_vars["security_timeout"].get()
            
            self.current_settings["dashboard"]["default_dashboard"] = self.settings_vars["dashboard_default"].get()
            self.current_settings["dashboard"]["auto_start_services"] = self.settings_vars["dashboard_auto_start"].get()
            self.current_settings["dashboard"]["window_positioning"] = self.settings_vars["dashboard_positioning"].get()
            
            self.current_settings["api"]["rate_limiting"] = self.settings_vars["api_rate_limiting"].get()
            self.current_settings["api"]["fallback_data"] = self.settings_vars["api_fallback"].get()
            self.current_settings["api"]["api_monitoring"] = self.settings_vars["api_monitoring"].get()
            
            self.current_settings["display"]["theme"] = self.settings_vars["display_theme"].get()
            self.current_settings["display"]["font_size"] = self.settings_vars["display_font_size"].get()
            self.current_settings["display"]["notifications"] = self.settings_vars["display_notifications"].get()
            
            # Save settings
            if self.save_settings():
                messagebox.showinfo("Success", "Settings applied successfully!")
                self.apply_btn.config(state='disabled')
            else:
                messagebox.showerror("Error", "Failed to save settings!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error applying settings: {e}")
    
    def on_closing(self):
        """Handle window closing"""
        self.root.destroy()
    
    def run(self):
        """Run the settings window"""
        self.root.mainloop()

if __name__ == "__main__":
    app = SettingsWindow()
    app.run()
