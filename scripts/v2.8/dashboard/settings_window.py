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
        self.root.geometry("350x700")
        self.root.resizable(False, False)
        
        # Center window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() // 2) - 175,
            (self.root.winfo_screenheight() // 2) - 350
        ))
        
        # Load current settings
        self.settings_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'settings.json')
        self.current_settings = self.load_settings()
        
        # Initialize settings variables dictionary
        self.settings_vars = {}
        
        # Store initial values for change detection
        self.initial_values = {}
        
        # Flag to prevent change detection during initialization
        self.initializing = True
        
        # Create GUI
        self.create_gui()
        
        # Store initial values after GUI creation
        self._store_initial_values()
        
        # Allow change detection now
        self.initializing = False
        
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
                "background_monitoring": False,
                "respect_48h_metric_skip": True,
                "metric_skip_hours": 48
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
        
        # Button frame - positioned directly under content
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=(20, 10))
        
        # Apply Changes button (initially disabled and faded)
        self.apply_btn = ttk.Button(button_frame, text="Apply Changes", 
                                   command=self.apply_changes, state='disabled')
        self.apply_btn.pack(side=tk.LEFT, padx=10)
        
        # Configure faded appearance for disabled state
        try:
            style = ttk.Style()
            style.configure('Disabled.TButton', foreground='gray')
            self.apply_btn.configure(style='Disabled.TButton')
        except:
            # Fallback if styling fails
            pass
        
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
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_auto_refresh"] = var
        
        # Cache retention
        ttk.Label(section_frame, text="Cache retention:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["cache"]["cache_retention"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["12 hours", "24 hours", "48 hours", "72 hours"],
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_retention"] = var
        
        # Background monitoring
        var = tk.BooleanVar(value=self.current_settings["cache"]["background_monitoring"])
        check = ttk.Checkbutton(section_frame, text="Background monitoring", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["cache_monitoring"] = var

        # Skip re-fetch within N hours (48h policy)
        var_skip = tk.BooleanVar(value=self.current_settings["cache"].get("respect_48h_metric_skip", True))
        check_skip = ttk.Checkbutton(section_frame, text="Skip re-fetch if data is recent (48h)", variable=var_skip)
        check_skip.pack(anchor=tk.W, pady=(10, 2))
        self.settings_vars["cache_respect_48h_skip"] = var_skip

        # Metric skip hours (default 48)
        ttk.Label(section_frame, text="Skip window (hours):").pack(anchor=tk.W)
        var_hours = tk.StringVar(value=str(self.current_settings["cache"].get("metric_skip_hours", 48)))
        entry_hours = ttk.Entry(section_frame, textvariable=var_hours, width=8)
        entry_hours.pack(anchor=tk.W, pady=(0, 10))
        self.settings_vars["cache_skip_hours"] = var_hours
        
        # Bind change events
        for var in [self.settings_vars["cache_auto_refresh"], self.settings_vars["cache_retention"], self.settings_vars["cache_monitoring"], self.settings_vars["cache_respect_48h_skip"], self.settings_vars["cache_skip_hours"]]:
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
                            state="readonly", width=20)
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
                            state="readonly", width=20)
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
                           state="readonly", width=20)
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
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["display_theme"] = var
        
        # Font size
        ttk.Label(section_frame, text="Font size:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["display"]["font_size"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Small", "Medium", "Large"],
                            state="readonly", width=20)
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
    
    def _store_initial_values(self):
        """Store initial values for change detection"""
        for key, var in self.settings_vars.items():
            if hasattr(var, 'get'):
                self.initial_values[key] = var.get()
    
    def _has_changes(self):
        """Check if any settings have changed from initial values"""
        for key, var in self.settings_vars.items():
            if hasattr(var, 'get'):
                current_value = var.get()
                initial_value = self.initial_values.get(key)
                if current_value != initial_value:
                    return True
        return False
    
    def on_setting_change(self, *args):
        """Called when any setting is changed"""
        # Don't process changes during initialization
        if hasattr(self, 'initializing') and self.initializing:
            return
            
        if self._has_changes():
            self.apply_btn.config(state='normal')
            # Remove faded style when enabled
            try:
                self.apply_btn.configure(style='TButton')
            except:
                pass
        else:
            self.apply_btn.config(state='disabled')
            # Apply faded style when disabled
            try:
                self.apply_btn.configure(style='Disabled.TButton')
            except:
                pass
    
    def apply_changes(self):
        """Apply the changes and save settings"""
        try:
            # Update current settings with new values
            self.current_settings["cache"]["auto_refresh_interval"] = self.settings_vars["cache_auto_refresh"].get()
            self.current_settings["cache"]["cache_retention"] = self.settings_vars["cache_retention"].get()
            self.current_settings["cache"]["background_monitoring"] = self.settings_vars["cache_monitoring"].get()
            # 48h skip policy
            self.current_settings["cache"]["respect_48h_metric_skip"] = bool(self.settings_vars["cache_respect_48h_skip"].get())
            # sanitize hours
            try:
                hours_val = int(str(self.settings_vars["cache_skip_hours"].get()).strip())
                if hours_val <= 0:
                    hours_val = 48
            except Exception:
                hours_val = 48
            self.current_settings["cache"]["metric_skip_hours"] = hours_val
            
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
            
            # Apply theme changes immediately
            self.apply_theme_changes()
            
            # Save settings
            if self.save_settings():
                messagebox.showinfo("Success", "Settings applied successfully!")
                # Update initial values to current values
                self._store_initial_values()
                self.apply_btn.config(state='disabled')
                # Re-apply faded style after disabling
                try:
                    self.apply_btn.configure(style='Disabled.TButton')
                except:
                    pass
            else:
                messagebox.showerror("Error", "Failed to save settings!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error applying settings: {e}")
    
    def apply_theme_changes(self):
        """Apply theme changes to the current window"""
        try:
            selected_theme = self.settings_vars["display_theme"].get()
            
            # Define theme colors
            if selected_theme == "Light":
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                frame_bg = '#ffffff'
                label_bg = '#ffffff'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
                button_bg = '#3498db'
                button_fg = '#ffffff'
            elif selected_theme == "Dark":
                bg_color = '#2c3e50'
                fg_color = '#ecf0f1'
                frame_bg = '#2c3e50'
                label_bg = '#34495e'
                entry_bg = '#34495e'
                entry_fg = '#ecf0f1'
                button_bg = '#3498db'
                button_fg = '#ffffff'
            else:
                # System default - use current system colors
                return
            
            # Apply theme to current window
            self.root.configure(bg=bg_color)
            
            # Update all widgets in the settings window
            self.update_widget_colors(self.root, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg)
            
            # Force update
            self.root.update_idletasks()
            self.root.update()
            
        except Exception as e:
            print(f"Error applying theme changes: {e}")
    
    def update_widget_colors(self, widget, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg):
        """Update widget colors recursively"""
        try:
            # Update current widget
            if isinstance(widget, tk.Label):
                widget.configure(bg=label_bg, fg=fg_color)
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=frame_bg)
            elif isinstance(widget, tk.Button):
                widget.configure(bg=button_bg, fg=button_fg)
            
            # Update all children
            for child in widget.winfo_children():
                self.update_widget_colors(child, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg)
                
        except Exception as e:
            # Silently ignore errors for ttk widgets
            pass
    
    def on_closing(self):
        """Handle window closing"""
        self.root.destroy()
    
    def run(self):
        """Run the settings window"""
        self.root.mainloop()

if __name__ == "__main__":
    app = SettingsWindow()
    app.run()
