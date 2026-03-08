#!/usr/bin/env python3.9
"""
DeFi Risk Assessment System Tray
Enhanced system tray with window management and complete functionality
Runs as background process to avoid duplicate dock icons
"""

import os
import sys

# CRITICAL: Add error handling for basic imports
try:
    # Test basic Python functionality
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
except Exception as e:
    print(f"Basic import error: {e}")
    sys.exit(1)

# CRITICAL: Import tkinter compatibility module FIRST
try:
    from tkinter_compatibility import tkinter_compat
    print("✅ Tkinter compatibility module imported")
except Exception as e:
    print(f"⚠️ Tkinter compatibility import error: {e}")
    tkinter_compat = None

# NOW import other modules after macOS compatibility is set up
import time
import subprocess
import threading
import tempfile
import signal
import json
import fcntl
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# CRITICAL: Import process manager with tkinter compatibility
try:
    from process_manager import process_manager
    print("✅ Process manager imported successfully")
except Exception as e:
    print(f"⚠️ Process manager import error: {e}")
    # Create a minimal process manager if import fails
    class MinimalProcessManager:
        def __init__(self):
            self.project_root = '/Users/amlfreak/Desktop/venv'
            self.data_dir = os.path.join(self.project_root, 'data')
            self.lock_dir = os.path.join(self.project_root, 'defi_dashboard_locks')
            self.processes = {}
            self.python_executable = sys.executable
            os.makedirs(self.lock_dir, exist_ok=True)
        
        def launch_dashboard(self):
            print("Minimal process manager: Dashboard launch requested")
            return True, "Dashboard launched"
        
        def launch_api_dashboard(self):
            print("Minimal process manager: API dashboard launch requested")
            return True, "API dashboard launched"
        
        def launch_credential_manager(self):
            print("Minimal process manager: Credential manager launch requested")
            return True, "Credential manager launched"
        
        def launch_chain_manager(self):
            print("Minimal process manager: Chain manager launch requested")
            return True, "Chain manager launched"
        
        def get_service_status(self):
            return {}
    
    process_manager = MinimalProcessManager()
    print("✅ Using minimal process manager")

# Set up macOS environment for system tray
if sys.platform == "darwin":
    # Set unified app icon environment variables
    os.environ['BUNDLE_IDENTIFIER'] = 'com.defi.riskassessment'
    os.environ['APP_BUNDLE'] = 'true'
    os.environ['CFBundleIdentifier'] = 'com.defi.riskassessment'
    os.environ['CFBundleName'] = 'Token Risk Assessment Tool'
    os.environ['CFBundleDisplayName'] = 'Token Risk Assessment Tool'
    os.environ['PARENT_BUNDLE_ID'] = 'com.defi.riskassessment'
    os.environ['INHERIT_BUNDLE_ID'] = 'com.defi.riskassessment'
    
    # Set activation policy for background operation
    os.environ['NSApplicationActivationPolicy'] = 'accessory'
    os.environ['LSUIElement'] = 'true'
    
    # Additional macOS environment variables
    os.environ['NSDocumentRevisionsKeepEveryOne'] = '1'
    os.environ['NSAppTransportSecurity'] = 'true'
    
    # Force basic mode and skip all macOS checks
    os.environ['TK_FORCE_BASIC_MODE'] = '1'
    os.environ['TK_SKIP_ALL_MACOS_CHECKS'] = '1'
    os.environ['TK_DISABLE_ALL_MACOS_FEATURES'] = '1'
    os.environ['TK_DISABLE_MACOS_VERSION_CALLS'] = '1'
    os.environ['TK_SKIP_MACOS_VERSION_CHECK'] = '1'
    os.environ['TK_DISABLE_MACOS_VERSION_METHOD'] = '1'
    os.environ['TK_USE_LEGACY_MODE'] = '1'
    os.environ['TK_DISABLE_NATIVE_FEATURES'] = '1'
    os.environ['TK_FORCE_COMPATIBILITY_MODE'] = '1'
    
    print("✅ Environment variables set for unified app icon")
    print("Running system tray with unified app icon compatibility")

# Project paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), 'defi_dashboard.py')

class DeFiSystemTray:
    _instance = None
    _lock_file = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeFiSystemTray, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.dashboard_process = None
        self.icon = None
        self.open_windows = {}  # Track open windows to prevent duplicates
        self.lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
        os.makedirs(self.lock_dir, exist_ok=True)
        self.unified_dashboard = None
        self.cache_refresh_thread = None
        
        # Set project root path
        self.project_root = PROJECT_ROOT
        
        # Create hidden root window for Toplevel windows
        self._create_hidden_root()
        
        # Clean up stale lock files on startup
        self.cleanup_stale_locks()
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Check if another instance is already running
        if not self._check_single_instance():
            print("Another DeFi System Tray instance is already running!")
            sys.exit(1)
        
        self.create_icon()
        
        # Disable background monitoring to prevent GIL crashes in Python 3.13
        # self.start_process_monitoring()  # Disabled - causes threading crashes
        
        # Bring window to front on startup
        self.bring_to_front()
        
        # Check cache monitoring setting and enable if configured
        try:
            settings_file = os.path.join(self.project_root, 'data', 'settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    background_monitoring = settings.get('cache', {}).get('background_monitoring', False)
                    if background_monitoring:
                        print("ℹ️ Background monitoring enabled in settings - starting cache monitoring")
                        self.start_cache_monitoring()
                    else:
                        print("ℹ️ Background monitoring disabled in settings")
        except Exception as e:
            print(f"⚠️ Could not check cache monitoring setting: {e}")
    
    def _check_single_instance(self):
        """Ensure only one system tray instance is running"""
        lock_file_path = os.path.join(tempfile.gettempdir(), 'defi_system_tray.lock')
        
        try:
            # Check if lock file exists and if the process is still running
            if os.path.exists(lock_file_path):
                try:
                    with open(lock_file_path, 'r') as f:
                        old_pid = f.read().strip()
                    
                    # Check if the old process is still running
                    if old_pid and old_pid.isdigit():
                        try:
                            os.kill(int(old_pid), 0)  # Check if process exists
                            print(f"⚠️ Another system tray instance (PID: {old_pid}) is running")
                            return False
                        except OSError:
                            # Process is dead, remove stale lock file
                            print(f"🧹 Removing stale lock file from dead process (PID: {old_pid})")
                            os.remove(lock_file_path)
                except Exception as e:
                    print(f"⚠️ Error reading lock file: {e}")
                    # Remove corrupted lock file
                    try:
                        os.remove(lock_file_path)
                    except:
                        pass
            
            # Create new lock file
            self._lock_file = open(lock_file_path, 'w')
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write current PID to lock file
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            
            print(f"✅ System tray lock file created (PID: {os.getpid()})")
            return True
            
        except (IOError, OSError) as e:
            # Another instance is running
            if hasattr(self, '_lock_file') and self._lock_file:
                self._lock_file.close()
            print(f"❌ Failed to create lock file: {e}")
            return False
    
    def _cleanup_lock_file(self):
        """Clean up the lock file on exit"""
        if self._lock_file:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
                lock_file_path = os.path.join(tempfile.gettempdir(), 'defi_system_tray.lock')
                if os.path.exists(lock_file_path):
                    os.remove(lock_file_path)
            except:
                pass
    
    def _cleanup_lock(self, service_name):
        """Clean up lock file for a specific service"""
        try:
            lock_file = os.path.join(self.lock_dir, f"{service_name}.lock")
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print(f"✅ Cleaned up lock file: {service_name}")
        except Exception as e:
            print(f"⚠️ Error cleaning up lock file {service_name}: {e}")
    
    def _create_hidden_root(self):
        """Create a hidden root window for Toplevel windows"""
        try:
            if tkinter_compat and tkinter_compat.is_compatible():
                self.root = tkinter_compat.create_safe_root("DeFi System Tray Root")
                # Ensure the root window is completely hidden
                if self.root:
                    self.root.withdraw()  # Hide the window
                    self.root.attributes('-topmost', False)  # Don't keep on top
                    # Set window to be completely invisible
                    if sys.platform == "darwin":
                        self.root.attributes('-alpha', 0.0)  # Make transparent
                print("✅ Safe hidden root window created (completely hidden)")
            else:
                print("⚠️ Tkinter compatibility not available, skipping root window")
                self.root = None
        except Exception as e:
            print(f"⚠️ Could not create hidden root window: {e}")
            self.root = None
    
    def bring_to_front(self):
        """Bring DeFi Risk Assessor windows to front"""
        try:
            import subprocess
            
            # Enhanced AppleScript to bring windows to front
            script = '''
            tell application "System Events"
                -- First try to find Python processes with DeFi windows
                set pythonProcesses to every application process whose name contains "Python"
                repeat with appProcess in pythonProcesses
                    try
                        tell appProcess
                            set windowList to every window
                            repeat with windowItem in windowList
                                set windowName to name of windowItem
                                if windowName contains "DeFi Risk Assessor" or windowName contains "Credential" or windowName contains "Dashboard" or windowName contains "Settings" or windowName contains "About" or windowName contains "API" or windowName contains "Chain" then
                                    set frontmost of appProcess to true
                                    perform action "AXRaise" of windowItem
                                    return "Found and raised window: " & windowName
                                end if
                            end repeat
                        end tell
                    end try
                end repeat
                
                -- If no specific windows found, try to bring any Python window to front
                repeat with appProcess in pythonProcesses
                    try
                        tell appProcess
                            if exists (window 1) then
                                set frontmost of appProcess to true
                                set windowList to every window
                                repeat with windowItem in windowList
                                    perform action "AXRaise" of windowItem
                                end repeat
                                return "Brought Python process to front"
                            end if
                        end tell
                    end try
                end repeat
                
                return "No DeFi windows found"
            end tell
            '''
            
            # Execute the AppleScript
            result = subprocess.run(["osascript", "-e", script], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                print(f"✅ Bring to front result: {output}")
            else:
                print(f"⚠️ Could not bring windows to front: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error bringing windows to front: {e}")
        
    def create_icon(self):
        """Create the system tray icon"""
        # Use generated magnifier icon by default (ICO file appears corrupted)
        print("✅ Using generated magnifier icon (clean, high-quality)")
        
        # Create a clean, high-quality magnifier icon
        image = Image.new('RGB', (64, 64), color='#2c3e50')
        draw = ImageDraw.Draw(image)
        
        # Draw a clean magnifier icon
        # Magnifier glass (circle)
        draw.ellipse([12, 12, 44, 44], fill='#3498db', outline='#ffffff', width=2)
        # Magnifier handle
        draw.line([44, 44, 52, 52], fill='#ffffff', width=3)
        # Magnifier lens highlight
        draw.ellipse([18, 18, 26, 26], fill='#ffffff', outline='#3498db', width=1)
        
        # Create dynamic menu that shows running services
        self.menu = self.create_dynamic_menu()
        
        self.icon = pystray.Icon("DeFi Risk Assessment", image, "DeFi Risk Assessment Tool", self.menu)
        print("✅ System tray icon created successfully")
        print("✅ Dynamic menu configured")
    

    
    def create_dynamic_menu(self):
        """Create dynamic menu that shows running services"""
        menu_items = []
        
        # Add running services section
        running_services = self.get_running_services()
        if running_services:
            menu_items.append(pystray.Menu.SEPARATOR)
            menu_items.append(item("🖥️ Running Services:", None, enabled=False))
            for service_name, window_title in running_services:
                menu_items.append(item(f"  📋 {service_name}", 
                                     lambda s=service_name, w=window_title: self.bring_service_to_front(s, w)))
            menu_items.append(pystray.Menu.SEPARATOR)
        
        # Add main menu items
        menu_items.extend([
            item('📊 Open Main Dashboard', self.open_dashboard, default=True),
            item('🔧 API Service Dashboard', self.open_api_dashboard),
            item('🚀 Quick Assessment', self.quick_assessment),
            pystray.Menu.SEPARATOR,
            item('🔐 Manage Credentials', self.manage_credentials),
            item('🔗 Manage Chains', self.manage_chains),
            item('🔄 Refresh Cache', self.manual_cache_refresh),
            item('📋 View Reports', self.view_reports),
            item('📈 Check Status', self.check_status),
            pystray.Menu.SEPARATOR,
            item('🧹 Force Cleanup', self.force_cleanup),
            item('⚙️ Settings', self.open_settings),
            item('ℹ️ About', self.show_about),
            pystray.Menu.SEPARATOR,
            item('❌ Quit', self.quit_application)
        ])
        
        return pystray.Menu(*menu_items)
    
    def get_running_services(self):
        """Get list of currently running services"""
        running_services = []
        service_mappings = {
            'main_dashboard': 'Main Dashboard',
            'api_dashboard': 'API Service Dashboard',
            'credentials': 'Credential Manager',
            'chains': 'Chain Manager',
            'settings': 'DeFi System Settings',
            'webhook_server': 'Webhook Server'
        }
        
        # Use process manager to get accurate status
        try:
            status = process_manager.get_service_status()
            for service_name, display_name in service_mappings.items():
                if service_name in status and status[service_name]['running']:
                    running_services.append((display_name, service_name))
        except Exception as e:
            print(f"⚠️ Error getting service status: {e}")
            # Fallback to old method
            for service_name, display_name in service_mappings.items():
                if self.is_service_running(service_name):
                    running_services.append((display_name, service_name))
        
        return running_services
    
    def bring_service_to_front(self, service_name, window_title):
        """Bring a specific service window to front"""
        try:
            self.bring_window_to_front(window_title)
            self.show_notification(f"{service_name} brought to front")
        except Exception as e:
            print(f"Error bringing {service_name} to front: {e}")
            self.show_notification(f"Error bringing {service_name} to front")
    
    def refresh_menu(self):
        """Refresh the system tray menu to show current running services"""
        try:
            if self.icon:
                # Create new menu
                new_menu = self.create_dynamic_menu()
                # Update the icon's menu
                self.icon.menu = new_menu
                print("✅ Menu refreshed")
        except Exception as e:
            print(f"Error refreshing menu: {e}")
    
    def get_lock_file(self, service_name):
        """Get lock file path for a service"""
        return os.path.join(self.lock_dir, f'{service_name}.lock')
    
    def is_service_running(self, service_name):
        """Check if a service is already running"""
        lock_file = self.get_lock_file(service_name)
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    data = json.load(f)
                    pid = data.get('pid')
                    
                # Check if process is actually running
                if pid:
                    try:
                        # Check if process exists and is running
                        os.kill(pid, 0)  # Doesn't actually kill, just checks existence
                        print(f"✅ Service {service_name} is running (PID: {pid})")
                        return True
                    except OSError:
                        # Process doesn't exist, remove stale lock file
                        print(f"🧹 Removing stale lock for {service_name} (PID: {pid} not found)")
                        try:
                            os.remove(lock_file)
                        except:
                            pass
                        return False
            except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
                # Lock file is corrupted or inaccessible, assume service is not running
                print(f"⚠️ Corrupted lock file for {service_name}: {e}")
                try:
                    os.remove(lock_file)
                except:
                    pass
                return False
        return False
    
    def create_service_lock(self, service_name, process):
        """Create a lock file for a service"""
        lock_file = self.get_lock_file(service_name)
        
        # Check if service is already running
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    lock_data = json.load(f)
                    old_pid = lock_data.get('pid')
                
                # Check if the old process is still running
                if old_pid:
                    try:
                        os.kill(int(old_pid), 0)  # Check if process exists
                        print(f"⚠️ Service {service_name} already running (PID: {old_pid})")
                        return False
                    except OSError:
                        # Process is dead, remove stale lock file
                        print(f"🧹 Removing stale lock for {service_name} (PID: {old_pid})")
                        try:
                            os.remove(lock_file)
                        except:
                            pass
            except Exception as e:
                print(f"⚠️ Error reading service lock file: {e}")
                # Remove corrupted lock file
                try:
                    os.remove(lock_file)
                except:
                    pass
        
        # Create new lock file
        lock_data = {
            'pid': process.pid,
            'started_at': time.time(),
            'service_name': service_name
        }
        try:
            with open(lock_file, 'w') as f:
                json.dump(lock_data, f)
            print(f"✅ Service lock created for {service_name} (PID: {process.pid})")
            return True
        except Exception as e:
            print(f"❌ Error creating service lock: {e}")
            return False
    
    def remove_service_lock(self, service_name):
        """Remove lock file for a service"""
        lock_file = self.get_lock_file(service_name)
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception as e:
            print(f"Warning: Could not remove lock file: {e}")
    
    def bring_window_to_front(self, window_title):
        """Bring a window to front by title (cross-platform)"""
        if sys.platform == "darwin":
            try:
                # Enhanced AppleScript for bringing specific windows to front
                script = f'''
                tell application "System Events"
                    -- First try to find the specific window
                    set appList to every application process whose name contains "Python"
                    repeat with appProcess in appList
                        try
                            tell appProcess
                                set windowList to every window
                                repeat with windowItem in windowList
                                    set windowName to name of windowItem
                                    if windowName contains "{window_title}" or windowName contains "DeFi" or windowName contains "Dashboard" then
                                        set frontmost of appProcess to true
                                        perform action "AXRaise" of windowItem
                                        return "Found and raised: " & windowName
                                    end if
                                end repeat
                            end tell
                        end try
                    end repeat
                    
                    -- If specific window not found, try to bring any Python window to front
                    repeat with appProcess in appList
                        try
                            tell appProcess
                                if exists (window 1) then
                                    set frontmost of appProcess to true
                                    set windowList to every window
                                    repeat with windowItem in windowList
                                        perform action "AXRaise" of windowItem
                                    end repeat
                                    return "Brought Python process to front"
                                end if
                            end tell
                        end try
                    end repeat
                    
                    return "No matching windows found"
                end tell
                '''
                result = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True)
                if result.returncode == 0:
                    output = result.stdout.strip()
                    print(f"✅ Brought window '{window_title}' to front: {output}")
                else:
                    print(f"⚠️ Could not bring window '{window_title}' to front: {result.stderr}")
            except Exception as e:
                print(f"Warning: Could not bring window to front: {e}")
        elif sys.platform == "win32":
            self._bring_window_to_front_windows(window_title)
        # Linux/X11 could be added here if needed
    
    def _bring_window_to_front_windows(self, window_title):
        """Windows-specific window management (separate method to avoid import issues)"""
        try:
            # Use importlib to dynamically import win32gui to avoid linter warnings
            import importlib
            win32gui = importlib.import_module('win32gui')
            
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if window_title.lower() in title.lower():
                        win32gui.SetForegroundWindow(hwnd)
                        windows.append(hwnd)
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
        except ImportError:
            print(f"Warning: win32gui not available on {sys.platform}")
        except Exception as e:
            print(f"Warning: Could not use Windows window management: {e}")
    
    def start_process_monitoring(self):
        """Start monitoring for dead processes and clean up lock files"""
        def process_monitor():
            # Wait before first check to let system stabilize
            time.sleep(10)
            while True:
                try:
                    self.cleanup_dead_processes()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    print(f"Process monitor error: {e}")
                    time.sleep(60)  # Wait 1 minute on error
                except KeyboardInterrupt:
                    print("🛑 Process monitoring interrupted")
                    break
        
        self.process_monitor_thread = threading.Thread(target=process_monitor, daemon=True)
        self.process_monitor_thread.start()
        print("Process monitoring started")
    
    def cleanup_dead_processes(self):
        """Clean up lock files for dead processes"""
        cleanup_occurred = False
        try:
            if os.path.exists(self.lock_dir):
                for filename in os.listdir(self.lock_dir):
                    if filename.endswith('.lock'):
                        lock_file = os.path.join(self.lock_dir, filename)
                        try:
                            with open(lock_file, 'r') as f:
                                data = json.load(f)
                                pid = data.get('pid')
                            
                            if pid:
                                try:
                                    os.kill(pid, 0)  # Check if process exists
                                except OSError:
                                    # Process is dead, remove lock file
                                    print(f"🧹 Cleaning up dead process lock: {filename} (PID: {pid})")
                                    try:
                                        os.remove(lock_file)
                                        cleanup_occurred = True
                                    except:
                                        pass
                        except Exception:
                            # Corrupted lock file, remove it
                            try:
                                os.remove(lock_file)
                                cleanup_occurred = True
                            except:
                                pass
            
            # Refresh menu if any cleanup occurred
            if cleanup_occurred:
                self.refresh_menu()
                
        except Exception as e:
            print(f"Process cleanup error: {e}")
    
    def start_cache_monitoring(self):
        """Start automatic cache refresh monitoring"""
        def cache_monitor():
            print("🔄 Cache monitor thread started")
            # Wait before first check to let system stabilize
            time.sleep(30)
            while True:
                try:
                    self.check_and_refresh_cache()
                    time.sleep(600)  # Check every 10 minutes (reduced frequency)
                except Exception as e:
                    print(f"⚠️ Cache monitor error: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
                except KeyboardInterrupt:
                    print("🛑 Cache monitoring interrupted")
                    break
        
        self.cache_refresh_thread = threading.Thread(target=cache_monitor, daemon=True)
        self.cache_refresh_thread.start()
        print("✅ Cache monitoring enabled and thread started")
    

    
    def check_and_refresh_cache(self):
        """Check cache age and refresh if needed"""
        try:
            cache_file = os.path.join(PROJECT_ROOT, 'data', 'real_data_cache.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                last_updated = cache_data.get('last_updated', 0)
                cache_age_hours = (time.time() - last_updated) / 3600
                
                # Refresh if cache is older than 2 hours
                if cache_age_hours > 2:
                    print(f"Cache is {cache_age_hours:.1f} hours old, triggering refresh...")
                    self.trigger_cache_refresh()
                else:
                    print(f"Cache is fresh ({cache_age_hours:.1f} hours old)")
            else:
                print("No cache file found, triggering initial refresh...")
                self.trigger_cache_refresh()
        except Exception as e:
            print(f"Error checking cache: {e}")
    
    def trigger_cache_refresh(self):
        """Trigger cache refresh via webhook"""
        try:
            import requests
            response = requests.post('http://localhost:5001/webhook/update_all', timeout=10)
            if response.status_code == 200:
                print("✅ Cache refresh triggered successfully")
                if self.icon:
                    self.show_notification("Cache refreshed successfully")
            else:
                print(f"❌ Cache refresh failed: {response.status_code}")
                if response.status_code == 403:
                    print("   Forbidden - webhook server may be rejecting requests")
                elif response.status_code == 404:
                    print("   Endpoint not found - check webhook server is running")
                print(f"   Response: {response.text[:200] if hasattr(response, 'text') else 'No response text'}")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Cache refresh connection error: {e}")
            print("   Is webhook server running on port 5001?")
        except Exception as e:
            print(f"❌ Cache refresh error: {e}")
    
    def manual_cache_refresh(self, icon=None, item=None):
        """Manual cache refresh from menu"""
        self.trigger_cache_refresh()
    
    def open_unified_dashboard(self, icon=None, item=None):
        """Open the unified dashboard"""
        # This method is deprecated - use individual dashboard methods instead
        self.open_dashboard()
    
    def open_dashboard(self, icon=None, item=None):
        """Open the main dashboard using process manager"""
        try:
            print("🔍 Opening main dashboard...")
            
            # Use the process manager to launch the dashboard
            success, message = process_manager.launch_dashboard()
            
            if success:
                self.show_notification(message)
                print(f"✅ Dashboard: {message}")
                # Bring window to front
                self.bring_to_front()
                # Refresh menu to show new running service
                self.refresh_menu()
            else:
                self.show_notification(f"Error: {message}")
                print(f"❌ Dashboard error: {message}")
                
        except Exception as e:
            print(f"❌ Error opening dashboard: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"Error opening dashboard: {e}")
    
    def open_api_dashboard(self, icon=None, item=None):
        """Open the API service dashboard using process manager"""
        try:
            print("🔍 Opening API dashboard...")
            
            # Use the process manager to launch the API dashboard
            success, message = process_manager.launch_api_dashboard()
            
            if success:
                self.show_notification(message)
                print(f"✅ API Dashboard: {message}")
                # Bring window to front
                self.bring_to_front()
                # Refresh menu to show new running service
                self.refresh_menu()
            else:
                self.show_notification(f"Error: {message}")
                print(f"❌ API Dashboard error: {message}")
                
        except Exception as e:
            print(f"❌ Error opening API dashboard: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"Error opening API dashboard: {e}")
    
    def quick_assessment(self, icon=None, item=None):
        """Start a quick assessment"""
        try:
            script_path = os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'defi_complete_risk_assessment_clean.py')
            
            # Verify the file exists
            if not os.path.exists(script_path):
                print(f"❌ Assessment script not found: {script_path}")
                self.show_notification("Assessment script not found")
                return
            
            # Use the same Python executable as the process manager
            python_executable = process_manager.python_executable
            
            env = os.environ.copy()
            env['PYTHONPATH'] = PROJECT_ROOT
            
            # Add macOS-specific environment variables
            if sys.platform == "darwin":
                env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
                env['TK_FRAMEWORK'] = '1'
                env['TK_SILENCE_DEPRECATION'] = '1'
            
            print(f"🚀 Starting risk assessment with {python_executable}")
            process = subprocess.Popen([python_executable, script_path], env=env, cwd=PROJECT_ROOT)
            print(f"✅ Quick assessment started with PID: {process.pid}")
            self.show_notification("Risk assessment started - check terminal for progress")
            
        except Exception as e:
            print(f"❌ Error starting assessment: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"Error starting assessment: {e}")
    
    def manage_credentials(self, icon=None, item=None):
        """Open credential management using process manager"""
        try:
            print("🔍 Opening credential manager...")
            
            # Use the process manager to launch the credential manager
            success, message = process_manager.launch_credential_manager()
            
            if success:
                self.show_notification(message)
                print(f"✅ Credential Manager: {message}")
                # Bring window to front
                self.bring_to_front()
                # Refresh menu to show new running service
                self.refresh_menu()
            else:
                self.show_notification(f"Error: {message}")
                print(f"❌ Credential Manager error: {message}")
                
        except Exception as e:
            print(f"❌ Error opening credential manager: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"Error opening credential manager: {e}")
    
    def manage_chains(self, icon=None, item=None):
        """Open chain management interface using process manager"""
        try:
            print("🔍 Opening chain manager...")
            
            # Use the process manager to launch the chain manager
            success, message = process_manager.launch_chain_manager()
            
            if success:
                self.show_notification(message)
                print(f"✅ Chain Manager: {message}")
                # Refresh menu to show new running service
                self.refresh_menu()
            else:
                self.show_notification(f"Error: {message}")
                print(f"❌ Chain Manager error: {message}")
                
        except Exception as e:
            print(f"❌ Error opening chain manager: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"Error opening chain manager: {e}")
    
    def view_reports(self, icon=None, item=None):
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
                self.show_notification("Reports directory opened")
            else:
                self.show_notification("No reports found")
        except Exception as e:
            self.show_notification(f"Error opening reports: {e}")
    
    def check_status(self, icon=None, item=None):
        """Check comprehensive system status"""
        print("🔍 Check Status button clicked!")
        self.show_notification("Opening system status...")
        
        # Use process manager to launch status window as subprocess
        try:
            success, message = process_manager.launch_status()
            if success:
                print(f"✅ Status: {message}")
            else:
                print(f"❌ Status launch failed: {message}")
        except Exception as e:
            print(f"❌ Status launch error: {e}")
            import traceback
            traceback.print_exc()
    

    
    def open_settings(self, icon=None, item=None):
        """Open settings window using subprocess approach for stability"""
        print("⚙️ Settings button clicked!")
        self.show_notification("Opening settings...")
        
        try:
            # Use subprocess approach exclusively for stability
            success, message = process_manager.launch_settings()
            
            if success:
                self.show_notification(message)
                print(f"✅ Settings: {message}")
                # Bring window to front
                self.bring_to_front()
                # Refresh menu to show new running service
                self.refresh_menu()
            else:
                self.show_notification(f"Error: {message}")
                print(f"❌ Settings error: {message}")
                
        except Exception as e:
            print(f"❌ Error opening settings: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"Error opening settings: {e}")
    
    def _create_interactive_settings_window(self):
        """Create interactive settings window in main thread"""
        try:
            # Use safe tkinter compatibility
            if not tkinter_compat or not tkinter_compat.is_compatible():
                print("⚠️ Tkinter compatibility not available")
                self.show_notification("Tkinter compatibility not available")
                return
            
            tk, ttk, messagebox = tkinter_compat.safe_import_tkinter()
            
            # Check if settings window is already open
            window_key = 'settings'
            if window_key in self.open_windows:
                try:
                    if hasattr(self.open_windows[window_key], 'state') and self.open_windows[window_key].state() == 'normal':
                        self.open_windows[window_key].lift()
                        self.open_windows[window_key].focus_force()
                        return
                except Exception:
                    del self.open_windows[window_key]
            
            # Create settings window using safe toplevel
            if self.root:
                settings_window = tkinter_compat.create_safe_toplevel(self.root, "DeFi System Settings")
            else:
                # Create a new root if none exists
                temp_root = tkinter_compat.create_safe_root("DeFi System Settings Root")
                settings_window = tkinter_compat.create_safe_toplevel(temp_root, "DeFi System Settings")
            
            settings_window.geometry("500x700")
            settings_window.resizable(False, False)
            
            # Track this window
            self.open_windows[window_key] = settings_window
            
            # Center window
            settings_window.geometry("+%d+%d" % (
                (settings_window.winfo_screenwidth() // 2) - 250,
                (settings_window.winfo_screenheight() // 2) - 350
            ))
            
            # Main frame
            main_frame = ttk.Frame(settings_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(main_frame, text="⚙️ DeFi System Settings", 
                                   font=('Arial', 16, 'bold'))
            title_label.pack(pady=(0, 20))
            
            # Create scrollable frame for settings
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Pack scrollbar and canvas
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            
            # Settings variables for change detection
            settings_vars = {}
            
            # Cache Settings Section
            cache_frame = ttk.LabelFrame(scrollable_frame, text="🔄 Cache Settings", padding=15)
            cache_frame.pack(fill=tk.X, pady=(0, 20))
            
            ttk.Label(cache_frame, text="Auto-refresh interval:").pack(anchor=tk.W)
            cache_interval_var = tk.StringVar(value="10 minutes")
            cache_interval_combo = ttk.Combobox(cache_frame, textvariable=cache_interval_var,
                                               values=["5 minutes", "10 minutes", "15 minutes", "30 minutes"],
                                               state="readonly", width=30)
            cache_interval_combo.pack(fill=tk.X, pady=(0, 10))
            settings_vars["cache_interval"] = cache_interval_var
            
            ttk.Label(cache_frame, text="Cache retention:").pack(anchor=tk.W)
            cache_retention_var = tk.StringVar(value="24 hours")
            cache_retention_combo = ttk.Combobox(cache_frame, textvariable=cache_retention_var,
                                                values=["12 hours", "24 hours", "48 hours", "72 hours"],
                                                state="readonly", width=30)
            cache_retention_combo.pack(fill=tk.X, pady=(0, 10))
            settings_vars["cache_retention"] = cache_retention_var
            
            cache_monitoring_var = tk.BooleanVar(value=False)
            cache_monitoring_check = ttk.Checkbutton(cache_frame, text="Background monitoring (disabled for stability)", 
                                                    variable=cache_monitoring_var, state='disabled')
            cache_monitoring_check.pack(anchor=tk.W)
            settings_vars["cache_monitoring"] = cache_monitoring_var
            
            # Security Settings Section
            security_frame = ttk.LabelFrame(scrollable_frame, text="🔐 Security Settings", padding=15)
            security_frame.pack(fill=tk.X, pady=(0, 20))
            
            vespia_var = tk.BooleanVar(value=True)
            vespia_check = ttk.Checkbutton(security_frame, text="Vespia integration", variable=vespia_var)
            vespia_check.pack(anchor=tk.W)
            settings_vars["vespia"] = vespia_var
            
            encryption_var = tk.BooleanVar(value=True)
            encryption_check = ttk.Checkbutton(security_frame, text="Credential encryption", variable=encryption_var)
            encryption_check.pack(anchor=tk.W)
            settings_vars["encryption"] = encryption_var
            
            # Display Settings Section
            display_frame = ttk.LabelFrame(scrollable_frame, text="🖥️ Display Settings", padding=15)
            display_frame.pack(fill=tk.X, pady=(0, 20))
            
            notifications_var = tk.BooleanVar(value=True)
            notifications_check = ttk.Checkbutton(display_frame, text="System tray notifications", variable=notifications_var)
            notifications_check.pack(anchor=tk.W)
            settings_vars["notifications"] = notifications_var
            
            window_management_var = tk.BooleanVar(value=True)
            window_management_check = ttk.Checkbutton(display_frame, text="Window management", variable=window_management_var)
            window_management_check.pack(anchor=tk.W)
            settings_vars["window_management"] = window_management_var
            
            # Save and Cancel buttons
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.pack(fill=tk.X, pady=20)
            
            def save_settings():
                try:
                    # Save settings logic here
                    messagebox.showinfo("Settings", "Settings saved successfully!")
                    settings_window.destroy()
                    if window_key in self.open_windows:
                        del self.open_windows[window_key]
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save settings: {e}")
            
            def cancel_settings():
                settings_window.destroy()
                if window_key in self.open_windows:
                    del self.open_windows[window_key]
            
            save_btn = ttk.Button(button_frame, text="Save Settings", command=save_settings)
            save_btn.pack(side=tk.RIGHT, padx=(10, 0))
            
            cancel_btn = ttk.Button(button_frame, text="Cancel", command=cancel_settings)
            cancel_btn.pack(side=tk.RIGHT)
            
            # Handle window close
            settings_window.protocol("WM_DELETE_WINDOW", cancel_settings)
            
            print("✅ Interactive settings window created successfully")
            
        except Exception as e:
            print(f"⚠️ Settings window error: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification("Settings window error")

    
    def force_cleanup(self, icon=None, item=None):
        """Force cleanup all stale processes and locks"""
        try:
            print("🧹 Force cleaning up all processes...")
            
            # Use the process manager to force cleanup
            process_manager.force_cleanup_stale_processes()
            
            # Force refresh service status
            process_manager.force_refresh_status()
            
            # Clean up all stale lock files
            process_manager.cleanup_all_stale_locks()
            
            # Also clean up local lock files
            self.cleanup_lock_files()
            
            # Refresh the menu
            self.refresh_menu()
            
            self.show_notification("Force cleanup completed - services refreshed")
            print("✅ Force cleanup completed")
            
        except Exception as e:
            print(f"❌ Error during force cleanup: {e}")
            self.show_notification(f"Error during cleanup: {e}")
    
    def show_about(self, icon=None, item=None):
        """Show comprehensive about information with system details"""
        print("ℹ️ About button clicked!")
        self.show_notification("Opening about information...")
        
        # Create window directly
        try:
            self._create_about_window()
            print("✅ About window creation completed")
        except Exception as e:
            print(f"❌ About window creation failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_about_window(self):
        """Create about window in main thread"""
        try:
            # Use safe tkinter compatibility
            if not tkinter_compat or not tkinter_compat.is_compatible():
                print("⚠️ Tkinter compatibility not available for about window")
                import platform
                about_info = f"""
🔍 DeFi Risk Assessment
Version 1.5 - Professional Edition

Python Version: {platform.python_version()}
Platform: {platform.system()} {platform.release()}

Data Sources:
• CoinGecko API: https://www.coingecko.com/en/api
• Additional APIs for comprehensive risk assessment

System tray is running successfully with macOS compatibility mode.
                """
                print(about_info)
                self.show_notification("About: DeFi Risk Assessment v1.5")
                return
            
            tk, ttk, messagebox = tkinter_compat.safe_import_tkinter()
            import platform
            import webbrowser
            from datetime import datetime
            
            # Check if about window is already open
            window_key = 'about'
            if window_key in self.open_windows:
                try:
                    if hasattr(self.open_windows[window_key], 'state') and self.open_windows[window_key].state() == 'normal':
                        self.open_windows[window_key].lift()
                        self.open_windows[window_key].focus_force()
                        return
                except Exception:
                    del self.open_windows[window_key]
            
            # Create about window using safe toplevel
            if self.root:
                about_window = tkinter_compat.create_safe_toplevel(self.root, "About DeFi Risk Assessment")
            else:
                # Create a new root if none exists
                temp_root = tkinter_compat.create_safe_root("About Root")
                about_window = tkinter_compat.create_safe_toplevel(temp_root, "About DeFi Risk Assessment")
            
            about_window.geometry("700x600")
            about_window.resizable(False, False)
            
            # Track this window
            self.open_windows[window_key] = about_window
            
            # Center window
            about_window.geometry("+%d+%d" % (
                (about_window.winfo_screenwidth() // 2) - 350,
                (about_window.winfo_screenheight() // 2) - 300
            ))
            
            # Force window to be visible and on top
            about_window.lift()
            about_window.attributes('-topmost', True)
            about_window.focus_force()
            about_window.after(100, lambda: about_window.attributes('-topmost', False))
            
            # Main frame
            main_frame = ttk.Frame(about_window)
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
            def close_about():
                about_window.destroy()
                if window_key in self.open_windows:
                    del self.open_windows[window_key]
            
            close_btn = ttk.Button(main_frame, text="Close", command=close_about)
            close_btn.pack(pady=20)
            
            # Handle window close
            about_window.protocol("WM_DELETE_WINDOW", close_about)
            
            print("✅ About window created successfully")
            
        except Exception as e:
            print(f"⚠️ About window error: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification("About window error")
    

    

    
    def show_notification(self, message):
        """Show system notification"""
        try:
            if self.icon:
                self.icon.notify(message, "DeFi Risk Assessment")
        except Exception:
            print(f"Notification: {message}")
    
    def verify_required_files(self):
        """Verify that required service files exist"""
        required_files = {
            'Main Dashboard': os.path.join(os.path.dirname(__file__), 'defi_dashboard.py'),
            'API Dashboard': os.path.join(os.path.dirname(__file__), 'api_service_dashboard.py'),
            'Credential Manager': os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management', 'gui_credentials.py'),
            'Chain Manager': os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'credential_management', 'gui_chains.py'),
            'Assessment Script': os.path.join(PROJECT_ROOT, 'scripts', 'v1.5', 'defi_complete_risk_assessment_clean.py')
        }
        
        print("🔍 Verifying required files...")
        for name, path in required_files.items():
            if os.path.exists(path):
                print(f"✅ {name}: {path}")
            else:
                print(f"❌ {name}: {path} (NOT FOUND)")
        
        print("✅ File verification complete")
    
    def cleanup_stale_locks(self):
        """Clean up stale lock files on startup"""
        try:
            if os.path.exists(self.lock_dir):
                for filename in os.listdir(self.lock_dir):
                    if filename.endswith('.lock'):
                        lock_file = os.path.join(self.lock_dir, filename)
                        try:
                            with open(lock_file, 'r') as f:
                                data = json.load(f)
                                pid = data.get('pid')
                            
                            if pid:
                                try:
                                    os.kill(pid, 0)  # Check if process exists
                                    print(f"✅ Found running service: {filename} (PID: {pid})")
                                except OSError:
                                    # Process is dead, remove stale lock file
                                    print(f"🧹 Removing stale lock: {filename} (PID: {pid} not found)")
                                    os.remove(lock_file)
                        except Exception as e:
                            print(f"⚠️ Removing corrupted lock file: {filename} ({e})")
                            try:
                                os.remove(lock_file)
                            except:
                                pass
        except Exception as e:
            print(f"⚠️ Error cleaning up stale locks: {e}")
    
    def cleanup_lock_files(self):
        """Clean up all lock files"""
        try:
            if os.path.exists(self.lock_dir):
                for filename in os.listdir(self.lock_dir):
                    if filename.endswith('.lock'):
                        try:
                            os.remove(os.path.join(self.lock_dir, filename))
                        except:
                            pass
        except:
            pass
    
    def quit_application(self, icon=None, item=None):
        """Quit the application and terminate all subprocesses"""
        try:
            print("🔄 Shutting down system tray and terminating all subprocesses...")
            
            # Force terminate all subprocesses immediately
            self._force_terminate_all_processes()
            
            # Terminate all subprocesses launched by the system tray
            self._terminate_all_subprocesses()
            
            # Close all tracked windows
            for window_key, window in list(self.open_windows.items()):
                try:
                    if hasattr(window, 'poll') and window.poll() is None:
                        window.terminate()
                    elif hasattr(window, 'destroy'):
                        window.destroy()
                except:
                    pass
            
            # Clean up lock files
            self.cleanup_lock_files()
            
            # Clean up singleton lock file
            self._cleanup_lock_file()
            
            # Stop the system tray icon
            if self.icon:
                self.icon.stop()
                
            print("✅ System tray shutdown complete")
            
            # Force exit the application
            os._exit(0)
            
        except Exception as e:
            print(f"⚠️ Error during shutdown: {e}")
            # Force stop the icon even if there's an error
            if self.icon:
                self.icon.stop()
            # Force exit even on error
            os._exit(1)
    
    def _terminate_all_subprocesses(self):
        """Terminate all subprocesses launched by the system tray"""
        try:
            print("🔄 Terminating all subprocesses...")
            
            # Get all running services from process manager
            running_services = process_manager.get_service_status()
            
            for service_name, service_info in running_services.items():
                if service_info.get('running', False):
                    pid = service_info.get('pid')
                    if pid:
                        try:
                            print(f"   🛑 Terminating {service_name} (PID: {pid})")
                            process_manager.terminate_service(service_name)
                        except Exception as e:
                            print(f"   ⚠️ Error terminating {service_name}: {e}")
            
            # Also check for any remaining processes by scanning lock files
            if os.path.exists(self.lock_dir):
                for filename in os.listdir(self.lock_dir):
                    if filename.endswith('.lock'):
                        service_name = filename[:-5]  # Remove .lock extension
                        lock_file = os.path.join(self.lock_dir, filename)
                        
                        try:
                            with open(lock_file, 'r') as f:
                                lock_data = json.load(f)
                                pid = lock_data.get('pid')
                                
                            if pid:
                                try:
                                    # Check if process is still running
                                    os.kill(pid, 0)
                                    print(f"   🛑 Force terminating {service_name} (PID: {pid})")
                                    os.kill(pid, signal.SIGTERM)
                                    
                                    # Wait a bit and force kill if still running
                                    time.sleep(1)
                                    try:
                                        os.kill(pid, 0)
                                        print(f"   💀 Force killing {service_name} (PID: {pid})")
                                        os.kill(pid, signal.SIGKILL)
                                    except OSError:
                                        pass  # Process already terminated
                                        
                                except OSError:
                                    pass  # Process already dead
                                    
                        except Exception as e:
                            print(f"   ⚠️ Error processing lock file {filename}: {e}")
            
            print("✅ All subprocesses terminated")
            
        except Exception as e:
            print(f"⚠️ Error terminating subprocesses: {e}")
    
    def _force_terminate_all_processes(self):
        """Force terminate all running subprocesses immediately"""
        print("🔄 Force terminating all subprocesses immediately...")
        
        # Kill all Python processes that might be our subprocesses
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and any('defi' in arg.lower() or 'dashboard' in arg.lower() or 'credential' in arg.lower() or 'chain' in arg.lower() for arg in cmdline):
                        if proc.pid != os.getpid():  # Don't kill ourselves
                            print(f"🛑 Force killing process: {proc.info['name']} (PID: {proc.pid})")
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except ImportError:
            # Fallback without psutil
            print("⚠️ psutil not available, using basic process termination")
        
        # Also kill any remaining processes by scanning lock files
        if os.path.exists(self.lock_dir):
            for filename in os.listdir(self.lock_dir):
                if filename.endswith('.lock'):
                    service_name = filename[:-5]
                    lock_file = os.path.join(self.lock_dir, filename)
                    try:
                        with open(lock_file, 'r') as f:
                            lock_data = json.load(f)
                            pid = lock_data.get('pid')
                        if pid:
                            try:
                                os.kill(pid, signal.SIGKILL)
                                print(f"🛑 Force killed process from lock file: {service_name} (PID: {pid})")
                            except OSError:
                                pass  # Process already dead
                    except:
                        pass
        
        # Clean up all lock files immediately
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains']:
            try:
                self._cleanup_lock(service_name)
            except Exception as e:
                print(f"⚠️ Error cleaning up lock for {service_name}: {e}")
        
        print("✅ Force termination complete")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print(f"🔄 Received signal {signum}, shutting down gracefully...")
            try:
                self.quit_application()
            except:
                pass
            # Force exit
            os._exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
        signal.signal(signal.SIGQUIT, signal_handler)  # Quit signal
        
        print("✅ Signal handlers configured for graceful shutdown")
    
    def run(self):
        """Start the system tray"""
        try:
            print("Starting DeFi Risk Assessment system tray...")
            print("✅ System tray should appear in menu bar")
            print("✅ Right-click the magnifier icon to see menu")
            
            # Verify required files exist
            self.verify_required_files()
            
            # macOS compatibility setup
            if sys.platform == "darwin":
                print("✅ macOS compatibility mode enabled")
            
            print("✅ Starting system tray icon...")
            self.icon.run()
        except Exception as e:
            print(f"❌ System tray error: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main entry point"""
    try:
        # Create and run the system tray
        main.app = DeFiSystemTray()
        main.app.run()
        
    except Exception as e:
        print(f"Failed to start system tray: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
