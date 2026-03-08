#!/usr/bin/env python3
"""
Simplified Credential Manager GUI
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox

# Set environment variables to avoid tkinter crashes
os.environ['TK_SILENCE_DEPRECATION'] = '1'
os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
os.environ['TK_FRAMEWORK'] = '1'
os.environ['DISPLAY'] = ':0'

# Disable problematic features
os.environ['TK_DISABLE_COLORS'] = '1'
os.environ['TK_DISABLE_THEMES'] = '1'
os.environ['TK_DISABLE_3D'] = '1'
os.environ['TK_DISABLE_ANIMATIONS'] = '1'
os.environ['TK_USE_BASIC_MODE'] = '1'

class SimpleCredentialManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Credential Manager")
        self.root.geometry("600x400")
        
        # Set up the UI
        self.setup_ui()
        
        # Load existing credentials
        self.load_credentials()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="API Credentials Manager", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Credentials frame
        cred_frame = ttk.LabelFrame(main_frame, text="API Keys", padding="10")
        cred_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollable frame for credentials
        canvas = tk.Canvas(cred_frame)
        scrollbar = ttk.Scrollbar(cred_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add some sample API keys
        self.add_credential_field("CoinGecko API Key", "coingecko")
        self.add_credential_field("CoinMarketCap API Key", "coinmarketcap")
        self.add_credential_field("Etherscan API Key", "etherscan")
        self.add_credential_field("Moralis API Key", "moralis")
        self.add_credential_field("BitQuery API Key", "bitquery")
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Save", command=self.save_credentials).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.root.destroy).pack(side=tk.LEFT)
        
    def add_credential_field(self, label_text, key_name):
        frame = ttk.Frame(self.scrollable_frame)
        frame.pack(fill=tk.X, pady=5)
        
        label = ttk.Label(frame, text=label_text, width=20)
        label.pack(side=tk.LEFT)
        
        entry = ttk.Entry(frame, width=50, show="*")
        entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # Store reference to entry
        setattr(self, f"{key_name}_entry", entry)
        
    def load_credentials(self):
        # Load from a simple JSON file
        try:
            with open("credentials.json", "r") as f:
                creds = json.load(f)
                
            for key, value in creds.items():
                entry = getattr(self, f"{key}_entry", None)
                if entry:
                    entry.insert(0, value)
        except FileNotFoundError:
            pass
            
    def save_credentials(self):
        creds = {}
        for attr in dir(self):
            if attr.endswith("_entry"):
                key = attr.replace("_entry", "")
                entry = getattr(self, attr)
                value = entry.get().strip()
                if value:
                    creds[key] = value
        
        try:
            with open("credentials.json", "w") as f:
                json.dump(creds, f, indent=2)
            messagebox.showinfo("Success", "Credentials saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save credentials: {e}")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SimpleCredentialManager()
    app.run()
