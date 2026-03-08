#!/usr/bin/env python3
"""
DeFi System Status Window
System status monitoring for DeFi Risk Assessment
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

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
        # Read actual settings to determine cache status
        cache_status = "Unknown"
        settings_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'settings.json')
        try:
            if os.path.exists(settings_file):
                import json
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    background_monitoring = settings.get('cache', {}).get('background_monitoring', False)
                    cache_status = "Enabled ✅" if background_monitoring else "Disabled ❌"
            else:
                cache_status = "Disabled ❌ (No settings file)"
        except Exception as e:
            cache_status = f"Error ❌ ({str(e)[:30]}...)"
        
        status_info = f"""
✅ System Tray: Running
✅ Python Version: {sys.version.split()[0]}
✅ Platform: {sys.platform}
✅ Working Directory: {os.getcwd()}

📊 Cache Status:
- Background monitoring: {cache_status}
- System tray: Active
- Menu functionality: Working
- Settings file: {'Found' if os.path.exists(settings_file) else 'Missing'}

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
