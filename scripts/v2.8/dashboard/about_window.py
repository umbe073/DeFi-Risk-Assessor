#!/usr/bin/env python3
"""
DeFi Risk Assessment About Window
Shows comprehensive about information with system details
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
import platform
import webbrowser
from datetime import datetime
from urllib.parse import urlparse

from system_update_manager import API_SERVICE_REGISTRY_FILE

# macOS compatibility fixes
if sys.platform == "darwin":
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

SERVICE_HOMEPAGE_URLS = {
    "etherscan": "https://etherscan.io/",
    "infura": "https://www.infura.io/",
    "moralis": "https://moralis.io/",
    "alchemy": "https://www.alchemy.com/",
    "coingecko": "https://www.coingecko.com/",
    "coinmarketcap": "https://coinmarketcap.com/",
    "coincap": "https://coincap.io/",
    "dexscreener": "https://dexscreener.com/",
    "birdeye": "https://birdeye.so/",
    "coinpaprika": "https://coinpaprika.com/",
    "ethplorer": "https://ethplorer.io/",
    "santiment": "https://santiment.net/",
    "solscan": "https://solscan.io/",
    "solanatracker": "https://solanatracker.io/",
    "zapper": "https://zapper.xyz/",
    "debank": "https://debank.com/",
    "oneinch": "https://1inch.io/",
    "lifi": "https://li.fi/",
    "breadcrumbs": "https://www.breadcrumbs.app/",
    "certik": "https://www.certik.com/",
    "honeypot": "https://honeypot.is/",
    "chainalysis_oracle": "https://www.chainalysis.com/",
    "ofac_sls": "https://sanctionssearch.ofac.treas.gov/",
    "scamsniffer": "https://www.scamsniffer.io/",
    "twitter": "https://x.com/",
    "discord": "https://discord.com/",
    "telegram": "https://telegram.org/",
    "reddit": "https://www.reddit.com/",
    "arkham": "https://arkhamintelligence.com/",
    "oklink": "https://www.oklink.com/",
    "goplus": "https://gopluslabs.io/",
    "trmlabs": "https://www.trmlabs.com/",
    "chainabuse": "https://www.chainabuse.com/",
    "thegraph": "https://thegraph.com/",
    "dune": "https://dune.com/",
    "bitcointalk": "https://bitcointalk.org/",
    "cointelegraph": "https://cointelegraph.com/",
    "coindesk": "https://www.coindesk.com/",
    "theblock": "https://www.theblock.co/",
    "decrypt": "https://decrypt.co/",
    "defillama": "https://defillama.com/",
}

SERVICE_NAME_TO_ID = {
    "etherscan api": "etherscan",
    "infura api": "infura",
    "moralis api": "moralis",
    "alchemy api": "alchemy",
    "coingecko api": "coingecko",
    "coinmarketcap api": "coinmarketcap",
    "coincap api": "coincap",
    "dexscreener api": "dexscreener",
    "birdeye api": "birdeye",
    "coinpaprika api": "coinpaprika",
    "ethplorer api": "ethplorer",
    "santiment api": "santiment",
    "solscan api": "solscan",
    "solanatracker api": "solanatracker",
    "zapper api": "zapper",
    "debank api": "debank",
    "1inch api": "oneinch",
    "lifi api": "lifi",
    "breadcrumbs api": "breadcrumbs",
    "certik api": "certik",
    "honeypot.is api": "honeypot",
    "chainalysis oracle": "chainalysis_oracle",
    "ofac sanctions list search": "ofac_sls",
    "scamsniffer blacklist": "scamsniffer",
    "x (twitter) api": "twitter",
    "discord api": "discord",
    "telegram api": "telegram",
    "reddit api": "reddit",
    "arkham api": "arkham",
    "oklink api": "oklink",
    "goplus api": "goplus",
    "trm labs api": "trmlabs",
    "chainabuse api": "chainabuse",
    "the graph": "thegraph",
    "dune api": "dune",
    "bitcointalk": "bitcointalk",
    "cointelegraph": "cointelegraph",
    "coindesk": "coindesk",
    "the block": "theblock",
    "decrypt": "decrypt",
    "defillama api": "defillama",
}

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

    def _fallback_sources(self):
        return [
            ("CoinGecko API", "https://www.coingecko.com/"),
            ("CoinMarketCap API", "https://coinmarketcap.com/"),
            ("Etherscan API", "https://etherscan.io/"),
            ("Ethplorer API", "https://ethplorer.io/"),
            ("Moralis API", "https://moralis.io/"),
            ("Infura API", "https://www.infura.io/"),
            ("Alchemy API", "https://www.alchemy.com/"),
            ("1inch API", "https://1inch.io/"),
            ("DeFiLlama API", "https://defillama.com/"),
            ("DexScreener API", "https://dexscreener.com/"),
            ("BirdEye API", "https://birdeye.so/"),
            ("CoinCap API", "https://coincap.io/"),
            ("Coinpaprika API", "https://coinpaprika.com/"),
            ("The Graph", "https://thegraph.com/"),
            ("Santiment API", "https://santiment.net/"),
            ("Solscan API", "https://solscan.io/"),
            ("SolanaTracker API", "https://solanatracker.io/"),
            ("Dune API", "https://dune.com/"),
            ("OKLink API", "https://www.oklink.com/"),
            ("GoPlus API", "https://gopluslabs.io/"),
            ("Chainabuse API", "https://www.chainabuse.com/"),
            ("Honeypot.is API", "https://honeypot.is/"),
            ("Chainalysis Oracle", "https://www.chainalysis.com/"),
            ("TRM Labs API", "https://www.trmlabs.com/"),
            ("ScamSniffer Blacklist", "https://www.scamsniffer.io/"),
        ]

    def _normalize_reference_url(self, service):
        """Convert registry entry URL to service homepage URL when possible."""
        if not isinstance(service, dict):
            return ""

        service_id = str(service.get("id") or "").strip().lower()
        if service_id in SERVICE_HOMEPAGE_URLS:
            return SERVICE_HOMEPAGE_URLS[service_id]

        name_key = str(service.get("name") or "").strip().lower()
        mapped_id = SERVICE_NAME_TO_ID.get(name_key, "")
        if mapped_id and mapped_id in SERVICE_HOMEPAGE_URLS:
            return SERVICE_HOMEPAGE_URLS[mapped_id]

        raw = str(service.get("reference_url") or "").strip()
        if not (raw.startswith("http://") or raw.startswith("https://")):
            return ""

        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}/"

    def _load_dynamic_sources(self):
        """Load API services from exported runtime registry (dynamic), fallback if unavailable."""
        if not os.path.exists(API_SERVICE_REGISTRY_FILE):
            return self._fallback_sources(), None
        try:
            with open(API_SERVICE_REGISTRY_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            services = payload.get("services", []) if isinstance(payload, dict) else []
            if not isinstance(services, list) or not services:
                return self._fallback_sources(), None

            rows = []
            for service in services:
                if not isinstance(service, dict):
                    continue
                name = str(service.get("name") or service.get("id") or "").strip()
                if not name:
                    continue
                url = self._normalize_reference_url(service)
                if not (url.startswith("http://") or url.startswith("https://")):
                    continue
                rows.append((name, url))
            if not rows:
                return self._fallback_sources(), None
            rows.sort(key=lambda x: x[0].lower())
            updated_at = payload.get("updated_at") if isinstance(payload, dict) else None
            return rows, updated_at
        except Exception:
            return self._fallback_sources(), None
        
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

        # Scrollable sources list so newly integrated APIs fit without resizing hacks.
        sources_canvas = tk.Canvas(attribution_frame, height=220, highlightthickness=0)
        sources_scroll = ttk.Scrollbar(attribution_frame, orient="vertical", command=sources_canvas.yview)
        sources_body = ttk.Frame(sources_canvas)
        sources_canvas.configure(yscrollcommand=sources_scroll.set)
        sources_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sources_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        sources_canvas.create_window((0, 0), window=sources_body, anchor="nw")
        sources_body.bind(
            "<Configure>",
            lambda e: sources_canvas.configure(scrollregion=sources_canvas.bbox("all"))
        )

        sources, updated_at = self._load_dynamic_sources()
        for label, url in sources:
            build_attr_row(sources_body, label, url)
        if updated_at:
            ttk.Label(
                sources_body,
                text=f"Registry updated at: {updated_at}",
                font=('Arial', 9),
                foreground='gray'
            ).pack(anchor=tk.W, pady=(8, 0))
        
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
