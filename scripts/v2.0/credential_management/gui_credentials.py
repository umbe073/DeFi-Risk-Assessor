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

# CRITICAL: Force foreground mode by unsetting background variables
if sys.platform == "darwin":
    # Explicitly unset any background mode variables that might have been inherited
    if 'LSUIElement' in os.environ:
        del os.environ['LSUIElement']
    if 'NSApplicationActivationPolicy' in os.environ:
        del os.environ['NSApplicationActivationPolicy']
    print("✅ Forced foreground mode by unsetting background variables")

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
import re
from typing import Dict, Set
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

DEFAULT_API_KEYS = [
    "ALCHEMY_API_KEY",
    "INFURA_API_KEY",
    "ETHERSCAN_API_KEY",
    "BSCSCAN_API_KEY",
    "ETHPLORER_API_KEY",
    "MORALIS_API_KEY",
    "COINGECKO_API_KEY",
    "COINGECKO_PRO_API_KEY",
    "COINMARKETCAP_API_KEY",
    "COINCAP_API_KEY",
    "COVALENT_API_KEY",
    "DEBANK_API_KEY",
    "DEBANK_ENABLED",
    "DUNE_API_KEY",
    "DUNE_ANALYTICS_API_KEY",
    "ZAPPER_API_KEY",
    "ARKHAM_API_KEY",
    "OKLINK_API_KEY",
    "TRMLABS_API_KEY",
    "TRM_LABS_API_KEY",
    "CHAINABUSE_API_KEY",
    "SANTIMENT_API_KEY",
    "THE_GRAPH_API_KEY",
    "BREADCRUMBS_API_KEY",
    "BITQUERY_API_KEY",
    "BITQUERY_ACCESS_TOKEN",
    "CERTIK_API_KEY",
    "LI_FI_API_KEY",
    "INCH_API_KEY",
    "GOPLUS_API_KEY",
    "SCORECHAIN_API_KEY",
    "OPENSANCTIONS_API_KEY",
    "LUKKA_API_KEY",
    "DEFISAFETY_API_KEY",
    "SOLSCAN_API_KEY",
    "SOLSCAN_PRO_API_KEY",
    "BIRDEYE_API_KEY",
    "SOLANATRACKER_API_KEY",
    "SOLANATRACKER_ENABLED",
    "TWITTER_BEARER_TOKEN",
    "TWITTER_API_KEY",
    "TWITTER_API_SECRET",
    "TWITTER_ACCESS_TOKEN",
    "TWITTER_ACCESS_TOKEN_SECRET",
    "TWITTER_CLIENT_ID",
    "TWITTER_CLIENT_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "COINTELEGRAPH_API_KEY",
    "COINTELEGRAPH_USER_AGENT",
    "COINDESK_API_KEY",
    "COINDESK_USER_AGENT",
    "THEBLOCK_API_KEY",
    "THEBLOCK_USER_AGENT",
    "DECRYPT_USER_AGENT",
    "VESPIA_API_KEY"
]

# Note: Running in foreground mode
print("Running credential manager")

# Allow importing sibling module
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
ENV_FILE_PATH = os.path.join(PROJECT_ROOT, '.env')
ENV_VAR_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')
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
            
            # Bring window to front (simplified)
            self.root.lift()
            
            # Force window to be visible and in foreground
            self.root.deiconify()
            self.root.focus_force()
            self.root.grab_set()
            
            print("✅ Window created and should be visible")

            # Set up signal handler for window focus
            import signal
            def focus_window(sig, frame):
                try:
                    self.root.lift()
                    self.root.focus_force()
                    self.root.deiconify()
                    print("✅ Window focused via signal")
                except:
                    pass
            
            signal.signal(signal.SIGUSR1, focus_window)
            
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
        self.listbox_keys = []

        # Edit panel
        edit_frame = ttk.LabelFrame(content, text="Edit Key")
        edit_frame.pack(side='right', fill='both', expand=True, padx=10)

        ttk.Label(edit_frame, text="Key Name:").grid(row=0, column=0, padx=6, pady=8, sticky='w')
        ttk.Entry(edit_frame, textvariable=self.key_name_var, width=42).grid(row=0, column=1, padx=6, pady=8, sticky='w')

        ttk.Label(edit_frame, text="Key Value:").grid(row=1, column=0, padx=6, pady=8, sticky='w')
        self.key_value_entry = ttk.Entry(edit_frame, textvariable=self.key_value_var, width=42, show='•')
        self.key_value_entry.grid(row=1, column=1, padx=6, pady=8, sticky='w')
        self.show_key_var = tk.BooleanVar()
        ttk.Checkbutton(
            edit_frame,
            text="👁️ Show",
            variable=self.show_key_var,
            command=self.toggle_key_visibility
        ).grid(row=1, column=2, padx=6, pady=8, sticky='w')

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
    
    def toggle_key_visibility(self):
        """Toggle visibility for the API key value entry"""
        if self.show_key_var.get():
            self.key_value_entry.configure(show='')
        else:
            self.key_value_entry.configure(show='•')
    
    def _read(self) -> Dict[str, str]:
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

    def _write(self, kv: Dict[str, str], reuse_salt: bool = True):
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

    def _is_credential_key(self, key: str) -> bool:
        key_name = str(key or '').strip().upper()
        if not key_name or not ENV_VAR_PATTERN.match(key_name):
            return False
        if key_name in DEFAULT_API_KEYS:
            return True
        hints = (
            'API_KEY',
            'TOKEN',
            'SECRET',
            'PASSWORD',
            'USER_AGENT',
            'CLIENT_ID',
            'CLIENT_SECRET',
        )
        return any(hint in key_name for hint in hints)

    def _normalize_env_value(self, value: str) -> str:
        text = str(value or '').strip()
        if len(text) >= 2 and (
            (text[0] == '"' and text[-1] == '"')
            or (text[0] == "'" and text[-1] == "'")
        ):
            text = text[1:-1]
        return text

    def _read_env_file(self, path: str = ENV_FILE_PATH) -> Dict[str, str]:
        kv: Dict[str, str] = {}
        if not path or not os.path.exists(path):
            return kv
        with open(path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                if not self._is_credential_key(key):
                    continue
                kv[key] = self._normalize_env_value(value)
        return kv

    def _format_env_value(self, value: str) -> str:
        text = str(value or '')
        if not text:
            return ''
        if any(ch in text for ch in (' ', '#', '"', "'", '\\')):
            escaped = text.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        return text

    def _write_env_file(
        self,
        updates: Dict[str, str] | None = None,
        remove_keys: Set[str] | None = None,
        path: str = ENV_FILE_PATH,
    ):
        updates = {str(k).strip(): str(v) for k, v in (updates or {}).items() if str(k).strip()}
        remove_keys = {str(k).strip() for k in (remove_keys or set()) if str(k).strip()}

        existing_lines = []
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                existing_lines = f.readlines()

        output_lines = []
        seen_keys = set()

        for raw_line in existing_lines:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                output_lines.append(raw_line)
                continue

            key = stripped.split('=', 1)[0].strip()
            if not ENV_VAR_PATTERN.match(key):
                output_lines.append(raw_line)
                continue

            if key in remove_keys:
                seen_keys.add(key)
                continue

            if key in updates:
                output_lines.append(f"{key}={self._format_env_value(updates[key])}\n")
                seen_keys.add(key)
            else:
                output_lines.append(raw_line)
                seen_keys.add(key)

        for key, value in sorted(updates.items()):
            if key in seen_keys or key in remove_keys:
                continue
            output_lines.append(f"{key}={self._format_env_value(value)}\n")

        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(output_lines)

    def _sync_store_with_env(self, kv: Dict[str, str]):
        merged = {str(k): str(v) for k, v in (kv or {}).items()}
        env_kv = self._read_env_file()
        store_changed = False
        env_updates = {}

        for key, value in env_kv.items():
            if key not in merged or not str(merged.get(key, '')).strip():
                if str(value).strip():
                    merged[key] = str(value)
                    store_changed = True

        for key, value in merged.items():
            val = str(value or '')
            if not val:
                continue
            if str(env_kv.get(key, '')) != val:
                env_updates[key] = val

        if store_changed:
            self._write(merged)
        if env_updates:
            self._write_env_file(updates=env_updates)

        return merged, env_kv

    def _refresh_list(self, disable=False):
        self.keys_list.delete(0, tk.END)
        self.listbox_keys = []
        if disable:
            return
        try:
            stored = self._read()
        except Exception:
            stored = {}
        env_stored = self._read_env_file()
        
        ordered_keys = []
        seen = set()
        for key in DEFAULT_API_KEYS:
            if key not in seen:
                ordered_keys.append(key)
                seen.add(key)
        for key in sorted(env_stored.keys()):
            if key not in seen:
                ordered_keys.append(key)
                seen.add(key)
        for key in sorted(stored.keys()):
            if key not in seen:
                ordered_keys.append(key)
                seen.add(key)
        
        for key in ordered_keys:
            label = key
            value = str(stored.get(key) or env_stored.get(key) or '').strip()
            if not value:
                label = f"{key} (not set)"
            self.keys_list.insert(tk.END, label)
            self.listbox_keys.append(key)

    # Actions
    def on_load(self):
        try:
            # Check if password is provided
            password = self.master_pw.get().strip()
            if not password:
                messagebox.showerror("Load failed", "Please enter a master password first.")
                return
            
            print(f"🔍 Attempting to load store with password: {password[:3]}***")

            if not (os.path.exists(self.paths['enc_path']) and os.path.exists(self.paths['meta_path'])):
                self._write({}, reuse_salt=False)
            
            # Read the store and verify it's working
            store_data = self._read()
            if store_data is not None:
                merged_store, env_kv = self._sync_store_with_env(store_data)
                print(f"✅ Store loaded successfully with {len(merged_store)} keys")
                self.status.configure(
                    text=(
                        f"✅ Store unlocked successfully "
                        f"({len(merged_store)} credentials in secure store, {len(env_kv)} credentials in .env)"
                    )
                )
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
            actual_key = self.listbox_keys[idx[0]]
            self.selected_key.set(actual_key)
            self.key_name_var.set(actual_key)
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
            if not val:
                val = self._read_env_file().get(name, '')
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
            self._write_env_file(updates={name: val})
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
            self._write_env_file(remove_keys={name})
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
            raw_import = self._read_env_file(path=path)
            add = {k: v for k, v in raw_import.items() if self._is_credential_key(k)}
            imported_count = len(add)
            
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
                self._write_env_file(updates=add)
                
                self.status.configure(text=f"✅ Successfully imported {imported_count} API keys from file")
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
    print("🚀 Starting credential manager main function...")
    if check_singleton():
        print("✅ Singleton check passed")
        create_lock_file()
        print("✅ Lock file created")
        main()
        print("✅ Main function completed")
    else:
        print("❌ Singleton check failed - another instance running")
