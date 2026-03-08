#!/usr/bin/env python3
"""
DeFi System Settings Window
Interactive settings management for DeFi Risk Assessment
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from system_update_manager import (
    DEFAULT_SYSTEM_UPDATE_SETTINGS,
    REQUIREMENTS_FILE,
    check_outdated_packages,
    extract_failed_packages_from_pip_output,
    extract_pip_failure_highlight_lines,
    humanize_elapsed,
    inject_settings_comments,
    install_requirements_upgrade,
    load_update_state,
    run_pip_check,
    run_safety_dry_run,
    save_update_state,
    should_run_auto_check,
    utc_now_iso,
)

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
        target_width = 760
        target_height = 1020
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        window_w = min(target_width, max(700, screen_w - 80))
        window_h = min(target_height, max(860, screen_h - 80))
        self.root.geometry(f"{window_w}x{window_h}")
        self.root.minsize(700, 860)
        self.root.resizable(True, True)
        
        # Center window
        self.root.geometry("+%d+%d" % (
            (self.root.winfo_screenwidth() // 2) - (window_w // 2),
            (self.root.winfo_screenheight() // 2) - (window_h // 2)
        ))
        
        # Load current settings
        # Keep settings in the shared project-level data directory.
        # dashboard/ -> v2.0/ -> scripts/ -> project root
        self.settings_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'settings.json')
        self.current_settings = self.load_settings()
        self.update_state = load_update_state()
        self.system_update_busy = False
        self.system_update_status_var = tk.StringVar(value="Idle")
        self.system_update_button = None
        self.system_update_last_check_label = None
        self.system_update_last_update_label = None
        self.system_update_outdated_label = None
        
        # Initialize settings variables dictionary
        self.settings_vars = {}
        
        # Store initial values for change detection
        self.initial_values = {}
        
        # Flag to prevent change detection during initialization
        self.initializing = True
        
        # Create GUI
        self.create_gui()
        
        # Store initial values after GUI creation
        self._store_initial_values()
        
        # Allow change detection now
        self.initializing = False

        # Start live system-update counters/scheduler
        self.refresh_system_update_labels()
        self._schedule_system_update_counter_tick()
        self._schedule_system_update_auto_tick(initial_delay_ms=2500)
        
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
                "cache_retention_custom_days": 30,
                "fallback_sync_interval": "4 hours",
                "fallback_sync_custom_hours": 4,
                "background_monitoring": False,
                "respect_48h_metric_skip": True,
                "metric_skip_hours": 48,
                "force_live_override_on_change": True,
                "metric_drift_threshold_pct": 2.0
            },
            "security": {
                "vespia_integration": True,
                "credential_encryption": True,
                "auto_lock_timeout": "30 minutes",
                "auto_lock_custom_minutes": 30
            },
            "dashboard": {
                "default_dashboard": "Main Dashboard",
                "auto_start_services": False,
                "window_positioning": "Centered"
            },
            "api": {
                "rate_limiting": True,
                "fallback_data": True,
                "api_monitoring": True,
                "conditional_requests": True,
                "adaptive_backoff": True,
                "max_parallel_requests": 4,
                "retry_backoff_seconds": 1.5,
                "request_jitter_ms": 200,
                "timeout": 30,
                "retry_attempts": 3
            },
            "eu_mode": {
                "enabled": True,
                "enable_eu_unlicensed_stablecoin": True,
                "enable_eu_regulatory_issues": True,
                "enable_mica_non_compliant": True,
                "enable_mica_no_whitepaper": True,
                "dynamic_allowlist_enabled": True,
                "allowlist_registry_file": "eu_regulated_stablecoins.json",
                "allowlist_extra_symbols": []
            },
            "display": {
                "theme": "System default",
                "font_size": "Medium",
                "notifications": True
            },
            "system_update": dict(DEFAULT_SYSTEM_UPDATE_SETTINGS)
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                merged = self._deep_merge_settings(default_settings, loaded)
                return inject_settings_comments(merged)
        except Exception as e:
            print(f"Error loading settings: {e}")

        return inject_settings_comments(default_settings)

    @staticmethod
    def _deep_merge_settings(defaults, loaded):
        """Merge loaded settings into defaults so missing legacy keys never crash the UI."""
        if not isinstance(defaults, dict):
            return loaded if loaded is not None else defaults
        merged = {}
        loaded_dict = loaded if isinstance(loaded, dict) else {}
        for key, default_value in defaults.items():
            loaded_value = loaded_dict.get(key)
            if isinstance(default_value, dict):
                merged[key] = SettingsWindow._deep_merge_settings(default_value, loaded_value)
            else:
                merged[key] = default_value if loaded_value is None else loaded_value
        for key, loaded_value in loaded_dict.items():
            if key not in merged:
                merged[key] = loaded_value
        return merged

    @staticmethod
    def _parse_duration_to_hours(value, default_hours=24):
        """Parse human-readable duration strings like '72 hours' or '30 days' into hours."""
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return float(default_hours)
        text = value.strip().lower()
        if not text:
            return float(default_hours)
        parts = text.split()
        try:
            amount = float(parts[0])
        except Exception:
            return float(default_hours)
        unit = parts[1] if len(parts) > 1 else 'hours'
        if unit.startswith('day'):
            return amount * 24.0
        if unit.startswith('week'):
            return amount * 24.0 * 7.0
        if unit.startswith('month'):
            return amount * 24.0 * 30.0
        if unit.startswith('year'):
            return amount * 24.0 * 365.0
        if unit.startswith('minute'):
            return amount / 60.0
        return amount

    @staticmethod
    def _parse_duration_to_minutes(value, default_minutes=30):
        """Parse human-readable durations into minutes."""
        hours = SettingsWindow._parse_duration_to_hours(value, default_minutes / 60.0)
        return max(1, int(round(hours * 60.0)))

    @staticmethod
    def _normalize_cache_retention_text(value):
        """Normalize cache retention text for persistence/display."""
        hours = SettingsWindow._parse_duration_to_hours(value, 24)
        if hours <= 0:
            hours = 24
        if hours >= 24 and abs(hours % 24) < 1e-9:
            days = int(round(hours / 24.0))
            return f"{days} day" + ("" if days == 1 else "s")
        if hours.is_integer():
            ih = int(hours)
            return f"{ih} hour" + ("" if ih == 1 else "s")
        return f"{hours:.1f} hours"

    @staticmethod
    def _normalize_auto_lock_text(value):
        """Normalize auto-lock timeout text for persistence/display."""
        minutes = SettingsWindow._parse_duration_to_minutes(value, 30)
        if minutes % 60 == 0:
            hours = minutes // 60
            return f"{hours} hour" + ("" if hours == 1 else "s")
        return f"{minutes} minute" + ("" if minutes == 1 else "s")

    @staticmethod
    def _build_cache_retention_options():
        return [
            "12 hours", "24 hours", "48 hours", "72 hours",
            "7 days", "30 days", "90 days", "180 days", "365 days",
            "Custom"
        ]

    @staticmethod
    def _build_auto_lock_options():
        return [
            "5 minutes", "15 minutes", "30 minutes", "1 hour", "2 hours",
            "Custom"
        ]

    @staticmethod
    def _build_fallback_sync_options():
        return [
            "30 minutes", "1 hour", "2 hours", "4 hours", "6 hours", "12 hours",
            "24 hours", "48 hours", "7 days", "30 days", "Custom"
        ]
    
    def save_settings(self):
        """Save settings to file"""
        try:
            self.current_settings = inject_settings_comments(self.current_settings)
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
        
        # Create scrollable content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(content_frame, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _resize_scrollable_content(event):
            # Keep content width synced to canvas width so sections expand and no large blank gutter appears.
            try:
                canvas.itemconfigure(canvas_window, width=max(100, int(event.width) - 2))
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass

        canvas.bind("<Configure>", _resize_scrollable_content)
        
        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Settings sections
        self.create_cache_settings(scrollable_frame)
        self.create_security_settings(scrollable_frame)
        self.create_dashboard_settings(scrollable_frame)
        self.create_api_settings(scrollable_frame)
        self.create_eu_mode_settings(scrollable_frame)
        self.create_display_settings(scrollable_frame)
        self.create_system_update_settings(scrollable_frame)

        # Ensure layout width/scroll region are initialized and always start at top.
        def _sync_initial_layout():
            try:
                canvas.update_idletasks()
                canvas.itemconfigure(canvas_window, width=max(100, canvas.winfo_width() - 2))
                canvas.configure(scrollregion=canvas.bbox("all"))
                canvas.yview_moveto(0.0)
            except Exception:
                pass
        self.root.after(50, _sync_initial_layout)
        
        # Button frame - pinned to window bottom (outside scroll area)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(14, 6))
        
        # Apply Changes button (initially disabled and faded)
        self.apply_btn = ttk.Button(button_frame, text="Apply Changes", 
                                   command=self.apply_changes, state='disabled')
        self.apply_btn.pack(side=tk.LEFT, padx=10)
        
        # Configure faded appearance for disabled state
        try:
            style = ttk.Style()
            style.configure('Disabled.TButton', foreground='gray')
            self.apply_btn.configure(style='Disabled.TButton')
        except:
            # Fallback if styling fails
            pass
        
        # Close button
        close_btn = ttk.Button(button_frame, text="Close", command=self.on_closing)
        close_btn.pack(side=tk.RIGHT, padx=10)
    
    def create_cache_settings(self, parent):
        """Create cache settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔄 Cache Settings", padding=15)
        section_frame.pack(fill=tk.X, expand=True, pady=(0, 20))
        cache_settings = self.current_settings.get("cache", {})
        
        # Auto-refresh interval
        ttk.Label(section_frame, text="Auto-refresh interval:").pack(anchor=tk.W)
        var = tk.StringVar(value=cache_settings.get("auto_refresh_interval", "10 minutes"))
        combo = ttk.Combobox(section_frame, textvariable=var, 
                            values=["5 minutes", "10 minutes", "15 minutes", "30 minutes"],
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_auto_refresh"] = var
        
        # Cache retention
        ttk.Label(section_frame, text="Cache retention:").pack(anchor=tk.W)
        retention_options = self._build_cache_retention_options()
        current_retention = str(cache_settings.get("cache_retention", "24 hours"))
        custom_ret_days = int(cache_settings.get("cache_retention_custom_days", 30) or 30)
        selected_retention = current_retention if current_retention in retention_options else "Custom"
        if selected_retention == "Custom":
            parsed_days = int(round(self._parse_duration_to_hours(current_retention, 24) / 24.0))
            custom_ret_days = max(1, min(365, parsed_days if parsed_days > 0 else custom_ret_days))
        var = tk.StringVar(value=selected_retention)
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=retention_options,
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_retention"] = var

        ttk.Label(section_frame, text="Custom retention (days, 1-365):").pack(anchor=tk.W)
        retention_custom_var = tk.StringVar(value=str(custom_ret_days))
        retention_custom_entry = ttk.Entry(section_frame, textvariable=retention_custom_var, width=10)
        retention_custom_entry.pack(anchor=tk.W, pady=(0, 10))
        self.settings_vars["cache_retention_custom_days"] = retention_custom_var

        def _toggle_retention_custom(*_):
            is_custom = self.settings_vars["cache_retention"].get() == "Custom"
            retention_custom_entry.configure(state='normal' if is_custom else 'disabled')
        _toggle_retention_custom()
        combo.bind("<<ComboboxSelected>>", lambda _e: (_toggle_retention_custom(), self.on_setting_change()))

        # Cache -> fallback sync interval
        ttk.Label(section_frame, text="Fallback sync interval:").pack(anchor=tk.W)
        sync_options = self._build_fallback_sync_options()
        current_sync = str(cache_settings.get("fallback_sync_interval", "4 hours"))
        custom_sync_hours = int(cache_settings.get("fallback_sync_custom_hours", 4) or 4)
        selected_sync = current_sync if current_sync in sync_options else "Custom"
        if selected_sync == "Custom":
            parsed_hours = int(round(self._parse_duration_to_hours(current_sync, custom_sync_hours)))
            custom_sync_hours = max(1, min(24 * 365, parsed_hours if parsed_hours > 0 else custom_sync_hours))
        sync_var = tk.StringVar(value=selected_sync)
        sync_combo = ttk.Combobox(section_frame, textvariable=sync_var,
                                  values=sync_options,
                                  state="readonly", width=20)
        sync_combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["cache_fallback_sync_interval"] = sync_var

        ttk.Label(section_frame, text="Custom fallback sync (hours, 1-8760):").pack(anchor=tk.W)
        sync_custom_var = tk.StringVar(value=str(custom_sync_hours))
        sync_custom_entry = ttk.Entry(section_frame, textvariable=sync_custom_var, width=10)
        sync_custom_entry.pack(anchor=tk.W, pady=(0, 10))
        self.settings_vars["cache_fallback_sync_custom_hours"] = sync_custom_var

        def _toggle_sync_custom(*_):
            is_custom = self.settings_vars["cache_fallback_sync_interval"].get() == "Custom"
            sync_custom_entry.configure(state='normal' if is_custom else 'disabled')
        _toggle_sync_custom()
        sync_combo.bind("<<ComboboxSelected>>", lambda _e: (_toggle_sync_custom(), self.on_setting_change()))
        
        # Background monitoring
        var = tk.BooleanVar(value=cache_settings.get("background_monitoring", False))
        check = ttk.Checkbutton(section_frame, text="Background monitoring", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["cache_monitoring"] = var

        # Skip re-fetch within N hours (48h policy)
        var_skip = tk.BooleanVar(value=cache_settings.get("respect_48h_metric_skip", True))
        check_skip = ttk.Checkbutton(section_frame, text="Skip re-fetch if data is recent (48h)", variable=var_skip)
        check_skip.pack(anchor=tk.W, pady=(10, 2))
        self.settings_vars["cache_respect_48h_skip"] = var_skip

        # Metric skip hours (default 48)
        ttk.Label(section_frame, text="Skip window (hours):").pack(anchor=tk.W)
        var_hours = tk.StringVar(value=str(cache_settings.get("metric_skip_hours", 48)))
        entry_hours = ttk.Entry(section_frame, textvariable=var_hours, width=8)
        entry_hours.pack(anchor=tk.W, pady=(0, 10))
        self.settings_vars["cache_skip_hours"] = var_hours
        
        # Bind change events
        for var in [
            self.settings_vars["cache_auto_refresh"],
            self.settings_vars["cache_retention"],
            self.settings_vars["cache_retention_custom_days"],
            self.settings_vars["cache_fallback_sync_interval"],
            self.settings_vars["cache_fallback_sync_custom_hours"],
            self.settings_vars["cache_monitoring"],
            self.settings_vars["cache_respect_48h_skip"],
            self.settings_vars["cache_skip_hours"]
        ]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_security_settings(self, parent):
        """Create security settings section"""
        section_frame = ttk.LabelFrame(parent, text="🔐 Security Settings", padding=15)
        section_frame.pack(fill=tk.X, expand=True, pady=(0, 20))
        security_settings = self.current_settings.get("security", {})
        
        # Vespia integration
        var = tk.BooleanVar(value=security_settings.get("vespia_integration", True))
        check = ttk.Checkbutton(section_frame, text="Vespia integration", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["security_vespia"] = var
        
        # Credential encryption
        var = tk.BooleanVar(value=security_settings.get("credential_encryption", True))
        check = ttk.Checkbutton(section_frame, text="Credential encryption", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["security_encryption"] = var
        
        # Auto-lock timeout
        ttk.Label(section_frame, text="Auto-lock timeout:").pack(anchor=tk.W)
        timeout_options = self._build_auto_lock_options()
        current_timeout = str(security_settings.get("auto_lock_timeout", "30 minutes"))
        custom_timeout_minutes = int(security_settings.get("auto_lock_custom_minutes", 30) or 30)
        selected_timeout = current_timeout if current_timeout in timeout_options else "Custom"
        if selected_timeout == "Custom":
            parsed_minutes = self._parse_duration_to_minutes(current_timeout, custom_timeout_minutes)
            custom_timeout_minutes = max(1, min(525600, parsed_minutes))
        var = tk.StringVar(value=selected_timeout)
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=timeout_options,
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["security_timeout"] = var

        ttk.Label(section_frame, text="Custom auto-lock (minutes):").pack(anchor=tk.W)
        timeout_custom_var = tk.StringVar(value=str(custom_timeout_minutes))
        timeout_custom_entry = ttk.Entry(section_frame, textvariable=timeout_custom_var, width=10)
        timeout_custom_entry.pack(anchor=tk.W, pady=(0, 10))
        self.settings_vars["security_timeout_custom_minutes"] = timeout_custom_var

        def _toggle_timeout_custom(*_):
            is_custom = self.settings_vars["security_timeout"].get() == "Custom"
            timeout_custom_entry.configure(state='normal' if is_custom else 'disabled')
        _toggle_timeout_custom()
        combo.bind("<<ComboboxSelected>>", lambda _e: (_toggle_timeout_custom(), self.on_setting_change()))
        
        # Bind change events
        for var in [
            self.settings_vars["security_vespia"],
            self.settings_vars["security_encryption"],
            self.settings_vars["security_timeout"],
            self.settings_vars["security_timeout_custom_minutes"]
        ]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_dashboard_settings(self, parent):
        """Create dashboard settings section"""
        section_frame = ttk.LabelFrame(parent, text="📊 Dashboard Settings", padding=15)
        section_frame.pack(fill=tk.X, expand=True, pady=(0, 20))
        dashboard_settings = self.current_settings.get("dashboard", {})
        
        # Default dashboard
        ttk.Label(section_frame, text="Default dashboard:").pack(anchor=tk.W)
        var = tk.StringVar(value=dashboard_settings.get("default_dashboard", "Main Dashboard"))
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Main Dashboard", "API Dashboard", "Credential Manager"],
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["dashboard_default"] = var
        
        # Auto-start services
        var = tk.BooleanVar(value=dashboard_settings.get("auto_start_services", False))
        check = ttk.Checkbutton(section_frame, text="Auto-start services", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["dashboard_auto_start"] = var
        
        # Window positioning
        ttk.Label(section_frame, text="Window positioning:").pack(anchor=tk.W)
        var = tk.StringVar(value=dashboard_settings.get("window_positioning", "Centered"))
        combo = ttk.Combobox(section_frame, textvariable=var,
                           values=["Centered", "Top-left", "Top-right", "Bottom-left", "Bottom-right"],
                           state="readonly", width=20)
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
        section_frame.pack(fill=tk.X, expand=True, pady=(0, 20))
        api_settings = self.current_settings.get("api", {})
        
        # Rate limiting
        var = tk.BooleanVar(value=api_settings.get("rate_limiting", True))
        check = ttk.Checkbutton(section_frame, text="Rate limiting", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_rate_limiting"] = var
        
        # Fallback data
        var = tk.BooleanVar(value=api_settings.get("fallback_data", True))
        check = ttk.Checkbutton(section_frame, text="Fallback data", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_fallback"] = var
        
        # API monitoring
        var = tk.BooleanVar(value=api_settings.get("api_monitoring", True))
        check = ttk.Checkbutton(section_frame, text="API monitoring", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["api_monitoring"] = var
        
        # Bind change events
        for var in [self.settings_vars["api_rate_limiting"], self.settings_vars["api_fallback"], self.settings_vars["api_monitoring"]]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)

    def create_eu_mode_settings(self, parent):
        """Create EU compliance mode section."""
        section_frame = ttk.LabelFrame(parent, text="🇪🇺 EU-mode", padding=15)
        section_frame.pack(fill=tk.X, expand=True, pady=(0, 20))
        eu_settings = self.current_settings.get("eu_mode", {})

        # Master EU-mode toggle.
        enabled_var = tk.BooleanVar(value=bool(eu_settings.get("enabled", True)))
        enabled_check = ttk.Checkbutton(
            section_frame,
            text="Enable EU-related compliance flags",
            variable=enabled_var,
        )
        enabled_check.pack(anchor=tk.W, pady=(0, 8))
        self.settings_vars["eu_mode_enabled"] = enabled_var

        # Per-flag toggles (manual on/off for next assessment run).
        unlicensed_var = tk.BooleanVar(value=bool(eu_settings.get("enable_eu_unlicensed_stablecoin", True)))
        ttk.Checkbutton(
            section_frame,
            text="Flag: EU Unlicensed Stablecoin",
            variable=unlicensed_var,
        ).pack(anchor=tk.W)
        self.settings_vars["eu_flag_unlicensed_stablecoin"] = unlicensed_var

        regulatory_var = tk.BooleanVar(value=bool(eu_settings.get("enable_eu_regulatory_issues", True)))
        ttk.Checkbutton(
            section_frame,
            text="Flag: EU Regulatory Issue (external/compliance signals)",
            variable=regulatory_var,
        ).pack(anchor=tk.W)
        self.settings_vars["eu_flag_regulatory_issues"] = regulatory_var

        mica_non_compliant_var = tk.BooleanVar(value=bool(eu_settings.get("enable_mica_non_compliant", True)))
        ttk.Checkbutton(
            section_frame,
            text="Flag: MiCA Non-Compliant",
            variable=mica_non_compliant_var,
        ).pack(anchor=tk.W)
        self.settings_vars["eu_flag_mica_non_compliant"] = mica_non_compliant_var

        mica_whitepaper_var = tk.BooleanVar(value=bool(eu_settings.get("enable_mica_no_whitepaper", True)))
        ttk.Checkbutton(
            section_frame,
            text="Flag: MiCA No Whitepaper",
            variable=mica_whitepaper_var,
        ).pack(anchor=tk.W, pady=(0, 8))
        self.settings_vars["eu_flag_mica_no_whitepaper"] = mica_whitepaper_var

        # Dynamic allowlist behavior.
        dynamic_allowlist_var = tk.BooleanVar(value=bool(eu_settings.get("dynamic_allowlist_enabled", True)))
        ttk.Checkbutton(
            section_frame,
            text="Use dynamic regulated-stablecoin allowlist from data file",
            variable=dynamic_allowlist_var,
        ).pack(anchor=tk.W)
        self.settings_vars["eu_dynamic_allowlist_enabled"] = dynamic_allowlist_var

        registry_file = str(eu_settings.get("allowlist_registry_file", "eu_regulated_stablecoins.json") or "eu_regulated_stablecoins.json")
        ttk.Label(section_frame, text="Allowlist registry file (inside data/):").pack(anchor=tk.W, pady=(8, 0))
        registry_var = tk.StringVar(value=registry_file)
        registry_entry = ttk.Entry(section_frame, textvariable=registry_var, width=36)
        registry_entry.pack(anchor=tk.W, pady=(0, 8))
        self.settings_vars["eu_allowlist_registry_file"] = registry_var

        extra_symbols = eu_settings.get("allowlist_extra_symbols", [])
        if isinstance(extra_symbols, (list, tuple)):
            extra_symbols_text = ", ".join(str(s).strip().upper() for s in extra_symbols if str(s).strip())
        else:
            extra_symbols_text = str(extra_symbols or "").strip()

        ttk.Label(section_frame, text="Extra regulated symbols (comma-separated):").pack(anchor=tk.W)
        extra_symbols_var = tk.StringVar(value=extra_symbols_text)
        extra_symbols_entry = ttk.Entry(section_frame, textvariable=extra_symbols_var, width=52)
        extra_symbols_entry.pack(anchor=tk.W, pady=(0, 4))
        self.settings_vars["eu_allowlist_extra_symbols"] = extra_symbols_var

        ttk.Label(
            section_frame,
            text="Applies on the next risk assessment run.",
            foreground="#5d6d7e",
        ).pack(anchor=tk.W, pady=(0, 2))

        # Bind change events.
        for var in [
            self.settings_vars["eu_mode_enabled"],
            self.settings_vars["eu_flag_unlicensed_stablecoin"],
            self.settings_vars["eu_flag_regulatory_issues"],
            self.settings_vars["eu_flag_mica_non_compliant"],
            self.settings_vars["eu_flag_mica_no_whitepaper"],
            self.settings_vars["eu_dynamic_allowlist_enabled"],
            self.settings_vars["eu_allowlist_registry_file"],
            self.settings_vars["eu_allowlist_extra_symbols"],
        ]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)
    
    def create_display_settings(self, parent):
        """Create display settings section"""
        section_frame = ttk.LabelFrame(parent, text="📈 Display Settings", padding=15)
        section_frame.pack(fill=tk.X, expand=True, pady=(0, 20))
        display_settings = self.current_settings.get("display", {})
        
        # Theme
        ttk.Label(section_frame, text="Theme:").pack(anchor=tk.W)
        var = tk.StringVar(value=display_settings.get("theme", "System default"))
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["System default", "Light", "Dark"],
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["display_theme"] = var
        
        # Font size
        ttk.Label(section_frame, text="Font size:").pack(anchor=tk.W)
        var = tk.StringVar(value=display_settings.get("font_size", "Medium"))
        combo = ttk.Combobox(section_frame, textvariable=var,
                            values=["Small", "Medium", "Large"],
                            state="readonly", width=20)
        combo.pack(fill=tk.X, pady=(0, 10))
        self.settings_vars["display_font_size"] = var
        
        # Notifications
        var = tk.BooleanVar(value=display_settings.get("notifications", True))
        check = ttk.Checkbutton(section_frame, text="Notifications", variable=var)
        check.pack(anchor=tk.W)
        self.settings_vars["display_notifications"] = var
        
        # Bind change events
        for var in [
            self.settings_vars["display_theme"],
            self.settings_vars["display_font_size"],
            self.settings_vars["display_notifications"],
        ]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)

    def create_system_update_settings(self, parent):
        """Create system update settings section."""
        section_frame = ttk.LabelFrame(parent, text="🧩 System Update", padding=15)
        section_frame.pack(fill=tk.X, expand=True, pady=(0, 20))
        system_update_settings = self.current_settings.get("system_update", {})

        update_enabled_var = tk.BooleanVar(value=bool(system_update_settings.get("enabled", True)))
        update_enabled_check = ttk.Checkbutton(
            section_frame,
            text="Enable automatic dependency update checks",
            variable=update_enabled_var
        )
        update_enabled_check.pack(anchor=tk.W, pady=(0, 6))
        self.settings_vars["system_update_enabled"] = update_enabled_var

        check_on_startup_var = tk.BooleanVar(value=bool(system_update_settings.get("check_on_startup", True)))
        check_on_startup_check = ttk.Checkbutton(
            section_frame,
            text="Run update check on startup",
            variable=check_on_startup_var
        )
        check_on_startup_check.pack(anchor=tk.W, pady=(0, 6))
        self.settings_vars["system_update_check_on_startup"] = check_on_startup_var

        ttk.Label(section_frame, text="Auto-check interval:").pack(anchor=tk.W)
        interval_options = [
            "6 hours",
            "12 hours",
            "24 hours",
            "7 days",
            "30 days",
            "Custom",
        ]
        current_interval = str(system_update_settings.get("auto_check_interval", "7 days"))
        selected_interval = current_interval if current_interval in interval_options else "Custom"
        interval_var = tk.StringVar(value=selected_interval)
        interval_combo = ttk.Combobox(
            section_frame,
            textvariable=interval_var,
            values=interval_options,
            state="readonly",
            width=20,
        )
        interval_combo.pack(fill=tk.X, pady=(0, 6))
        self.settings_vars["system_update_interval"] = interval_var

        ttk.Label(section_frame, text="Custom interval (hours):").pack(anchor=tk.W)
        custom_hours = int(system_update_settings.get("auto_check_custom_hours", 168) or 168)
        custom_hours_var = tk.StringVar(value=str(max(1, custom_hours)))
        custom_hours_entry = ttk.Entry(section_frame, textvariable=custom_hours_var, width=10)
        custom_hours_entry.pack(anchor=tk.W, pady=(0, 6))
        self.settings_vars["system_update_custom_hours"] = custom_hours_var

        auto_install_var = tk.BooleanVar(value=bool(system_update_settings.get("auto_install_safe_updates", False)))
        auto_install_check = ttk.Checkbutton(
            section_frame,
            text="Auto-install updates when safety check passes",
            variable=auto_install_var
        )
        auto_install_check.pack(anchor=tk.W, pady=(0, 6))
        self.settings_vars["system_update_auto_install"] = auto_install_var

        safety_var = tk.BooleanVar(value=bool(system_update_settings.get("safety_check_enabled", True)))
        safety_check = ttk.Checkbutton(
            section_frame,
            text="Run pip dry-run safety validation before install",
            variable=safety_var
        )
        safety_check.pack(anchor=tk.W, pady=(0, 8))
        self.settings_vars["system_update_safety_check"] = safety_var

        timeout_value = int(system_update_settings.get("max_update_timeout_seconds", 1800) or 1800)
        ttk.Label(section_frame, text="Install timeout (seconds):").pack(anchor=tk.W)
        timeout_var = tk.StringVar(value=str(max(120, timeout_value)))
        timeout_entry = ttk.Entry(section_frame, textvariable=timeout_var, width=12)
        timeout_entry.pack(anchor=tk.W, pady=(0, 8))
        self.settings_vars["system_update_timeout_seconds"] = timeout_var

        def _toggle_custom_interval_entry(*_):
            is_custom = self.settings_vars["system_update_interval"].get() == "Custom"
            custom_hours_entry.configure(state="normal" if is_custom else "disabled")

        _toggle_custom_interval_entry()
        interval_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: (_toggle_custom_interval_entry(), self.on_setting_change())
        )

        self.system_update_last_check_label = ttk.Label(section_frame, text="Last check: Never")
        self.system_update_last_check_label.pack(anchor=tk.W, pady=(2, 0))
        self.system_update_last_update_label = ttk.Label(section_frame, text="Last update: Never")
        self.system_update_last_update_label.pack(anchor=tk.W, pady=(2, 0))
        self.system_update_outdated_label = ttk.Label(section_frame, text="Pending updates: unknown")
        self.system_update_outdated_label.pack(anchor=tk.W, pady=(2, 6))
        ttk.Label(
            section_frame,
            textvariable=self.system_update_status_var,
            foreground="#4a4a4a",
        ).pack(anchor=tk.W, pady=(0, 6))

        self.system_update_button = ttk.Button(
            section_frame,
            text="Check Libraries Now",
            command=self.manual_check_libraries,
        )
        self.system_update_button.pack(anchor=tk.W, pady=(0, 2))

        # Bind change events
        for var in [
            self.settings_vars["system_update_enabled"],
            self.settings_vars["system_update_check_on_startup"],
            self.settings_vars["system_update_interval"],
            self.settings_vars["system_update_custom_hours"],
            self.settings_vars["system_update_auto_install"],
            self.settings_vars["system_update_safety_check"],
            self.settings_vars["system_update_timeout_seconds"],
        ]:
            if hasattr(var, 'trace_add'):
                var.trace_add('write', self.on_setting_change)
            elif hasattr(var, 'trace'):
                var.trace('w', self.on_setting_change)

    def _read_system_update_settings_from_ui(self):
        """Read System Update controls from UI vars (or persisted settings fallback)."""
        persisted = self.current_settings.get("system_update", {})
        try:
            custom_hours = int(str(self.settings_vars.get("system_update_custom_hours").get()).strip())
        except Exception:
            custom_hours = int(persisted.get("auto_check_custom_hours", 168) or 168)
        custom_hours = max(1, min(24 * 365, custom_hours))

        try:
            timeout_seconds = int(str(self.settings_vars.get("system_update_timeout_seconds").get()).strip())
        except Exception:
            timeout_seconds = int(persisted.get("max_update_timeout_seconds", 1800) or 1800)
        timeout_seconds = max(120, min(7200, timeout_seconds))

        return {
            "enabled": bool(self.settings_vars.get("system_update_enabled").get() if "system_update_enabled" in self.settings_vars else persisted.get("enabled", True)),
            "check_on_startup": bool(self.settings_vars.get("system_update_check_on_startup").get() if "system_update_check_on_startup" in self.settings_vars else persisted.get("check_on_startup", True)),
            "auto_check_interval": str(self.settings_vars.get("system_update_interval").get() if "system_update_interval" in self.settings_vars else persisted.get("auto_check_interval", "7 days")),
            "auto_check_custom_hours": custom_hours,
            "auto_install_safe_updates": bool(self.settings_vars.get("system_update_auto_install").get() if "system_update_auto_install" in self.settings_vars else persisted.get("auto_install_safe_updates", False)),
            "safety_check_enabled": bool(self.settings_vars.get("system_update_safety_check").get() if "system_update_safety_check" in self.settings_vars else persisted.get("safety_check_enabled", True)),
            "max_update_timeout_seconds": timeout_seconds,
        }

    def refresh_system_update_labels(self):
        """Refresh text labels showing dependency update/check recency."""
        self.update_state = load_update_state()
        if self.system_update_last_check_label is not None:
            self.system_update_last_check_label.config(
                text=f"Last check: {humanize_elapsed(self.update_state.get('last_check_at'))}"
            )
        if self.system_update_last_update_label is not None:
            self.system_update_last_update_label.config(
                text=f"Last update: {humanize_elapsed(self.update_state.get('last_update_at'))}"
            )
        if self.system_update_outdated_label is not None:
            outdated_count = int(self.update_state.get("last_outdated_count", 0) or 0)
            status = str(self.update_state.get("last_check_status", "never"))
            self.system_update_outdated_label.config(
                text=f"Pending updates: {outdated_count} (status: {status})"
            )

    def _schedule_system_update_counter_tick(self):
        self.refresh_system_update_labels()
        self.root.after(4000, self._schedule_system_update_counter_tick)

    def _schedule_system_update_auto_tick(self, initial_delay_ms=60000):
        def _tick():
            if not self.system_update_busy:
                config = self._read_system_update_settings_from_ui()
                state = load_update_state()
                if should_run_auto_check(config, state):
                    self._start_library_check(manual=False, auto_install=bool(config.get("auto_install_safe_updates", False)))
            self._schedule_system_update_auto_tick(initial_delay_ms=60000)

        self.root.after(initial_delay_ms, _tick)

    def _set_system_update_busy(self, busy: bool, status_text: str = ""):
        self.system_update_busy = bool(busy)
        if status_text:
            self.system_update_status_var.set(status_text)
        if self.system_update_button is not None:
            self.system_update_button.config(state="disabled" if busy else "normal")

    def manual_check_libraries(self):
        """Run manual dependency check and optionally install safe updates."""
        self._start_library_check(manual=True, auto_install=False)

    def _start_library_check(self, manual: bool, auto_install: bool):
        if self.system_update_busy:
            return
        mode = "manual" if manual else "automatic"
        self._set_system_update_busy(True, f"Running {mode} dependency check...")
        worker = threading.Thread(
            target=self._library_check_worker,
            args=(manual, auto_install),
            daemon=True,
        )
        worker.start()

    def _library_check_worker(self, manual: bool, auto_install: bool):
        config = self._read_system_update_settings_from_ui()
        state = load_update_state()
        check_result = check_outdated_packages(timeout_seconds=300)
        state["last_check_at"] = utc_now_iso()
        state["last_check_duration_seconds"] = float(check_result.get("duration_seconds", 0.0) or 0.0)
        state["last_check_output_tail"] = (
            (check_result.get("stdout_tail") or "")
            + ("\n" + check_result.get("stderr_tail") if check_result.get("stderr_tail") else "")
        ).strip()

        if not bool(check_result.get("ok", False)):
            state["last_check_status"] = "failed"
            state["last_error"] = str(check_result.get("error", "Unknown check error"))
            save_update_state(state)
            self.root.after(0, lambda: self._finish_system_update(
                f"Check failed: {state['last_error']}",
                show_error=manual,
                show_popup=manual,
            ))
            return

        packages = check_result.get("packages", []) or []
        state["last_outdated_packages"] = packages
        state["last_outdated_count"] = len(packages)
        state["last_error"] = ""

        if not packages:
            state["last_check_status"] = "up_to_date"
            save_update_state(state)
            self.root.after(0, lambda: self._finish_system_update(
                "Dependencies are already up to date.",
                show_popup=manual,
            ))
            return

        state["last_check_status"] = "updates_available"
        save_update_state(state)

        if auto_install:
            self._run_install_worker(
                config=config,
                manual=manual,
                available_packages=list(packages),
            )
            return

        if manual:
            self.root.after(0, lambda p=list(packages): self._prompt_manual_install(p))
        else:
            self.root.after(0, lambda: self._finish_system_update(
                f"{len(packages)} update(s) available. Auto-install is disabled.",
                show_popup=manual,
            ))

    def _prompt_manual_install(self, packages):
        package_list = list(packages or [])
        package_count = len(package_list)
        self._set_system_update_busy(False, f"{package_count} update(s) found. Awaiting confirmation.")
        self.refresh_system_update_labels()
        should_install = messagebox.askyesno(
            "Library Updates Available",
            (
                f"{package_count} package update(s) are available.\n\n"
                "Run safety validation and install updates now?"
            ),
        )
        if should_install:
            self._start_library_install(manual=True, available_packages=package_list)

    @staticmethod
    def _package_spec_from_outdated_entry(entry):
        """Build pip install spec from pip list --outdated row."""
        if not isinstance(entry, dict):
            return ""
        name = str(entry.get("name", "")).strip()
        latest = str(entry.get("latest_version", "")).strip()
        if not name:
            return ""
        if latest:
            return f"{name}=={latest}"
        return name

    def _start_library_install(self, manual: bool, available_packages=None, selected_package_specs=None):
        if self.system_update_busy:
            return
        if selected_package_specs:
            self._set_system_update_busy(True, "Running safety checks for selected packages...")
        else:
            self._set_system_update_busy(True, "Running safety checks before install...")
        config = self._read_system_update_settings_from_ui()
        worker = threading.Thread(
            target=self._run_install_worker,
            kwargs={
                "config": config,
                "manual": manual,
                "available_packages": list(available_packages or []),
                "selected_package_specs": list(selected_package_specs or []),
            },
            daemon=True,
        )
        worker.start()

    def _show_selective_safety_dialog(self, available_packages, safety_result):
        """Show package selector when safety check fails, allowing selective install."""
        packages = [p for p in (available_packages or []) if isinstance(p, dict)]
        if not packages:
            self._finish_system_update(
                "Safety dry-run failed and no package list is available for selective install.",
                show_error=True,
                show_popup=True,
            )
            return

        package_names = [str(p.get("name", "")).strip() for p in packages if str(p.get("name", "")).strip()]

        def _norm_pkg(name):
            return str(name or "").strip().lower().replace("_", "-")

        selectable_lookup = {_norm_pkg(name): name for name in package_names}
        failed_candidates = extract_failed_packages_from_pip_output(
            safety_result.get("stdout_tail"),
            safety_result.get("stderr_tail"),
            package_names,
        )
        failed_names = set()
        failed_external = []
        for raw_name in failed_candidates:
            normalized = _norm_pkg(raw_name)
            if normalized in selectable_lookup:
                failed_names.add(selectable_lookup[normalized])
            elif str(raw_name or "").strip():
                failed_external.append(str(raw_name).strip())
        failed_external = sorted(list(dict.fromkeys(failed_external)), key=lambda x: x.lower())
        failure_detail_lines = extract_pip_failure_highlight_lines(
            safety_result.get("stdout_tail"),
            safety_result.get("stderr_tail"),
            max_lines=24,
        )
        failed_norm_set = {_norm_pkg(name) for name in failed_names}

        dialog = tk.Toplevel(self.root)
        dialog.title("Safety Check Failed - Select Packages")
        dialog.geometry("860x620")
        dialog.minsize(760, 520)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        summary_text = (
            "Safety dry-run failed for the full update set.\n"
            "Uncheck problematic packages and install the rest."
        )
        ttk.Label(frame, text=summary_text, justify="left").pack(anchor=tk.W, pady=(0, 8))

        failed_text = ", ".join(sorted(failed_names)) if failed_names else "None auto-detected in selectable update list."
        ttk.Label(
            frame,
            text=f"Detected problematic package(s) in this list: {failed_text}",
            foreground="#c0392b",
        ).pack(anchor=tk.W, pady=(0, 4))

        if failed_external:
            external_text = ", ".join(failed_external)
            ttk.Label(
                frame,
                text=(
                    "Likely blocking requirement(s) not in this selectable list "
                    f"(auto-skipped by selective install): {external_text}"
                ),
                foreground="#d35400",
                justify="left",
            ).pack(anchor=tk.W, pady=(0, 8))

        details_box = ttk.LabelFrame(frame, text="Safety Check Details")
        details_box.pack(fill=tk.X, pady=(0, 8))
        details_text = tk.Text(details_box, height=7, wrap="word", borderwidth=0, highlightthickness=0)
        details_scroll = ttk.Scrollbar(details_box, orient="vertical", command=details_text.yview)
        details_text.configure(yscrollcommand=details_scroll.set)
        details_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        if failure_detail_lines:
            details_text.insert("1.0", "\n".join(failure_detail_lines))
        else:
            details_text.insert("1.0", "No specific pip failure lines were captured. Check terminal output for full details.")
        details_text.configure(state="disabled")

        list_container = ttk.Frame(frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(list_container, highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        options_frame = ttk.Frame(canvas)
        options_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        options_window = canvas.create_window((0, 0), window=options_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(options_window, width=max(100, int(e.width) - 2)))
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        selections = []
        for pkg in packages:
            name = str(pkg.get("name", "")).strip()
            if not name:
                continue
            current_v = str(pkg.get("version", "")).strip()
            latest_v = str(pkg.get("latest_version", "")).strip()
            label = f"{name}  ({current_v or '?'} -> {latest_v or 'latest'})"
            is_flagged = _norm_pkg(name) in failed_norm_set
            default_checked = not is_flagged
            var = tk.BooleanVar(value=default_checked)
            cb = tk.Checkbutton(options_frame, text=label, variable=var, anchor="w", justify="left")
            if is_flagged:
                cb.configure(fg="#c0392b")
            cb.pack(fill=tk.X, anchor=tk.W, padx=2, pady=1)
            selections.append((pkg, var))

        button_row = ttk.Frame(frame)
        button_row.pack(fill=tk.X, pady=(10, 0))

        def _select_all():
            for _, var in selections:
                var.set(True)

        def _select_safe_only():
            for pkg_row, var in selections:
                pkg_name = str(pkg_row.get("name", "")).strip()
                var.set(_norm_pkg(pkg_name) not in failed_norm_set)

        def _clear_all():
            for _, var in selections:
                var.set(False)

        def _install_selected():
            chosen = [pkg for pkg, var in selections if bool(var.get())]
            if not chosen:
                messagebox.showwarning("System Update", "Select at least one package to continue.")
                return
            specs = [self._package_spec_from_outdated_entry(pkg) for pkg in chosen]
            specs = [x for x in specs if x]
            if not specs:
                messagebox.showwarning("System Update", "No valid package specs selected.")
                return
            dialog.destroy()
            self._start_library_install(
                manual=True,
                available_packages=chosen,
                selected_package_specs=specs,
            )

        ttk.Button(button_row, text="Select All", command=_select_all).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Select Safe Only", command=_select_safe_only).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(button_row, text="Clear All", command=_clear_all).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(button_row, text="Cancel", command=lambda: (dialog.destroy(), self._finish_system_update("Install cancelled.", show_popup=False))).pack(side=tk.RIGHT)
        ttk.Button(button_row, text="Install Selected", command=_install_selected).pack(side=tk.RIGHT, padx=(0, 6))

    def _run_install_worker(self, config, manual: bool, available_packages=None, selected_package_specs=None):
        state = load_update_state()
        timeout_seconds = int(config.get("max_update_timeout_seconds", 1800) or 1800)
        safety_enabled = bool(config.get("safety_check_enabled", True))
        package_specs = [str(x).strip() for x in (selected_package_specs or []) if str(x).strip()]
        user_selected_specs = bool(package_specs)
        is_selective_install = bool(package_specs)
        package_name_candidates = [
            str(item.get("name", "")).strip()
            for item in (available_packages or [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]

        # Default "Update Libraries Now" should target the currently outdated packages,
        # not pinned requirements entries. Otherwise the install can succeed but keep the
        # same outdated-count unchanged.
        if (not is_selective_install) and available_packages:
            inferred_specs = [
                self._package_spec_from_outdated_entry(item)
                for item in available_packages
                if isinstance(item, dict)
            ]
            inferred_specs = [spec for spec in inferred_specs if spec]
            if inferred_specs:
                package_specs = list(dict.fromkeys(inferred_specs))
                is_selective_install = True

        if safety_enabled:
            safety = run_safety_dry_run(
                requirements_path=REQUIREMENTS_FILE,
                timeout_seconds=min(timeout_seconds, 900),
                package_specs=package_specs if is_selective_install else None,
            )
            if not bool(safety.get("ok", False)):
                state["last_update_status"] = "blocked_by_safety_check"
                state["last_error"] = str(safety.get("error", "Safety dry-run failed"))
                state["last_update_output_tail"] = (
                    (safety.get("stdout_tail") or "")
                    + ("\n" + safety.get("stderr_tail") if safety.get("stderr_tail") else "")
                ).strip()
                save_update_state(state)
                failed_pkgs = extract_failed_packages_from_pip_output(
                    safety.get("stdout_tail"),
                    safety.get("stderr_tail"),
                    package_name_candidates,
                )
                if manual and (not user_selected_specs):
                    self.root.after(0, lambda: self._set_system_update_busy(False, "Safety check failed. Review package list."))
                    self.root.after(0, lambda pkgs=list(available_packages or []), sr=dict(safety): self._show_selective_safety_dialog(pkgs, sr))
                else:
                    failed_suffix = f" Failing package(s): {', '.join(failed_pkgs)}." if failed_pkgs else ""
                    self.root.after(0, lambda: self._finish_system_update(
                        f"Safety dry-run failed. Update not installed.{failed_suffix}",
                        show_error=manual,
                        show_popup=manual,
                    ))
                return

        install_result = install_requirements_upgrade(
            requirements_path=REQUIREMENTS_FILE,
            timeout_seconds=timeout_seconds,
            package_specs=package_specs if is_selective_install else None,
        )
        if not bool(install_result.get("ok", False)):
            state["last_update_status"] = "failed"
            state["last_error"] = str(install_result.get("error", "Install failed"))
            state["last_update_duration_seconds"] = float(install_result.get("duration_seconds", 0.0) or 0.0)
            state["last_update_output_tail"] = (
                (install_result.get("stdout_tail") or "")
                + ("\n" + install_result.get("stderr_tail") if install_result.get("stderr_tail") else "")
            ).strip()
            save_update_state(state)
            self.root.after(0, lambda: self._finish_system_update(
                "Library install failed. See terminal/log output for details.",
                show_error=manual,
                show_popup=manual,
            ))
            return

        verify_result = run_pip_check()
        state["last_update_duration_seconds"] = float(install_result.get("duration_seconds", 0.0) or 0.0)
        state["last_update_at"] = utc_now_iso()
        state["last_update_output_tail"] = (
            (install_result.get("stdout_tail") or "")
            + ("\n" + install_result.get("stderr_tail") if install_result.get("stderr_tail") else "")
        ).strip()
        # Immediately re-check outdated packages so "Pending updates" reflects post-install reality.
        post_check = check_outdated_packages(timeout_seconds=300)
        if bool(post_check.get("ok", False)):
            remaining_packages = post_check.get("packages", []) or []
            state["last_check_at"] = utc_now_iso()
            state["last_check_duration_seconds"] = float(post_check.get("duration_seconds", 0.0) or 0.0)
            state["last_check_output_tail"] = (
                (post_check.get("stdout_tail") or "")
                + ("\n" + post_check.get("stderr_tail") if post_check.get("stderr_tail") else "")
            ).strip()
            state["last_outdated_packages"] = remaining_packages
            state["last_outdated_count"] = len(remaining_packages)
            state["last_check_status"] = "up_to_date" if not remaining_packages else "updates_available"
        else:
            remaining_packages = state.get("last_outdated_packages", []) or []
            state["last_check_status"] = "failed"
            state["last_error"] = str(post_check.get("error", state.get("last_error", "")))

        if bool(verify_result.get("ok", False)):
            state["last_update_status"] = "success"
            state["last_error"] = ""
            save_update_state(state)
            if remaining_packages:
                self.root.after(0, lambda: self._finish_system_update(
                    f"Libraries updated, but {len(remaining_packages)} update(s) are still pending.",
                    show_popup=manual,
                ))
            else:
                self.root.after(0, lambda: self._finish_system_update(
                    "Libraries updated successfully. No pending updates remain.",
                    show_popup=manual,
                ))
        else:
            state["last_update_status"] = "installed_with_warnings"
            state["last_error"] = str(verify_result.get("error", "pip check reported issues"))
            state["last_update_output_tail"] = (
                state.get("last_update_output_tail", "")
                + "\n"
                + (verify_result.get("stdout_tail") or "")
                + ("\n" + verify_result.get("stderr_tail") if verify_result.get("stderr_tail") else "")
            ).strip()
            save_update_state(state)
            self.root.after(0, lambda: self._finish_system_update(
                "Install completed, but pip check reported dependency warnings.",
                show_error=manual,
                show_popup=manual,
            ))

    def _finish_system_update(self, message: str, show_error: bool = False, show_popup: bool = False):
        self._set_system_update_busy(False, message)
        self.refresh_system_update_labels()
        if not show_popup:
            return
        if show_error:
            messagebox.showwarning("System Update", message)
        elif message:
            messagebox.showinfo("System Update", message)
    
    def _store_initial_values(self):
        """Store initial values for change detection"""
        for key, var in self.settings_vars.items():
            if hasattr(var, 'get'):
                self.initial_values[key] = var.get()
    
    def _has_changes(self):
        """Check if any settings have changed from initial values"""
        for key, var in self.settings_vars.items():
            if hasattr(var, 'get'):
                current_value = var.get()
                initial_value = self.initial_values.get(key)
                if current_value != initial_value:
                    return True
        return False
    
    def on_setting_change(self, *args):
        """Called when any setting is changed"""
        # Don't process changes during initialization
        if hasattr(self, 'initializing') and self.initializing:
            return
            
        if self._has_changes():
            self.apply_btn.config(state='normal')
            # Remove faded style when enabled
            try:
                self.apply_btn.configure(style='TButton')
            except:
                pass
        else:
            self.apply_btn.config(state='disabled')
            # Apply faded style when disabled
            try:
                self.apply_btn.configure(style='Disabled.TButton')
            except:
                pass
    
    def apply_changes(self):
        """Apply the changes and save settings"""
        try:
            # Ensure required sections exist for legacy settings files.
            self.current_settings.setdefault("cache", {})
            self.current_settings.setdefault("security", {})
            self.current_settings.setdefault("dashboard", {})
            self.current_settings.setdefault("api", {})
            self.current_settings.setdefault("eu_mode", {})
            self.current_settings.setdefault("display", {})

            # Update current settings with new values
            self.current_settings["cache"]["auto_refresh_interval"] = self.settings_vars["cache_auto_refresh"].get()
            cache_retention_choice = self.settings_vars["cache_retention"].get()
            if cache_retention_choice == "Custom":
                try:
                    custom_days = int(str(self.settings_vars["cache_retention_custom_days"].get()).strip())
                except Exception:
                    custom_days = 0
                if custom_days < 1 or custom_days > 365:
                    messagebox.showerror("Invalid Cache Retention", "Custom cache retention must be between 1 and 365 days.")
                    return
                self.current_settings["cache"]["cache_retention_custom_days"] = custom_days
                self.current_settings["cache"]["cache_retention"] = f"{custom_days} day" + ("" if custom_days == 1 else "s")
            else:
                self.current_settings["cache"]["cache_retention"] = self._normalize_cache_retention_text(cache_retention_choice)
                parsed_days = int(round(self._parse_duration_to_hours(cache_retention_choice, 24) / 24.0))
                self.current_settings["cache"]["cache_retention_custom_days"] = max(1, min(365, parsed_days))
            fallback_sync_choice = self.settings_vars["cache_fallback_sync_interval"].get()
            if fallback_sync_choice == "Custom":
                try:
                    custom_hours = int(str(self.settings_vars["cache_fallback_sync_custom_hours"].get()).strip())
                except Exception:
                    custom_hours = 0
                if custom_hours < 1 or custom_hours > 24 * 365:
                    messagebox.showerror("Invalid Fallback Sync", "Custom fallback sync must be between 1 and 8760 hours.")
                    return
                self.current_settings["cache"]["fallback_sync_custom_hours"] = custom_hours
                self.current_settings["cache"]["fallback_sync_interval"] = f"{custom_hours} hour" + ("" if custom_hours == 1 else "s")
            else:
                self.current_settings["cache"]["fallback_sync_interval"] = fallback_sync_choice
                parsed_hours = int(round(self._parse_duration_to_hours(fallback_sync_choice, 4)))
                self.current_settings["cache"]["fallback_sync_custom_hours"] = max(1, min(24 * 365, parsed_hours))
            self.current_settings["cache"]["background_monitoring"] = self.settings_vars["cache_monitoring"].get()
            # 48h skip policy
            self.current_settings["cache"]["respect_48h_metric_skip"] = bool(self.settings_vars["cache_respect_48h_skip"].get())
            # sanitize hours
            try:
                hours_val = int(str(self.settings_vars["cache_skip_hours"].get()).strip())
                if hours_val <= 0:
                    hours_val = 48
            except Exception:
                hours_val = 48
            self.current_settings["cache"]["metric_skip_hours"] = hours_val
            
            self.current_settings["security"]["vespia_integration"] = self.settings_vars["security_vespia"].get()
            self.current_settings["security"]["credential_encryption"] = self.settings_vars["security_encryption"].get()
            timeout_choice = self.settings_vars["security_timeout"].get()
            if timeout_choice == "Custom":
                try:
                    custom_minutes = int(str(self.settings_vars["security_timeout_custom_minutes"].get()).strip())
                except Exception:
                    custom_minutes = 0
                if custom_minutes < 1 or custom_minutes > 525600:
                    messagebox.showerror("Invalid Auto-lock Timeout", "Custom auto-lock timeout must be between 1 and 525600 minutes.")
                    return
                self.current_settings["security"]["auto_lock_custom_minutes"] = custom_minutes
                self.current_settings["security"]["auto_lock_timeout"] = self._normalize_auto_lock_text(f"{custom_minutes} minutes")
            else:
                normalized_timeout = self._normalize_auto_lock_text(timeout_choice)
                self.current_settings["security"]["auto_lock_timeout"] = normalized_timeout
                self.current_settings["security"]["auto_lock_custom_minutes"] = self._parse_duration_to_minutes(normalized_timeout, 30)
            
            self.current_settings["dashboard"]["default_dashboard"] = self.settings_vars["dashboard_default"].get()
            self.current_settings["dashboard"]["auto_start_services"] = self.settings_vars["dashboard_auto_start"].get()
            self.current_settings["dashboard"]["window_positioning"] = self.settings_vars["dashboard_positioning"].get()
            
            self.current_settings["api"]["rate_limiting"] = self.settings_vars["api_rate_limiting"].get()
            self.current_settings["api"]["fallback_data"] = self.settings_vars["api_fallback"].get()
            self.current_settings["api"]["api_monitoring"] = self.settings_vars["api_monitoring"].get()
            # Persist advanced reliability/rate-limit defaults so they can be tuned centrally.
            self.current_settings["api"].setdefault("conditional_requests", True)
            self.current_settings["api"].setdefault("adaptive_backoff", True)
            self.current_settings["api"].setdefault("max_parallel_requests", 4)
            self.current_settings["api"].setdefault("retry_backoff_seconds", 1.5)
            self.current_settings["api"].setdefault("request_jitter_ms", 200)
            self.current_settings["api"].setdefault("timeout", 30)
            self.current_settings["api"].setdefault("retry_attempts", 3)
            self.current_settings["cache"].setdefault("force_live_override_on_change", True)
            self.current_settings["cache"].setdefault("metric_drift_threshold_pct", 2.0)

            registry_name = str(self.settings_vars["eu_allowlist_registry_file"].get() or "").strip()
            if not registry_name:
                registry_name = "eu_regulated_stablecoins.json"
            registry_name = os.path.basename(registry_name)
            if not registry_name.lower().endswith(".json"):
                registry_name = f"{registry_name}.json"

            raw_extra_symbols = str(self.settings_vars["eu_allowlist_extra_symbols"].get() or "")
            extra_symbols = []
            for part in raw_extra_symbols.replace("\n", ",").split(","):
                candidate = str(part).strip().upper()
                if candidate:
                    extra_symbols.append(candidate)
            extra_symbols = sorted(set(extra_symbols))

            self.current_settings["eu_mode"]["enabled"] = bool(self.settings_vars["eu_mode_enabled"].get())
            self.current_settings["eu_mode"]["enable_eu_unlicensed_stablecoin"] = bool(self.settings_vars["eu_flag_unlicensed_stablecoin"].get())
            self.current_settings["eu_mode"]["enable_eu_regulatory_issues"] = bool(self.settings_vars["eu_flag_regulatory_issues"].get())
            self.current_settings["eu_mode"]["enable_mica_non_compliant"] = bool(self.settings_vars["eu_flag_mica_non_compliant"].get())
            self.current_settings["eu_mode"]["enable_mica_no_whitepaper"] = bool(self.settings_vars["eu_flag_mica_no_whitepaper"].get())
            self.current_settings["eu_mode"]["dynamic_allowlist_enabled"] = bool(self.settings_vars["eu_dynamic_allowlist_enabled"].get())
            self.current_settings["eu_mode"]["allowlist_registry_file"] = registry_name
            self.current_settings["eu_mode"]["allowlist_extra_symbols"] = extra_symbols
            
            self.current_settings["display"]["theme"] = self.settings_vars["display_theme"].get()
            self.current_settings["display"]["font_size"] = self.settings_vars["display_font_size"].get()
            self.current_settings["display"]["notifications"] = self.settings_vars["display_notifications"].get()

            system_update_cfg = self._read_system_update_settings_from_ui()
            self.current_settings["system_update"] = dict(DEFAULT_SYSTEM_UPDATE_SETTINGS)
            self.current_settings["system_update"].update(system_update_cfg)
            
            # Apply theme changes immediately
            self.apply_theme_changes()
            
            # Save settings
            if self.save_settings():
                messagebox.showinfo("Success", "Settings applied successfully!")
                # Update initial values to current values
                self._store_initial_values()
                self.apply_btn.config(state='disabled')
                self.refresh_system_update_labels()
                # Re-apply faded style after disabling
                try:
                    self.apply_btn.configure(style='Disabled.TButton')
                except:
                    pass
            else:
                messagebox.showerror("Error", "Failed to save settings!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error applying settings: {e}")
    
    def apply_theme_changes(self):
        """Apply theme changes to the current window"""
        try:
            selected_theme = self.settings_vars["display_theme"].get()
            
            # Define theme colors
            if selected_theme == "Light":
                bg_color = '#ffffff'
                fg_color = '#2c3e50'
                frame_bg = '#ffffff'
                label_bg = '#ffffff'
                entry_bg = '#ffffff'
                entry_fg = '#2c3e50'
                button_bg = '#3498db'
                button_fg = '#ffffff'
            elif selected_theme == "Dark":
                bg_color = '#2c3e50'
                fg_color = '#ecf0f1'
                frame_bg = '#2c3e50'
                label_bg = '#34495e'
                entry_bg = '#34495e'
                entry_fg = '#ecf0f1'
                button_bg = '#3498db'
                button_fg = '#ffffff'
            else:
                # System default - use current system colors
                return
            
            # Apply theme to current window
            self.root.configure(bg=bg_color)
            
            # Update all widgets in the settings window
            self.update_widget_colors(self.root, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg)
            
            # Force update
            self.root.update_idletasks()
            self.root.update()
            
        except Exception as e:
            print(f"Error applying theme changes: {e}")
    
    def update_widget_colors(self, widget, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg):
        """Update widget colors recursively"""
        try:
            # Update current widget
            if isinstance(widget, tk.Label):
                widget.configure(bg=label_bg, fg=fg_color)
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=entry_bg, fg=entry_fg, insertbackground=entry_fg)
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=frame_bg)
            elif isinstance(widget, tk.Button):
                widget.configure(bg=button_bg, fg=button_fg)
            
            # Update all children
            for child in widget.winfo_children():
                self.update_widget_colors(child, bg_color, fg_color, frame_bg, label_bg, entry_bg, entry_fg, button_bg, button_fg)
                
        except Exception as e:
            # Silently ignore errors for ttk widgets
            pass
    
    def on_closing(self):
        """Handle window closing"""
        self.root.destroy()
    
    def run(self):
        """Run the settings window"""
        self.root.mainloop()

if __name__ == "__main__":
    app = SettingsWindow()
    app.run()
