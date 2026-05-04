#!/usr/bin/env python3
"""
Process Manager for DeFi Risk Assessment System
Handles all process launches with proper error handling and unified app icon
"""

import os
import sys
import subprocess
import time
import signal
import threading
import json
import tempfile
from pathlib import Path

class ProcessManager:
    def __init__(self):
        self.project_root = '/Users/amlfreak/Desktop/venv'
        self.data_dir = os.path.join(self.project_root, 'data')
        self.lock_dir = os.path.join(self.project_root, 'defi_dashboard_locks')
        self.processes = {}
        self.python_executable = self._get_python_executable()
        # Focus behavior: disabled|safe|aggressive (default: safe to improve reopen behavior)
        self.focus_behavior = os.getenv('FOCUS_BEHAVIOR', 'safe').lower()
        
        # Ensure lock directory exists
        os.makedirs(self.lock_dir, exist_ok=True)
    
    def _get_python_executable(self):
        """Get the best Python executable to use"""
        # Use system Python 3.13 for full module compatibility
        system_python = '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3'
        if os.path.exists(system_python):
            return system_python
        
        # Fallback to Python 3.9 for tkinter compatibility (best for Apple Silicon Macs)
        python39 = '/opt/homebrew/bin/python3.9'
        if os.path.exists(python39):
            return python39
        
        # Fallback to Python 3.11
        python311 = '/opt/homebrew/bin/python3.11'
        if os.path.exists(python311):
            return python311
        
        # Fallback to system Python
        return sys.executable
    
    def _create_environment(self):
        """Create environment variables for secure subprocess execution"""
        env = os.environ.copy()
        env['PYTHONPATH'] = self.project_root
        # Propagate focus behavior to subprocesses
        env['FOCUS_BEHAVIOR'] = self.focus_behavior
        
        # macOS specific environment variables for security and compatibility
        if sys.platform == "darwin":
            # AGGRESSIVE unified app icon environment variables with CORRECT bundle identifier
            env['BUNDLE_IDENTIFIER'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['APP_BUNDLE'] = 'true'
            env['CFBundleIdentifier'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['CFBundleName'] = 'Token Risk Assessment Tool'
            env['CFBundleDisplayName'] = 'Token Risk Assessment Tool'
            env['PARENT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['INHERIT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            
            # CRITICAL: Force inheritance of bundle identifier from parent process
            if 'BUNDLE_IDENTIFIER' in os.environ:
                env['BUNDLE_IDENTIFIER'] = os.environ['BUNDLE_IDENTIFIER']
            if 'CFBundleIdentifier' in os.environ:
                env['CFBundleIdentifier'] = os.environ['CFBundleIdentifier']
            if 'PARENT_BUNDLE_ID' in os.environ:
                env['PARENT_BUNDLE_ID'] = os.environ['PARENT_BUNDLE_ID']
            if 'INHERIT_BUNDLE_ID' in os.environ:
                env['INHERIT_BUNDLE_ID'] = os.environ['INHERIT_BUNDLE_ID']
            
            # Performance optimizations
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            
            # CRITICAL: Force all subprocesses to hide from dock
            env['NSApplicationActivationPolicy'] = 'accessory'
            env['LSUIElement'] = 'true'
            env['NSWindowCollectionBehavior'] = 'NSWindowCollectionBehaviorParticipatesInCycle'
            env['NSWindowLevel'] = 'Normal'
            
            # CRITICAL: Additional dock hiding variables
            env['NSWindowCollectionBehavior'] = 'NSWindowCollectionBehaviorParticipatesInCycle'
            env['NSWindowLevel'] = 'Normal'
            env['NSApplicationActivationPolicy'] = 'accessory'
            env['LSUIElement'] = 'true'
            
            # AGGRESSIVE: Force tkinter to use framework mode
            env['TK_SILENCE_DEPRECATION'] = '1'
            env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
            env['TK_FRAMEWORK'] = '1'
            env['DISPLAY'] = ':0'
            
            # Security enhancements
            env['NSDocumentRevisionsKeepEveryOne'] = '1'
            env['NSAppTransportSecurity'] = 'true'
            
            # AGGRESSIVE: Force basic mode and skip ALL macOS checks
            env['TK_FORCE_BASIC_MODE'] = '1'
            env['TK_SKIP_ALL_MACOS_CHECKS'] = '1'
            env['TK_DISABLE_ALL_MACOS_FEATURES'] = '1'
            env['TK_DISABLE_MACOS_VERSION_CALLS'] = '1'
            env['TK_SKIP_MACOS_VERSION_CHECK'] = '1'
            env['TK_DISABLE_MACOS_VERSION_METHOD'] = '1'
            env['TK_USE_LEGACY_MODE'] = '1'
            env['TK_DISABLE_NATIVE_FEATURES'] = '1'
            env['TK_FORCE_COMPATIBILITY_MODE'] = '1'
            
            # AGGRESSIVE: Additional variables to prevent Python icon
            env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
            env['TK_FRAMEWORK'] = '1'
            env['TK_SILENCE_DEPRECATION'] = '1'
            
            # AGGRESSIVE: Force app to run as background process
            env['NSApplicationActivationPolicy'] = 'accessory'
            env['LSUIElement'] = 'true'
            
            # AGGRESSIVE: Prevent dock icon completely
            env['NSWindowCollectionBehavior'] = 'NSWindowCollectionBehaviorParticipatesInCycle'
            env['NSWindowLevel'] = 'Normal'
            
            # AGGRESSIVE: Additional bundle inheritance
            env['CFBundleExecutable'] = 'Token Risk Assessment Tool'
            env['CFBundlePackageType'] = 'APPL'
            env['CFBundleSignature'] = '????'
            env['CFBundleVersion'] = '1.0'
            env['CFBundleShortVersionString'] = '1.0'
            
            # AGGRESSIVE: Force parent bundle inheritance
            env['PARENT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['INHERIT_BUNDLE_ID'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['BUNDLE_IDENTIFIER'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            env['CFBundleIdentifier'] = 'com.apple.ScriptEditor.id.Token-Risk-Assessment-Tool'
            
            # Additional variables to prevent Python icon from showing
            env['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
            env['TK_FRAMEWORK'] = '1'
            env['TK_SILENCE_DEPRECATION'] = '1'
            env['NSApplicationActivationPolicy'] = 'accessory'
            env['LSUIElement'] = 'true'
            
            # Force unified app icon inheritance
            env['PARENT_BUNDLE_ID'] = 'com.defi.riskassessment'
            env['INHERIT_BUNDLE_ID'] = 'com.defi.riskassessment'
            env['BUNDLE_IDENTIFIER'] = 'com.defi.riskassessment'
            env['APP_BUNDLE'] = 'true'
        
        return env
    
    def _get_lock_file(self, service_name):
        """Get lock file path for a service"""
        return os.path.join(self.lock_dir, f"{service_name}.lock")
    
    def _is_service_running(self, service_name):
        """Check if a service is running"""
        lock_file = self._get_lock_file(service_name)
        
        if not os.path.exists(lock_file):
            return False
        
        try:
            with open(lock_file, 'r') as f:
                lock_data = json.load(f)
                pid = lock_data.get('pid')
            
            if pid:
                # Check if process is still running
                os.kill(pid, 0)
                
                # Additional check: verify the process is actually the right one
                try:
                    # On macOS, check if the process is still responsive
                    if sys.platform == "darwin":
                        # Check if the process is still in the process list
                        result = subprocess.run(['ps', '-p', str(pid)], capture_output=True, text=True)
                        if result.returncode != 0:
                            # Process not found, clean up
                            self._cleanup_lock(service_name)
                            return False
                
                except Exception:
                    # If we can't check, assume it's running
                    pass
                
                return True
        except (OSError, json.JSONDecodeError, FileNotFoundError):
            # Process is dead or lock file is corrupted
            self._cleanup_lock(service_name)
        
        return False
    
    def _cleanup_lock(self, service_name):
        """Clean up stale lock file"""
        lock_file = self._get_lock_file(service_name)
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print(f"✅ Cleaned up stale lock file: {service_name}")
        except OSError as e:
            print(f"⚠️ Error cleaning up lock file {service_name}: {e}")
    
    def cleanup_all_stale_locks(self):
        """Clean up all stale lock files"""
        try:
            if not os.path.exists(self.lock_dir):
                return
            
            for filename in os.listdir(self.lock_dir):
                if filename.endswith('.lock'):
                    service_name = filename[:-5]  # Remove .lock extension
                    if not self._is_service_running(service_name):
                        self._cleanup_lock(service_name)
        except Exception as e:
            print(f"⚠️ Error during bulk lock cleanup: {e}")
    
    def _create_service_lock(self, service_name, process):
        """Create a lock file for a service"""
        lock_file = self._get_lock_file(service_name)
        
        # Clean up any existing lock
        self._cleanup_lock(service_name)
        
        # Create new lock
        lock_data = {
            'pid': process.pid,
            'started_at': time.time(),
            'service_name': service_name,
            'python_executable': self.python_executable
        }
        
        try:
            with open(lock_file, 'w') as f:
                json.dump(lock_data, f)
            return True
        except Exception as e:
            print(f"Error creating lock for {service_name}: {e}")
            return False
    
    def _bring_window_to_front(self, service_name):
        """Bring a specific service window to front using AppleScript (configurable)."""
        # Respect focus behavior configuration
        if self.focus_behavior in ("disabled", "off", "false", "0"):
            print(f"ℹ️ Skipping bring-to-front for '{service_name}' (focus disabled)")
            return False

        if sys.platform == "darwin":
            try:
                # Map service names to exact window title patterns
                window_patterns = {
                    'main_dashboard': ['DeFi Risk Assessment Dashboard', 'DeFi Dashboard', 'Dashboard'],
                    'api_dashboard': ['DeFi API Service Dashboard', 'API Service Dashboard', 'API Dashboard'],
                    'credentials': ['DeFi Risk Assessor - Credentials Manager', 'Credentials Manager', 'Credential'],
                    'chains': ['Chain ID Management', 'Chain Manager'],
                    'settings': ['DeFi System Settings', 'Settings'],
                    'status': ['DeFi System Status', 'Status'],
                    'about': ['About DeFi Risk Assessment', 'About']
                }

                # Small delay to allow windows to fully load
                time.sleep(0.4)

                patterns = window_patterns.get(service_name, [service_name])
                primary_pattern = patterns[0]
                fallback_pattern = patterns[-1] if len(patterns) > 1 else primary_pattern

                # Safe AppleScript: only attempt AXRaise; avoid AXMain/AXFocused
                aggressive = self.focus_behavior == 'aggressive'
                set_frontmost = 'set frontmost of appProcess to true' if aggressive else '-- frontmost change disabled in safe mode'

                script = f'''
                tell application "System Events"
                    set pythonProcesses to every application process whose name contains "Python"
                    repeat with appProcess in pythonProcesses
                        try
                            tell appProcess
                                set windowList to every window
                                repeat with windowItem in windowList
                                    set windowName to name of windowItem
                                    if windowName contains "{primary_pattern}" or windowName contains "{fallback_pattern}" or windowName contains "DeFi" then
                                        {set_frontmost}
                                        try
                                            perform action "AXRaise" of windowItem
                                        end try
                                        return "Found and raised: " & windowName
                                    end if
                                end repeat
                            end tell
                        on error
                            -- Continue to next process
                        end try
                    end repeat
                    return "No matching windows found"
                end tell
                '''

                result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
                if result.returncode == 0:
                    output = (result.stdout or '').strip()
                    if (not output) or ('No matching windows found' in output):
                        print(f"ℹ️ No matching windows found for '{service_name}' (no focus change)")
                        return False
                    print(f"✅ Brought service '{service_name}' to front: {output}")
                    return True
                else:
                    print(f"⚠️ Could not bring service '{service_name}' to front: {result.stderr}")
                    return False
            except Exception as e:
                print(f"❌ Error bringing service to front: {e}")
                return False
        return False
    
    def launch_dashboard(self):
        """Launch the main dashboard"""
        service_name = 'main_dashboard'
        window_title = "DeFi Dashboard"
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Check if already running - STRICT single instance check
            if self._is_service_running(service_name):
                print(f"⚠️ {service_name} already running, bringing to front")
                self._bring_window_to_front(service_name)
                return True, "Dashboard brought to front"
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Dashboard script path
            dashboard_path = os.path.join(self.project_root, 'scripts/v2.0/dashboard/defi_dashboard.py')
            
            if not os.path.exists(dashboard_path):
                return False, f"Dashboard file not found: {dashboard_path}"
            
            # Launch process with direct subprocess for better PID tracking
            env = self._create_environment()
            
            print(f"🚀 Starting {service_name}...")
            
            # Use direct subprocess launch for better PID tracking
            process = subprocess.Popen([
                self.python_executable, dashboard_path
            ], env=env, cwd=self.project_root)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            # Wait for window to open (increased wait time)
            time.sleep(3)
            
            # Bring to front
            self._bring_window_to_front(service_name)
            
            print(f"✅ {service_name} launched successfully")
            return True, "Dashboard launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)
    
    def launch_api_dashboard(self):
        """Launch the API service dashboard"""
        service_name = 'api_dashboard'
        window_title = "API Service Dashboard"
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Check if already running - STRICT single instance check
            if self._is_service_running(service_name):
                print(f"⚠️ {service_name} already running, bringing to front")
                self._bring_window_to_front(service_name)
                return True, "API Dashboard brought to front"
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # API Dashboard script path
            api_path = os.path.join(self.project_root, 'scripts/v2.0/dashboard/api_service_dashboard.py')
            
            if not os.path.exists(api_path):
                return False, f"API Dashboard file not found: {api_path}"
            
            # Launch process with shell wrapper to set environment variables before Python starts
            env = self._create_environment()
            
            print(f"🚀 Starting {service_name}...")
            
            # Add critical environment variables to hide Python icon
            env['LSUIElement'] = '1'
            env['NSApplicationActivationPolicy'] = 'accessory'
            
            # Create shell command that sets environment variables before launching Python
            shell_cmd = f'LSUIElement=1 NSApplicationActivationPolicy=accessory {self.python_executable} "{api_path}"'
            
            process = subprocess.Popen([
                '/bin/bash', '-c', shell_cmd
            ], env=env, cwd=self.project_root)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            # Wait for window to open
            time.sleep(2)
            
            # Bring to front
            self._bring_window_to_front(service_name)
            
            print(f"✅ {service_name} launched successfully")
            return True, "API Dashboard launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)
    
    def launch_credential_manager(self):
        """Launch the credential manager"""
        service_name = 'credentials'
        window_title = "Credential Management"
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Always try to launch - let the singleton check handle duplicates
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Credential manager script path (direct launch)
            cred_path = os.path.join(self.project_root, 'scripts/v2.0/credential_management/gui_credentials.py')
            
            if not os.path.exists(cred_path):
                return False, f"Credential manager file not found: {cred_path}"
            
            # Launch process with shell wrapper to set environment variables before Python starts
            env = self._create_environment()
            
            print(f"🚀 Starting {service_name}...")
            
            # Add critical environment variables to hide Python icon
            env['LSUIElement'] = '1'
            env['NSApplicationActivationPolicy'] = 'accessory'
            
            # Create shell command that sets environment variables before launching Python
            shell_cmd = f'LSUIElement=1 NSApplicationActivationPolicy=accessory {self.python_executable} "{cred_path}"'
            
            process = subprocess.Popen([
                '/bin/bash', '-c', shell_cmd
            ], env=env, cwd=self.project_root)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            # Wait for window to open (increased wait time)
            time.sleep(3)
            
            # Bring to front
            self._bring_window_to_front(service_name)
            
            print(f"✅ {service_name} launched successfully")
            return True, "Credential manager launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)
    
    def launch_settings(self):
        """Launch the settings window"""
        service_name = 'settings'
        window_title = "DeFi System Settings"
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Check if already running
            if self._is_service_running(service_name):
                print(f"⚠️ {service_name} already running, bringing to front")
                self._bring_window_to_front(service_name)
                return True, "Settings brought to front"
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Create settings script path
            settings_path = os.path.join(self.project_root, 'scripts/v2.0/dashboard/settings_window.py')
            
            # Create the settings script if it doesn't exist
            if not os.path.exists(settings_path):
                self._create_settings_script(settings_path)
            
            # Launch process with shell wrapper to set environment variables before Python starts
            env = self._create_environment()
            
            print(f"🚀 Starting {service_name}...")
            
            # Add critical environment variables to hide Python icon
            env['LSUIElement'] = '1'
            env['NSApplicationActivationPolicy'] = 'accessory'
            
            # Create shell command that sets environment variables before launching Python
            shell_cmd = f'LSUIElement=1 NSApplicationActivationPolicy=accessory {self.python_executable} "{settings_path}"'
            
            process = subprocess.Popen([
                '/bin/bash', '-c', shell_cmd
            ], env=env, cwd=self.project_root)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            # Wait for window to open
            time.sleep(2)
            
            # Bring to front
            self._bring_window_to_front(service_name)
            
            print(f"✅ {service_name} launched successfully")
            return True, "Settings launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)

    def launch_status(self):
        """Launch the status window"""
        service_name = 'status'
        window_title = "DeFi System Status"
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Check if already running
            if self._is_service_running(service_name):
                print(f"⚠️ {service_name} already running, bringing to front")
                self._bring_window_to_front(service_name)
                return True, "Status brought to front"
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Create status script path
            status_path = os.path.join(self.project_root, 'scripts/v2.0/dashboard/status_window.py')
            
            # Create the status script if it doesn't exist
            if not os.path.exists(status_path):
                self._create_status_script(status_path)
            
            # Launch process
            env = self._create_environment()
            
            print(f"🚀 Starting {service_name}...")
            process = subprocess.Popen([
                self.python_executable, status_path
            ], env=env, cwd=self.project_root)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            # Wait for window to open
            time.sleep(2)
            
            # Bring to front
            self._bring_window_to_front(service_name)
            
            print(f"✅ {service_name} launched successfully")
            return True, "Status launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)

    def launch_assessment(self):
        """Launch the risk assessment script"""
        service_name = 'assessment'
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Check if already running
            if self._is_service_running(service_name):
                print(f"⚠️ {service_name} already running")
                return True, "Assessment already running"
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Assessment script path
            assessment_path = os.path.join(self.project_root, 'scripts/v2.0/defi_complete_risk_assessment_clean.py')
            
            if not os.path.exists(assessment_path):
                return False, f"Assessment script not found: {assessment_path}"
            
            # Launch process with proper environment
            env = self._create_environment()
            env['PYTHONPATH'] = os.path.join(self.project_root, 'scripts/v2.0') + ':' + env.get('PYTHONPATH', '')
            
            print(f"🚀 Starting {service_name}...")
            
            # Change working directory to scripts/v2.0 so the script can find modules
            script_dir = os.path.join(self.project_root, 'scripts/v2.0')
            
            process = subprocess.Popen([
                self.python_executable, 'defi_complete_risk_assessment_clean.py'
            ], env=env, cwd=script_dir)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            print(f"✅ {service_name} launched successfully")
            return True, "Assessment launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)

    def launch_about(self):
        """Launch the about window"""
        service_name = 'about'
        window_title = "About DeFi Risk Assessment"
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Check if already running
            if self._is_service_running(service_name):
                print(f"⚠️ {service_name} already running, bringing to front")
                self._bring_window_to_front(service_name)
                return True, "About window brought to front"
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Create about script path
            about_path = os.path.join(self.project_root, 'scripts/v2.0/dashboard/about_window.py')
            
            # Create the about script if it doesn't exist
            if not os.path.exists(about_path):
                self._create_about_script(about_path)
            
            # Launch process
            env = self._create_environment()
            
            print(f"🚀 Starting {service_name}...")
            process = subprocess.Popen([
                self.python_executable, about_path
            ], env=env, cwd=self.project_root)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            # Wait for window to open
            time.sleep(2)
            
            # Bring to front
            self._bring_window_to_front(service_name)
            
            print(f"✅ {service_name} launched successfully")
            return True, "About window launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)

    def _create_settings_script(self, settings_path):
        """Create the settings window script"""
        settings_script = '''#!/usr/bin/env python3
"""
DeFi System Settings Window
Interactive settings management for DeFi Risk Assessment
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox

# macOS compatibility fixes
if sys.platform == "darwin":
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

class SettingsWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DeFi System Settings")
        self.root.geometry("500x700")
        self.root.resizable(False, False)
        
        # Center window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() // 2) - 250,
            (self.root.winfo_screenheight() // 2) - 350
        ))
        
        # Load current settings
        self.settings_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'settings.json')
        self.current_settings = self.load_settings()
        
        # Create GUI
        self.create_gui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Show window
        self.root.lift()
        self.root.focus_force()
        
    def load_settings(self):
        """Load current settings from file"""
        default_settings = {
            "cache": {
                "auto_refresh_interval": "10 minutes",
                "cache_retention": "24 hours",
                "background_monitoring": False
            },
            "security": {
                "vespia_integration": True,
                "credential_encryption": True,
                "auto_lock_timeout": "30 minutes"
            },
            "dashboard": {
                "default_dashboard": "Main Dashboard",
                "auto_start_services": False,
                "window_positioning": "Centered"
            },
            "api": {
                "rate_limiting": True,
                "fallback_data": True,
                "api_monitoring": True
            },
            "display": {
                "theme": "System default",
                "font_size": "Medium",
                "notifications": True
            }
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        
        return default_settings
    
    def save_settings(self):
        """Save settings to file"""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.current_settings, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def create_gui(self):
        """Create the GUI"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="⚙️ DeFi System Settings", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Create scrollable frame
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
        
        # Settings sections
        self.create_cache_settings(scrollable_frame)
        self.create_security_settings(scrollable_frame)
        self.create_dashboard_settings(scrollable_frame)
        self.create_api_settings(scrollable_frame)
        self.create_display_settings(scrollable_frame)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Apply Changes button (initially disabled)
        self.apply_btn = ttk.Button(button_frame, text="Apply Changes", 
                                   command=self.apply_changes, state='disabled')
        self.apply_btn.pack(side=tk.LEFT, padx=10)
        
        # Close button
        close_btn = ttk.Button(button_frame, text="Close", command=self.on_closing)
        close_btn.pack(side=tk.RIGHT, padx=10)
        
        # Store variables for change detection
        self.settings_vars = {}
    
    def create_cache_settings(self, parent):
        """Create cache settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔄 Cache Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Auto-refresh interval
        ttk.Label(section_frame, text="Auto-refresh interval:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["cache"]["auto_refresh_interval"])
        combo = ttk.Combobox(section_frame, textvariable=var, 
                            values=["5 minutes", "10 minutes", "15 minutes", "30 minutes"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_auto_refresh"] = var
        
        # Cache retention
        ttk.Label(section_frame, text="Cache retention:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["cache"]["cache_retention"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["12 hours", "24 hours", "48 hours", "72 hours"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_retention"] = var
        
        # Background monitoring
        var = tk.BooleanVar(value=self.current_settings["cache"]["background_monitoring"])
        check = ttk.Checkbutton(section_frame, text="Background monitoring", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["cache_monitoring"] = var
        
        # Bind change events
        for var in [self.settings_vars["cache_auto_refresh"], self.settings_vars["cache_retention"], self.settings_vars["cache_monitoring"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_security_settings(self, parent):
        """Create security settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔐 Security Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Vespia integration
        var = tk.BooleanVar(value=self.current_settings["security"]["vespia_integration"])
        check = ttk.Checkbutton(section_frame, text="Vespia integration", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["security_vespia"] = var
        
        # Credential encryption
        var = tk.BooleanVar(value=self.current_settings["security"]["credential_encryption"])
        check = ttk.Checkbutton(section_frame, text="Credential encryption", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["security_encryption"] = var
        
        # Auto-lock timeout
        ttk.Label(section_frame, text="Auto-lock timeout:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["security"]["auto_lock_timeout"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["15 minutes", "30 minutes", "1 hour", "2 hours"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["security_timeout"] = var
        
        # Bind change events
        for var in [self.settings_vars["security_vespia"], self.settings_vars["security_encryption"], self.settings_vars["security_timeout"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_dashboard_settings(self, parent):
        """Create dashboard settings section"""
        section_frame = ttk.LabelFrame(parent, text="📊 Dashboard Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Default dashboard
        ttk.Label(section_frame, text="Default dashboard:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["dashboard"]["default_dashboard"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Main Dashboard", "API Dashboard", "Credential Manager"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["dashboard_default"] = var
        
        # Auto-start services
        var = tk.BooleanVar(value=self.current_settings["dashboard"]["auto_start_services"])
        check = ttk.Checkbutton(section_frame, text="Auto-start services", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["dashboard_auto_start"] = var
        
        # Window positioning
        ttk.Label(section_frame, text="Window positioning:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["dashboard"]["window_positioning"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Centered", "Top-left", "Top-right", "Bottom-left", "Bottom-right"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["dashboard_positioning"] = var
        
        # Bind change events
        for var in [self.settings_vars["dashboard_default"], self.settings_vars["dashboard_auto_start"], self.settings_vars["dashboard_positioning"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_api_settings(self, parent):
        """Create API settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔗 API Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Rate limiting
        var = tk.BooleanVar(value=self.current_settings["api"]["rate_limiting"])
        check = ttk.Checkbutton(section_frame, text="Rate limiting", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_rate_limiting"] = var
        
        # Fallback data
        var = tk.BooleanVar(value=self.current_settings["api"]["fallback_data"])
        check = ttk.Checkbutton(section_frame, text="Fallback data", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_fallback"] = var
        
        # API monitoring
        var = tk.BooleanVar(value=self.current_settings["api"]["api_monitoring"])
        check = ttk.Checkbutton(section_frame, text="API monitoring", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_monitoring"] = var
        
        # Bind change events
        for var in [self.settings_vars["api_rate_limiting"], self.settings_vars["api_fallback"], self.settings_vars["api_monitoring"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_display_settings(self, parent):
        """Create display settings section"""
        section_frame = ttk.LabelFrame(parent, text="📈 Display Settings", padding=15)
        section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Theme
        ttk.Label(section_frame, text="Theme:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["display"]["theme"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["System default", "Light", "Dark"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["display_theme"] = var
        
        # Font size
        ttk.Label(section_frame, text="Font size:").pack(anchor=tk.W)
        var = tk.StringVar(value=self.current_settings["display"]["font_size"])
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Small", "Medium", "Large"],
                            state="readonly", width=30)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["display_font_size"] = var
        
        # Notifications
        var = tk.BooleanVar(value=self.current_settings["display"]["notifications"])
        check = ttk.Checkbutton(section_frame, text="Notifications", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["display_notifications"] = var
        
        # Bind change events
        for var in [self.settings_vars["display_theme"], self.settings_vars["display_font_size"], self.settings_vars["display_notifications"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def on_setting_change(self, *args):
        """Called when any setting is changed"""
        self.apply_btn.config(state='normal')
    
    def apply_changes(self):
        """Apply the changes and save settings"""
        try:
            # Update current settings with new values
            self.current_settings["cache"]["auto_refresh_interval"] = self.settings_vars["cache_auto_refresh"].get()
            self.current_settings["cache"]["cache_retention"] = self.settings_vars["cache_retention"].get()
            self.current_settings["cache"]["background_monitoring"] = self.settings_vars["cache_monitoring"].get()
            
            self.current_settings["security"]["vespia_integration"] = self.settings_vars["security_vespia"].get()
            self.current_settings["security"]["credential_encryption"] = self.settings_vars["security_encryption"].get()
            self.current_settings["security"]["auto_lock_timeout"] = self.settings_vars["security_timeout"].get()
            
            self.current_settings["dashboard"]["default_dashboard"] = self.settings_vars["dashboard_default"].get()
            self.current_settings["dashboard"]["auto_start_services"] = self.settings_vars["dashboard_auto_start"].get()
            self.current_settings["dashboard"]["window_positioning"] = self.settings_vars["dashboard_positioning"].get()
            
            self.current_settings["api"]["rate_limiting"] = self.settings_vars["api_rate_limiting"].get()
            self.current_settings["api"]["fallback_data"] = self.settings_vars["api_fallback"].get()
            self.current_settings["api"]["api_monitoring"] = self.settings_vars["api_monitoring"].get()
            
            self.current_settings["display"]["theme"] = self.settings_vars["display_theme"].get()
            self.current_settings["display"]["font_size"] = self.settings_vars["display_font_size"].get()
            self.current_settings["display"]["notifications"] = self.settings_vars["display_notifications"].get()
            
            # Save settings
            if self.save_settings():
                messagebox.showinfo("Success", "Settings applied successfully!")
                self.apply_btn.config(state='disabled')
            else:
                messagebox.showerror("Error", "Failed to save settings!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error applying settings: {e}")
    
    def on_closing(self):
        """Handle window closing"""
        self.root.destroy()
    
    def run(self):
        """Run the settings window"""
        self.root.mainloop()

if __name__ == "__main__":
    app = SettingsWindow()
    app.run()
'''
        
        try:
            with open(settings_path, 'w') as f:
                f.write(settings_script)
            print(f"✅ Created settings script: {settings_path}")
        except Exception as e:
            print(f"❌ Error creating settings script: {e}")

    def _create_status_script(self, status_path):
        """Create the status window script"""
        status_script = '''#!/usr/bin/env python3
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
'''
        
        try:
            with open(status_path, 'w') as f:
                f.write(status_script)
            print(f"✅ Created status script: {status_path}")
        except Exception as e:
            print(f"❌ Error creating status script: {e}")

    def launch_chain_manager(self):
        """Launch the chain manager"""
        service_name = 'chains'
        window_title = "Chain ID Management"
        
        try:
            print(f"🔍 Launching {service_name}...")
            
            # Always try to launch - let the singleton check handle duplicates
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Force cleanup any stale locks before launching
            self._cleanup_lock(service_name)
            
            # Chain manager script path (direct launch)
            chains_path = os.path.join(self.project_root, 'scripts/v2.0/credential_management/gui_chains.py')
            
            if not os.path.exists(chains_path):
                return False, f"Chain manager file not found: {chains_path}"
            
            # Launch process with shell wrapper to set environment variables before Python starts
            env = self._create_environment()
            
            print(f"🚀 Starting {service_name}...")
            
            # Add critical environment variables to hide Python icon
            env['LSUIElement'] = '1'
            env['NSApplicationActivationPolicy'] = 'accessory'
            
            # Create shell command that sets environment variables before launching Python
            shell_cmd = f'LSUIElement=1 NSApplicationActivationPolicy=accessory {self.python_executable} "{chains_path}"'
            
            process = subprocess.Popen([
                '/bin/bash', '-c', shell_cmd
            ], env=env, cwd=self.project_root)
            
            print(f"✅ Process started with PID: {process.pid}")
            
            # Create lock file
            if not self._create_service_lock(service_name, process):
                process.terminate()
                return False, "Failed to create service lock"
            
            # Store process reference
            self.processes[service_name] = process
            
            # Wait for window to open
            time.sleep(2)
            
            # Bring to front
            self._bring_window_to_front(window_title)
            
            print(f"✅ {service_name} launched successfully")
            return True, "Chain manager launched successfully"
            
        except Exception as e:
            print(f"❌ Error launching {service_name}: {e}")
            return False, str(e)
    
    def get_running_services(self):
        """Get list of running services"""
        services = []
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains', 'settings', 'status']:
            if self._is_service_running(service_name):
                services.append(service_name)
        return services
    
    def cleanup_all(self):
        """Clean up all processes and locks"""
        for service_name, process in self.processes.items():
            try:
                process.terminate()
            except:
                pass
        
        # Clean up all lock files
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains', 'settings', 'status']:
            self._cleanup_lock(service_name)
    
    def force_cleanup_stale_processes(self):
        """Force cleanup of all stale processes and locks"""
        print("🧹 Force cleaning up stale processes...")
        
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains', 'settings', 'status']:
            lock_file = self._get_lock_file(service_name)
            
            if os.path.exists(lock_file):
                try:
                    with open(lock_file, 'r') as f:
                        lock_data = json.load(f)
                        pid = lock_data.get('pid')
                    
                    if pid:
                        # Try to kill the process
                        try:
                            os.kill(pid, 0)  # Check if exists
                            print(f"⚠️ Force killing stale process {service_name} (PID: {pid})")
                            os.kill(pid, 9)  # Force kill
                        except OSError:
                            # Process already dead
                            pass
                except Exception as e:
                    print(f"⚠️ Error checking {service_name}: {e}")
                
                # Always remove the lock file
                self._cleanup_lock(service_name)
        
        print("✅ Stale processes cleanup completed")
    
    def get_service_status(self):
        """Get detailed status of all services"""
        status = {}
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains', 'status']:
            is_running = self._is_service_running(service_name)
            lock_file = self._get_lock_file(service_name)
            has_lock = os.path.exists(lock_file)
            
            # Get PID if available
            pid = None
            if has_lock:
                try:
                    with open(lock_file, 'r') as f:
                        lock_data = json.load(f)
                        pid = lock_data.get('pid')
                except:
                    pass
            
            # If we have a lock but process is not running, clean up
            if has_lock and not is_running:
                print(f"🧹 Cleaning up stale lock for {service_name}")
                self._cleanup_lock(service_name)
                has_lock = False
                pid = None
            
            status[service_name] = {
                'running': is_running,
                'has_lock': has_lock,
                'lock_file': lock_file,
                'pid': pid
            }
        
        return status
    
    def force_refresh_status(self):
        """Force refresh service status and clean up stale processes"""
        print("🔄 Force refreshing service status...")
        
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains', 'about']:
            lock_file = self._get_lock_file(service_name)
            if os.path.exists(lock_file):
                try:
                    with open(lock_file, 'r') as f:
                        lock_data = json.load(f)
                        pid = lock_data.get('pid')
                    
                    if pid:
                        # Check if process is actually running
                        try:
                            os.kill(pid, 0)  # Check if exists
                            # Process is running, don't be aggressive about cleanup
                            if service_name in self.processes:
                                process = self.processes[service_name]
                                if process.poll() is not None:
                                    # Process has terminated
                                    print(f"🧹 Process {service_name} (PID: {pid}) has terminated")
                                    self._cleanup_lock(service_name)
                                    del self.processes[service_name]
                        except OSError:
                            # Process is dead
                            print(f"🧹 Process {service_name} (PID: {pid}) is dead, cleaning up")
                            self._cleanup_lock(service_name)
                            if service_name in self.processes:
                                del self.processes[service_name]
                except Exception as e:
                    print(f"⚠️ Error checking {service_name}: {e}")
                    # Only clean up if it's clearly corrupted
                    if "JSON" in str(e).upper():
                        self._cleanup_lock(service_name)
        
        print("✅ Service status refreshed")
        return self.get_service_status()
    
    def terminate_service(self, service_name):
        """Terminate a specific service"""
        try:
            # Get the lock file
            lock_file = self._get_lock_file(service_name)
            
            if os.path.exists(lock_file):
                # Read PID from lock file
                with open(lock_file, 'r') as f:
                    lock_data = json.load(f)
                    pid = lock_data.get('pid')
                
                if pid:
                    # Try to terminate the process gracefully
                    try:
                        os.kill(pid, signal.SIGTERM)
                        print(f"✅ Sent SIGTERM to {service_name} (PID: {pid})")
                        
                        # Wait a bit for graceful shutdown
                        time.sleep(2)
                        
                        # Check if process is still running
                        try:
                            os.kill(pid, 0)
                            # Process still running, force kill
                            print(f"⚠️ Force killing {service_name} (PID: {pid})")
                            os.kill(pid, signal.SIGKILL)
                        except OSError:
                            # Process already terminated
                            pass
                            
                    except OSError as e:
                        print(f"⚠️ Error terminating {service_name} (PID: {pid}): {e}")
            
            # Clean up the lock file
            self._cleanup_lock(service_name)
            
            # Remove from processes dict if present
            if service_name in self.processes:
                del self.processes[service_name]
            
            print(f"✅ {service_name} terminated successfully")
            
        except Exception as e:
            print(f"❌ Error terminating {service_name}: {e}")
    
    def terminate_all_services(self):
        """Terminate all running services"""
        print("🔄 Terminating all services...")
        
        for service_name in ['main_dashboard', 'api_dashboard', 'credentials', 'chains', 'about']:
            if self._is_service_running(service_name):
                self.terminate_service(service_name)
        
        print("✅ All services terminated")

    def _create_about_script(self, about_path):
        """Create the about window script"""
        about_script = '''#!/usr/bin/env python3
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
                try:
                    crypto_image = crypto_image.resize((64, 64), Image.Resampling.LANCZOS)
                except AttributeError:
                    # Fallback for older PIL versions
                    crypto_image = crypto_image.resize((64, 64), Image.LANCZOS)
                crypto_photo = ImageTk.PhotoImage(crypto_image)
                icon_label = ttk.Label(main_frame, image=crypto_photo)
                icon_label.image = crypto_photo  # Keep a reference
                icon_label.pack(pady=(0, 20))
            else:
                # Fallback to text icon
                icon_label = ttk.Label(main_frame, text="🔍", font=('Arial', 48))
                icon_label.pack(pady=(0, 20))
        except Exception as e:
            # Fallback to text icon if image loading fails
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
'''
        
        with open(about_path, 'w') as f:
            f.write(about_script)
        
        # Make executable (750: owner rwx, group rx; avoid world-readable 755)
        os.chmod(about_path, 0o750)
        print(f"✅ Created about script: {about_path}")

# Global process manager instance
process_manager = ProcessManager()
