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
        
        # App icon (crypto icon)
        try:
            # Try to load and display the crypto icon
            from PIL import Image, ImageTk
            crypto_icon_path = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'Logos', 'crypto.icns')
            if os.path.exists(crypto_icon_path):
                crypto_image = Image.open(crypto_icon_path)
                # Resize to reasonable size for the about window
                crypto_image = crypto_image.resize((64, 64), Image.Resampling.LANCZOS)
                self.crypto_photo = ImageTk.PhotoImage(crypto_image)
                self.icon_label = ttk.Label(main_frame, image=self.crypto_photo)
                self.icon_label.pack(pady=(0, 20))
            else:
                # Fallback to text icon
                self.icon_label = ttk.Label(main_frame, text="🔍", font=('Arial', 48))
                self.icon_label.pack(pady=(0, 20))
        except Exception:
            # Fallback to text icon if image loading fails
            self.icon_label = ttk.Label(main_frame, text="🔍", font=('Arial', 48))
            self.icon_label.pack(pady=(0, 20))
        
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
        
        # Attribution section (expanded)
        attribution_frame = ttk.LabelFrame(info_frame, text="Data Sources", padding=15)
        attribution_frame.pack(fill=tk.X, pady=20)
        
        def build_attr_row(parent, label_text, url):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=3)
            lab = ttk.Label(row, text=f"• {label_text}: ", font=('Arial', 11, 'bold'))
            lab.pack(side=tk.LEFT)
            link = ttk.Label(row, text=url, font=('Arial', 11), foreground='blue', cursor='hand2')
            link.pack(side=tk.LEFT)
            link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            link.bind("<Enter>", lambda e: link.config(foreground='red'))
            link.bind("<Leave>", lambda e: link.config(foreground='blue'))

        # Build comprehensive attributions (multi-column layout if needed)
        build_attr_row(attribution_frame, "CoinGecko API", "https://www.coingecko.com/en/api")
        build_attr_row(attribution_frame, "CoinMarketCap API", "https://coinmarketcap.com/api/")
        build_attr_row(attribution_frame, "Etherscan API", "https://etherscan.io/apis")
        build_attr_row(attribution_frame, "Ethplorer API", "https://ethplorer.io/")
        build_attr_row(attribution_frame, "Moralis API", "https://moralis.io/")
        build_attr_row(attribution_frame, "1inch API", "https://docs.1inch.io/")
        build_attr_row(attribution_frame, "DeFiLlama API", "https://defillama.com/docs/api")
        build_attr_row(attribution_frame, "The Graph", "https://thegraph.com/")
        build_attr_row(attribution_frame, "Santiment API", "https://api.santiment.net/")
        build_attr_row(attribution_frame, "Twitter API", "https://developer.twitter.com/en/docs/twitter-api")
        build_attr_row(attribution_frame, "Telegram Bot API", "https://core.telegram.org/bots/api")
        build_attr_row(attribution_frame, "Discord API", "https://discord.com/developers/docs/intro")
        build_attr_row(attribution_frame, "CoinDesk RSS", "https://www.coindesk.com/arc/outboundfeeds/rss/")
        build_attr_row(attribution_frame, "The Block API", "https://www.theblock.co/api/content")
        build_attr_row(attribution_frame, "Decrypt RSS", "https://decrypt.co/feed")
        # Ensure frame is large enough to show all
        try:
            self.root.update_idletasks()
            attribution_frame.update_idletasks()
            # Expand the window if content height exceeds
            needed = attribution_frame.winfo_height() + 360
            current_h = self.root.winfo_height()
            if needed > current_h:
                self.root.geometry(f"700x{needed}")
        except Exception:
            pass
        
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
