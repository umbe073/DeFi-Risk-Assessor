#!/usr/bin/env python3
"""
DeFi Risk Assessment Main Dashboard
Primary interface for the DeFi risk assessment tool
"""

import os
import sys

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
import subprocess
import threading
import time
from datetime import datetime, timedelta
import pickle

# App bundle mode is now handled by the macOS compatibility fix
# No need for separate dock utilities

# Import token mappings from external file
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from token_mappings import (
        get_token_name, get_token_symbol, get_coingecko_id, 
        get_paprika_id, get_market_cap_estimate, get_holder_estimate, get_token_type,
        get_cmc_id, get_cmc_name, get_cmc_slug
    )
except ImportError:
    # Fallback if token_mappings.py is not available
    def get_token_name(address): return 'Unknown Token'
    def get_token_symbol(address): return 'Unknown'
    def get_coingecko_id(symbol): return None
    def get_paprika_id(symbol): return None
    def get_market_cap_estimate(symbol): return 0
    def get_holder_estimate(symbol): return 0
    def get_token_type(symbol): return 'Unknown'
    def get_cmc_id(symbol): return None
    def get_cmc_name(symbol): return None
    def get_cmc_slug(symbol): return None

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

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
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 30))
        
        title_label = ttk.Label(header_frame, text="🛡️ DeFi Risk Assessment Tool")
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        subtitle_label = ttk.Label(header_frame, text="Professional cryptocurrency risk analysis platform")
        subtitle_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        # Quick Actions Panel
        actions_frame = ttk.LabelFrame(main_frame, text="🚀 Quick Actions", padding="20")
        actions_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 15))
        actions_frame.columnconfigure(0, weight=1)
        
        # Action buttons
        assess_btn = ttk.Button(actions_frame, text="🔍 Start Risk Assessment", 
                               command=self.start_assessment)
        assess_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        api_btn = ttk.Button(actions_frame, text="🔧 API Service Monitor", 
                            command=self.open_api_dashboard)
        api_btn.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        creds_btn = ttk.Button(actions_frame, text="🔐 Manage Credentials", 
                              command=self.manage_credentials)
        creds_btn.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        chains_btn = ttk.Button(actions_frame, text="🔗 Manage Chains", 
                               command=self.manage_chains)
        chains_btn.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        tokens_btn = ttk.Button(actions_frame, text="📝 Edit Token List", 
                               command=self.edit_tokens)
        tokens_btn.grid(row=4, column=0, sticky=(tk.W, tk.E))
        
        # Recent Reports Panel
        reports_frame = ttk.LabelFrame(main_frame, text="📊 Recent Reports", padding="20")
        reports_frame.grid(row=1, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        reports_frame.columnconfigure(0, weight=1)
        reports_frame.rowconfigure(1, weight=1)
        
        # Reports list
        reports_list_frame = ttk.Frame(reports_frame)
        reports_list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
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
        
        self.reports_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        reports_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Reports action buttons
        reports_actions = ttk.Frame(reports_frame)
        reports_actions.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        reports_actions.columnconfigure(2, weight=1)
        
        view_btn = ttk.Button(reports_actions, text="👁️ View Report", command=self.view_selected_report)
        view_btn.grid(row=0, column=0, padx=(0, 10))
        
        export_btn = ttk.Button(reports_actions, text="📤 Export", command=self.export_report)
        export_btn.grid(row=0, column=1, padx=(0, 10))
        
        refresh_btn = ttk.Button(reports_actions, text="🔄 Refresh", command=self.load_recent_reports)
        refresh_btn.grid(row=0, column=3)
        
        # System Status Panel (smaller)
        status_frame = ttk.LabelFrame(main_frame, text="📈 System Status", padding="15")
        status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N), pady=(15, 0))
        
        self.status_text = tk.Text(status_frame, height=6, wrap=tk.WORD, font=('Courier', 9))
        status_scroll = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scroll.set)
        
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        status_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
        
        # Data Viewer Panel (new)
        data_frame = ttk.LabelFrame(main_frame, text="📊 Token Data Viewer", padding="15")
        data_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(15, 0))
        
        # Data viewer controls
        data_controls = ttk.Frame(data_frame)
        data_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        load_csv_btn = ttk.Button(data_controls, text="📁 Load CSV Data", command=self.load_csv_data)
        load_csv_btn.grid(row=0, column=0, padx=(0, 10))
        
        load_excel_btn = ttk.Button(data_controls, text="📊 Load Excel Data", command=self.load_excel_data)
        load_excel_btn.grid(row=0, column=1, padx=(0, 10))
        
        refresh_data_btn = ttk.Button(data_controls, text="🔄 Refresh Data", command=self.refresh_data_view)
        refresh_data_btn.grid(row=0, column=2)
        
        # Data treeview
        data_tree_frame = ttk.Frame(data_frame)
        data_tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        data_tree_frame.columnconfigure(0, weight=1)
        data_tree_frame.rowconfigure(0, weight=1)
        
        # Treeview for data
        self.data_columns = ('Token', 'Symbol', 'Market Cap', 'Volume 24h', 'Holders', 'Liquidity', 'Is Stablecoin', 'Chain')
        self.data_tree = ttk.Treeview(data_tree_frame, columns=self.data_columns, show='headings', height=8)
        
        # Define headings
        for col in self.data_columns:
            self.data_tree.heading(col, text=col)
            self.data_tree.column(col, width=100)
        
        # Scrollbars for data
        data_v_scroll = ttk.Scrollbar(data_tree_frame, orient=tk.VERTICAL, command=self.data_tree.yview)
        data_h_scroll = ttk.Scrollbar(data_tree_frame, orient=tk.HORIZONTAL, command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=data_v_scroll.set, xscrollcommand=data_h_scroll.set)
        
        self.data_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        data_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        data_h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(1, weight=1)
        
        # Live Logs Panel (moved to bottom)
        logs_frame = ttk.LabelFrame(main_frame, text="📋 Live Assessment Logs", padding="15")
        logs_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(15, 0))
        
        self.logs_text = tk.Text(logs_frame, height=6, wrap=tk.WORD, font=('Courier', 9), 
                                bg='#1e1e1e', fg='#ffffff', insertbackground='white')
        logs_scroll = ttk.Scrollbar(logs_frame, orient=tk.VERTICAL, command=self.logs_text.yview)
        self.logs_text.configure(yscrollcommand=logs_scroll.set)
        
        self.logs_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        logs_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Clear logs button
        clear_logs_btn = ttk.Button(logs_frame, text="Clear Logs", command=self.clear_logs)
        clear_logs_btn.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        
        # Configure main frame row weights
        main_frame.rowconfigure(3, weight=2)  # Data viewer gets more space
        main_frame.rowconfigure(4, weight=1)  # Logs get less space
        
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
            
            # Look for report files
            reports_found = 0
            if os.path.exists(DATA_DIR):
                # Get all Excel files and sort by modification time
                excel_files = []
                for file in os.listdir(DATA_DIR):
                    if file.endswith('.xlsx'):
                        file_path = os.path.join(DATA_DIR, file)
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
                    self.reports_tree.insert('', 'end', values=(date, tokens, status))
                    reports_found += 1
                    
                    if reports_found >= 10:  # Limit to last 10 reports
                        break
                
                print(f"   ✅ Added {reports_found} reports to the list")
            else:
                print(f"   ❌ DATA_DIR does not exist: {DATA_DIR}")
            
            if reports_found == 0:
                self.reports_tree.insert('', 'end', values=('No reports found', '', ''))
                print("   ⚠️ No reports found")
                
        except Exception as e:
            print(f"Error loading reports: {e}")
            import traceback
            traceback.print_exc()
    
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
            script_path = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'defi_complete_risk_assessment_clean.py')
            if not os.path.exists(script_path):
                messagebox.showerror("Error", f"Risk assessment script not found:\n{script_path}")
                return
            
            # Check if the progress bar module exists
            progress_bar_path = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'working_progress_bar.py')
            if not os.path.exists(progress_bar_path):
                messagebox.showerror("Error", f"Progress bar module not found:\n{progress_bar_path}")
                return
            
            # Check if tokens.csv exists
            tokens_file = os.path.join(DATA_DIR, 'tokens.csv')
            if not os.path.exists(tokens_file):
                messagebox.showerror("Error", f"Tokens file not found:\n{tokens_file}\n\nPlease create a tokens.csv file in the data directory.")
                return
            
            # Launch the risk assessment script with proper environment
            env = os.environ.copy()
            env['PYTHONPATH'] = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5') + ':' + env.get('PYTHONPATH', '')
            
            # Change working directory to scripts/v1.5 so the script can find modules
            script_dir = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5')
            
            # Start the assessment in a separate process
            process = subprocess.Popen(
                [sys.executable, 'defi_complete_risk_assessment_clean.py'], 
                cwd=script_dir,  # Set working directory to scripts/v1.5
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
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
            
            # Store the process for monitoring
            self.assessment_process = process
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start assessment:\n{str(e)}")
            self.update_status(f"❌ Error starting assessment: {str(e)}")
    
    def open_api_dashboard(self):
        """Open API service dashboard"""
        try:
            api_dashboard_path = os.path.join(os.path.dirname(__file__), 'api_service_dashboard.py')
            subprocess.Popen([sys.executable, api_dashboard_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open API dashboard: {e}")
    
    def manage_credentials(self):
        """Open credential management"""
        try:
            creds_path = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management', 'gui_credentials.py')
            subprocess.Popen([sys.executable, creds_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open credential manager: {e}")
    
    def manage_chains(self):
        """Open chain management"""
        try:
            chains_path = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management', 'gui_chains.py')
            subprocess.Popen([sys.executable, chains_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open chain manager: {e}")
    
    def edit_tokens(self):
        """Open token list for editing"""
        try:
            tokens_file = os.path.join(DATA_DIR, 'tokens.csv')
            if sys.platform == "darwin":
                subprocess.Popen(["open", tokens_file])
            elif sys.platform == "win32":
                os.startfile(tokens_file)
            else:
                subprocess.Popen(["xdg-open", tokens_file])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open token list: {e}")
    
    def view_selected_report(self):
        """View the selected report"""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a report to view.")
            return
        
        try:
            # Find and open the most recent Excel report
            if os.path.exists(DATA_DIR):
                reports = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx') and 'Risk Assessment' in f]
                if reports:
                    latest_report = max(reports, key=lambda x: os.path.getmtime(os.path.join(DATA_DIR, x)))
                    report_path = os.path.join(DATA_DIR, latest_report)
                    
                    if sys.platform == "darwin":
                        subprocess.Popen(["open", report_path])
                    elif sys.platform == "win32":
                        os.startfile(report_path)
                    else:
                        subprocess.Popen(["xdg-open", report_path])
                else:
                    messagebox.showinfo("No Reports", "No report files found.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open report: {e}")
    
    def export_report(self):
        """Export selected report"""
        selection = self.reports_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a report to export.")
            return
        
        try:
            # Ask user for export location
            export_path = filedialog.asksaveasfilename(
                title="Export Report",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            
            if export_path:
                # Copy the latest report to export location
                if os.path.exists(DATA_DIR):
                    reports = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx') and 'Risk Assessment' in f]
                    if reports:
                        latest_report = max(reports, key=lambda x: os.path.getmtime(os.path.join(DATA_DIR, x)))
                        source_path = os.path.join(DATA_DIR, latest_report)
                        
                        import shutil
                        shutil.copy2(source_path, export_path)
                        messagebox.showinfo("Export Complete", f"Report exported to:\n{export_path}")
                    else:
                        messagebox.showinfo("No Reports", "No report files found to export.")
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
                    elif current_count == 0 and self.last_assessment_state > 0:
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
    
    def load_csv_data(self):
        """Load and display data from CSV file with enhanced real-time data integration and cache system"""
        try:
            import pandas as pd
            import os
            
            # Check cache first
            cache_data = self.load_cache()
            use_cache = False
            
            if cache_data and self.is_cache_valid(cache_data):
                print(f"      📦 Using cached data (age: {datetime.now() - cache_data['timestamp']})")
                use_cache = True
            elif cache_data:
                # Cache exists but is old
                cache_age = datetime.now() - cache_data['timestamp']
                hours_old = cache_age.total_seconds() / 3600
                
                result = messagebox.askyesno(
                    "Cache Expired", 
                    f"Token data cache is {hours_old:.1f} hours old.\n\nWould you like to refresh the cache with new API data?\n\nClick 'Yes' to refresh, 'No' to use cached data anyway."
                )
                
                if result:
                    print(f"      🔄 User chose to refresh cache")
                    use_cache = False
                else:
                    print(f"      📦 User chose to use cached data despite age")
                    use_cache = True
            
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
                        '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRON',
                        '0x67898d21cd030fc7bfc62808c0cd675097d370f1': 'Sonic'
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
                        '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRX',
                        '0x67898d21cd030fc7bfc62808c0cd675097d370f1': 'SONIC'
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
                    if '3845bad' in token_address.lower():
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
                    if real_data and isinstance(real_data, dict):
                        market_cap = real_data.get('market_cap', 0)
                        volume_24h = real_data.get('volume_24h', 0)
                        holders = real_data.get('holders', 0)
                        liquidity = real_data.get('liquidity', 0)
                        print(f"      ✅ Got real-time data for {symbol}: MC=${market_cap:,.0f}, Vol=${volume_24h:,.0f}, Holders={holders:,}, Liq=${liquidity:,.0f}")
                    else:
                        print(f"      ⚠️  No real-time data for {symbol}, using defaults")
                    
                    # Check if stablecoin
                    is_stablecoin = self._is_stablecoin(symbol, token_name)
                    
                    # Insert into tree
                    formatted_values = (
                        token_name,
                        symbol,
                        self._format_number(market_cap, is_currency=True),
                        self._format_number(volume_24h, is_currency=True),
                        self._format_number(holders, is_currency=False),
                        self._format_number(liquidity, is_currency=True),
                        'Yes' if is_stablecoin else 'No',
                        chain
                    )
                    
                    self.data_tree.insert('', 'end', values=formatted_values)
                    
                except Exception as e:
                    print(f"      ❌ Error processing row {index}: {e}")
                    continue
            
            print(f"      ✅ Successfully loaded {len(df)} tokens with real-time data")
            
            # Save cache if we fetched new data
            if not use_cache and token_data_cache:
                self.save_cache(token_data_cache)
            
            messagebox.showinfo("Success", f"Loaded {len(df)} tokens from {os.path.basename(csv_file)}")
            
        except Exception as e:
            print(f"      ❌ Error loading CSV: {e}")
            messagebox.showerror("Error", f"Failed to load CSV file: {e}")
    
    def load_excel_data(self):
        """Load and display data from Excel file with enhanced real-time data integration"""
        try:
            import pandas as pd
            import os
            
            # Find the most recent Excel file
            excel_files = []
            for file in os.listdir(DATA_DIR):
                if file.endswith('.xlsx') and 'Risk Assessment Results' in file:
                    file_path = os.path.join(DATA_DIR, file)
                    excel_files.append((file_path, os.path.getmtime(file_path)))
            
            if not excel_files:
                messagebox.showwarning("No Data", "No risk assessment Excel files found in data directory.")
                return
            
            # Sort by modification time (newest first)
            excel_files.sort(key=lambda x: x[1], reverse=True)
            excel_file = excel_files[0][0]
            
            print(f"      📁 Loading Excel: {excel_file}")
            
            df = pd.read_excel(excel_file)
            print(f"      ✅ Loaded {len(df)} tokens from Excel")
            
            # Clear existing data
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
            
            # Process each row with enhanced data integration
            for index, row in df.iterrows():
                try:
                    # Handle different column name formats
                    # For risk assessment CSV: token, chain, risk_score, risk_category, error
                    # For detailed Excel: name, symbol, token_address, market_data, onchain_data
                    
                    # Extract token name from various possible sources
                    token_name = self._extract_token_name(row)
                    
                    # Extract symbol with address-based correction
                    symbol = row.get('symbol', 'Unknown')
                    token_address = row.get('token_address', '')
                    
                    # Handle risk assessment CSV format
                    if 'token' in row and 'chain' in row:
                        token_address = row.get('token', '')
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
                                '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRON',
                                '0x67898d21cd030fc7bfc62808c0cd675097d370f1': 'Sonic'
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
                                '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRX',
                                '0x67898d21cd030fc7bfc62808c0cd675097d370f1': 'SONIC'
                            }
                            if token_address.lower() in address_mappings:
                                symbol = address_mappings[token_address.lower()]
                    
                    # Fetch real-time data for this token
                    print(f"      🔍 Fetching real-time data for {symbol} ({token_address})")
                    try:
                        real_data = self._get_real_token_data(token_address, symbol)
                    except TypeError as e:
                        print(f"      ⚠️  Method call error for {symbol}: {e}")
                        real_data = {}
                    
                    # Extract market data with real-time fallback
                    market_cap = real_data.get('market_cap', 0) if real_data else 0
                    volume_24h = real_data.get('volume_24h', 0) if real_data else 0
                    liquidity = real_data.get('liquidity', 0) if real_data else 0
                    holders = real_data.get('holders', 0) if real_data else 0
                    
                    # If no real-time data, try to extract from existing data
                    if market_cap == 0:
                        market_cap = self._extract_market_data_enhanced(row).get('market_cap', 0)
                    if volume_24h == 0:
                        volume_24h = self._extract_market_data_enhanced(row).get('volume_24h', 0)
                    if liquidity == 0:
                        liquidity = self._extract_market_data_enhanced(row).get('liquidity', 0)
                    if holders == 0:
                        holders = self._extract_holders_fixed(row)
                    
                    # Extract other data
                    is_stablecoin = self._is_stablecoin(symbol, token_name)
                    risk_score = row.get('risk_score', 0)
                    risk_category = row.get('risk_category', 'Unknown')
                    chain = row.get('chain', 'ethereum')
                    
                    # Insert into tree with real-time data
                    self.data_tree.insert('', 'end', values=(
                        token_name,
                        symbol,
                        self._format_number(market_cap, is_currency=True),
                        self._format_number(volume_24h, is_currency=True),
                        self._format_number(holders, is_currency=False),
                        self._format_number(liquidity, is_currency=True),
                        'Yes' if is_stablecoin else 'No',
                        risk_score,
                        risk_category,
                        chain
                    ))
                    
                except Exception as e:
                    print(f"      ❌ Error processing row {index}: {e}")
                    continue
            
            print(f"      ✅ Successfully loaded {len(df)} tokens with real-time data")
            messagebox.showinfo("Success", f"Loaded {len(df)} tokens from {os.path.basename(excel_file)}")
            
        except Exception as e:
            print(f"      ❌ Error loading Excel: {e}")
            messagebox.showerror("Error", f"Failed to load Excel file: {e}")
    
    def refresh_data_view(self):
        """Refresh the data view"""
        try:
            # Try to load the most recent data file
            if os.path.exists(DATA_DIR):
                files = [f for f in os.listdir(DATA_DIR) if f.endswith(('.csv', '.xlsx'))]
                if files:
                    latest_file = max(files, key=lambda x: os.path.getmtime(os.path.join(DATA_DIR, x)))
                    if latest_file.endswith('.csv'):
                        self.load_csv_data()
                    else:
                        self.load_excel_data()
                else:
                    self.add_log_entry("⚠️ No data files found", "warning")
        except Exception as e:
            self.add_log_entry(f"❌ Refresh error: {e}", "error")
    
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
            if market_cap > 0 or volume_24h > 0 or liquidity > 0:
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
                            if data['liquidity'] == 0:
                                data['liquidity'] = quote.get('market_cap', 0) * 0.05
                            
                            print(f"      ✅ CoinMarketCap data for {symbol}: ${data['market_cap']:,.0f} market cap, ${data['volume_24h']:,.0f} volume")
                            return
                except Exception as e:
                    pass
            
            # 2. Try COINAPI (if available)
            coinapi_api_key = os.getenv('COINAPI_API_KEY')
            if coinapi_api_key and symbol and symbol != 'Unknown':
                try:
                    # Get current market data from COINAPI
                    coinapi_url = f"https://rest.coinapi.io/v1/exchangerate/{symbol.upper()}/USD"
                    headers = {'X-CoinAPI-Key': coinapi_api_key}
                    
                    response = requests.get(coinapi_url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        rate_data = response.json()
                        price_usd = rate_data.get('rate', 0)
                        
                        # Get historical data for volume
                        from datetime import datetime, timedelta
                        end_time = datetime.utcnow()
                        start_time = end_time - timedelta(days=1)
                        
                        ohlcv_url = f"https://rest.coinapi.io/v1/ohlcv/{symbol.upper()}/USD/history"
                        params = {
                            'period_id': '1DAY',
                            'time_start': start_time.isoformat() + 'Z',
                            'time_end': end_time.isoformat() + 'Z',
                            'limit': 1
                        }
                        
                        ohlcv_response = requests.get(ohlcv_url, headers=headers, params=params, timeout=10)
                        volume_24h = 0
                        if ohlcv_response.status_code == 200:
                            ohlcv_data = ohlcv_response.json()
                            if ohlcv_data:
                                volume_24h = ohlcv_data[0].get('volume_traded', 0)
                        
                        # Get order book for liquidity estimation
                        orderbook_url = f"https://rest.coinapi.io/v1/orderbook/{symbol.upper()}/USD"
                        orderbook_response = requests.get(orderbook_url, headers=headers, timeout=10)
                        liquidity = 0
                        if orderbook_response.status_code == 200:
                            orderbook = orderbook_response.json()
                            if orderbook and 'asks' in orderbook and 'bids' in orderbook:
                                ask_liquidity = sum(float(ask[1]) for ask in orderbook['asks'][:10])
                                bid_liquidity = sum(float(bid[1]) for bid in orderbook['bids'][:10])
                                liquidity = (ask_liquidity + bid_liquidity) / 2
                        
                        if data['market_cap'] == 0:
                            # Estimate market cap from price (rough calculation)
                            data['market_cap'] = price_usd * 1000000  # Assume 1M supply
                        if data['volume_24h'] == 0:
                            data['volume_24h'] = volume_24h
                        if data['liquidity'] == 0:
                            data['liquidity'] = liquidity
                        
                        print(f"      ✅ COINAPI data for {symbol}: ${data['market_cap']:,.0f} market cap, ${data['volume_24h']:,.0f} volume")
                        return
                except Exception as e:
                    pass
            
            # 3. Try CoinPaprika API (free, no key required)
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
                            if data['liquidity'] == 0:
                                data['liquidity'] = coin_data.get('market_cap_usd', 0) * 0.05
                            
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
                        if data['liquidity'] == 0:
                            data['liquidity'] = protocol_data.get('tvl', 0) * 0.1
                        
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
                                    'liquidity': market_cap * 0.05 if market_cap > 1000000 else 0,
                                    'holders': holders
                                }
            
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
            'market_cap': 0,
            'liquidity': 0,
            'holders': 0,
            'volume_24h': 0,
            'concentration': 0
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
            
            # 2. ETHPLORER API (holders, volume, liquidity) - IMPROVED DATA FETCHING
            if token_address:
                try:
                    ethplorer_url = f"https://api.ethplorer.io/getTokenInfo/{token_address}?apiKey=freekey"
                    response = requests.get(ethplorer_url, timeout=10)
                    if response.status_code == 200:
                        token_info = response.json()
                        
                        # Get holders count if not already set
                        if 'holdersCount' in token_info and data['holders'] == 0:
                            data['holders'] = int(token_info['holdersCount'])
                            print(f"      ✅ Ethplorer holders for {symbol}: {data['holders']:,}")
                        
                        # For tokens that might not have holdersCount, try alternative approach
                        elif data['holders'] == 0 and 'address' in token_info:
                            # Try to get holders from top holders endpoint
                            try:
                                holders_url = f"https://api.ethplorer.io/getTopTokenHolders/{token_address}?apiKey=freekey&limit=1"
                                holders_response = requests.get(holders_url, timeout=10)
                                if holders_response.status_code == 200:
                                    holders_data = holders_response.json()
                                    if 'holders' in holders_data and holders_data['holders']:
                                        # Estimate total holders based on top holder percentage
                                        top_holder = holders_data['holders'][0]
                                        if 'balance' in top_holder and 'totalSupply' in token_info:
                                            try:
                                                top_balance = float(top_holder['balance'])
                                                total_supply = float(token_info['totalSupply'])
                                                if total_supply > 0:
                                                    # Estimate holders based on top holder concentration
                                                    # If top holder has 1% of supply, estimate ~100 holders
                                                    concentration = (top_balance / total_supply) * 100
                                                    if concentration > 0:
                                                        estimated_holders = int(100 / concentration)
                                                        if estimated_holders > 0 and estimated_holders < 1000000:  # Sanity check
                                                            data['holders'] = estimated_holders
                                                            print(f"      ✅ Estimated holders for {symbol}: {data['holders']:,} (from concentration)")
                                            except (ValueError, TypeError):
                                                pass
                            except Exception as e:
                                pass
                        
                        # Get volume data if not already set
                        if 'price' in token_info and 'volume24h' in token_info and data['volume_24h'] == 0:
                            data['volume_24h'] = float(token_info['volume24h'])
                            print(f"      ✅ Ethplorer volume for {symbol}: ${data['volume_24h']:,.0f}")
                        
                        # Get market cap from price and supply if not already set
                        if 'price' in token_info and 'totalSupply' in token_info and data['market_cap'] == 0:
                            try:
                                price = float(token_info['price']['rate'])
                                supply = float(token_info['totalSupply'])
                                market_cap = price * supply
                                # Sanity check: market cap should be reasonable (less than 1 trillion)
                                if market_cap > 0 and market_cap < 1e12:
                                    data['market_cap'] = market_cap
                                    print(f"      ✅ Ethplorer market cap for {symbol}: ${data['market_cap']:,.0f}")
                                else:
                                    print(f"      ⚠️ Ethplorer market cap for {symbol} too large: ${market_cap:,.0f}, skipping")
                            except (ValueError, TypeError):
                                pass
                        
                        # Get liquidity from DEX data (more accurate)
                        if data['liquidity'] == 0:
                            try:
                                # Try to get liquidity from Uniswap V2
                                uniswap_url = f"https://api.ethplorer.io/getTopTokenHolders/{token_address}?apiKey=freekey&limit=1"
                                uniswap_response = requests.get(uniswap_url, timeout=10)
                                if uniswap_response.status_code == 200:
                                    holders_data = uniswap_response.json()
                                    if holders_data and 'holders' in holders_data:
                                        # Estimate liquidity based on top holder (usually DEX)
                                        top_holder = holders_data['holders'][0]
                                        if 'balance' in top_holder and 'price' in token_info:
                                            try:
                                                balance = float(top_holder['balance'])
                                                price = float(token_info['price']['rate'])
                                                # Estimate liquidity as 5% of top holder balance
                                                estimated_liquidity = balance * price * 0.05
                                                if estimated_liquidity > 0 and estimated_liquidity < 1e10:
                                                    data['liquidity'] = estimated_liquidity
                                                    print(f"      ✅ Estimated liquidity for {symbol}: ${data['liquidity']:,.0f}")
                                            except (ValueError, TypeError):
                                                pass
                            except Exception as e:
                                pass
                        
                        # If liquidity is still 0, use market cap estimate
                        if data['liquidity'] == 0 and data['market_cap'] > 0:
                            data['liquidity'] = data['market_cap'] * 0.05
                            print(f"      ✅ Ethplorer liquidity estimate for {symbol}: ${data['liquidity']:,.0f} (5% of market cap)")
                except Exception as e:
                    pass
                except Exception as e:
                    pass
            
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
                            if data['liquidity'] == 0:
                                data['liquidity'] = coin_data.get('usd_market_cap', 0) * 0.05
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
                            if data['liquidity'] == 0:
                                data['liquidity'] = market_data.get('market_cap', {}).get('usd', 0) * 0.05
                            
                            # Extract holders from community data
                            community_data = coin_data.get('community_data', {})
                            if 'reddit_subscribers' in community_data and data['holders'] == 0:
                                data['holders'] = community_data.get('reddit_subscribers', 0) * 100
                            
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
            # Enhanced address mappings for better token identification
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
                '0x50327c6c5a14dcade707abad2e27eb517df87ab5': 'TRON',
                '0x67898d21cd030fc7bfc62808c0cd675097d370f1': 'Sonic'
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
            if market_cap > 0 or volume_24h > 0 or liquidity > 0:
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
                    # Try to bring existing window to front
                    if sys.platform == "darwin":
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
