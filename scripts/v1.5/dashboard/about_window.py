#!/usr/bin/env python3
"""
DeFi Risk Assessment About Window
Shows comprehensive about information with system details
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import platform
import webbrowser
from datetime import datetime

# macOS compatibility fixes
if sys.platform == "darwin":
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

class AboutWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("About DeFi Risk Assessment")
        self.root.geometry("700x600")
        self.root.resizable(False, False)
        
        # Center window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() // 2) - 350,
            (self.root.winfo_screenheight() // 2) - 300
        ))
        
        # Create GUI
        self.create_gui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show window
        self.root.lift()
        self.root.focus_force()
        
    def create_gui(self):
        """Create the GUI"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
        
        # App icon (magnifier icon)
        icon_label = ttk.Label(main_frame, text="🔍", font=('Arial', 48))
        icon_label.pack(pady=(0, 20))
        
        # App title
        title_label = ttk.Label(main_frame, text="DeFi Risk Assessment", 
                               font=('Arial', 24, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Version
        version_label = ttk.Label(main_frame, text="Version 1.5 - Professional Edition", 
                                 font=('Arial', 14))
        version_label.pack(pady=(0, 20))
        
        # Info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        # Python version
        python_info = ttk.Label(info_frame, text=f"Python Version: {platform.python_version()}", 
                               font=('Arial', 11))
        python_info.pack(pady=5)
        
        # Platform info
        platform_info = ttk.Label(info_frame, text=f"Platform: {platform.system()} {platform.release()}", 
                                 font=('Arial', 11))
        platform_info.pack(pady=5)
        
        # Attribution section
        attribution_frame = ttk.LabelFrame(info_frame, text="Data Sources", padding=15)
        attribution_frame.pack(fill=tk.X, pady=20)
        
        # CoinGecko attribution
        coingecko_frame = ttk.Frame(attribution_frame)
        coingecko_frame.pack(fill=tk.X, pady=5)
        
        coingecko_label = ttk.Label(coingecko_frame, text="• CoinGecko API: ", font=('Arial', 11, 'bold'))
        coingecko_label.pack(side=tk.LEFT)
        
        def open_coingecko():
            webbrowser.open("https://www.coingecko.com/en/api")
        
        coingecko_link = ttk.Label(coingecko_frame, text="https://www.coingecko.com/en/api", 
                                  font=('Arial', 11), foreground='blue', cursor='hand2')
        coingecko_link.pack(side=tk.LEFT)
        coingecko_link.bind("<Button-1>", lambda e: open_coingecko())
        coingecko_link.bind("<Enter>", lambda e: coingecko_link.config(foreground='red'))
        coingecko_link.bind("<Leave>", lambda e: coingecko_link.config(foreground='blue'))
        
        # Build info
        build_info = ttk.Label(info_frame, text=f"Build: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                              font=('Arial', 10), foreground='gray')
        build_info.pack(pady=10)
        
        # Close button
        close_btn = ttk.Button(main_frame, text="Close", command=self.on_closing)
        close_btn.pack(pady=20)
    
    def on_closing(self):
        """Handle window close"""
        self.root.destroy()

if __name__ == "__main__":
    app = AboutWindow()
    app.root.mainloop()
