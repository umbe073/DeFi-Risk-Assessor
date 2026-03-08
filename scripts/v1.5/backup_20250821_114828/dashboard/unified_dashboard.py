#!/usr/bin/env python3
"""
Unified Dashboard Manager
Main application that manages all dashboard panels as embedded components
"""

import os
import sys
import time
import json
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

class DashboardPanel:
    """Base class for dashboard panels"""
    def __init__(self, parent_frame, title):
        self.parent_frame = parent_frame
        self.title = title
        self.frame = None
        self.is_visible = False
        
    def create_panel(self):
        """Create the panel content - to be implemented by subclasses"""
        raise NotImplementedError
        
    def show(self):
        """Show the panel"""
        if not self.frame:
            self.create_panel()
        self.frame.pack(fill='both', expand=True)
        self.is_visible = True
        
    def hide(self):
        """Hide the panel"""
        if self.frame:
            self.frame.pack_forget()
        self.is_visible = False
        
    def destroy(self):
        """Destroy the panel"""
        if self.frame:
            self.frame.destroy()
            self.frame = None
        self.is_visible = False

class APIServicePanel(DashboardPanel):
    """API Service monitoring panel"""
    def __init__(self, parent_frame):
        super().__init__(parent_frame, "API Services")
        
    def create_panel(self):
        """Create the API service panel"""
        self.frame = ttk.Frame(self.parent_frame)
        
        # Header
        header_label = ttk.Label(self.frame, text="🔧 API Service Dashboard", 
                                font=('Arial', 16, 'bold'))
        header_label.pack(pady=10)
        
        # Service status area
        status_frame = ttk.LabelFrame(self.frame, text="Service Status", padding="10")
        status_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Service list
        self.services_tree = ttk.Treeview(status_frame, columns=('status', 'rate_limit'), height=10)
        self.services_tree.heading('#0', text='Service')
        self.services_tree.heading('status', text='Status')
        self.services_tree.heading('rate_limit', text='Rate Limit')
        
        self.services_tree.pack(fill='both', expand=True)
        
        # Load initial data
        self.update_service_status()
        
    def update_service_status(self):
        """Update service status display"""
        # Clear existing items
        for item in self.services_tree.get_children():
            self.services_tree.delete(item)
            
        # Sample services (this would be loaded from actual API service manager)
        services = [
            ("🔗 Etherscan API", "✅ Active", "95/100 calls"),
            ("📊 CoinGecko API", "✅ Active", "8/10 calls"),
            ("🔧 Moralis API", "⚠️ Limited", "99/100 calls"),
            ("💰 CoinMarketCap", "✅ Active", "250/333 calls"),
        ]
        
        for service_name, status, rate_limit in services:
            self.services_tree.insert('', 'end', text=service_name, 
                                    values=(status, rate_limit))

class MainDashboardPanel(DashboardPanel):
    """Main dashboard panel"""
    def __init__(self, parent_frame):
        super().__init__(parent_frame, "Main Dashboard")
        
    def create_panel(self):
        """Create the main dashboard panel"""
        self.frame = ttk.Frame(self.parent_frame)
        
        # Header
        header_label = ttk.Label(self.frame, text="📊 DeFi Risk Assessment Dashboard", 
                                font=('Arial', 16, 'bold'))
        header_label.pack(pady=10)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(self.frame, text="System Overview", padding="15")
        stats_frame.pack(fill='x', padx=10, pady=5)
        
        # Load and display cache status
        self.update_cache_status(stats_frame)
        
        # Actions frame
        actions_frame = ttk.LabelFrame(self.frame, text="Quick Actions", padding="15")
        actions_frame.pack(fill='x', padx=10, pady=5)
        
        # Action buttons
        buttons_frame = ttk.Frame(actions_frame)
        buttons_frame.pack(fill='x')
        
        ttk.Button(buttons_frame, text="🚀 Quick Assessment", 
                  command=self.start_assessment).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="📋 View Reports", 
                  command=self.view_reports).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="🔄 Refresh Cache", 
                  command=self.refresh_cache).pack(side='left', padx=5)
        
    def update_cache_status(self, parent_frame):
        """Update cache status display"""
        try:
            cache_file = os.path.join(PROJECT_ROOT, 'data', 'real_data_cache.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                last_updated = cache_data.get('last_updated', 0)
                cache_age = (time.time() - last_updated) / 3600
                token_count = len(cache_data.get('tokens', {}))
                
                if cache_age < 2:
                    status_color = "green"
                    status_text = f"✅ Cache Fresh ({cache_age:.1f}h old)"
                elif cache_age < 24:
                    status_color = "orange"
                    status_text = f"⚠️ Cache Aging ({cache_age:.1f}h old)"
                else:
                    status_color = "red"
                    status_text = f"❌ Cache Stale ({cache_age:.1f}h old)"
                
                cache_label = ttk.Label(parent_frame, text=f"💾 {status_text}")
                cache_label.pack(anchor='w')
                
                tokens_label = ttk.Label(parent_frame, text=f"🪙 Tokens Cached: {token_count}")
                tokens_label.pack(anchor='w')
            else:
                error_label = ttk.Label(parent_frame, text="❌ No cache file found")
                error_label.pack(anchor='w')
                
        except Exception as e:
            error_label = ttk.Label(parent_frame, text=f"❌ Cache error: {e}")
            error_label.pack(anchor='w')
    
    def start_assessment(self):
        """Start risk assessment"""
        try:
            script_path = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'defi_complete_risk_assessment_clean.py')
            subprocess.Popen([sys.executable, script_path], cwd=PROJECT_ROOT)
            messagebox.showinfo("Assessment Started", "Risk assessment process started in background")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start assessment: {e}")
    
    def view_reports(self):
        """Open reports directory"""
        try:
            reports_dir = os.path.join(PROJECT_ROOT, 'data')
            if os.path.exists(reports_dir):
                if sys.platform == "darwin":
                    subprocess.Popen(["open", reports_dir])
                elif sys.platform == "win32":
                    os.startfile(reports_dir)
                else:
                    subprocess.Popen(["xdg-open", reports_dir])
            else:
                messagebox.showwarning("No Reports", "No reports directory found")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open reports: {e}")
    
    def refresh_cache(self):
        """Trigger cache refresh"""
        try:
            # Trigger webhook refresh
            import requests
            response = requests.post('http://localhost:5001/webhook/update_all', timeout=5)
            if response.status_code == 200:
                messagebox.showinfo("Cache Refresh", "Cache refresh triggered successfully")
                # Refresh the display after a delay
                self.frame.after(2000, lambda: self.update_cache_status(self.frame.winfo_children()[1]))
            else:
                messagebox.showwarning("Cache Refresh", f"Cache refresh failed: {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh cache: {e}")

class CredentialsPanel(DashboardPanel):
    """Credentials management panel"""
    def __init__(self, parent_frame):
        super().__init__(parent_frame, "Credentials")
        
    def create_panel(self):
        """Create the credentials panel"""
        self.frame = ttk.Frame(self.parent_frame)
        
        # Header
        header_label = ttk.Label(self.frame, text="🔐 API Credentials Management", 
                                font=('Arial', 16, 'bold'))
        header_label.pack(pady=10)
        
        # Credentials status
        status_frame = ttk.LabelFrame(self.frame, text="API Keys Status", padding="15")
        status_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Count configured APIs
        self.update_credentials_status(status_frame)
        
    def update_credentials_status(self, parent_frame):
        """Update credentials status display"""
        try:
            from dotenv import load_dotenv
            env_file = os.path.join(PROJECT_ROOT, '.env')
            
            if os.path.exists(env_file):
                load_dotenv(env_file)
                
                # List of expected API keys
                expected_keys = [
                    'ETHERSCAN_API_KEY', 'MORALIS_API_KEY', 'COINGECKO_API_KEY',
                    'COINMARKETCAP_API_KEY', 'COVALENT_API_KEY', 'TWITTER_BEARER_TOKEN',
                    'SANTIMENT_API_KEY', 'BREADCRUMBS_API_KEY', 'INFURA_API_KEY',
                    'ALCHEMY_API_KEY', 'INCH_API_KEY', 'DEBANK_API_KEY',
                    'ZAPPER_API_KEY', 'ETHPLORER_API_KEY', 'CERTIK_API_KEY',
                    'SCORECHAIN_API_KEY', 'TRMLABS_API_KEY', 'LUKKA_API_KEY',
                    'DEFISAFETY_API_KEY', 'ARKHAM_API_KEY'
                ]
                
                configured_count = 0
                for key in expected_keys:
                    value = os.getenv(key)
                    if value and value.strip() and value != 'your_key_here':
                        configured_count += 1
                
                total_keys = len(expected_keys)
                
                status_label = ttk.Label(parent_frame, 
                                       text=f"🔑 API Keys Configured: {configured_count}/{total_keys}")
                status_label.pack(anchor='w')
                
                if configured_count == total_keys:
                    completeness_label = ttk.Label(parent_frame, text="✅ All API keys configured")
                elif configured_count >= total_keys * 0.8:
                    completeness_label = ttk.Label(parent_frame, text="⚠️ Most API keys configured")
                else:
                    completeness_label = ttk.Label(parent_frame, text="❌ Many API keys missing")
                    
                completeness_label.pack(anchor='w')
            else:
                error_label = ttk.Label(parent_frame, text="❌ No .env file found")
                error_label.pack(anchor='w')
                
        except Exception as e:
            error_label = ttk.Label(parent_frame, text=f"❌ Credentials error: {e}")
            error_label.pack(anchor='w')

class UnifiedDashboard:
    """Main unified dashboard application"""
    def __init__(self):
        self.root = None
        self.notebook = None
        self.panels = {}
        self.system_tray = None
        self.lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
        os.makedirs(self.lock_dir, exist_ok=True)
        
    def create_main_window(self):
        """Create the main dashboard window"""
        self.root = tk.Tk()
        self.root.title("DeFi Risk Assessment - Unified Dashboard")
        self.root.geometry("1200x800")
        
        # Configure window attributes to minimize dock presence
        if sys.platform == "darwin":
            try:
                self.root.wm_attributes('-type', 'dialog')
            except:
                pass
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create panels
        self.create_panels()
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Create lock file
        self.create_lock_file()
        
    def create_panels(self):
        """Create all dashboard panels"""
        # Main Dashboard tab
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text="📊 Dashboard")
        self.panels['main'] = MainDashboardPanel(main_frame)
        self.panels['main'].show()
        
        # API Services tab
        api_frame = ttk.Frame(self.notebook)
        self.notebook.add(api_frame, text="🔧 API Services")
        self.panels['api'] = APIServicePanel(api_frame)
        self.panels['api'].show()
        
        # Credentials tab
        cred_frame = ttk.Frame(self.notebook)
        self.notebook.add(cred_frame, text="🔐 Credentials")
        self.panels['credentials'] = CredentialsPanel(cred_frame)
        self.panels['credentials'].show()
        
    def create_lock_file(self):
        """Create lock file for unified dashboard"""
        lock_file = os.path.join(self.lock_dir, 'unified_dashboard.lock')
        lock_data = {
            'pid': os.getpid(),
            'started_at': time.time(),
            'service_name': 'unified_dashboard'
        }
        
        try:
            with open(lock_file, 'w') as f:
                json.dump(lock_data, f)
            
            # Register cleanup
            import atexit
            atexit.register(lambda: self.cleanup_lock_file(lock_file))
        except Exception as e:
            print(f"Warning: Could not create lock file: {e}")
    
    def cleanup_lock_file(self, lock_file):
        """Clean up lock file"""
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except:
            pass
    
    def is_running(self):
        """Check if unified dashboard is already running"""
        lock_file = os.path.join(self.lock_dir, 'unified_dashboard.lock')
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    data = json.load(f)
                    pid = data.get('pid')
                    
                if pid:
                    try:
                        os.kill(pid, 0)
                        return True
                    except OSError:
                        os.remove(lock_file)
            except:
                try:
                    os.remove(lock_file)
                except:
                    pass
        return False
    
    def show_window(self):
        """Show the main window"""
        if not self.root:
            self.create_main_window()
        
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        
    def hide_window(self):
        """Hide the main window"""
        if self.root:
            self.root.withdraw()
    
    def quit_application(self):
        """Quit the application"""
        if self.root:
            self.root.destroy()
    
    def run(self):
        """Run the unified dashboard"""
        if self.is_running():
            print("Unified dashboard is already running")
            # Try to bring existing window to front
            return False
            
        self.create_main_window()
        self.root.mainloop()
        return True

def main():
    """Main entry point"""
    app = UnifiedDashboard()
    if not app.run():
        print("Dashboard already running - bringing to front")

if __name__ == "__main__":
    main()
