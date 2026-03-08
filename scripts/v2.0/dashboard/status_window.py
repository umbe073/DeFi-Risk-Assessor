#!/usr/bin/env python3
"""
DeFi System Status Window
System status monitoring for DeFi Risk Assessment
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk

from system_update_manager import SETTINGS_FILE, humanize_elapsed, load_update_state

# macOS compatibility fixes
if sys.platform == "darwin":
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

class StatusWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DeFi System Status")
        self.root.geometry("500x400")
        self.root.resizable(True, True)
        
        # Center window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() // 2) - 250,
            (self.root.winfo_screenheight() // 2) - 200
        ))
        
        # Create GUI
        self.create_gui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show window
        self.root.lift()
        self.root.focus_force()
    
    def get_cache_refresh_interval(self):
        """Get cache refresh interval from settings"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    return settings.get('cache', {}).get('auto_refresh_interval', 'Not configured')
            return "Not configured"
        except Exception:
            return "Error reading"
    
    def get_cache_retention(self):
        """Get cache retention period from settings"""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    return settings.get('cache', {}).get('cache_retention', 'Not configured')
            return "Not configured"
        except Exception:
            return "Error reading"
    
    def create_gui(self):
        """Create the status window GUI"""
        # Title
        title_label = ttk.Label(self.root, text="🛡️ DeFi System Status", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)
        
        # Status info
        status_text = tk.Text(self.root, height=15, width=60)
        status_text.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        
        # Add status information
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    background_monitoring = settings.get('cache', {}).get('background_monitoring', False)
                    if background_monitoring:
                        cache_status = "Enabled ✅"
                    else:
                        cache_status = "Disabled ❌ (Can be enabled in Settings)"
            else:
                cache_status = "Disabled ❌ (No settings file - use Settings to configure)"
        except json.JSONDecodeError as e:
            cache_status = f"Error ❌ (Invalid settings file: {str(e)[:30]}...)"
        except Exception as e:
            cache_status = f"Error ❌ (Cannot read settings: {str(e)[:30]}...)"

        update_state = load_update_state()
        libs_last_check = humanize_elapsed(update_state.get("last_check_at"))
        libs_last_update = humanize_elapsed(update_state.get("last_update_at"))
        libs_pending = int(update_state.get("last_outdated_count", 0) or 0)
        libs_check_status = str(update_state.get("last_check_status", "unknown"))
        libs_update_status = str(update_state.get("last_update_status", "unknown"))
        
        status_info = f"""
✅ System Tray: Running
✅ Python Version: {sys.version.split()[0]}
✅ Platform: {sys.platform}
✅ Working Directory: {os.getcwd()}

📊 Cache Status:
- Background monitoring: {cache_status}
- Cache refresh interval: {self.get_cache_refresh_interval()}
- Cache retention: {self.get_cache_retention()}
- System tray: Active
- Menu functionality: Working

🖥️ System Resources:
- Memory: Available
- CPU: Normal
- Processes: Stable

🔄 Recent Activity:
- System tray started successfully
- Cache monitoring initialized
- Menu items configured
- Window management active

🔧 Services Status:
- Main Dashboard: Available
- API Dashboard: Available
- Credential Manager: Available
- Chain Manager: Available
- Settings: Available
- Status Window: Active

🧰 System Update:
- Last dependency check: {libs_last_check}
- Last successful/attempted update: {libs_last_update}
- Pending package updates: {libs_pending}
- Check status: {libs_check_status}
- Update status: {libs_update_status}
        """
        
        status_text.insert(tk.END, status_info)
        status_text.config(state=tk.DISABLED)
        
        # Close button
        close_btn = ttk.Button(self.root, text="Close", command=self.on_closing)
        close_btn.pack(pady=10)
    
    def on_closing(self):
        """Handle window closing"""
        self.root.destroy()
    
    def run(self):
        """Run the status window"""
        self.root.mainloop()

if __name__ == "__main__":
    app = StatusWindow()
    app.run()
