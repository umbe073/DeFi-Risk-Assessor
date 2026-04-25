#!/usr/bin/env python3
"""
DeFi Risk Assessment Main Dashboard
Primary interface for the DeFi risk assessment tool
"""

import sys
import os

# macOS compatibility setup
if sys.platform == "darwin":
    # Basic environment variables
    os.environ['LSUIElement'] = 'true'
    os.environ['NSApplicationActivationPolicy'] = 'accessory'
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

# macOS compatibility fixes - must be done before importing tkinter
if sys.platform == "darwin":
    # Import and apply macOS compatibility fix
    try:
        # Add the current directory to the path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Use tkinter compatibility module for macOS compatibility
        from tkinter_compatibility import tkinter_compat
        if tkinter_compat.is_compatible():
            print("✅ Tkinter compatibility verified")
        else:
            print("⚠️ Tkinter compatibility not available")
    except ImportError:
        # Fallback - just set basic environment variables
        os.environ['TK_SILENCE_DEPRECATION'] = '1'
        os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
        os.environ['TK_FRAMEWORK'] = '1'
        os.environ['DISPLAY'] = ':0'
        print("✅ Basic macOS compatibility applied")

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import hashlib
import hmac
import subprocess
import threading
import time
from datetime import datetime, timedelta
import pickle

# App bundle mode is now handled by the macOS compatibility fix
# No need for separate dock utilities

# Import token mappings from external file
try:
    # Add the v2.0 directory to the path (go up one directory from dashboard)
    v2_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(v2_dir)
    from token_mappings import (
        get_token_name, get_token_symbol, get_coingecko_id, 
        get_paprika_id, get_token_type,
        get_cmc_id, get_cmc_name, get_cmc_slug
    )
except ImportError:
    # Fallback if token_mappings.py is not available - regenerate from CSV
    try:
        import subprocess
        import os
        v2_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.run(['python3', 'generate_token_mappings.py'], cwd=v2_dir, check=True)
        from token_mappings import (
            get_token_name, get_token_symbol, get_coingecko_id, 
            get_paprika_id, get_token_type,
            get_cmc_id, get_cmc_name, get_cmc_slug
        )
    except Exception as e:
        print(f"      ⚠️ Failed to regenerate token mappings: {e}")
        # Fallback functions with explicit return types to satisfy type checker
        from typing import Optional
        def get_token_name(address: str) -> str: return 'Unknown Token'
        def get_token_symbol(address: str) -> str: return 'Unknown'
        def get_coingecko_id(symbol: str) -> Optional[str]: return None
        def get_paprika_id(symbol: str) -> Optional[str]: return None
        # No estimation functions - only real data
        def get_token_type(symbol: str) -> str: return 'Unknown'
        def get_cmc_id(symbol: str) -> Optional[str]: return None
        def get_cmc_name(symbol: str) -> Optional[str]: return None
        def get_cmc_slug(symbol: str) -> Optional[str]: return None

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
except Exception:
    pass

WEBHOOK_BASE_URL = str(os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5001')).strip().rstrip('/')
WEBHOOK_SHARED_SECRET = str(os.getenv('WEBHOOK_SHARED_SECRET', '')).strip()


def _webhook_headers(payload_bytes: bytes = b'', *, include_signature: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {'Accept': 'application/json'}
    if not WEBHOOK_SHARED_SECRET:
        return headers

    headers['Authorization'] = f'Bearer {WEBHOOK_SHARED_SECRET}'
    if include_signature:
        timestamp = str(int(time.time()))
        signed_payload = f'{timestamp}.'.encode('utf-8') + (payload_bytes or b'')
        signature = hmac.new(
            WEBHOOK_SHARED_SECRET.encode('utf-8'),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        headers['X-Webhook-Timestamp'] = timestamp
        headers['X-Webhook-Signature'] = f'sha256={signature}'
    return headers

class DeFiDashboard:
    def __init__(self):
        try:
            # Create root window
            self.root = tk.Tk()
            
            # Track assessment state to avoid duplicate logs
            self.last_assessment_state = None
            self.assessment_start_time = None
            self.last_log_check = 0
            self.assessment_process_count = 0
            
            # Cache system
            self.cache_file = os.path.join(DATA_DIR, 'token_data_cache.pkl')
            self.cache_duration = timedelta(hours=1)  # 1 hour cache
            # Track visible report rows to their absolute paths
            self.report_paths = {}
            
            self.setup_window()
            self.create_widgets()
            self.load_recent_reports()
            
            # Set up proper cleanup on window close
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
        except Exception as e:
            print(f"Error initializing dashboard: {e}")
            # Create a simple error window
            try:
                error_root = tk.Tk()
                error_root.title("Dashboard Error")
                error_root.geometry("400x200")
                
                error_label = tk.Label(error_root, text=f"Dashboard failed to initialize:\n{str(e)}", 
                                     font=('Arial', 12), wraplength=350)
                error_label.pack(pady=20)
                
                close_button = tk.Button(error_root, text="Close", command=error_root.destroy)
                close_button.pack(pady=10)
                
                error_root.mainloop()
            except:
                print("Could not create error window")
                sys.exit(1)
        
    def setup_window(self):
        """Setup the main dashboard window"""
        try:
            self.root.title("DeFi Risk Assessment Dashboard")
            self.root.geometry("1200x800")  # Adjusted to match screenshot dimensions
            self.root.resizable(True, True)
            
            # macOS compatibility fixes
            if sys.platform == "darwin":
                # Avoid macOS-specific crashes
                try:
                    self.root.tk.call('tk', 'scaling', 1.0)
                except:
                    pass
                    
                # Additional macOS fixes
                try:
                    # Set window level to avoid dock issues
                    self.root.attributes('-topmost', False)
                except:
                    pass
                    
                # Disable problematic theme usage on macOS
                pass
            else:
                # Modern styling for other platforms
                try:
                    style = ttk.Style()
                    style.theme_use('clam')
                except:
                    pass
            
            # Configure custom styles with error handling - DISABLED due to macOS crash
            # try:
            #     style = ttk.Style()
            #     style.configure('Title.TLabel', font=('Arial', 20, 'bold'), foreground='#2c3e50')
            #     style.configure('Subtitle.TLabel', font=('Arial', 12), foreground='#5d6d7e')
            #     style.configure('Action.TButton', font=('Arial', 11, 'bold'))
            # except:
            #     # Fallback to default styles if custom styles fail
            #     pass
            
            # Bring window to front with error handling
            try:
                self.root.lift()
                self.root.attributes('-topmost', True)
                self.root.after_idle(self.root.attributes, '-topmost', False)
            except:
                pass
                
        except Exception as e:
            print(f"Warning: Error in setup_window: {e}")
            # Continue with basic setup
            pass
        
    def create_widgets(self):
        """Create all dashboard widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="30")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=3)  # Left column (Quick Actions + Token Data Viewer) gets more space
        main_frame.columnconfigure(1, weight=1)  # Right column (Reports + Status + Logs) gets less space
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 30))
        
        title_label = ttk.Label(header_frame, text="🛡️ DeFi Risk Assessment Tool")
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        subtitle_label = ttk.Label(header_frame, text="Professional cryptocurrency risk analysis platform")
        subtitle_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        # Quick Actions Panel (more compact)
        actions_frame = ttk.LabelFrame(main_frame, text="🚀 Quick Actions", padding="10")
        actions_frame.grid(row=1, column=0, sticky="we", padx=(0, 15))
        actions_frame.columnconfigure(0, weight=1)
        
        # Action buttons (more compact)
        assess_btn = ttk.Button(actions_frame, text="🔍 Start Risk Assessment", 
                               command=self.start_assessment)
        assess_btn.grid(row=0, column=0, sticky="we", pady=(0, 5), ipady=2)
        
        api_btn = ttk.Button(actions_frame, text="🔧 API Service Monitor", 
                            command=self.open_api_dashboard)
        api_btn.grid(row=1, column=0, sticky="we", pady=(0, 5), ipady=2)
        
        creds_btn = ttk.Button(actions_frame, text="🔐 Manage Credentials", 
                              command=self.manage_credentials)
        creds_btn.grid(row=2, column=0, sticky="we", pady=(0, 5), ipady=2)
        
        chains_btn = ttk.Button(actions_frame, text="🔗 Manage Chains", 
                               command=self.manage_chains)
        chains_btn.grid(row=3, column=0, sticky="we", pady=(0, 5), ipady=2)
        
        tokens_btn = ttk.Button(actions_frame, text="📝 Edit Token List", 
                               command=self.edit_tokens)
        tokens_btn.grid(row=4, column=0, sticky="we", ipady=2)
        
        # Recent Reports Panel
        reports_frame = ttk.LabelFrame(main_frame, text="📊 Recent Reports", padding="20")
        reports_frame.grid(row=1, column=1, sticky="nsew")
        reports_frame.columnconfigure(0, weight=1)
        reports_frame.rowconfigure(1, weight=1)
        
        # Reports list
        reports_list_frame = ttk.Frame(reports_frame)
        reports_list_frame.grid(row=1, column=0, sticky="nsew")
        reports_list_frame.columnconfigure(0, weight=1)
        reports_list_frame.rowconfigure(0, weight=1)
        
        # Treeview for reports
        columns = ('Date', 'Tokens', 'Status')
        self.reports_tree = ttk.Treeview(reports_list_frame, columns=columns, show='headings', height=10)
        
        # Define headings
        self.reports_tree.heading('Date', text='Date')
        self.reports_tree.heading('Tokens', text='Tokens Analyzed')
        self.reports_tree.heading('Status', text='Status')
        
        # Configure column widths
        self.reports_tree.column('Date', width=120)
        self.reports_tree.column('Tokens', width=100)
        self.reports_tree.column('Status', width=100)
        
        # Scrollbar for reports
        reports_scroll = ttk.Scrollbar(reports_list_frame, orient=tk.VERTICAL, command=self.reports_tree.yview)
        self.reports_tree.configure(yscrollcommand=reports_scroll.set)
        
        self.reports_tree.grid(row=0, column=0, sticky="nsew")
        reports_scroll.grid(row=0, column=1, sticky="ns")
        
        # Reports action buttons
        reports_actions = ttk.Frame(reports_frame)
        reports_actions.grid(row=2, column=0, sticky="we", pady=(10, 0))
        reports_actions.columnconfigure(2, weight=1)
        
        view_btn = ttk.Button(reports_actions, text="👁️ View Report", command=self.view_selected_report)
        view_btn.grid(row=0, column=0, padx=(0, 10))
        
        export_btn = ttk.Button(reports_actions, text="📤 Export", command=self.export_report)
        export_btn.grid(row=0, column=1, padx=(0, 10))
        
        refresh_btn = ttk.Button(reports_actions, text="🔄 Refresh", command=self.load_recent_reports)
        refresh_btn.grid(row=0, column=3)
        
        # System Status Panel (right side, expanded height)
        status_frame = ttk.LabelFrame(main_frame, text="📈 System Status", padding="10")
        status_frame.grid(row=2, column=1, sticky="nsew", pady=(15, 0))
        
        self.status_text = tk.Text(status_frame, height=12, wrap=tk.WORD, font=('Courier', 9))
        status_scroll = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scroll.set)
        
        self.status_text.grid(row=0, column=0, sticky="nsew")
        status_scroll.grid(row=0, column=1, sticky="ns")
        
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
        
        # Data Viewer Panel (left column) — move up to fill gap under Quick Actions
        data_frame = ttk.LabelFrame(main_frame, text="📊 Token Data Viewer", padding="15")
        data_frame.grid(row=2, column=0, sticky="nsew", pady=(15, 0))
        
        # Data viewer controls
        data_controls = ttk.Frame(data_frame)
        data_controls.grid(row=0, column=0, sticky="we", pady=(0, 10))
        
        load_csv_btn = ttk.Button(data_controls, text="📁 Load CSV Data", command=self.load_csv_data)
        load_csv_btn.grid(row=0, column=0, padx=(0, 10))
        
        load_excel_btn = ttk.Button(data_controls, text="📊 Load Excel Data", command=self.load_excel_data)
        load_excel_btn.grid(row=0, column=1, padx=(0, 10))
        
        refresh_data_btn = ttk.Button(data_controls, text="🔄 Refresh Data", command=self.refresh_data_view)
        refresh_data_btn.grid(row=0, column=2)
        
        # Data treeview
        data_tree_frame = ttk.Frame(data_frame)
        data_tree_frame.grid(row=1, column=0, sticky="nsew")
        data_tree_frame.columnconfigure(0, weight=1)
        data_tree_frame.rowconfigure(0, weight=1)
        
        # Treeview for data
        # Token Data Viewer must contain exactly these columns in this order
        self.data_columns = (
            'Token', 'Symbol', 'Chain', 'Market Cap', 'Volume 24h', 'Holders', 'Liquidity'
        )
        self._data_sort_column = None
        self._data_sort_descending = False
        # Set height to leave room for logs
        self.data_tree = ttk.Treeview(data_tree_frame, columns=self.data_columns, show='headings', height=15)
        
        # Define headings
        for col in self.data_columns:
            self.data_tree.heading(col, text=col, command=lambda c=col: self.sort_data_tree_by_column(c))
            self.data_tree.column(col, width=100)
        
        # Scrollbars for data
        data_v_scroll = ttk.Scrollbar(data_tree_frame, orient=tk.VERTICAL, command=self.data_tree.yview)
        data_h_scroll = ttk.Scrollbar(data_tree_frame, orient=tk.HORIZONTAL, command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=data_v_scroll.set, xscrollcommand=data_h_scroll.set)
        
        self.data_tree.grid(row=0, column=0, sticky="nsew")
        data_v_scroll.grid(row=0, column=1, sticky="ns")
        data_h_scroll.grid(row=1, column=0, sticky="we")
        
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(1, weight=1)
        
        # Live Logs Panel (right side, expanded height)
        logs_frame = ttk.LabelFrame(main_frame, text="📋 Live Assessment Logs", padding="10")
        logs_frame.grid(row=3, column=1, sticky="nsew", pady=(15, 0))
        
        self.logs_text = tk.Text(logs_frame, height=12, wrap=tk.WORD, font=('Courier', 9), 
                                bg='#1e1e1e', fg='#ffffff', insertbackground='white')
        logs_scroll = ttk.Scrollbar(logs_frame, orient=tk.VERTICAL, command=self.logs_text.yview)
        self.logs_text.configure(yscrollcommand=logs_scroll.set)
        
        self.logs_text.grid(row=0, column=0, sticky="nsew")
        logs_scroll.grid(row=0, column=1, sticky="ns")
        
        # Clear logs button
        clear_logs_btn = ttk.Button(logs_frame, text="Clear Logs", command=self.clear_logs)
        clear_logs_btn.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        
        # Configure main frame row weights
        main_frame.rowconfigure(1, weight=0)  # Quick Actions (fixed height)
        # Give Token Data Viewer row moderate space
        main_frame.rowconfigure(2, weight=4)
        # Give Logs row more space to be visible
        main_frame.rowconfigure(3, weight=4)
        
        # Load initial status and start log monitoring
        self.update_system_status()
        self.start_log_monitoring()
    
    def load_cache(self):
        """Load cached token data"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    return cache_data
        except Exception as e:
            print(f"Error loading cache: {e}")
        return None
    
    def save_cache(self, token_data):
        """Save token data to cache"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            cache_data = {
                'timestamp': datetime.now(),
                'data': token_data
            }
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            print(f"      💾 Cache saved with {len(token_data)} tokens")
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def is_cache_valid(self, cache_data):
        """Check if cache is still valid (less than 1 hour old)"""
        if not cache_data or 'timestamp' not in cache_data:
            return False
        
        cache_age = datetime.now() - cache_data['timestamp']
        return cache_age < self.cache_duration
    
    def load_recent_reports(self):
        """Load recent assessment reports"""
        try:
            print(f"🔍 Loading recent reports from {DATA_DIR}")
            
            # Clear existing items
            for item in self.reports_tree.get_children():
                self.reports_tree.delete(item)
            self.report_paths = {}
            
            # Look for report files in the risk_reports directory
            reports_found = 0
            reports_dir = os.path.join(DATA_DIR, 'risk_reports')
            if os.path.exists(reports_dir):
                # Get all Excel files and sort by modification time
                excel_files = []
                for file in os.listdir(reports_dir):
                    if file.startswith('~$'):
                        continue
                    if file.endswith('.xlsx') and 'Risk Assessment Results' in file:
                        file_path = os.path.join(reports_dir, file)
                        stat = os.stat(file_path)
                        excel_files.append((file_path, stat.st_mtime, file))
                        print(f"   📄 Found Excel file: {file} (modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')})")
                
                # Sort by modification time (newest first)
                excel_files.sort(key=lambda x: x[1], reverse=True)
                print(f"   📊 Found {len(excel_files)} Excel files total")
                
                for file_path, mtime, filename in excel_files:
                    date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                    
                    # Try to determine token count (placeholder)
                    tokens = "Multiple"
                    status = "✅ Complete"
                    
                    print(f"   ➕ Adding to tree: {date} - {filename}")
                    row_id = self.reports_tree.insert('', 'end', values=(date, tokens, status))
                    self.report_paths[row_id] = file_path
                    reports_found += 1
                
                print(f"   ✅ Added {reports_found} reports to the list")
            else:
                print(f"   ❌ Reports directory does not exist: {reports_dir}")
            
            if reports_found == 0:
                self.reports_tree.insert('', 'end', values=('No reports found', '', ''))
                print("   ⚠️ No reports found")
                
        except Exception as e:
            print(f"Error loading reports: {e}")
            import traceback
            traceback.print_exc()

    def _get_selected_report_path(self):
        """Resolve the file path for the selected report row."""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a report first.")
            return None
        row_id = selection[0]
        report_path = self.report_paths.get(row_id)
        if not report_path:
            messagebox.showwarning("Report Not Found", "Could not resolve the selected report path. Please refresh and try again.")
            return None
        if not os.path.exists(report_path):
            messagebox.showwarning("Missing File", f"Selected report no longer exists:\n{report_path}\n\nRefreshing report list.")
            self.load_recent_reports()
            return None
        return report_path
    
    def update_status(self, message: str):
        """Update the status display with a message"""
        try:
            # Update the status text widget
            if hasattr(self, 'status_text'):
                self.status_text.delete(1.0, tk.END)
                timestamp = datetime.now().strftime('%H:%M:%S')
                status_message = f"[{timestamp}] {message}\n\n"
                
                # Add current system status
                status_message += "System Status:\n"
                status_message += "✅ Dashboard: Running\n"
                status_message += "✅ Python: Active\n"
                status_message += "✅ File System: Accessible\n"
                
                self.status_text.insert(tk.END, status_message)
                self.status_text.see(tk.END)
                
                # Also print to console for debugging
                print(f"[STATUS] {message}")
                
        except Exception as e:
            print(f"Error updating status: {e}")
    
    def update_system_status(self):
        """Update system status display"""
        try:
            status_lines = []
            
            # Check API keys
            env_file = os.path.join(PROJECT_ROOT, '.env')
            api_count = 0
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    for line in f:
                        if 'API_KEY=' in line and not line.strip().startswith('#'):
                            if '=' in line and line.split('=', 1)[1].strip():
                                api_count += 1
            
            status_lines.append(f"🔑 API Keys Configured: {api_count}/20")
            
            # Check cache status
            cache_file = os.path.join(DATA_DIR, 'real_data_cache.json')
            if os.path.exists(cache_file):
                stat = os.stat(cache_file)
                age_hours = (time.time() - stat.st_mtime) / 3600
                status_lines.append(f"💾 Cache Status: {age_hours:.1f}h old")
            else:
                status_lines.append("💾 Cache Status: Not found")
            
            # Check token list
            tokens_file = os.path.join(DATA_DIR, 'tokens.csv')
            if os.path.exists(tokens_file):
                with open(tokens_file, 'r') as f:
                    lines = len(f.readlines()) - 1  # Exclude header
                status_lines.append(f"📋 Token List: {lines} tokens")
            else:
                status_lines.append("📋 Token List: Not found")
            
            # System health
            status_lines.append("")
            status_lines.append("🟢 System Status: Operational")
            status_lines.append(f"⏰ Last Updated: {datetime.now().strftime('%H:%M:%S')}")
            
            # Update display
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, '\n'.join(status_lines))
            
        except Exception as e:
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, f"Error updating status: {e}")
        
        # Schedule next update
        self.root.after(5000, self.update_system_status)  # Update every 5 seconds
    
    def start_assessment(self):
        """Start a new risk assessment with progress bar"""
        try:
            # Check if the risk assessment script exists
            script_path = os.path.join(PROJECT_ROOT, 'scripts', 'v2.0', 'defi_complete_risk_assessment_clean.py')
            if not os.path.exists(script_path):
                messagebox.showerror("Error", f"Risk assessment script not found:\n{script_path}")
                return
            
            # Check if the progress bar module exists
            progress_bar_path = os.path.join(PROJECT_ROOT, 'scripts', 'v2.0', 'working_progress_bar.py')
            if not os.path.exists(progress_bar_path):
                messagebox.showerror("Error", f"Progress bar module not found:\n{progress_bar_path}")
                return
            
            # Check if tokens.csv exists
            tokens_file = os.path.join(DATA_DIR, 'tokens.csv')
            if not os.path.exists(tokens_file):
                messagebox.showerror("Error", f"Tokens file not found:\n{tokens_file}\n\nPlease create a tokens.csv file in the data directory.")
                return
            
            # Use the process manager to launch the assessment
            from process_manager import process_manager
            
            # Launch the assessment using the process manager
            success, message = process_manager.launch_assessment()
            
            if success:
                # Show a message that the assessment is starting
                messagebox.showinfo(
                    "Assessment Started", 
                    "🚀 Risk assessment has been started!\n\n"
                    "📊 A progress bar window should open in your browser showing the assessment progress.\n\n"
                    "⏳ The assessment will run in the background and notify you when complete.\n\n"
                    "🔍 You can monitor progress in the browser window that opens."
                )
                
                # Update the status in the dashboard
                self.update_status("🚀 Risk assessment started - check browser for progress bar")
            else:
                messagebox.showerror("Error", f"Failed to start assessment:\n{message}")
                self.update_status(f"❌ Error starting assessment: {message}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start assessment:\n{str(e)}")
            self.update_status(f"❌ Error starting assessment: {str(e)}")
    
    def open_api_dashboard(self):
        """Open API service dashboard"""
        try:
            # Import and use process manager for foreground launch
            from process_manager import ProcessManager
            process_manager = ProcessManager()
            success, message = process_manager.launch_api_dashboard()
            if not success:
                messagebox.showerror("Error", f"Failed to open API dashboard: {message}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open API dashboard: {e}")
    
    def manage_credentials(self):
        """Open credential management"""
        try:
            # Use the global process manager instance
            from process_manager import process_manager
            success, message = process_manager.launch_credential_manager()
            if not success:
                messagebox.showerror("Error", f"Failed to open credential manager: {message}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open credential manager: {e}")
    
    def manage_chains(self):
        """Open chain management"""
        try:
            # Use the global process manager instance
            from process_manager import process_manager
            success, message = process_manager.launch_chain_manager()
            if not success:
                messagebox.showerror("Error", f"Failed to open chain manager: {message}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open chain manager: {e}")
    
    def edit_tokens(self):
        """Open interactive token editor"""
        try:
            # Import the token editor
            from token_editor import TokenEditor
            
            # Create and run the token editor
            editor = TokenEditor(self.root)
            editor.run()
            
            # Refresh the dashboard data after editing
            self.refresh_dashboard_data()
            
        except ImportError as e:
            print(f"Token editor import failed: {e}")
            # Fallback to opening the CSV file directly
            try:
                tokens_file = os.path.join(DATA_DIR, 'tokens.csv')
                if sys.platform == "darwin":
                    subprocess.Popen(["open", tokens_file])
                elif sys.platform == "win32":
                    os.startfile(tokens_file)
                else:
                    subprocess.Popen(["xdg-open", tokens_file])
                messagebox.showinfo("Info", "Token editor not available. Opening CSV file directly.\nPlease run the update script after making changes.")
            except Exception as e2:
                messagebox.showerror("Error", f"Failed to open token list: {e2}")
        except Exception as e:
            print(f"Token editor error: {e}")
            messagebox.showerror("Error", f"Failed to open token editor: {e}")
            
    def refresh_dashboard_data(self):
        """Refresh dashboard data after token changes"""
        try:
            # Reload recent reports to reflect any token changes
            self.load_recent_reports()
            
            # Update status
            self.update_status("✅ Dashboard refreshed after token changes")
            
        except Exception as e:
            print(f"Warning: Failed to refresh dashboard data: {e}")
    
    def view_selected_report(self):
        """View the selected report"""
        report_path = self._get_selected_report_path()
        if not report_path:
            return
        
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", report_path])
            elif sys.platform == "win32":
                os.startfile(report_path)
            else:
                subprocess.Popen(["xdg-open", report_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open report: {e}")
    
    def export_report(self):
        """Export selected report"""
        source_path = self._get_selected_report_path()
        if not source_path:
            return
        
        try:
            # Ask user for export location
            export_path = filedialog.asksaveasfilename(
                title="Export Report",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            
            if export_path:
                import shutil
                shutil.copy2(source_path, export_path)
                messagebox.showinfo("Export Complete", f"Report exported to:\n{export_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")
    
    def clear_logs(self):
        """Clear the logs display"""
        self.logs_text.delete(1.0, tk.END)
        self.add_log_entry("📋 Logs cleared", "info")
    
    def add_log_entry(self, message, log_type="info"):
        """Add a log entry with timestamp and color coding"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Color coding based on log type
        colors = {
            'info': '#00ff00',      # Green
            'warning': '#ffff00',   # Yellow  
            'error': '#ff4444',     # Red
            'success': '#00ff88',   # Light green
            'processing': '#88ccff' # Light blue
        }
        
        color = colors.get(log_type, '#ffffff')
        
        # Insert at end and scroll down
        self.logs_text.insert(tk.END, f"[{timestamp}] {message}\n")
        
        # Apply color to the last line
        line_start = f"{self.logs_text.index(tk.END).split('.')[0]}.0 linestart"
        line_end = f"{self.logs_text.index(tk.END).split('.')[0]}.0 lineend"
        
        try:
            # Create a tag for this log type if it doesn't exist
            tag_name = f"log_{log_type}"
            self.logs_text.tag_configure(tag_name, foreground=color)
            self.logs_text.tag_add(tag_name, line_start, line_end)
        except:
            pass  # Ignore tag errors
        
        # Auto-scroll to bottom
        self.logs_text.see(tk.END)
        
        # Limit log entries to last 100 lines to prevent memory issues
        lines = self.logs_text.get(1.0, tk.END).count('\n')
        if lines > 100:
            # Remove oldest lines
            self.logs_text.delete(1.0, f"{lines-100}.0")
    
    def start_log_monitoring(self):
        """Start monitoring for assessment logs"""
        self.add_log_entry("🚀 Log monitoring started", "info")
        self.check_running_assessments()
        
        # Schedule regular checks
        self.root.after(2000, self.monitor_logs)  # Check every 2 seconds
    
    def monitor_logs(self):
        """Monitor for new log entries"""
        try:
            # Check if assessment is running
            self.check_running_assessments()
            
            # Add periodic system status updates
            current_time = time.time()
            if (current_time - self.last_log_check) > 60:  # Every minute
                self.add_system_status_log()
                self.last_log_check = current_time
            
            # Schedule next check
            self.root.after(2000, self.monitor_logs)
        except Exception as e:
            self.add_log_entry(f"❌ Log monitoring error: {e}", "error")
    
    def check_running_assessments(self):
        """Check for running assessment processes"""
        try:
            import subprocess
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            processes = result.stdout
            
            # Look for running assessment processes
            if 'defi_complete_risk_assessment_clean.py' in processes:
                lines = processes.split('\n')
                assessment_processes = [line for line in lines if 'defi_complete_risk_assessment_clean.py' in line]
                current_count = len(assessment_processes)
                
                # Only log if state has changed or enough time has passed
                current_time = time.time()
                should_log = False
                
                if self.last_assessment_state != current_count:
                    # State changed - log the change
                    if current_count > 0 and self.last_assessment_state == 0:
                        self.add_log_entry(f"🚀 Assessment started - {current_count} process(es) running", "success")
                        self.assessment_start_time = current_time
                    elif current_count == 0 and (self.last_assessment_state or 0) > 0:
                        duration = current_time - self.assessment_start_time if self.assessment_start_time else 0
                        self.add_log_entry(f"✅ Assessment completed in {duration:.1f}s", "success")
                    else:
                        self.add_log_entry(f"📊 Assessment processes: {current_count} running", "processing")
                    should_log = True
                elif current_count > 0 and (current_time - self.last_log_check) > 30:
                    # Log progress every 30 seconds when assessment is running
                    duration = current_time - self.assessment_start_time if self.assessment_start_time else 0
                    self.add_log_entry(f"⏳ Assessment in progress... ({duration:.0f}s elapsed)", "processing")
                    should_log = True
                
                if should_log:
                    self.last_assessment_state = current_count
                    self.last_log_check = current_time
                    self.assessment_process_count = current_count
                    
                    # Try to read recent logs for more detailed status
                    self.read_recent_logs()
            else:
                # No processes running
                if self.last_assessment_state != 0:
                    self.add_log_entry("💤 No assessment processes running", "info")
                    self.last_assessment_state = 0
                    self.assessment_start_time = None
                    
        except Exception as e:
            pass  # Don't spam with ps errors
    
    def read_recent_logs(self):
        """Read recent logs from assessment processes"""
        try:
            # Look for recent log files
            logs_dir = os.path.join(PROJECT_ROOT, 'logs')
            if os.path.exists(logs_dir):
                log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
                
                if log_files:
                    # Get the most recent log file
                    latest_log = max(log_files, key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)))
                    log_path = os.path.join(logs_dir, latest_log)
                    
                    # Read last few lines
                    with open(log_path, 'r') as f:
                        lines = f.readlines()
                        
                    # Show only the most recent interesting logs
                    recent_lines = lines[-3:] if len(lines) >= 3 else lines
                    
                    for line in recent_lines:
                        line = line.strip()
                        if line and any(keyword in line.lower() for keyword in 
                                      ['error', 'success', 'complete', 'failed', 'starting', 'processing', 
                                       'token', 'api', 'symbol', 'risk', 'score']):
                            
                            # Determine log type based on content
                            if 'error' in line.lower() or 'failed' in line.lower():
                                log_type = 'error'
                            elif 'success' in line.lower() or 'complete' in line.lower():
                                log_type = 'success'
                            elif 'warning' in line.lower():
                                log_type = 'warning'
                            elif 'token' in line.lower() or 'symbol' in line.lower():
                                log_type = 'info'
                            else:
                                log_type = 'processing'
                            
                            # Extract meaningful part of log and add context
                            if ': ' in line:
                                message = line.split(': ', 1)[1]
                            else:
                                message = line
                            
                            # Add context based on content
                            if 'token' in line.lower():
                                self.add_log_entry(f"🪙 {message}", log_type)
                            elif 'api' in line.lower():
                                self.add_log_entry(f"🔗 {message}", log_type)
                            elif 'symbol' in line.lower():
                                self.add_log_entry(f"🏷️ {message}", log_type)
                            elif 'risk' in line.lower() or 'score' in line.lower():
                                self.add_log_entry(f"📊 {message}", log_type)
                            else:
                                self.add_log_entry(f"📋 {message}", log_type)
                            
        except Exception:
            pass  # Don't spam with log reading errors

    def add_system_status_log(self):
        """Add periodic system status log entries"""
        try:
            import random
            # Get current system status
            cache_file = os.path.join(DATA_DIR, 'real_data_cache.json')
            cache_status = "❌ Missing" if not os.path.exists(cache_file) else "✅ Available"
            
            # Random status messages to keep logs varied
            status_messages = [
                f"💾 Cache status: {cache_status}",
                f"🔍 Monitoring {self.assessment_process_count} assessment process(es)",
                f"⏰ System time: {datetime.now().strftime('%H:%M:%S')}",
                f"📊 Dashboard active - monitoring for updates",
                f"🛡️ Risk assessment system operational"
            ]
            
            # Select a random message
            message = random.choice(status_messages)
            self.add_log_entry(message, "info")
            
        except Exception:
            pass  # Don't spam with status errors
    
    def on_closing(self):
        """Handle window close event"""
        try:
            print("🔄 Dashboard window closing, cleaning up...")
            
            # Clean up lock file
            self.cleanup_lock_file()
            
            # Destroy the window
            self.root.destroy()
            
            print("✅ Dashboard cleanup completed")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            # Force destroy anyway
            try:
                self.root.destroy()
            except:
                pass
    
    def cleanup_lock_file(self):
        """Clean up the lock file for this dashboard"""
        try:
            lock_dir = os.path.join('/Users/amlfreak/Desktop/venv/defi_dashboard_locks')
            lock_file = os.path.join(lock_dir, 'main_dashboard.lock')
            
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print("✅ Lock file cleaned up")
        except Exception as e:
            print(f"⚠️ Could not clean up lock file: {e}")
    
    def run(self):
        """Start the dashboard"""
        self.root.mainloop()
    
    def ensure_token_data_viewer_current(self, force_rebuild: bool = False):
        """Ensure token_data_viewer.csv is current, optionally forcing a rebuild."""
        try:
            token_data_viewer_path = os.path.join(DATA_DIR, 'token_data_viewer.csv')
            tokens_csv_path = os.path.join(DATA_DIR, 'tokens.csv')
            viewer_exists = os.path.exists(token_data_viewer_path)
            
            # If tokens.csv is missing we can only use whatever viewer data is already there
            if not os.path.exists(tokens_csv_path):
                return viewer_exists
            
            tokens_mtime = os.path.getmtime(tokens_csv_path)
            viewer_mtime = os.path.getmtime(token_data_viewer_path) if viewer_exists else 0
            needs_update = force_rebuild or (not viewer_exists) or tokens_mtime > viewer_mtime
            
            if not needs_update:
                return True
            
            # Ask the user before running the expensive updater (can overwrite cached real data)
            if force_rebuild:
                prompt_msg = (
                    "Refresh Data was requested.\n\n"
                    "Do you want to rebuild Token Data Viewer cache now using live APIs?"
                )
            elif viewer_exists:
                prompt_msg = (
                    "tokens.csv was updated after token_data_viewer.csv was generated.\n\n"
                    "Do you want to rebuild the Token Data Viewer cache now? "
                    "Choosing 'No' keeps the previously cached real data."
                )
            else:
                prompt_msg = (
                    "token_data_viewer.csv is missing.\n\n"
                    "Do you want to generate it now using update_token_data_viewer.py?"
                )
            
            if not messagebox.askyesno("Token Data Viewer Update", prompt_msg, parent=self.root):
                self.add_log_entry("⚠️ Using existing Token Data Viewer cache (may be stale).", "warning")
                return viewer_exists
            
            scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            updater_script = os.path.join(scripts_dir, 'update_token_data_viewer.py')
            if not os.path.exists(updater_script):
                self.add_log_entry("❌ update_token_data_viewer.py not found. Cannot refresh viewer data.", "error")
                messagebox.showerror(
                    "Token Data Viewer Update",
                    "update_token_data_viewer.py was not found. Please ensure the script exists."
                )
                return viewer_exists
            
            self.add_log_entry("⚙️ Running Token Data Viewer updater...", "processing")
            result = subprocess.run(
                [sys.executable, updater_script],
                cwd=scripts_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.add_log_entry("✅ Token Data Viewer cache refreshed with latest tokens.csv", "success")
                return True
            
            error_output = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            self.add_log_entry(f"❌ Token Data Viewer update failed: {error_output}", "error")
            messagebox.showerror(
                "Token Data Viewer Update Failed",
                f"The update_token_data_viewer.py script failed:\n\n{error_output}\n\n"
                "Existing CSV data will be reused."
            )
            return viewer_exists
        except Exception as e:
            self.add_log_entry(f"❌ Failed to refresh Token Data Viewer: {e}", "error")
            return False
    
    def load_csv_data(self, force_refresh: bool = False):
        """Load and display data from CSV file (preferred), else webhook cache, else risk_report.csv files"""
        try:
            import pandas as pd
            import os
            import requests
            import json
            
            # Rebuild token_data_viewer.csv if tokens.csv is newer
            viewer_ready = self.ensure_token_data_viewer_current(force_rebuild=force_refresh)
            
            # PRIORITY 1: Try to load from token_data_viewer.csv first (only real data, no estimates)
            token_data_viewer_path = os.path.join(DATA_DIR, 'token_data_viewer.csv')
            if viewer_ready and os.path.exists(token_data_viewer_path):
                print(f"      📁 Loading Token Data Viewer cache (real data, no estimates)")
                df = pd.read_csv(
                    token_data_viewer_path,
                    keep_default_na=False,
                    na_values=[''],
                )
                print(f"      ✅ Loaded {len(df)} tokens from Token Data Viewer cache")
                
                # Clear existing data
                for item in self.data_tree.get_children():
                    self.data_tree.delete(item)
                
                # Display rows exactly as stored (already formatted)
                for index, row in df.iterrows():
                    try:
                        token = str(row.get('Token', 'Unknown'))
                        symbol = str(row.get('Symbol', 'Unknown'))
                        chain = str(row.get('Chain', 'ethereum'))
                        
                        def normalize(value, default='N/A'):
                            if value is None:
                                return default
                            value_str = str(value)
                            if value_str.strip() == '' or value_str.lower() == 'nan':
                                return default
                            return value_str
                        
                        market_cap = normalize(row.get('Market Cap'))
                        volume_24h = normalize(row.get('Volume 24h'))
                        holders = normalize(row.get('Holders'))
                        liquidity = normalize(row.get('Liquidity'))
                        
                        self.data_tree.insert(
                            '',
                            'end',
                            values=(token, symbol, chain, market_cap, volume_24h, holders, liquidity),
                        )
                    except Exception as row_err:
                        print(f"      ❌ Error displaying row {index}: {row_err}")
                        continue
                
                print(f"      ✅ Successfully loaded {len(df)} tokens with real data")
                messagebox.showinfo("Success", f"Loaded {len(df)} tokens with real data")
                return
            
            # PRIORITY 2: Try to load from tokens.csv (legacy support)
            tokens_csv_path = os.path.join(DATA_DIR, 'tokens.csv')
            if os.path.exists(tokens_csv_path):
                print(f"      📁 Loading from tokens.csv file")
                df = pd.read_csv(tokens_csv_path)
                print(f"      ✅ Loaded {len(df)} tokens from tokens.csv")
                
                # Clear existing data
                for item in self.data_tree.get_children():
                    self.data_tree.delete(item)
                
                # Process CSV data
                self.process_csv_data(df)
                return
            
            # PRIORITY 3: Try to use webhook cache data if CSV not available
            try:
                # Get cache status from webhook server
                response = requests.get(
                    f'{WEBHOOK_BASE_URL}/webhook/status',
                    timeout=5,
                    headers=_webhook_headers(),
                )
                if response.status_code == 200:
                    cache_status = response.json()
                    cache_age_hours = cache_status.get('cache_age_hours', 0)
                    cache_tokens = cache_status.get('cache_tokens', 0)
                    
                    print(f"      📦 Webhook cache status: {cache_age_hours:.1f}h old, {cache_tokens} tokens")
                    
                    # Try to get the actual cache data
                    cache_response = requests.get(
                        f'{WEBHOOK_BASE_URL}/webhook/cache',
                        timeout=10,
                        headers=_webhook_headers(),
                    )
                    if cache_response.status_code == 200:
                        cache_data = cache_response.json()
                        print(f"      ✅ Successfully loaded webhook cache data")
                        print(f"      📊 Cache contains {len(cache_data.get('tokens', {}))} tokens")
                        
                        # Clear existing data
                        for item in self.data_tree.get_children():
                            self.data_tree.delete(item)
                        
                        # Process cache data
                        self.process_webhook_cache_data(cache_data)
                        return
                    else:
                        print(f"      ⚠️ Could not retrieve webhook cache data")
                else:
                    print(f"      ⚠️ Could not connect to webhook server")
            except Exception as e:
                print(f"      ⚠️ Error accessing webhook cache: {e}")
            
            # PRIORITY 4: Fallback to token_fallbacks.json if webhook cache is not available
            print(f"      📁 Falling back to token_fallbacks.json")
            if self.render_fallback_file():
                print("      ✅ Loaded Token Data Viewer from token_fallbacks.json")
                return
            
            # PRIORITY 5: Final fallback to risk_report.csv files
            print(f"      📁 Final fallback to risk_report.csv files")
            
            # Find the most recent CSV file
            csv_files = []
            for file in os.listdir(DATA_DIR):
                if file.endswith('.csv') and 'risk_report' in file:
                    file_path = os.path.join(DATA_DIR, file)
                    csv_files.append((file_path, os.path.getmtime(file_path)))
            
            if not csv_files:
                messagebox.showwarning("No Data", "No risk assessment CSV files found in data directory.")
                return
            
            # Sort by modification time (newest first)
            csv_files.sort(key=lambda x: x[1], reverse=True)
            csv_file = csv_files[0][0]
            
            print(f"      📁 Loading CSV: {csv_file}")
            
            df = pd.read_csv(csv_file)
            print(f"      ✅ Loaded {len(df)} tokens from CSV")
            
            # Clear existing data
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
            
            # Prepare to collect token data for caching
            token_data_cache = {}
            
            # Process each row - SIMPLE APPROACH
            for index, row in df.iterrows():
                try:
                    # Extract basic info from CSV
                    token_address = row.get('token_address', '')
                    chain = row.get('chain', 'ethereum')
                    symbol = row.get('symbol', 'Unknown')
                    token_name = row.get('name', 'Unknown Token')
                    
                    # Fix token names using address mapping
                    address_mappings = {
                        '0x3845badade8e6dff049820680d1f14bd3903a5d0': 'The Sandbox',
                        '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': 'Aave',
                        '0x3506424f91fd33084466f402d5d97f05f8e3b4af': 'Chiliz',
                        '0xc00e94cb662c3520282e6f5717214004a7f26888': 'Compound',
                        '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USD Coin',
                        '0xdac17f958d2ee523a2206206994597c13d831ec7': 'Tether USD',
                        '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': 'Wrapped Bitcoin',
                        '0x514910771af9ca656af840dff83e8264ecf986ca': 'Chainlink',
                        '0x111111111117dc0aa78b770fa6a738034120c302': '1inch',
                        '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6': 'Polygon',
                        '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'Uniswap',
                        '0x6b175474e89094c44da98b954eedeac495271d0f': 'Dai',
                        '0xc944e90c64b2c07662a292be6244bdf05cda44a7': 'The Graph',
                        '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2': 'Maker',
                        '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2': 'SushiSwap',
                        '0xd1d2eb1b1e90b638588728b4130137d262c87cae': 'Gala Games',
                        '0x4a220e6096b25eadb88358cb44068a3248254675': 'Quant',
                        '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': 'Decentraland',
                        '0x0d8775f648430679a709e98d2b0cb6250d2887ef': 'Basic Attention Token',
                        '0x4200000000000000000000000000000000000042': 'Optimism',
                        '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRON'
                    }
                    
                    # Fix symbol mappings
                    symbol_mappings = {
                        '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': 'AAVE',
                        '0x3506424f91fd33084466f402d5d97f05f8e3b4af': 'CHZ',
                        '0xc00e94cb662c3520282e6f5717214004a7f26888': 'COMP',
                        '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',
                        '0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT',
                        '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': 'WBTC',
                        '0x514910771af9ca656af840dff83e8264ecf986ca': 'LINK',
                        '0x111111111117dc0aa78b770fa6a738034120c302': '1INCH',
                        '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6': 'POL',
                        '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'UNI',
                        '0x6b175474e89094c44da98b954eedeac495271d0f': 'DAI',
                        '0xc944e90c64b2c07662a292be6244bdf05cda44a7': 'GRT',
                        '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2': 'MKR',
                        '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2': 'SUSHI',
                        '0xd1d2eb1b1e90b638588728b4130137d262c87cae': 'GALA',
                        '0x4a220e6096b25eadb88358cb44068a3248254675': 'QNT',
                        '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': 'MANA',
                        '0x0d8775f648430679a709e98d2b0cb6250d2887ef': 'BAT',
                        '0x4200000000000000000000000000000000000042': 'OP',
                        '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRX'
                    }
                    
                    # Fix token name and symbol using external mappings
                    if token_address:
                        token_name = get_token_name(token_address)
                        symbol = get_token_symbol(token_address)
                        if token_name != 'Unknown Token':
                            print(f"      ✅ Fixed token name: {token_name}")
                        if symbol != 'Unknown':
                            print(f"      ✅ Fixed symbol: {symbol}")
                    
                    # Special SAND token fix
                    if token_address and '3845bad' in token_address.lower():
                        symbol = 'SAND'
                        token_name = 'The Sandbox'
                        print(f"      ✅ SAND token corrected: {token_address} -> SAND")
                    
                    # Additional token name fixes for specific tokens
                    if token_name == 'Unknown Token' and token_address:
                        additional_names = {
                            '0x4200000000000000000000000000000000000042': 'Optimism',
                            '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRON',
                            '0xd1d2eb1b1e90b638588728b4130137d262c87cae': 'Gala Games',
                            '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': 'Decentraland',
                            '0x4a220e6096b25eadb88358cb44068a3248254675': 'Quant',
                            '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6': 'Polygon',
                            '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'Uniswap'
                        }
                        if token_address.lower() in additional_names:
                            token_name = additional_names[token_address.lower()]
                            print(f"      🔍 Token name corrected: {token_address} -> {token_name}")
                    
                    # Additional symbol fixes for specific tokens
                    if symbol == 'Unknown' and token_address:
                        additional_symbols = {
                            '0x4200000000000000000000000000000000000042': 'OP',
                            '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRX',
                            '0xd1d2eb1b1e90b638588728b4130137d262c87cae': 'GALA',
                            '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': 'MANA',
                            '0x4a220e6096b25eadb88358cb44068a3248254675': 'QNT',
                            '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6': 'POL',
                            '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'UNI'
                        }
                        if token_address.lower() in additional_symbols:
                            symbol = additional_symbols[token_address.lower()]
                            print(f"      🔍 Symbol corrected: {token_address} -> {symbol}")
                    
                    # Simple data extraction - just get what's in the CSV
                    market_cap = 0
                    volume_24h = 0
                    holders = 0
                    liquidity = 0
                    
                    # Try to get real-time data for this token
                    try:
                        real_data = self._get_real_token_data(token_address, symbol)
                    except TypeError as e:
                        print(f"      ⚠️  Method call error for {symbol}: {e}")
                        real_data = None
                    
                    # Initialize with cached data first
                    cached_data = self._get_cached_market_data(symbol)
                    if cached_data:
                        market_cap = cached_data.get('market_cap', 0)
                        volume_24h = cached_data.get('volume_24h', 0)
                        holders = cached_data.get('holders', 0)
                        liquidity = cached_data.get('liquidity', 0)
                        print(f"      📦 Using cached data for {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
                    
                    # Override with real-time data if available
                    if real_data and isinstance(real_data, dict):
                        if real_data.get('market_cap', 0) > 0:
                            market_cap = real_data.get('market_cap', 0)
                        if real_data.get('volume_24h', 0) > 0:
                            volume_24h = real_data.get('volume_24h', 0)
                        if real_data.get('holders', 0) > 0:
                            holders = real_data.get('holders', 0)
                        if real_data.get('liquidity', 0) > 0:
                            liquidity = real_data.get('liquidity', 0)
                        print(f"      ✅ Updated with real-time data for {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
                    else:
                        print(f"      ⚠️  No real-time data for {symbol}, using cached data")
                    
                    # Check if stablecoin
                    is_stablecoin = self._is_stablecoin(symbol, token_name)
                    
                    # Extract optional risk fields if present in CSV
                    risk_score = row.get('risk_score', '')
                    risk_category = row.get('risk_category', '')

                    # Insert into tree (standardized 10-column format)
                    formatted_values = (
                        token_name,             # Token
                        symbol,                 # Symbol
                        chain,                  # Chain
                        self._format_number(market_cap, is_currency=True),   # Market Cap
                        self._format_number(volume_24h, is_currency=True),   # Volume 24h
                        self._format_number(holders, is_currency=False),     # Holders
                        self._format_number(liquidity, is_currency=True)     # Liquidity
                    )
                    
                    self.data_tree.insert('', 'end', values=formatted_values)
                    
                except Exception as e:
                    print(f"      ❌ Error processing row {index}: {e}")
                    continue
            
            print(f"      ✅ Successfully loaded {len(df)} tokens with real-time data")
            
            # Save cache if we fetched new data
            if token_data_cache:
                self.save_cache(token_data_cache)
            
            messagebox.showinfo("Success", f"Loaded {len(df)} tokens from {os.path.basename(csv_file)}")
            
        except Exception as e:
            print(f"      ❌ Error loading CSV: {e}")
            messagebox.showerror("Error", f"Failed to load CSV file: {e}")

    def process_csv_data(self, df):
        """Process CSV data and display in the dashboard"""
        try:
            print(f"      📊 Processing {len(df)} tokens from CSV")
            
            # Process each row from CSV
            for index, row in df.iterrows():
                try:
                    # Extract basic info from CSV
                    token_address = row.get('address', '')
                    chain = row.get('chain', 'ethereum')
                    symbol = row.get('symbol', 'Unknown')
                    token_name = row.get('name', 'Unknown Token')
                    
                    # Get market data from cache or real-time sources
                    market_cap = 0
                    volume_24h = 0
                    holders = 0
                    liquidity = 0
                    
                    # Try to get real-time data for this token first
                    try:
                        real_data = self._get_real_token_data(token_address, symbol)
                        if real_data:
                            # Only use real data if it's not estimated/fallback values
                            if real_data.get('market_cap', 0) > 0 and real_data.get('market_cap', 0) < 1e12:  # Reasonable market cap range
                                market_cap = real_data.get('market_cap', 0)
                            if real_data.get('volume_24h', 0) > 0 and real_data.get('volume_24h', 0) < 1e12:  # Reasonable volume range
                                volume_24h = real_data.get('volume_24h', 0)
                            if real_data.get('holders', 0) > 0 and real_data.get('holders', 0) < 1e8:  # Reasonable holder count
                                holders = real_data.get('holders', 0)
                            if real_data.get('liquidity', 0) > 0:
                                liquidity = real_data.get('liquidity', 0)
                            print(f"      ✅ Using real-time data for {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
                    except Exception as e:
                        print(f"      ⚠️ Error getting real-time data for {symbol}: {e}")
                    
                    # Only use cached data if no real-time data available and it's not estimated values
                    if market_cap == 0:
                        cached_data = self._get_cached_market_data(symbol)
                        if cached_data:
                            # Check if cached data looks like real data (not estimated)
                            cached_mc = cached_data.get('market_cap', 0)
                            cached_vol = cached_data.get('volume_24h', 0)
                            cached_holders = cached_data.get('holders', 0)
                            cached_liquidity = cached_data.get('liquidity', 0)
                            
                            # Only use cached data if it doesn't look like estimated values
                            if cached_mc > 0 and cached_mc < 1e12:  # Reasonable market cap
                                market_cap = cached_mc
                            if cached_vol > 0 and cached_vol < 1e12:  # Reasonable volume
                                volume_24h = cached_vol
                            if cached_holders > 0 and cached_holders < 1e8:  # Reasonable holder count
                                holders = cached_holders
                            if cached_liquidity > 0:
                                liquidity = cached_liquidity
                            
                            if market_cap > 0 or volume_24h > 0 or holders > 0 or liquidity > 0:
                                print(f"      📦 Using cached data for {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
                            else:
                                print(f"      ⚠️ Cached data for {symbol} appears to be estimated values, skipping")
                    
                    # Add to tree view with correct column order: Token, Symbol, Chain, Market Cap, Volume 24h, Holders, Liquidity
                    self.data_tree.insert('', 'end', values=(
                        token_name,  # Token
                        symbol,      # Symbol
                        chain,       # Chain
                        f"${market_cap:,.0f}" if market_cap > 0 else "N/A",  # Market Cap
                        f"${volume_24h:,.0f}" if volume_24h > 0 else "N/A",    # Volume 24h
                        f"{holders:,}" if holders > 0 else "N/A",              # Holders
                        f"${liquidity:,.0f}" if liquidity > 0 else "N/A"       # Liquidity
                    ))
                    
                    print(f"      ✅ Added {symbol} ({token_name}) to dashboard")
                    
                except Exception as e:
                    print(f"      ❌ Error processing row {index}: {e}")
                    continue
            
            print(f"      ✅ Successfully processed {len(df)} tokens from CSV")
            
        except Exception as e:
            print(f"      ❌ Error processing CSV data: {e}")
            messagebox.showerror("Error", f"Failed to process CSV data: {e}")

    def process_webhook_cache_data(self, cache_data):
        """Process webhook cache data and display in the dashboard"""
        try:
            tokens = cache_data.get('tokens', {})
            fallback_data = cache_data.get('fallback_data', {})
            symbol_cache = cache_data.get('symbol_cache', {})
            
            print(f"      📊 Processing {len(tokens)} tokens from webhook cache")
            
            # Process each token in the cache
            for token_address, token_info in tokens.items():
                try:
                    # Extract basic info from multiple possible sources
                    # PRIORITY 1: Use top-level symbol from webhook cache (most reliable)
                    symbol = token_info.get('symbol', 'Unknown')
                    token_name = token_info.get('name', 'Unknown Token')
                    
                    # If webhook cache has a valid symbol, use it and get name from token mappings
                    if symbol != 'Unknown':
                        # Get the proper name from token mappings if available
                        mapped_name = get_token_name(token_address)
                        if mapped_name != 'Unknown Token':
                            token_name = mapped_name
                        print(f"      🔄 Using webhook cache symbol for {token_address}: {symbol} - {token_name}")
                    else:
                        # PRIORITY 2: Try to get symbol and name from liquidity_data.alchemy
                        liquidity_data = token_info.get('liquidity_data', {})
                        if 'alchemy' in liquidity_data and isinstance(liquidity_data['alchemy'], dict):
                            symbol = liquidity_data['alchemy'].get('symbol', 'Unknown')
                            token_name = liquidity_data['alchemy'].get('name', 'Unknown Token')
                        
                        # PRIORITY 3: If still unknown, try onchain_data sources
                        if symbol == 'Unknown':
                            onchain_data = token_info.get('onchain_data', {})
                            for source, data in onchain_data.items():
                                if isinstance(data, dict) and data.get('symbol'):
                                    symbol = data.get('symbol', 'Unknown')
                                    token_name = data.get('name', 'Unknown Token')
                                    break
                        
                        # PRIORITY 4: Final fallback - use token mappings
                        if symbol == 'Unknown' or token_name == 'Unknown Token':
                            symbol = get_token_symbol(token_address)
                            token_name = get_token_name(token_address)
                            print(f"      🔄 Using token mappings for {token_address}: {symbol} - {token_name}")
                    
                    # Get market data from cache - use top-level fields first
                    market_cap = token_info.get('market_cap', 0)
                    volume_24h = token_info.get('volume_24h', 0)
                    holders = token_info.get('holders', 0)
                    liquidity = token_info.get('liquidity', 0)
                    
                    # If top-level fields are 0, try to extract from nested structure
                    if market_cap == 0 or volume_24h == 0:
                        market_data = token_info.get('market_data', {})
                        if isinstance(market_data, dict):
                            for source, source_data in market_data.items():
                                if isinstance(source_data, dict):
                                    if market_cap == 0 and source_data.get('market_cap', 0) > 0:
                                        market_cap = source_data.get('market_cap', 0)
                                    if volume_24h == 0 and source_data.get('volume_24h', 0) > 0:
                                        volume_24h = source_data.get('volume_24h', 0)
                    
                    # If holders is 0, try to extract from nested structure
                    if holders == 0:
                        onchain_data = token_info.get('onchain_data', {})
                        if isinstance(onchain_data, dict):
                            for source, source_data in onchain_data.items():
                                if isinstance(source_data, dict) and source_data.get('holders', 0) > 0:
                                    holders = source_data.get('holders', 0)
                                    break
                    
                    # If liquidity is 0, try to extract from nested structure
                    if liquidity == 0:
                        liquidity_data = token_info.get('liquidity_data', {})
                        if isinstance(liquidity_data, dict):
                            for source, source_data in liquidity_data.items():
                                if isinstance(source_data, dict) and source_data.get('liquidity_score', 0) > 0:
                                    liquidity = source_data.get('liquidity_score', 0)
                                    break
                    
                    price = 0
                    aggregates = token_info.get('aggregates', {}) if isinstance(token_info, dict) else {}
                    
                    # Prefer aggregated market values if present
                    try:
                        if isinstance(aggregates, dict) and 'market' in aggregates:
                            agg_market = aggregates.get('market', {})
                            mc = agg_market.get('market_cap', 0)
                            vol = agg_market.get('volume_24h', 0)
                            if isinstance(mc, (int, float)) and mc > 0:
                                market_cap = mc
                            if isinstance(vol, (int, float)) and vol > 0:
                                volume_24h = vol
                    except Exception:
                        pass
                    # Try to get market cap and volume from various sources if aggregates missing
                    if market_cap == 0 or volume_24h == 0:
                        for source, data in market_data.items():
                            if isinstance(data, dict):
                                if market_cap == 0 and data.get('market_cap', 0) > 0:
                                    market_cap = data.get('market_cap', 0)
                                if volume_24h == 0 and data.get('volume_24h', 0) > 0:
                                    volume_24h = data.get('volume_24h', 0)
                                if data.get('price', 0) > 0:
                                    price = data.get('price', 0)
                    
                    # Only use real data - no fallback market data
                    if market_cap == 0:
                        print(f"      💧 {symbol} no real market data available - showing 0")
                    if volume_24h == 0:
                        print(f"      💧 {symbol} no real volume data available - showing 0")
                    
                    # Check if we have real liquidity data
                    real_liquidity_found = liquidity > 0
                    # If fallback contains multiple non-zero values for liquidity, average them
                    try:
                        fb = fallback_data.get(token_address, {}) if isinstance(fallback_data, dict) else {}
                        hist = fb.get('history', {}).get('liquidity', []) if isinstance(fb, dict) else []
                        if hist and isinstance(hist, list):
                            vals: list[float] = []
                            for h in hist:
                                if isinstance(h, dict):
                                    v = h.get('value')
                                    if isinstance(v, (int, float)) and v > 0:
                                        vals.append(float(v))
                            if len(vals) >= 2:
                                avg_l = sum(vals) / len(vals)
                                if avg_l > 0:
                                    liquidity = avg_l
                                    real_liquidity_found = True
                    except Exception:
                        pass
                    
                    # If no real liquidity data, show 0 (honest)
                    if not real_liquidity_found:
                        print(f"      💧 {symbol} no real liquidity data available - showing 0")
                    
                    # Check if stablecoin
                    is_stablecoin = self._is_stablecoin(symbol, token_name)
                    
                    # Determine the correct chain
                    chain = self._get_token_chain(token_address, token_info)
                    
                    # Debug logging for first few tokens
                    if len(self.data_tree.get_children()) < 3:
                        print(f"      🔍 {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,.0f}, Liq=${liquidity:,.0f}, Chain={chain}")
                    
                    # Insert into tree using the exact Token Data Viewer columns
                    formatted_values = (
                        token_name,
                        symbol,
                        chain,
                        self._format_number(market_cap, is_currency=True),
                        self._format_number(volume_24h, is_currency=True),
                        self._format_number(holders, is_currency=False),
                        self._format_number(liquidity, is_currency=True)
                    )
                    
                    self.data_tree.insert('', 'end', values=formatted_values)
                    
                except Exception as e:
                    print(f"      ❌ Error processing token {token_address}: {e}")
                    continue
            
            print(f"      ✅ Successfully processed {len(tokens)} tokens from webhook cache")
            messagebox.showinfo("Success", f"Loaded {len(tokens)} tokens from webhook cache")
            
        except Exception as e:
            print(f"      ❌ Error processing webhook cache data: {e}")
            messagebox.showerror("Error", f"Failed to process webhook cache data: {e}")

    def render_fallback_file(self) -> bool:
        """Load data from data/token_fallbacks.json and render into the Token Data Viewer.
        Returns True if data was loaded and rendered, else False.
        """
        try:
            fallback_path = os.path.join(DATA_DIR, 'token_fallbacks.json')
            if not os.path.exists(fallback_path):
                return False
            with open(fallback_path, 'r') as f:
                fb = json.load(f)
            token_map = fb.get('token_mappings', {})
            if not isinstance(token_map, dict) or not token_map:
                return False
            
            # Check if any token has comprehensive data (market cap + volume + liquidity) - if not, skip fallback file
            has_comprehensive_data = False
            for token_address, data in token_map.items():
                if isinstance(data, dict):
                    # Check for comprehensive data: market cap, volume, and liquidity
                    has_market_cap = False
                    has_volume = False
                    has_liquidity = False
                    
                    # Check market data
                    market_data = data.get('market_data', {})
                    if isinstance(market_data, dict):
                        for source, source_data in market_data.items():
                            if isinstance(source_data, dict):
                                if source_data.get('market_cap', 0) > 0:
                                    has_market_cap = True
                                if source_data.get('volume_24h', 0) > 0:
                                    has_volume = True
                    
                    # Check liquidity data
                    liquidity_data = data.get('liquidity_data', {})
                    if isinstance(liquidity_data, dict):
                        for source, source_data in liquidity_data.items():
                            if isinstance(source_data, dict) and source_data.get('liquidity_score', 0) > 0:
                                has_liquidity = True
                                break
                    
                    # Also check for top-level fields
                    if data.get('liquidity', 0) > 0:
                        has_liquidity = True
                    
                    # Only consider it comprehensive if it has at least 2 out of 3 data types
                    if sum([has_market_cap, has_volume, has_liquidity]) >= 2:
                        has_comprehensive_data = True
                        break
            
            # If no comprehensive data found, skip fallback file and try webhook cache
            if not has_comprehensive_data:
                print("      💧 Fallback file has insufficient data - trying webhook cache instead")
                return False
            # Clear existing rows
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
            # Render rows
            for token_address, data in token_map.items():
                try:
                    name = data.get('name') or get_token_name(token_address) or 'Unknown Token'
                    symbol = data.get('symbol') or get_token_symbol(token_address) or 'Unknown'
                    
                    # Extract market data from nested structure
                    mc = 0
                    vol = 0
                    market_data = data.get('market_data', {})
                    if isinstance(market_data, dict):
                        for source, source_data in market_data.items():
                            if isinstance(source_data, dict):
                                if mc == 0 and source_data.get('market_cap', 0) > 0:
                                    mc = source_data.get('market_cap', 0)
                                if vol == 0 and source_data.get('volume_24h', 0) > 0:
                                    vol = source_data.get('volume_24h', 0)
                    
                    # Extract holders from nested structure
                    holders = 0
                    onchain_data = data.get('onchain_data', {})
                    if isinstance(onchain_data, dict):
                        for source, source_data in onchain_data.items():
                            if isinstance(source_data, dict) and source_data.get('holders', 0) > 0:
                                holders = source_data.get('holders', 0)
                                print(f"      🔍 Found holders for {symbol}: {holders} from {source}")
                                break
                    
                    # Extract liquidity from nested structure
                    liq = 0
                    liquidity_data = data.get('liquidity_data', {})
                    if isinstance(liquidity_data, dict):
                        for source, source_data in liquidity_data.items():
                            if isinstance(source_data, dict) and source_data.get('liquidity_score', 0) > 0:
                                liq = source_data.get('liquidity_score', 0)
                                break
                    # Average liquidity from history if >1 non-zero datapoints exist
                    history_data = data.get('history')
                    hist = []
                    if isinstance(history_data, dict):
                        hist = history_data.get('liquidity', []) or []
                    if isinstance(hist, list) and hist:
                        vals: list[float] = []
                        for h in hist:
                            if isinstance(h, dict):
                                v = h.get('value')
                                if isinstance(v, (int, float)) and v > 0:
                                    vals.append(float(v))
                        if len(vals) >= 2:
                            avg = sum(vals) / len(vals)
                            if avg > 0:
                                liq = avg
                    chain = data.get('chain') or self._get_token_chain(token_address, {})
                    formatted = (
                        name,
                        symbol,
                        chain,
                        self._format_number(mc, is_currency=True),
                        self._format_number(vol, is_currency=True),
                        self._format_number(holders, is_currency=False),
                        self._format_number(liq, is_currency=True)
                    )
                    self.data_tree.insert('', 'end', values=formatted)
                except Exception:
                    continue
            return True
        except Exception as e:
            print(f"      ❌ Error rendering fallback file: {e}")
            return False
    
    def _get_fallback_market_data(self, symbol):
        """Get fallback market data from webhook cache"""
        try:
            # Try to get fallback data from webhook cache
            fallback_file = 'fallback_data.json'
            if os.path.exists(fallback_file):
                with open(fallback_file, 'r') as f:
                    fallback_data = json.load(f)
                
                # Find token by symbol in fallback data
                for token_address, data in fallback_data.get('token_mappings', {}).items():
                    if data.get('symbol', '').upper() == symbol.upper():
                        return {
                            'market_cap': data.get('market_cap', 0),
                            'volume_24h': data.get('volume_24h', 0),
                            'liquidity': data.get('liquidity', 0)
                        }
        except Exception as e:
            print(f"      ❌ Error reading fallback data: {e}")
        
        return None
    

    
    def _get_token_chain(self, token_address, token_info):
        """Determine the correct blockchain for a token"""
        try:
            # Check for L2 tokens first
            if token_address.lower() == '0x4200000000000000000000000000000000000042':
                return 'optimism'  # OP token
            
            # Check onchain_data sources for chain information
            onchain_data = token_info.get('onchain_data', {})
            for source, data in onchain_data.items():
                if source == 'optimism':
                    return 'optimism'
                elif source == 'polygon':
                    return 'polygon'
                elif source == 'arbitrum':
                    return 'arbitrum'
                elif source == 'bsc':
                    return 'bsc'
            
            # Check token name for chain hints
            token_name = ''
            liquidity_data = token_info.get('liquidity_data', {})
            if 'alchemy' in liquidity_data and isinstance(liquidity_data['alchemy'], dict):
                token_name = liquidity_data['alchemy'].get('name', '')
            
            # Extract symbol from token_info
            symbol = token_info.get('symbol', '')
            
            if 'POL (ex-MATIC)' in token_name:
                return 'polygon'  # POL is the rebranded MATIC on Polygon
            elif 'Optimism' in token_name:
                return 'optimism'
            elif 'Sonic' in token_name:
                return 's-chain'  # Sonic is on S Chain
            elif symbol == 'SONIC':
                return 's-chain'  # SONIC token is on S Chain
            
            # Default to ethereum for most tokens
            return 'ethereum'
            
        except Exception as e:
            print(f"      ⚠️ Error determining chain for {token_address}: {e}")
            return 'ethereum'
    
    def load_excel_data(self):
        """Load and display data from Excel file with enhanced real-time data integration"""
        # Ensure we're on the main thread for GUI operations
        import threading
        if threading.current_thread() is not threading.main_thread():
            # Schedule on main thread
            self.root.after(0, self.load_excel_data)
            return
        
        # Create error log file for debugging
        import os
        from datetime import datetime
        error_log_file = os.path.join(DATA_DIR, 'excel_load_errors.log')
        
        def log_error(msg):
            """Log error to both console and file"""
            print(msg)
            try:
                with open(error_log_file, 'a') as f:
                    f.write(f"{datetime.now().isoformat()}: {msg}\n")
            except:
                pass
        
        try:
            # Clear previous error log
            try:
                with open(error_log_file, 'w') as f:
                    f.write(f"Excel Load Error Log - {datetime.now().isoformat()}\n")
                    f.write("=" * 60 + "\n")
            except:
                pass
            
            # Log start
            self.add_log_entry("📊 Loading Excel data...", "info")
            log_error("Starting Excel data load...")
            import pandas as pd
            import os
            
            # Find the most recent Excel file in DATA_DIR and risk_reports subdirectory
            excel_files = []
            search_dirs = [
                DATA_DIR,
                os.path.join(DATA_DIR, 'risk_reports')
            ]
            
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                try:
                    for file in os.listdir(search_dir):
                        # Skip temporary lock files (starting with ~$)
                        if file.startswith('~$'):
                            continue
                        if file.endswith('.xlsx') and 'Risk Assessment Results' in file:
                            file_path = os.path.join(search_dir, file)
                            # Verify it's actually a file and not a directory
                            if os.path.isfile(file_path):
                                excel_files.append((file_path, os.path.getmtime(file_path)))
                except PermissionError:
                    continue
                except Exception as e:
                    print(f"      ⚠️  Error scanning {search_dir}: {e}")
                    continue
            
            if not excel_files:
                messagebox.showwarning("No Data", "No risk assessment Excel files found in data directory.")
                return
            
            # Sort by modification time (newest first)
            excel_files.sort(key=lambda x: x[1], reverse=True)
            excel_file = excel_files[0][0]
            
            print(f"      📁 Loading Excel: {excel_file}")
            print(f"      📁 Full path: {os.path.abspath(excel_file)}")
            
            # Verify file exists and is readable
            if not os.path.exists(excel_file):
                raise FileNotFoundError(f"Excel file not found: {excel_file}")
            
            if not os.path.isfile(excel_file):
                raise ValueError(f"Path is not a file: {excel_file}")
            
            # Check file size (empty or corrupted files might cause issues)
            file_size = os.path.getsize(excel_file)
            if file_size == 0:
                raise ValueError(f"Excel file is empty: {excel_file}")
            
            print(f"      📊 File size: {file_size} bytes")
            
            # Try to read the Excel file with better error handling
            try:
                df = pd.read_excel(excel_file, engine='openpyxl')
            except Exception as e:
                error_msg = str(e).lower()
                # If openpyxl fails with zipfile error, the file might be corrupted or wrong format
                if 'zipfile' in error_msg or 'not a zip file' in error_msg or 'bad zipfile' in error_msg:
                    print(f"      ⚠️  openpyxl failed with zipfile error: {e}")
                    print(f"      🔍 Verifying file format...")
                    
                    # Check if file is actually an Excel file by reading first few bytes
                    try:
                        with open(excel_file, 'rb') as f:
                            header = f.read(4)
                            # Excel files should start with PK (ZIP signature)
                            if header[:2] != b'PK':
                                raise ValueError(f"File does not appear to be a valid Excel file. File header: {header.hex()}")
                            print(f"      ✅ File header looks valid: {header.hex()}")
                    except Exception as header_error:
                        raise Exception(f"File validation failed: {header_error}. Original error: {e}")
                    
                    # Try alternative reading methods
                    print(f"      🔄 Trying alternative reading methods...")
                    try:
                        # Try with xlrd engine (for older Excel formats)
                        try:
                            import xlrd  # type: ignore
                            df = pd.read_excel(excel_file, engine='xlrd')
                            print(f"      ✅ Successfully loaded with xlrd engine")
                        except ImportError:
                            print(f"      ⚠️  xlrd not available, trying without engine specification...")
                            # Last resort: try without specifying engine
                            df = pd.read_excel(excel_file)
                            print(f"      ✅ Successfully loaded without specifying engine")
                    except Exception as xlrd_error:
                        print(f"      ⚠️  Alternative methods also failed: {xlrd_error}")
                        raise Exception(f"Failed to read Excel file. File may be corrupted or in an unsupported format. Original error: {e}, Alternative error: {xlrd_error}")
                else:
                    # Other errors - just raise them
                    raise
            print(f"      ✅ Loaded {len(df)} tokens from Excel")
            
            # Verify data_tree exists
            if not hasattr(self, 'data_tree') or self.data_tree is None:
                raise AttributeError("data_tree is not initialized. Cannot insert data.")
            
            print(f"      ✅ data_tree is initialized: {self.data_tree}")
            print(f"      ✅ data_tree columns: {self.data_columns if hasattr(self, 'data_columns') else 'N/A'}")
            
            # Test tree insertion with a dummy row first
            try:
                test_values = ('TEST', 'TEST', 'test', '$0', '$0', '0', '$0')
                print(f"      🧪 Testing tree insertion with values: {test_values}")
                print(f"      🧪 Tree widget exists: {hasattr(self, 'data_tree')}")
                print(f"      🧪 Tree widget is None: {self.data_tree is None if hasattr(self, 'data_tree') else 'N/A'}")
                
                if not hasattr(self, 'data_tree') or self.data_tree is None:
                    raise AttributeError("data_tree attribute doesn't exist or is None")
                
                try:
                    # Check if widget is still alive
                    widget_exists = self.data_tree.winfo_exists()
                    print(f"      🧪 Tree widget exists check: {widget_exists}")
                    if not widget_exists:
                        raise AttributeError("Tree widget exists() returned False - widget may be destroyed")
                except tk.TclError as winfo_error:
                    error_msg = f"Tree widget winfo_exists() failed: {winfo_error}"
                    print(f"      ❌ {error_msg}")
                    self.add_log_entry(f"❌ {error_msg}", "error")
                    raise AttributeError(f"Tree widget is not accessible: {winfo_error}")
                
                # Try test insertion
                test_item = self.data_tree.insert('', 'end', values=test_values)
                if test_item:
                    self.data_tree.delete(test_item)
                    print(f"      ✅ Tree insertion test passed - tree is functional")
                    self.add_log_entry("✅ Tree insertion test passed", "success")
                else:
                    error_msg = "Tree insert returned None - tree may not be properly initialized"
                    print(f"      ⚠️  {error_msg}")
                    self.add_log_entry(f"❌ {error_msg}", "error")
                    raise Exception(error_msg)
            except tk.TclError as tcl_test_error:
                error_msg = f"Tree insertion test failed with TclError: {tcl_test_error}"
                print(f"      ❌ {error_msg}")
                import traceback
                print(f"      Traceback: {traceback.format_exc()}")
                # Log to status text as well
                self.add_log_entry(f"❌ {error_msg}", "error")
                raise Exception(f"Cannot insert into tree (TclError): {tcl_test_error}")
            except Exception as test_error:
                error_msg = f"Tree insertion test failed: {test_error}"
                print(f"      ❌ {error_msg}")
                import traceback
                print(f"      Traceback: {traceback.format_exc()}")
                # Log to status text as well
                self.add_log_entry(f"❌ {error_msg}", "error")
                raise Exception(f"Cannot insert into tree: {test_error}")
            
            # Clear existing data
            try:
                existing_items = self.data_tree.get_children()
                print(f"      🗑️  Clearing {len(existing_items)} existing items from tree...")
                for item in existing_items:
                    self.data_tree.delete(item)
                print(f"      ✅ Cleared existing data")
            except Exception as clear_error:
                print(f"      ⚠️  Error clearing tree: {clear_error}")
                # Continue anyway - might be empty already
            
            # Process each row with enhanced data integration
            rows_inserted = 0
            row_counter = 0
            errors_count = 0
            first_error = None  # Capture first error for display
            print(f"      📊 Processing {len(df)} rows from Excel file...")
            print(f"      📋 Available columns: {list(df.columns)}")
            print(f"      📋 Tree columns: {self.data_columns if hasattr(self, 'data_columns') else 'N/A'}")
            
            for index, row in df.iterrows():
                try:
                    row_counter += 1
                    
                    # Handle different column name formats
                    # Excel format: 'Token Name', 'Token Address', 'Symbol', 'Chain', 'Market Cap', 'Volume 24h', 'Holders', 'Liquidity'
                    # CSV format: token, chain, risk_score, risk_category, error
                    
                    # Extract token name - try Excel format first, then CSV format
                    token_name = (
                        self._safe_get_value(row, ['Token Name', 'token_name', 'name'], '') or
                        self._extract_token_name(row) or
                        'Unknown'
                    )
                    
                    # Extract symbol - try Excel format first, then CSV format
                    symbol = self._safe_get_value(row, ['Symbol', 'symbol'], 'Unknown')
                    
                    # Extract token address - try Excel format first, then CSV format
                    token_address = self._safe_get_value(row, ['Token Address', 'token_address', 'token'], '')
                    
                    # Extract chain - try Excel format first, then CSV format
                    chain = self._safe_get_value(row, ['Chain', 'chain'], 'ethereum')
                    
                    # Debug output for first row
                    if row_counter == 1:
                        print(f"      🔍 First row sample:")
                        print(f"         Token Name: {token_name}")
                        print(f"         Symbol: {symbol}")
                        print(f"         Token Address: {token_address}")
                        print(f"         Chain: {chain}")
                    
                    # Handle risk assessment CSV format (legacy support)
                    if not token_address and 'token' in str(row.index).lower():
                        token_address = row.get('token', '')
                        if not symbol or symbol == 'Unknown':
                            symbol = 'Unknown'  # Will be corrected by address mapping
                        # Try to get token name from address mapping
                        if token_address:
                            address_name_mappings = {
                                '0x3845badade8e6dff049820680d1f14bd3903a5d0': 'The Sandbox',
                                '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': 'Aave',
                                '0x3506424f91fd33084466f402d5d97f05f8e3b4af': 'Chiliz',
                                '0xc00e94cb662c3520282e6f5717214004a7f26888': 'Compound',
                                '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USD Coin',
                                '0xdac17f958d2ee523a2206206994597c13d831ec7': 'Tether',
                                '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': 'Wrapped Bitcoin',
                                '0x514910771af9ca656af840dff83e8264ecf986ca': 'Chainlink',
                                '0x111111111117dc0aa78b770fa6a738034120c302': '1inch',
                                '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6': 'Polygon',
                                '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'Uniswap',
                                '0x6b175474e89094c44da98b954eedeac495271d0f': 'Dai',
                                '0xc944e90c64b2c07662a292be6244bdf05cda44a7': 'The Graph',
                                '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2': 'Maker',
                                '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2': 'SushiSwap',
                                '0xd1d2eb1b1e90b638588728b4130137d262c87cae': 'Gala',
                                '0x4a220e6096b25eadb88358cb44068a3248254675': 'Quant',
                                '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': 'Decentraland',
                                '0x0d8775f648430679a709e98d2b0cb6250d2887ef': 'Basic Attention Token',
                                '0x4200000000000000000000000000000000000042': 'Optimism',
                                '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRON'
                            }
                            if token_address.lower() in address_name_mappings:
                                token_name = address_name_mappings[token_address.lower()]
                    
                    # Address-based symbol correction
                    if token_address:
                        # Special SAND token fix
                        if '3845bad' in token_address.lower():
                            symbol = 'SAND'
                            print(f"      ✅ SAND token corrected: {token_address} -> SAND")
                        else:
                            address_mappings = {
                                '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': 'AAVE',
                                '0x3506424f91fd33084466f402d5d97f05f8e3b4af': 'CHZ',
                                '0xc00e94cb662c3520282e6f5717214004a7f26888': 'COMP',
                                '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',
                                '0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT',
                                '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': 'WBTC',
                                '0x514910771af9ca656af840dff83e8264ecf986ca': 'LINK',
                                '0x111111111117dc0aa78b770fa6a738034120c302': '1INCH',
                                '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6': 'POL',
                                '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'UNI',
                                '0x6b175474e89094c44da98b954eedeac495271d0f': 'DAI',
                                '0xc944e90c64b2c07662a292be6244bdf05cda44a7': 'GRT',
                                '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2': 'MKR',
                                '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2': 'SUSHI',
                                '0xd1d2eb1b1e90b638588728b4130137d262c87cae': 'GALA',
                                '0x4a220e6096b25eadb88358cb44068a3248254675': 'QNT',
                                '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': 'MANA',
                                '0x0d8775f648430679a709e98d2b0cb6250d2887ef': 'BAT',
                                '0x4200000000000000000000000000000000000042': 'OP',
                                '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRX'
                            }
                            if token_address.lower() in address_mappings:
                                symbol = address_mappings[token_address.lower()]
                    
                    # Extract data from Excel columns (try Excel format first, then fallback)
                    # Excel format: 'Market Cap', 'Volume 24h', 'Holders', 'Liquidity'
                    market_cap = self._safe_get_value(row, ['Market Cap', 'market_cap', 'MarketCap'], 0)
                    volume_24h = self._safe_get_value(row, ['Volume 24h', 'volume_24h', 'Volume24h'], 0)
                    holders = self._safe_get_value(row, ['Holders', 'holders', 'holder_count'], 0)
                    liquidity = self._safe_get_value(row, ['Liquidity', 'liquidity', 'total_liquidity'], 0)
                    
                    # Initialize with cached data if Excel values are zero (skip for now to avoid errors)
                    # Commented out to avoid potential method errors blocking insertion
                    # if market_cap == 0 or volume_24h == 0 or holders == 0 or liquidity == 0:
                    #     try:
                    #         cached_data = self._get_cached_market_data(symbol)
                    #         if cached_data:
                    #             if market_cap == 0:
                    #                 market_cap = cached_data.get('market_cap', 0)
                    #             if volume_24h == 0:
                    #                 volume_24h = cached_data.get('volume_24h', 0)
                    #             if holders == 0:
                    #                 holders = cached_data.get('holders', 0)
                    #             if liquidity == 0:
                    #                 liquidity = cached_data.get('liquidity', 0)
                    #             print(f"      📦 Using cached data for {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
                    #     except Exception as cache_error:
                    #         print(f"      ⚠️  Cache lookup error for {symbol}: {cache_error}")
                    
                    # Fetch real-time data for this token (skip for now to avoid errors blocking insertion)
                    # Commented out to avoid potential method errors blocking insertion
                    # if market_cap == 0 or volume_24h == 0 or holders == 0 or liquidity == 0:
                    #     print(f"      🔍 Fetching real-time data for {symbol} ({token_address})")
                    #     try:
                    #         real_data = self._get_real_token_data(token_address, symbol)
                    #     except (TypeError, AttributeError) as e:
                    #         print(f"      ⚠️  Method call error for {symbol}: {e}")
                    #         real_data = {}
                    #     except Exception as e:
                    #         print(f"      ⚠️  Error fetching real-time data for {symbol}: {e}")
                    #         real_data = {}
                    #     
                    #     # Override with real-time data if available
                    #     if real_data and isinstance(real_data, dict):
                    #         if market_cap == 0 and real_data.get('market_cap', 0) > 0:
                    #             market_cap = real_data.get('market_cap', 0)
                    #         if volume_24h == 0 and real_data.get('volume_24h', 0) > 0:
                    #             volume_24h = real_data.get('volume_24h', 0)
                    #         if holders == 0 and real_data.get('holders', 0) > 0:
                    #             holders = real_data.get('holders', 0)
                    #         if liquidity == 0 and real_data.get('liquidity', 0) > 0:
                    #             liquidity = real_data.get('liquidity', 0)
                    #         print(f"      ✅ Updated with real-time data for {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
                    
                    # If still no data, try to extract from existing data structures (skip to avoid errors)
                    # Commented out to avoid potential method errors blocking insertion
                    # if market_cap == 0:
                    #     try:
                    #         market_cap = self._extract_market_data_enhanced(row).get('market_cap', 0)
                    #     except:
                    #         pass
                    # if volume_24h == 0:
                    #     try:
                    #         volume_24h = self._extract_market_data_enhanced(row).get('volume_24h', 0)
                    #     except:
                    #         pass
                    # if liquidity == 0:
                    #     try:
                    #         liquidity = self._extract_market_data_enhanced(row).get('liquidity', 0)
                    #     except:
                    #         pass
                    # if holders == 0:
                    #     try:
                    #         holders = self._extract_holders_fixed(row)
                    #     except:
                    #         pass
                    
                    # Extract other data
                    is_stablecoin = self._is_stablecoin(symbol, token_name)
                    risk_score = self._safe_get_value(row, ['Risk Score', 'risk_score', 'RiskScore'], 0)
                    risk_category = self._safe_get_value(row, ['Risk Category', 'risk_category', 'RiskCategory'], 'Unknown')
                    
                    # Debug: Print values before insertion
                    if row_counter <= 3:  # Print first 3 rows for debugging
                        print(f"      🔍 Row {row_counter} before insertion:")
                        print(f"         token_name={token_name}, symbol={symbol}, chain={chain}")
                        print(f"         market_cap={market_cap}, volume_24h={volume_24h}, holders={holders}, liquidity={liquidity}")
                    
                    # Insert into tree with exact Token Data Viewer column order
                    formatted_values = None
                    try:
                        # Prepare values for insertion
                        formatted_values = (
                            str(token_name) if token_name else 'Unknown',
                            str(symbol) if symbol else 'Unknown',
                            str(chain) if chain else 'ethereum',
                            self._format_number(market_cap, is_currency=True),
                            self._format_number(volume_24h, is_currency=True),
                            self._format_number(holders, is_currency=False),
                            self._format_number(liquidity, is_currency=True)
                        )
                        
                        # Verify we have the right number of values
                        expected_cols = len(self.data_columns) if hasattr(self, 'data_columns') else 7
                        if len(formatted_values) != expected_cols:
                            raise ValueError(f"Number of values ({len(formatted_values)}) doesn't match number of columns ({expected_cols})")
                        
                        # Verify all values are strings (treeview requires strings)
                        formatted_values = tuple(str(v) if v is not None else '' for v in formatted_values)
                        
                        # Verify we have exactly 7 values for 7 columns
                        expected_cols = len(self.data_columns) if hasattr(self, 'data_columns') else 7
                        if len(formatted_values) != expected_cols:
                            raise ValueError(f"Column count mismatch: got {len(formatted_values)} values but tree expects {expected_cols} columns. Values: {formatted_values}")
                        
                        # Verify tree is still valid
                        if not hasattr(self, 'data_tree') or self.data_tree is None:
                            raise AttributeError("data_tree is None or doesn't exist")
                        
                        # Check if tree is still alive (not destroyed)
                        try:
                            widget_alive = self.data_tree.winfo_exists()
                            if not widget_alive:
                                raise AttributeError("data_tree widget has been destroyed")
                        except tk.TclError as winfo_err:
                            raise AttributeError(f"data_tree widget is not accessible: {winfo_err}")
                        
                        # Try to insert - this is the critical operation
                        # Double-check column configuration
                        try:
                            tree_cols = self.data_tree.cget('columns')
                            if tree_cols != self.data_columns:
                                print(f"      ⚠️  Warning: Tree columns {tree_cols} don't match expected {self.data_columns}")
                        except Exception as col_check_error:
                            print(f"      ⚠️  Could not check tree columns: {col_check_error}")
                        
                        # Final validation before insertion
                        if row_counter == 1:
                            print(f"      🔍 First row insertion attempt:")
                            print(f"         Formatted values: {formatted_values}")
                            print(f"         Values count: {len(formatted_values)}")
                            print(f"         Expected columns: {self.data_columns if hasattr(self, 'data_columns') else 'N/A'}")
                            print(f"         Expected count: {len(self.data_columns) if hasattr(self, 'data_columns') else 7}")
                        
                        item_id = self.data_tree.insert('', 'end', values=formatted_values)
                        
                        if item_id:
                            rows_inserted += 1
                            if row_counter <= 3:  # Print first 3 rows for debugging
                                print(f"      ✅ Inserted row {rows_inserted}: {token_name} ({symbol})")
                                print(f"         Item ID: {item_id}")
                                print(f"         Formatted values: {formatted_values}")
                        else:
                            raise ValueError("Tree insert returned None/empty item ID")
                            
                    except tk.TclError as tcl_error:
                        # Tkinter-specific error - most common issue
                        errors_count += 1
                        import traceback
                        error_msg = f"Tkinter error: {tcl_error}"
                        if first_error is None:
                            first_error = error_msg
                            # Log first error to status text, console, and file
                            log_msg = f"❌ Tkinter error inserting row: {tcl_error}"
                            self.add_log_entry(log_msg, "error")
                            log_error(f"FIRST ERROR - {log_msg}")
                            log_error(f"Full traceback:\n{traceback.format_exc()}")
                            print(f"      {log_msg}")
                            print(f"      Full traceback:")
                            print(f"      {traceback.format_exc()}")
                        log_error(f"Row {row_counter} Tkinter error: {tcl_error} | Token: {token_name} ({symbol})")
                        print(f"      ❌ Tkinter error inserting row {row_counter}: {tcl_error}")
                        print(f"         Token: {token_name} ({symbol})")
                        print(f"         Formatted values: {formatted_values}")
                        print(f"         This usually means the tree widget was destroyed or is not accessible")
                        # Force flush
                        import sys
                        sys.stdout.flush()
                        continue
                    except Exception as insert_error:
                        import traceback
                        errors_count += 1
                        error_msg = f"{type(insert_error).__name__}: {insert_error}"
                        if first_error is None:
                            first_error = error_msg
                            # Log first error to status text, console, and file
                            log_msg = f"❌ Error inserting row: {insert_error}"
                            self.add_log_entry(log_msg, "error")
                            log_error(f"FIRST ERROR - {log_msg}")
                            log_error(f"Full traceback:\n{traceback.format_exc()}")
                            print(f"      {log_msg}")
                            print(f"      Full traceback:")
                            print(f"      {traceback.format_exc()}")
                        log_error(f"Row {row_counter} error: {insert_error} | Token: {token_name} ({symbol}) | Values: {formatted_values}")
                        print(f"      ❌ Error inserting row {row_counter} into tree: {insert_error}")
                        print(f"         Error type: {type(insert_error).__name__}")
                        print(f"         Token: {token_name} ({symbol})")
                        print(f"         Values: name={token_name}, symbol={symbol}, chain={chain}, mc={market_cap}, vol={volume_24h}, holders={holders}, liq={liquidity}")
                        if formatted_values is not None:
                            print(f"         Formatted values: {formatted_values}")
                            print(f"         Formatted values count: {len(formatted_values)}")
                        print(f"         Expected columns count: {len(self.data_columns) if hasattr(self, 'data_columns') else 'N/A'}")
                        # Force flush
                        import sys
                        sys.stdout.flush()
                        continue
                    
                except Exception as e:
                    import traceback
                    errors_count += 1
                    error_msg = f"Error processing row {row_counter}: {e}"
                    print(f"      ❌ {error_msg}")
                    print(f"         Error type: {type(e).__name__}")
                    if errors_count <= 3:  # Show first 3 errors in detail
                        print(f"         Full traceback: {traceback.format_exc()}")
                    # Force flush to ensure error is visible
                    import sys
                    sys.stdout.flush()
                    continue
            
            print(f"      📊 Summary: Processed {row_counter} rows, inserted {rows_inserted} tokens, encountered {errors_count} errors")
            print(f"      ✅ Successfully loaded {rows_inserted} tokens (out of {len(df)} total rows)")
            
            if rows_inserted > 0:
                self.add_log_entry(f"✅ Loaded {rows_inserted} tokens from Excel", "success")
                messagebox.showinfo("Success", f"Loaded {rows_inserted} tokens from {os.path.basename(excel_file)}")
            else:
                error_msg = f"Excel file loaded but no tokens were inserted.\n\n"
                error_msg += f"Processed: {row_counter} rows\n"
                error_msg += f"Errors: {errors_count}\n\n"
                if first_error:
                    error_msg += f"First error: {first_error}\n\n"
                    # Log first error to status text for visibility
                    self.add_log_entry(f"❌ Excel load failed: {first_error}", "error")
                error_msg += f"Check System Status panel below for detailed error messages.\n"
                error_msg += f"Error log saved to: {error_log_file}"
                messagebox.showwarning("Warning", error_msg)
                log_error(f"Load completed with {errors_count} errors. First error: {first_error}")
                print(f"      ⚠️  No rows were inserted. This might indicate:")
                print(f"         1. All rows failed validation")
                print(f"         2. Tree insertion is failing")
                print(f"         3. Data extraction is returning empty values")
                if first_error:
                    print(f"         First error was: {first_error}")
                    self.add_log_entry(f"❌ Error details: {first_error}", "error")
                print(f"         Check the System Status panel and error messages above for details.")
                # Force flush all output
                import sys
                sys.stdout.flush()
            
        except Exception as e:
            print(f"      ❌ Error loading Excel: {e}")
            messagebox.showerror("Error", f"Failed to load Excel file: {e}")
    
    def refresh_data_view(self):
        """Refresh the data view"""
        try:
            # Refresh button must trigger a live CSV rebuild instead of loading whichever file is newest.
            # This avoids stale XLSX/token_fallback snapshots masking new on-chain holders.
            self.load_csv_data(force_refresh=True)
        except Exception as e:
            self.add_log_entry(f"❌ Refresh error: {e}", "error")

    def _normalize_sort_value(self, column_name, value):
        """Normalize table values for robust Treeview sorting."""
        text = str(value or '').strip()
        if not text or text.lower() in {'n/a', 'na', 'none', 'unknown', 'nan'}:
            return (1, None)

        numeric_columns = {'Market Cap', 'Volume 24h', 'Holders', 'Liquidity'}
        if column_name in numeric_columns:
            cleaned = (
                text.replace('$', '')
                .replace(',', '')
                .replace('%', '')
                .replace('B', 'e9')
                .replace('M', 'e6')
                .replace('K', 'e3')
                .strip()
            )
            try:
                return (0, float(cleaned))
            except ValueError:
                return (1, None)

        return (0, text.lower())

    def _refresh_data_tree_headings(self):
        """Refresh column headers and keep sort arrow indicator in sync."""
        for col in self.data_columns:
            label = col
            if col == self._data_sort_column:
                label = f"{col} {'↑' if self._data_sort_descending else '↓'}"
            self.data_tree.heading(col, text=label, command=lambda c=col: self.sort_data_tree_by_column(c))

    def sort_data_tree_by_column(self, column_name):
        """Sort Token Data Viewer by selected column with direction toggle."""
        try:
            if column_name not in self.data_columns:
                return

            # First click = ascending (A->Z / low->high), second click = descending.
            if self._data_sort_column == column_name:
                self._data_sort_descending = not self._data_sort_descending
            else:
                self._data_sort_column = column_name
                self._data_sort_descending = False

            col_index = self.data_columns.index(column_name)
            rows = []
            for item_id in self.data_tree.get_children(''):
                values = self.data_tree.item(item_id, 'values')
                cell_value = values[col_index] if col_index < len(values) else ''
                sort_key = self._normalize_sort_value(column_name, cell_value)
                rows.append((sort_key, item_id))

            rows.sort(key=lambda x: x[0], reverse=self._data_sort_descending)
            for new_index, (_, item_id) in enumerate(rows):
                self.data_tree.move(item_id, '', new_index)

            self._refresh_data_tree_headings()
            direction = "descending (Z→A)" if self._data_sort_descending else "ascending (A→Z)"
            self.add_log_entry(f"↕️ Sorted Token Data Viewer by {column_name} ({direction})", "info")
        except Exception as e:
            self.add_log_entry(f"❌ Sort error on {column_name}: {e}", "error")
    
    def _safe_get_value(self, row, possible_keys, default=None):
        """Safely get value from row trying multiple possible key names"""
        import pandas as pd
        
        # Handle pandas Series (from df.iterrows())
        if hasattr(row, 'index') and hasattr(row, '__getitem__'):
            # It's a pandas Series
            for key in possible_keys:
                try:
                    if key in row.index:
                        value = row[key]
                        # Handle pandas NaN values
                        if pd.isna(value):
                            continue
                        # Convert numpy types to Python types
                        if hasattr(value, 'item'):
                            try:
                                value = value.item()
                            except (ValueError, AttributeError):
                                pass
                        return value
                except (KeyError, IndexError):
                    continue
        else:
            # It's a regular dict
            for key in possible_keys:
                try:
                    if key in row:
                        value = row.get(key, default)
                        # Handle pandas NaN values
                        if pd.isna(value):
                            continue
                        # Convert numpy types to Python types
                        if hasattr(value, 'item'):
                            try:
                                value = value.item()
                            except (ValueError, AttributeError):
                                pass
                        return value
                except (KeyError, TypeError):
                    continue
        return default
    
    def _format_number(self, value, is_currency=True):
        """Format numbers for display"""
        try:
            import pandas as pd
            
            if pd.isna(value) or value == 0:
                return "0"
            
            value = float(value)
            
            if is_currency:
                # Format as currency (for market cap, volume, liquidity)
                if value >= 1_000_000_000:
                    return f"${value/1_000_000_000:.2f}B"
                elif value >= 1_000_000:
                    return f"${value/1_000_000:.2f}M"
                elif value >= 1_000:
                    return f"${value/1_000:.2f}K"
                else:
                    return f"${value:.2f}"
            else:
                # Format as plain number (for holders)
                if value >= 1_000_000:
                    return f"{value/1_000_000:.2f}M"
                elif value >= 1_000:
                    return f"{value/1_000:.2f}K"
                else:
                    return f"{value:,.0f}"
        except:
            return str(value)

    def _safe_json_parse(self, json_string, default=None):
        """Safely parse JSON with comprehensive error handling"""
        if not json_string or not isinstance(json_string, str):
            return default or {}
        
        try:
            # Clean the JSON string
            cleaned = json_string.strip()
            if not cleaned or cleaned == 'nan':
                return default or {}
            
            # Try to parse
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            try:
                # Replace single quotes with double quotes
                fixed = cleaned.replace("'", '"')
                return json.loads(fixed)
            except:
                try:
                    # Try to fix more complex JSON issues
                    import re
                    # Fix missing quotes around property names
                    fixed = re.sub(r'(\w+):', r'"\1":', cleaned)
                    # Replace single quotes with double quotes
                    fixed = fixed.replace("'", '"')
                    return json.loads(fixed)
                except:
                    try:
                        # Try to extract valid JSON from malformed string
                        # Find JSON-like structures
                        json_pattern = r'\{[^{}]*\}'
                        matches = re.findall(json_pattern, cleaned)
                        if matches:
                            return json.loads(matches[0])
                    except:
                        pass
            
            # If all parsing attempts fail, return default
            return default or {}
        except Exception as e:
            return default or {}
    
    def _extract_nested_value(self, data, path, default=0):
        """Extract value from nested dictionary using dot notation"""
        if not data or not isinstance(data, dict):
            return default
        
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current if current is not None else default
    
    def _extract_holders_fixed(self, row):
        """Fixed holders extraction that handles malformed JSON"""
        holders = 0
        
        # Try onchain_data first
        onchain_data = row.get('onchain_data', '{}')
        if onchain_data and isinstance(onchain_data, str):
            # Handle malformed JSON like {'total_holders' 0}
            try:
                # Try to fix common malformed patterns
                fixed_data = onchain_data.replace("'", '"')
                # Fix missing quotes around values
                import re
                fixed_data = re.sub(r':\s*(\d+)', r': "\1"', fixed_data)
                fixed_data = re.sub(r':\s*([^"\d][^,}]*[^"\d,}])', r': "\1"', fixed_data)
                
                onchain_json = json.loads(fixed_data)
                
                # Look for holders in various nested structures
                holders = (
                    self._extract_nested_value(onchain_json, 'holders.total_holders') or
                    self._extract_nested_value(onchain_json, 'holder_count') or
                    self._extract_nested_value(onchain_json, 'total_holders') or
                    self._extract_nested_value(onchain_json, 'addresses') or
                    self._extract_nested_value(onchain_json, 'holders') or
                    0
                )
            except:
                # If JSON parsing fails, try regex extraction
                try:
                    import re
                    # Look for patterns like 'total_holders': 4065
                    match = re.search(r"'total_holders':\s*(\d+)", onchain_data)
                    if match:
                        holders = int(match.group(1))
                    else:
                        # Look for any number that might be holders
                        numbers = re.findall(r'\d+', onchain_data)
                        if numbers:
                            # Use the first reasonable number (not 0)
                            for num in numbers:
                                num_int = int(num)
                                if num_int > 100:  # Reasonable holder count
                                    holders = num_int
                                    break
                except:
                    pass
        
        # If no holders found, try enhanced_data
        if holders == 0:
            enhanced_data = self._safe_json_parse(row.get('enhanced_data', '{}'))
            if enhanced_data:
                holders = (
                    self._extract_nested_value(enhanced_data, 'ethplorer.holders') or
                    self._extract_nested_value(enhanced_data, 'onchain_data.holders.total_holders') or
                    0
                )
        
        return holders
    
    def _extract_market_data_enhanced(self, row):
        """Enhanced market data extraction with better fallback logic"""
        market_cap = 0
        volume_24h = 0
        liquidity = 0
        
        # Try multiple sources for market data
        market_sources = ['enhanced_data', 'market_data']
        for source in market_sources:
            source_data = self._safe_json_parse(row.get(source, '{}'))
            if not source_data:
                continue
            
            # Extract market cap from various nested structures
            market_cap = (
                self._extract_nested_value(source_data, 'market_cap') or
                self._extract_nested_value(source_data, 'marketCap') or
                self._extract_nested_value(source_data, 'market_cap_usd') or
                self._extract_nested_value(source_data, 'market_cap_usd_24h') or
                self._extract_nested_value(source_data, 'coingecko.market_data.market_cap') or
                self._extract_nested_value(source_data, 'cmc.data.market_cap') or
                self._extract_nested_value(source_data, 'coingecko.market_data.market_cap.usd') or
                0
            )
            
            # Extract volume from various nested structures
            volume_24h = (
                self._extract_nested_value(source_data, 'volume_24h') or
                self._extract_nested_value(source_data, 'volume24h') or
                self._extract_nested_value(source_data, 'volume_usd_24h') or
                self._extract_nested_value(source_data, 'total_volume') or
                self._extract_nested_value(source_data, 'coingecko.market_data.total_volume') or
                self._extract_nested_value(source_data, 'cmc.data.volume_24h') or
                self._extract_nested_value(source_data, 'coingecko.market_data.total_volume.usd') or
                0
            )
            
            # Extract liquidity from various nested structures
            liquidity = (
                self._extract_nested_value(source_data, 'liquidity') or
                self._extract_nested_value(source_data, 'liquidity_usd') or
                self._extract_nested_value(source_data, 'total_liquidity') or
                self._extract_nested_value(source_data, 'onchain_data.liquidity') or
                0
            )
            
            # If we found any data, break
            if (
                (isinstance(market_cap, (int, float)) and market_cap > 0) or
                (isinstance(volume_24h, (int, float)) and volume_24h > 0) or
                (isinstance(liquidity, (int, float)) and liquidity > 0)
            ):
                break
        
        # Always try fallback with real-time data if local data is missing
        if market_cap == 0 or volume_24h == 0:
            symbol = row.get('symbol', 'Unknown')
            token_address = row.get('token_address', '')
            fallback_data = self._get_fallback_token_data(symbol, token_address)
            
            # Use fallback data if local data is missing
            if market_cap == 0:
                market_cap = fallback_data['market_cap']
            if volume_24h == 0:
                volume_24h = fallback_data['volume_24h']
        
        # Try to get real token data from multiple APIs
        symbol = row.get('symbol', 'Unknown')
        token_address = row.get('token_address', '')
        try:
            real_data = self._get_real_token_data(token_address, symbol)
        except TypeError as e:
            print(f"      ⚠️  Method call error for {symbol}: {e}")
            real_data = {}
        
        # Use real data if local data is missing
        if real_data and isinstance(real_data, dict):
            if liquidity == 0 and real_data.get('liquidity', 0) > 0:
                liquidity = real_data['liquidity']
            if self._extract_holders_fixed(row) == 0 and real_data.get('holders', 0) > 0:
                # Update holders in the row for future reference
                row['real_holders'] = real_data['holders']
            if volume_24h == 0 and real_data.get('volume_24h', 0) > 0:
                volume_24h = real_data['volume_24h']
        
        return market_cap, volume_24h, liquidity
    
    def _get_fallback_token_data(self, symbol, token_address):
        """Get fallback token data from multiple sources"""
        fallback_data = {
            'name': 'Unknown',
            'market_cap': 0,
            'volume_24h': 0,
            'holders': 0,
            'liquidity': 0
        }
        
        # Use external token mappings
        if token_address:
            fallback_data['name'] = get_token_name(token_address)
            # Update symbol if it was wrong
            correct_symbol = get_token_symbol(token_address)
            if correct_symbol and correct_symbol != 'Unknown':
                symbol = correct_symbol
        elif symbol:
            # Try to get name from symbol (if we have a mapping)
            fallback_data['name'] = get_token_name(symbol)
        
        # Try to get real-time data from CoinGecko (free API)
        try:
            import requests
            
            # Get CoinGecko ID
            coin_id = self._get_coingecko_id(symbol)
            if coin_id:
                # Try simple price API first (more reliable)
                coingecko_url = f"https://api.coingecko.com/api/v3/simple/price"
                params = {
                    'ids': coin_id,
                    'vs_currencies': 'usd',
                    'include_market_cap': 'true',
                    'include_24hr_vol': 'true'
                }
                
                response = requests.get(coingecko_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if coin_id in data:
                        coin_data = data[coin_id]
                        fallback_data['market_cap'] = coin_data.get('usd_market_cap', 0)
                        fallback_data['volume_24h'] = coin_data.get('usd_24h_vol', 0)
                        print(f"      ✅ Fetched real-time data for {symbol}: ${fallback_data['market_cap']:,.0f} market cap")
                    
        except Exception as e:
            # Silently fail - this is just a fallback
            pass
        
        return fallback_data
    
    def _get_alternative_market_data(self, data, symbol, token_address):
        """Get market data from alternative sources when CoinGecko fails"""
        try:
            import requests
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            # 1. Try CoinMarketCap API (if available)
            cmc_api_key = os.getenv('COINMARKETCAP_API_KEY')
            if cmc_api_key and symbol and symbol != 'Unknown':
                try:
                    cmc_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
                    params = {
                        'symbol': symbol,
                        'convert': 'USD'
                    }
                    headers = {
                        'X-CMC_PRO_API_KEY': cmc_api_key
                    }
                    
                    response = requests.get(cmc_url, params=params, headers=headers, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        if 'data' in result and symbol in result['data']:
                            coin_data = result['data'][symbol]
                            quote = coin_data.get('quote', {}).get('USD', {})
                            
                            if data['market_cap'] == 0:
                                data['market_cap'] = quote.get('market_cap', 0)
                            if data['volume_24h'] == 0:
                                data['volume_24h'] = quote.get('volume_24h', 0)
                            # Do not estimate liquidity from market cap
                            
                            print(f"      ✅ CoinMarketCap data for {symbol}: ${data['market_cap']:,.0f} market cap, ${data['volume_24h']:,.0f} volume")
                            return
                except Exception as e:
                    pass
            
            # 2. Try CoinPaprika API (free, no key required)
            if symbol and symbol != 'Unknown':
                try:
                    # Get CoinPaprika ID from external mappings
                    paprika_id = get_paprika_id(symbol)
                    if paprika_id:
                        paprika_url = f"https://api.coinpaprika.com/v1/tickers/{paprika_id}"
                        response = requests.get(paprika_url, timeout=10)
                        if response.status_code == 200:
                            coin_data = response.json()
                            
                            if data['market_cap'] == 0:
                                data['market_cap'] = coin_data.get('market_cap_usd', 0)
                            if data['volume_24h'] == 0:
                                data['volume_24h'] = coin_data.get('volume_24h', 0)
                            # Do not estimate liquidity from market cap
                            
                            print(f"      ✅ CoinPaprika data for {symbol}: ${data['market_cap']:,.0f} market cap, ${data['volume_24h']:,.0f} volume")
                            return
                except Exception as e:
                    pass
            
            # 4. Try DeFiLlama API (free, no key required)
            if token_address:
                try:
                    defillama_url = f"https://api.llama.fi/protocol/{token_address.lower()}"
                    response = requests.get(defillama_url, timeout=10)
                    if response.status_code == 200:
                        protocol_data = response.json()
                        
                        if data['market_cap'] == 0:
                            data['market_cap'] = protocol_data.get('marketCap', 0)
                        if data['volume_24h'] == 0:
                            data['volume_24h'] = protocol_data.get('volume24h', 0)
                        # Do not estimate liquidity from TVL
                        
                        print(f"      ✅ DeFiLlama data for {symbol}: ${data['market_cap']:,.0f} market cap, ${data['volume_24h']:,.0f} volume")
                        return
                except Exception as e:
                    pass
            
            # 5. Use webhook cache data if available (only if it contains real data)
            cached_data = self._get_cached_market_data(symbol)
            if cached_data and (cached_data.get('market_cap', 0) > 0 or cached_data.get('holders', 0) > 0):
                if data['market_cap'] == 0:
                    data['market_cap'] = cached_data.get('market_cap', 0)
                if data['volume_24h'] == 0:
                    data['volume_24h'] = cached_data.get('volume_24h', 0)
                if data['liquidity'] == 0:
                    data['liquidity'] = cached_data.get('liquidity', 0)
                if data['holders'] == 0:
                    data['holders'] = cached_data.get('holders', 0)
                
                print(f"      ✅ Webhook cache data for {symbol}: MC=${data['market_cap']:,.0f}, Vol=${data['volume_24h']:,.0f}, Holders={data['holders']:,}")
                return
            
            # NO ESTIMATED DATA - Only use real data from webhook cache
            # If values are still 0, leave them as 0 rather than using estimates
            
            # NO ESTIMATED DATA - Only use real data from webhook cache
            # If values are still 0, leave them as 0 rather than using estimates
            
        except Exception as e:
            print(f"      ❌ Alternative data error for {symbol}: {e}")
    

    
    def _get_cached_market_data(self, symbol):
        """Get cached market data from webhook cache"""
        try:
            # First try the webhook cache (real_data_cache.json)
            webhook_cache_file = os.path.join(DATA_DIR, 'real_data_cache.json')
            if os.path.exists(webhook_cache_file):
                with open(webhook_cache_file, 'r') as f:
                    cache_data = json.load(f)
                    
                # Search through all tokens in the cache
                for token_key, token_data in cache_data.get('tokens', {}).items():
                    # Check if this token matches our symbol
                    token_address = token_data.get('address', '')
                    if token_address:
                        # Use external mapping to get symbol from address
                        cached_symbol = get_token_symbol(token_address)
                        if cached_symbol == symbol:
                            market_data = token_data.get('market_data', {})
                            onchain_data = token_data.get('onchain_data', {})
                            
                            # Extract market data from nested structure
                            market_cap = 0
                            volume_24h = 0
                            holders = token_data.get('total_holders', 0)
                            
                            # Check all market data sources
                            for source, source_data in market_data.items():
                                if isinstance(source_data, dict):
                                    market_cap = source_data.get('market_cap', market_cap)
                                    volume_24h = source_data.get('volume_24h', volume_24h)
                            
                            # Check onchain data for holders if not found in total_holders
                            if holders == 0:
                                for source, source_data in onchain_data.items():
                                    if isinstance(source_data, dict):
                                        holders = source_data.get('holders', holders)
                            
                            # Return data if we have any real values (not placeholder values)
                            if market_cap > 0 or volume_24h > 0 or holders > 0:
                                return {
                                    'market_cap': market_cap,
                                    'volume_24h': volume_24h,
                                    'liquidity': 0,
                                    'holders': holders
                                }
                            else:
                                print(f"      ⚠️ Cache entry for {symbol} exists but has no real values (MC={market_cap}, Vol={volume_24h}, Holders={holders})")
            
            # Fallback to old cache method
            cache_file = os.path.join(DATA_DIR, 'token_data_cache.pkl')
            if os.path.exists(cache_file):
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    if 'data' in cache_data:
                        for token_addr, token_data in cache_data['data'].items():
                            if token_data.get('symbol') == symbol:
                                market_data = token_data.get('market_data', {})
                                return {
                                    'market_cap': market_data.get('coingecko', {}).get('market_cap', 0),
                                    'volume_24h': market_data.get('coingecko', {}).get('volume_24h', 0),
                                    'liquidity': market_data.get('enhanced_data', {}).get('liquidity', 0)
                                }
        except Exception as e:
            print(f"      ❌ Cache read error: {e}")
        return None
    

    
    def _get_real_token_data(self, token_address, symbol):
        """Fetch real token data from multiple APIs: liquidity, holders, volume, concentration"""
        data = {
            'market_cap': 0.0,
            'liquidity': 0.0,
            'holders': 0,
            'volume_24h': 0.0,
            'concentration': 0.0
        }
        
        # Debug logging for SAND token specifically
        if token_address and '3845bad' in token_address.lower():
            print(f"      🔍 SAND token detected: {token_address}")
            print(f"      🔍 Current symbol: {symbol}")
        
        try:
            import requests
            import os
            import time
            from dotenv import load_dotenv
            load_dotenv()
            
            # FIRST: Check webhook cache for real data (highest priority)
            cached_data = self._get_cached_market_data(symbol)
            if cached_data and (cached_data.get('market_cap', 0) > 0 or cached_data.get('holders', 0) > 0):
                # Only use cache if it has real data (not placeholder values)
                data['market_cap'] = cached_data.get('market_cap', 0)
                data['volume_24h'] = cached_data.get('volume_24h', 0)
                data['liquidity'] = cached_data.get('liquidity', 0)
                data['holders'] = cached_data.get('holders', 0)
                print(f"      ✅ Using webhook cache data for {symbol}: MC=${data['market_cap']:,.0f}, Holders={data['holders']:,}")
                return data
            elif cached_data:
                print(f"      ⚠️ Found cached data for {symbol} but it has no real values, fetching fresh data")
            
            # Use external token mappings for symbol correction
            if token_address and (symbol == 'Unknown' or not symbol):
                corrected_symbol = get_token_symbol(token_address)
                if corrected_symbol != 'Unknown':
                    symbol = corrected_symbol
                    print(f"      🔍 Symbol corrected from address: {symbol}")
            
            # Try to get CoinGecko data
            coin_id = None
            if symbol and symbol != 'Unknown':
                # Use external mapping
                coin_id = get_coingecko_id(symbol)
            
            # 1. ETHERSCAN API (holders, concentration) - Do this first as it's reliable
            etherscan_api_key = os.getenv('ETHERSCAN_API_KEY')
            if etherscan_api_key and token_address:
                try:
                    # Standard Etherscan for all tokens (including OP)
                    # No estimated data - only real data from APIs
                        # Standard Etherscan for Ethereum tokens
                        etherscan_url = "https://api.etherscan.io/api"
                        params = {
                            'module': 'token',
                            'action': 'tokenholderlist',
                            'contractaddress': token_address,
                            'page': 1,
                            'offset': 1,
                            'apikey': etherscan_api_key
                        }
                        
                        response = requests.get(etherscan_url, params=params, timeout=10)
                        if response.status_code == 200:
                            result = response.json()
                            if result.get('status') == '1' and result.get('result'):
                                # Get total holders from first result
                                holders_data = result['result'][0]
                                data['holders'] = int(holders_data.get('TokenHolderCount', 0))
                                print(f"      ✅ Etherscan holders for {symbol}: {data['holders']:,}")
                                
                                # Calculate concentration (top 10 holders percentage)
                                if data['holders'] > 0:
                                    top_holders_url = "https://api.etherscan.io/api"
                                    top_params = {
                                        'module': 'token',
                                        'action': 'tokenholderlist',
                                        'contractaddress': token_address,
                                        'page': 1,
                                        'offset': 10,
                                        'apikey': etherscan_api_key
                                    }
                                    
                                    top_response = requests.get(top_holders_url, params=top_params, timeout=10)
                                    if top_response.status_code == 200:
                                        top_result = top_response.json()
                                        if top_result.get('status') == '1' and top_result.get('result'):
                                            total_supply = float(top_result['result'][0].get('TokenSupply', 0))
                                            top_10_balance = sum(float(holder.get('TokenHolderQuantity', 0)) for holder in top_result['result'][:10])
                                            if total_supply > 0:
                                                data['concentration'] = (top_10_balance / total_supply) * 100
                                                print(f"      ✅ Etherscan concentration for {symbol}: {data['concentration']:.2f}%")
                except Exception as e:
                    pass
            
            # 2. ETHPLORER API (holders, volume, liquidity) - FLATTENED
            if token_address:
                ethplorer_url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey=freekey"
                try:
                    response = requests.get(ethplorer_url, timeout=10)
                    if response.status_code != 200:
                        raise RuntimeError("Ethplorer token info HTTP error")
                    token_info = response.json()
                except Exception:
                    token_info = {}

                # Holders count
                try:
                    if data['holders'] == 0 and 'holdersCount' in token_info:
                        data['holders'] = int(token_info['holdersCount'])
                        print(f"      ✅ Ethplorer holders for {symbol}: {data['holders']:,}")
                except Exception:
                    pass

                # No holder estimation - only use real data

                # Volume 24h
                try:
                    if data['volume_24h'] == 0 and 'price' in token_info and 'volume24h' in token_info:
                        data['volume_24h'] = float(token_info['volume24h'])
                        print(f"      ✅ Ethplorer volume for {symbol}: ${data['volume_24h']:,.0f}")
                except Exception:
                    pass

                # Market cap from price and supply
                try:
                    if data['market_cap'] == 0 and 'price' in token_info and 'totalSupply' in token_info:
                        price = float(token_info['price']['rate'])
                        supply = float(token_info['totalSupply'])
                        market_cap = price * supply
                        if 0 < market_cap < 1e12:
                            data['market_cap'] = market_cap
                            print(f"      ✅ Ethplorer market cap for {symbol}: ${data['market_cap']:,.0f}")
                except Exception:
                    pass

                # Liquidity from DeFiLlama
                try:
                    if data['liquidity'] == 0 and token_address:
                        defillama_url = f"https://api.llama.fi/token/{token_address}"
                        defillama_response = requests.get(defillama_url, timeout=10)
                        if defillama_response.status_code == 200:
                            defillama_data = defillama_response.json()
                            if 'tvl' in defillama_data and defillama_data['tvl'] > 0:
                                data['liquidity'] = defillama_data['tvl']
                                print(f"      ✅ DeFiLlama liquidity for {symbol}: ${data['liquidity']:,.0f}")
                except Exception as e:
                    print(f"      ⚠️ DeFiLlama liquidity fetch failed for {symbol}: {e}")
            
            # 3. COINGECKO API (market cap, volume) - With better rate limit handling
            if coin_id:
                try:
                    # Add longer delay to prevent rate limiting
                    time.sleep(1.0)  # Increased delay
                    
                    # Use simple price API first (more reliable)
                    coingecko_url = "https://api.coingecko.com/api/v3/simple/price"
                    params = {
                        'ids': coin_id,
                        'vs_currencies': 'usd',
                        'include_market_cap': 'true',
                        'include_24hr_vol': 'true'
                    }
                    
                    response = requests.get(coingecko_url, params=params, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        if coin_id in result:
                            coin_data = result[coin_id]
                            if data['market_cap'] == 0:
                                data['market_cap'] = coin_data.get('usd_market_cap', 0)
                            if data['volume_24h'] == 0:
                                data['volume_24h'] = coin_data.get('usd_24h_vol', 0)
                            print(f"      ✅ CoinGecko simple data for {symbol}: ${data['market_cap']:,.0f} market cap, ${data['volume_24h']:,.0f} volume")
                    elif response.status_code == 429:
                        print(f"      ⚠️ CoinGecko rate limit hit for {symbol}, using fallbacks")
                        # Try alternative data sources immediately
                        self._get_alternative_market_data(data, symbol, token_address)
                    
                    # If simple API didn't work, try detailed API
                    if (data['volume_24h'] == 0 or data['market_cap'] == 0) and response.status_code != 429:
                        time.sleep(1.0)  # Increased delay
                        coingecko_detailed_url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                        response = requests.get(coingecko_detailed_url, timeout=10)
                        if response.status_code == 200:
                            coin_data = response.json()
                            
                            # Extract market data
                            market_data = coin_data.get('market_data', {})
                            if data['market_cap'] == 0:
                                data['market_cap'] = market_data.get('market_cap', {}).get('usd', 0)
                            if data['volume_24h'] == 0:
                                data['volume_24h'] = market_data.get('total_volume', {}).get('usd', 0)
                            # Do not estimate liquidity from market cap
                            
                            # NO ESTIMATED VALUES - only use real holders data
                            # Removed reddit_subscribers * 100 estimation logic
                            
                            print(f"      ✅ CoinGecko detailed data for {symbol}: ${data['volume_24h']:,.0f} volume")
                        elif response.status_code == 429:
                            print(f"      ⚠️ CoinGecko rate limit hit for {symbol} fallback")
                            self._get_alternative_market_data(data, symbol, token_address)
                except Exception as e:
                    print(f"      ❌ CoinGecko error for {symbol}: {e}")
                    # Try alternative data sources on any error
                    self._get_alternative_market_data(data, symbol, token_address)
            
            # 4. COVALENT API (market cap, volume) - More reliable fallback
            covalent_api_key = os.getenv('COVALENT_API_KEY')
            if covalent_api_key and token_address and (data['market_cap'] == 0 or data['volume_24h'] == 0):
                try:
                    covalent_url = f"https://api.covalenthq.com/v1/1/tokens/{token_address}/"
                    params = {'key': covalent_api_key}
                    
                    response = requests.get(covalent_url, params=params, timeout=10)
                    if response.status_code == 200:
                        result = response.json()
                        if 'data' in result and result['data']:
                            token_data = result['data']
                            if 'quote_rate' in token_data and 'total_supply' in token_data:
                                price = float(token_data['quote_rate'])
                                supply = float(token_data['total_supply'])
                                if data['market_cap'] == 0:
                                    data['market_cap'] = price * supply
                                    print(f"      ✅ Covalent market cap for {symbol}: ${data['market_cap']:,.0f}")
                            
                            if 'volume_24h' in token_data and data['volume_24h'] == 0:
                                data['volume_24h'] = float(token_data['volume_24h'])
                                print(f"      ✅ Covalent volume for {symbol}: ${data['volume_24h']:,.0f}")
                except Exception as e:
                    pass
            
            # 5. THE GRAPH APIs (liquidity, volume) - For DEX data
            if token_address and (data['liquidity'] == 0 or data['volume_24h'] == 0):
                try:
                    # Uniswap V3
                    uniswap_url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
                    query = """
                    query ($token: String!) {
                        token(id: $token) {
                            totalValueLockedUSD
                            volumeUSD
                            volume
                        }
                    }
                    """
                    
                    response = requests.post(
                        uniswap_url,
                        json={'query': query, 'variables': {'token': token_address.lower()}},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'data' in result and result['data'] and result['data']['token']:
                            token_data = result['data']['token']
                            tvl = float(token_data.get('totalValueLockedUSD', 0))
                            volume = float(token_data.get('volumeUSD', 0))
                            
                            if tvl > 0 and tvl < 1e15 and data['liquidity'] == 0:  # Sanity check
                                data['liquidity'] = tvl
                                print(f"      ✅ Uniswap V3 liquidity for {symbol}: ${data['liquidity']:,.0f}")
                            
                            if volume > 0 and data['volume_24h'] == 0:
                                data['volume_24h'] = volume
                                print(f"      ✅ Uniswap V3 volume for {symbol}: ${data['volume_24h']:,.0f}")
                except Exception as e:
                    pass
                
                try:
                    # SushiSwap
                    sushiswap_url = "https://api.thegraph.com/subgraphs/name/sushiswap/exchange"
                    query = """
                    query ($token: String!) {
                        token(id: $token) {
                            totalSupply
                            volume
                            liquidity
                        }
                    }
                    """
                    
                    response = requests.post(
                        sushiswap_url,
                        json={'query': query, 'variables': {'token': token_address.lower()}},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if 'data' in result and result['data'] and result['data']['token']:
                            token_data = result['data']['token']
                            liquidity = float(token_data.get('liquidity', 0))
                            volume = float(token_data.get('volume', 0))
                            
                            if liquidity > 0 and liquidity < 1e15 and data['liquidity'] == 0:  # Sanity check
                                data['liquidity'] = liquidity
                                print(f"      ✅ SushiSwap liquidity for {symbol}: ${data['liquidity']:,.0f}")
                            
                            if volume > 0 and data['volume_24h'] == 0:
                                data['volume_24h'] = volume
                                print(f"      ✅ SushiSwap volume for {symbol}: ${data['volume_24h']:,.0f}")
                except Exception as e:
                    pass
            
            # 6. ADDITIONAL COINGECKO FALLBACKS for tokens without direct mapping
            if data['market_cap'] == 0 or data['volume_24h'] == 0:
                # Try alternative symbol mappings
                alternative_symbols = {
                    'USDC': 'usd-coin',
                    'USDT': 'tether',
                    'WBTC': 'wrapped-bitcoin',
                    'LINK': 'chainlink',
                    '1INCH': '1inch',
                    'UNI': 'uniswap',
                    'GRT': 'the-graph',
                    'MKR': 'maker',
                    'SUSHI': 'sushi',
                    'COMP': 'compound-governance-token',
                    'BAT': 'basic-attention-token',
                    'MANA': 'decentraland',
                    'SAND': 'the-sandbox',
                    'OP': 'optimism',
                    'TRX': 'tron',
                    'POL': 'matic-network',
                    'CHZ': 'chiliz',
                    'QNT': 'quant-network',
                    'GALA': 'gala'
                }
                
                if symbol.upper() in alternative_symbols:
                    try:
                        time.sleep(1.0)  # Increased delay to prevent rate limiting
                        fallback_coin_id = alternative_symbols[symbol.upper()]
                        coingecko_url = "https://api.coingecko.com/api/v3/simple/price"
                        params = {
                            'ids': fallback_coin_id,
                            'vs_currencies': 'usd',
                            'include_market_cap': 'true',
                            'include_24hr_vol': 'true'
                        }
                        
                        response = requests.get(coingecko_url, params=params, timeout=10)
                        if response.status_code == 200:
                            result = response.json()
                            if fallback_coin_id in result:
                                coin_data = result[fallback_coin_id]
                                if data['market_cap'] == 0:
                                    data['market_cap'] = coin_data.get('usd_market_cap', 0)
                                if data['volume_24h'] == 0:
                                    data['volume_24h'] = coin_data.get('usd_24h_vol', 0)
                                # No estimated liquidity - only use real data
                                print(f"      ✅ CoinGecko fallback data for {symbol}: ${data['market_cap']:,.0f} market cap, ${data['volume_24h']:,.0f} volume")
                        elif response.status_code == 429:
                            print(f"      ⚠️ CoinGecko rate limit hit for {symbol} fallback")
                            self._get_alternative_market_data(data, symbol, token_address)
                    except Exception as e:
                        print(f"      ❌ CoinGecko fallback error for {symbol}: {e}")
                        self._get_alternative_market_data(data, symbol, token_address)
            
            # NO ESTIMATED DATA - Only use real data from APIs
            # If we don't have real data, leave it as 0 rather than estimating
            
            # Final sanity checks - only for unreasonably large values
            if data['liquidity'] > 1e15:  # If liquidity is unreasonably large
                data['liquidity'] = 0  # Reset to 0 rather than estimate
                print(f"      ⚠️  Reset unreasonably large liquidity for {symbol}")
            
            # Final liquidity sanity check - if still unreasonably large, reset to 0
            if data['liquidity'] > data['market_cap'] * 0.5 and data['market_cap'] > 0:  # If liquidity > 50% of market cap
                data['liquidity'] = 0  # Reset to 0 rather than estimate
                print(f"      ⚠️  Reset unreasonably large liquidity for {symbol}")
            
            # Final fallback: if we still don't have market data, try alternative sources
            if data['market_cap'] == 0 or data['volume_24h'] == 0:
                self._get_alternative_market_data(data, symbol, token_address)

            # NO ESTIMATED DATA - Only use real data from webhook cache
            # If values are still 0, leave them as 0 rather than using estimates

            return data
            
        except Exception as e:
            print(f"      ❌ Error in _get_real_token_data for {symbol}: {e}")
            return data
    
    def _get_coingecko_id(self, symbol):
        """Get CoinGecko coin ID from symbol"""
        # Use external token mappings
        return get_coingecko_id(symbol) or symbol.lower()
    
    def _correct_symbol_by_address(self, token_address, current_symbol):
        """Correct symbol based on token address using external mappings"""
        if not token_address:
            return current_symbol
            
        # Use external token mappings
        corrected_symbol = get_token_symbol(token_address)
        if corrected_symbol and corrected_symbol != 'Unknown':
            print(f"      ✅ Symbol corrected from address: {token_address} -> {corrected_symbol}")
            return corrected_symbol
        
        return current_symbol
    
    def _extract_token_name(self, row):
        """Extract token name from various possible sources with enhanced address-based mapping"""
        # Address-based token identification (highest priority)
        token_address = row.get('token_address', '') or row.get('token', '')
        if token_address:
            # Use external token mappings for address-based identification
            try:
                from token_mappings import get_token_name
                token_name = get_token_name(token_address)
                if token_name != 'Unknown Token':
                    return token_name
            except ImportError:
                # Fallback to hardcoded mappings if external file not available
                address_name_mappings = {
                    '0x3845badade8e6dff049820680d1f14bd3903a5d0': 'The Sandbox',
                    '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9': 'Aave',
                    '0x3506424f91fd33084466f402d5d97f05f8e3b4af': 'Chiliz',
                    '0xc00e94cb662c3520282e6f5717214004a7f26888': 'Compound',
                    '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USD Coin',
                    '0xdac17f958d2ee523a2206206994597c13d831ec7': 'Tether',
                    '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': 'Wrapped Bitcoin',
                    '0x514910771af9ca656af840dff83e8264ecf986ca': 'Chainlink',
                    '0x111111111117dc0aa78b770fa6a738034120c302': '1inch',
                    '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6': 'Polygon',
                    '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'Uniswap',
                    '0x6b175474e89094c44da98b954eedeac495271d0f': 'Dai',
                    '0xc944e90c64b2c07662a292be6244bdf05cda44a7': 'The Graph',
                    '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2': 'Maker',
                    '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2': 'SushiSwap',
                    '0xd1d2eb1b1e90b638588728b4130137d262c87cae': 'Gala',
                    '0x4a220e6096b25eadb88358cb44068a3248254675': 'Quant',
                    '0x0f5d2fb29fb7d3cfee444a200298f468908cc942': 'Decentraland',
                    '0x0d8775f648430679a709e98d2b0cb6250d2887ef': 'Basic Attention Token',
                    '0x4200000000000000000000000000000000000042': 'Optimism',
                    '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRON'
                }
                
                if token_address.lower() in address_name_mappings:
                    return address_name_mappings[token_address.lower()]
        
        # Try to extract from name field
        name = row.get('name', '')
        if name and name != 'Unknown':
            return name
        
        # Try to extract from symbol field
        symbol = row.get('symbol', '')
        if symbol and symbol != 'Unknown':
            # Map common symbols to names
            symbol_name_mappings = {
                'AAVE': 'Aave',
                'CHZ': 'Chiliz',
                'COMP': 'Compound',
                'USDC': 'USD Coin',
                'USDT': 'Tether',
                'WBTC': 'Wrapped Bitcoin',
                'LINK': 'Chainlink',
                '1INCH': '1inch',
                'POL': 'Polygon',
                'UNI': 'Uniswap',
                'DAI': 'Dai',
                'GRT': 'The Graph',
                'MKR': 'Maker',
                'SUSHI': 'SushiSwap',
                'GALA': 'Gala',
                'QNT': 'Quant',
                'MANA': 'Decentraland',
                'SAND': 'The Sandbox',
                'BAT': 'Basic Attention Token',
                'OP': 'Optimism',
                'TRX': 'TRON',
                'SONIC': 'Sonic'
            }
            return symbol_name_mappings.get(symbol.upper(), symbol)
        
        return 'Unknown'
    
    def _extract_market_data(self, row):
        """Enhanced market data extraction from multiple sources"""
        market_cap = 0
        volume_24h = 0
        liquidity = 0
        
        # Try multiple sources for market data
        market_sources = ['enhanced_data', 'market_data']
        for source in market_sources:
            source_data = self._safe_json_parse(row.get(source, '{}'))
            if not source_data:
                continue
            
            # Extract market cap from various nested structures
            market_cap = (
                self._extract_nested_value(source_data, 'market_cap') or
                self._extract_nested_value(source_data, 'marketCap') or
                self._extract_nested_value(source_data, 'market_cap_usd') or
                self._extract_nested_value(source_data, 'market_cap_usd_24h') or
                self._extract_nested_value(source_data, 'coingecko.market_data.market_cap') or
                self._extract_nested_value(source_data, 'cmc.data.market_cap') or
                self._extract_nested_value(source_data, 'coingecko.market_data.market_cap.usd') or
                0
            )
            
            # Extract volume from various nested structures
            volume_24h = (
                self._extract_nested_value(source_data, 'volume_24h') or
                self._extract_nested_value(source_data, 'volume24h') or
                self._extract_nested_value(source_data, 'volume_usd_24h') or
                self._extract_nested_value(source_data, 'total_volume') or
                self._extract_nested_value(source_data, 'coingecko.market_data.total_volume') or
                self._extract_nested_value(source_data, 'cmc.data.volume_24h') or
                self._extract_nested_value(source_data, 'coingecko.market_data.total_volume.usd') or
                0
            )
            
            # Extract liquidity from various nested structures
            liquidity = (
                self._extract_nested_value(source_data, 'liquidity') or
                self._extract_nested_value(source_data, 'liquidity_usd') or
                self._extract_nested_value(source_data, 'total_liquidity') or
                self._extract_nested_value(source_data, 'onchain_data.liquidity') or
                0
            )
            
            # If we found any data, break
            if (
                (isinstance(market_cap, (int, float)) and market_cap > 0) or
                (isinstance(volume_24h, (int, float)) and volume_24h > 0) or
                (isinstance(liquidity, (int, float)) and liquidity > 0)
            ):
                break
        
        # If no data found, try fallback
        if market_cap == 0 and volume_24h == 0:
            symbol = row.get('symbol', 'Unknown')
            token_address = row.get('token_address', '')
            fallback_data = self._get_fallback_token_data(symbol, token_address)
            market_cap = fallback_data['market_cap']
            volume_24h = fallback_data['volume_24h']
        
        return market_cap, volume_24h, liquidity
    
    def _extract_holders(self, row):
        """Enhanced holders extraction from nested structures"""
        holders = 0
        
        # Try onchain_data first
        onchain_data = self._safe_json_parse(row.get('onchain_data', '{}'))
        if onchain_data:
            # Look for holders in various nested structures
            holders = (
                self._extract_nested_value(onchain_data, 'holders.total_holders') or
                self._extract_nested_value(onchain_data, 'holder_count') or
                self._extract_nested_value(onchain_data, 'total_holders') or
                self._extract_nested_value(onchain_data, 'addresses') or
                self._extract_nested_value(onchain_data, 'holders') or
                0
            )
        
        # If no holders found, try enhanced_data
        if holders == 0:
            enhanced_data = self._safe_json_parse(row.get('enhanced_data', '{}'))
            if enhanced_data:
                holders = (
                    self._extract_nested_value(enhanced_data, 'ethplorer.holders') or
                    self._extract_nested_value(enhanced_data, 'onchain_data.holders.total_holders') or
                    0
                )
        
        return holders

    def _is_stablecoin(self, symbol, token_name):
        """Determine if a token is a stablecoin"""
        stablecoin_symbols = ['USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'FRAX', 'USDP', 'USDD']
        stablecoin_names = ['tether', 'usd coin', 'dai', 'binance usd', 'trueusd', 'frax', 'pax dollar', 'usdd']
        
        if symbol.upper() in stablecoin_symbols:
            return True
        if token_name.lower() in stablecoin_names:
            return True
        return False
    
    def _safe_float(self, value, default=0.0):
        """Safely convert value to float"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                return float(value) if value.strip() else default
            else:
                return default
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0):
        """Safely convert value to int"""
        try:
            if isinstance(value, (int, float)):
                return int(value)
            elif isinstance(value, str):
                return int(float(value)) if value.strip() else default
            else:
                return default
        except (ValueError, TypeError):
            return default

def main():
    """Main entry point"""
    try:
        # Add time import
        import time
        
        dashboard = DeFiDashboard()
        dashboard.run()
    except Exception as e:
        print(f"Dashboard error: {e}")
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error", f"Could not start dashboard: {e}")
        except:
            pass

def create_lock_file():
    """Create lock file for this instance"""
    import tempfile
    import json
    import time
    import atexit
    
    lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
    os.makedirs(lock_dir, exist_ok=True)
    lock_file = os.path.join(lock_dir, 'main_dashboard.lock')
    
    lock_data = {
        'pid': os.getpid(),
        'started_at': time.time(),
        'service_name': 'main_dashboard'
    }
    
    try:
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f)
        
        # Register cleanup on exit
        atexit.register(lambda: cleanup_lock_file(lock_file))
        
    except Exception as e:
        print(f"Warning: Could not create lock file: {e}")

def cleanup_lock_file(lock_file):
    """Clean up lock file on exit"""
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except:
        pass

def check_singleton():
    """Check if another instance is already running"""
    import tempfile
    import json
    import subprocess
    
    lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
    lock_file = os.path.join(lock_dir, 'main_dashboard.lock')
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                data = json.load(f)
                pid = data.get('pid')
                
            if pid:
                try:
                    os.kill(pid, 0)
                    print("DeFi Dashboard is already running")
                    # Try to bring existing window to front (configurable)
                    from os import getenv
                    focus_mode = (getenv('FOCUS_BEHAVIOR', 'disabled') or '').lower()
                    if sys.platform == "darwin" and focus_mode not in ("disabled", "off", "false", "0"):
                        script = f'''
                        tell application "System Events"
                            set appList to every application process whose name contains "Python"
                            repeat with appProcess in appList
                                try
                                    tell appProcess
                                        set windowList to every window
                                        repeat with windowItem in windowList
                                            if name of windowItem contains "DeFi Dashboard" then
                                                set frontmost of appProcess to true
                                                perform action "AXRaise" of windowItem
                                                return
                                            end if
                                        end repeat
                                    end tell
                                end try
                            end repeat
                        end tell
                        '''
                        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
                    return False
                except OSError:
                    os.remove(lock_file)
        except (json.JSONDecodeError, FileNotFoundError):
            try:
                os.remove(lock_file)
            except:
                pass
    
    return True

if __name__ == "__main__":
    if check_singleton():
        create_lock_file()
        main()
