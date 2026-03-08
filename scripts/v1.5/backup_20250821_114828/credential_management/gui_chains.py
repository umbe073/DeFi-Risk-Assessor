#!/usr/bin/env python3
"""
Chain Management GUI
Secure management interface for blockchain chain IDs
"""

# macOS compatibility fixes - must be done before importing tkinter
import os
import sys

# Set environment variables immediately to prevent tkinter crashes
if sys.platform == "darwin":
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    os.environ['PYTHON_CONFIGURE_OPTS'] = '--enable-framework'
    os.environ['TK_FRAMEWORK'] = '1'
    os.environ['DISPLAY'] = ':0'

if sys.platform == "darwin":
    # Basic macOS compatibility - environment variables already set above
    print("Running with basic macOS compatibility")

import tkinter as tk
from tkinter import ttk, messagebox

# Note: Dock utilities are handled by the system tray, not needed here
print("Running in background mode (hidden from dock)")

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'

class ChainManager:
    def __init__(self):
        self.env_file = os.path.join(PROJECT_ROOT, '.env')
        self.chains = self.load_chain_config()
        
    def load_chain_config(self):
        """Load chain configuration"""
        return {
            'SONIC_CHAIN_ID': {
                'name': 'Sonic Network',
                'default': '130',
                'description': 'Sonic blockchain chain ID',
                'required': False
            },
            'BSC_CHAIN_ID': {
                'name': 'Binance Smart Chain',
                'default': '56',
                'description': 'BSC blockchain chain ID',
                'required': False
            },
            'POL_CHAIN_ID': {
                'name': 'Polygon',
                'default': '137',
                'description': 'Polygon blockchain chain ID',
                'required': False
            },
            'OP_CHAIN_ID': {
                'name': 'Optimism',
                'default': '10',
                'description': 'Optimism L2 chain ID',
                'required': False
            },
            'ETH_CHAIN_ID': {
                'name': 'Ethereum Mainnet',
                'default': '1',
                'description': 'Ethereum mainnet chain ID',
                'required': True
            },
            'ARB_CHAIN_ID': {
                'name': 'Arbitrum One',
                'default': '42161',
                'description': 'Arbitrum L2 chain ID',
                'required': False
            },
            'AVAX_CHAIN_ID': {
                'name': 'Avalanche C-Chain',
                'default': '43114',
                'description': 'Avalanche blockchain chain ID',
                'required': False
            },
            'FTM_CHAIN_ID': {
                'name': 'Fantom Opera',
                'default': '250',
                'description': 'Fantom blockchain chain ID',
                'required': False
            }
        }
    
    def get_current_chains(self):
        """Get currently configured chain IDs from configuration file"""
        current_chains = {}
        
        if os.path.exists(self.env_file):
            try:
                with open(self.env_file, 'r') as f:
                    lines = f.readlines()
                
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key in self.chains:
                            current_chains[key] = value
            except Exception as e:
                print(f"Error reading configuration file: {e}")
        
        return current_chains
    
    def update_env_file(self, chain_updates):
        """Update chain IDs in configuration file"""
        try:
            # Read existing content
            existing_lines = []
            if os.path.exists(self.env_file):
                with open(self.env_file, 'r') as f:
                    existing_lines = f.readlines()
            
            # Track which chains were updated
            updated_chains = set()
            
            # Update existing lines
            for i, line in enumerate(existing_lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    key = stripped.split('=', 1)[0].strip()
                    if key in chain_updates:
                        existing_lines[i] = f"{key}={chain_updates[key]}\n"
                        updated_chains.add(key)
            
            # Add new chain IDs that weren't in the file
            for key, value in chain_updates.items():
                if key not in updated_chains:
                    existing_lines.append(f"{key}={value}\n")
            
            # Write updated content
            with open(self.env_file, 'w') as f:
                f.writelines(existing_lines)
            
            return True, "Chain IDs updated successfully"
            
        except Exception as e:
            return False, f"Error updating configuration file: {e}"


class ChainManagementGUI:
    def __init__(self):
        self.manager = ChainManager()
        self.root = tk.Tk()
        self.chain_vars = {}
        
        # Store widget references for theme updates
        self.main_widgets = {}
        
        self.setup_window()
        self.create_widgets()
        self.load_current_values()
        
    def setup_window(self):
        """Setup the main window"""
        self.root.title("Chain ID Management")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Bring to front
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)
        
        # Center the window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() // 2) - 350,
            (self.root.winfo_screenheight() // 2) - 300
        ))
        
        # Modern styling
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#2c3e50')
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground='#34495e')
        style.configure('Chain.TLabel', font=('Arial', 10), foreground='#2c3e50')
        style.configure('Desc.TLabel', font=('Arial', 9), foreground='#7f8c8d')
        style.configure('Required.TLabel', font=('Arial', 9, 'bold'), foreground='#e74c3c')
        
    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.main_widgets['main_frame'] = main_frame
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="🔗 Blockchain Chain ID Management", style='Title.TLabel')
        title_label.grid(row=0, column=0, pady=(0, 20), sticky=tk.W)
        self.main_widgets['title_label'] = title_label
        
        # Instructions
        instruction_text = """Configure blockchain chain IDs for multi-chain support. 
Chain IDs are used to identify different blockchain networks for API calls and data fetching."""
        
        instruction_label = ttk.Label(main_frame, text=instruction_text, 
                                    font=('Arial', 10), foreground='#5d6d7e', justify=tk.LEFT)
        instruction_label.grid(row=1, column=0, pady=(0, 20), sticky=(tk.W, tk.E))
        self.main_widgets['instruction_label'] = instruction_label
        
        # Chains frame with scrollbar
        chains_container = ttk.Frame(main_frame)
        chains_container.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        chains_container.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Canvas and scrollbar for chains
        canvas = tk.Canvas(chains_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(chains_container, orient="vertical", command=canvas.yview)
        self.chains_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        chains_container.rowconfigure(0, weight=1)
        chains_container.columnconfigure(0, weight=1)
        
        canvas_frame = canvas.create_window((0, 0), window=self.chains_frame, anchor="nw")
        
        # Configure scrolling
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def configure_canvas_width(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_frame, width=canvas_width)
            
        self.chains_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", configure_canvas_width)
        
        # Create chain entry widgets
        self.create_chain_entries()
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        control_frame.columnconfigure(5, weight=1)
        
        # Reset to defaults button
        reset_btn = ttk.Button(control_frame, text="🔄 Reset to Defaults", command=self.reset_to_defaults)
        reset_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Save button
        save_btn = ttk.Button(control_frame, text="💾 Save Changes", command=self.save_changes)
        save_btn.grid(row=0, column=1, padx=(0, 10))
        
        # Load from file button
        load_btn = ttk.Button(control_frame, text="📂 Reload from File", command=self.reload_from_file)
        load_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Display Settings button
        settings_btn = ttk.Button(control_frame, text="🎨 Display Settings", command=self.show_display_settings)
        settings_btn.grid(row=0, column=3, padx=(0, 10))
        
        # About button
        about_btn = ttk.Button(control_frame, text="ℹ️ About", command=self.show_about)
        about_btn.grid(row=0, column=4, padx=(0, 10))
        
        # Close button
        close_btn = ttk.Button(control_frame, text="❌ Close", command=self.close_window)
        close_btn.grid(row=0, column=5)
        
        # Commentary frame
        commentary_frame = ttk.LabelFrame(main_frame, text="ℹ️ Instructions", padding="10")
        commentary_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        commentary_frame.columnconfigure(0, weight=1)
        
        commentaries = [
            "🔄 Reset to Defaults: Restore all chain IDs to their standard values",
            "💾 Save Changes: Save the current chain IDs to the configuration file",
            "📂 Reload from File: Reload chain IDs from the current configuration file",
            "🎨 Display Settings: Customize theme and appearance settings",
            "ℹ️ About: View application information and version details",
            "❌ Close: Close this window (changes will be lost if not saved)"
        ]
        
        for i, comment in enumerate(commentaries):
            comment_label = ttk.Label(commentary_frame, text=comment, font=('Arial', 9), foreground='#5d6d7e')
            comment_label.grid(row=i, column=0, sticky=tk.W, pady=2)
    
    def create_chain_entries(self):
        """Create entry widgets for each chain"""
        self.chains_frame.columnconfigure(1, weight=1)
        
        row = 0
        for chain_key, chain_info in self.manager.chains.items():
            # Chain frame
            chain_frame = ttk.LabelFrame(self.chains_frame, text=chain_info['name'], padding="10")
            chain_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
            chain_frame.columnconfigure(1, weight=1)
            
            # Chain ID label
            id_label = ttk.Label(chain_frame, text="Chain ID:", style='Chain.TLabel')
            id_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            
            # Chain ID entry
            chain_var = tk.StringVar(value=chain_info['default'])
            entry = ttk.Entry(chain_frame, textvariable=chain_var, font=('Courier', 11))
            entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
            
            # Required indicator
            if chain_info['required']:
                req_label = ttk.Label(chain_frame, text="(Required)", style='Required.TLabel')
                req_label.grid(row=0, column=2, sticky=tk.W)
            
            # Description
            desc_label = ttk.Label(chain_frame, text=chain_info['description'], style='Desc.TLabel')
            desc_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
            
            # Default value info
            default_label = ttk.Label(chain_frame, text=f"Default: {chain_info['default']}", 
                                    font=('Arial', 8), foreground='#95a5a6')
            default_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
            
            self.chain_vars[chain_key] = chain_var
            row += 1
    
    def load_current_values(self):
        """Load current chain IDs from configuration file"""
        current_chains = self.manager.get_current_chains()
        
        for chain_key, chain_var in self.chain_vars.items():
            if chain_key in current_chains:
                chain_var.set(current_chains[chain_key])
    
    def reset_to_defaults(self):
        """Reset all chain IDs to default values"""
        if messagebox.askyesno("Reset to Defaults", 
                              "Reset all chain IDs to their default values?\n\n"
                              "This will overwrite any custom values you've entered."):
            for chain_key, chain_var in self.chain_vars.items():
                default_value = self.manager.chains[chain_key]['default']
                chain_var.set(default_value)
            
            messagebox.showinfo("Reset Complete", "All chain IDs have been reset to default values.")
    
    def save_changes(self):
        """Save current chain IDs to configuration file"""
        try:
            # Validate chain IDs
            chain_updates = {}
            for chain_key, chain_var in self.chain_vars.items():
                value = chain_var.get().strip()
                
                # Validate that it's a number
                if value:
                    try:
                        int(value)
                        chain_updates[chain_key] = value
                    except ValueError:
                        messagebox.showerror("Invalid Chain ID", 
                                           f"Chain ID for {self.manager.chains[chain_key]['name']} "
                                           f"must be a number. Got: '{value}'")
                        return
                elif self.manager.chains[chain_key]['required']:
                    messagebox.showerror("Required Field", 
                                       f"Chain ID for {self.manager.chains[chain_key]['name']} is required.")
                    return
            
            # Save to file
            success, message = self.manager.update_env_file(chain_updates)
            
            if success:
                messagebox.showinfo("Save Successful", 
                                  f"{message}\n\n"
                                  f"Updated {len(chain_updates)} chain IDs in configuration file.")
            else:
                messagebox.showerror("Save Failed", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save chain IDs: {e}")
    
    def reload_from_file(self):
        """Reload chain IDs from configuration file"""
        if messagebox.askyesno("Reload from File", 
                                "Reload chain IDs from the configuration file?\n\n"
                                "This will overwrite any unsaved changes."):
            self.load_current_values()
            messagebox.showinfo("Reload Complete", "Chain IDs have been reloaded from the configuration file.")
    
    def show_display_settings(self):
        """Show display settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Display Settings")
        settings_window.geometry("400x300")
        settings_window.resizable(False, False)
        
        # Center the settings window
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🎨 Display Settings", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Theme selection
        theme_frame = ttk.LabelFrame(main_frame, text="Theme", padding="10")
        theme_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.theme_var = tk.StringVar(value=self.get_current_theme())
        
        # Theme options
        themes = [
            ("Light Theme", "light"),
            ("Dark Theme", "dark"),
            ("System Default", "clam"),
            ("Classic", "classic"),
            ("Alt", "alt")
        ]
        
        for text, value in themes:
            rb = ttk.Radiobutton(theme_frame, text=text, variable=self.theme_var, value=value)
            rb.pack(anchor=tk.W, pady=2)
        
        # Font size section
        font_frame = ttk.LabelFrame(main_frame, text="Font Size", padding="10")
        font_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.font_size_var = tk.IntVar(value=10)
        font_size_scale = ttk.Scale(font_frame, from_=8, to=16, variable=self.font_size_var, orient=tk.HORIZONTAL)
        font_size_scale.pack(fill=tk.X, pady=5)
        
        font_size_label = ttk.Label(font_frame, text="Size: 10")
        font_size_label.pack()
        
        def update_font_label(val):
            font_size_label.config(text=f"Size: {int(float(val))}")
        
        font_size_scale.config(command=update_font_label)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        apply_btn = ttk.Button(button_frame, text="Apply", command=lambda: self.apply_display_settings(settings_window))
        apply_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=settings_window.destroy)
        cancel_btn.pack(side=tk.RIGHT)
    
    def get_current_theme(self):
        """Get the current theme"""
        style = ttk.Style()
        current = style.theme_use()
        if current == 'clam':
            return 'clam'
        return current
    
    def apply_display_settings(self, settings_window):
        """Apply the selected display settings"""
        try:
            # Apply theme
            selected_theme = self.theme_var.get()
            font_size = self.font_size_var.get()
            
            # Show progress message
            progress_label = tk.Label(settings_window, text="Applying theme changes...", font=('Arial', 10, 'bold'))
            progress_label.pack(pady=10)
            settings_window.update()
            
            # Apply theme directly to all widgets
            self.apply_theme_directly(selected_theme, font_size)
            
            settings_window.destroy()
            
            # Show success message with theme preview
            self.show_theme_preview(selected_theme)
            
            messagebox.showinfo("Settings Applied", f"Display settings have been applied.\nTheme: {selected_theme.title()}\nFont size: {font_size}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply display settings: {e}")
    
    def apply_theme_directly(self, theme, font_size):
        """Apply theme directly to all widgets without recreating the interface"""
        try:
            # Define theme colors
            if theme == "light":
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                frame_bg = '#ffffff'
                label_bg = '#ffffff'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
                button_bg = '#3498db'
                button_fg = '#ffffff'
                desc_color = '#7f8c8d'
            elif theme == "dark":
                bg_color = '#2c3e50'
                fg_color = '#ecf0f1'
                frame_bg = '#2c3e50'
                label_bg = '#34495e'
                entry_bg = '#34495e'
                entry_fg = '#ecf0f1'
                button_bg = '#3498db'
                button_fg = '#ffffff'
                desc_color = '#bdc3c7'
            else:
                # System default
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                frame_bg = '#ffffff'
                label_bg = '#ffffff'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
                button_bg = '#3498db'
                button_fg = '#ffffff'
                desc_color = '#7f8c8d'
            
            # Update root window
            self.root.configure(bg=bg_color)
            
            # Update all widgets recursively
            self.update_all_widgets(self.root, theme, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg, desc_color, font_size)
            
            # Specifically update entry fields and labels
            self.update_visible_widgets(theme, entry_bg, entry_fg, label_bg, fg_color)
            
            # Force update
            self.root.update_idletasks()
            self.root.update()
            
            # Create a visual flash effect to make changes obvious
            self.create_theme_flash_effect(theme)
            
            # Force complete window redraw
            self.force_window_redraw()
            
        except Exception as e:
            print(f"Error applying theme directly: {e}")
    
    def update_all_widgets(self, widget, theme, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg, desc_color, font_size):
        """Update all widgets with new theme colors"""
        try:
            # Update current widget
            if isinstance(widget, tk.Label):
                widget.configure(bg=label_bg, fg=fg_color)
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=frame_bg)
            elif isinstance(widget, tk.Canvas):
                widget.configure(bg=frame_bg)
            elif isinstance(widget, tk.Button):
                widget.configure(bg=button_bg, fg=button_fg)
            
            # Update all children
            for child in widget.winfo_children():
                self.update_all_widgets(child, theme, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg, desc_color, font_size)
                
        except Exception as e:
            # Silently ignore errors
            pass
    
    def create_theme_flash_effect(self, theme):
        """Create a visual flash effect to make theme changes obvious"""
        try:
            # Temporarily change the root background to a bright color
            if theme == "light":
                flash_color = '#ffeb3b'  # Bright yellow
            elif theme == "dark":
                flash_color = '#9c27b0'  # Bright purple
            else:
                flash_color = '#4caf50'  # Bright green
            
            # Flash effect
            original_bg = self.root.cget('bg')
            self.root.configure(bg=flash_color)
            self.root.update()
            
            # Brief delay
            self.root.after(200)
            
            # Restore theme color
            if theme == "light":
                self.root.configure(bg='#ffffff')
            elif theme == "dark":
                self.root.configure(bg='#2c3e50')
            else:
                self.root.configure(bg='#ffffff')
            
            self.root.update()
            
        except Exception as e:
            print(f"Error creating flash effect: {e}")
    
    def force_window_redraw(self):
        """Force the entire window to redraw by temporarily hiding and showing it"""
        try:
            # Temporarily hide the window
            self.root.withdraw()
            
            # Brief delay
            self.root.after(100)
            
            # Show the window again
            self.root.deiconify()
            
            # Bring to front
            self.root.lift()
            self.root.focus_force()
            
        except Exception as e:
            print(f"Error forcing window redraw: {e}")
    
    def show_theme_preview(self, theme):
        """Show a brief theme preview to confirm the change"""
        try:
            # Create a small preview window
            preview = tk.Toplevel(self.root)
            preview.title("Theme Preview")
            preview.geometry("300x150")
            preview.resizable(False, False)
            preview.transient(self.root)
            
            # Set theme colors
            if theme == "light":
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                preview_text = "Light Theme Applied"
            elif theme == "dark":
                bg_color = '#2c3e50'
                fg_color = '#ecf0f1'
                preview_text = "Dark Theme Applied"
            else:
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                preview_text = "System Theme Applied"
            
            # Configure preview window
            preview.configure(bg=bg_color)
            
            # Add preview content
            label = tk.Label(preview, text=preview_text, font=('Arial', 14, 'bold'), 
                           bg=bg_color, fg=fg_color)
            label.pack(pady=20)
            
            # Auto-close after 2 seconds
            preview.after(2000, preview.destroy)
            
        except Exception as e:
            print(f"Error showing theme preview: {e}")
    
    def update_visible_widgets(self, theme, entry_bg, entry_fg, label_bg, fg_color):
        """Update the most visible widgets to ensure theme changes are obvious"""
        try:
            # Find and update all entry fields
            for widget in self.root.winfo_children():
                self.find_and_update_entries(widget, entry_bg, entry_fg)
                self.find_and_update_labels(widget, label_bg, fg_color)
                
        except Exception as e:
            print(f"Error updating visible widgets: {e}")
    
    def find_and_update_entries(self, widget, entry_bg, entry_fg):
        """Find and update all entry widgets"""
        try:
            if isinstance(widget, tk.Entry):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
                print(f"Updated entry widget: bg={entry_bg}, fg={entry_fg}")
            
            # Check children
            for child in widget.winfo_children():
                self.find_and_update_entries(child, entry_bg, entry_fg)
                
        except Exception as e:
            pass
    
    def find_and_update_labels(self, widget, label_bg, fg_color):
        """Find and update all label widgets"""
        try:
            if isinstance(widget, tk.Label):
                widget.configure(bg=label_bg, fg=fg_color)
                print(f"Updated label widget: bg={label_bg}, fg={fg_color}")
            
            # Check children
            for child in widget.winfo_children():
                self.find_and_update_labels(child, label_bg, fg_color)
                
        except Exception as e:
            pass
    
    def recreate_interface_with_theme(self, theme, font_size):
        """Recreate the entire interface with the new theme"""
        try:
            # Clear all existing widgets
            for widget in self.root.winfo_children():
                widget.destroy()
            
            # Configure the theme
            style = ttk.Style()
            
            if theme == "light":
                # Light theme configuration
                style.theme_use('clam')
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                frame_bg = '#ffffff'
                label_bg = '#ffffff'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
                button_bg = '#3498db'
                button_fg = '#ffffff'
                
                # Configure styles for light theme
                style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground=fg_color, background=bg_color)
                style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground=fg_color, background=bg_color)
                style.configure('Chain.TLabel', font=('Arial', font_size), foreground=fg_color, background=bg_color)
                style.configure('Desc.TLabel', font=('Arial', font_size-1), foreground='#7f8c8d', background=bg_color)
                style.configure('Required.TLabel', font=('Arial', font_size-1, 'bold'), foreground='#e74c3c', background=bg_color)
                style.configure('TFrame', background=frame_bg)
                style.configure('TLabelframe', background=frame_bg)
                style.configure('TLabelframe.Label', background=frame_bg, foreground=fg_color)
                style.configure('TEntry', fieldbackground=entry_bg, foreground=entry_fg)
                style.configure('TButton', background=button_bg, foreground=button_fg)
                style.configure('TScale', background=frame_bg)
                style.configure('TRadiobutton', background=frame_bg, foreground=fg_color)
                
            elif theme == "dark":
                # Dark theme configuration
                style.theme_use('clam')
                bg_color = '#2c3e50'
                fg_color = '#ecf0f1'
                frame_bg = '#2c3e50'
                label_bg = '#34495e'
                entry_bg = '#34495e'
                entry_fg = '#ecf0f1'
                button_bg = '#3498db'
                button_fg = '#ffffff'
                
                # Configure styles for dark theme
                style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground=fg_color, background=bg_color)
                style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground=fg_color, background=bg_color)
                style.configure('Chain.TLabel', font=('Arial', font_size), foreground=fg_color, background=bg_color)
                style.configure('Desc.TLabel', font=('Arial', font_size-1), foreground='#bdc3c7', background=bg_color)
                style.configure('Required.TLabel', font=('Arial', font_size-1, 'bold'), foreground='#e74c3c', background=bg_color)
                style.configure('TFrame', background=frame_bg)
                style.configure('TLabelframe', background=label_bg)
                style.configure('TLabelframe.Label', background=label_bg, foreground=fg_color)
                style.configure('TEntry', fieldbackground=entry_bg, foreground=entry_fg)
                style.configure('TButton', background=button_bg, foreground=button_fg)
                style.configure('TScale', background=frame_bg)
                style.configure('TRadiobutton', background=frame_bg, foreground=fg_color)
                
            else:
                # System default theme
                style.theme_use(theme)
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                frame_bg = '#ffffff'
                label_bg = '#ffffff'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
                button_bg = '#3498db'
                button_fg = '#ffffff'
                
                # Reset to default colors
                style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground=fg_color)
                style.configure('Header.TLabel', font=('Arial', 12, 'bold'), foreground=fg_color)
                style.configure('Chain.TLabel', font=('Arial', font_size), foreground=fg_color)
                style.configure('Desc.TLabel', font=('Arial', font_size-1), foreground='#7f8c8d')
                style.configure('Required.TLabel', font=('Arial', font_size-1, 'bold'), foreground='#e74c3c')
            
            # Set root window background
            self.root.configure(bg=bg_color)
            
            # Recreate all widgets with new theme
            self.setup_window()
            self.create_widgets()
            self.load_current_values()
            
            # Apply theme to all entry fields and labels
            self.apply_theme_to_widgets(theme, font_size)
            
            # Force update
            self.root.update_idletasks()
            self.root.update()
            
        except Exception as e:
            print(f"Error recreating interface: {e}")
            # Fallback: just update the root background
            if theme == "light":
                self.root.configure(bg='#ffffff')
            elif theme == "dark":
                self.root.configure(bg='#2c3e50')
    
    def apply_theme_to_widgets(self, theme, font_size):
        """Apply theme colors directly to all widgets"""
        try:
            if theme == "light":
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
                label_bg = '#ffffff'
            elif theme == "dark":
                bg_color = '#2c3e50'
                fg_color = '#ecf0f1'
                entry_bg = '#34495e'
                entry_fg = '#ecf0f1'
                label_bg = '#34495e'
            else:
                return  # Use default for other themes
            
            # Update all entry fields
            for chain_key, chain_var in self.chain_vars.items():
                # Find the entry widget for this chain
                for widget in self.root.winfo_children():
                    self.update_widget_theme(widget, theme, bg_color, fg_color, entry_bg, entry_fg, label_bg)
                    
        except Exception as e:
            print(f"Error applying theme to widgets: {e}")
    
    def update_widget_theme(self, widget, theme, bg_color, fg_color, entry_bg, entry_fg, label_bg):
        """Update a widget and all its children with the new theme"""
        try:
            # Update current widget - handle both tk and ttk widgets
            if isinstance(widget, tk.Entry):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
            elif isinstance(widget, tk.Label):
                widget.configure(bg=label_bg, fg=fg_color)
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=bg_color)
            elif isinstance(widget, tk.Canvas):
                widget.configure(bg=bg_color)
            elif isinstance(widget, ttk.Entry):
                # ttk widgets use styles, not direct bg/fg
                pass
            elif isinstance(widget, ttk.Label):
                # ttk widgets use styles, not direct bg/fg
                pass
            elif isinstance(widget, ttk.Frame):
                # ttk widgets use styles, not direct bg/fg
                pass
            elif isinstance(widget, ttk.Canvas):
                # ttk widgets use styles, not direct bg/fg
                pass
            
            # Update all children
            for child in widget.winfo_children():
                self.update_widget_theme(child, theme, bg_color, fg_color, entry_bg, entry_fg, label_bg)
                
        except Exception as e:
            # Silently ignore errors for ttk widgets
            pass
    
    def update_widget_colors(self, theme):
        """Update all widget colors to match the selected theme"""
        try:
            if theme == "light":
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                frame_bg = '#ffffff'
                label_bg = '#ffffff'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
            elif theme == "dark":
                bg_color = '#2c3e50'
                fg_color = '#ecf0f1'
                frame_bg = '#2c3e50'
                label_bg = '#34495e'
                entry_bg = '#34495e'
                entry_fg = '#ecf0f1'
            else:
                return  # Use default colors for other themes
            
            # Update root window
            self.root.configure(bg=bg_color)
            
            # Update stored main widgets
            self.update_main_widgets(theme, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg)
            
            # Update all frames recursively
            self.update_frame_colors(self.root, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg)
            
        except Exception as e:
            print(f"Error updating widget colors: {e}")
    
    def update_main_widgets(self, theme, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg):
        """Update the main stored widgets with new colors"""
        try:
            # Update main frame
            if 'main_frame' in self.main_widgets:
                self.main_widgets['main_frame'].configure(style='TFrame')
            
            # Update title label
            if 'title_label' in self.main_widgets:
                if theme == "light":
                    self.main_widgets['title_label'].configure(style='Title.TLabel')
                elif theme == "dark":
                    self.main_widgets['title_label'].configure(style='Title.TLabel')
            
            # Update instruction label
            if 'instruction_label' in self.main_widgets:
                if theme == "light":
                    self.main_widgets['instruction_label'].configure(foreground='#5d6d7e')
                elif theme == "dark":
                    self.main_widgets['instruction_label'].configure(foreground='#bdc3c7')
                    
        except Exception as e:
            print(f"Error updating main widgets: {e}")
    
    def apply_theme_specific_updates(self, theme):
        """Apply theme-specific updates that require special handling"""
        try:
            if theme == "light":
                # Light theme specific updates
                self.root.configure(bg='#ffffff')
                # Update canvas background if it exists
                for widget in self.root.winfo_children():
                    if isinstance(widget, tk.Canvas):
                        widget.configure(bg='#ffffff')
                        
            elif theme == "dark":
                # Dark theme specific updates
                self.root.configure(bg='#2c3e50')
                # Update canvas background if it exists
                for widget in self.root.winfo_children():
                    if isinstance(widget, tk.Canvas):
                        widget.configure(bg='#2c3e50')
                        
        except Exception as e:
            print(f"Error applying theme-specific updates: {e}")
    
    def refresh_interface(self):
        """Force a complete refresh of the interface to apply all theme changes"""
        try:
            # Force all pending updates
            self.root.update_idletasks()
            
            # Force a complete redraw
            self.root.update()
            
            # Trigger a geometry update
            self.root.geometry(self.root.geometry())
            
        except Exception as e:
            print(f"Error refreshing interface: {e}")
    
    def update_frame_colors(self, widget, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg):
        """Recursively update colors of all widgets in a frame"""
        try:
            # Update the current widget
            if isinstance(widget, tk.Label):
                widget.configure(bg=label_bg, fg=fg_color)
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=frame_bg)
            elif isinstance(widget, tk.Canvas):
                widget.configure(bg=frame_bg)
            elif isinstance(widget, tk.Toplevel):
                widget.configure(bg=bg_color)
            elif hasattr(widget, 'configure'):
                # Try to update ttk widgets by reconfiguring their style
                try:
                    widget.configure(style='TFrame' if isinstance(widget, ttk.Frame) else None)
                except:
                    pass
            
            # Recursively update all child widgets
            for child in widget.winfo_children():
                self.update_frame_colors(child, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg)
                
        except Exception as e:
            print(f"Error updating widget {widget}: {e}")
    
    def show_about(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About Chain ID Management")
        about_window.geometry("500x400")
        about_window.resizable(False, False)
        
        # Center the about window
        about_window.transient(self.root)
        about_window.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(about_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title with icon
        title_label = ttk.Label(main_frame, text="🔗 Chain ID Management", font=('Arial', 18, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Version info
        version_label = ttk.Label(main_frame, text="Version 1.5", font=('Arial', 12))
        version_label.pack(pady=(0, 20))
        
        # Description
        description_text = """A secure blockchain chain ID management tool for multi-chain DeFi operations.

This application allows you to configure and manage blockchain chain IDs for different networks including:
• Ethereum Mainnet (ETH)
• Binance Smart Chain (BSC)
• Polygon (POL)
• Arbitrum One (ARB)
• Optimism (OP)
• Avalanche C-Chain (AVAX)
• Fantom Opera (FTM)
• Sonic Network (SONIC)

Features:
✓ Secure configuration management
✓ Real-time validation
✓ Default value restoration
✓ File-based persistence
✓ Modern GUI interface"""
        
        description_label = ttk.Label(main_frame, text=description_text, font=('Arial', 10), justify=tk.LEFT)
        description_label.pack(pady=(0, 20), fill=tk.X)
        
        # Project info
        project_frame = ttk.LabelFrame(main_frame, text="Project Information", padding="10")
        project_frame.pack(fill=tk.X, pady=(0, 20))
        
        project_info = """Project: DeFi Risk Assessment Suite
Module: Chain ID Management
Developer: DeFi Risk Assessment Team
License: MIT License"""
        
        project_label = ttk.Label(project_frame, text=project_info, font=('Arial', 9), justify=tk.LEFT)
        project_label.pack(fill=tk.X)
        
        # Close button
        close_btn = ttk.Button(main_frame, text="Close", command=about_window.destroy)
        close_btn.pack(pady=(20, 0))
    
    def close_window(self):
        """Close the window"""
        # Check if there are unsaved changes
        current_chains = self.manager.get_current_chains()
        has_changes = False
        
        for chain_key, chain_var in self.chain_vars.items():
            current_value = current_chains.get(chain_key, self.manager.chains[chain_key]['default'])
            if chain_var.get().strip() != current_value:
                has_changes = True
                break
        
        if has_changes:
            result = messagebox.askyesnocancel("Unsaved Changes", 
                                             "You have unsaved changes. Do you want to save them before closing?")
            if result is True:  # Yes, save
                self.save_changes()
                self.root.quit()
                self.root.destroy()
            elif result is False:  # No, don't save
                self.root.quit()
                self.root.destroy()
            # Cancel - do nothing
        else:
            self.root.quit()
            self.root.destroy()
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()


def main():
    """Main entry point"""
    try:
        app = ChainManagementGUI()
        app.run()
    except Exception as e:
        print(f"Chain management error: {e}")
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error", f"Could not start chain management: {e}")
        except:
            pass

def check_singleton():
    """Check if another instance is already running"""
    import tempfile
    import json
    import subprocess
    
    lock_dir = os.path.join(tempfile.gettempdir(), 'defi_dashboard_locks')
    lock_file = os.path.join(lock_dir, 'chains.lock')
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                data = json.load(f)
                pid = data.get('pid')
                
            if pid:
                try:
                    os.kill(pid, 0)
                    print("Chain ID Management is already running")
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
                                            if name of windowItem contains "Chain ID Management" then
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
    lock_file = os.path.join(lock_dir, 'chains.lock')
    
    lock_data = {
        'pid': os.getpid(),
        'started_at': time.time(),
        'service_name': 'chains'
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

if __name__ == "__main__":
    if check_singleton():
        create_lock_file()
        main()
