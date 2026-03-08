#!/usr/bin/env python3
"""
Interactive Token Editor
=======================

A GUI window for editing tokens.csv data directly in the dashboard.
Provides a user-friendly interface for adding, editing, and removing tokens.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import os
import subprocess
import sys
import atexit
import tempfile
from pathlib import Path

class TokenEditor:
    def __init__(self, parent=None):
        self.parent = parent
        self.tokens_data = []
        self.csv_file = None
        self.lock_file = None
        
        # Check if another instance is already running
        if not self.check_single_instance():
            return
            
        self.setup_csv_path()
        self.create_window()
        self.load_tokens()
        
    def check_single_instance(self):
        """Check if another instance is already running and prevent multiple instances"""
        try:
            # Create a lock file in temp directory
            temp_dir = Path(tempfile.gettempdir())
            self.lock_file = temp_dir / "token_editor.lock"
            
            # Try to create the lock file
            if self.lock_file.exists():
                # Check if the process is still running by reading PID
                try:
                    with open(self.lock_file, 'r') as f:
                        pid = int(f.read().strip())
                    
                    # Check if process is still running
                    try:
                        os.kill(pid, 0)  # This will raise an error if process doesn't exist
                        # Process is still running
                        messagebox.showerror("Error", 
                                           "Token Editor is already running!\n\n"
                                           "Please close the existing Token Editor window "
                                           "before opening a new one.")
                        return False
                    except OSError:
                        # Process is not running, remove stale lock file
                        print(f"Removing stale lock file for process {pid}")
                        self.lock_file.unlink(missing_ok=True)
                except (ValueError, FileNotFoundError):
                    # Invalid lock file, remove it
                    print("Removing invalid lock file")
                    self.lock_file.unlink(missing_ok=True)
            
            # Create new lock file with current PID
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            print(f"Created lock file: {self.lock_file} with PID: {os.getpid()}")
            
            # Register cleanup function
            atexit.register(self.cleanup_lock_file)
            
            return True
            
        except Exception as e:
            print(f"Error checking single instance: {e}")
            return True  # Allow running if there's an error
            
    def cleanup_lock_file(self):
        """Clean up the lock file when the application exits"""
        try:
            if self.lock_file and self.lock_file.exists():
                print(f"Cleaning up lock file: {self.lock_file}")
                self.lock_file.unlink()
                print("Lock file cleaned up successfully")
        except Exception as e:
            print(f"Error cleaning up lock file: {e}")
            
    def on_window_close(self):
        """Handle window close event"""
        try:
            print("Window close event triggered")
            # Clean up lock file
            self.cleanup_lock_file()
            # Destroy the window
            self.window.destroy()
        except Exception as e:
            print(f"Error closing window: {e}")
            # Force destroy if cleanup fails
            try:
                self.window.destroy()
            except:
                pass
        
    def setup_csv_path(self):
        """Setup the path to tokens.csv"""
        try:
            # Get the project root (3 levels up from this script)
            script_dir = Path(__file__).parent
            project_root = script_dir.parent.parent.parent
            self.csv_file = project_root / 'data' / 'tokens.csv'
        except Exception as e:
            print(f"Error setting up CSV path: {e}")
            self.csv_file = None
    
    def create_window(self):
        """Create the main editor window"""
        self.window = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        self.window.title("Token Editor - Edit Token List")
        self.window.geometry("900x700")
        self.window.resizable(True, True)
        
        # Configure grid weights
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)
        
        # Create header
        self.create_header()
        
        # Create main content
        self.create_main_content()
        
        # Create footer
        self.create_footer()
        
        # Center the window
        self.center_window()
        
        # Bind window close event to cleanup
        self.window.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
    def create_header(self):
        """Create the header section"""
        header_frame = ttk.Frame(self.window)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(header_frame, text="Token List Editor", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        # File path display
        path_label = ttk.Label(header_frame, text=f"File: {self.csv_file}", 
                              font=("Arial", 10), foreground="gray")
        path_label.grid(row=1, column=0, columnspan=2, sticky="w")
        
    def create_main_content(self):
        """Create the main content area with token list"""
        # Main frame
        main_frame = ttk.Frame(self.window)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Add token button
        add_btn = ttk.Button(buttons_frame, text="➕ Add Token", 
                            command=self.add_token)
        add_btn.pack(side="left", padx=(0, 10))
        
        # Remove token button
        remove_btn = ttk.Button(buttons_frame, text="➖ Remove Token", 
                               command=self.remove_token)
        remove_btn.pack(side="left", padx=(0, 10))
        
        # Edit token button
        edit_btn = ttk.Button(buttons_frame, text="✏️ Edit Token", 
                             command=self.edit_selected_token)
        edit_btn.pack(side="left", padx=(0, 10))
        
        # Refresh button
        refresh_btn = ttk.Button(buttons_frame, text="🔄 Refresh", 
                                command=self.load_tokens)
        refresh_btn.pack(side="left", padx=(0, 10))
        
        # Import CSV button
        import_btn = ttk.Button(buttons_frame, text="📁 Import CSV", 
                               command=self.import_csv)
        import_btn.pack(side="left", padx=(0, 10))
        
        # Export CSV button
        export_btn = ttk.Button(buttons_frame, text="💾 Export CSV", 
                               command=self.export_csv)
        export_btn.pack(side="left")
        
        # Create treeview for tokens
        self.create_token_treeview(main_frame)
        
    def create_token_treeview(self, parent):
        """Create the treeview for displaying tokens"""
        # Create frame for treeview and scrollbars
        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
        # Create treeview
        columns = ("Address", "Chain", "Symbol", "Name")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.tree.heading("Address", text="Address")
        self.tree.heading("Chain", text="Chain")
        self.tree.heading("Symbol", text="Symbol")
        self.tree.heading("Name", text="Name")
        
        # Configure column widths (standardized)
        self.tree.column("Address", width=250, minwidth=200)
        self.tree.column("Chain", width=120, minwidth=100)
        self.tree.column("Symbol", width=100, minwidth=80)
        self.tree.column("Name", width=250, minwidth=200)
        
        # Create scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Bind double-click event for editing
        self.tree.bind("<Double-1>", self.edit_token)
        
    def create_footer(self):
        """Create the footer with action buttons"""
        footer_frame = ttk.Frame(self.window)
        footer_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        footer_frame.grid_columnconfigure(1, weight=1)
        
        # Status label
        self.status_label = ttk.Label(footer_frame, text="Ready", 
                                     font=("Arial", 10), foreground="gray")
        self.status_label.grid(row=0, column=0, sticky="w")
        
        # Action buttons
        buttons_frame = ttk.Frame(footer_frame)
        buttons_frame.grid(row=0, column=1, sticky="e")
        
        # Save button
        save_btn = ttk.Button(buttons_frame, text="💾 Save Changes", 
                             command=self.save_changes, style="Accent.TButton")
        save_btn.pack(side="right", padx=(10, 0))
        
        # Cancel button
        cancel_btn = ttk.Button(buttons_frame, text="❌ Cancel", 
                               command=self.cancel_changes)
        cancel_btn.pack(side="right")
        
    def center_window(self):
        """Center the window on screen"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
    def load_tokens(self):
        """Load tokens from CSV file"""
        try:
            if not self.csv_file or not self.csv_file.exists():
                messagebox.showerror("Error", f"CSV file not found: {self.csv_file}")
                return
                
            # Read CSV file
            df = pd.read_csv(self.csv_file)
            self.tokens_data = df.to_dict('records')
            
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Add tokens to treeview
            for i, token in enumerate(self.tokens_data):
                self.tree.insert("", "end", values=(
                    token.get('address', ''),
                    token.get('chain', ''),
                    token.get('symbol', ''),
                    token.get('name', '')
                ))
            
            self.update_status(f"Loaded {len(self.tokens_data)} tokens")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tokens: {e}")
            self.update_status("Error loading tokens")
            
    def add_token(self):
        """Add a new token"""
        dialog = TokenDialog(self.window, title="Add New Token")
        if dialog.result:
            # Add to treeview
            self.tree.insert("", "end", values=dialog.result)
            self.update_status("Token added (not saved yet)")
            
    def remove_token(self):
        """Remove selected token"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a token to remove")
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to remove the selected token?"):
            self.tree.delete(selection[0])
            self.update_status("Token removed (not saved yet)")
            
    def edit_token(self, event):
        """Edit selected token (double-click)"""
        self.edit_selected_token()
        
    def edit_selected_token(self):
        """Edit selected token"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a token to edit")
            return
            
        # Get current values
        item = self.tree.item(selection[0])
        current_values = item['values']
        
        # Open field selection dialog
        field_dialog = FieldSelectionDialog(self.window, current_values)
        if field_dialog.result:
            field_name = field_dialog.result
            field_index = {"Address": 0, "Chain": 1, "Symbol": 2, "Name": 3}[field_name]
            current_value = current_values[field_index]
            
            # Open value editing dialog based on field type
            if field_name == "Chain":
                # Use chain selection dialog
                value_dialog = ChainSelectionDialog(self.window, current_value)
            else:
                # Use text input dialog
                value_dialog = ValueInputDialog(self.window, field_name, current_value)
            
            if value_dialog.result:
                new_value = value_dialog.result
                
                # Update the specific field
                updated_values = list(current_values)
                updated_values[field_index] = new_value
                
                # Update treeview
                self.tree.item(selection[0], values=updated_values)
                self.update_status(f"Updated {field_name} (not saved yet)")
            
    def save_changes(self):
        """Save changes to CSV file and update token mappings"""
        try:
            # Collect data from treeview
            tokens = []
            for item in self.tree.get_children():
                values = self.tree.item(item)['values']
                tokens.append({
                    'address': values[0],
                    'chain': values[1],
                    'symbol': values[2],
                    'name': values[3]
                })
            
            # Create DataFrame and save to CSV
            df = pd.DataFrame(tokens)
            df.to_csv(self.csv_file, index=False)
            
            # Update token mappings
            self.update_token_mappings()
            
            messagebox.showinfo("Success", "Changes saved successfully!\nToken mappings have been updated.")
            self.update_status(f"Saved {len(tokens)} tokens")
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save changes: {e}")
            self.update_status("Error saving changes")
            
    def update_token_mappings(self):
        """Run the token mappings update script"""
        try:
            # Get the script directory
            script_dir = Path(__file__).resolve().parent.parent
            mapping_generator = script_dir / 'generate_token_mappings.py'
            if not mapping_generator.exists():
                raise FileNotFoundError(f"{mapping_generator} not found")

            result = subprocess.run(
                [sys.executable, str(mapping_generator)],
                cwd=script_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                print("✅ Token mappings updated successfully")
                self.update_status("Token mappings updated successfully")
            else:
                print(f"Warning: Token mappings update failed: {result.stderr}")
                self.update_status("Warning: Token mappings update failed")
                
        except Exception as e:
            print(f"Warning: Failed to update token mappings: {e}")
            self.update_status("Warning: Failed to update token mappings")
            
    def cancel_changes(self):
        """Cancel changes and reload from file"""
        if messagebox.askyesno("Confirm", "Discard all changes and reload from file?"):
            self.load_tokens()
            self.window.destroy()
            
    def import_csv(self):
        """Import tokens from another CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select CSV file to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                df = pd.read_csv(file_path)
                # Validate format
                required_columns = ['address', 'chain', 'symbol', 'name']
                if not all(col in df.columns for col in required_columns):
                    messagebox.showerror("Error", "CSV file must contain columns: address, chain, symbol, name")
                    return
                
                # Clear existing data
                for item in self.tree.get_children():
                    self.tree.delete(item)
                
                # Add imported data
                for _, row in df.iterrows():
                    self.tree.insert("", "end", values=(
                        row['address'], row['chain'], row['symbol'], row['name']
                    ))
                
                self.update_status(f"Imported {len(df)} tokens")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import CSV: {e}")
                
    def export_csv(self):
        """Export current tokens to CSV file"""
        file_path = filedialog.asksaveasfilename(
            title="Save tokens as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Collect data from treeview
                tokens = []
                for item in self.tree.get_children():
                    values = self.tree.item(item)['values']
                    tokens.append({
                        'address': values[0],
                        'chain': values[1],
                        'symbol': values[2],
                        'name': values[3]
                    })
                
                # Create DataFrame and save
                df = pd.DataFrame(tokens)
                df.to_csv(file_path, index=False)
                
                messagebox.showinfo("Success", f"Tokens exported to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export CSV: {e}")
                
    def update_status(self, message):
        """Update status label"""
        self.status_label.config(text=message)
        
    def run(self):
        """Run the token editor"""
        # Check if window was created (instance check passed)
        if hasattr(self, 'window') and not self.parent:
            self.window.mainloop()


class ValueInputDialog:
    """Dialog for inputting a new value for a field"""
    def __init__(self, parent, field_name, current_value):
        self.parent = parent
        self.field_name = field_name
        self.current_value = current_value
        self.result = None
        self.create_dialog()
        
    def create_dialog(self):
        """Create the value input dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"Edit {self.field_name}")
        self.dialog.geometry("600x250")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.center_dialog()
        
        # Create content
        self.create_content()
        
        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        
    def create_content(self):
        """Create dialog content"""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text=f"Edit {self.field_name}", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Current value display
        ttk.Label(main_frame, text=f"Current value: {self.current_value}").pack(anchor="w", pady=(0, 10))
        
        # New value input
        ttk.Label(main_frame, text=f"New {self.field_name.lower()}:").pack(anchor="w")
        self.value_var = tk.StringVar(value=self.current_value)
        value_entry = ttk.Entry(main_frame, textvariable=self.value_var, width=70)
        value_entry.pack(fill="x", pady=(5, 20))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        # OK button
        ok_btn = ttk.Button(button_frame, text="OK", command=self.ok_clicked)
        ok_btn.pack(side="right", padx=(10, 0))
        
        # Cancel button
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked)
        cancel_btn.pack(side="right")
        
        # Focus on entry and select all text
        value_entry.focus()
        value_entry.select_range(0, tk.END)
        
    def center_dialog(self):
        """Center the dialog on screen"""
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
    def ok_clicked(self):
        """Handle OK button click"""
        value = self.value_var.get().strip()
        if not value:
            messagebox.showerror("Error", f"{self.field_name} cannot be empty")
            return
            
        self.result = value
        self.dialog.destroy()
        
    def cancel_clicked(self):
        """Handle Cancel button click"""
        self.dialog.destroy()


class ChainSelectionDialog:
    """Dialog for selecting a blockchain"""
    def __init__(self, parent, current_value):
        self.parent = parent
        self.current_value = current_value
        self.result = None
        self.create_dialog()
        
    def create_dialog(self):
        """Create the chain selection dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Select Chain")
        self.dialog.geometry("450x250")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.center_dialog()
        
        # Create content
        self.create_content()
        
        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        
    def create_content(self):
        """Create dialog content"""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Select Blockchain", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Current value display
        ttk.Label(main_frame, text=f"Current chain: {self.current_value}").pack(anchor="w", pady=(0, 10))
        
        # Chain selection
        ttk.Label(main_frame, text="Select new chain:").pack(anchor="w")
        self.chain_var = tk.StringVar(value=self.current_value)
        chain_combo = ttk.Combobox(main_frame, textvariable=self.chain_var,
                                  values=['ethereum', 'polygon', 'op', 'sonic', 'bsc', 'arbitrum'],
                                  state="readonly", width=30)
        chain_combo.pack(fill="x", pady=(5, 20))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        # OK button
        ok_btn = ttk.Button(button_frame, text="OK", command=self.ok_clicked)
        ok_btn.pack(side="right", padx=(10, 0))
        
        # Cancel button
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked)
        cancel_btn.pack(side="right")
        
        # Focus on combo box
        chain_combo.focus()
        
    def center_dialog(self):
        """Center the dialog on screen"""
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
    def ok_clicked(self):
        """Handle OK button click"""
        chain = self.chain_var.get()
        if not chain:
            messagebox.showerror("Error", "Please select a chain")
            return
            
        self.result = chain
        self.dialog.destroy()
        
    def cancel_clicked(self):
        """Handle Cancel button click"""
        self.dialog.destroy()


class FieldSelectionDialog:
    """Dialog for selecting which field to edit"""
    def __init__(self, parent, current_values):
        self.parent = parent
        self.current_values = current_values
        self.result = None
        self.create_dialog()
        
    def create_dialog(self):
        """Create the field selection dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Edit Token Field")
        self.dialog.geometry("450x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.center_dialog()
        
        # Create content
        self.create_content()
        
        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        
    def create_content(self):
        """Create dialog content"""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Select Field to Edit", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Current values display
        values_frame = ttk.LabelFrame(main_frame, text="Current Values", padding="10")
        values_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(values_frame, text=f"Address: {self.current_values[0]}").pack(anchor="w")
        ttk.Label(values_frame, text=f"Chain: {self.current_values[1]}").pack(anchor="w")
        ttk.Label(values_frame, text=f"Symbol: {self.current_values[2]}").pack(anchor="w")
        ttk.Label(values_frame, text=f"Name: {self.current_values[3]}").pack(anchor="w")
        
        # Field selection section
        field_frame = ttk.LabelFrame(main_frame, text="Step 1: Select Field", padding="10")
        field_frame.pack(fill="x", pady=(0, 20))
        
        ttk.Label(field_frame, text="Choose which field you want to edit:").pack(anchor="w")
        
        # Create a frame for the dropdown to add some styling
        dropdown_frame = ttk.Frame(field_frame)
        dropdown_frame.pack(fill="x", pady=(5, 10))
        
        self.field_var = tk.StringVar()
        field_combo = ttk.Combobox(dropdown_frame, textvariable=self.field_var,
                                  values=["Address", "Chain", "Symbol", "Name"],
                                  state="readonly", width=30)
        field_combo.pack(fill="x")
        field_combo.bind("<<ComboboxSelected>>", self.on_field_selected)
        
        # Add a placeholder text to make it clear it's a dropdown
        field_combo.set("Select a field...")
        
        # Add a small hint text
        hint_label = ttk.Label(field_frame, text="Click the dropdown arrow to see options", 
                              font=("Arial", 8), foreground="gray")
        hint_label.pack(anchor="w")
        
        # Confirm field selection button
        self.confirm_field_btn = ttk.Button(field_frame, text="✅ Confirm Field Selection", 
                                           command=self.confirm_field_selection, state="disabled")
        self.confirm_field_btn.pack(pady=(5, 0))
        
        # Status label for field selection
        self.field_status_label = ttk.Label(field_frame, text="No field selected", 
                                           font=("Arial", 9), foreground="gray")
        self.field_status_label.pack(pady=(5, 0))
        
        # Separator
        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=20)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        # Cancel button
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked)
        cancel_btn.pack(side="right")
        
        # Focus on combo box
        field_combo.focus()
        
    def center_dialog(self):
        """Center the dialog on screen"""
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
    def on_field_selected(self, event):
        """Handle field selection from dropdown"""
        field = self.field_var.get()
        print(f"Field selected: {field}")  # Debug output
        if field and field != "Select a field...":
            # Enable confirm button when field is selected
            self.confirm_field_btn.config(state="normal")
            self.field_status_label.config(text=f"Selected: {field}", foreground="green")
            print(f"Confirm button enabled for field: {field}")  # Debug output
        else:
            self.confirm_field_btn.config(state="disabled")
            self.field_status_label.config(text="No field selected", foreground="gray")
            
    def confirm_field_selection(self):
        """Confirm the selected field and close dialog"""
        field = self.field_var.get()
        if not field or field == "Select a field...":
            messagebox.showerror("Error", "Please select a field first")
            return
            
        print(f"Confirming field selection: {field}")  # Debug output
        
        # Set the result to just the field name and close the dialog
        self.result = field
        self.dialog.destroy()
            
    def cancel_clicked(self):
        """Handle Cancel button click"""
        self.dialog.destroy()


class TokenDialog:
    """Dialog for adding/editing tokens"""
    def __init__(self, parent, title="Token Dialog", initial_values=None):
        self.parent = parent
        self.result = None
        
        # Default values
        self.default_values = ['', 'ethereum', '', '']
        if initial_values:
            self.default_values = list(initial_values)
            
        self.create_dialog(title)
        
    def create_dialog(self, title):
        """Create the dialog window"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(title)
        self.dialog.geometry("400x300")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.center_dialog()
        
        # Create content
        self.create_content()
        
        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        
    def create_content(self):
        """Create dialog content"""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # Address field
        ttk.Label(main_frame, text="Address:").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.address_var = tk.StringVar(value=self.default_values[0])
        address_entry = ttk.Entry(main_frame, textvariable=self.address_var, width=50)
        address_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Chain field
        ttk.Label(main_frame, text="Chain:").grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.chain_var = tk.StringVar(value=self.default_values[1])
        chain_combo = ttk.Combobox(main_frame, textvariable=self.chain_var, 
                                  values=['ethereum', 'polygon', 'op', 'sonic', 'bsc', 'arbitrum'],
                                  state="readonly", width=20)
        chain_combo.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Symbol field
        ttk.Label(main_frame, text="Symbol:").grid(row=4, column=0, sticky="w", pady=(0, 5))
        self.symbol_var = tk.StringVar(value=self.default_values[2])
        symbol_entry = ttk.Entry(main_frame, textvariable=self.symbol_var, width=20)
        symbol_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Name field
        ttk.Label(main_frame, text="Name:").grid(row=6, column=0, sticky="w", pady=(0, 5))
        self.name_var = tk.StringVar(value=self.default_values[3])
        name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=50)
        name_entry.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, sticky="ew")
        button_frame.grid_columnconfigure(1, weight=1)
        
        # OK button
        ok_btn = ttk.Button(button_frame, text="OK", command=self.ok_clicked)
        ok_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Cancel button
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked)
        cancel_btn.grid(row=0, column=1, sticky="e")
        
        # Configure grid weights
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Focus on first entry
        address_entry.focus()
        
    def center_dialog(self):
        """Center the dialog on screen"""
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
        
    def ok_clicked(self):
        """Handle OK button click"""
        # Validate input
        address = self.address_var.get().strip()
        chain = self.chain_var.get().strip()
        symbol = self.symbol_var.get().strip()
        name = self.name_var.get().strip()
        
        if not address or not chain or not symbol or not name:
            messagebox.showerror("Error", "All fields are required")
            return
            
        # Set result and close dialog
        self.result = [address, chain, symbol, name]
        self.dialog.destroy()
        
    def cancel_clicked(self):
        """Handle Cancel button click"""
        self.dialog.destroy()


def cleanup_token_editor_lock():
    """Manual cleanup function to remove token editor lock file"""
    try:
        temp_dir = Path(tempfile.gettempdir())
        lock_file = temp_dir / "token_editor.lock"
        
        if lock_file.exists():
            print(f"Removing token editor lock file: {lock_file}")
            lock_file.unlink()
            print("Token editor lock file removed successfully")
            return True
        else:
            print("No token editor lock file found")
            return False
    except Exception as e:
        print(f"Error removing token editor lock file: {e}")
        return False

if __name__ == "__main__":
    # Test the token editor
    editor = TokenEditor()
    editor.run()
