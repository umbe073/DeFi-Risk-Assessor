#!/usr/bin/env python3
"""
Minimal DeFi Dashboard
Basic working version without problematic features
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

class MinimalDeFiDashboard:
    def __init__(self):
        # Set environment variables for macOS compatibility
        if sys.platform == "darwin":
            os.environ['TK_SILENCE_DEPRECATION'] = '1'
        
        self.root = tk.Tk()
        self.root.title("DeFi Risk Assessment Dashboard")
        self.root.geometry("800x600")
        
        self.create_widgets()
        
    def create_widgets(self):
        """Create basic widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🛡️ DeFi Risk Assessment Tool", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))
        
        subtitle_label = ttk.Label(main_frame, text="Professional cryptocurrency risk analysis platform")
        subtitle_label.pack(pady=(0, 30))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=20)
        
        # Action buttons
        assess_btn = ttk.Button(buttons_frame, text="🔍 Start Risk Assessment", 
                               command=self.start_assessment)
        assess_btn.pack(fill=tk.X, pady=5)
        
        api_btn = ttk.Button(buttons_frame, text="🔧 API Service Monitor", 
                            command=self.open_api_dashboard)
        api_btn.pack(fill=tk.X, pady=5)
        
        creds_btn = ttk.Button(buttons_frame, text="🔐 Manage Credentials", 
                              command=self.manage_credentials)
        creds_btn.pack(fill=tk.X, pady=5)
        
        chains_btn = ttk.Button(buttons_frame, text="🔗 Manage Chains", 
                               command=self.manage_chains)
        chains_btn.pack(fill=tk.X, pady=5)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.pack(pady=20)
        
    def start_assessment(self):
        """Start risk assessment"""
        self.status_label.config(text="Starting risk assessment...")
        
        def run_assessment():
            try:
                script_path = os.path.join(PROJECT_ROOT, 'scripts/v1.5/defi_complete_risk_assessment_clean.py')
                subprocess.run([sys.executable, script_path], check=True)
                self.root.after(0, lambda: self.status_label.config(text="Assessment completed!"))
            except Exception as e:
                self.root.after(0, lambda: self.status_label.config(text=f"Error: {str(e)}"))
        
        threading.Thread(target=run_assessment, daemon=True).start()
    
    def open_api_dashboard(self):
        """Open API dashboard"""
        try:
            script_path = os.path.join(PROJECT_ROOT, 'scripts/v1.5/dashboard/api_service_dashboard.py')
            subprocess.Popen([sys.executable, script_path])
            self.status_label.config(text="API Dashboard opened")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open API Dashboard: {str(e)}")
    
    def manage_credentials(self):
        """Open credential manager"""
        try:
            script_path = os.path.join(PROJECT_ROOT, 'scripts/v1.5/credential_management/gui_credentials.py')
            subprocess.Popen([sys.executable, script_path])
            self.status_label.config(text="Credential Manager opened")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Credential Manager: {str(e)}")
    
    def manage_chains(self):
        """Open chain manager"""
        try:
            script_path = os.path.join(PROJECT_ROOT, 'scripts/v1.5/credential_management/gui_chains.py')
            subprocess.Popen([sys.executable, script_path])
            self.status_label.config(text="Chain Manager opened")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Chain Manager: {str(e)}")
    
    def run(self):
        """Run the dashboard"""
        self.root.mainloop()

def main():
    """Main function"""
    try:
        app = MinimalDeFiDashboard()
        app.run()
    except Exception as e:
        print(f"Error starting dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
