#!/usr/bin/env python3
"""
GUI Credentials Manager (Desktop)
=================================

Provides a simple desktop window to set up/request the master password and
add/edit/delete API keys without using the terminal.

Backed by the encrypted credentials store used by the main script:
- data/creds.meta (JSON with salt)
- data/creds.enc  (Fernet-encrypted JSON of {KEY: VALUE})

Requirements: cryptography, tkinter (standard on macOS)
"""

# macOS compatibility fixes - must be done before importing tkinter
import os
import sys

# Set critical environment variables immediately for macOS
if sys.platform == "darwin":
    # Set these before any tkinter imports to prevent crashes
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'
    os.environ['TK_DISABLE_COLORS'] = '1'
    os.environ['TK_DISABLE_THEMES'] = '1'
    os.environ['TK_DISABLE_3D'] = '1'
    os.environ['TK_DISABLE_ANIMATIONS'] = '1'
    os.environ['TK_USE_BASIC_MODE'] = '1'
    os.environ['TK_SKIP_MACOS_VERSION_CHECK'] = '1'
    os.environ['TK_DISABLE_MACOS_VERSION_CHECK'] = '1'
    os.environ['TK_DISABLE_NSAPPLICATION_SETUP'] = '1'
    os.environ['TK_DISABLE_AUTORELEASE_POOL'] = '1'
    os.environ['TK_DISABLE_EVENT_LOOP'] = '1'
    
    # Additional environment variables to completely disable problematic features
    os.environ['TK_DISABLE_MACOS_COLORS'] = '1'
    os.environ['TK_DISABLE_MACOS_THEMES'] = '1'
    os.environ['TK_DISABLE_MACOS_3D'] = '1'
    os.environ['TK_DISABLE_MACOS_ANIMATIONS'] = '1'
    os.environ['TK_DISABLE_MACOS_VERSION'] = '1'
    os.environ['TK_DISABLE_MACOS_NSAPPLICATION'] = '1'
    os.environ['TK_DISABLE_MACOS_AUTORELEASE'] = '1'
    os.environ['TK_DISABLE_MACOS_EVENT_LOOP'] = '1'
    
    # Force tkinter to use basic mode and skip all macOS-specific features
    os.environ['TK_FORCE_BASIC_MODE'] = '1'
    os.environ['TK_SKIP_ALL_MACOS_CHECKS'] = '1'
    os.environ['TK_DISABLE_ALL_MACOS_FEATURES'] = '1'
    
    print("✅ Critical macOS environment variables set")

if sys.platform == "darwin":
    # Use environment variables only for macOS compatibility
    # This approach works reliably and avoids import issues
    print("✅ Using environment variables for macOS compatibility")

import json
import base64
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Note: Dock utilities are handled by the system tray, not needed here
print("Running credential manager")

# Allow importing sibling module
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
sys.path.append(os.path.dirname(SCRIPT_DIR))

# Import will be done after tkinter initialization to avoid conflicts


class GuiCreds:
    def __init__(self):
        try:
            # Create root window
            self.root = tk.Tk()
                
            self.root.title("DeFi Risk Assessor - Credentials Manager")
            self.root.geometry("900x600")
            self.root.resizable(True, True)
            
            # Center the window on screen
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            
            # Bring window to front
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.attributes('-topmost', False)

            # Import secure_credentials after tkinter is initialized
            try:
                from secure_credentials import (
                    derive_key,
                    read_store,
                    write_store,
                    project_paths,
                )
                # Store the imported functions as instance variables
                self.read_store = read_store
                self.write_store = write_store
                self.derive_key = derive_key
                self.paths = project_paths()
                os.makedirs(self.paths['project_root'], exist_ok=True)
                os.makedirs(self.paths['data_dir'], exist_ok=True)
            except Exception as e:
                print(f"❌ Could not import secure_credentials: {e}")
                print("Install dependencies first.")
                raise

            self.master_pw = tk.StringVar()
            self.selected_key = tk.StringVar()
            self.key_name_var = tk.StringVar()
            self.key_value_var = tk.StringVar()

            self._build_ui()
            self._refresh_list(disable=True)
            
            # Set up proper cleanup on window close
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
        except Exception as e:
            print(f"Error initializing GUI: {e}")
            raise
            
    def on_closing(self):
        """Handle window close event"""
        try:
            self.cleanup_lock_file()
            self.root.destroy()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            self.root.destroy()
            
    def cleanup_lock_file(self):
        """Clean up the credential manager lock file"""
        try:
            import tempfile
            lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
            lock_file = os.path.join(lock_dir, 'credentials.lock')
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print("Credential Manager lock file cleaned up")
        except Exception as e:
            print(f"Error cleaning up lock file: {e}")

    def _build_ui(self):
        # Master password frame
        pw_frame = ttk.LabelFrame(self.root, text="Master Password")
        pw_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(pw_frame, text="Password:").grid(row=0, column=0, padx=6, pady=6, sticky='w')
        pw_entry = ttk.Entry(pw_frame, textvariable=self.master_pw, show='•', width=40)
        pw_entry.grid(row=0, column=1, padx=6, pady=6, sticky='w')
        
        # Show/Hide password toggle
        self.show_password_var = tk.BooleanVar()
        show_pw_check = ttk.Checkbutton(pw_frame, text="👁️ Show", variable=self.show_password_var, 
                                       command=lambda: self.toggle_password_visibility(pw_entry))
        show_pw_check.grid(row=0, column=2, padx=6, pady=6)
        
        ttk.Button(pw_frame, text="Load", command=self.on_load).grid(row=0, column=3, padx=6, pady=6)
        ttk.Button(pw_frame, text="Init Store", command=self.on_init_store).grid(row=0, column=4, padx=6, pady=6)
        ttk.Button(pw_frame, text="Rotate", command=self.on_rotate).grid(row=0, column=5, padx=6, pady=6)

        # Brief commentary for password actions
        ttk.Label(
            pw_frame,
            text=(
                "Load: Unlock the encrypted store and list keys.  "
                "Init Store: Create a new encrypted store (or overwrite).  "
                "Rotate: Change the master password and re-encrypt all stored keys with the new password."
            ),
            style='Small.TLabel',
            wraplength=850,
            justify='left'
        ).grid(row=1, column=0, columnspan=6, padx=6, pady=(0,6), sticky='w')

        # Main content split
        content = ttk.Frame(self.root)
        content.pack(fill='both', expand=True, padx=10, pady=5)

        # Keys list
        list_frame = ttk.LabelFrame(content, text="Stored Keys")
        list_frame.pack(side='left', fill='both', expand=True)
        self.keys_list = tk.Listbox(list_frame, exportselection=False)
        self.keys_list.pack(fill='both', expand=True, padx=6, pady=6)
        self.keys_list.bind('<<ListboxSelect>>', self.on_select_key)

        # Edit panel
        edit_frame = ttk.LabelFrame(content, text="Edit Key")
        edit_frame.pack(side='right', fill='both', expand=True, padx=10)

        ttk.Label(edit_frame, text="Key Name:").grid(row=0, column=0, padx=6, pady=8, sticky='w')
        ttk.Entry(edit_frame, textvariable=self.key_name_var, width=42).grid(row=0, column=1, padx=6, pady=8, sticky='w')

        ttk.Label(edit_frame, text="Key Value:").grid(row=1, column=0, padx=6, pady=8, sticky='w')
        ttk.Entry(edit_frame, textvariable=self.key_value_var, width=42, show='•').grid(row=1, column=1, padx=6, pady=8, sticky='w')

        btns = ttk.Frame(edit_frame)
        btns.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btns, text="Get", command=self.on_get).pack(side='left', padx=4)
        ttk.Button(btns, text="Set / Update", command=self.on_set).pack(side='left', padx=4)
        ttk.Button(btns, text="Remove", command=self.on_remove).pack(side='left', padx=4)

        # Brief commentary for edit actions
        ttk.Label(
            edit_frame,
            text=(
                "Get: Reveal the selected key value.  "
                "Set/Update: Add or update the key and securely save it.  "
                "Remove: Delete the selected key from the store."
            ),
            style='Small.TLabel',
            wraplength=360,
            justify='left'
        ).grid(row=3, column=0, columnspan=2, padx=6, sticky='w')

        # Import/Export
        ie = ttk.Frame(edit_frame)
        ie.grid(row=4, column=0, columnspan=2, pady=4)
        ttk.Button(ie, text="Import File", command=self.on_import_env).pack(side='left', padx=4)
        ttk.Button(ie, text="Export File", command=self.on_export_env).pack(side='left', padx=4)

        # Brief commentary for import/export
        ttk.Label(
            edit_frame,
            text=(
                "Import File: Load keys from a configuration file into the encrypted store.  "
                "Export File: Write all stored keys into a configuration file."
            ),
            style='Small.TLabel',
            wraplength=360,
            justify='left'
        ).grid(row=5, column=0, columnspan=2, padx=6, sticky='w')

        # Status
        self.status = ttk.Label(self.root, text="Store not loaded", anchor='w')
        self.status.pack(fill='x', padx=10, pady=6)

        # Bottom action bar with additional buttons
        bottom = ttk.Frame(self.root)
        bottom.pack(fill='x', padx=10, pady=(0,10))
        
        # Left side - OK button
        ttk.Button(bottom, text="OK", command=self.on_ok).pack(side='left')
        


        # Styles for small commentary text
        try:
            style = ttk.Style(self.root)
            style.configure('Small.TLabel', font=('Helvetica', 9))
        except Exception:
            pass

    # Helpers
    def toggle_password_visibility(self, entry_widget):
        """Toggle password visibility in the entry widget"""
        if self.show_password_var.get():
            entry_widget.configure(show='')
        else:
            entry_widget.configure(show='•')
    
    def _read(self):
        try:
            print(f"🔍 Reading store from: {self.paths['enc_path']}")
            print(f"🔍 Meta file: {self.paths['meta_path']}")
            print(f"🔍 Password length: {len(self.master_pw.get())}")
            
            result = self.read_store(self.paths['enc_path'], self.paths['meta_path'], self.master_pw.get())
            print(f"🔍 Read result: {type(result)}, length: {len(result) if result else 0}")
            return result
        except Exception as e:
            print(f"❌ _read error: {e}")
            import traceback
            traceback.print_exc()
            # Preserve the original exception type and message
            raise e

    def _write(self, kv: dict, reuse_salt: bool = True):
        try:
            if reuse_salt and os.path.exists(self.paths['meta_path']):
                with open(self.paths['meta_path'], 'r') as f:
                    meta = json.load(f)
                salt = base64.b64decode(meta.get('salt', ''))
                self.write_store(self.paths['enc_path'], self.paths['meta_path'], self.master_pw.get(), kv, salt)
            else:
                self.write_store(self.paths['enc_path'], self.paths['meta_path'], self.master_pw.get(), kv)
        except Exception as e:
            raise e

    def _refresh_list(self, disable=False):
        self.keys_list.delete(0, tk.END)
        if disable:
            return
        try:
            for k in sorted(self._read().keys()):
                self.keys_list.insert(tk.END, k)
        except Exception:
            pass

    # Actions
    def on_load(self):
        try:
            # Check if password is provided
            password = self.master_pw.get().strip()
            if not password:
                messagebox.showerror("Load failed", "Please enter a master password first.")
                return
            
            print(f"🔍 Attempting to load store with password: {password[:3]}***")
            
            # Read the store and verify it's working
            store_data = self._read()
            if store_data is not None:
                print(f"✅ Store loaded successfully with {len(store_data)} keys")
                self.status.configure(text=f"✅ Store unlocked successfully ({len(store_data)} credentials stored)")
                self._refresh_list()
            else:
                print("⚠️ Store is empty or not initialized")
                self.status.configure(text="⚠️ Store is empty - add some credentials to get started")
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            print(f"❌ Load error: {error_msg}")
            print(f"❌ Error type: {error_type}")
            import traceback
            traceback.print_exc()
            
            # Check for specific error types and provide user-friendly messages
            if "Incorrect master password" in error_msg:
                messagebox.showerror("🔐 Authentication Failed", 
                    "❌ Incorrect master password.\n\n"
                    "The password you entered does not match the one used to encrypt this store.\n\n"
                    "Please check your password and try again.\n\n"
                    "💡 Tips:\n"
                    "• Make sure Caps Lock is off\n"
                    "• Check for extra spaces\n"
                    "• Verify you're using the correct password")
            elif "password" in error_msg.lower() or "key" in error_msg.lower():
                messagebox.showerror("🔐 Authentication Failed", 
                    "❌ Incorrect master password.\n\n"
                    "Please verify your password and try again.")
            elif "file" in error_msg.lower() or "No such file" in error_msg:
                messagebox.showerror("📁 Store Not Found", 
                    "❌ Store file not found.\n\n"
                    "The encrypted credential store has not been initialized yet.\n\n"
                    "Please click 'Initialize Store' to create a new encrypted store.")
            elif "permission" in error_msg.lower():
                messagebox.showerror("🚫 Permission Denied", 
                    "❌ Permission denied.\n\n"
                    "The application cannot access the credential store files.\n\n"
                    "Please check file permissions and try again.")
            elif "empty" in error_msg.lower() or "no password" in error_msg.lower():
                messagebox.showerror("🔑 Password Required", 
                    "❌ No password provided.\n\n"
                    "Please enter your master password to unlock the credential store.")
            else:
                # Check if this might be a password-related error by looking at the error type
                if error_type in ['InvalidToken', 'ValueError'] or 'password' in error_msg.lower() or 'key' in error_msg.lower():
                    messagebox.showerror("🔐 Authentication Failed", 
                        "❌ Incorrect master password.\n\n"
                        "The password you entered does not match the one used to encrypt this store.\n\n"
                        "Please check your password and try again.\n\n"
                        "💡 Tips:\n"
                        "• Make sure Caps Lock is off\n"
                        "• Check for extra spaces\n"
                        "• Verify you're using the correct password")
                else:
                    messagebox.showerror("❌ Load Error", 
                        f"An unexpected error occurred while loading the credential store:\n\n"
                        f"{error_msg}\n\n"
                        f"Please try again or contact support if the problem persists.")

    def on_init_store(self):
        try:
            self._write({}, reuse_salt=False)
            self.status.configure(text="✅ Store initialized")
            self._refresh_list()
        except Exception as e:
            messagebox.showerror("Init failed", str(e))

    def on_rotate(self):
        try:
            # Read existing
            kv = self._read()
            # Prompt new password
            dlg = tk.Toplevel(self.root)
            dlg.title("Rotate Master Password")
            ttk.Label(dlg, text="New Password:").grid(row=0, column=0, padx=6, pady=8)
            npw = tk.StringVar()
            ttk.Entry(dlg, textvariable=npw, show='•', width=30).grid(row=0, column=1, padx=6, pady=8)
            ttk.Label(dlg, text="Confirm:").grid(row=1, column=0, padx=6, pady=8)
            cpw = tk.StringVar()
            ttk.Entry(dlg, textvariable=cpw, show='•', width=30).grid(row=1, column=1, padx=6, pady=8)

            def do_rotate():
                if npw.get() != cpw.get() or not npw.get():
                    messagebox.showerror("Error", "Passwords do not match or empty")
                    return
                # Write with new salt
                self.write_store(self.paths['enc_path'], self.paths['meta_path'], npw.get(), kv)
                self.master_pw.set(npw.get())
                self.status.configure(text="✅ Password rotated")
                dlg.destroy()

            ttk.Button(dlg, text="Rotate", command=do_rotate).grid(row=2, column=0, columnspan=2, pady=8)
            dlg.grab_set()
        except Exception as e:
            messagebox.showerror("Rotate failed", str(e))

    def on_select_key(self, _evt):
        try:
            idx = self.keys_list.curselection()
            if not idx:
                return
            name = self.keys_list.get(idx[0])
            self.selected_key.set(name)
            self.key_name_var.set(name)
            # Don't auto-fill value to avoid accidental exposure
        except Exception:
            pass

    def on_get(self):
        try:
            name = self.key_name_var.get().strip()
            if not name:
                return
            kv = self._read()
            val = kv.get(name, '')
            self.key_value_var.set(val)
            self.status.configure(text=f"Read value for {name}")
        except Exception as e:
            messagebox.showerror("Get failed", str(e))

    def on_set(self):
        try:
            name = self.key_name_var.get().strip()
            val = self.key_value_var.get()
            if not name:
                messagebox.showerror("Error", "Key name is required")
                return
            kv = self._read()
            kv[name] = val
            self._write(kv)
            self.status.configure(text=f"✅ Set {name}")
            self._refresh_list()
        except Exception as e:
            messagebox.showerror("Set failed", str(e))

    def on_remove(self):
        try:
            name = self.key_name_var.get().strip()
            if not name:
                return
            kv = self._read()
            if name in kv:
                kv.pop(name)
                self._write(kv)
                self.status.configure(text=f"✅ Removed {name}")
                self._refresh_list()
        except Exception as e:
            messagebox.showerror("Remove failed", str(e))

    def on_import_env(self):
        try:
            path = filedialog.askopenfilename(title="Select .env file")
            if not path:
                return
            
            print(f"🔍 Selected file: {path}")
            
            # Enhanced .env parse with filtering for API keys only
            add = {}
            imported_count = 0
            excluded_count = 0
            
            # Define sections to include and exclude
            include_sections = [
                "# Required API Keys (Essential for basic functionality)",
                "# Optional API Keys (For enhanced functionality)", 
                "# SOCIAL SERVICES API Keys"
            ]
            
            exclude_patterns = [
                "_CHAIN_ID=",  # Exclude all chain IDs
                "SCORECHAIN_API_KEY=",
                "TRM_LABS_API_KEY=",
                "OPENSANCTIONS_API_KEY=",
                "LUKKA_API_KEY=",
                "DEFISAFETY_API_KEY="
            ]
            
            current_section = None
            in_valid_section = False
            
            with open(path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Check if this is a section header
                    if line.startswith('#'):
                        current_section = line
                        in_valid_section = any(section in line for section in include_sections)
                        
                        # Special handling for social services section and its subsections
                        if "# SOCIAL SERVICES API Keys" in line or "# Twitter (X) API" in line or "# Telegram API" in line or "# Reddit API" in line or "# Discord API" in line or "# BitcoinTalk Service" in line or "# Cointelegraph Service" in line or "# CoinDesk Service" in line or "# TheBlock Service" in line or "# Decrypt Service" in line:
                            in_valid_section = True
                        
                        # Check for excluded sections
                        if "#CHAIN IDs" in line or "# Not Implemented Yet" in line:
                            in_valid_section = False
                        
                        print(f"🔍 Section: {line} - Valid: {in_valid_section}")
                        continue
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Only process lines if we're in a valid section
                    if not in_valid_section:
                        continue
                    
                    if '=' in line:
                        try:
                            k, v = line.split('=', 1)
                            key = k.strip()
                            value = v.strip().strip('"').strip("'")
                            
                            # Check if this key should be excluded
                            should_exclude = any(pattern in f"{key}=" for pattern in exclude_patterns)
                            
                            if should_exclude:
                                excluded_count += 1
                                print(f"⚠️ Excluded: {key}")
                                continue
                            
                            # Validate key format and add if valid
                            if key and not key.startswith('#'):
                                add[key] = value
                                imported_count += 1
                                print(f"✅ Imported: {key}")
                        except Exception as parse_error:
                            print(f"Warning: Could not parse line {line_num}: {line}")
                            continue
            
            print(f"🔍 Parsed {imported_count} API keys from .env file (excluded {excluded_count} chain IDs and unimplemented keys)")
            
            if imported_count > 0:
                try:
                    # Try to read existing store
                    print("🔍 Attempting to read existing store...")
                    kv = self._read()
                    print(f"🔍 Read existing store with {len(kv)} keys")
                except Exception as read_error:
                    print(f"⚠️ Could not read existing store: {read_error}")
                    # Check if store needs to be initialized
                    if not self.master_pw.get().strip():
                        messagebox.showerror("Import failed", "Please enter a master password and initialize the store first.")
                        return
                    
                    # Try to initialize the store with current password
                    try:
                        print("🔍 Initializing store with current password...")
                        self._write({}, reuse_salt=False)
                        kv = {}
                        print("✅ Store initialized successfully")
                    except Exception as init_error:
                        print(f"❌ Store initialization failed: {init_error}")
                        messagebox.showerror("Import failed", "Could not initialize store. Please check your password and try again.")
                        return
                
                # Update with new keys
                kv.update(add)
                print(f"🔍 Total keys after update: {len(kv)}")
                
                # Write the updated store
                print("🔍 Writing updated store...")
                self._write(kv)
                print("✅ Store written successfully")
                
                self.status.configure(text=f"✅ Successfully imported {imported_count} API keys (excluded {excluded_count} chain IDs and unimplemented keys)")
                self._refresh_list()
            else:
                self.status.configure(text="⚠️ No valid keys found in .env file")
                
        except FileNotFoundError:
            messagebox.showerror("Import failed", "File not found")
        except PermissionError:
            messagebox.showerror("Import failed", "Permission denied to read file")
        except UnicodeDecodeError:
            messagebox.showerror("Import failed", "File encoding error. Please ensure the file is UTF-8 encoded")
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Import error: {error_msg}")
            import traceback
            traceback.print_exc()
            
            if "password" in error_msg.lower():
                messagebox.showerror("Import failed", "Incorrect master password. Please check your password.")
            elif "file" in error_msg.lower():
                messagebox.showerror("Import failed", "Store file not found. Please initialize the store first.")
            else:
                messagebox.showerror("Import failed", f"Error: {error_msg}")

    def on_export_env(self):
        try:
            path = filedialog.asksaveasfilename(title="Save .env file", defaultextension=".env", filetypes=[("ENV", ".env"), ("All", "*.*")])
            if not path:
                return
            kv = self._read()
            with open(path, 'w') as f:
                for k, v in kv.items():
                    f.write(f"{k}={v}\n")
            self.status.configure(text=f"✅ Exported {len(kv)} keys")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def on_ok(self):
        try:
            # Close window to allow the main script to continue
            self.root.destroy()
        except Exception:
            self.root.quit()
    



def main():
    app = GuiCreds()
    app.root.mainloop()


def check_singleton():
    """Check if another instance is already running"""
    import tempfile
    import json
    import subprocess
    
    lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
    lock_file = os.path.join(lock_dir, 'credentials.lock')
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                data = json.load(f)
                pid = data.get('pid')
                
            if pid:
                try:
                    os.kill(pid, 0)
                    print("Credential Management is already running")
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
                                            if name of windowItem contains "Credential Management" then
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

def create_lock_file():
    """Create lock file for this instance"""
    import tempfile
    import json
    import time
    import atexit
    
    lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
    os.makedirs(lock_dir, exist_ok=True)
    lock_file = os.path.join(lock_dir, 'credentials.lock')
    
    lock_data = {
        'pid': os.getpid(),
        'started_at': time.time(),
        'service_name': 'credentials'
    }
    
    try:
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f)
        
        # Register cleanup on exit
        atexit.register(lambda: cleanup_lock_file(lock_file))
        
        # Also register signal handlers for proper cleanup
        import signal
        
        def signal_handler(sig, frame):
            cleanup_lock_file(lock_file)
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGQUIT, signal_handler)
        
    except Exception as e:
        print(f"Warning: Could not create lock file: {e}")

def cleanup_lock_file(lock_file):
    """Clean up lock file on exit"""
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except:
        pass

if __name__ == '__main__':
    if check_singleton():
        create_lock_file()
        main()


